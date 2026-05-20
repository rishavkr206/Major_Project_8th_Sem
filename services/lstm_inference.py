"""
LSTM inference service — loads trained dual-head Keras model + feature scaler.

Artifacts (same layout as `pipelines/feature_engineering.py` + `ml/lstm_training.py`):
  {LSTM_ARTIFACTS_DIR}/scaler.pkl
  {LSTM_ARTIFACTS_DIR}/feature_cols.pkl
  {LSTM_ARTIFACTS_DIR}/y_reg_mean.pkl
  {LSTM_ARTIFACTS_DIR}/y_reg_std.pkl
  {LSTM_ARTIFACTS_DIR}/models/lstm_model.keras  (or lstm_model.keras in that dir)

Override directory with env `LSTM_ARTIFACTS_DIR`. Otherwise tries `ml/simulated_phase1/`, then `ml/`.
"""

from __future__ import annotations

import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _candidate_artifact_dirs() -> List[str]:
    dirs: List[str] = []
    env = os.environ.get("LSTM_ARTIFACTS_DIR")
    if env:
        dirs.append(os.path.abspath(env))
    dirs.append(os.path.join(REPO_ROOT, "ml", "simulated_phase1"))
    dirs.append(os.path.join(REPO_ROOT, "ml"))
    seen: set[str] = set()
    out: List[str] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _find_model_path(base: str) -> Optional[str]:
    for rel in ("models/lstm_model.keras", "lstm_model.keras"):
        p = os.path.join(base, *rel.split("/"))
        if os.path.isfile(p):
            return p
    return None


def _pick_artifact_dir() -> Optional[str]:
    for d in _candidate_artifact_dirs():
        if not os.path.isdir(d):
            continue
        need = ("scaler.pkl", "feature_cols.pkl", "y_reg_mean.pkl", "y_reg_std.pkl")
        if not all(os.path.isfile(os.path.join(d, f)) for f in need):
            continue
        if _find_model_path(d):
            return d
    return None


