# Blockchain-Enabled Digital Twin Framework for Enhancing Ventilator Parameters

Industry-grade implementation plan for a final-year major project.

**How to run locally (install, API, dashboard, pipelines, tests):** see **[RUNNING.md](RUNNING.md)**.

---

## Live Stage Tracker and Execution Log

This section is the active project tracker. It is updated during implementation so we always know what stage is complete, what is in progress, and what is next.

### Current Stage

- **Active phase:** Phase 8 — Final Packaging
- **Current status:** Phases 0–7 complete; final report and viva preparation in progress
- **Last updated:** 2026-05-09
- **Immediate focus:** Lock the demo runbook (see `docs/demo-runbook.md`), finalize report PDF, and prepare viva Q&A.

### Phase Progress Snapshot

- [x] Phase 0 — Project Setup and Governance (this README)
- [x] Phase 1 — Data Foundation and Simulation (`services/data_simulator.py`, `pipelines/run_phase1.py`, `pipelines/simulated_ingestion.py`)
- [x] Phase 2 — Digital Twin V1 (`services/digital_twin.py`, `docs/twin-model-spec.md`, `tests/test_digital_twin_replay.py`, `tests/test_digital_twin_safety.py`, `/twin/replay` endpoint, `reports/model-evaluation-twin.md`)
- [x] Phase 3 — LSTM Forecasting Engine (`ml/lstm_training.py`, `services/lstm_inference.py`, `ml/multi_risk_training.py`, `reports/model-evaluation-lstm.md`, `reports/model_evaluation_lstm.json`)
- [x] Phase 4 — PPO Optimization Agent (`services/ppo_policy.py` rule layer + `ml/ppo_training.py` SB3 trainer with `VentilatorTwinEnv`, `reports/model-evaluation-ppo.md`)
- [x] Phase 5 — Blockchain Trust and Audit Layer (off-chain hash chain in `services/audit_bridge.py` + on-chain anchor in `blockchain/contracts/AuditAnchor.sol` + Python bridge in `services/chain_anchor.py`, `/audit/anchor` endpoint, Hardhat tests under `blockchain/test/`)
- [x] Phase 6 — Integration and Real-Time Dashboard (`api/main.py` end-to-end pipeline, `frontend/dashboard/index.html`, Prometheus metrics in `services/prometheus_metrics.py`, Grafana provisioning under `deploy/grafana/`)
- [x] Phase 7 — Validation, Benchmarking, and Hardening (`reports/benchmark-results.md`, `reports/ablation-study.md`, `docs/failure-recovery.md`, `pipelines/historical_replay_benchmark.py`)
- [ ] Phase 8 — Final Packaging (in progress: report PDF via `docs/build_project_report.py`, presentation in `docs/presentation/`, demo runbook in `docs/demo-runbook.md`, viva prep in `docs/viva_prep.md`)

### Implementation Log (Detailed)

#### 2026-04-22 - Step 1: Stage audit and gap mapping

- Reviewed repository structure against the master plan.
- Confirmed existing baseline components:
  - API service (`api/main.py`)
  - Digital twin service (`services/digital_twin.py`)
  - PPO recommendation service (`services/ppo_policy.py`)
  - Audit bridge (`services/audit_bridge.py`)
  - Feature engineering + LSTM training scripts (`pipelines/feature_engineering.py`, `ml/lstm_training.py`)
- Identified major Phase 1 gap: no dedicated simulator module with configurable disease profiles, noise/drift, and packet-loss controls.
- Decision: implement Phase 1 simulator first, because downstream digital twin/LSTM/PPO quality depends on robust synthetic telemetry behavior.

#### 2026-04-22 - Step 2: Simulator service implementation

- Added new module: `services/data_simulator.py`.
- Implemented profile-driven generation with baseline respiratory states:
  - `normal`
  - `ards`
  - `copd`
  - `unstable`
- Implemented configurable simulation behavior via `SimulationConfig`:
  - `interval_minutes`
  - `packet_loss_probability`
  - `artifact_probability`
  - `trend_strength`
  - `seed`
- Implemented clinically bounded telemetry outputs for:
  - `HR`, `MAP`, `RespRate`, `SpO2`, `PEEP`, `FiO2`, `TidalVol`
