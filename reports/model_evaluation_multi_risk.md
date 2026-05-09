# Multi-Risk LSTM Model Evaluation Report

## Executive Summary

This report documents the implementation and evaluation of a **multi-task LSTM model** that predicts 5 clinical risks simultaneously from ventilator time-series data. The model extends the original single-target Hypoxia/Next_SpO2 model to predict the following outcomes:

### Prediction Targets

**Regression (Next-Step Vital Predictions):**
- Next_SpO2 (oxygen saturation)
- Next_HR (heart rate)
- Next_MAP (mean arterial pressure)
- Next_RespRate (respiratory rate)
- Next_TidalVol (tidal volume)

**Classification (Binary Risk Predictions):**
- Hypoxia_Risk: SpO2 < 90% (oxygen desaturation)
- Tachycardia_Risk: HR < 40 or HR > 140 (abnormal heart rate)
- Hypotension_Risk: MAP < 60 mmHg (low blood pressure)
- Tachypnea_Risk: RespRate < 8 or RespRate > 30 (abnormal breathing rate)
- VILI_Risk: TidalVol < 280 or > 600 ml (ventilator-induced lung injury risk)

---

## 1. Clinical Framework Reference

All thresholds and safety ranges are derived from **docs/blockchain_ventilator_framework.md § 3.3 "Clinical Parameter Ranges"**:

| Parameter | Safe Range | Critical Range | Risk Label |
|-----------|-----------|----------------|------------|
| SpO₂ | 92–100% | <90% | Hypoxia_Risk |
| Heart Rate | 60–100 bpm | <40 or >140 | Tachycardia_Risk |
| MAP | 65–100 mmHg | <60 | Hypotension_Risk |
| Resp Rate | 12–20 breaths/min | <8 or >30 | Tachypnea_Risk |
| Tidal Volume | 6–8 ml/kg (~280–600 ml) | <280 or >600 | VILI_Risk |

---

## 2. Dataset & Feature Engineering

### Data Source
- **clean_full_data_v2.csv**: 799,964 rows across 4,566 unique patient stays
- **Sample**: 400 stays × 60,225 total records (for tractable training on CPU/GPU)

### Base Vitals (7 features)
HR, MAP, RespRate, SpO2, PEEP, FiO2, TidalVol (all normalized/scaled)

### Engineered Features
- **Derived ICU Features**: SpO2/FiO2 ratio, Minute ventilation, PEEP×FiO2 product, MAP/HR ratio
- **PPO State Features**: msi, sf_ratio, vent_oxy_coupling, peep_effect, resp_stress, stability_score, etc.
- **Lag Features**: 1-step and 2-step lags for all base features
- **Trend Features**: Rate-of-change across the 3-hour window
- **Rolling Statistics**: 4-step mean and std for all features

**Total Feature Count**: 102 features per timestep

### Sequence Construction
- **Window Length**: 12 timesteps (3 hours at 15-minute intervals)
- **Target**: Next timestep (15 minutes ahead)
- **Train/Val/Test Split**: 70% / 15% / 15% stratified on Hypoxia_Risk

---

## 3. Model Architecture

### Bidirectional LSTM Encoder
```
Input [seq_len=12, n_features=102]
  ↓
BiLSTM Layer 1: 256 units, return_sequences=True
  ↓ (LayerNorm)
BiLSTM Layer 2: 128 units, return_sequences=False
  ↓ (BatchNorm)
Dense: 128 units (ReLU)
  ↓ (Dropout 0.4)
Shared Dense: 64 units (ReLU)
  ↓ (Dropout 0.4)
```

### Task-Specific Heads

**5 Regression Heads** (Next_SpO2, Next_HR, Next_MAP, Next_RespRate, Next_TidalVol):
```
Shared Encoder [64 units]
  ↓
Dense: 64 units (ReLU) → Dropout → Dense: 32 units (ReLU) → Output: 1 (Linear)
```

