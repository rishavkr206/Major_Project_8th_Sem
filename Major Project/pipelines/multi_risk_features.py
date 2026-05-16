"""
Multi-target feature engineering pipeline.

Extends the existing single-target Hypoxia/SpO2 pipeline (feature_engineering.py)
with **four additional clinical risk targets** drawn from the project framework
docs/blockchain_ventilator_framework.md §3 "Clinical Parameter Ranges":

    Regression heads (Next_*):
        Next_HR        Next_MAP        Next_RespRate        Next_TidalVol
    Classification heads (binary risk in next step):
        Tachycardia_Risk    HR    < 40   OR > 140
        Hypotension_Risk    MAP   < 60
        Tachypnea_Risk      RR    < 8    OR > 30
        VILI_Risk           TV    < 280  OR > 600  (proxy for <4 / >10 ml/kg)

The original Hypoxia/Next_SpO2 targets are retained so the multi-task model
covers all five clinical risks in one pass through the LSTM encoder.

Output artefacts (under ml/multi_risk/):
    X_train.pkl  X_val.pkl  X_test.pkl
    y_reg_train.pkl ...        (matrix [N, 5])
    y_cls_train.pkl ...        (matrix [N, 5])
    feature_cols.pkl
    scaler.pkl
    y_reg_mean.pkl / y_reg_std.pkl    (vectors [5])
    risk_thresholds.json              (for inference + report)
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipelines.feature_engineering import (  # noqa: E402
    BASE_FEATURE_COLS,
    CLIP_BOUNDS,
    FEATURE_COLS,
    TREND_FEATURE_COLS,
    add_derived_features,
    add_lag_features,
    add_ppo_state_reward_features,
    add_trend_features,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DATA_PATH = os.path.join(REPO_ROOT, "clean_full_data_v2.csv")
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "ml", "multi_risk")
DEFAULT_SEQ_LEN = 12

# Order matters — used as column index in the [N, 5] target matrices and as
# output-head names in the trained Keras model.
REG_TARGETS = ["Next_SpO2", "Next_HR", "Next_MAP", "Next_RespRate", "Next_TidalVol"]
CLS_TARGETS = [
    "Hypoxia_Risk",
    "Tachycardia_Risk",
    "Hypotension_Risk",
    "Tachypnea_Risk",
    "VILI_Risk",
    "Shock_Risk",
]
RISK_LABELS = {
    "Hypoxia_Risk":     {"source": "SpO2",     "rule": "SpO2 < 90"},
    "Tachycardia_Risk": {"source": "HR",       "rule": "HR < 40 or HR > 140"},
    "Hypotension_Risk": {"source": "MAP",      "rule": "MAP < 60"},
    "Tachypnea_Risk":   {"source": "RespRate", "rule": "RespRate < 8 or RespRate > 30"},
    "VILI_Risk":        {"source": "TidalVol", "rule": "TidalVol < 280 or TidalVol > 600"},
    # Modified Shock Index = HR / MAP. MSI > 1.3 is a validated early-warning
    # indicator for circulatory shock (captures occult/compensated shock that
    # MAP-only or HR-only thresholds miss). MAP=0 guarded as no-shock to avoid
    # divide-by-zero artefacts on missing windows.
    "Shock_Risk":       {"source": "HR/MAP",   "rule": "(HR / MAP) > 1.3"},
}

# Extra clip bounds for the new Next_* regression targets.
EXTRA_CLIP_BOUNDS = {
    "Next_HR":       (0, 300),
    "Next_MAP":      (0, 200),
    "Next_RespRate": (0, 80),
    "Next_TidalVol": (100, 1000),
}


# ─── Helpers ─────────────────────────────────────────────────────────────────
def load_and_clean(path: str, max_patients: int | None) -> pd.DataFrame:
    print(f"[1/6] Loading data from {path} ...")
    df = pd.read_csv(path, parse_dates=["charttime"])
    print(f"      Raw shape: {df.shape}, stays: {df['stay_id'].nunique()}")

    if max_patients is not None and df["stay_id"].nunique() > max_patients:
        keep = (
            df["stay_id"].drop_duplicates().sort_values().head(max_patients).tolist()
        )
        df = df[df["stay_id"].isin(keep)].copy()
        print(
            f"      Sampled to {max_patients} stays -> {df.shape[0]:,} rows "
            f"({df['stay_id'].nunique()} stays)"
        )

    bounds = {**CLIP_BOUNDS, **EXTRA_CLIP_BOUNDS}
    for col, (lo, hi) in bounds.items():
        if col in df.columns:
            df[col] = df[col].clip(lo, hi)

    df = df.sort_values(["stay_id", "charttime"]).reset_index(drop=True)
    df = df.dropna(subset=BASE_FEATURE_COLS).reset_index(drop=True)
    print(f"      After cleaning: {df.shape}")
    return df


def add_next_step_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-shift each base vital per stay_id to obtain Next_* targets."""
    print("[2/6] Computing Next_* regression targets ...")
    grp = df.groupby("stay_id")
    df["Next_SpO2"] = grp["SpO2"].shift(-1)
    df["Next_HR"] = grp["HR"].shift(-1)
    df["Next_MAP"] = grp["MAP"].shift(-1)
    df["Next_RespRate"] = grp["RespRate"].shift(-1)
    df["Next_TidalVol"] = grp["TidalVol"].shift(-1)
    return df


