"""Ventilator feature engineering for ICU time-series datasets.

Adds engineered features, temporal derivatives, rolling statistics, and binary risk labels.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


CANONICAL_COLUMNS = {
    'spo2': 'SpO2',
    'spO2': 'SpO2',
    'spO₂': 'SpO2',
    'fio2': 'FiO2',
    'peep': 'PEEP',
    'tidal_volume': 'tidal_volume',
    'tidalvol': 'tidal_volume',
    'tv': 'tidal_volume',
    'tidalvol_mL': 'tidal_volume',
    'respiratory_rate': 'RR',
    'resp_rate': 'RR',
    'respiratoryrate': 'RR',
    'resprate': 'RR',
    'rr': 'RR',
    'heart_rate': 'HR',
    'heartrate': 'HR',
    'hr': 'HR',
    'mean_arterial_pressure': 'MAP',
    'map': 'MAP',
    'stay_id': 'stay_id',
    'charttime': 'charttime',
}

ENGINEERED_FEATURES = [
    'SF_Ratio',
    'Minute_Ventilation',
    'VSI',
    'Shock_Index',
    'Oxygen_Delivery_Proxy',
]

TEMPORAL_COLUMNS = ['SpO2', 'FiO2', 'PEEP', 'tidal_volume', 'RR', 'HR', 'MAP']

ROLLING_MEAN_COLS = ['SpO2', 'MAP']
ROLLING_STD_COLS = ['SpO2', 'HR', 'RR', 'MAP']


@dataclass
class RiskThresholds:
    threshold_RR: float = 3.0
    threshold_VQ: float = 0.15
    threshold_OD: float = 6000.0


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Map common ICU column names to canonical names used by this pipeline."""
    rename_map = {}
    for col in df.columns:
        key = col.strip().replace(' ', '_').lower()
        if key in CANONICAL_COLUMNS:
            rename_map[col] = CANONICAL_COLUMNS[key]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def ensure_fio2_fraction(df: pd.DataFrame, fio2_col: str = 'FiO2') -> pd.DataFrame:
    """Convert FiO2 values to fractional form if they appear as percentages."""
    if fio2_col not in df.columns:
        raise KeyError(f"FiO2 column not found. Available columns: {list(df.columns)}")
    fio2 = df[fio2_col].astype(float)
    if fio2.max() > 1.0:
        if fio2.max() <= 100.0:
            fio2 = fio2 / 100.0
        else:
            fio2 = fio2 / 100.0
    df[fio2_col] = fio2.clip(lower=0.21, upper=1.0)
    return df


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived ventilator and oxygenation features."""
    df = df.copy()
    if 'SpO2' not in df.columns or 'FiO2' not in df.columns:
        raise KeyError('SpO2 and FiO2 are required to compute S/F ratio')
    df['SF_Ratio'] = df['SpO2'] / df['FiO2'].replace(0, np.nan)
    df['Minute_Ventilation'] = df['RR'] * df['tidal_volume']
    df['VSI'] = df['PEEP'] * df['tidal_volume']
    df['Shock_Index'] = df['HR'] / df['MAP'].replace(0, np.nan)
    df['Oxygen_Delivery_Proxy'] = df['SpO2'] * df['MAP']
    df['SF_Ratio'] = df['SF_Ratio'].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df['Shock_Index'] = df['Shock_Index'].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return df


def add_temporal_features(df: pd.DataFrame, group_col: Optional[str] = 'stay_id') -> pd.DataFrame:
    """Add lag and first-difference temporal features for core variables."""
    df = df.copy()
    sort_cols = [group_col, 'charttime'] if group_col in df.columns and 'charttime' in df.columns else None
    if sort_cols:
        df = df.sort_values(sort_cols)
    if group_col in df.columns:
        groups = df.groupby(group_col, group_keys=False)
    else:
        groups = [(None, df)]

    for col in TEMPORAL_COLUMNS:
        if col not in df.columns:
            raise KeyError(f'{col} is required for temporal feature creation')
        lag1 = groups[col].shift(1)
        lag2 = groups[col].shift(2)
        df[f'{col}_lag1'] = lag1
        df[f'{col}_lag2'] = lag2
        df[f'{col}_diff1'] = df[col] - df[f'{col}_lag1']

    df = df.bfill().fillna(0.0)
    return df


def add_rolling_statistics(df: pd.DataFrame, window: int = 5, group_col: Optional[str] = 'stay_id') -> pd.DataFrame:
    """Add rolling mean and standard deviation features."""
    df = df.copy()
    sort_cols = [group_col, 'charttime'] if group_col in df.columns and 'charttime' in df.columns else None
    if sort_cols:
        df = df.sort_values(sort_cols)
    if group_col in df.columns:
        groups = df.groupby(group_col, group_keys=False)
    else:
        groups = [(None, df)]

    for col in ROLLING_MEAN_COLS:
        if col not in df.columns:
            raise KeyError(f'{col} is required for rolling mean')
        df[f'{col}_rolling_mean_{window}'] = groups[col].transform(lambda x: x.rolling(window, min_periods=1).mean())

    for col in ROLLING_STD_COLS:
        if col not in df.columns:
            raise KeyError(f'{col} is required for rolling std')
        df[f'{col}_rolling_std_{window}'] = groups[col].transform(lambda x: x.rolling(window, min_periods=1).std().fillna(0.0))

    return df


def add_risk_labels(df: pd.DataFrame, thresholds: RiskThresholds) -> pd.DataFrame:
    """Add binary risk labels based on engineered features and thresholds."""
    df = df.copy()
    if 'SF_Ratio' not in df.columns or 'FiO2' not in df.columns or 'PEEP' not in df.columns:
        raise KeyError('SF_Ratio, FiO2, and PEEP are required for refractory hypoxia risk')
    if 'RR' not in df.columns or 'MAP' not in df.columns or 'Shock_Index' not in df.columns:
        raise KeyError('RR, MAP, and Shock_Index are required for risk labels')
    if 'Minute_Ventilation' not in df.columns:
        raise KeyError('Minute_Ventilation is required for V/Q mismatch risk')
    if 'Oxygen_Delivery_Proxy' not in df.columns:
        raise KeyError('Oxygen_Delivery_Proxy is required for oxygen delivery failure risk')

    df['Hypoxemia_Risk'] = (df['SpO2'] < 92).astype(int)
    df['Refractory_Hypoxia_Risk'] = (
        (df['SF_Ratio'] < 200.0)
        & (df['FiO2'] > 0.6)
        & (df['PEEP'] > 8.0)
    ).astype(int)
    df['Ventilation_Instability_Risk'] = (df.get('RR_rolling_std_5', df['RR'].rolling(5, min_periods=1).std().fillna(0.0)) > thresholds.threshold_RR).astype(int)
    df['Shock_Risk'] = (df['Shock_Index'] > 0.9).astype(int)
    df['VQ_Mismatch_Risk'] = ((df['Minute_Ventilation'] / df['MAP'].replace(0, np.nan)) > thresholds.threshold_VQ).astype(int)
    df['Oxygen_Delivery_Failure_Risk'] = (df['Oxygen_Delivery_Proxy'] < thresholds.threshold_OD).astype(int)
    df[['VQ_Mismatch_Risk', 'Oxygen_Delivery_Failure_Risk']] = df[['VQ_Mismatch_Risk', 'Oxygen_Delivery_Failure_Risk']].fillna(0).astype(int)
    return df


def engineer_ventilator_dataset(
    df: pd.DataFrame,
    thresholds: Optional[RiskThresholds] = None,
) -> pd.DataFrame:
    """Apply the full pipeline of feature engineering and risk labeling."""
    thresholds = thresholds or RiskThresholds()
    original_index = df.index
    df = normalize_column_names(df)
    df = ensure_fio2_fraction(df)
    df = add_engineered_features(df)
    df = add_temporal_features(df)
    df = add_rolling_statistics(df, window=5)
    df = add_risk_labels(df, thresholds)
    if original_index is not None:
        df = df.loc[original_index]
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description='Create engineered ventilator features and risk labels')
    parser.add_argument('--input', required=True, help='Input CSV file path')
    parser.add_argument('--output', required=True, help='Output CSV file path')
    parser.add_argument('--threshold_rr', type=float, default=3.0, help='Threshold for RR rolling std risk')
    parser.add_argument('--threshold_vq', type=float, default=0.15, help='Threshold for MV/MAP V/Q mismatch risk')
    parser.add_argument('--threshold_od', type=float, default=6000.0, help='Threshold for oxygen delivery failure risk')
    args = parser.parse_args()

    header = pd.read_csv(args.input, nrows=0)
    parse_dates = ['charttime'] if 'charttime' in header.columns else []
    df = pd.read_csv(args.input, parse_dates=parse_dates)

    engineered = engineer_ventilator_dataset(
        df,
        thresholds=RiskThresholds(
            threshold_RR=args.threshold_rr,
            threshold_VQ=args.threshold_vq,
            threshold_OD=args.threshold_od,
        ),
    )
    engineered.to_csv(args.output, index=False)
    print(f'Wrote engineered dataset with {len(engineered.columns)} columns to {args.output}')


if __name__ == '__main__':
    main()