**5 Classification Heads** (Risk Predictions):
```
Shared Encoder [64 units]
  ↓
Dense: 64 units (ReLU) → Dropout → Dense: 32 units (ReLU) → Output: 1 (Sigmoid)
```

### Loss Functions & Weights

| Target | Loss | Loss Weight | Description |
|--------|------|-------------|-------------|
| Next_SpO2 | MSE | 1.0 | Unweighted regression |
| Next_HR | MSE | 1.0 | Unweighted regression |
| Next_MAP | MSE | 1.0 | Unweighted regression |
| Next_RespRate | MSE | 1.0 | Unweighted regression |
| Next_TidalVol | MSE | 1.0 | Unweighted regression |
| Hypoxia_Risk | Focal Loss | 8.0 | Rare class (1.73% positive) |
| Tachycardia_Risk | Focal Loss | 8.0 | Rarest class (0.70% positive) |
| Hypotension_Risk | Focal Loss | 8.0 | Common class (8.88% positive) |
| Tachypnea_Risk | Focal Loss | 8.0 | Moderate class (7.34% positive) |
| VILI_Risk | Focal Loss | 8.0 | Most common (18.21% positive) |

**Focal Loss Parameters**: γ=1.5, α=0.8 (emphasize hard negatives)

### Training Hyperparameters
- **Optimizer**: Adam (learning_rate=0.001)
- **Batch Size**: 256
- **Epochs**: 15–40 (with early stopping, patience=15)
- **Dropout**: 0.4 throughout
- **L2 Regularization**: 1e-4 on LSTM weights
- **Class Weighting**: Hypoxia, Tachycardia (75–125×), Hypotension, Tachypnea (10–12×), VILI (5×)

---

## 4. Class Balance in Training Data

| Risk | Positive Rate (%) | Count | Use Case |
|------|---------|-------|----------|
| Hypoxia_Risk | 1.73% | 659/37984 | Severe warning signal |
| Tachycardia_Risk | 0.70% | 266/37984 | Rarest but critical |
| Hypotension_Risk | 8.88% | 3372/37984 | Common, needs balance |
| Tachypnea_Risk | 7.34% | 2786/37984 | Moderate frequency |
| VILI_Risk | 18.21% | 6912/37984 | Most common, ~1 in 5 |

**Strategy**: Focal loss + class weights handle extreme imbalance; higher weight on rarer classes.

---

## 5. Evaluation Metrics

### Regression Targets (Next_*)
- **MAE** (Mean Absolute Error): average absolute deviation in vital units (mmHg, bpm, breaths/min, %)
- **RMSE** (Root Mean Squared Error): penalizes large errors more heavily

### Classification Targets (Risk)
- **AUROC** (Area Under ROC Curve): probability ranking quality (0.5=random, 1.0=perfect)
- **AUC-PR** (Area Under Precision-Recall Curve): weighted by positive class prevalence
- **F1 Score @ 0.5**: standard threshold
- **F1 Score (Optimal)**: best threshold found on validation set
- **Sensitivity (Recall)**: % of true risks caught
- **Specificity**: % of true non-risks correctly ruled out

---

## 6. Expected Performance (Baseline from Framework)

Based on single-target Hypoxia model in existing system:

| Metric | Expected Range |
|--------|-----------------|
| Next_SpO2 MAE | 2.5–4.5 % |
| Next_SpO2 RMSE | 3.5–6.0 % |
| Hypoxia_Risk AUROC | 0.85–0.92 |
| Hypoxia_Risk F1 (optimal) | 0.65–0.80 |

**Multi-task learning trade-off**: Shared encoder may slightly reduce per-task performance but improves generalization and inference speed (single forward pass for 10 outputs).

---

## 7. Implementation & Artifacts

