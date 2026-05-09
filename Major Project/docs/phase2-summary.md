# Phase 2 — Digital Twin V1: Closeout Summary

This document is the single-page traceability map for Phase 2. It links the
specification → tests → evaluation → quality gate → CI → dashboard surface,
so any reviewer can verify the phase is complete in one read.

## 1. Goals (from README §Phase 2)

- Build a patient-specific virtual replica of respiratory mechanics.
- Enable safe what-if simulation of proposed ventilator parameter changes.
- Provide uncertainty estimates and deterministic replay for regression testing.

**Exit criteria (from README):**
1. Twin can reproduce historical trajectory with acceptable error.
2. Twin can run what-if simulation in near real time.

Both criteria are now satisfied — see §5 for evidence.

## 2. Specification

- Contract: [`docs/twin-model-spec.md`](twin-model-spec.md)
- Inputs: patient observation history (≥ 12 records of `SpO2/PEEP/FiO2/TidalVol/HR/MAP/RespRate`),
  proposed ventilator settings, current SpO2.
- Outputs: trajectory, upper/lower bands, mean SpO2, delta SpO2, uncertainty,
  risk_flag, tv_risk, applied (post-clamp) settings.
- Hard safety bounds:
  - PEEP 3–20 cmH₂O · FiO₂ 21–100 % · TidalVol 200–800 mL · SpO₂ clipping 60–100 %
- Determinism contract: identical inputs with `noise_scale=0` or seeded RNG → byte-identical trajectory.

## 3. Implementation

| Layer | File | Role |
| --- | --- | --- |
| Core model | [`services/digital_twin.py`](../services/digital_twin.py) | calibrate, simulate, safety clamp, uncertainty |
| API surface | [`api/main.py`](../api/main.py) — `POST /twin/replay` | deterministic / seeded stochastic replay; emits `TWIN_SIM` audit block |
| Audit wiring | [`services/audit_bridge.py`](../services/audit_bridge.py) | every replay logged as `TWIN_SIM` event with payload + chain hash |
| Dashboard panel | [`frontend/dashboard/index.html`](../frontend/dashboard/index.html) | "Twin Replay (Debug)" with bands, applied settings, risk badges |

## 4. Tests

| File | Coverage | Result |
| --- | --- | --- |
| [`tests/test_digital_twin_replay.py`](../tests/test_digital_twin_replay.py) | deterministic replay, safe-bound clamp, seeded RNG repeatability | 3 / 3 ✅ |
| [`tests/test_digital_twin_safety.py`](../tests/test_digital_twin_safety.py) | extreme proposed settings (incl. ±∞), severe / supranormal calibration histories, empty/single-point history, invalid `simulate()` args, trajectory bound clipping, risk-flag semantics, output structure contract, band positivity | 16 / 16 ✅ |
| [`tests/test_simulator_api.py`](../tests/test_simulator_api.py) | `/twin/replay` happy path, `/twin/replay` step-validation, **TWIN_SIM audit-block append + chain re-verify** | 4 / 4 ✅ |

Run all: `python -m unittest discover -s tests -p "test_*.py"`.

## 5. Evaluation Evidence

### 5a. Synthetic-scenario gate
Runner: [`pipelines/evaluate_digital_twin.py`](../pipelines/evaluate_digital_twin.py)
Scenarios: ARDS rescue, COPD wean, boundary-clamp stress, high-volume warning, oxygen wean, mild recruitment.

| Metric | Value | Threshold | Status |
| --- | --- | --- | --- |
| trend_direction_accuracy | 100.00 % | ≥ 70 % | ✅ |
| replay_consistency       | 100.00 % | ≥ 100 % | ✅ |
| mean_abs_delta_spo2      | 1.495   | ≤ 8.0  | ✅ |
| rmse_delta_spo2          | 1.723   | ≤ 10.0 | ✅ |

CI command (non-zero exit on failure): `python pipelines/evaluate_digital_twin.py --fail-on-thresholds`

### 5b. Historical-trajectory replay (Phase 2 exit criterion #1)
Runner: [`pipelines/historical_replay_benchmark.py`](../pipelines/historical_replay_benchmark.py)
Dataset: real ICU export `clean_full_data_v2.csv`, 100 patient stays, 12-step calibration, 24-step replay horizon.

| Metric | Value | Threshold | Status |
| --- | --- | --- | --- |
| teacher_forced.mae_avg | 1.69 SpO₂ pp | ≤ 4.0 | ✅ |
| teacher_forced.rmse_avg | 2.17 SpO₂ pp | — | — |
| free_running.mae_avg   | 2.87 SpO₂ pp | ≤ 6.0 | ✅ |
| free_running.rmse_avg  | 3.35 SpO₂ pp | — | — |
| free_running.mae_p95   | 8.05 SpO₂ pp | informational | — |

Detailed JSON: `reports/twin_historical_replay.json`.

CI command: `python pipelines/historical_replay_benchmark.py --fail-on-thresholds`

### 5c. Real-time simulate() latency (exit criterion #2)
- Single 4-step deterministic call ≈ < 1 ms on commodity laptop CPU (no model load, pure NumPy).
- API end-to-end `/twin/replay` round-trip ≈ < 10 ms (FastAPI + JSON + audit insert).
- Well under the 2-second NFR-01 latency budget.

## 6. CI Quality Gate

Workflow: `.github/workflows/twin-quality-gate.yml`

Triggers on push / PR for twin-related paths. Runs:
1. `python -m unittest discover -s tests -p "test_*.py"` — all 23 tests must pass.
2. `python pipelines/evaluate_digital_twin.py --fail-on-thresholds` — synthetic gate.
3. (Recommended addition) `python pipelines/historical_replay_benchmark.py --fail-on-thresholds` — real-data gate.

## 7. Dashboard Surface (Phase 2 ↔ Phase 6 wiring)

`frontend/dashboard/index.html` exposes:
- Main trajectory chart now overlays the twin's `trajectory` and shaded `±uncertainty` band.
- "Twin Replay (Debug)" panel: configurable PEEP / FiO₂ / TidalVol / steps / noise_scale / seed.
  - Calls `POST /twin/replay`.
  - Renders mini trajectory chart with bands.
  - Displays applied (post-clamp) settings, mean SpO₂, delta SpO₂, uncertainty, compliance.
  - Shows risk_flag and tv_risk badges.
  - Emits a visible warning when proposed values were clamped.
- Audit timeline now renders `TWIN_SIM` events (purple flask icon) alongside RECOMMENDATION / ACCEPT / OVERRIDE / REJECT / ALERT / MODEL_INFER.

## 8. Remaining Phase 2 Work — None

All originally queued items from README §Step 18 "Next Implementation Steps" plus the Phase 2 exit criteria are complete:

| Originally queued | Status |
| --- | --- |
| Integrate tuned twin behavior into recommendation reporting flow | ✅ already wired in `services/ppo_policy.py:153` |
| Dashboard-side replay visualization panel scaffold | ✅ Item 2/3 of this closeout |
| Phase 2 summary section mapping spec → tests → gate → CI | ✅ this document |
| Implementation log kept current after each milestone | ✅ updated in README + this file |

Phase 2 is **complete**. Next phase: LSTM Phase 3 closeout (`reports/model-evaluation-lstm.md`).
