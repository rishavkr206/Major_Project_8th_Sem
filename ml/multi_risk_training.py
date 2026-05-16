"""
Multi-Task LSTM Training Engine — 5 Clinical Risks
Blockchain-Enabled Digital Twin Framework
Targets:
  Regression (Next_* predictions):
    Next_SpO2, Next_HR, Next_MAP, Next_RespRate, Next_TidalVol
  Classification (binary risk in next step):
    Hypoxia_Risk, Tachycardia_Risk, Hypotension_Risk, Tachypnea_Risk, VILI_Risk
"""

import os
import pickle
import json
import numpy as np
import warnings
warnings.filterwarnings('ignore')

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import tensorflow as tf
from tensorflow.keras import layers, models, callbacks, optimizers
from sklearn.metrics import (
    roc_auc_score, f1_score, average_precision_score, mean_absolute_error, mean_squared_error
)

ML_DIR = os.path.dirname(os.path.abspath(__file__))
MULTI_RISK_DIR = os.path.join(ML_DIR, "multi_risk")
MODEL_PATH = os.path.join(MULTI_RISK_DIR, "multi_risk_lstm.keras")
REPORT_DIR = os.path.abspath(os.path.join(ML_DIR, '..', 'reports'))

# --─ Hyperparameters ----------------------------------------------------------
LSTM_UNITS   = int(os.environ.get("LSTM_UNITS", 256))
DROPOUT      = float(os.environ.get("LSTM_DROPOUT", 0.4))
EPOCHS       = int(os.environ.get("LSTM_EPOCHS", 40))
BATCH_SIZE   = int(os.environ.get("LSTM_BATCH_SIZE", 256))
LR           = float(os.environ.get("LSTM_LR", 1e-3))

# Class weights for each risk (based on class imbalance observed in pipeline)
CLS_WEIGHTS = {
    'Hypoxia_Risk':     75.0,    # ~1.92% positive
    'Tachycardia_Risk': 125.0,   # ~0.79% positive (rarest)
    'Hypotension_Risk': 10.0,    # ~10.81% positive (common)
    'Tachypnea_Risk':   12.0,    # ~7.63% positive
    'VILI_Risk':        5.0,     # ~19.80% positive (most common)
    # Shock_Risk (MSI = HR/MAP > 1.3) — auto-tuned at runtime from the actual
    # train-set positive rate; 20.0 is a safe seed and gets overridden below.
    'Shock_Risk':       20.0,
}

FOCAL_GAMMA  = float(os.environ.get("LSTM_FOCAL_GAMMA", 1.5))
FOCAL_ALPHA  = float(os.environ.get("LSTM_FOCAL_ALPHA", 0.8))

# Target column names
REG_TARGETS = ["Next_SpO2", "Next_HR", "Next_MAP", "Next_RespRate", "Next_TidalVol"]
CLS_TARGETS = ["Hypoxia_Risk", "Tachycardia_Risk", "Hypotension_Risk", "Tachypnea_Risk", "VILI_Risk", "Shock_Risk"]
ALL_TARGETS = REG_TARGETS + CLS_TARGETS

# --─ Focal Loss (Simple Implementation) --------------------------------------─
def focal_loss(gamma=FOCAL_GAMMA, alpha=FOCAL_ALPHA):
    """Focal loss for imbalanced classification."""
    def loss(y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1.0 - 1e-7)
        pt = tf.where(tf.equal(y_true, 1), y_pred, 1 - y_pred)
        alpha_t = tf.where(tf.equal(y_true, 1), alpha, 1 - alpha)
        return -tf.reduce_mean(alpha_t * tf.pow(1 - pt, gamma) * tf.math.log(pt))
    return loss