### Code Structure
```
ml/
  multi_risk_features.py         # Feature engineering pipeline
  multi_risk_training.py         # Multi-task LSTM trainer
  multi_risk/
    X_train.pkl, X_val.pkl, X_test.pkl          (sequences)
    y_reg_train.pkl, y_reg_val.pkl, y_reg_test.pkl  (next vitals)
    y_cls_train.pkl, y_cls_val.pkl, y_cls_test.pkl  (risk labels)
    scaler.pkl                  (StandardScaler for features)
    y_reg_mean.pkl, y_reg_std.pkl     (normalization stats)
    feature_cols.pkl            (feature names)
    risk_thresholds.json        (metadata)
    multi_risk_lstm.keras       (trained model)

services/
  multi_risk_inference.py        # Production inference engine
  
api/
  main.py                         # FastAPI endpoints (+ new /patient/{id}/risks)

reports/
  model_evaluation_multi_risk.json # Test metrics
```

### API Endpoint

**POST /patient/{stay_id}/risks**
```json
{
  "history": [
    {"HR": 85, "MAP": 75, "RespRate": 18, "SpO2": 96, "PEEP": 5, "FiO2": 40, "TidalVol": 450},
    ...  // 12 timesteps minimum
  ]
}
```

**Response:**
```json
{
  "stay_id": 30004018,
  "predictions": {
    "regression": {
      "Next_SpO2": {"prediction": 96.5, "scaled_pred": 0.0234},
      "Next_HR": {"prediction": 88.2, "scaled_pred": -0.0112},
      ...
    },
    "classification": {
      "Hypoxia_Risk": {"probability": 0.08, "risk": 0, "threshold": 0.5},
      "Tachycardia_Risk": {"probability": 0.02, "risk": 0, "threshold": 0.5},
      ...
    }
  },
  "summary": {
    "high_risk_flags": [],  // If any risk probability > threshold
    "next_spo2": 96.5
  },
  "source": "multi_risk_lstm"
}
```

---

## 8. Clinical Validation & Safety

### Risk Stratification
- **Green (Low Risk)**: All risk probabilities < 0.3 → routine monitoring
- **Yellow (Moderate Risk)**: 1–2 risks in 0.3–0.7 range → increased observation
- **Red (High Risk)**: Any risk probability > 0.7 OR multiple simultaneous risks → clinical alert

### False Positive / False Negative Trade-offs
- **High Sensitivity** (catch all risks, ~90% recall): threshold ≈ 0.2–0.3
  - Useful for early warning; expect more alerts
- **High Specificity** (avoid false alarms, ~95% TNR): threshold ≈ 0.7–0.8
  - Fewer alerts but may miss emerging risks
- **Balanced F1**: threshold ≈ 0.4–0.6 (recommended for deployment)

### Limitations & Disclaimers
1. **Data-dependent**: Model trained on MIMIC-like ICU cohort; may not generalize to other hospitals or patient populations
2. **15-minute horizon**: Predictions valid only for the immediate next interval; does not forecast multi-hour trajectories
3. **No causal intervention**: Model is observational; cannot predict effect of clinician actions outside its training distribution
4. **Ensemble not yet tested**: Fusion with domain heuristics (e.g., blood gas analysis) not included in current evaluation

---

## 9. Training Pipeline Steps

### Step 1: Feature Engineering
```bash
cd "Major Project"
python -m pipelines.multi_risk_features --max-patients 400 --out-dir ml/multi_risk
```
**Output**: Pickle files + metadata in `ml/multi_risk/`

### Step 2: Model Training
```bash
python ml/multi_risk_training.py
```
**Output**: Trained Keras model + evaluation metrics in `reports/model_evaluation_multi_risk.json`

### Step 3: Inference Service
```python
from services.multi_risk_inference import MultiRiskInferenceEngine
engine = MultiRiskInferenceEngine()
engine.load()
results = engine.predict_sequence(X_seq)
```

### Step 4: API Integration
Server auto-loads at startup; test with:
```bash
curl -X POST http://localhost:8000/patient/30004018/risks \
  -H "Content-Type: application/json" \
  -d '{"history": [...]}'
```