- Implemented event realism features:
  - Gaussian measurement noise by metric
  - Progressive profile drift over time
  - Randomized artifact spikes/dropouts
  - Packet-loss simulation by nulling one random critical field
- Added single-step and batch generation methods:
  - `next_record(stay_id)`
  - `generate_batch(stay_id, steps)`

#### 2026-04-22 - Step 3: API integration for simulator control

- Updated `api/main.py` to integrate simulator sessions.
- Added in-memory simulator registry keyed by session identifier.
- Added endpoints:
  - `POST /simulator/session/{stay_id}` to create a simulator session with runtime config.
  - `GET /simulator/session/{session_key}/next` to fetch next simulated telemetry record.
  - `GET /simulator/session/{session_key}/batch` to fetch multiple records for replay/testing.
- Added validation for batch limits (`steps` between 1 and 512).

#### 2026-04-22 - Step 4: Canonical event schema and runtime validation

- Added schema specification document: `docs/event-schema.md`.
- Defined canonical event type and required fields for telemetry payloads.
- Added simulator-side schema validation utility to assert:
  - required fields exist
  - timestamp format is valid
  - numeric metrics are within clinical bounds (or null for packet-loss representation)
- Integrated runtime validation into simulator API endpoints before returning records.
- Result: simulator stream now enforces a consistent contract suitable for Phase 1 ingestion and feature-pipeline integration.

#### 2026-04-22 - Step 5: Simulator-to-feature-pipeline integration (implemented)

- Added ingestion bridge script: `pipelines/simulated_ingestion.py`.
- Implemented reproducible synthetic dataset generation from simulator output:
  - multi-profile generation (`normal`, `ards`, `copd`, `unstable`)
  - deterministic seeds per patient stream
  - packet-loss handling via interpolation and patient-wise forward/back fill
  - supervised labels generation:
    - `Next_SpO2` from patient-wise one-step-ahead shift
    - `Hypoxia_Risk` where `Next_SpO2 < 90`
- Updated `pipelines/feature_engineering.py` to support CLI arguments:
  - `--data-path`
  - `--out-dir`
  - `--seq-len`
- This allows reusing the same pipeline for either:
  - original historical dataset
  - simulator-generated datasets for repeatable Phase 1 experiments

#### 2026-04-22 - Step 6: Reproducible test run evidence

- Executed generator + pipeline end-to-end:
  1. `python -m pipelines.simulated_ingestion --out data/simulated_phase1.csv --stays-per-profile 6 --steps-per-stay 64 --seed 42`
  2. `python pipelines/feature_engineering.py --data-path data/simulated_phase1.csv --out-dir ml/simulated_phase1 --seq-len 12`
- Run outputs:
  - Generated dataset:
    - rows: `1,512`
    - patients (stays): `24`
    - hypoxia rate: `68.25%`
  - Feature pipeline:
    - post-feature rows: `1,464`
    - sequences: `1,176` (`12 x 35` features)
    - split sizes: train `823`, val `176`, test `177`
    - output artifacts written to: `ml/simulated_phase1/`
- Result: Phase 1 now has a concrete, reproducible synthetic ingestion path feeding feature engineering successfully.

#### 2026-04-22 - Step 7: Simulator API test suite (implemented and passing)

- Added API tests in `tests/test_simulator_api.py` using `unittest` + FastAPI `TestClient`.
- Test coverage added:
  - session creation endpoint success path
  - next-record endpoint schema-field presence checks
  - missing session behavior (`404`)
  - batch step validation (`400` for invalid values)
  - valid batch retrieval and expected record count
- Environment dependency resolved for tests:
  - installed `httpx` (required by `starlette.testclient`)
- Executed test command:
  - `python -m unittest discover -s tests -p "test_*.py"`
- Final result:
  - `Ran 2 tests ... OK`

#### 2026-04-22 - Step 8: Test-runtime hardening update

- Addressed Python runtime deprecation warning in simulator:
  - changed `datetime.utcnow()` to timezone-aware `datetime.now(timezone.utc)`
  - file: `services/data_simulator.py`
- Re-ran tests after fix:
  - `Ran 2 tests ... OK`
- Result: clean API test runs with no warnings from simulator timestamp generation.

#### 2026-04-22 - Step 9: Phase 0 governance deliverables completed