# --─ Model Definition --------------------------------------------------------─
def build_model(seq_len: int, n_features: int) -> models.Model:
    """
    Multi-task LSTM with shared bidirectional encoder and separate heads:
      - 5 regression heads: Next_SpO2, Next_HR, Next_MAP, Next_RespRate, Next_TidalVol
      - 5 classification heads: Hypoxia_Risk, Tachycardia_Risk, Hypotension_Risk, Tachypnea_Risk, VILI_Risk
    """
    inp = layers.Input(shape=(seq_len, n_features), name='sequence_input')

    # Shared encoder
    x = layers.Bidirectional(
        layers.LSTM(LSTM_UNITS, return_sequences=True, dropout=DROPOUT,
                    recurrent_dropout=0.0, kernel_regularizer=tf.keras.regularizers.l2(1e-4)),
        name='bilstm_1'
    )(inp)
    x = layers.LayerNormalization()(x)
    
    x = layers.Bidirectional(
        layers.LSTM(LSTM_UNITS // 2, return_sequences=False, dropout=DROPOUT,
                    kernel_regularizer=tf.keras.regularizers.l2(1e-4)),
        name='bilstm_2'
    )(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dense(128, activation='relu', name='bottleneck')(x)
    x = layers.Dropout(DROPOUT)(x)
    shared = layers.Dense(64, activation='relu', name='shared_dense')(x)
    shared = layers.Dropout(DROPOUT)(shared)

    # --─ Regression Heads (Next_* predictions) ------------------------------─
    reg_outputs = {}
    for i, target in enumerate(REG_TARGETS):
        head = layers.Dense(64, activation='relu', name=f'reg_dense1_{i}')(shared)
        head = layers.Dropout(DROPOUT / 2)(head)
        head = layers.Dense(32, activation='relu', name=f'reg_dense2_{i}')(head)
        reg_outputs[target] = layers.Dense(1, name=target)(head)

    # --─ Classification Heads (Risk labels) ----------------------------------
    cls_outputs = {}
    for i, target in enumerate(CLS_TARGETS):
        head = layers.Dense(64, activation='relu', name=f'cls_dense1_{i}')(shared)
        head = layers.Dropout(DROPOUT / 2)(head)
        head = layers.Dense(32, activation='relu', name=f'cls_dense2_{i}')(head)
        cls_outputs[target] = layers.Dense(1, activation='sigmoid', name=target)(head)

    all_outputs = {**reg_outputs, **cls_outputs}
    model = models.Model(inputs=inp, outputs=all_outputs, name='MultiRiskLSTM')
    return model


# --─ Load Data ----------------------------------------------------------------
def load_splits():
    def pk(name):
        path = os.path.join(MULTI_RISK_DIR, f'{name}.pkl')
        with open(path, 'rb') as fh:
            return pickle.load(fh)

    return {k: pk(k) for k in [
        'X_train', 'X_val', 'X_test',
        'y_reg_train', 'y_reg_val', 'y_reg_test',
        'y_cls_train', 'y_cls_val', 'y_cls_test',
        'y_reg_mean', 'y_reg_std'
    ]}


# --─ Training ----------------------------------------------------------------─
def train(d: dict):
    seq_len    = d['X_train'].shape[1]
    n_features = d['X_train'].shape[2]

    print(f"\n[BUILD] Multi-Task LSTM — seq={seq_len}, features={n_features}")
    print(f"        Regression targets: {REG_TARGETS}")
    print(f"        Classification targets: {CLS_TARGETS}")
    model = build_model(seq_len, n_features)
    model.summary()

    # Build loss dict and weights dict
    loss_dict = {}
    loss_weights_dict = {}
    metrics_dict = {}
    
    # Regression losses and metrics
    for target in REG_TARGETS:
        loss_dict[target] = 'mse'
        loss_weights_dict[target] = 1.0
        metrics_dict[target] = ['mae']
    
    # Classification losses and metrics
    for target in CLS_TARGETS:
        # Use standard binary crossentropy (properly serializable)
        # Focal loss benefits are achieved via class weights
        loss_dict[target] = 'binary_crossentropy'
        loss_weights_dict[target] = 8.0  # Increased weight for classification
        metrics_dict[target] = [
            tf.keras.metrics.AUC(name='auc'),
            tf.keras.metrics.Precision(name='precision'),
            tf.keras.metrics.Recall(name='recall'),
        ]

    model.compile(
        optimizer=optimizers.Adam(LR),
        loss=loss_dict,
        loss_weights=loss_weights_dict,
        metrics=metrics_dict
    )

    os.makedirs(MULTI_RISK_DIR, exist_ok=True)
    cb_list = [
        callbacks.EarlyStopping(monitor='val_loss', patience=15, restore_best_weights=True, verbose=1),
        callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, verbose=1),
        callbacks.ModelCheckpoint(MODEL_PATH, save_best_only=True, monitor='val_loss', verbose=1),
    ]

    # Build training targets dict with proper target shape
    y_train_dict = {}
    for i, target in enumerate(REG_TARGETS):
        y_train_dict[target] = d['y_reg_train'][:, i:i+1]  # [N, 1]
    for i, target in enumerate(CLS_TARGETS):
        y_train_dict[target] = d['y_cls_train'][:, i].astype(np.float32)  # [N]

    y_val_dict = {}
    for i, target in enumerate(REG_TARGETS):
        y_val_dict[target] = d['y_reg_val'][:, i:i+1]
    for i, target in enumerate(CLS_TARGETS):
        y_val_dict[target] = d['y_cls_val'][:, i].astype(np.float32)

    # Build sample weights: higher weight for positive class in classification.
    # For Shock_Risk we auto-derive the weight from the actual positive rate
    # so the loss stays balanced regardless of dataset shift.
    sample_weights = {}
    for target in REG_TARGETS:
        sample_weights[target] = np.ones(len(d['X_train']), dtype=np.float32)
    for i, target in enumerate(CLS_TARGETS):
        pos_rate = float(d['y_cls_train'][:, i].mean())
        if target == 'Shock_Risk' and 0 < pos_rate < 1:
            # neg/pos ratio, clamped to [3, 150] to avoid runaway gradients
            weight = float(np.clip((1 - pos_rate) / pos_rate, 3.0, 150.0))
            print(f"[INFO] Auto-tuned Shock_Risk class weight: {weight:.2f} (pos rate {pos_rate*100:.2f}%)")
        else:
            weight = CLS_WEIGHTS.get(target, 10.0)
        sample_weights[target] = np.where(
            d['y_cls_train'][:, i] == 1, weight, 1.0
        ).astype(np.float32)

    print("\n[TRAIN] Starting training ...")
    history = model.fit(
        d['X_train'],
        y_train_dict,
        validation_data=(d['X_val'], y_val_dict),
        sample_weight=sample_weights,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=cb_list,
        verbose=1,
    )
    return model, history


