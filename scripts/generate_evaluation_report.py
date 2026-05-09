#!/usr/bin/env python
"""
Generate evaluation report for trained multi-risk LSTM model.
Run this after model training to create the evaluation metrics JSON.
"""

import os
import sys
import json
import pickle
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sklearn.metrics import (
    roc_auc_score, f1_score, average_precision_score, 
    mean_absolute_error, mean_squared_error
)
import tensorflow as tf

ML_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ml'))
MULTI_RISK_DIR = os.path.join(ML_DIR, "multi_risk")
MODEL_PATH = os.path.join(MULTI_RISK_DIR, "multi_risk_lstm.keras")
REPORT_DIR = os.path.abspath(os.path.join(ML_DIR, '..', 'reports'))

REG_TARGETS = ["Next_SpO2", "Next_HR", "Next_MAP", "Next_RespRate", "Next_TidalVol"]
CLS_TARGETS = ["Hypoxia_Risk", "Tachycardia_Risk", "Hypotension_Risk", "Tachypnea_Risk", "VILI_Risk"]


def main():
    print("=" * 70)
    print("  Generating Evaluation Report for Multi-Risk LSTM")
    print("=" * 70)
    
    # Load model
    print(f"\n[LOAD] Loading model from {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        print(f"[ERR] Model file not found: {MODEL_PATH}")
        print("      Run ml/multi_risk_training.py first")
        return False
    
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        print("[OK] Model loaded successfully")
    except Exception as e:
        print(f"[ERR] Failed to load model: {e}")
        return False
    
    # Load test data
    print(f"\n[LOAD] Loading test data from {MULTI_RISK_DIR}")
    try:
        def pk(name):
            path = os.path.join(MULTI_RISK_DIR, f'{name}.pkl')
            with open(path, 'rb') as fh:
                return pickle.load(fh)
        
        X_test = pk('X_test')
        y_reg_test = pk('y_reg_test')
        y_cls_test = pk('y_cls_test')
        y_reg_mean = pk('y_reg_mean')
        y_reg_std = pk('y_reg_std')
        print(f"[OK] Loaded test data: X_test {X_test.shape}, y_reg {y_reg_test.shape}, y_cls {y_cls_test.shape}")
    except Exception as e:
        print(f"[ERR] Failed to load test data: {e}")
        return False
    
    # Evaluate
    print("\n[EVAL] Evaluating on test set ...")
    
    try:
        pred_dict = model.predict(X_test, batch_size=512, verbose=0)
    except Exception as e:
        print(f"[ERR] Prediction failed: {e}")
        return False
    
    results = {}
    
    # Evaluate regression targets
    print("\n  ── Regression Targets ────────────────────")
    for i, target in enumerate(REG_TARGETS):
        pred_scaled = pred_dict[target].flatten()
        y_mean = y_reg_mean[i]
        y_std = y_reg_std[i]
        
        # Inverse scale
        pred = pred_scaled * y_std + y_mean
        true = y_reg_test[:, i] * y_std + y_mean
        
        mae = mean_absolute_error(true, pred)
        rmse = np.sqrt(mean_squared_error(true, pred))
        
        results[f'{target}_mae'] = round(float(mae), 4)
        results[f'{target}_rmse'] = round(float(rmse), 4)
        print(f"  {target:18s} — MAE: {mae:7.3f}, RMSE: {rmse:7.3f}")
    
    # Evaluate classification targets
    print("\n  ── Classification Targets ────────────────")
    for i, target in enumerate(CLS_TARGETS):
        pred_prob = pred_dict[target].flatten()
        true = y_cls_test[:, i]
        
        auroc = roc_auc_score(true, pred_prob)
        ap = average_precision_score(true, pred_prob)
        
        # Find optimal threshold for F1
        best_f1 = 0.0
        best_thresh = 0.5
        for thresh in np.arange(0.1, 0.95, 0.05):
            f1_candidate = f1_score(true, (pred_prob > thresh).astype(int))
            if f1_candidate > best_f1:
                best_f1 = f1_candidate
                best_thresh = thresh
        
        f1_default = f1_score(true, (pred_prob > 0.5).astype(int))
        
        results[f'{target}_auroc'] = round(float(auroc), 4)
        results[f'{target}_auc_pr'] = round(float(ap), 4)
        results[f'{target}_f1_thresh05'] = round(float(f1_default), 4)
        results[f'{target}_f1_optimal'] = round(float(best_f1), 4)
        results[f'{target}_optimal_threshold'] = round(float(best_thresh), 2)
        
        pos_rate = true.mean() * 100
        print(f"  {target:18s} — AUROC: {auroc:.4f}, AUC-PR: {ap:.4f}, " 
              f"F1@0.5: {f1_default:.4f}, F1_opt: {best_f1:.4f} (threshold={best_thresh:.2f}), "
              f"positive_rate={pos_rate:.2f}%")

    print("  ──────────────────────────────────────────")

    # Save evaluation report
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, 'model_evaluation_multi_risk.json')
    try:
        with open(report_path, 'w') as fh:
            json.dump(results, fh, indent=2)
        print(f"\n[OK] Evaluation report saved → {report_path}")
        return True
    except Exception as e:
        print(f"[ERR] Failed to save report: {e}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