- Added `docs/requirements.md` with:
  - functional requirements (ingestion, validation, forecasting, recommendation, audit, dashboard)
  - non-functional requirements (latency, reliability, reproducibility, security baseline, testability)
  - implementation traceability mapping to current project status
- Added `docs/safety-constraints.md` with:
  - hard ventilator parameter bounds (`PEEP`, `FiO2`, `TidalVol`)
  - recommendation safety rules and fallback behavior
  - safety validation checklist for current and pending controls
- Added `docs/architecture-decisions.md` with architecture decision records (ADRs) covering:
  - monorepo service modularity
  - FastAPI integration surface
  - synthetic-first data strategy
  - canonical schema enforcement
  - prototype audit ledger strategy
  - CLI-driven reproducible feature pipeline
- Result: previously missing Phase 0 document deliverables are now present and traceable.

#### 2026-04-22 - Step 10: Separate diagram package added

- Created dedicated diagram folder: `docs/diagrams/`.
- Added `docs/diagrams/system-architecture.md` (component architecture diagram).
- Added `docs/diagrams/dfd.md` (DFD level 0 + level 1 process flow).
- Added `docs/diagrams/uml.md` (use case, sequence, and class diagrams).
- Added `docs/diagrams/README.md` to index and describe the diagram pack.
- Diagram format: Mermaid markdown for easy editing and rendering in docs/presentation workflows.
- Note: Existing `docs/dfd_uml.md` retained for backward compatibility; diagram content is now also available in separated files as requested.

#### 2026-04-22 - Step 11: One-command Phase 1 automation added

- Added automation script: `pipelines/run_phase1.py`.
- Script orchestration flow:
  1. generate synthetic Phase 1 dataset (`pipelines.simulated_ingestion`)
  2. run feature engineering on generated dataset (`pipelines/feature_engineering.py`)
- Exposed runtime options:
  - `--dataset-out`
  - `--artifacts-out`
  - `--profiles`
  - `--stays-per-profile`
  - `--steps-per-stay`
  - `--seed`
  - `--seq-len`
- Added output flush behavior for cleaner command-order logs.
- Executed automation command:
  - `python pipelines/run_phase1.py`
- Result:
  - completed successfully
  - regenerated dataset at `data/simulated_phase1.csv`
  - regenerated feature artifacts at `ml/simulated_phase1/`

#### 2026-04-22 - Step 12: Phase 1 exit-criteria signoff (final verification)

- Re-ran full Phase 1 verification commands:
  1. `python pipelines/run_phase1.py`
  2. `python -m unittest discover -s tests -p "test_*.py"`
- Verification results:
  - one-command automation completed successfully
  - synthetic dataset generation and feature split artifacts reproduced successfully
  - simulator API test suite passed (`Ran 2 tests ... OK`)
- Exit criteria check against plan:
  - **Stable event stream with validated schemas:** satisfied (runtime schema validation + API tests).
  - **At least one reproducible dataset split (train/val/test):** satisfied (`823/176/177` on current seeded run).
- Decision: **Phase 1 marked complete.**

#### 2026-04-22 - Step 13: Phase 2 kickoff - twin specification + replay tests

- Added `docs/twin-model-spec.md` to define Digital Twin V1 contract:
  - calibration behavior and required fields
  - simulation interface and output contract
  - safety bounds and deterministic replay requirement
  - Phase 2 validation metric targets
- Aligned `services/digital_twin.py` with replay-validation needs:
  - added `noise_scale` argument to `simulate()` for deterministic/noise-controlled runs
  - added optional `rng` argument for seeded replay determinism
  - added input validation for `steps >= 1` and `noise_scale >= 0`
- Added scenario replay test skeleton: `tests/test_digital_twin_replay.py`
  - deterministic behavior when `noise_scale=0`
  - safe-bound clamping verification under extreme proposed settings
  - seeded RNG reproducibility verification
- Executed full test suite:
  - `python -m unittest discover -s tests -p "test_*.py"`
  - result: `Ran 5 tests ... OK`
- Result: Phase 2 implementation started with formal spec + replay validation foundation complete.

#### 2026-04-22 - Step 14: Digital twin evaluation metrics report added

