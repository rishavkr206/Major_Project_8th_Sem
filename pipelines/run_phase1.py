"""
One-command Phase 1 automation.

Runs:
1) simulator ingestion data generation
2) feature engineering pipeline on generated dataset
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run_command(command: list[str], cwd: str) -> None:
    print(f"\n[RUN] {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 1 synthetic data + feature pipeline")
    parser.add_argument("--dataset-out", default="data/simulated_phase1.csv")
    parser.add_argument("--artifacts-out", default="ml/simulated_phase1")
    parser.add_argument("--profiles", default="normal,ards,copd,unstable")
    parser.add_argument("--stays-per-profile", type=int, default=6)
    parser.add_argument("--steps-per-stay", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seq-len", type=int, default=12)
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    ingestion_cmd = [
        sys.executable,
        "-m",
        "pipelines.simulated_ingestion",
        "--out",
        args.dataset_out,
        "--profiles",
        args.profiles,
        "--stays-per-profile",
        str(args.stays_per_profile),
        "--steps-per-stay",
        str(args.steps_per_stay),
        "--seed",
        str(args.seed),
    ]

    feature_cmd = [
        sys.executable,
        "pipelines/feature_engineering.py",
        "--data-path",
        args.dataset_out,
        "--out-dir",
        args.artifacts_out,
        "--seq-len",
        str(args.seq_len),
    ]

    print("=" * 64, flush=True)
    print("Phase 1 automation started", flush=True)
    print(f"Dataset output   : {args.dataset_out}", flush=True)
    print(f"Artifacts output : {args.artifacts_out}", flush=True)
    print("=" * 64, flush=True)

    run_command(ingestion_cmd, cwd=repo_root)
    run_command(feature_cmd, cwd=repo_root)

    print("\n" + "=" * 64, flush=True)
    print("Phase 1 automation completed successfully", flush=True)
    print("=" * 64, flush=True)


if __name__ == "__main__":
    main()
