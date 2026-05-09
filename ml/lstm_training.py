"""
LSTM Forecasting Engine — Training Script
Blockchain-Enabled Digital Twin Framework
Targets: Next_SpO2 (regression) + Hypoxia_Risk (binary classification)
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
    roc_auc_score, f1_score, average_precision_score,
    mean_absolute_error, mean_squared_error
)

ML_DIR = os.path.dirname(os.path.abspath(__file__))
# Pickles from feature_engineering live here (override with LSTM_ARTIFACTS_DIR to match inference)
ARTIFACT_DIR = os.path.abspath(os.environ.get("LSTM_ARTIFACTS_DIR", ML_DIR))
MODEL_DIR = os.path.join(ARTIFACT_DIR, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "lstm_model.keras")
REPORT_DIR = os.path.join(ML_DIR, '..', 'reports')

# ─── Hyperparameters ──────────────────────────────────────────────────────────
LSTM_UNITS   = int(os.environ.get("LSTM_UNITS", 256))
DROPOUT      = float(os.environ.get("LSTM_DROPOUT", 0.4))
EPOCHS       = int(os.environ.get("LSTM_EPOCHS", 30))
BATCH_SIZE   = int(os.environ.get("LSTM_BATCH_SIZE", 256))
LR           = float(os.environ.get("LSTM_LR", 1e-3))
CLS_WEIGHT   = float(os.environ.get("LSTM_CLS_WEIGHT", 75))
FOCAL_GAMMA  = float(os.environ.get("LSTM_FOCAL_GAMMA", 1.5))
FOCAL_ALPHA  = float(os.environ.get("LSTM_FOCAL_ALPHA", 0.8))

# ─── Focal Loss ───────────────────────────────────────────────────────────────
def focal_loss(gamma=FOCAL_GAMMA, alpha=FOCAL_ALPHA):
    def loss(y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1.0 - 1e-7)
        pt     = tf.where(tf.equal(y_true, 1), y_pred, 1 - y_pred)
        alpha_t = tf.where(tf.equal(y_true, 1), alpha, 1 - alpha)
        return -tf.reduce_mean(alpha_t * tf.pow(1 - pt, gamma) * tf.math.log(pt))
    return loss


# ─── Model Definition ─────────────────────────────────────────────────────────
def build_model(seq_len: int, n_features: int) -> models.Model:
    """
    Bidirectional LSTM with two output heads:
      - next_spo2  : scalar regression
      - hypoxia    : binary classification probability
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
    x = layers.Dense(128, activation='relu', name='bottleneck')(x)  # Increased capacity
    x = layers.Dropout(DROPOUT)(x)
    shared = layers.Dense(64, activation='relu', name='shared_dense')(x)
    shared = layers.Dropout(DROPOUT)(shared)

    # Head 1 — Next SpO2 regression
    reg_head = layers.Dense(64, activation='relu', name='reg_dense_1')(shared)
    reg_head = layers.Dropout(DROPOUT / 2)(reg_head)
    reg_head = layers.Dense(32, activation='relu', name='reg_dense_2')(reg_head)
    reg_out  = layers.Dense(1, name='next_spo2')(reg_head)

    # Head 2 — Hypoxia Risk classification
    cls_head = layers.Dense(64, activation='relu', name='cls_dense_1')(shared)
    cls_head = layers.Dropout(DROPOUT / 2)(cls_head)
    cls_head = layers.Dense(32, activation='relu', name='cls_dense_2')(cls_head)
    cls_out  = layers.Dense(1, activation='sigmoid', name='hypoxia_risk')(cls_head)

    model = models.Model(inputs=inp, outputs=[reg_out, cls_out], name='VentilatorLSTM')
    return model


# ─── Load Data ────────────────────────────────────────────────────────────────
def load_splits():
    def pk(name):
        path = os.path.join(ARTIFACT_DIR, f'{name}.pkl')
        with open(path, 'rb') as fh:
            return pickle.load(fh)

    return {k: pk(k) for k in [
        'X_train', 'X_val', 'X_test',
        'y_reg_train', 'y_reg_val', 'y_reg_test',
        'y_cls_train', 'y_cls_val', 'y_cls_test',
        'y_reg_mean', 'y_reg_std'
    ]}


