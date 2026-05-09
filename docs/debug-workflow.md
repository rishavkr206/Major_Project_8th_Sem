# Debug Workflow: Twin Replay Endpoint

## Purpose

Use `/twin/replay` to validate digital twin behavior with deterministic or seeded replay runs before changing recommendation logic.

## API Endpoint

- `POST /twin/replay`

## Recommended Debug Sequence

1. Start API:
   - `python api/main.py`
2. Send deterministic replay request (`noise_scale=0`) for stable baseline.
3. Re-run same payload to confirm identical trajectory.
4. Send seeded stochastic replay request (`noise_scale>0`, fixed `seed`) to validate replay consistency.
5. Compare:
   - `trajectory`
   - `delta_spo2`
   - `risk_flag`
   - `applied` clamp behavior

## Example Deterministic Request

```bash
curl -X POST "http://127.0.0.1:8000/twin/replay" -H "Content-Type: application/json" -d "{\"stay_id\":910050,\"history\":[{\"SpO2\":91.0,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.1,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.2,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.3,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.4,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.5,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.6,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.7,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.8,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":91.9,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":92.0,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20},{\"SpO2\":92.1,\"PEEP\":8.0,\"FiO2\":55.0,\"TidalVol\":450.0,\"HR\":90,\"MAP\":75,\"RespRate\":20}],\"proposed\":{\"PEEP\":10.0,\"FiO2\":65.0,\"TidalVol\":430.0},\"current_spo2\":92.0,\"steps\":4,\"noise_scale\":0.0}"
```

## Example Seeded Stochastic Request

```bash
curl -X POST "http://127.0.0.1:8000/twin/replay" -H "Content-Type: application/json" -d "{\"stay_id\":910050,\"proposed\":{\"PEEP\":10.0,\"FiO2\":65.0,\"TidalVol\":430.0},\"steps\":4,\"noise_scale\":1.0,\"seed\":1234}"
```

## Frontend Debug Panel Notes

- Expose controls for:
  - `steps`
  - `noise_scale`
  - `seed`
  - proposed settings (`PEEP`, `FiO2`, `TidalVol`)
- Add quick toggle:
  - "Deterministic mode" -> force `noise_scale=0`
- Render:
  - trajectory line chart
  - uncertainty bands
  - applied (clamped) settings summary
  - risk flags (`risk_flag`, `tv_risk`)