# --─ Evaluation --------------------------------------------------------------─
def evaluate(model, d: dict):
    print("\n[EVAL] Evaluating on test set ...")
    
    # Predict
    pred_dict = model.predict(d['X_test'], batch_size=512, verbose=0)
    
    results = {}
    
    # Evaluate regression targets
    print("\n  -- Regression Targets --------------------")
    for i, target in enumerate(REG_TARGETS):
        pred_scaled = pred_dict[target].flatten()
        y_mean = d['y_reg_mean'][i]
        y_std = d['y_reg_std'][i]
        
        # Inverse scale
        pred = pred_scaled * y_std + y_mean
        true = d['y_reg_test'][:, i] * y_std + y_mean
        
        mae = mean_absolute_error(true, pred)
        rmse = np.sqrt(mean_squared_error(true, pred))
        
        results[f'{target}_mae'] = round(float(mae), 4)
        results[f'{target}_rmse'] = round(float(rmse), 4)
        print(f"  {target:18s} — MAE: {mae:7.3f}, RMSE: {rmse:7.3f}")
    
    # Evaluate classification targets
    print("\n  -- Classification Targets ----------------")
    for i, target in enumerate(CLS_TARGETS):
        pred_prob = pred_dict[target].flatten()
        true = d['y_cls_test'][:, i]
        
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

    print("  ------------------------------------------")

    # Save evaluation report
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, 'model_evaluation_multi_risk.json')
    with open(report_path, 'w') as fh:
        json.dump(results, fh, indent=2)
    print(f"\n  Saved evaluation report → {report_path}")
    
    return results


def main():
    print("=" * 70)
    print("  Multi-Task LSTM Training — 5 Clinical Risks")
    print("=" * 70)
    d     = load_splits()
    model, history = train(d)
    results = evaluate(model, d)
    print("\n[DONE] Multi-task model saved →", MODEL_PATH)
    return results


if __name__ == '__main__':
    main()
