"""
LSTM accuracy vs dataset size — sweep study.

For each target row count in `--sizes`, this script:

  1. Picks `(stays_per_profile, steps_per_stay)` such that the resulting
     simulator dataset contains approximately `target_rows` rows.
  2. Runs `pipelines/simulated_ingestion.py` to generate the CSV.
  3. Runs `pipelines/feature_engineering.py` to build LSTM-ready pickles.
  4. Runs `ml/lstm_training.py` against those pickles and captures the
     test-set metrics from `reports/model_evaluation_lstm.json`.
  5. Aggregates every run into:
        reports/lstm_dataset_size_study.json
        reports/lstm_dataset_size_study.md

Default invocation (small + fast for laptop demos):

    python pipelines/lstm_dataset_size_study.py --sizes 1000,2000 --epochs 8

Recommended for the report:

    python pipelines/lstm_dataset_size_study.py --sizes 1000,2000,4000,8000 --epochs 20

Notes
-----
* Each run trains a fresh model — no warm starts. Wall-clock dominated by
  LSTM training; reduce `--epochs` (and `--seq-len`) to iterate quickly.
* The script is profile-agnostic: pass `--profiles normal,ards,copd,unstable`
  or include the new `lung_infected` profile.
* Artifacts (pickles, models) live under a per-size subdirectory inside
  `--workspace` so that previous runs are not clobbered.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_REPORT_JSON = os.path.join(REPO_ROOT, "reports", "lstm_dataset_size_study.json")
DEFAULT_REPORT_MD = os.path.join(REPO_ROOT, "reports", "lstm_dataset_size_study.md")
DEFAULT_LSTM_REPORT = os.path.join(REPO_ROOT, "reports", "model_evaluation_lstm.json")


def _solve_stays_steps(target_rows: int, n_profiles: int, max_steps: int = 96) -> tuple[int, int]:
    """
    Pick (stays_per_profile, steps_per_stay) so that
    `n_profiles * stays * steps ≈ target_rows`, preferring longer stays
    because the LSTM windows benefit from continuity per patient.

    The simulator drops the final row when computing Next_SpO2, so the
    realised CSV ends up `n_profiles * stays * (steps - 1)` rows. We oversize
    `steps` by 1 to compensate.
    """
    if target_rows < n_profiles:
        raise ValueError(f"target_rows={target_rows} too small for {n_profiles} profiles")

    # Aim for steps near max_steps; fall back to fewer stays if the row count
    # is small enough that one stay per profile is already too many rows.
    steps = max_steps
    stays = max(1, round(target_rows / (n_profiles * (steps - 1))))
    if stays * n_profiles * (steps - 1) < target_rows * 0.85:
        # Need to grow steps too — increase until budget covered or capped.
        while stays * n_profiles * (steps - 1) < target_rows and steps < 4 * max_steps:
            steps += 8
    # Final guard
    if stays < 1:
        stays = 1
    return stays, steps + 1  # +1 for the dropped Next_SpO2 row


def _run(cmd: List[str], cwd: str, env: Dict[str, str] | None = None) -> None:
    print(f"\n[RUN] {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit {proc.returncode}): {' '.join(cmd)}")


def _count_rows(csv_path: str) -> int:
    # Cheap row count without loading pandas; subtract header.
    with open(csv_path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh) - 1


def run_one_size(
    target_rows: int,
    profiles: List[str],
    workspace: str,
    seq_len: int,
    epochs: int,
    seed: int,
) -> Dict:
    stays, steps = _solve_stays_steps(target_rows, len(profiles))
    size_tag = f"size_{target_rows}"
    work_dir = os.path.join(workspace, size_tag)
    os.makedirs(work_dir, exist_ok=True)
    csv_path = os.path.join(work_dir, "dataset.csv")
    artifacts_dir = os.path.join(work_dir, "artifacts")

    # 1) Generate dataset
    _run(
        [
            sys.executable,
            "-m",
            "pipelines.simulated_ingestion",
            "--out", csv_path,
            "--profiles", ",".join(profiles),
            "--stays-per-profile", str(stays),
            "--steps-per-stay", str(steps),
            "--seed", str(seed),
        ],
        cwd=REPO_ROOT,
    )
    realised_rows = _count_rows(csv_path)

    # 2) Feature engineering
    _run(
        [
            sys.executable,
            "pipelines/feature_engineering.py",
            "--data-path", csv_path,
            "--out-dir", artifacts_dir,
            "--seq-len", str(seq_len),
        ],
        cwd=REPO_ROOT,
    )

    # 3) LSTM training. We point the trainer at our per-size artifact dir and
    # cap epochs via env var. The trainer always overwrites
    # reports/model_evaluation_lstm.json, so we read it immediately after.
    env = os.environ.copy()
    env["LSTM_ARTIFACTS_DIR"] = artifacts_dir
    env["LSTM_EPOCHS"] = str(epochs)

    if os.path.exists(DEFAULT_LSTM_REPORT):
        os.remove(DEFAULT_LSTM_REPORT)

    train_start = time.perf_counter()
    _run([sys.executable, "ml/lstm_training.py"], cwd=REPO_ROOT, env=env)
    train_seconds = time.perf_counter() - train_start

    # 4) Capture metrics
    if not os.path.exists(DEFAULT_LSTM_REPORT):
        raise RuntimeError(
            f"Expected metrics file missing: {DEFAULT_LSTM_REPORT}. "
            "Did ml/lstm_training.py exit early?"
        )
    with open(DEFAULT_LSTM_REPORT, "r", encoding="utf-8") as fh:
        metrics = json.load(fh)

    # 5) Snapshot the per-size artifacts so the headline LSTM report doesn't
    # silently shadow the next run when humans inspect it later.
    snapshot = os.path.join(work_dir, "model_evaluation_lstm.json")
    shutil.copyfile(DEFAULT_LSTM_REPORT, snapshot)

    return {
        "target_rows":      target_rows,
        "realised_rows":    realised_rows,
        "stays_per_profile": stays,
        "steps_per_stay":   steps,
        "seq_len":          seq_len,
        "epochs":           epochs,
        "train_seconds":    round(train_seconds, 2),
        "metrics":          metrics,
        "artifacts_dir":    artifacts_dir,
    }


def write_markdown(report: Dict, out_path: str) -> None:
    """Render an at-a-glance Markdown table for inclusion in the paper."""
    rows = report["runs"]
    lines: List[str] = []
    lines.append("# LSTM Accuracy vs Dataset Size")
    lines.append("")
    lines.append(f"_Generated: {report['generated_at']}_")
    lines.append("")
    lines.append(
        f"Profiles: `{', '.join(report['profiles'])}` · "
        f"seq_len: `{report['seq_len']}` · epochs: `{report['epochs']}` · "
        f"seed: `{report['seed']}`"
    )
    lines.append("")
    lines.append("| Target rows | Realised rows | Train seconds | MAE (SpO2) | RMSE | Hypoxia AUROC | Hypoxia F1 (opt) | Optimal threshold |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        m = r["metrics"]
        lines.append(
            f"| {r['target_rows']:,} | {r['realised_rows']:,} | {r['train_seconds']} "
            f"| {m.get('next_spo2_mae', '—')} | {m.get('next_spo2_rmse', '—')} "
            f"| {m.get('hypoxia_auroc', '—')} | {m.get('hypoxia_f1_optimal', '—')} "
            f"| {m.get('hypoxia_optimal_threshold', '—')} |"
        )
    lines.append("")
    lines.append("## Reading the table")
    lines.append("")
    lines.append(
        "- **MAE / RMSE** are on the de-scaled SpO2 prediction head — lower is better. "
        "Expect the curve to flatten once the dataset is large enough to cover the "
        "feature distribution."
    )
    lines.append(
        "- **Hypoxia AUROC** evaluates the binary head ranking. AUROC plateaus quickly; "
        "use **Hypoxia F1 (optimal)** to judge how decisive the classifier is at the "
        "selected threshold."
    )
    lines.append(
        "- The data-hungry phase is visible whenever doubling the rows yields a "
        "non-trivial F1 jump. Diminishing returns means more data won't help — focus "
        "on better features or longer sequences."
    )
    lines.append("")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="LSTM accuracy vs dataset size sweep")
    parser.add_argument(
        "--sizes",
        default="1000,2000",
        help="Comma-separated target row counts (default: 1000,2000)",
    )
    parser.add_argument(
        "--profiles",
        default="normal,ards,copd,unstable",
        help="Comma-separated simulator profiles to use",
    )
    parser.add_argument("--seq-len", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=8,
                        help="LSTM_EPOCHS for each run (lower = faster, default 8)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--workspace",
        default=os.path.join(REPO_ROOT, "data", "lstm_size_study"),
        help="Directory holding per-size CSV + pickles (will be created)",
    )
    parser.add_argument("--report-json", default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", default=DEFAULT_REPORT_MD)
    args = parser.parse_args()

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    if not sizes:
        raise SystemExit("--sizes must contain at least one row count")
    if not profiles:
        raise SystemExit("--profiles must contain at least one profile name")

    os.makedirs(args.workspace, exist_ok=True)
    os.makedirs(os.path.dirname(args.report_json), exist_ok=True)

    runs: List[Dict] = []
    for size in sizes:
        print("=" * 64)
        print(f"  Dataset size sweep — target {size:,} rows")
        print("=" * 64)
        result = run_one_size(
            target_rows=size,
            profiles=profiles,
            workspace=args.workspace,
            seq_len=args.seq_len,
            epochs=args.epochs,
            seed=args.seed,
        )
        runs.append(result)

    report = {
        "generated_at":    datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profiles":        profiles,
        "seq_len":         args.seq_len,
        "epochs":          args.epochs,
        "seed":            args.seed,
        "runs":            runs,
    }

    with open(args.report_json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    write_markdown(report, args.report_md)

    print("\n" + "=" * 64)
    print(f"Wrote {args.report_json}")
    print(f"Wrote {args.report_md}")
    print("=" * 64)


if __name__ == "__main__":
    main()