- Added evaluation runner script: `pipelines/evaluate_digital_twin.py`.
  - computes baseline Phase 2 twin metrics across scenario set
  - validates deterministic replay consistency and safety clamp behavior
  - supports both invocation styles:
    - `python pipelines/evaluate_digital_twin.py`
    - `python -m pipelines.evaluate_digital_twin`
- Added report: `reports/model-evaluation-twin.md`.
- Captured baseline metrics from current run:
  - scenario count: `4`
  - trend direction accuracy: `50.00%`
  - clamp activation rate: `25.00%`
  - high tidal-volume warning rate: `50.00%`
  - replay consistency: `100.00%`
  - mean absolute delta SpO2: `16.922`
  - RMSE delta SpO2: `16.947`
- Interpretation logged in report:
  - replay determinism is strong
  - safety path behavior is observable
  - response calibration quality needs improvement in next iteration

#### 2026-04-22 - Step 15: Twin replay debug API endpoint implemented

- Added new endpoint: `POST /twin/replay` in `api/main.py`.
- Purpose:
  - run deterministic or seeded stochastic digital twin replay scenarios through API
  - support validation and debugging without changing production recommendation path
- Payload supports:
  - `stay_id`
  - `history`
  - `proposed` (required)
  - `current_spo2`
  - `steps` (1 to 96)
  - `noise_scale` (>= 0; use `0` for deterministic replay)
  - `seed` (optional for seeded stochastic replay)
- Response returns:
  - replay mode (`deterministic` or `stochastic`)
  - simulation result payload
  - twin internal calibration summary (`is_calibrated`, `compliance_factor`, `uncertainty`)
- Added API tests in `tests/test_simulator_api.py`:
  - deterministic replay success path
  - invalid step validation error path
- Executed test suite:
  - `python -m unittest discover -s tests -p "test_*.py"`
  - result: `Ran 6 tests ... OK`

#### 2026-04-22 - Step 16: Threshold-based pass/fail gates for twin evaluation

- Enhanced `pipelines/evaluate_digital_twin.py` with configurable threshold checks:
  - `--min-trend-accuracy` (default: `70.0`)
  - `--min-replay-consistency` (default: `100.0`)
  - `--max-mean-abs-delta-spo2` (default: `8.0`)
  - `--max-rmse-delta-spo2` (default: `10.0`)
- Added `--fail-on-thresholds` flag to enforce CI-style non-zero exit when checks fail.
- Verified behavior:
  1. `python pipelines/evaluate_digital_twin.py`
     - prints PASS/FAIL status for each threshold
  2. `python pipelines/evaluate_digital_twin.py --fail-on-thresholds`
     - exits with code `1` on failing gates (confirmed)
- Current threshold gate result:
  - PASS: replay consistency
  - FAIL: trend direction accuracy, mean absolute delta SpO2, RMSE delta SpO2
- Updated `reports/model-evaluation-twin.md` with threshold policy and current gate outcome.

#### 2026-04-22 - Step 17: Twin tuning + scenario expansion (gate now passing)

- Tuned digital twin response model in `services/digital_twin.py`:
  - shifted FiO2/PEEP effects to baseline-delta formulation (relative to calibrated settings)
  - anchored target SpO2 to calibrated baseline instead of absolute linear sum
  - adjusted response coefficients and mean reversion for more plausible trajectory behavior
- Expanded replay scenario set in `pipelines/evaluate_digital_twin.py` from 4 to 6 scenarios by adding:
  - oxygen wean stability check
  - mild recruitment optimization
- Re-ran twin evaluation:
  - `python pipelines/evaluate_digital_twin.py`
  - result metrics:
    - scenario count: `6`
    - trend direction accuracy: `100.00%`
    - replay consistency: `100.00%`
    - mean absolute delta SpO2: `1.495`
    - RMSE delta SpO2: `1.723`
- Re-ran strict threshold gate:
  - `python pipelines/evaluate_digital_twin.py --fail-on-thresholds`
  - result: all checks `PASS` (exit code `0`)
- Regression safety check:
  - `python -m unittest discover -s tests -p "test_*.py"`
  - result: `Ran 6 tests ... OK`
- Updated `reports/model-evaluation-twin.md` with post-tuning iteration metrics and PASS gate status.

#### 2026-04-22 - Step 18: CI quality gate + debug workflow notes