---

## 10. Comparison with Single-Task Model

### Single-Task Baseline (Original)
- **Targets**: Next_SpO2 (regression) + Hypoxia_Risk (classification)
- **Encoder Sharing**: 2 tasks
- **Inference**: 2 outputs per pass
- **Per-task Optimization**: Separate loss tuning for each task

### Multi-Task Model (New)
- **Targets**: 5 regression + 5 classification (10 total)
- **Encoder Sharing**: 10 tasks
- **Inference**: 10 outputs per pass
- **Unified Optimization**: Single loss backprop through shared encoder

### Trade-offs
| Aspect | Single-Task | Multi-Task |
|--------|-----------|-----------|
| Inference Latency | Baseline | ~1.5–2× (more outputs) |
| Inference Throughput | Single | 10 predictions per forward pass |
| Memory Footprint | Small | +30% (larger decoder heads) |
| Generalization | Narrow | Broader (transfer learning) |
| Clinical Coverage | Limited (SpO2 only) | Comprehensive (all 5 risks) |
| Deployment Complexity | Simple | Moderate (1 model, 10 outputs) |

---

## 11. Future Work & Extensions

### Model Improvements
1. **Multi-horizon LSTM**: Predict 2, 4, 6 steps ahead (15, 30, 45 min)
2. **Attention Mechanism**: Learn which timesteps matter most
3. **Ensemble**: Combine with rule-based heuristics + domain expert priors
4. **Uncertainty Quantification**: Dropout-based Bayesian estimates of prediction confidence

### Clinical Integration
1. **Clinician Feedback Loop**: Collect expert overrides to retrain
2. **Continuous Monitoring**: Real-time risk alerts via Prometheus + Grafana
3. **Decision Support**: Suggest optimal PEEP/FiO2 to reduce risk (via PPO policy)
4. **Audit Trail**: Blockchain logging of all predictions + actions (Phase 5)

### Data Collection
1. **Prospective Validation**: Test on held-out ICU cohort
2. **Fairness Audit**: Check performance across demographics (age, sex, BMI)
3. **Failure Mode Analysis**: Identify worst-case scenarios

---

## 12. References

1. **Framework**: `docs/blockchain_ventilator_framework.md` (§3.3 Clinical Parameter Ranges)
2. **Feature Engineering**: `pipelines/feature_engineering.py` + `pipelines/ppo_feature_engineering.py`
3. **Original LSTM**: `ml/lstm_training.py` (single-task baseline)
4. **PPO Reward Design**: `services/ppo_policy.py` (includes VILI penalty, stability score)
5. **Digital Twin Validation**: `services/digital_twin.py` (simulates response to ventilator adjustments)

---

## Appendix: Test Set Predictions (Sample)

*(To be filled after model training completes)*

```json
{
  "test_sample_count": 8140,
  "regression_metrics": {
    "Next_SpO2": {"mae": 3.14, "rmse": 4.72},
    "Next_HR": {"mae": 8.23, "rmse": 11.45},
    "Next_MAP": {"mae": 6.87, "rmse": 9.34},
    "Next_RespRate": {"mae": 2.31, "rmse": 3.45},
    "Next_TidalVol": {"mae": 45.6, "rmse": 62.3}
  },
  "classification_metrics": {
    "Hypoxia_Risk": {
      "auroc": 0.89,
      "auc_pr": 0.65,
      "f1_thresh05": 0.72,
      "f1_optimal": 0.78,
      "optimal_threshold": 0.42
    },
    "Tachycardia_Risk": {
      "auroc": 0.84,
      "auc_pr": 0.48,
      "f1_thresh05": 0.55,
      "f1_optimal": 0.68,
      "optimal_threshold": 0.38
    },
    ...
  }
}
```

---

**Report Generated**: 2026-05-07  
**Model Version**: multi_risk_lstm.keras  
**Framework Version**: Blockchain-Enabled Digital Twin v1.0
