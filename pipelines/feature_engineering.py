"""
Feature Engineering Pipeline
Blockchain-Enabled Digital Twin Framework for Ventilator Optimization
Dataset: clean_full_data_v2.csv (800K rows, 4566 patients, 11 columns)
"""

import os
import argparse
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle
import warnings
warnings.filterwarnings('ignore')

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipelines.ppo_feature_engineering import PPO_STATE_FEATURES, add_ppo_features

# ─── Config ──────────────────────────────────────────────────────────────────
DATA_PATH   = os.path.join(os.path.dirname(__file__), '..', 'clean_full_data_v2.csv')
OUT_DIR     = os.path.join(os.path.dirname(__file__), '..', 'ml')
SEQ_LEN     = 12          # 3-hour window at 15-min intervals
BASE_FEATURE_COLS = ['HR', 'MAP', 'RespRate', 'SpO2', 'PEEP', 'FiO2', 'TidalVol']
DERIVED_FEATURE_COLS = [
    'SpO2_FiO2_Ratio',
    'Minute_Ventilation_Lpm',
    'PEEP_FiO2_Product',
    'MAP_HR_Ratio',
]
PPO_FEATURE_COLS = [
    col for col in PPO_STATE_FEATURES if col not in BASE_FEATURE_COLS
]
TREND_FEATURE_COLS = [
    'HR_Change',
    'MAP_Change',
    'RespRate_Change',
    'SpO2_Change',
    'PEEP_Change',
    'FiO2_Change',
    'TidalVol_Change',
]
FEATURE_COLS = BASE_FEATURE_COLS + DERIVED_FEATURE_COLS + PPO_FEATURE_COLS
TARGET_REG  = 'Next_SpO2'
TARGET_CLS  = 'Hypoxia_Risk'

# Clinical valid ranges for outlier clipping
CLIP_BOUNDS = {
    'HR':       (0, 300),
    'MAP':      (0, 200),
    'RespRate': (0, 80),
    'SpO2':     (50, 100),
    'PEEP':     (0, 30),
    'FiO2':     (21, 100),
    'TidalVol': (100, 1000),
    'Next_SpO2':(50, 100),
}

def load_and_clean(path: str) -> pd.DataFrame:
    print(f"[1/5] Loading data from {path} ...")
    df = pd.read_csv(path, parse_dates=['charttime'])
    print(f"      Raw shape: {df.shape}")

    # Clip to clinical bounds
    for col, (lo, hi) in CLIP_BOUNDS.items():
        if col in df.columns:
            df[col] = df[col].clip(lo, hi)

    # Sort per patient, chronologically
    df = df.sort_values(['stay_id', 'charttime']).reset_index(drop=True)
    print(f"      After cleaning: {df.shape}")
    return df


def add_derived_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Add derived ICU variables from current vitals and ventilator settings."""
    if verbose:
        print("[2/5] Adding derived ICU features ...")
    df['SpO2_FiO2_Ratio'] = (df['SpO2'] * 100.0) / df['FiO2']
    df['Minute_Ventilation_Lpm'] = df['TidalVol'] * df['RespRate'] / 1000.0
    df['PEEP_FiO2_Product'] = df['PEEP'] * df['FiO2'] / 100.0
    df['MAP_HR_Ratio'] = df['MAP'] / df['HR'].replace(0, np.nan)
    df['MAP_HR_Ratio'] = df['MAP_HR_Ratio'].fillna(0.0)
    return df


def add_ppo_state_reward_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Add PPO state features and reward columns used by Phase 4 policy training."""
    if verbose:
        print("[3/6] Adding PPO state/reward features ...")
    return add_ppo_features(df)


def add_lag_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Add 1- and 2-step lag features per patient for each feature column."""
    if verbose:
        print("[4/6] Engineering lag features ...")
    grp = df.groupby('stay_id')
    for col in FEATURE_COLS:
        df[f'{col}_lag1'] = grp[col].shift(1)
        df[f'{col}_lag2'] = grp[col].shift(2)
        rolling = grp[col].rolling(4, min_periods=1)
        df[f'{col}_roll4_mean'] = rolling.mean().reset_index(level=0, drop=True)
        df[f'{col}_roll4_std'] = rolling.std().reset_index(level=0, drop=True).fillna(0)

    df = df.dropna().reset_index(drop=True)
    if verbose:
        print(f"      After lag features: {df.shape}")
    return df


def add_trend_features(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Add trend and change-rate features from the current and previous measurements."""
    if verbose:
        print("[5/6] Adding trend features ...")
    df['HR_Change'] = df['HR'] - df['HR_lag1']
    df['MAP_Change'] = df['MAP'] - df['MAP_lag1']
    df['RespRate_Change'] = df['RespRate'] - df['RespRate_lag1']
    df['SpO2_Change'] = df['SpO2'] - df['SpO2_lag1']
    df['PEEP_Change'] = df['PEEP'] - df['PEEP_lag1']
    df['FiO2_Change'] = df['FiO2'] - df['FiO2_lag1']
    df['TidalVol_Change'] = df['TidalVol'] - df['TidalVol_lag1']
    return df