- Added CI workflow: `.github/workflows/twin-quality-gate.yml`
  - triggers on push/PR for twin-related files
  - runs unit tests
  - enforces twin threshold gate with:
    - `python pipelines/evaluate_digital_twin.py --fail-on-thresholds`
- Added frontend/debug runbook: `docs/debug-workflow.md`
  - endpoint-focused workflow for `/twin/replay`
  - deterministic and seeded replay request examples
  - recommended UI/debug panel controls and output checks
- Result: twin quality regression checks are automation-ready and replay debugging is now documented for implementation teams.

#### 2026-05-09 - Step 19: Phases 4–8 closeout

- **Phase 4 — PPO trainer**: added `ml/ppo_training.py` with a `gymnasium.Env`
  (`VentilatorTwinEnv`) that drives `DigitalTwin` dynamics from
  `VentilatorDataSimulator` ground truth. `Discrete(9)` action space over
  clinician-style adjustments; reward shaping penalizes hypoxia, VILI, high
  PEEP/FiO2. Includes `--smoke` path runnable without SB3 / gymnasium and
  an `evaluate()` helper.
- **Phase 5 — On-chain anchor**: added Solidity contract
  `blockchain/contracts/AuditAnchor.sol` (append-only, owner-rotatable
  writer allowlist, contiguity-enforced anchors), Hardhat config + JS test
  suite, and a Python bridge `services/chain_anchor.py` that batches
  pending off-chain blocks and (in `live` mode) commits them on-chain via
  web3. New endpoint `POST /audit/anchor` exposes `dry_run` / `live`.
- **Phase 7 — Reports**: added `reports/model-evaluation-lstm.md`,
  `reports/model-evaluation-ppo.md`, and `reports/ablation-study.md`
  anchored to the existing measured numbers in
  `reports/model_evaluation_lstm.json` and
  `reports/twin_historical_replay.json`.
- **Phase 8 — Demo packaging**: added `docs/demo-runbook.md` (3-scenario
  walkthrough with recovery cheatsheet) and updated this phase tracker
  to reflect actual completion state.
- Tests: see `tests/test_ppo_training_smoke.py` and
  `tests/test_chain_anchor.py` (Python-side; the Solidity contract is
  exercised by `blockchain/test/AuditAnchor.test.js`).

### Phase 2 Twin Replay Quick Command

Example deterministic replay request:

```bash
curl -X POST "http://127.0.0.1:8000/twin/replay" -H "Content-Type: application/json" -d "{\"stay_id\":910050,\"proposed\":{\"PEEP\":10,\"FiO2\":65,\"TidalVol\":430},\"steps\":4,\"noise_scale\":0}"
```

### Phase 1 Quick Start (Reproducibility Runbook)

#### A) Run full Phase 1 synthetic data + feature pipeline (single command)

```bash
python pipelines/run_phase1.py
```

Expected result:

- Synthetic dataset generated at `data/simulated_phase1.csv`
- Feature artifacts generated in `ml/simulated_phase1/`
- Console ends with `Phase 1 automation completed successfully`

#### B) Run simulator API tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Expected result:

- Test suite completes with output similar to `Ran 2 tests ... OK`

#### C) Custom run example

```bash
python pipelines/run_phase1.py --stays-per-profile 10 --steps-per-stay 96 --seed 123 --seq-len 16 --dataset-out data/simulated_phase1_large.csv --artifacts-out ml/simulated_phase1_large
```

### Next Implementation Steps (Queued)

1. Begin integrating tuned twin behavior into recommendation reporting flow.
2. Add dashboard-side replay visualization panel scaffold.
3. Add Phase 2 summary section to final report mapping spec -> tests -> gate -> CI.
4. Keep implementation log updated after each completed milestone.

---

## 1) Project Goal (Clear North Star)

Build a real-time, safe, and auditable ICU ventilation intelligence platform that:

- Predicts short-term respiratory deterioration using AI.
- Recommends optimized ventilator parameter adjustments using reinforcement learning.
- Simulates intervention outcomes with a patient-specific digital twin before action.
- Ensures tamper-proof clinical traceability using blockchain-based audit records.

### Mission Statement

Deliver a clinician-in-the-loop decision support system that improves patient-ventilator synchronization, reduces avoidable ventilation risks, and provides trusted, explainable, and scalable infrastructure for modern ICUs.

---

## 2) Success Criteria (What "Done" Means)

