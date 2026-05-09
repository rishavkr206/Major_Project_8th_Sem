Slide-by-Slide Presenter Notes — 8 Slides (~6–8 minutes)

Slide 1 — Title (20s)
- Title: "Blockchain-Enabled Digital Twin for Ventilator Safety"
- Presenter note: Quick greeting + one-line project goal.

Slide 2 — Problem (40s)
- Bullets:
  - ICU ventilator patients change quickly
  - Delayed/inaccurate adjustments cause harm
  - Need: early warnings, safe checks, auditability
- Presenter note: Give a short real-world example (patient desaturates in 15 minutes).

Slide 3 — High-level Architecture (50s)
- Bullets:
  - Data ingestion & simulator
  - Feature pipeline → Multi-risk LSTM
  - Digital Twin sandbox
  - API, Dashboard, Audit ledger
- Presenter note: Walk left-to-right, emphasize safety loop (Twin between model and clinician).

Slide 4 — Data & Simulator (40s)
- Bullets:
  - Reproducible synthetic datasets
  - Packet-loss and artifact modeling
  - Feature engineering artifacts saved under `ml/`
- Presenter note: Mention `pipelines/run_phase1.py` and deterministic seeds for reproducibility.

Slide 5 — Digital Twin (50s)
- Bullets:
  - Deterministic replay (`noise_scale=0`)
  - Safety clamping (PEEP, FiO2, TidalVol bounds)
  - Uncertainty bands + risk_flag
- Presenter note: Show a short twin replay screenshot or callout and say metrics (MAE ~1.7 SpO2 pp).

Slide 6 — Multi-risk LSTM (1m)
- Bullets:
  - Single model predicts 5 vitals + 5 risks
  - Dual-head BiLSTM architecture
  - Handle class imbalance with focal loss + class weights
- Presenter note: Briefly explain why multi-task improves shared representation and deployment simplicity.

Slide 7 — Demo (live) (1m)
- Bullets:
  - 1) `POST /patient/{id}/risks` — show JSON output
  - 2) `POST /twin/replay` — propose PEEP increase and show clamping/risk
  - 3) Dashboard panel and `/metrics` update
- Presenter note: Keep each API call under 20s; narrate what the clinician sees and the audit entry.

Slide 8 — Results, Impact & Next Steps (40s)
- Bullets:
  - Phase 1 & 2 complete; tests/pass and evaluation reports available
  - Impact: early warnings, safer recommendations, auditability
  - Next: clinical validation, threshold tuning, RL integration
- Presenter note: Close with thank you and an invitation for questions.

Q&A (remaining time)
- Prepare: Why LSTM? Safety/clamping details? Audit design? Clinical validation plan?
- Presenter note: Keep answers focused and reference `reports/` and `docs/` for metrics.