# ─── Training ─────────────────────────────────────────────────────────────────
def train(d: dict):
    seq_len    = d['X_train'].shape[1]
    n_features = d['X_train'].shape[2]

    print(f"\n[BUILD] Bidirectional LSTM — seq={seq_len}, features={n_features}")
    model = build_model(seq_len, n_features)
    model.summary()

    model.compile(
        optimizer=optimizers.Adam(LR),
        loss={
            'next_spo2':    'mse',
            'hypoxia_risk': focal_loss(gamma=FOCAL_GAMMA, alpha=FOCAL_ALPHA),
        },
        loss_weights={'next_spo2': 1.0, 'hypoxia_risk': 8.0},  # Increased weight for classification
        metrics={
            'next_spo2':    ['mae'],
            'hypoxia_risk': [
                tf.keras.metrics.AUC(name='auc'),
                tf.keras.metrics.Precision(name='precision'),
                tf.keras.metrics.Recall(name='recall'),
            ]
        }
    )

    os.makedirs(MODEL_DIR, exist_ok=True)
    cb_list = [
        callbacks.EarlyStopping(monitor='val_loss', patience=15, restore_best_weights=True, verbose=1),  # Increased patience
        callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, verbose=1),  # Adjusted patience
        callbacks.ModelCheckpoint(MODEL_PATH, save_best_only=True, monitor='val_loss', verbose=1),
    ]

    cls_sample_weight = np.where(d['y_cls_train'] == 1, CLS_WEIGHT, 1.0).astype(np.float32)
    reg_sample_weight = np.ones_like(d['y_reg_train'], dtype=np.float32)

    print("\n[TRAIN] Starting training ...")
    history = model.fit(
        d['X_train'],
        {'next_spo2': d['y_reg_train'], 'hypoxia_risk': d['y_cls_train'].astype(np.float32)},
        validation_data=(
            d['X_val'],
            {'next_spo2': d['y_reg_val'], 'hypoxia_risk': d['y_cls_val'].astype(np.float32)}
        ),
        sample_weight=[reg_sample_weight, cls_sample_weight],
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=cb_list,
        verbose=1,
    )
    return model, history


# ─── Evaluation ───────────────────────────────────────────────────────────────
def evaluate(model, d: dict):
    print("\n[EVAL] Evaluating on test set ...")
    pred_reg_scaled, pred_cls = model.predict(d['X_test'], batch_size=512, verbose=0)
    pred_reg_scaled = pred_reg_scaled.flatten()
    pred_cls        = pred_cls.flatten()

    # Inverse scale regression target
    y_mean, y_std = d['y_reg_mean'], d['y_reg_std']
    pred_reg = pred_reg_scaled * y_std + y_mean
    true_reg = d['y_reg_test']  * y_std + y_mean

    mae  = mean_absolute_error(true_reg, pred_reg)
    rmse = np.sqrt(mean_squared_error(true_reg, pred_reg))
    auroc = roc_auc_score(d['y_cls_test'], pred_cls)
    ap    = average_precision_score(d['y_cls_test'], pred_cls)
    
    # Find optimal threshold for F1
    best_f1 = 0.0
    best_thresh = 0.5
    for thresh in np.arange(0.1, 0.95, 0.05):
        f1_candidate = f1_score(d['y_cls_test'], (pred_cls > thresh).astype(int))
        if f1_candidate > best_f1:
            best_f1 = f1_candidate
            best_thresh = thresh
    
    f1_default = f1_score(d['y_cls_test'], (pred_cls > 0.5).astype(int))

    results = {
        'next_spo2_mae':            round(float(mae), 4),
        'next_spo2_rmse':           round(float(rmse), 4),
        'hypoxia_auroc':            round(float(auroc), 4),
        'hypoxia_avg_prec':         round(float(ap), 4),
        'hypoxia_f1_thresh05':      round(float(f1_default), 4),
        'hypoxia_f1_optimal':       round(float(best_f1), 4),
        'hypoxia_optimal_threshold':round(float(best_thresh), 2),
    }

    print("\n  ── Test Results ──────────────────────────")
    for k, v in results.items():
        print(f"  {k:<35} {v}")
    print("  ──────────────────────────────────────────")

    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, 'model_evaluation_lstm.json')
    with open(report_path, 'w') as fh:
        json.dump(results, fh, indent=2)
    print(f"\n  Saved evaluation report → {report_path}")
    return results


def main():
    print("=" * 60)
    print("  LSTM Training — Ventilator Optimization Framework")
    print("=" * 60)
    d     = load_splits()
    model, history = train(d)
    results = evaluate(model, d)
    print("\n[DONE] Model saved →", MODEL_PATH)
    return results

if __name__ == '__main__':
    main()