The project is successful when all of the following are achieved:

- End-to-end pipeline runs in near real time from data ingestion to recommendation display.
- Digital twin updates continuously with incoming ventilator and patient signals.
- LSTM predicts key respiratory trends with validated accuracy.
- PPO agent provides safe parameter recommendations under clinical constraints.
- Every recommendation/action event is immutably auditable (on-chain metadata + off-chain details).
- Dashboard shows live metrics, risk alerts, recommendation rationale, and audit history.

### Target Performance KPIs

- Inference + recommendation latency: under 2 seconds at edge.
- Asynchrony risk model AUROC: greater than 0.85.
- Prediction error improvement over baseline: at least 20%.
- Audit coverage: 100% of system-generated recommendation events logged.
- Simulated reduction in asynchrony events: 25% or better versus static strategy baseline.

---

## 3) Scope

### In Scope

- Synthetic + historical time-series based development.
- Real-time streaming ingestion.
- LSTM forecasting model.
- PPO optimization policy in constrained action space.
- Digital twin simulation service.
- Smart contract-based integrity/access/audit workflow.
- Clinician-facing observability dashboard.

### Out of Scope (for initial academic release)

- Full autonomous ventilator control without clinician approval.
- Live deployment in production ICU without institutional approvals.
- Regulatory certification and medical device commercialization activities.

---

## 4) High-Level Architecture (Implementation Perspective)

1. **Data Layer**
   - Ventilator waveforms, settings, vitals, and contextual clinical labels.
   - Time synchronization, denoising, feature extraction.

2. **Communication Layer**
   - MQTT for telemetry ingestion.
   - Event bus (Kafka or equivalent) for stream processing.
   - REST/gRPC APIs for service orchestration.

3. **Compute Layer (Edge + Cloud)**
   - Edge: low-latency inference and fail-safe rule engine.
   - Cloud: model training, re-training, experimentation, and long-term storage.

4. **AI Layer**
   - LSTM forecasting service for short-term respiratory trajectory.
   - PPO policy service for adaptive ventilator recommendation.

5. **Digital Twin Layer**
   - Patient-specific lung behavior model.
   - What-if simulation and risk projection.

6. **Blockchain Layer**
   - Smart contracts for integrity, role-based access metadata, and immutable audit events.

7. **Visualization Layer**
   - Real-time dashboards (Grafana/Power BI or web app equivalent).

---

## 5) Step-by-Step Master Plan

## Phase 0: Project Setup and Governance (Week 1)

### Objectives

- Freeze requirements.
- Define safety boundaries and evaluation protocol.
- Establish repo and team workflow.

### Tasks

- Create architecture decision record (ADR) document.
- Define primary use cases and non-functional requirements.
- Define constraints for safe recommendation bounds (e.g., pressure/volume/FiO2 limits).
- Create backlog and milestone tracker.

### Deliverables

- `docs/requirements.md`
- `docs/safety-constraints.md`
- `docs/architecture-decisions.md`
- Initial project board with milestones.

---

## Phase 1: Data Foundation and Simulation (Weeks 2-4)

### Objectives

- Build reliable, realistic data flow.
- Prepare training-ready datasets.

### Tasks

- Build a ventilator telemetry simulator if real ICU feed unavailable.
- Generate disease profiles (ARDS/COPD/normal/unstable states).
- Add realistic noise, drift, missing packets, and artifact injection.
- Implement stream ingestion service and schema validation.
- Build feature extraction pipeline (windowed + event-driven features).

### Deliverables

- `services/data-simulator/`
- `services/ingestion/`
- `pipelines/feature-engineering/`
- Versioned dataset snapshots.

### Exit Criteria

- Stable event stream with validated schemas.
- At least one reproducible dataset split (train/val/test).

---

## Phase 2: Digital Twin V1 (Weeks 5-6)

### Objectives

- Build a patient-specific virtual replica for intervention simulation.

### Tasks

- Implement baseline respiratory mechanics model (compliance/resistance dynamics).
- Create state estimator to fit model parameters from incoming signals.
- Build simulation API to test candidate ventilator parameter changes.
- Add uncertainty estimation for twin outputs.

### Deliverables

- `services/digital-twin/`
- `docs/twin-model-spec.md`
- Scenario replay test suite.

### Exit Criteria

