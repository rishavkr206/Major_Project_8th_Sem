import os
import time
import asyncio
import json
import math
from typing import Dict, List

import requests
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ORION = os.environ.get("ORION_URL", "http://orion:1026/v2")
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

clients: List[WebSocket] = []
setpoints = {"oxygen": 95.0, "pressure": 18.0, "breathing_rate": 16.0}


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def ai_predictions(oxygen, pressure, breathing_rate):
    # simple heuristics + logistic transform
    hypoxia_score = sigmoid((90 - oxygen) / 5)
    pressure_risk = sigmoid((pressure - 20) / 3)
    apnea_risk = sigmoid((20 - breathing_rate) / 5)
    return {"hypoxia_prob": float(hypoxia_score), "pressure_risk_prob": float(pressure_risk), "apnea_prob": float(apnea_risk)}


def orion_headers():
    return {"Content-Type": "application/json"}


def create_or_update_entity(entity_id: str, entity_type: str, attrs: Dict):
    url = f"{ORION}/entities"
    payload = {"id": entity_id, "type": entity_type}
    for k, v in attrs.items():
        payload[k] = {"value": v}
    # try create
    r = requests.post(url, json=payload, headers=orion_headers())
    if r.status_code in (201, 204):
        return True
    # if exists, patch
    patch_url = f"{ORION}/entities/{entity_id}/attrs"
    body = {k: {"value": v} for k, v in attrs.items()}
    r2 = requests.patch(patch_url, json=body, headers=orion_headers())
    return r2.status_code in (204,)


async def broadcast(message: Dict):
    living = []
    for ws in clients:
        try:
            await ws.send_json(message)
            living.append(ws)
        except Exception:
            pass
    clients.clear()
    clients.extend(living)


async def simulator_loop():
    ventilator_id = "Ventilator:V1"
    patient_id = "Patient:P1"
    while True:
        # simulate
        oxygen = max(60.0, min(100.0, setpoints["oxygen"] + np.random.normal(0, 1.5)))
        pressure = max(5.0, min(40.0, setpoints["pressure"] + np.random.normal(0, 1.2)))
        breathing_rate = max(6.0, min(40.0, setpoints["breathing_rate"] + np.random.normal(0, 1.0)))
        timestamp = int(time.time())

        ai = ai_predictions(oxygen, pressure, breathing_rate)

        telemetry = {
            "oxygen": round(float(oxygen), 2),
            "pressure": round(float(pressure), 2),
            "breathing_rate": round(float(breathing_rate), 2),
            "timestamp": timestamp,
            "ai": ai,
        }

        # update Orion
        try:
            create_or_update_entity(ventilator_id, "Ventilator", {"pressure": telemetry["pressure"], "status": "ON", "lastUpdate": timestamp})
            create_or_update_entity(patient_id, "Patient", {"oxygen": telemetry["oxygen"], "breathing_rate": telemetry["breathing_rate"], "lastUpdate": timestamp})
        except Exception:
            pass

        # check alerts
        alerts = []
        if telemetry["oxygen"] < 88.0:
            alerts.append({"type": "hypoxia", "message": f"Low oxygen {telemetry['oxygen']}%"})
        if telemetry["pressure"] > 28.0:
            alerts.append({"type": "pressure", "message": f"High airway pressure {telemetry['pressure']} cmH2O"})

        # create alert entities in Orion and include in broadcast
        for i, a in enumerate(alerts, start=1):
            alert_id = f"Alert:{timestamp}:{i}"
            try:
                create_or_update_entity(alert_id, "Alert", {"alertType": a["type"], "message": a["message"], "timestamp": timestamp})
            except Exception:
                pass

        payload = {"telemetry": telemetry, "alerts": alerts}
        # broadcast to websockets
        await broadcast({"type": "telemetry", "data": payload})

        await asyncio.sleep(1.0)


@app.on_event("startup")
async def startup_event():
    # launch simulator background task
    asyncio.create_task(simulator_loop())


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep open; client can send pings or commands if desired
    except WebSocketDisconnect:
        try:
            clients.remove(ws)
        except Exception:
            pass


@app.post("/control")
async def control(params: Dict):
    # expected: {"oxygen": 95, "pressure": 18, "breathing_rate": 16}
    global setpoints
    for k in ("oxygen", "pressure", "breathing_rate"):
        if k in params:
            setpoints[k] = float(params[k])
    return {"status": "ok", "setpoints": setpoints}


@app.get("/api/status")
async def status():
    return {"service": "digital-twin-backend", "orion": ORION, "mqtt": MQTT_BROKER}
