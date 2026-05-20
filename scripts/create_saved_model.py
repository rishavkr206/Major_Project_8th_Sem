import os
import pickle
import numpy as np
from tensorflow.keras import layers, models

ART = os.path.abspath(os.environ.get('LSTM_ARTIFACTS_DIR', 'ml/simulated_phase1'))
X_train_p = os.path.join(ART, 'X_train.pkl')
feat_p = os.path.join(ART, 'feature_cols.pkl')
md = os.path.join(ART, 'models')
os.makedirs(md, exist_ok=True)

with open(feat_p, 'rb') as fh:
    feat = pickle.load(fh)

with open(X_train_p, 'rb') as fh:
    X_train = pickle.load(fh)

seq_len = X_train.shape[1]
n_features = X_train.shape[2]

inp = layers.Input(shape=(seq_len, n_features), name='sequence_input')
x = layers.LSTM(16, return_sequences=False)(inp)
reg_out = layers.Dense(1, name='next_spo2')(x)
cls_out = layers.Dense(1, activation='sigmoid', name='hypoxia_risk')(x)
model = models.Model(inputs=inp, outputs=[reg_out, cls_out])
model.save(os.path.join(md, 'lstm_model.keras'))
print('Saved dummy model to', os.path.join(md, 'lstm_model.keras'))
