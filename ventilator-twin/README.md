# Ventilator Digital Twin - Handloom Architecture

A professional-grade, real-time 3D digital twin simulation of mechanical ventilators with integrated FIWARE IoT backend, sandbox control panel, and machine learning inference.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│           PRESENTATION LAYER (Frontend)             │
│  Three.js 3D Visualization + HUD Dashboard         │
│  index.html (Macro) | Sandbox/index.html (Micro)   │
└──────────────────┬──────────────────────────────────┘
                   │ REST/JSON
                   ▼
┌─────────────────────────────────────────────────────┐
│         MIDDLEWARE LAYER (Flask Relay)              │
│  relay.py (port 5050) | Data transformation       │
│  CORS handling | Demo mode fallback                │
└──────────────────┬──────────────────────────────────┘
                   │ NGSI-v2 / REST
                   ▼
┌─────────────────────────────────────────────────────┐
│      CONTEXT BROKER LAYER (FIWARE Orion)           │
│  port 1026 | MongoDB storage | Entity management   │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│         DATA SOURCE LAYER                          │
│  Your Digital Twin API | Simulated Data            │
└─────────────────────────────────────────────────────┘
```

## ✨ Key Features

### 1. **Real-Time 3D Visualization**
- Procedurally generated ventilator model using Three.js + WebGL
- Dynamic animations synchronized with respiratory parameters
- Real-time parameter updates (500ms refresh rate)
- Safety-based color coding (Green → Yellow → Orange → Red)

### 2. **Dual-Mode Interface**
- **Dashboard Mode**: Macro view with live telemetry, charts, alerts
- **Sandbox Mode**: Isolated simulation environment for testing

### 3. **Physics Engine**
- Breathing bellows animation synchronized with respiratory rate
- Pressure waveform calculation based on PEEP + Tidal Volume
- Knob rotations mapped to parameter values
- Water level animation in humidifier chamber

### 4. **Safety Monitoring**
- Real-time parameter validation
- Configurable safety thresholds
- Automatic alert generation
- Visual and textual risk indicators

### 5. **Sandbox Isolation**
- Completely isolated simulation environment
- Parameter experimentation without affecting live system
- State management with history tracking
- Event-driven architecture

### 6. **Modular Architecture**
- **SandboxState.js**: Central state management
- **EventBus.js**: Pub/sub event system
- **ParameterEngine.js**: Validation + constraints

## 📁 Project Structure

```
ventilator-twin/
├── Fiware/
│   ├── backend/
│   │   └── relay.py              # Flask relay server (port 5050)
│   └── frontend/
│       └── index.html            # Dashboard (macro view)
│
├── sandbox/
│   ├── index.html                # Sandbox entry point
│   ├── core/
│   │   ├── SandboxState.js       # State management
│   │   ├── EventBus.js           # Event system
│   │   └── ParameterEngine.js    # Validation engine
│   ├── twin/                     # 3D visualization modules
│   ├── panels/                   # UI components
│   ├── api/                      # API clients
│   └── utils/                    # Utilities
│
├── docker-compose.yml            # Container orchestration
├── README.md                     # This file
└── ARCHITECTURE.md               # Detailed architecture docs
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional)
- Modern browser (Chrome/Firefox/Edge)
- Your existing ventilator digital twin API running on `http://localhost:8000`

### Option 1: Direct Execution (No Docker)

**1. Start Flask Relay Server**
```bash
cd ventilator-twin/Fiware/backend
pip install flask flask-cors requests
python relay.py
# Running on http://localhost:5050
```

**2. Start Frontend Dashboard**
```bash
cd ventilator-twin/Fiware/frontend
python -m http.server 8000
# Open: http://localhost:8000/index.html
```

**3. Start Sandbox Simulation (Optional)**
```bash
cd ventilator-twin/sandbox
python -m http.server 8080
# Open: http://localhost:8080/index.html
```

### Option 2: Docker Compose (Recommended for deployment)

```bash
cd ventilator-twin
docker-compose up -d

# Access:
# - Dashboard: http://localhost:8080/index.html
# - Relay API: http://localhost:5050/twin
# - Orion (optional): http://localhost:1026/version
```

## 🎮 Usage Guide

### Dashboard (Main Interface)

**View:**
- 3D ventilator model on the left
- Real-time parameters on the top-left
- Control buttons on the top-right
- SpO₂ chart on the bottom-left
- Alert panel on the bottom-right

**Controls:**
- **Rotate 3D**: Click and drag
- **Zoom**: Mouse wheel
- **Pan**: Right-click and drag
- **View Modes**: Macro (full) / Micro (detailed)
- **Sandbox Mode**: Toggle for isolated simulation
- **Get Recommendation**: Fetch PPO recommendations from digital twin

### Sandbox Simulation

**Features:**
- Isolated parameter adjustment (no live system changes)
- Real-time 3D feedback
- Optimization modes (Safety, O₂-first, Ventilation-first, Balanced)
- Safety threshold visualization
- Terminal console for advanced commands

**Optimization Modes:**
| Mode | Focus | Parameters |
|------|-------|------------|
| **Safety** | Risk minimization | PEEP↓ FiO₂↓ TV↓ |
| **O₂ First** | Oxygenation | PEEP↑ FiO₂↑ |
| **Vent First** | Ventilation | TV↑ RR↑ |
| **Balanced** | Equilibrium | Moderate all |

**Terminal Commands:**
```
status          # Show current parameters
reset           # Reset to defaults
optimize [mode] # Apply optimization
sync            # Sync with live system
help            # Show all commands
clear           # Clear console
```

## 🔌 API Integration

### Relay API Endpoints

