"""
Simulator ingestion bridge for Phase 1 reproducible tests.

Generates synthetic telemetry events using VentilatorDataSimulator and writes
a feature-pipeline-ready CSV containing Next_SpO2 and Hypoxia_Risk labels.
"""

from __future__ import annotations

import argparse
import os
from typing import List

import pandas as pd

from services.data_simulator import SimulationConfig, VentilatorDataSimulator, validate_record


def generate_simulated_dataframe(
    profiles: List[str],
    stays_per_profile: int,
    steps_per_stay: int,
    seed: int,
) -> pd.DataFrame:
    records = []
    stay_id = 800000

    for profile_idx, profile in enumerate(profiles):
        for local_idx in range(stays_per_profile):
            config = SimulationConfig(
                profile=profile,
                seed=seed + (profile_idx * 1000) + local_idx,
                packet_loss_probability=0.03,
                artifact_probability=0.02,
                trend_strength=0.05,
            )
            simulator = VentilatorDataSimulator(config=config)
            patient_records = simulator.generate_batch(stay_id=stay_id, steps=steps_per_stay)
            for item in patient_records:
                validate_record(item)
            records.extend(patient_records)
            stay_id += 1

    df = pd.DataFrame(records)
    df["charttime"] = pd.to_datetime(df["charttime"])
    df = df.sort_values(["stay_id", "charttime"]).reset_index(drop=True)

    # Fill transient packet-loss nulls by local interpolation then forward/back fill.
    numeric_cols = ["HR", "MAP", "RespRate", "SpO2", "PEEP", "FiO2", "TidalVol"]
    df[numeric_cols] = (
        df.groupby("stay_id")[numeric_cols]
        .transform(lambda g: g.interpolate(limit_direction="both").ffill().bfill())
    )

    # Build supervised targets used by feature_engineering.py
    df["Next_SpO2"] = df.groupby("stay_id")["SpO2"].shift(-1)
    df["Hypoxia_Risk"] = (df["Next_SpO2"] < 90.0).astype(int)
    df = df.dropna(subset=["Next_SpO2"]).reset_index(drop=True)

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate simulator dataset for feature pipeline")
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "simulated_phase1.csv"),
        help="Output CSV path for generated dataset",
    )
    parser.add_argument(
        "--profiles",
        default="normal,ards,copd,unstable",
        help="Comma-separated simulator profiles",
    )
    parser.add_argument("--stays-per-profile", type=int, default=8)
    parser.add_argument("--steps-per-stay", type=int, default=72)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    df = generate_simulated_dataframe(
        profiles=profiles,
        stays_per_profile=args.stays_per_profile,
        steps_per_stay=args.steps_per_stay,
        seed=args.seed,
    )

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)

    print("=" * 60)
    print("Simulator ingestion dataset generated")
    print(f"Output path      : {out_path}")
    print(f"Rows             : {len(df):,}")
    print(f"Patients (stays) : {df['stay_id'].nunique()}")
    print(f"Hypoxia rate     : {df['Hypoxia_Risk'].mean() * 100:.2f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