def add_risk_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the five binary risk labels keyed off the *next-step* values."""
    print("[3/6] Computing binary risk labels (clinical critical ranges) ...")
    df["Hypoxia_Risk"]     = (df["Next_SpO2"]     < 90).astype(int)
    df["Tachycardia_Risk"] = ((df["Next_HR"] < 40) | (df["Next_HR"] > 140)).astype(int)
    df["Hypotension_Risk"] = (df["Next_MAP"]      < 60).astype(int)
    df["Tachypnea_Risk"]   = ((df["Next_RespRate"] < 8) | (df["Next_RespRate"] > 30)).astype(int)
    df["VILI_Risk"]        = ((df["Next_TidalVol"] < 280) | (df["Next_TidalVol"] > 600)).astype(int)

    # Modified Shock Index (MSI) on next-step values. Guard MAP > 0 so we never
    # divide by zero or label a missing/zero MAP as shock by accident.
    next_msi = np.where(df["Next_MAP"] > 0, df["Next_HR"] / df["Next_MAP"].replace(0, np.nan), 0.0)
    df["Shock_Risk"]       = (next_msi > 1.3).astype(int)

    for col in CLS_TARGETS:
        rate = df[col].mean() * 100
        print(f"      {col:18s} positive rate: {rate:5.2f}%")
    return df


def build_sequences(df: pd.DataFrame, seq_len: int):
    """Build (X_seq, y_reg [N,5], y_cls [N,5]) arrays."""
    print(f"[4/6] Building LSTM sequences (window={seq_len}) ...")

    all_feat_cols = (
        FEATURE_COLS
        + TREND_FEATURE_COLS
        + [f"{c}_lag1" for c in FEATURE_COLS]
        + [f"{c}_lag2" for c in FEATURE_COLS]
        + [f"{c}_roll4_mean" for c in FEATURE_COLS]
        + [f"{c}_roll4_std" for c in FEATURE_COLS]
    )
    all_feat_cols = [c for c in all_feat_cols if c in df.columns]
    print(f"      Feature columns: {len(all_feat_cols)}")

    X_seqs, y_regs, y_clss = [], [], []
    for _, grp in df.groupby("stay_id"):
        grp = grp.reset_index(drop=True)
        feat_arr = grp[all_feat_cols].values.astype(np.float32)
        reg_arr = grp[REG_TARGETS].values.astype(np.float32)
        cls_arr = grp[CLS_TARGETS].values.astype(np.int32)

        for i in range(seq_len, len(grp)):
            X_seqs.append(feat_arr[i - seq_len : i])
            y_regs.append(reg_arr[i])
            y_clss.append(cls_arr[i])

    X = np.array(X_seqs, dtype=np.float32)
    Y_reg = np.array(y_regs, dtype=np.float32)
    Y_cls = np.array(y_clss, dtype=np.int32)
    print(f"      Sequences: X={X.shape}, y_reg={Y_reg.shape}, y_cls={Y_cls.shape}")
    return X, Y_reg, Y_cls, all_feat_cols


def scale_and_split(X, Y_reg, Y_cls, out_dir):
    print("[5/6] Scaling features + targets and splitting ...")
    n, t, f = X.shape

    scaler = StandardScaler()
    X_flat = X.reshape(-1, f)
    X_scaled = scaler.fit_transform(X_flat).reshape(n, t, f)

    y_reg_mean = Y_reg.mean(axis=0)
    y_reg_std = Y_reg.std(axis=0) + 1e-8
    Y_reg_scaled = (Y_reg - y_reg_mean) / y_reg_std

    # Stratify on Hypoxia_Risk (rarest meaningful class is also the headline risk).
    strat = Y_cls[:, 0]
    idx_train, idx_temp = train_test_split(
        np.arange(n), test_size=0.30, stratify=strat, random_state=42
    )
    idx_val, idx_test = train_test_split(
        idx_temp, test_size=0.50, stratify=strat[idx_temp], random_state=42
    )

    splits = {
        "X_train": X_scaled[idx_train],
        "X_val": X_scaled[idx_val],
        "X_test": X_scaled[idx_test],
        "y_reg_train": Y_reg_scaled[idx_train],
        "y_reg_val": Y_reg_scaled[idx_val],
        "y_reg_test": Y_reg_scaled[idx_test],
        "y_cls_train": Y_cls[idx_train],
        "y_cls_val": Y_cls[idx_val],
        "y_cls_test": Y_cls[idx_test],
        "scaler": scaler,
        "y_reg_mean": y_reg_mean,
        "y_reg_std": y_reg_std,
    }

    os.makedirs(out_dir, exist_ok=True)
    for key, val in splits.items():
        with open(os.path.join(out_dir, f"{key}.pkl"), "wb") as fh:
            pickle.dump(val, fh)

    print(
        f"      Train: {splits['X_train'].shape}, "
        f"Val: {splits['X_val'].shape}, Test: {splits['X_test'].shape}"
    )
    return splits


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-risk feature pipeline")
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--seq-len", type=int, default=DEFAULT_SEQ_LEN)
    parser.add_argument(
        "--max-patients",
        type=int,
        default=400,
        help="cap stays for tractable CPU training (set 0 / -1 for all)",
    )
    args = parser.parse_args()
    max_patients = args.max_patients if args.max_patients and args.max_patients > 0 else None

    print("=" * 64)
    print("  Multi-target Feature Engineering Pipeline")
    print("=" * 64)

    df = load_and_clean(args.data_path, max_patients)
    df = add_next_step_targets(df)
    df = add_risk_labels(df)
    df = df.dropna(subset=REG_TARGETS).reset_index(drop=True)

    df = add_derived_features(df)
    df = add_ppo_state_reward_features(df)
    df = add_lag_features(df)
    df = add_trend_features(df)

    X, Y_reg, Y_cls, feat_cols = build_sequences(df, args.seq_len)

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "feature_cols.pkl"), "wb") as fh:
        pickle.dump(feat_cols, fh)

    splits = scale_and_split(X, Y_reg, Y_cls, args.out_dir)

    metadata = {
        "reg_targets": REG_TARGETS,
        "cls_targets": CLS_TARGETS,
        "risk_definitions": RISK_LABELS,
        "n_features": len(feat_cols),
        "seq_len": args.seq_len,
        "n_train": int(splits["X_train"].shape[0]),
        "n_val": int(splits["X_val"].shape[0]),
        "n_test": int(splits["X_test"].shape[0]),
        "positive_rates_train": {
            CLS_TARGETS[i]: float(splits["y_cls_train"][:, i].mean())
            for i in range(len(CLS_TARGETS))
        },
    }
    with open(os.path.join(args.out_dir, "risk_thresholds.json"), "w") as fh:
        json.dump(metadata, fh, indent=2, default=str)

    print("[6/6] Summary:")
    for k in ("n_train", "n_val", "n_test", "n_features"):
        print(f"  {k:14s}: {metadata[k]}")
    print("  Class balance (train, % positives):")
    for risk, rate in metadata["positive_rates_train"].items():
        print(f"    {risk:18s}: {rate*100:5.2f}%")
    print("=" * 64)
    print(f"  Pipeline complete. Artefacts at: {args.out_dir}")
    print("  Next: python ml/multi_risk_training.py")
    print("=" * 64)


if __name__ == "__main__":
    main()
