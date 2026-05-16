# Safety Constraints for Ventilator Recommendations

## Objective

Define strict recommendation bounds and safety rules for the prototype decision support pipeline.

## Hard Parameter Bounds

- `PEEP`: 3.0 to 20.0 cmH2O
- `FiO2`: 21.0 to 100.0 percent
- `TidalVol`: 200.0 to 800.0 mL
- `SpO2` expected physiological range in simulation: 55.0 to 100.0 percent

Any recommendation outside hard bounds must be rejected and clamped to nearest valid limit.

## Safety Rules

- **SC-01 Bound enforcement:** Always clamp proposed parameter updates to hard bounds.
- **SC-02 Risk alerting:** Flag a recommendation as high risk when predicted/simulated mean SpO2 falls below 90.
- **SC-03 High tidal volume warning:** Raise warning when `TidalVol > 600` mL.
- **SC-04 Null-safe behavior:** If critical telemetry fields are missing, recommendation must either:
  - use last valid values with warning, or
  - return "insufficient data" status (preferred for production mode).
- **SC-05 Clinician final control:** No autonomous ventilator actuation; recommendation requires clinician action.
- **SC-06 Audit logging:** Log all recommendation and clinician decision events with payload hash linkage.

## Operational Fallbacks

- If model confidence is low, provide conservative recommendation and explicit warning message.
- If audit bridge is unavailable, cache event payloads for retry and mark audit status as degraded.
- If schema validation fails, reject record and prevent downstream model inference for that event.

## Validation Checklist

- [x] API enforces batch argument constraints for simulator endpoint.
- [x] Telemetry schema validation exists before returning simulator events.
- [x] Simulator outputs are bounded to clinical ranges.
- [ ] End-to-end confidence threshold policy documented and enforced in API response contract.
- [x] Automated safety regression tests for edge-case physiological extremes (`tests/test_digital_twin_safety.py` — 16 tests covering bound clamping at infinities, calibration extremes, empty/single-point history, invalid simulate args, trajectory clipping, and risk-flag semantics).
