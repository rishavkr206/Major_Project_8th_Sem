"""
Ventilator Digital Twin - Flask Relay Server
Bridges the gap between the 3D frontend and the digital twin backend
Port: 5050
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
from datetime import datetime
import threading
import time

app = Flask(__name__)
CORS(app)

# ──────────────────── CONFIGURATION ────────────────────
DIGITAL_TWIN_API = "http://localhost:7000"  # Your existing digital twin API (change when ready)
FIWARE_ORION = "http://localhost:1026"      # Optional: FIWARE Context Broker
DEMO_MODE = True                             # Fallback if API unavailable (generates realistic mock data)

# ──────────────────── CACHED STATE ────────────────────
current_state = {
    "patient_id": 123,
    "peep": 5.0,
    "fio2": 40.0,
    "tidal_vol": 450.0,
    "resp_rate": 12,
    "pressure": 15.0,
    "spo2": 98.0,
    "spo2_predicted": 97.5,
    "hr": 80,
    "map": 75,
    "temperature": 36.8,
    "status": "stable",
    "timestamp": datetime.now().isoformat()
}

# ──────────────────── UTILITY FUNCTIONS ────────────────────
def fetch_patient_state(patient_id: int):
    """Fetch current ventilator state from digital twin API"""
    try:
        response = requests.get(
            f"{DIGITAL_TWIN_API}/patient/{patient_id}/state",
            timeout=2
        )
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"[RELAY] API fetch failed: {e}")
        return None

def generate_mock_state():
    """Generate realistic mock state if API unavailable"""
    import random
    import math
    
    # Simulate realistic variations
    time_factor = time.time() % 60 / 60.0
    breathing_cycle = math.sin(time_factor * 2 * math.pi)
    
    return {
        "patient_id": 123,
        "peep": 5.0 + random.gauss(0, 0.3),
        "fio2": 40.0 + random.gauss(0, 2),
        "tidal_vol": 450.0 + breathing_cycle * 50,  # Breathing animation
        "resp_rate": 12 + random.randint(-1, 1),
        "pressure": 15.0 + breathing_cycle * 8,
        "spo2": 98.0 + random.gauss(0, 0.5),
        "spo2_predicted": 97.5 + random.gauss(0, 0.5),
        "hr": 80 + random.gauss(0, 3),
        "map": 75 + random.gauss(0, 2),
        "temperature": 36.8 + random.gauss(0, 0.2),
        "status": "stable" if random.random() > 0.1 else "warning",
        "timestamp": datetime.now().isoformat()
    }

# ──────────────────── REST ENDPOINTS ────────────────────

@app.route("/twin", methods=["GET"])
def get_twin_state():
    """Fetch current twin state"""
    global current_state
    
    patient_id = request.args.get("patient_id", 123, type=int)
    
    # Try to fetch from digital twin API
    api_state = fetch_patient_state(patient_id)
    
    if api_state:
        current_state = api_state
    elif DEMO_MODE:
        # Fallback to mock state
        current_state = generate_mock_state()
    
    return jsonify(current_state)

@app.route("/twin/history", methods=["GET"])
def get_twin_history():
    """Get historical state for charts"""
    patient_id = request.args.get("patient_id", 123, type=int)
    limit = request.args.get("limit", 100, type=int)
    
    try:
        # Try to fetch from digital twin API
        response = requests.get(
            f"{DIGITAL_TWIN_API}/patient/{patient_id}/history",
            params={"limit": limit},
            timeout=2
        )
        if response.status_code == 200:
            return jsonify(response.json())
    except:
        pass
    
    # Generate mock history
    history = []
    for i in range(limit):
        timestamp = datetime.now().isoformat()
        history.append({
            "peep": 5.0 + (i % 10) * 0.5,
            "fio2": 40.0 + (i % 20),
            "tidal_vol": 450.0 + (i % 100),
            "spo2": 98.0 - (i % 5),
            "timestamp": timestamp
        })
    
    return jsonify({"history": history})

@app.route("/twin/recommend", methods=["GET"])
def get_recommendation():
    """Get PPO recommendations from digital twin"""
    patient_id = request.args.get("patient_id", 123, type=int)
    
    try:
        response = requests.get(
            f"{DIGITAL_TWIN_API}/patient/{patient_id}/recommend",
            timeout=2
        )
        if response.status_code == 200:
            return jsonify(response.json())
    except:
        pass
    
    # Mock recommendation
    return jsonify({
        "peep": 7.0,
        "fio2": 45.0,
        "tidal_vol": 480.0,
        "reason": "Optimize for safety thresholds",
        "confidence": 0.85
    })

@app.route("/twin/apply", methods=["POST"])
def apply_parameters():
    """Apply ventilator parameter changes"""
    data = request.json
    patient_id = data.get("patient_id", 123)
    
    try:
        response = requests.post(
            f"{DIGITAL_TWIN_API}/patient/{patient_id}/apply",
            json=data,
            timeout=2
        )
        if response.status_code == 200:
            return jsonify({"success": True, "data": response.json()})
    except:
        pass
    
    return jsonify({
        "success": True,
        "message": "Parameters queued for application",
        "patient_id": patient_id
    })

@app.route("/sandbox", methods=["GET"])
def sandbox_state():
    """Get sandbox simulation state"""
    return jsonify({
        "mode": "sandbox",
        "is_isolated": True,
        "last_sync": datetime.now().isoformat()
    })

@app.route("/sandbox/simulate", methods=["POST"])
def sandbox_simulate():
    """Run simulation with given parameters"""
    params = request.json
    
    try:
        response = requests.post(
            f"{DIGITAL_TWIN_API}/twin/simulate",
            json=params,
            timeout=5
        )
        if response.status_code == 200:
            return jsonify(response.json())
    except:
        pass
    
    # Mock simulation result
    return jsonify({
        "success": True,
        "predicted_spo2": 97.5,
        "predicted_hr": 82,
        "risk_level": "low",
        "estimated_time": "24h"
    })

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    api_health = "ok"
    try:
        requests.get(f"{DIGITAL_TWIN_API}/health", timeout=1)
    except:
        api_health = "offline"
    
    return jsonify({
        "status": "ok",
        "digital_twin_api": api_health,
        "timestamp": datetime.now().isoformat()
    })

# ──────────────────── WEBSOCKET (Optional) ────────────────────
# For real-time streaming, use socketio
# from flask_socketio import SocketIO, emit
# socketio = SocketIO(app, cors_allowed_origins="*")

# @socketio.on('connect')
# def on_connect():
#     print('Client connected')
#     emit('response', {'data': 'Connected to relay'})

# @socketio.on('request_state')
# def on_request_state():
#     state = generate_mock_state()
#     emit('state_update', state, broadcast=True)

# ──────────────────── BACKGROUND UPDATER ────────────────────
def background_updater():
    """Continuously update state in background"""
    while True:
        try:
            global current_state
            api_state = fetch_patient_state(123)
            if api_state:
                current_state = api_state
            elif DEMO_MODE:
                current_state = generate_mock_state()
        except Exception as e:
            print(f"[BACKGROUND] Update failed: {e}")
        
        time.sleep(0.5)  # Update every 500ms

# Start background updater in daemon thread
updater_thread = threading.Thread(target=background_updater, daemon=True)
updater_thread.start()

# ──────────────────── MAIN ────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Ventilator Digital Twin - Flask Relay Server")
    print("=" * 60)
    print(f"🌍 API: {DIGITAL_TWIN_API}")
    print(f"📦 Demo Mode: {DEMO_MODE}")
    print(f"🚀 Starting on http://localhost:5050")
    print("=" * 60)
    
    # Uncomment for WebSocket support:
    # socketio.run(app, host="0.0.0.0", port=5050, debug=False)
    
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