class LSTMForecaster:
    """Lazy-loads the Ventilator LSTM when TensorFlow + artifacts are available."""

    def __init__(self) -> None:
        self._model = None
        self._scaler = None
        self._y_mean: Optional[float] = None
        self._y_std: Optional[float] = None
        self._feat_cols: Optional[List[str]] = None
        self._seq_len: Optional[int] = None
        self._artifact_dir: Optional[str] = None
        self._model_path: Optional[str] = None
        self._load_error: Optional[str] = None

    @staticmethod
    def probe_artifacts() -> Dict[str, Any]:
        base = _pick_artifact_dir()
        if not base:
            return {
                "artifacts_found": False,
                "artifact_dir": None,
                "model_path": None,
                "hint": "Run: python pipelines/run_phase1.py && python ml/lstm_training.py "
                "(set LSTM_ARTIFACTS_DIR=ml/simulated_phase1 if pickles live there)",
            }
        mp = _find_model_path(base)
        return {
            "artifacts_found": True,
            "artifact_dir": base,
            "model_path": mp,
            "hint": None,
        }

    def ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        base = _pick_artifact_dir()
        if not base:
            self._load_error = "No directory with scaler.pkl, feature_cols.pkl, y_reg_mean/std, and lstm_model.keras"
            return False
        mp = _find_model_path(base)
        if not mp:
            self._load_error = "lstm_model.keras not found under artifact dir"
            return False
        try:
            import tensorflow as tf
        except ImportError as exc:
            self._load_error = f"tensorflow not installed: {exc}"
            return False
        try:
            with open(os.path.join(base, "scaler.pkl"), "rb") as fh:
                self._scaler = pickle.load(fh)
            with open(os.path.join(base, "feature_cols.pkl"), "rb") as fh:
                self._feat_cols = list(pickle.load(fh))
            with open(os.path.join(base, "y_reg_mean.pkl"), "rb") as fh:
                self._y_mean = float(np.asarray(pickle.load(fh)).reshape(-1)[0])
            with open(os.path.join(base, "y_reg_std.pkl"), "rb") as fh:
                self._y_std = float(np.asarray(pickle.load(fh)).reshape(-1)[0])

            try:
                self._model = tf.keras.models.load_model(mp, compile=False)
            except Exception:
                from ml.lstm_training import focal_loss

                self._model = tf.keras.models.load_model(
                    mp,
                    compile=False,
                    custom_objects={"focal_loss": focal_loss(gamma=2.0, alpha=0.75)},
                )

            shape = self._model.input_shape
            if shape is None or len(shape) < 3:
                raise ValueError("Unexpected model input_shape")
            self._seq_len = int(shape[1])
            n_feat = int(shape[2])
            if len(self._feat_cols) != n_feat:
                raise ValueError(
                    f"feature_cols length {len(self._feat_cols)} != model input features {n_feat}"
                )
        except Exception as exc:
            self._load_error = str(exc)
            self._model = None
            self._scaler = None
            self._feat_cols = None
            self._seq_len = None
            return False

        self._artifact_dir = base
        self._model_path = mp
        return True

    def status(self) -> Dict[str, Any]:
        probe = self.probe_artifacts()
        out = {
            **probe,
            "model_loaded": self._model is not None,
            "load_error": self._load_error,
        }
        if self._model is not None and self._seq_len is not None:
            out["seq_len"] = self._seq_len
            out["n_features"] = len(self._feat_cols or [])
        return out

    def min_history_points(self) -> int:
        """Minimum raw telemetry rows before lag/dropna still leaves a full LSTM window."""
        return max(40, (self._seq_len or 12) + 12)

    def predict_from_history(
        self, history: List[Dict[str, Any]], stay_id: int = 1
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Returns (pred_next_spo2_unscaled, hypoxia_prob) or (None, None) if inference is unavailable.
        """
        if not self.ensure_loaded() or not history:
            return None, None

        assert self._scaler is not None and self._feat_cols is not None
        assert self._model is not None and self._seq_len is not None
        assert self._y_std is not None and self._y_mean is not None

        from pipelines.feature_engineering import (
            CLIP_BOUNDS,
            BASE_FEATURE_COLS,
            FEATURE_COLS,
            add_derived_features,
            add_lag_features,
            add_trend_features,
            add_ppo_state_reward_features,
        )

        rows: List[Dict[str, Any]] = []
        for r in history:
            row: Dict[str, Any] = {"stay_id": int(r.get("stay_id", stay_id))}
            ct = r.get("charttime")
            row["charttime"] = ct if ct is not None else pd.NaT
            for col in BASE_FEATURE_COLS:
                v = r.get(col)
                if v is None:
                    return None, None
                row[col] = float(v)
            row["Next_SpO2"] = float(row["SpO2"])
            row["Hypoxia_Risk"] = 0
            rows.append(row)

        df = pd.DataFrame(rows)
        df["charttime"] = pd.to_datetime(df["charttime"], errors="coerce")
        if df["charttime"].isna().all():
            df["charttime"] = pd.date_range("2024-01-01", periods=len(df), freq="15min")
        else:
            df["charttime"] = df["charttime"].ffill().bfill()

        for col, (lo, hi) in CLIP_BOUNDS.items():
            if col in df.columns:
                df[col] = df[col].clip(lo, hi)

        df = df.sort_values("charttime").reset_index(drop=True)
        df = add_derived_features(df, verbose=False)
        df = add_ppo_state_reward_features(df, verbose=False)
        df = add_lag_features(df, verbose=False)
        # Training includes trend features after lag engineering; keep inference aligned.
        df = add_trend_features(df, verbose=False)
        if len(df) < self._seq_len + 1:
            return None, None

        feat_arr = df[self._feat_cols].values.astype(np.float32)
        n = len(feat_arr)
        # Align with training: window rows [(n-1)-seq_len .. n-2] predicts target at row n-1
        win = feat_arr[n - 1 - self._seq_len : n - 1]
        if win.shape != (self._seq_len, len(self._feat_cols)):
            return None, None

        f_dim = win.shape[1]
        # Scaler is fit on per-row feature vectors (n_features), not flattened windows.
        scaled_win = self._scaler.transform(win)
        scaled = scaled_win.reshape(1, self._seq_len, f_dim)
        pred_reg_s, pred_cls = self._model.predict(scaled, verbose=0)
        reg_scaled = float(np.asarray(pred_reg_s).reshape(-1)[0])
        hypoxia_prob = float(np.asarray(pred_cls).reshape(-1)[0])
        pred_spo2 = reg_scaled * self._y_std + self._y_mean
        return pred_spo2, hypoxia_prob


_forecaster_singleton: Optional[LSTMForecaster] = None


def get_lstm_forecaster() -> LSTMForecaster:
    global _forecaster_singleton
    if _forecaster_singleton is None:
        _forecaster_singleton = LSTMForecaster()
    return _forecaster_singleton