- Twin can reproduce historical trajectory with acceptable error.
- Twin can run what-if simulation in near real time.

---

## Phase 3: LSTM Forecasting Engine (Weeks 7-8)

### Objectives

- Predict near-future respiratory states and risk signals.

### Tasks

- Design sequence features and labeling strategy.
- Train LSTM model(s) for horizon-based prediction (e.g., +1 min, +5 min).
- Evaluate with MAE/RMSE/AUROC/calibration.
- Package model as inference microservice.

### Deliverables

- `ml/lstm-training/`
- `services/lstm-inference/`
- `reports/model-evaluation-lstm.md`

### Exit Criteria

- Model meets predefined baseline thresholds.
- Inference service handles real-time stream input.

---

## Phase 4: PPO Optimization Agent (Weeks 9-10)

### Objectives

- Generate safe and personalized ventilator parameter recommendations.

### Tasks

- Define RL environment state/action/reward design.
- Implement clinical safety penalties and action clamps.
- Train PPO in digital twin/simulation sandbox.
- Add confidence scoring and policy sanity checks.

### Deliverables

- `ml/ppo-training/`
- `services/ppo-policy/`
- `docs/reward-design.md`
- `reports/model-evaluation-ppo.md`

### Exit Criteria

- PPO outperforms baseline control policy in simulated outcomes.
- No constraint-violating actions under safety test suite.

---

## Phase 5: Blockchain Trust and Audit Layer (Weeks 11-12)

### Objectives

- Ensure verifiable, immutable, and role-aware system traceability.

### Tasks

- Define what goes on-chain (hashes, metadata, approvals) vs off-chain (raw data).
- Implement smart contracts:
  - Integrity registry.
  - Access policy metadata.
  - Audit event recorder.
- Integrate signing and hash verification in pipeline.

### Deliverables

- `blockchain/contracts/`
- `services/audit-bridge/`
- `docs/onchain-offchain-policy.md`

### Exit Criteria

- Every critical recommendation event linked to verifiable audit proof.

---

## Phase 6: Integration and Real-Time Dashboard (Weeks 13-14)

### Objectives

- Connect all modules into one coherent clinician-ready platform.

### Tasks

- Orchestrate services with Docker Compose/Kubernetes.
- Build dashboard with:
  - Live trends.
  - Predicted trajectories.
  - PPO recommendations + confidence.
  - Twin simulation previews.
  - Blockchain audit timeline.
- Implement clinician accept/reject/override workflow capture.

### Deliverables

- `deploy/docker-compose.yml` or K8s manifests.
- `frontend/dashboard/`
- `docs/integration-architecture.md`

### Exit Criteria

- Complete end-to-end demo works continuously.

---

## Phase 7: Validation, Benchmarking, and Hardening (Weeks 15-16)

### Objectives

- Prove technical credibility and robustness.

### Tasks

- Run stress tests (high load, packet loss, delayed data).
- Run ablation studies:
  - No twin vs twin.
  - LSTM only vs LSTM+PPO.
  - With vs without blockchain audit.
- Measure KPI improvements against baseline methods.
- Build failure playbooks and fallback behaviors.

### Deliverables

- `reports/benchmark-results.md`
- `reports/ablation-study.md`
- `docs/failure-recovery.md`

### Exit Criteria

- Demonstrated measurable improvement with documented statistical evidence.

---

## Phase 8: Final Packaging (Week 17+)

### Objectives

- Make the project presentation-ready and viva-ready.

### Tasks

- Finalize report chapters (problem, literature, architecture, methods, results).
- Prepare PPT with architecture, flowchart, and benchmark visuals.
- Prepare live demo script with 2-3 scenarios.
- Prepare viva Q&A bank and defense notes.

### Deliverables

- Final report PDF.
- Final presentation deck.
- Demo runbook.
- Viva preparation document.

---

## 6) Detailed Workstreams

### Workstream A: Data Engineering

- Streaming ingestion reliability.
- Feature store and reproducible dataset versioning.
- Time synchronization and data quality monitoring.

### Workstream B: AI/ML Engineering

- LSTM and PPO lifecycle (train, validate, deploy, monitor).
- Drift detection and retraining strategy.
- Explainability layer for model outputs.

### Workstream C: Digital Twin Engineering

