"""Create PPO-ready ventilator state features and reward signals.

The input CSV is expected to contain:
stay_id, charttime, HR, MAP, RespRate, SpO2, PEEP, FiO2, TidalVol,
Next_SpO2, Hypoxia_Risk.
"""

from __future__ import annotations

import argparse
import os
import pickle
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


EPS = 1e-6

REQUIRED_COLUMNS = [
    "stay_id",
    "charttime",
    "HR",
    "MAP",
    "RespRate",
    "SpO2",
    "PEEP",
    "FiO2",
    "TidalVol",
    "Next_SpO2",
    "Hypoxia_Risk",
]

PPO_STATE_FEATURES = [
    "HR",
    "MAP",
    "RespRate",
    "SpO2",
    "PEEP",
    "FiO2",
    "TidalVol",
    "msi",
    "sf_ratio",
    "minute_ventilation",
    "vent_oxy_coupling",
    "peep_effect",
    "resp_stress",
    "msi_smooth",
    "msi_trend",
]


def _assert_required_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _replace_invalid_numeric(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return df


def add_ppo_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add requested state features and reward-related PPO signals."""
    df = df.copy()
    _assert_required_columns(df, REQUIRED_COLUMNS)

    df["charttime"] = pd.to_datetime(df["charttime"], errors="coerce")
    df = df.sort_values(["stay_id", "charttime"]).reset_index(drop=True)

    # Forward-fill raw patient streams first, without changing supervised labels.
    value_cols = ["HR", "MAP", "RespRate", "SpO2", "PEEP", "FiO2", "TidalVol"]
    df[value_cols] = df.groupby("stay_id", group_keys=False)[value_cols].ffill()

    df["msi"] = df["HR"] / (df["MAP"] + EPS)
    df["sf_ratio"] = df["SpO2"] / (df["FiO2"] + EPS)
    df["minute_ventilation"] = df["TidalVol"] * df["RespRate"]
    df["vent_oxy_coupling"] = df["SpO2"] / (df["minute_ventilation"] + EPS)
    df["peep_effect"] = df["SpO2"] / (df["PEEP"] + EPS)
    df["resp_stress"] = df["RespRate"] * (df["FiO2"] / (df["SpO2"] + EPS))

    groups = df.groupby("stay_id", group_keys=False)
    df["msi_smooth"] = groups["msi"].transform(
        lambda s: s.rolling(window=3, min_periods=1).mean()
    )
    df["msi_trend"] = groups["msi"].diff()

    # Prompt-requested weighted signal, interpreted with Phase 2 report semantics:
    # reward stable oxygenation and penalize pressure/ventilator burden. The final
    # reward subtracts explicit hypoxia/shock penalties instead of multiplying them.
    df["stability_score"] = (
        (1.0 * df["Next_SpO2"])
        - (0.8 * df["msi_smooth"])
        - (0.6 * df["FiO2"])
        - (0.4 * df["RespRate"])
    )
    df["shock_penalty"] = (df["MAP"] < 65).astype(int)
    df["hypoxia_penalty"] = (df["SpO2"] < 90).astype(int)
    df["final_reward"] = (
        df["stability_score"]
        - (10.0 * df["hypoxia_penalty"])
        - (15.0 * df["shock_penalty"])
    )

    df = _replace_invalid_numeric(df)
    fill_cols = [col for col in df.columns if col not in ("stay_id", "charttime")]
    df[fill_cols] = df.groupby("stay_id", group_keys=False)[fill_cols].ffill()
    df = df.dropna().reset_index(drop=True)
    return df


def normalize_ppo_features(
    df: pd.DataFrame,
    scaler_out: str | None = None,
) -> tuple[pd.DataFrame, StandardScaler]:
    """Standardize PPO state features and optionally persist the scaler."""
    df = df.copy()
    _assert_required_columns(df, PPO_STATE_FEATURES)

    scaler = StandardScaler()
    df[PPO_STATE_FEATURES] = scaler.fit_transform(df[PPO_STATE_FEATURES])

    if scaler_out:
        os.makedirs(os.path.dirname(os.path.abspath(scaler_out)), exist_ok=True)
        with open(scaler_out, "wb") as fh:
            pickle.dump(scaler, fh)

    return df, scaler


def build_ppo_ready_dataframe(
    input_csv: str,
    scaler_out: str | None = None,
) -> pd.DataFrame:
    df = pd.read_csv(input_csv, parse_dates=["charttime"])
    engineered = add_ppo_features(df)
    normalized, _ = normalize_ppo_features(engineered, scaler_out=scaler_out)
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Create PPO-ready ventilator dataset")
    parser.add_argument("--input", default="clean_full_data_v2.csv")
    parser.add_argument("--output", default="ppo_ready_ventilator_data.csv")
    parser.add_argument("--scaler-out", default=os.path.join("ml", "ppo_state_scaler.pkl"))
    args = parser.parse_args()

    out_path = os.path.abspath(args.output)
    df = build_ppo_ready_dataframe(args.input, scaler_out=args.scaler_out)
    df.to_csv(out_path, index=False)
    print("=" * 64)
    print("PPO-ready ventilator dataset created")
    print(f"Input       : {os.path.abspath(args.input)}")
    print(f"Output      : {out_path}")
    print(f"Rows        : {len(df):,}")
    print(f"Columns     : {len(df.columns)}")
    print(f"Scaler      : {os.path.abspath(args.scaler_out)}")
    print("=" * 64)


if __name__ == "__main__":
    main()
