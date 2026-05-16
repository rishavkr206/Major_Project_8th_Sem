# Canonical Telemetry Event Schema (Phase 1)

This schema defines the canonical payload contract for simulated/live ventilator telemetry used by ingestion, feature engineering, digital twin calibration, and model inference.

## Event Type

- `ventilator_telemetry.v1`

## Required Fields

- `stay_id` (integer): ICU stay identifier.
- `charttime` (string, ISO-8601 UTC): event timestamp.
- `HR` (number or null): heart rate, bpm.
- `MAP` (number or null): mean arterial pressure, mmHg.
- `RespRate` (number or null): respiratory rate, breaths/min.
- `SpO2` (number or null): oxygen saturation percentage.
- `PEEP` (number or null): positive end-expiratory pressure, cmH2O.
- `FiO2` (number or null): inspired oxygen fraction percentage.
- `TidalVol` (number or null): tidal volume, mL.

## Validation Rules

- `charttime` must be parseable as ISO timestamp.
- Numeric fields must lie within clinical bounds when not null:
  - `HR`: 35 to 220
  - `MAP`: 35 to 145
  - `RespRate`: 6 to 55
  - `SpO2`: 55 to 100
  - `PEEP`: 3 to 20
  - `FiO2`: 21 to 100
  - `TidalVol`: 200 to 800
- `stay_id` must be positive integer.
- Missing packet behavior is represented with `null` values in a subset of numeric fields.

## Notes

- In this prototype, schema versioning is documented by file revision and event-type suffix (`v1`).
- Future versions should include:
  - explicit `event_id`
  - producer identifier
  - checksum/hash for transport integrity
