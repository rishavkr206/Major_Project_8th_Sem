# FIWARE Digital Twin Integration

This project now includes a FIWARE adapter service that publishes the ventilator digital twin and patient telemetry to an Orion Context Broker.

## What is implemented

- `services/fiware_adapter.py` — publishes FIWARE-compatible entities using NGSI-LD by default.
- `api/main.py` now publishes:
  - patient history snapshots from `/patient/{stay_id}/history`
  - digital twin replay output from `/twin/replay`
  - AI recommendation results from `/patient/{stay_id}/recommend`
- `GET /fiware/status` — verifies Orion reachability and adapter configuration.

## FIWARE Entity Model

The adapter creates/updates a `VentilatorTwin` entity with the following attributes:

- `SpO2`, `PEEP`, `FiO2`, `TidalVol`
- `HR`, `MAP`, `RespRate`
- `complianceFactor`, `baselineSpO2`
- `lastPEEP`, `lastFiO2`, `lastTidalVol`
- `uncertainty`, `isCalibrated`
- `trajectory`, `upperBand`, `lowerBand`
- `meanSpO2`, `deltaSpO2`, `riskFlag`, `tvRisk`
- `appliedPEEP`, `appliedFiO2`, `appliedTidalVol`
- `eventSource`, `observationSource`, `historyLength`

### Recommended FIWARE setup

1. Run a FIWARE Orion broker on `http://localhost:1026`.
2. Optional: run `QuantumLeap` + `CrateDB` to persist time-series history.
3. Configure environment variables if you need non-default values:
   - `FIWARE_BASE_URL` — Orion base URL (default: `http://localhost:1026`)
   - `FIWARE_API_VERSION` — `ld` (default) or `v2`
   - `FIWARE_SERVICE` — service header tenant (default: `openiot`)
   - `FIWARE_SERVICE_PATH` — service path (default: `/`)
   - `FIWARE_ENABLED` — set to `false` to disable FIWARE publication

## Example FIWARE status check

```bash
curl http://127.0.0.1:8000/fiware/status
```

## Example Orion payload

### NGSI-LD

```json
{
  "id": "urn:ngsi-ld:VentilatorTwin:30004018",
  "type": "VentilatorTwin",
  "SpO2": {"type": "Property", "value": 94.1},
  "PEEP": {"type": "Property", "value": 10.0},
  "FiO2": {"type": "Property", "value": 60.0},
  "TidalVol": {"type": "Property", "value": 450.0},
  "trajectory": {"type": "Property", "value": [94.1, 94.7, 95.1]},
  "riskFlag": {"type": "Property", "value": false}
}
```

### NGSI v2

The same entity is published with `Content-Type: application/json` to `/v2/entities?options=upsert`.

## Free 3D Ventilator Model

The dashboard now ships with a built-in ventilator model at `frontend/dashboard/ventilator.glb` and uses `<model-viewer>` for browser rendering.

### Recommended sources for improved models

- `Free3D` — search for `ventilator` and pick a downloadable `glTF`/`GLB` asset.
- `Sketchfab` — filter to `downloadable` models and choose a free license.
- `TurboSquid` / `Creazilla` — good fallback sources for free medical device assets.

### License guidance

Choose a model that is explicitly licensed for free use:

- `CC0` (public domain)
- `Creative Commons Attribution`
- platform-specific free license with no commercial restriction if your project is academic

### Best practice

- Prefer a low-to-medium poly `glTF`/`GLB` model for browser performance.
- Keep the model in the dashboard folder, e.g. `frontend/dashboard/ventilator.glb`.
- Render it with a simple WebGL viewer such as `<model-viewer>` or `three.js`.

## How to make it perfect

- Use `/fiware/status` to confirm Orion connectivity before running the dashboard.
- Keep the twin contract in `docs/twin-model-spec.md` aligned with Orion attributes.
- Publish patient history from the same endpoint that supplies the dashboard.
- Publish twin simulation results immediately after a replay request for audit and visualization.

## If Orion is not running

The API still works normally with the existing simulator and digital twin.
The FIWARE adapter will safely print a warning if publishing is unavailable.
