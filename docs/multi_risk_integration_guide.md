# Multi-Risk LSTM Integration Guide

## Quick Start

### 1. Generate Training Features
```bash
cd "Major Project"
python -m pipelines.multi_risk_features --max-patients 400 --out-dir ml/multi_risk
```

This generates:
- `ml/multi_risk/X_train.pkl` — Training sequences [37984, 12, 102]
- `ml/multi_risk/y_reg_train.pkl` — Next-vitals targets [37984, 5]
- `ml/multi_risk/y_cls_train.pkl` — Risk labels [37984, 5]
- Plus validation and test splits
- `ml/multi_risk/risk_thresholds.json` — Metadata

### 2. Train Multi-Task LSTM
```bash
# Default: 40 epochs
python ml/multi_risk_training.py

# Custom epochs:
export LSTM_EPOCHS=20
python ml/multi_risk_training.py
```

Outputs:
- `ml/multi_risk/multi_risk_lstm.keras` — Trained model
- `reports/model_evaluation_multi_risk.json` — Test metrics

### 3. Run API Server
```bash
pip install fastapi uvicorn tensorflow pandas scikit-learn
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

### POST /patient/{stay_id}/risks
Predict 5 clinical risks for a patient given 3-hour history.

**Request:**
```bash
curl -X POST http://localhost:8000/patient/30004018/risks \
  -H "Content-Type: application/json" \
  -d '{
    "history": [
      {"HR": 85, "MAP": 75, "RespRate": 18, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 450},
      {"HR": 86, "MAP": 76, "RespRate": 19, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 455},
      {"HR": 87, "MAP": 77, "RespRate": 18, "SpO2": 97, "PEEP": 5, "FiO2": 40, "TidalVol": 450},
      {"HR": 88, "MAP": 78, "RespRate": 20, "SpO2": 97, "PEEP": 5, "FiO2": 40, "TidalVol": 460},
      {"HR": 89, "MAP": 79, "RespRate": 19, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 458},
      {"HR": 90, "MAP": 80, "RespRate": 18, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 456},
      {"HR": 91, "MAP": 81, "RespRate": 20, "SpO2": 97, "PEEP": 5, "FiO2": 40, "TidalVol": 462},
      {"HR": 92, "MAP": 82, "RespRate": 19, "SpO2": 97, "PEEP": 5, "FiO2": 40, "TidalVol": 460},
      {"HR": 88, "MAP": 78, "RespRate": 18, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 455},
      {"HR": 87, "MAP": 77, "RespRate": 19, "SpO2": 97, "PEEP": 5, "FiO2": 40, "TidalVol": 459},
      {"HR": 86, "MAP": 76, "RespRate": 20, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 454},
      {"HR": 85, "MAP": 75, "RespRate": 18, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 452}
    ]
  }'
```

**Response:**
```json
{
  "stay_id": 30004018,
  "predictions": {
    "regression": {
      "Next_SpO2": {
        "prediction": 96.5,
        "scaled_pred": 0.0234
      },
      "Next_HR": {
        "prediction": 88.2,
        "scaled_pred": -0.0112
      },
      "Next_MAP": {
        "prediction": 76.8,
        "scaled_pred": 0.0087
      },
      "Next_RespRate": {
        "prediction": 18.9,
        "scaled_pred": -0.0045
      },
      "Next_TidalVol": {
        "prediction": 455.3,
        "scaled_pred": 0.0156
      }
    },
    "classification": {
      "Hypoxia_Risk": {
        "probability": 0.0823,
        "risk": 0,
        "threshold": 0.5
      },
      "Tachycardia_Risk": {
        "probability": 0.0234,
        "risk": 0,
        "threshold": 0.5
      },
      "Hypotension_Risk": {
        "probability": 0.0456,
        "risk": 0,
        "threshold": 0.5
      },
      "Tachypnea_Risk": {
        "probability": 0.0612,
        "risk": 0,
        "threshold": 0.5
      },
      "VILI_Risk": {
        "probability": 0.1234,
        "risk": 0,
        "threshold": 0.5
      }
    }
  },
  "summary": {
    "high_risk_flags": [],
    "next_spo2": 96.5
  },
  "source": "multi_risk_lstm"
}
```

---

## Python Usage

### Direct Inference
```python
from services.multi_risk_inference import MultiRiskInferenceEngine
import numpy as np

# Load engine
engine = MultiRiskInferenceEngine()
if not engine.load():
    print("Model not trained yet")
    exit(1)

# Build sequence from history
history = [
    {"HR": 85, "MAP": 75, "RespRate": 18, "SpO2": 96, ...},
    # ... 12 timesteps
]

# Extract features (simplified; use feature_engineering.py for production)
X_seq = np.array([...])  # Shape: [12, 102]

# Predict
results = engine.predict_sequence(X_seq)

# Access predictions
print(f"Next SpO2: {results['Next_SpO2']['prediction']}")
print(f"Hypoxia Risk: {results['Hypoxia_Risk']['probability']:.3f}")
```

### Batch Predictions
```python
from services.multi_risk_inference import MultiRiskInferenceEngine
import numpy as np