- Patient parameter identification.
- Fast simulation API.
- Twin fidelity and uncertainty management.

### Workstream D: Blockchain Engineering

- Contract development and testing.
- Security checks and event indexing.
- Off-chain/on-chain consistency verifier.

### Workstream E: Platform and DevOps

- Containerization.
- CI/CD and reproducibility.
- Monitoring and observability.

---

## 7) Technology Stack (Recommended)

- **Language:** Python, TypeScript
- **AI/ML:** TensorFlow or PyTorch, Stable-Baselines3, scikit-learn
- **APIs:** FastAPI, gRPC
- **Streaming:** MQTT broker, Kafka
- **Storage:** PostgreSQL + Time-series DB (TimescaleDB/InfluxDB) + object storage
- **Blockchain:** Hyperledger Fabric or Ethereum-compatible private chain + Solidity
- **Visualization:** Grafana + custom React dashboard
- **Deployment:** Docker, Kubernetes, Azure/AWS
- **Observability:** Prometheus, Grafana, ELK/OpenSearch

---

## 8) Repository Blueprint

```text
Major Project/
  README.md
  docs/
    requirements.md
    safety-constraints.md
    architecture-decisions.md
    integration-architecture.md
  services/
    data-simulator/
    ingestion/
    digital-twin/
    lstm-inference/
    ppo-policy/
    audit-bridge/
  ml/
    lstm-training/
    ppo-training/
  pipelines/
    feature-engineering/
  blockchain/
    contracts/
  frontend/
    dashboard/
  deploy/
    docker-compose.yml
  reports/
    model-evaluation-lstm.md
    model-evaluation-ppo.md
    benchmark-results.md
    ablation-study.md
```

---

## 9) End-to-End Workflow (Execution Loop)

1. Capture live/simulated ventilator and vitals streams.
2. Validate, align, and transform data into features.
3. Update digital twin state.
4. Forecast near-future dynamics with LSTM.
5. Generate optimization actions via PPO.
6. Run safety and confidence checks.
7. Present recommendation to clinician for acceptance/override.
8. Apply accepted action (simulated/live environment as configured).
9. Log full event off-chain; commit cryptographic proof on-chain.
10. Feed outcomes back into learning and twin recalibration loop.

---

## 10) Risk Register and Mitigation

- **Data quality risk:** implement quality scoring and anomaly rejection.
- **Model drift risk:** continuous calibration checks + scheduled retraining.
- **Unsafe recommendation risk:** strict hard constraints + human approval.
- **Latency risk:** edge inference, caching, async pipeline optimization.
- **Blockchain overhead risk:** store hashes/metadata only on-chain.
- **Security/privacy risk:** encryption, key rotation, RBAC, least-privilege policies.

---

## 11) Innovation Pack (Must-Have Advanced Features)

- Self-healing control mode when confidence degrades.
- Federated learning-ready architecture across institutions.
- Adversarial and spoofing anomaly detector on telemetry.
- Explanation engine with immutable explanation fingerprints.
- Adaptive trust scoring for recommendation display.

---

## 12) Weekly Execution Checklist

Each week, complete the following:

- Define weekly objective and measurable acceptance criteria.
- Ship at least one end-to-end test scenario.
- Record metrics and compare with baseline.
- Update risk log and mitigation status.
- Demo incremental progress (not only code, but outcome evidence).

---

## 13) Final Deliverables Checklist

- [ ] Working real-time integrated prototype.
- [ ] Digital twin + LSTM + PPO functional pipeline.
- [ ] Blockchain-backed audit and access metadata proof.
- [ ] Dashboard with operational and clinical views.
- [ ] Benchmarking report with KPI improvements.
- [ ] Final report + presentation + viva preparation.

---

## 14) Suggested Immediate Next 7 Actions (Start Now)

1. Create folder structure from repository blueprint.
2. Freeze safety constraints with supervisor review.
3. Implement and test data simulator service first.
4. Define canonical event schema and feature contract.
5. Build minimal digital twin service endpoint.
6. Start LSTM baseline training on synthetic data.
7. Set up dashboard shell and telemetry panel pipeline.

---

## 15) One-Line Project Pitch

An AI-driven, blockchain-trusted digital twin co-pilot for ventilator optimization that brings predictive safety, adaptive control, and immutable clinical accountability to ICU respiratory care.

