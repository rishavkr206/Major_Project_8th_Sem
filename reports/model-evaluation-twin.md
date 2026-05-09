# Digital Twin V1 Evaluation Report (Phase 2 Baseline)

## Scope

This report documents baseline evaluation metrics for the current Digital Twin implementation with deterministic replay support.

Evaluation runner:

- `python pipelines/evaluate_digital_twin.py`

## Scenario Set

The baseline evaluation uses 4 scenarios:

1. ARDS rescue strategy
2. COPD conservative shift
3. Boundary clamp stress
4. High volume warning path

Each scenario performs:

- deterministic simulation (`noise_scale=0`) for stable delta analysis
- seeded stochastic replay checks for consistency validation

## Baseline Metrics (2026-04-22)

| Metric | Value |
| --- | --- |
| Scenario count | 4 |
| Trend direction accuracy | 50.00% |
| Clamp activation rate | 25.00% |
| High tidal-volume warning rate | 50.00% |
| Replay consistency (seeded) | 100.00% |
| Mean absolute delta SpO2 | 16.922 |
| RMSE delta SpO2 | 16.947 |

## Iteration 2 Metrics (2026-04-22, post-tuning)

After tuning twin response coefficients and expanding scenario coverage:

| Metric | Value |
| --- | --- |
| Scenario count | 6 |
| Trend direction accuracy | 100.00% |
| Clamp activation rate | 16.67% |
| High tidal-volume warning rate | 33.33% |
| Replay consistency (seeded) | 100.00% |
| Mean absolute delta SpO2 | 1.495 |
| RMSE delta SpO2 | 1.723 |

## Threshold Gate (Regression Policy)

Evaluation thresholds currently configured in `pipelines/evaluate_digital_twin.py`:

- Minimum trend direction accuracy: `70.0`
- Minimum replay consistency: `100.0`
- Maximum mean absolute delta SpO2: `8.0`
- Maximum RMSE delta SpO2: `10.0`

Command for enforced gate:

- `python pipelines/evaluate_digital_twin.py --fail-on-thresholds`

Current gate outcome:

- **PASS** (all threshold checks passing)
- Command verified:
  - `python pipelines/evaluate_digital_twin.py --fail-on-thresholds`

## Interpretation

- Replay consistency is strong (100%), which satisfies deterministic regression expectations.
- Safety behavior is visible:
  - boundary clamping triggered in stress scenarios
  - high tidal-volume warnings triggered when expected under aggressive settings
- Trend-direction alignment improved after tuning and now meets threshold gate criteria.
- Delta error magnitudes are substantially reduced versus baseline run and currently pass configured gate thresholds.

## Iteration 3 — Historical Trajectory Replay (Phase 2 Exit Criterion)

Runner: `pipelines/historical_replay_benchmark.py`
Dataset: real ICU export `clean_full_data_v2.csv` (falls back to `data/simulated_phase1.csv`).
Method: 12-row calibration window per patient → walk-forward replay across the next 24 rows
applying the *actual* clinician PEEP/FiO₂/TidalVol settings, comparing predicted SpO₂ vs
observed SpO₂.

Two scoring modes:

- **teacher_forced** — prediction conditioned on previous *actual* SpO₂ (one-step-ahead error).
- **free_running** — prediction feeds back into next step (multi-step drift error).

| Metric (100 patients, real ICU) | Value | Threshold | Status |
| --- | --- | --- | --- |
| teacher_forced.mae_avg  | 1.689 SpO₂ pp | ≤ 4.0  | ✅ |
| teacher_forced.rmse_avg | 2.175 SpO₂ pp | —       | — |
| teacher_forced.mae_p50  | 1.286 SpO₂ pp | —       | — |
| teacher_forced.mae_p95  | 4.232 SpO₂ pp | —       | — |
| free_running.mae_avg    | 2.868 SpO₂ pp | ≤ 6.0  | ✅ |
| free_running.rmse_avg   | 3.353 SpO₂ pp | —       | — |
| free_running.mae_p50    | 2.062 SpO₂ pp | —       | — |
| free_running.mae_p95    | 8.050 SpO₂ pp | informational | — |

Detailed JSON: `reports/twin_historical_replay.json`.

CI gate command (non-zero exit on failure):

```
python pipelines/historical_replay_benchmark.py --fail-on-thresholds
```

**Interpretation:** The twin one-step-ahead error of ~1.7 SpO₂ percentage points
matches the typical noise floor of pulse-oximetry measurement itself. Free-running
6-hour drift sits below 3 SpO₂ pp on average, which is well within "acceptable
error" for what-if planning. Phase 2 exit criterion #1 (*"Twin can reproduce
historical trajectory with acceptable error"*) is satisfied.

## Next Improvements

- Calibrate per-disease-profile compliance priors from labeled MIMIC subsets.
- Add a residual-tail model (e.g. small GP) to absorb the long-tail of patients with
  free-running MAE > 8 (current p95).
- Optional: compare against a naive "persistence" baseline (predict SpO₂ stays constant)
  as a sanity-check denominator.
