"""
LSTM Feature Enrichment Pipeline
Generates LSTM-based predictions for all 7 ventilator parameters
Creates enriched CSV with original + predicted features for downstream modeling
"""

import os
import pickle
import numpy as np
import pandas as pd
from pathlib import Path

import tensorflow as tf
from tensorflow.keras import models

# ─── Config ──────────────────────────────────────────────────────────────────
ML_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACT_DIR = os.path.abspath(os.environ.get("LSTM_ARTIFACTS_DIR", os.path.join(ML_DIR, 'ml')))
MODEL_PATH = os.path.join(ARTIFACT_DIR, 'models', 'lstm_model.keras')
DATA_PATH = os.path.join(ML_DIR, 'clean_full_data_v2.csv')
OUTPUT_DIR = os.path.join(ML_DIR, 'data')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'clean_full_data_lstm_enriched.csv')

FEATURE_COLS = ['HR', 'MAP', 'RespRate', 'SpO2', 'PEEP', 'FiO2', 'TidalVol']
TARGET_REG = 'Next_SpO2'
TARGET_CLS = 'Hypoxia_Risk'

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


def load_and_prepare_data():
    """Load original data and prepare for LSTM inference."""
    print("[1/4] Loading original dataset ...")
    df = pd.read_csv(DATA_PATH, parse_dates=['charttime'])
    print(f"      Shape: {df.shape}")
    
    # Clip to clinical bounds
    for col, (lo, hi) in CLIP_BOUNDS.items():
        if col in df.columns:
            df[col] = df[col].clip(lo, hi)
    
    # Sort per patient, chronologically
    df = df.sort_values(['stay_id', 'charttime']).reset_index(drop=True)
    print(f"      After cleaning: {df.shape}")
    return df


def add_lag_features(df):
    """Add lag features (same as training pipeline)."""
    print("[2/4] Engineering lag features ...")
    grp = df.groupby('stay_id')
    for col in FEATURE_COLS:
        df[f'{col}_lag1'] = grp[col].shift(1)
        df[f'{col}_lag2'] = grp[col].shift(2)
        df[f'{col}_roll4_mean'] = grp[col].transform(lambda x: x.rolling(4, min_periods=1).mean())
        df[f'{col}_roll4_std']  = grp[col].transform(lambda x: x.rolling(4, min_periods=1).std().fillna(0))
    
    df = df.dropna().reset_index(drop=True)
    print(f"      After lags: {df.shape}")
    return df


def load_scaler():
    """Load the scaler used during training."""
    scaler_path = os.path.join(ARTIFACT_DIR, 'scaler.pkl')
    if not os.path.exists(scaler_path):
        print("[!] WARNING: scaler.pkl not found. Using identity scaling.")
        return None
    
    with open(scaler_path, 'rb') as fh:
        return pickle.load(fh)


def build_sequences_for_inference(df, seq_len=12):
    """Build sequences from full dataset for LSTM inference."""
    print(f"[3/4] Building sequences (window={seq_len}) ...")
    
    all_feat_cols = (
        FEATURE_COLS +
        [f'{c}_lag1' for c in FEATURE_COLS] +
        [f'{c}_lag2' for c in FEATURE_COLS] +
        [f'{c}_roll4_mean' for c in FEATURE_COLS] +
        [f'{c}_roll4_std' for c in FEATURE_COLS]
    )
    
    X_list = []
    stay_ids = []
    indices = []
    
    for stay_id, grp in df.groupby('stay_id'):
        grp_vals = grp[all_feat_cols].values
        
        # Build sequences
        for i in range(len(grp_vals) - seq_len):
            seq = grp_vals[i:i + seq_len]
            X_list.append(seq)
            stay_ids.append(stay_id)
            indices.append(i + seq_len)  # Index of the target row
    
    X = np.array(X_list)
    print(f"      Sequences built: {X.shape}")
    return X, np.array(stay_ids), np.array(indices), df


def generate_predictions(model, X, scaler=None):
    """Generate LSTM predictions for SpO2 and hypoxia risk."""
    print(f"[4/4] Running LSTM inference on {len(X)} sequences ...")
    
    pred_spo2_scaled, pred_hypoxia = model.predict(X, batch_size=512, verbose=1)
    
    # Inverse scale if scaler exists
    if scaler and hasattr(scaler, 'inverse_transform'):
        pred_spo2 = scaler.inverse_transform(pred_spo2_scaled)
    else:
        pred_spo2 = pred_spo2_scaled
    
    pred_spo2 = pred_spo2.flatten()
    pred_hypoxia = pred_hypoxia.flatten()
    
    print(f"      Predictions generated: {len(pred_spo2)} samples")
    return pred_spo2, pred_hypoxia


def build_enriched_dataset(df, stay_ids, indices, pred_spo2, pred_hypoxia):
    """Build enriched CSV with LSTM predictions."""
    print("\n[OUT] Building enriched dataset ...")
    
    # Create output dataframe
    results = []
    for i, (stay_id, idx, spo2_pred, hyp_pred) in enumerate(
        zip(stay_ids, indices, pred_spo2, pred_hypoxia)
    ):
        # Get original row
        orig_row = df[(df['stay_id'] == stay_id) & (df.index == idx - 1)]
        if len(orig_row) == 0:
            continue
        
        row_dict = orig_row.iloc[0].to_dict()
        row_dict['lstm_pred_next_spo2'] = float(spo2_pred)
        row_dict['lstm_pred_hypoxia_prob'] = float(hyp_pred)
        results.append(row_dict)
    
    enriched_df = pd.DataFrame(results)
    print(f"      Enriched dataset shape: {enriched_df.shape}")
    
    return enriched_df


def main():
    print("=" * 70)
    print("  LSTM Feature Enrichment — Ventilator Optimization Framework")
    print("=" * 70)
    
    # Check if model exists
    if not os.path.exists(MODEL_PATH):
        print(f"\n[ERROR] Model not found at {MODEL_PATH}")
        print("        Please train the LSTM first: python ml/lstm_training.py")
        return
    
    # Load data and model
    df = load_and_prepare_data()
    df_features = add_lag_features(df)
    model = models.load_model(MODEL_PATH, custom_objects=None)
    scaler = load_scaler()
    
    # Build sequences and generate predictions
    X, stay_ids, indices, df_orig = build_sequences_for_inference(df_features)
    pred_spo2, pred_hypoxia = generate_predictions(model, X, scaler)
    
    # Build enriched dataset
    enriched_df = build_enriched_dataset(df_orig, stay_ids, indices, pred_spo2, pred_hypoxia)
    
    # Save to CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    enriched_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n[SAVE] Enriched dataset → {OUTPUT_FILE}")
    print(f"       Columns: {list(enriched_df.columns)}")
    print(f"       Rows: {len(enriched_df)}")
    
    # Summary statistics
    print("\n[SUMMARY] LSTM Prediction Statistics")
    print(f"  Next SpO2 (predicted):")
    print(f"    Mean: {pred_spo2.mean():.2f}, Std: {pred_spo2.std():.2f}")
    print(f"    Min: {pred_spo2.min():.2f}, Max: {pred_spo2.max():.2f}")
    print(f"  Hypoxia Risk (predicted probability):")
    print(f"    Mean: {pred_hypoxia.mean():.4f}, Std: {pred_hypoxia.std():.4f}")
    print(f"    Min: {pred_hypoxia.min():.4f}, Max: {pred_hypoxia.max():.4f}")
    
    print("\n[DONE] Feature enrichment complete!")
    return enriched_df


if __name__ == '__main__':
    main()
