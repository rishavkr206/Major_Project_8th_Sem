# Digital Twin V1 Model Specification

## Scope

Define the behavior contract for `DigitalTwin` in Phase 2, including calibration, what-if simulation, uncertainty handling, and replay validation expectations.

## Model Inputs

- Observation history records (minimum expected fields):
  - `SpO2`, `PEEP`, `FiO2`, `TidalVol`
  - optional contextual fields used upstream: `HR`, `MAP`, `RespRate`
- Proposed ventilator settings:
  - `PEEP`, `FiO2`, `TidalVol`
- Current measured `SpO2`

## Core State Parameters

- `compliance_factor`: inferred lung response multiplier from recent variability.
- `baseline_spo2`: average recent oxygen saturation.
- `last_PEEP`, `last_FiO2`, `last_TidalVol`: baseline settings snapshot.
- `uncertainty`: scalar confidence band width estimate.
- `is_calibrated`: calibration completion flag.

## Calibration Contract

- Method: `calibrate(history)`
- Uses most recent window (last 12 observations).
- Updates baseline settings and compliance estimate.
- Compliance estimation heuristic:
  - higher SpO2 variability -> lower compliance
- Uncertainty estimate:
  - derived from SpO2 standard deviation
  - minimum floor retained to avoid zero-uncertainty outputs

## Simulation Contract

- Method: `simulate(proposed, current_spo2, steps=4, noise_scale=1.0, rng=None)`
- Safety behavior:
  - proposed values are clamped to hard bounds
  - invalid `steps < 1` rejected
  - invalid `noise_scale < 0` rejected
- Output fields:
  - `trajectory`, `upper_band`, `lower_band`
  - `mean_spo2`, `delta_spo2`, `uncertainty`
  - `risk_flag`, `tv_risk`
  - `applied` (post-clamp settings)

## Clinical Bounds (V1)

- `PEEP`: 3.0 to 20.0
- `FiO2`: 21.0 to 100.0
- `TidalVol`: 200.0 to 800.0
- Simulated SpO2 clipping: 60.0 to 100.0

## Deterministic Replay Requirement

For scenario replay tests, use:

- fixed calibration history
- `noise_scale=0` or seeded RNG

This ensures stable outcomes for regression checking across code changes.

## Validation Metrics (Phase 2 Target)

- Twin trajectory plausibility under bounded interventions
- Safety-bound adherence rate: 100%
- Replay consistency under deterministic mode: 100%
- Mean prediction error against held-out trajectory (to be measured in Phase 2 evaluation report)
