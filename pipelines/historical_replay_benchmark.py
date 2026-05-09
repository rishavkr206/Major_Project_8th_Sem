"""
Digital Twin — Historical Trajectory Replay Benchmark (Phase 2 exit criterion).

Goal: prove that the twin can reproduce real patient SpO2 trajectories with
acceptable error, not just synthetic scenarios.

Method (per patient stay_id):
    1. Sort observations by charttime.
    2. Use the first `calibration_window` rows to calibrate the twin.
    3. Walk the next `horizon` rows (the held-out segment). For each step:
         - take the *actual* PEEP / FiO2 / TidalVol the clinician applied
         - call twin._spo2_from_settings() to get the predicted next SpO2
         - compare against the actual measured SpO2 at that step
    4. Aggregate MAE, RMSE per patient and globally.

Two scoring modes (both reported):
    - teacher_forced: prediction conditioned on the previous *actual* SpO2
      (measures one-step-ahead error; standard time-series eval)
    - free_running:   prediction feeds back into next step
      (measures multi-step drift error; harder)

Default dataset: clean_full_data_v2.csv (real ICU export). Falls back to
data/simulated_phase1.csv when the historical CSV is absent.

CLI:
    python pipelines/historical_replay_benchmark.py
    python pipelines/historical_replay_benchmark.py --fail-on-thresholds

Outputs:
    reports/twin_historical_replay.json
    stdout summary table + per-patient sample
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.digital_twin import DigitalTwin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DATASETS = [
    os.path.join(REPO_ROOT, "clean_full_data_v2.csv"),
    os.path.join(REPO_ROOT, "data", "simulated_phase1.csv"),
]
REPORT_PATH = os.path.join(REPO_ROOT, "reports", "twin_historical_replay.json")
REQUIRED_COLS = ("stay_id", "charttime", "SpO2", "PEEP", "FiO2", "TidalVol", "HR", "MAP", "RespRate")


@dataclass
class PatientResult:
    stay_id: int
    n_steps: int
    teacher_mae: float
    teacher_rmse: float
    free_mae: float
    free_rmse: float
    final_actual: float
    final_pred_free: float


def _resolve_dataset(path_arg: Optional[str]) -> str:
    candidates = [path_arg] if path_arg else DEFAULT_DATASETS
    for p in candidates:
        if not p:
            continue
        if os.path.isfile(p) and os.path.getsize(p) > 1024:
            # Skip git-lfs pointer files (~130 bytes)
            with open(p, "rb") as fh:
                head = fh.read(64)
            if b"git-lfs" in head:
                continue
            return p
    raise FileNotFoundError(
        "No usable dataset found. Tried: "
        + ", ".join(c for c in candidates if c)
        + ". Run `python pipelines/run_phase1.py` to regenerate the synthetic CSV."
    )


def _load_dataset(path: str, max_patients: int) -> pd.DataFrame:
    use_cols = list(REQUIRED_COLS)
    df = pd.read_csv(path, usecols=use_cols)
    df = df.dropna(subset=["stay_id", "charttime", "SpO2", "PEEP", "FiO2", "TidalVol"])
    df["stay_id"] = df["stay_id"].astype(int)
    df = df.sort_values(["stay_id", "charttime"]).reset_index(drop=True)

    # Pick the first max_patients with enough rows
    counts = df.groupby("stay_id").size()
    enough = counts[counts >= 24].index.tolist()
    if not enough:
        # Fall back to whatever we have if the dataset is small
        enough = counts.index.tolist()
    selected = enough[:max_patients]
    return df[df["stay_id"].isin(selected)].copy()


def _safe_metric(values: List[float]) -> Tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    arr = np.asarray(values, dtype=float)
    mae = float(np.mean(np.abs(arr)))
    rmse = float(math.sqrt(float(np.mean(np.square(arr)))))
    return mae, rmse


def _replay_one_patient(
    df_patient: pd.DataFrame,
    calibration_window: int,
    horizon: int,
) -> Optional[PatientResult]:
    if len(df_patient) < calibration_window + 4:
        return None

    cal_rows = df_patient.iloc[:calibration_window].to_dict(orient="records")
    eval_rows = df_patient.iloc[calibration_window : calibration_window + horizon]
    if eval_rows.empty:
        return None

    twin = DigitalTwin(stay_id=int(df_patient.iloc[0]["stay_id"]))
    # Twin.calibrate expects keys SpO2/PEEP/FiO2/TidalVol/HR/MAP/RespRate — already present
    twin.calibrate(cal_rows)

    # Initial SpO2 anchor: the last calibration observation
    prev_actual = float(df_patient.iloc[calibration_window - 1]["SpO2"])
    prev_pred_free = prev_actual

    teacher_errors: List[float] = []
    free_errors: List[float] = []
    final_actual = prev_actual
    final_pred_free = prev_actual

    for _, row in eval_rows.iterrows():
        peep = float(row["PEEP"])
        fio2 = float(row["FiO2"])
        tv = float(row["TidalVol"])
        actual = float(row["SpO2"])

        # Teacher-forced: predict from previous actual
        pred_t = twin._spo2_from_settings(peep, fio2, tv, prev_actual)
        teacher_errors.append(pred_t - actual)

        # Free-running: predict from previous predicted
        pred_f = twin._spo2_from_settings(peep, fio2, tv, prev_pred_free)
        free_errors.append(pred_f - actual)

        prev_actual = actual
        prev_pred_free = pred_f
        final_actual = actual
        final_pred_free = pred_f

    teacher_mae, teacher_rmse = _safe_metric(teacher_errors)
    free_mae, free_rmse = _safe_metric(free_errors)

    return PatientResult(
        stay_id=int(df_patient.iloc[0]["stay_id"]),
        n_steps=len(eval_rows),
        teacher_mae=teacher_mae,
        teacher_rmse=teacher_rmse,
        free_mae=free_mae,
        free_rmse=free_rmse,
        final_actual=round(final_actual, 2),
        final_pred_free=round(final_pred_free, 2),
    )


def run_benchmark(
    dataset_path: Optional[str] = None,
    max_patients: int = 100,
    calibration_window: int = 12,
    horizon: int = 24,
) -> Dict:
    path = _resolve_dataset(dataset_path)
    df = _load_dataset(path, max_patients=max_patients)

    results: List[PatientResult] = []
    for stay_id, group in df.groupby("stay_id"):
        r = _replay_one_patient(group, calibration_window, horizon)
        if r is not None:
            results.append(r)

    if not results:
        raise RuntimeError(
            "No patient produced a result — dataset too small or filtering too strict."
        )

    teacher_mae_avg = float(np.mean([r.teacher_mae for r in results]))
    teacher_rmse_avg = float(np.mean([r.teacher_rmse for r in results]))
    free_mae_avg = float(np.mean([r.free_mae for r in results]))
    free_rmse_avg = float(np.mean([r.free_rmse for r in results]))

    teacher_mae_p50 = float(np.median([r.teacher_mae for r in results]))
    teacher_mae_p95 = float(np.quantile([r.teacher_mae for r in results], 0.95))
    free_mae_p50 = float(np.median([r.free_mae for r in results]))
    free_mae_p95 = float(np.quantile([r.free_mae for r in results], 0.95))

    return {
        "dataset_path": path,
        "calibration_window": calibration_window,
        "horizon": horizon,
        "patient_count": len(results),
        "teacher_forced": {
            "mae_avg": round(teacher_mae_avg, 4),
            "rmse_avg": round(teacher_rmse_avg, 4),
            "mae_p50": round(teacher_mae_p50, 4),
            "mae_p95": round(teacher_mae_p95, 4),
        },
        "free_running": {
            "mae_avg": round(free_mae_avg, 4),
            "rmse_avg": round(free_rmse_avg, 4),
            "mae_p50": round(free_mae_p50, 4),
            "mae_p95": round(free_mae_p95, 4),
        },
        "sample_patients": [asdict(r) for r in results[:10]],
    }


def evaluate_thresholds(
    metrics: Dict,
    max_teacher_mae: float,
    max_free_mae: float,
) -> List[Tuple[str, bool, float, float]]:
    return [
        (
            "teacher_forced.mae_avg",
            metrics["teacher_forced"]["mae_avg"] <= max_teacher_mae,
            metrics["teacher_forced"]["mae_avg"],
            max_teacher_mae,
        ),
        (
            "free_running.mae_avg",
            metrics["free_running"]["mae_avg"] <= max_free_mae,
            metrics["free_running"]["mae_avg"],
            max_free_mae,
        ),
    ]


def _print_report(metrics: Dict) -> None:
    print("=" * 64)
    print("Digital Twin Historical Replay Benchmark")
    print("=" * 64)
    print(f"dataset:              {metrics['dataset_path']}")
    print(f"patients evaluated:   {metrics['patient_count']}")
    print(f"calibration window:   {metrics['calibration_window']}")
    print(f"replay horizon:       {metrics['horizon']}")
    print("-" * 64)
    print("Teacher-forced (one-step-ahead)")
    for k, v in metrics["teacher_forced"].items():
        print(f"  {k:14s}: {v}")
    print("Free-running (multi-step drift)")
    for k, v in metrics["free_running"].items():
        print(f"  {k:14s}: {v}")
    print("-" * 64)
    print("Sample patient breakdown:")
    print(f"  {'stay_id':>10s} {'n':>3s}  {'teach_mae':>9s}  {'free_mae':>9s}  {'actual':>7s}  {'pred':>7s}")
    for p in metrics["sample_patients"][:8]:
        print(
            f"  {p['stay_id']:>10d} {p['n_steps']:>3d}  "
            f"{p['teacher_mae']:>9.3f}  {p['free_mae']:>9.3f}  "
            f"{p['final_actual']:>7.2f}  {p['final_pred_free']:>7.2f}"
        )
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(description="Twin historical replay benchmark")
    parser.add_argument("--dataset", type=str, default=None, help="path to a CSV with required columns")
    parser.add_argument("--max-patients", type=int, default=100)
    parser.add_argument("--calibration-window", type=int, default=12)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--max-teacher-mae", type=float, default=4.0,
                        help="threshold: teacher-forced MAE must be <= this")
    parser.add_argument("--max-free-mae", type=float, default=6.0,
                        help="threshold: free-running MAE must be <= this")
    parser.add_argument("--fail-on-thresholds", action="store_true")
    parser.add_argument("--report-path", type=str, default=REPORT_PATH)
    args = parser.parse_args()

    metrics = run_benchmark(
        dataset_path=args.dataset,
        max_patients=args.max_patients,
        calibration_window=args.calibration_window,
        horizon=args.horizon,
    )
    _print_report(metrics)

    checks = evaluate_thresholds(metrics, args.max_teacher_mae, args.max_free_mae)
    print("Threshold checks")
    failed = False
    for name, passed, value, threshold in checks:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}: {value:.3f} <= {threshold:.3f}")
        if not passed:
            failed = True
    print("=" * 64)

    metrics["thresholds"] = {
        "max_teacher_mae": args.max_teacher_mae,
        "max_free_mae": args.max_free_mae,
        "passed": not failed,
    }

    os.makedirs(os.path.dirname(args.report_path), exist_ok=True)
    with open(args.report_path, "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"Wrote {args.report_path}")

    if failed and args.fail_on_thresholds:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
