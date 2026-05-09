# Failure Playbook & Fallback Protocols

This document outlines the system failure conditions, safety boundaries, and manual fallback protocols to maintain patient safety in case the AI/Blockchain layer goes offline.

## 1. Safety Hard-Bounds (Continuous Enforcement)

The backend `ppo_policy.py` engine enforces these hard clamps before simulation:
* **PEEP:** Minimum 3.0 cmH2O | Maximum 20.0 cmH2O
* **FiO2:** Minimum 21.0% | Maximum 100.0%
* **Tidal Volume:** Minimum 200.0 mL | Maximum 800.0 mL

No recommendation outside this range is valid under any circumstance.

## 2. Failure Scenarios and Recovery Actions

### Scenario A: Sensor Disconnection / Telemetry Loss
**Trigger**: Stream of vitals from patient monitor stops for > 15 minutes.
**System Action**:
- AI Co-Pilot suspends recommendations.
- Blockchain Audit logs `SENSOR_LOST` event.
**Clinician Action**:
- Maintain current ventilator settings. Replace loose probes.
- Check edge gateway cables.

### Scenario B: LSTM Model Drift (High Prediction Error)
**Trigger**: Next SpO2 MSE drifts by > 20% over a 24-hour validation window.
**System Action**:
- Dashboard displays: `WARNING: Modest Prediction Confidence`.
- Prediction uncertainty bounds expand automatically in the Digital Twin module.
**Clinician Action**:
- Trigger a periodic retraining cycle via MLOps pipeline.
- Evaluate recommendations with higher manual scrutiny.

### Scenario C: Blockchain Network / Local Ledger Corruption
**Trigger**: `verify_chain()` detects a hash mismatch or tampered ledger.
**System Action**:
- Dashboard status turns RED.
- `alert_level` set to `CRITICAL`.
**Clinician Action**:
- Contact IT immediately. Action logging reverts to standard hospital EMR.
- Verify node synchrony for any external peers if federated.

### Scenario D: Digital Twin Uncalibrated
**Trigger**: SpO2 variability is too chaotic to fit compliance factor stably.
**System Action**:
- Twin simulation assigns flat ±5% uncertainty.
- PPO policy lowers recommendation confidence score below 50%.
**Clinician Action**:
- Override AI. Treat patient based on ABG (Arterial Blood Gas) manually. 