engine = MultiRiskInferenceEngine()
engine.load()

# Process multiple sequences
predictions = []
for X_seq in X_test_batch:
    pred = engine.predict_sequence(X_seq)
    predictions.append(pred)

# Aggregate
hypoxia_probs = [p['Hypoxia_Risk']['probability'] for p in predictions]
print(f"Mean hypoxia risk: {np.mean(hypoxia_probs):.3f}")
```

---

## Risk Stratification

### Color-Coded Alerts

**Green (Safe)** — All risks < 0.3
```
✓ Routine monitoring
```

**Yellow (Caution)** — 1–2 risks in 0.3–0.7
```
⚠ Increased observation every 15–30 min
  Consider: Check blood gas, inspect alarm settings
```

**Orange (Watch)** — 2+ risks in 0.5–0.8 OR 1 risk > 0.7
```
⚠⚠ Active intervention
  Recommend: Reassess PEEP, FiO2; call respiratory therapy
```

**Red (Critical)** — 3+ risks > 0.7 OR any risk > 0.9
```
🚨 Immediate action required
  Contact: Physician + ICU team
```

---

## Threshold Customization

The default threshold is 0.5 for all risks. To adjust:

**Example: More sensitive to Hypoxia**
```python
engine.predict_sequence(X_seq)  # Get probabilities
probs = results['Hypoxia_Risk']['probability']
risk_flag = int(probs > 0.3)  # Lower threshold = more sensitive
```

**Per-risk thresholds from training report:**
```json
{
  "Hypoxia_Risk": 0.42,
  "Tachycardia_Risk": 0.38,
  "Hypotension_Risk": 0.45,
  "Tachypnea_Risk": 0.40,
  "VILI_Risk": 0.48
}
```

---

## Troubleshooting

### Model Not Loading
```
[ERR] Model not found: .../multi_risk_lstm.keras
```
**Fix**: Run training script: `python ml/multi_risk_training.py`

### Feature Mismatch
```
ValueError: No matching features found in history
```
**Fix**: Ensure history has all 7 required columns:
- HR, MAP, RespRate, SpO2, PEEP, FiO2, TidalVol

### Insufficient History
```
HTTPException: history must be a list of at least 12 vital sign measurements
```
**Fix**: Provide at least 12 timesteps (3 hours at 15-min intervals)

### Shape Mismatch
```
ValueError: Expected 2D sequence, got 3D
```
**Fix**: Pass shape [seq_len=12, n_features=102], not [batch, seq, features]

---

## Files Generated

### Training Artifacts
```
ml/multi_risk/
  ├─ X_train.pkl, X_val.pkl, X_test.pkl
  ├─ y_reg_train.pkl, y_reg_val.pkl, y_reg_test.pkl
  ├─ y_cls_train.pkl, y_cls_val.pkl, y_cls_test.pkl
  ├─ scaler.pkl
  ├─ y_reg_mean.pkl, y_reg_std.pkl
  ├─ feature_cols.pkl
  ├─ risk_thresholds.json
  └─ multi_risk_lstm.keras
```

### Evaluation Reports
```
reports/
  ├─ model_evaluation_multi_risk.json   (test metrics)
  └─ model_evaluation_multi_risk.md     (this guide)
```

---

## Advanced: Custom Thresholds

### Post-Training Threshold Optimization
```python
from sklearn.metrics import f1_score
import numpy as np

# Load test predictions
pred_probs = model.predict(X_test)['Hypoxia_Risk'].flatten()
y_test = y_cls_test[:, 0]

# Find optimal threshold
best_f1, best_thresh = 0, 0.5
for thresh in np.arange(0.1, 0.9, 0.05):
    f1 = f1_score(y_test, (pred_probs > thresh).astype(int))
    if f1 > best_f1:
        best_f1, best_thresh = f1, thresh

print(f"Optimal threshold: {best_thresh}, F1: {best_f1:.3f}")
```

### Deploy Custom Thresholds
Edit `services/multi_risk_inference.py`:
```python
RISK_THRESHOLDS = {
    "Hypoxia_Risk": 0.42,  # Optimized
    "Tachycardia_Risk": 0.38,
    "Hypotension_Risk": 0.45,
    "Tachypnea_Risk": 0.40,
    "VILI_Risk": 0.48,
}
```

---

## Next Steps

1. **Monitor Performance**: Track AUROC, F1, sensitivity on new ICU data
2. **Gather Feedback**: Collect clinician overrides to identify failure modes
3. **Retrain**: Monthly/quarterly updates with fresh data
4. **Ensemble**: Combine with rule-based heuristics for robustness
5. **Validate**: Prospective A/B test against current standard of care

---

## References

- `docs/blockchain_ventilator_framework.md` — Clinical thresholds
- `pipelines/multi_risk_features.py` — Feature engineering
- `ml/multi_risk_training.py` — Model training
- `services/multi_risk_inference.py` — Inference engine
- `api/main.py` — API integration
- `reports/model_evaluation_multi_risk.md` — Full evaluation report

---

**Last Updated**: 2026-05-07