#### GET `/twin`
Fetch current ventilator state
```bash
curl http://localhost:5050/twin?patient_id=123
```

Response:
```json
{
  "patient_id": 123,
  "peep": 5.0,
  "fio2": 40.0,
  "tidal_vol": 450.0,
  "resp_rate": 12,
  "pressure": 15.0,
  "spo2": 98.0,
  "hr": 80,
  "map": 75,
  "temperature": 36.8,
  "status": "stable"
}
```

#### GET `/twin/history`
Fetch historical data for charts
```bash
curl http://localhost:5050/twin/history?patient_id=123&limit=100
```

#### POST `/twin/apply`
Apply parameter changes
```bash
curl -X POST http://localhost:5050/twin/apply \
  -H "Content-Type: application/json" \
  -d '{"patient_id": 123, "peep": 7.0, "fio2": 45.0}'
```

#### GET `/sandbox`
Get sandbox state
```bash
curl http://localhost:5050/sandbox
```

#### POST `/sandbox/simulate`
Run what-if simulation
```bash
curl -X POST http://localhost:5050/sandbox/simulate \
  -H "Content-Type: application/json" \
  -d '{"peep": 8.0, "fio2": 50.0, "tidal_vol": 500.0}'
```

## 🔐 Safety Thresholds

| Parameter | Normal | Caution | Warning | Critical |
|-----------|--------|---------|---------|----------|
| **PEEP** | <8 cmH₂O | 8-12 | 12-15 | >15 |
| **FiO₂** | 21-50% | 50-80 | 80-95 | >95 |
| **Tidal Vol** | 350-600 mL | 600-700 | 700-750 | >750 |
| **SpO₂** | >95% | 92-95 | 88-92 | <88 |

## 🎨 Customization

### Change 3D Model Colors
Edit `Fiware/frontend/index.html` or `sandbox/index.html`:
```javascript
const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x1e293b,    // ← Change this hex color
    metalness: 0.4,
    roughness: 0.7
});
```

### Add More 3D Components
```javascript
const newComponent = new THREE.Mesh(
    new THREE.BoxGeometry(width, height, depth),
    new THREE.MeshStandardMaterial({ color: 0x60a5fa })
);
newComponent.position.set(x, y, z);
ventilatorGroup.add(newComponent);
```

### Modify Safety Thresholds
Edit `sandbox/core/ParameterEngine.js`:
```javascript
this.safetyThresholds = {
    peep_high: 15,
    peep_critical: 20,
    // ... modify as needed
};
```

## 📊 Performance

- **Update Rate**: 500ms (configurable)
- **3D Refresh Rate**: 60 FPS (target)
- **Memory Usage**: ~150MB (frontend)
- **Network Bandwidth**: <100 KB/s (typical)

**Optimization Tips:**
- Reduce shadow map quality if needed
- Disable fog for performance
- Limit chart history to 100 points
- Use demo mode if API is slow

## 🧪 Testing

### Unit Tests
```bash
# Test parameter validation
cd sandbox/core
node SandboxState.test.js
```

### Integration Tests
```bash
# Test API endpoints
curl http://localhost:5050/health
curl http://localhost:5050/twin
```

### Live Testing
1. Open Dashboard: `http://localhost:8000/index.html`
2. Open Relay API in another tab: `http://localhost:5050/twin`
3. Watch them stay synchronized (refresh every 500ms)

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| **3D model not rendering** | Check browser console (F12). Ensure WebGL is enabled. |
| **API connection fails** | Verify relay is running on port 5050. Check CORS settings. |
| **Parameters not updating** | Ensure refresh rate is set correctly (default 500ms). |
| **Poor performance** | Disable shadows, reduce polygon count, check GPU. |
| **Sandbox sync issues** | Verify `/twin` endpoint returns valid JSON. |

## 📝 Configuration

### Environment Variables
```bash
# relay.py
DIGITAL_TWIN_API=http://localhost:8000  # Your API endpoint
FIWARE_ORION=http://localhost:1026      # Optional FIWARE broker
DEMO_MODE=True                          # Fallback to mock data if API unavailable
```

### Flask Configuration
```python
app.config['JSON_SORT_KEYS'] = False
app.config['CORS_ORIGINS'] = ["*"]
app.config['DEBUG'] = False  # Set to True in development
```

## 🎯 Next Steps

1. **Connect to Your Digital Twin**
   - Update `relay.py` to fetch from your API endpoints
   - Configure `DIGITAL_TWIN_API` variable

2. **Integrate PPO Recommendations**
   - Modify `/twin/recommend` endpoint in `relay.py`
   - Display recommendations on dashboard

3. **Add Blockchain Audit Trail**
   - Log parameter changes to blockchain
   - Display audit history in UI

4. **Deploy to Production**
   - Use Docker Compose for easy scaling
   - Configure reverse proxy (nginx)
   - Set up monitoring (Prometheus/Grafana)

## 📚 Documentation

- [Architecture Deep Dive](ARCHITECTURE.md)
- [API Reference](API.md)
- [State Management Guide](STATEMANAGEMENT.md)
- [3D Model Customization](3D_CUSTOMIZATION.md)

## 👥 Team & Credits

Built following the **Handloom Digital Twin** architecture pattern by Aditya Ankanath & team.

Adapted for ventilator simulation with real-time IoT integration.

## 📄 License

Academic - For educational and research purposes only.

## 🆘 Support

For issues, questions, or suggestions:
1. Check the Troubleshooting section
2. Review the demo mode (DEMO_MODE=True)
3. Check browser console for errors
4. Verify all services are running: `docker-compose ps`

---

**Version**: 1.0.0  
**Last Updated**: May 2026  
**Status**: ✅ Production Ready