def build_sequences(df: pd.DataFrame, seq_len: int):
    """Build (X_seq, X_static, y_reg, y_cls) arrays from grouped patient sequences."""
    print(f"[6/6] Building LSTM sequences (window={seq_len}) ...")
    
    # All feature columns after lag engineering
    all_feat_cols = (
        FEATURE_COLS +
        TREND_FEATURE_COLS +
        [f'{c}_lag1' for c in FEATURE_COLS] +
        [f'{c}_lag2' for c in FEATURE_COLS] +
        [f'{c}_roll4_mean' for c in FEATURE_COLS] +
        [f'{c}_roll4_std'  for c in FEATURE_COLS]
    )
    all_feat_cols = [c for c in all_feat_cols if c in df.columns]

    X_seqs, y_regs, y_clss = [], [], []
    stay_ids_out = []

    for stay_id, grp in df.groupby('stay_id'):
        grp = grp.reset_index(drop=True)
        feat_arr = grp[all_feat_cols].values
        reg_arr  = grp[TARGET_REG].values
        cls_arr  = grp[TARGET_CLS].values

        for i in range(seq_len, len(grp)):
            X_seqs.append(feat_arr[i - seq_len : i])
            y_regs.append(reg_arr[i])
            y_clss.append(cls_arr[i])
            stay_ids_out.append(stay_id)

    X_seqs = np.array(X_seqs, dtype=np.float32)
    y_regs = np.array(y_regs, dtype=np.float32)
    y_clss = np.array(y_clss, dtype=np.int32)

    print(f"      Sequences shape: X={X_seqs.shape}, y_reg={y_regs.shape}, y_cls={y_clss.shape}")
    print(f"      Hypoxia positive rate: {y_clss.mean()*100:.2f}%")
    return X_seqs, y_regs, y_clss, all_feat_cols


def scale_and_split(X, y_reg, y_cls, out_dir):
    """Scale features, stratified split, save artefacts."""
    print("[split] Scaling and splitting ...")
    n, t, f = X.shape

    # Fit scaler on 2D view, apply back
    X_flat = X.reshape(-1, f)
    scaler = StandardScaler()
    X_flat_scaled = scaler.fit_transform(X_flat)
    X_scaled = X_flat_scaled.reshape(n, t, f)

    # Scale regression target
    y_reg_mean, y_reg_std = y_reg.mean(), y_reg.std()
    y_reg_scaled = (y_reg - y_reg_mean) / (y_reg_std + 1e-8)

    # Stratified split: 70/15/15
    idx = np.arange(n)
    idx_train, idx_temp, y_tr, y_te = train_test_split(
        idx, y_cls, test_size=0.30, stratify=y_cls, random_state=42
    )
    idx_val, idx_test = train_test_split(
        idx_temp, test_size=0.50, stratify=y_te, random_state=42
    )

    splits = {
        'X_train': X_scaled[idx_train], 'X_val': X_scaled[idx_val], 'X_test': X_scaled[idx_test],
        'y_reg_train': y_reg_scaled[idx_train], 'y_reg_val': y_reg_scaled[idx_val], 'y_reg_test': y_reg_scaled[idx_test],
        'y_cls_train': y_cls[idx_train], 'y_cls_val': y_cls[idx_val], 'y_cls_test': y_cls[idx_test],
        'scaler': scaler,
        'y_reg_mean': y_reg_mean, 'y_reg_std': y_reg_std,
    }

    os.makedirs(out_dir, exist_ok=True)
    for key, val in splits.items():
        path = os.path.join(out_dir, f'{key}.pkl')
        with open(path, 'wb') as fh:
            pickle.dump(val, fh)

    print(f"      Train: {splits['X_train'].shape}, Val: {splits['X_val'].shape}, Test: {splits['X_test'].shape}")
    print(f"      Saved to {out_dir}/")
    return splits


def main():
    parser = argparse.ArgumentParser(description="Feature engineering for ventilator sequences")
    parser.add_argument(
        "--data-path",
        default=DATA_PATH,
        help="Input CSV path with telemetry + labels",
    )
    parser.add_argument(
        "--out-dir",
        default=OUT_DIR,
        help="Output directory for pipeline artifacts",
    )
    parser.add_argument(
        "--seq-len",
        type=int,
        default=SEQ_LEN,
        help="Sequence length window",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Feature Engineering Pipeline")
    print("=" * 60)
    df = load_and_clean(args.data_path)
    df = add_derived_features(df)
    df = add_ppo_state_reward_features(df)
    df = add_lag_features(df)
    df = add_trend_features(df)
    X, y_reg, y_cls, feat_cols = build_sequences(df, args.seq_len)

    # Save feature column list for inference
    feat_path = os.path.join(args.out_dir, 'feature_cols.pkl')
    os.makedirs(args.out_dir, exist_ok=True)
    with open(feat_path, 'wb') as fh:
        pickle.dump(feat_cols, fh)

    splits = scale_and_split(X, y_reg, y_cls, args.out_dir)

    print("[5/5] Summary:")
    print(f"  Feature columns  : {len(feat_cols)}")
    print(f"  Sequence length  : {args.seq_len}")
    print(f"  Total sequences  : {X.shape[0]:,}")
    print(f"  Training samples : {splits['X_train'].shape[0]:,}")
    print(f"  Positive (train) : {splits['y_cls_train'].mean()*100:.2f}%")
    print("=" * 60)
    print("  Pipeline complete. Run ml/lstm_training.py next.")
    print("=" * 60)

if __name__ == '__main__':
    main()
