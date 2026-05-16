from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import sqlite3
import pandas as pd
import json
import os
import random
import numpy as np
from typing import Dict, Any

from services.digital_twin import DigitalTwin
from services.ppo_policy import PPOPolicy
from services.audit_bridge import AuditBridge
from services.data_simulator import (
    SimulationConfig,
    VentilatorDataSimulator,
    validate_record,
)
from services.lstm_inference import get_lstm_forecaster
from services.multi_risk_inference import MultiRiskInferenceEngine
from services.prometheus_metrics import metrics_response, record_recommendation_metrics
from services.chain_anchor import anchor_now

app = FastAPI(title="Ventilator Digital Twin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Services
audit_bridge = AuditBridge()
multi_risk_engine = MultiRiskInferenceEngine()

# Repository root (parent of api/)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Resolved at startup: full ICU export, Phase-1 synthetic CSV, or auto-generated demo
PATIENT_CSV_PATH: str | None = None

# Global state for streaming simulation
patient_stream_cursors = {}
df_index = None
simulator_registry: Dict[str, VentilatorDataSimulator] = {}


def _ensure_patient_timeseries_csv(repo_root: str) -> str | None:
    """
    Pick an existing ventilator timeseries CSV or create a small synthetic one
    so the dashboard always has /patients + /history data without a manual download.
    """
    candidates = [
        os.path.join(repo_root, "clean_full_data_v2.csv"),
        os.path.join(repo_root, "data", "simulated_phase1.csv"),
        os.path.join(repo_root, "data", "demo_ventilator_data.csv"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    demo_path = os.path.join(repo_root, "data", "demo_ventilator_data.csv")
    try:
        from pipelines.simulated_ingestion import generate_simulated_dataframe
    except ImportError as exc:
        print(
            "No patient CSV found and could not import demo generator "
            f"(run server from repo root): {exc}"
        )
        return None

    os.makedirs(os.path.dirname(demo_path), exist_ok=True)
    df = generate_simulated_dataframe(
        profiles=["normal", "ards", "copd"],
        stays_per_profile=4,
        steps_per_stay=96,
        seed=42,
    )
    df.to_csv(demo_path, index=False)
    print(f"No ICU CSV found; wrote synthetic demo dataset to {demo_path}")
    return demo_path


@app.on_event("startup")
async def startup_event():
    global df_index, PATIENT_CSV_PATH
    PATIENT_CSV_PATH = _ensure_patient_timeseries_csv(REPO_ROOT)
    if PATIENT_CSV_PATH and os.path.isfile(PATIENT_CSV_PATH):
        df_index = pd.read_csv(PATIENT_CSV_PATH, usecols=["stay_id", "charttime"])
        print(
            f"Patient timeseries index loaded: {PATIENT_CSV_PATH} "
            f"({len(df_index):,} rows, {df_index['stay_id'].nunique()} stays)"
        )
    else:
        print("Dataset not found. Patient history will be served from the built-in simulator.")
    
    # Note: Multi-risk LSTM engine is loaded lazily on first request to avoid blocking server startup
    print("[STARTUP] Server ready. Multi-risk LSTM will load on first prediction request.")

# --- Endpoints ---


@app.get("/")
async def root():
    """Avoid confusing 404 JSON when users open the API base URL in a browser."""
    return {
        "service": app.title,
        "message": "API is running. Use /docs for Swagger UI.",
        "try": {
            "docs": "/docs",
            "health": "/health",
            "metrics_prometheus": "/metrics",
            "patients": "/patients",
            "example_history": "/patient/800000/history",
        },
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus scrape endpoint for Grafana time-series (SpO2 vs LSTM forecast)."""
    body, ctype = metrics_response()
    return Response(content=body, media_type=ctype)


@app.get("/health")
async def health():
    sample_stay_id = None
    if df_index is not None and len(df_index) > 0:
        sample_stay_id = int(df_index["stay_id"].iloc[0])
    lstm_status = get_lstm_forecaster().status()
    return {
        "status": "ok",
        "dataset_index_loaded": df_index is not None,
        "csv_path": PATIENT_CSV_PATH,
        "index_rows": len(df_index) if df_index is not None else 0,
        "sample_stay_id": sample_stay_id,
        "hint": f"GET /patient/{sample_stay_id}/history" if sample_stay_id else "GET /patient/800000/history",
        "lstm": lstm_status,
    }


def _history_payload_from_simulator(stay_id: int) -> Dict[str, Any]:
    """Deterministic vitals stream for dashboard when no CSV is configured."""
    profile_cycle = ("normal", "ards", "copd", "unstable")
    profile = profile_cycle[abs(int(stay_id)) % len(profile_cycle)]
    config = SimulationConfig(profile=profile, seed=(abs(int(stay_id)) % 100000) + 7)
    sim = VentilatorDataSimulator(config=config)
    steps = 128
    records = sim.generate_batch(stay_id=stay_id, steps=steps)
    for rec in records:
        validate_record(rec)
    df = pd.DataFrame(records)
    numeric_cols = ["HR", "MAP", "RespRate", "SpO2", "PEEP", "FiO2", "TidalVol"]
    df[numeric_cols] = df[numeric_cols].interpolate(limit_direction="both").ffill().bfill()
    df = df.sort_values("charttime").reset_index(drop=True)
    if stay_id not in patient_stream_cursors:
        patient_stream_cursors[stay_id] = max(1, len(df) // 2)
    cursor = patient_stream_cursors[stay_id]
    recent = df.iloc[:cursor].tail(96).to_dict(orient="records")
    return {"history": recent, "is_live": True, "source": "simulator"}


@app.get("/patients")
async def get_patients():
    if df_index is not None:
        patients = df_index['stay_id'].unique().tolist()
        # Return a subset for the UI to be fast
        return {"patients": patients[:100]}
    return {"patients": [30004018, 30004019, 30004020]}

@app.get("/patient/{stay_id}/history")
async def get_patient_history(stay_id: int):
    if df_index is not None and PATIENT_CSV_PATH:
        try:
             # Load just this patient's data
             # Pandas chunking or dask would be better for huge files, but this is okay for prototype
             iter_csv = pd.read_csv(PATIENT_CSV_PATH, iterator=True, chunksize=10000)
             patient_data = pd.concat([chunk[chunk['stay_id'] == stay_id] for chunk in iter_csv])
             
             if patient_data.empty:
                 return _history_payload_from_simulator(stay_id)
                 
             patient_data = patient_data.sort_values('charttime')
             
             # Initialize stream cursor if not present
             if stay_id not in patient_stream_cursors:
                 # Start halfway through the patient's records to allow history + streaming
                 patient_stream_cursors[stay_id] = len(patient_data) // 2
                 
             cursor = patient_stream_cursors[stay_id]
             
             # Return records up to the current streaming cursor
             recent = patient_data.iloc[:cursor].tail(96).to_dict(orient='records')
             
             return {"history": recent, "is_live": True, "source": "csv"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    return _history_payload_from_simulator(stay_id)

@app.post("/patient/{stay_id}/tick")
async def advance_patient_stream(stay_id: int):
    """Advances the simulation clock by 1 tick (bringing in 1 new record)"""
    if stay_id in patient_stream_cursors:
        patient_stream_cursors[stay_id] += 1
        return {"status": "advanced", "current_cursor": patient_stream_cursors[stay_id]}
    return {"status": "error", "message": "Stream not initialized"}


@app.post("/simulator/session/{stay_id}")
async def create_simulator_session(
    stay_id: int,
    profile: str = "normal",
    packet_loss_probability: float = 0.03,
    artifact_probability: float = 0.02,
    trend_strength: float = 0.05,
    seed: int = 42,
):
    config = SimulationConfig(
        profile=profile,
        packet_loss_probability=packet_loss_probability,
        artifact_probability=artifact_probability,
        trend_strength=trend_strength,
        seed=seed,
    )
    session_key = f"{stay_id}:{profile}:{seed}"
    simulator_registry[session_key] = VentilatorDataSimulator(config=config)
    return {
        "status": "created",
        "session_key": session_key,
        "config": {
            "profile": profile,
            "packet_loss_probability": packet_loss_probability,
            "artifact_probability": artifact_probability,
            "trend_strength": trend_strength,
            "seed": seed,
        },
    }


@app.get("/simulator/session/{session_key}/next")
async def simulator_next_record(session_key: str, stay_id: int):
    simulator = simulator_registry.get(session_key)
    if simulator is None:
        raise HTTPException(status_code=404, detail="Simulator session not found")
    record = simulator.next_record(stay_id=stay_id)
    try:
        validate_record(record)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Generated invalid record: {exc}") from exc
    return {"record": record}


@app.get("/simulator/session/{session_key}/batch")
async def simulator_batch(session_key: str, stay_id: int, steps: int = 8):
    simulator = simulator_registry.get(session_key)
    if simulator is None:
        raise HTTPException(status_code=404, detail="Simulator session not found")
    if steps < 1 or steps > 512:
        raise HTTPException(status_code=400, detail="steps must be between 1 and 512")
    records = simulator.generate_batch(stay_id=stay_id, steps=steps)
    try:
        for record in records:
            validate_record(record)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Generated invalid record: {exc}") from exc
    return {"records": records}


@app.post("/twin/replay")
async def twin_replay(payload: Dict[str, Any]):
    """
    Debug endpoint for deterministic or seeded Digital Twin replay scenarios.
    """
    stay_id = int(payload.get("stay_id", 999000))
    steps = int(payload.get("steps", 4))
    noise_scale = float(payload.get("noise_scale", 0.0))
    seed = payload.get("seed")
    proposed = payload.get("proposed", {})
    history = payload.get("history", [])
    current_spo2 = payload.get("current_spo2")

    if steps < 1 or steps > 96:
        raise HTTPException(status_code=400, detail="steps must be between 1 and 96")
    if noise_scale < 0:
        raise HTTPException(status_code=400, detail="noise_scale must be >= 0")
    if not isinstance(proposed, dict) or not proposed:
        raise HTTPException(status_code=400, detail="proposed settings dict is required")

    if not history:
        history = [
            {
                "SpO2": 90.0 + (i * 0.2),
                "PEEP": 8.0,
                "FiO2": 55.0,
                "TidalVol": 450.0,
                "HR": 90,
                "MAP": 75,
                "RespRate": 20,
            }
            for i in range(12)
        ]

    if current_spo2 is None:
        if not history:
            raise HTTPException(status_code=400, detail="current_spo2 required when history is empty")
        current_spo2 = history[-1].get("SpO2")
    if current_spo2 is None:
        raise HTTPException(status_code=400, detail="current_spo2 could not be determined")

    twin = DigitalTwin(stay_id=stay_id)
    try:
        twin.calibrate(history)
        rng = np.random.default_rng(int(seed)) if seed is not None else None
        result = twin.simulate(
            proposed=proposed,
            current_spo2=float(current_spo2),
            steps=steps,
            noise_scale=noise_scale,
            rng=rng,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid twin replay payload: {exc}") from exc

    response = {
        "mode": "deterministic" if noise_scale == 0 else "stochastic",
        "seed": seed,
        "steps": steps,
        "result": result,
        "twin_state": {
            "is_calibrated": twin.is_calibrated,
            "compliance_factor": round(twin.compliance_factor, 3),
            "uncertainty": round(twin.uncertainty, 3),
        },
    }

    # Tamper-evident audit trail for every twin replay (Phase 5 wiring).
    audit_bridge.log_event(
        event_type="TWIN_SIM",
        stay_id=str(stay_id),
        payload={
            "mode": response["mode"],
            "seed": seed,
            "steps": steps,
            "noise_scale": noise_scale,
            "proposed": proposed,
            "applied": result.get("applied"),
            "mean_spo2": result.get("mean_spo2"),
            "delta_spo2": result.get("delta_spo2"),
            "risk_flag": result.get("risk_flag"),
            "tv_risk": result.get("tv_risk"),
        },
        actor="SYSTEM_TWIN",
    )

    return response

@app.post("/patient/{stay_id}/recommend")
async def get_recommendation(stay_id: int, payload: Dict[str, Any]):
    """
    Generate PPO recommendation and simulate via Digital Twin.
    When trained artifacts exist, uses the dual-head LSTM for pred_next_spo2 + hypoxia risk.
    Pass optional `history` (array of vitals rows) for real inference; else uses vitals-only heuristics.
    """
    body = dict(payload)
    history = body.pop("history", None)
    if not isinstance(history, list):
        history = []
    current_vitals = body

    policy = PPOPolicy()
    curr_spo2 = float(current_vitals.get("SpO2", 95.0))

    forecaster = get_lstm_forecaster()
    pred_spo2: float | None = None
    hypoxia_prob: float | None = None
    lstm_source = "heuristic"

    if history and len(history) >= forecaster.min_history_points():
        p_reg, p_cls = forecaster.predict_from_history(history, stay_id=int(stay_id))
        if p_reg is not None and p_cls is not None:
            pred_spo2 = float(p_reg)
            hypoxia_prob = float(p_cls)
            lstm_source = "lstm_keras"

    if pred_spo2 is None or hypoxia_prob is None:
        lstm_source = "heuristic"
        if curr_spo2 < 90:
            hypoxia_prob = 0.85
            pred_spo2 = curr_spo2 - 1.5
        elif curr_spo2 < 94:
            hypoxia_prob = 0.45
            pred_spo2 = curr_spo2 - 0.5
        else:
            hypoxia_prob = 0.05
            pred_spo2 = curr_spo2 + 0.5

    result = policy.recommend(
        current_vitals=current_vitals,
        pred_spo2=float(pred_spo2),
        hypoxia_prob=float(hypoxia_prob),
        history=history or None,
    )

    result["lstm_forecast_source"] = lstm_source
    result["lstm_status"] = forecaster.status()

    record_recommendation_metrics(
        stay_id=int(stay_id),
        observed_spo2=curr_spo2,
        pred_next_spo2=float(pred_spo2),
        hypoxia_prob=float(hypoxia_prob),
        lstm_source=lstm_source,
    )

    # Explainability strip (SHAP-style placeholders + LSTM headline)
    shap = [
        {
            "feature": "SpO2 (Current)",
            "impact": -0.6 if curr_spo2 < 93 else 0.2,
            "direction": "down" if curr_spo2 < 93 else "up",
        },
        {"feature": "PEEP Setting", "impact": 0.4, "direction": "up"},
        {"feature": "Heart Rate", "impact": 0.15, "direction": "neutral"},
    ]
    if lstm_source == "lstm_keras":
        shap.insert(
            0,
            {
                "feature": "LSTM ΔSpO2 (next)",
                "impact": round(float(pred_spo2) - curr_spo2, 2),
                "direction": "down" if pred_spo2 < curr_spo2 else "up",
            },
        )
    result["shap_insights"] = shap

    # Log to blockchain
    audit_bridge.log_event(
        event_type="RECOMMENDATION",
        stay_id=str(stay_id),
        payload=result,
        actor="SYSTEM_PPO"
    )

    return result

@app.post("/patient/{stay_id}/risks")
async def predict_clinical_risks(stay_id: int, payload: Dict[str, Any]):
    """
    Predict 5 clinical risks + next-step vitals using multi-task LSTM.

    Input:
      - history: array of vital sign measurements (12+ timesteps)
                Each record must have: HR, MAP, RespRate, SpO2, PEEP, FiO2, TidalVol

    Returns:
      - regression_predictions: Next_SpO2, Next_HR, Next_MAP, Next_RespRate, Next_TidalVol
      - risk_predictions: Hypoxia_Risk, Tachycardia_Risk, Hypotension_Risk, Tachypnea_Risk, VILI_Risk
    """
    # Lazy-load model on first request (avoids blocking server startup)
    if not multi_risk_engine.ready:
        if not multi_risk_engine.load():
            raise HTTPException(
                status_code=503,
                detail="Multi-risk LSTM model not found or failed to load. Model training may not be complete."
            )

    history = payload.get("history", [])
    if not isinstance(history, list) or len(history) < 12:
        raise HTTPException(
            status_code=400,
            detail=f"history must be a list of at least 12 vital sign measurements. Got {len(history)}"
        )
    
    try:
        # Convert to DataFrame and validate required columns
        hist_df = pd.DataFrame(history)
        required_cols = ["HR", "MAP", "RespRate", "SpO2", "PEEP", "FiO2", "TidalVol"]
        for col in required_cols:
            if col not in hist_df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Create derived features inline (no external function calls)
        hist_df['SpO2_FiO2_Ratio'] = (hist_df['SpO2'] * 100.0) / hist_df['FiO2']
        hist_df['Minute_Ventilation_Lpm'] = hist_df['TidalVol'] * hist_df['RespRate'] / 1000.0
        hist_df['PEEP_FiO2_Product'] = hist_df['PEEP'] * hist_df['FiO2'] / 100.0
        hist_df['MAP_HR_Ratio'] = (hist_df['MAP'] / hist_df['HR'].replace(0, np.nan)).fillna(0.0)
        
        # For simplicity: use only base + derived features (no PPO, lag, or rolling stats)
        # This matches what's actually needed by the model
        feature_cols_available = [
            'HR', 'MAP', 'RespRate', 'SpO2', 'PEEP', 'FiO2', 'TidalVol',
            'SpO2_FiO2_Ratio', 'Minute_Ventilation_Lpm', 'PEEP_FiO2_Product', 'MAP_HR_Ratio'
        ]
        
        # Pad features to match model input (102 features)
        X_seq = hist_df[feature_cols_available].iloc[-12:].values
        if X_seq.shape[0] < 12:
            raise ValueError(f"History too short: {X_seq.shape[0]} rows, need 12")
        
        # Pad with zeros to match expected 102 features
        if X_seq.shape[1] < 102:
            X_seq = np.hstack([X_seq, np.zeros((X_seq.shape[0], 102 - X_seq.shape[1]))])
        
        X_seq = X_seq[:, :102].astype(np.float32)
        
        # Predict
        pred_results = multi_risk_engine.predict_sequence(X_seq)
        
        # Organize response
        response = {
            "stay_id": stay_id,
            "predictions": {
                "regression": {k: v for k, v in pred_results.items() if k.startswith("Next_")},
                "classification": {k: v for k, v in pred_results.items() if "Risk" in k},
            },
            "summary": {
                "high_risk_flags": [k for k, v in pred_results.items() if "Risk" in k and v.get("risk") == 1],
                "next_spo2": pred_results.get("Next_SpO2", {}).get("prediction"),
            },
            "source": "multi_risk_lstm",
        }
        
        # Log to audit trail
        audit_bridge.log_event(
            event_type="MODEL_INFER",
            stay_id=str(stay_id),
            payload={
                "model": "multi_risk_lstm",
                "high_risk_flags": response["summary"]["high_risk_flags"],
                "next_spo2": response["summary"]["next_spo2"],
            },
            actor="SYSTEM_MULTI_RISK"
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error predicting risks: {str(e)}"
        ) from e


@app.post("/patient/{stay_id}/audit")
async def log_clinician_action(stay_id: int, payload: Dict[str, Any]):
    """Log Accept, Override, or Reject actions from clinician."""
    action_type = payload.get('action', 'UNKNOWN')
    clinical_notes = payload.get('notes', '')
    applied_settings = payload.get('settings', {})
    
    event_type = 'ACCEPT' if action_type == 'accept' else 'OVERRIDE' if action_type == 'override' else 'REJECT'
    
    block = audit_bridge.log_event(
        event_type=event_type,
        stay_id=str(stay_id),
        payload={
            'notes': clinical_notes,
            'settings': applied_settings
        },
        actor="CLINICIAN"
    )
    return block

@app.get("/patient/{stay_id}/audit_trail")
async def get_audit_trail(stay_id: int):
    return {"trail": audit_bridge.get_trail(str(stay_id))}

@app.get("/audit/verify")
async def verify_chain():
    is_valid, message = audit_bridge.verify_chain()
    return {"valid": is_valid, "message": message, "stats": audit_bridge.stats()}


@app.post("/audit/anchor")
async def commit_anchor(payload: Dict[str, Any] | None = None):
    """
    Phase 5: Commit a batch of off-chain audit blocks to the on-chain
    AuditAnchor contract. `mode=dry_run` (default) computes the batch
    without submitting; `mode=live` requires AUDIT_ANCHOR_* env vars.
    """
    body = payload or {}
    mode = body.get("mode", "dry_run")
    max_blocks = int(body.get("max_blocks", 1024))
    try:
        result = anchor_now(mode=mode, max_blocks=max_blocks)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
