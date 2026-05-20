# Ventilator Digital Twin (simulated)

This scaffold provides a simulated ventilator digital twin using FIWARE Orion Context Broker, a FastAPI backend simulator, MQTT broker (Mosquitto), and a simple frontend dashboard (Tailwind + Chart.js).

Services (docker-compose):
- MongoDB
- FIWARE Orion Context Broker (NGSIv2)
- Mosquitto MQTT
- Backend (FastAPI) — serves frontend and runs simulator

How it works:
- The backend runs a simulation loop emitting ventilator and patient telemetry every second.
- Telemetry is written to Orion entities (`Ventilator:V1`, `Patient:P1`) and alert entities are created when abnormal conditions are detected.
- A WebSocket `/ws` streams telemetry and alerts to the frontend.
- Frontend provides controls to update setpoints (oxygen, pressure, breathing rate) via `POST /control`.
- Simple AI predictions (heuristic-based) are computed server-side and included in the telemetry stream.

Run (from repository root):

1. Build and start services:

```bash
cd "digital_twin"
docker-compose up --build
```

2. Open the dashboard: http://localhost:8000

Notes and next steps:
- This is simulated data only and not for clinical use.
- You can extend AI predictions by replacing the `ai_predictions` function in `backend/main.py`.
- The backend mounts `frontend/` statically — edit `frontend/index.html` and `frontend/app.js` to change UI.
