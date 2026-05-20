# Ventilator 3D Twin - Quick Start Guide

## 🎯 What You Have

A professional Handloom-style architecture with:
- ✅ **3D Dashboard** - Real-time ventilator visualization
- ✅ **Flask Relay API** - Bridges your digital twin to frontend
- ✅ **Sandbox Simulation** - Isolated parameter testing
- ✅ **Safety Monitoring** - Threshold-based alerts
- ✅ **Modular Architecture** - Easy to extend

---

## 🚀 Run It In 3 Steps

### Step 1: Start Flask Relay (Port 5050)
```bash
cd ventilator-twin/Fiware/backend
pip install flask flask-cors requests
python relay.py
```

✅ You should see:
```
============================================================
Ventilator Digital Twin - Flask Relay Server
============================================================
🌍 API: http://localhost:8000
📦 Demo Mode: True
🚀 Starting on http://localhost:5050
============================================================
```

### Step 2: Start Dashboard (Port 8000)
```bash
cd ventilator-twin/Fiware/frontend
python -m http.server 8000
```

✅ Open in browser: **http://localhost:8000/index.html**

You'll see:
- 3D ventilator model in center
- Real-time parameters on left
- Control buttons on right
- SpO₂ chart on bottom-left
- Alerts on bottom-right

### Step 3 (Optional): Start Sandbox (Port 8080)
```bash
cd ventilator-twin/sandbox
python -m http.server 8080
```

✅ Open: **http://localhost:8080/index.html**

Isolated simulation with sliders and terminal console.

---

## ✨ Live Data Integration

Your system is currently in **DEMO MODE** (generates mock data).

To connect to your **actual digital twin**, edit `Fiware/backend/relay.py`:

```python
# Line ~10: Change this
DIGITAL_TWIN_API = "http://localhost:8000"

# Make sure your API returns data in this format:
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

That's it! The 3D model will update in real-time.

---

## 🎮 Dashboard Controls

| Element | Interaction |
|---------|-------------|
| 3D Model | Drag to rotate, Scroll to zoom |
| Knobs | Rotate based on parameter values |
| Screen | Changes color (green→orange→red) based on risk |
| Water Level | Animates with breathing cycle |
| Status Light | Blinks to show system status |

---

## 🧪 Sandbox Commands

Type these in the terminal console at bottom:

```
status              # Show current parameters
reset               # Reset to defaults
optimize safety     # Apply safety optimization
optimize oxygenation # Apply O₂ focus
sync                # Sync with live system
help                # Show all commands
```

---

## 📊 Safety Color Coding

| Color | Status | Parameters |
|-------|--------|------------|
| 🟦 Blue | Normal | All within safe ranges |
| 🟨 Yellow | Caution | Some parameters elevated |
| 🟧 Orange | Warning | High risk detected |
| 🟥 Red | Critical | Emergency parameters |

---

## 🔗 Architecture Summary

```
Your Digital Twin API (port 8000)
         ↓
   Flask Relay (port 5050)
         ↓
  3D Dashboard (port 8000) ← You open this!
         ↓
   Three.js WebGL Visualization
         ↓
   Real-time Parameter Updates
```

---

## 🐛 Health Check

Test each component:

```bash
# Check relay is running
curl http://localhost:5050/health

# Check it can reach your API
curl http://localhost:5050/twin

# Check dashboard loads
curl http://localhost:8000/index.html
```

---

## 📂 File Locations

| Component | Location | Purpose |
|-----------|----------|---------|
| **Flask Backend** | `ventilator-twin/Fiware/backend/relay.py` | Fetches & serves data |
| **Dashboard** | `ventilator-twin/Fiware/frontend/index.html` | 3D visualization |
| **Sandbox** | `ventilator-twin/sandbox/index.html` | Isolated simulation |
| **State Mgmt** | `ventilator-twin/sandbox/core/SandboxState.js` | Data store |
| **Validation** | `ventilator-twin/sandbox/core/ParameterEngine.js` | Safety checks |
| **Events** | `ventilator-twin/sandbox/core/EventBus.js` | Pub/Sub system |

---

## 🎯 Next Steps

1. **Test with demo data** (current state)
2. **Connect to your API** (edit relay.py)
3. **Add PPO recommendations** (modify `/twin/recommend` endpoint)
4. **Integrate blockchain** (log parameter changes)
5. **Deploy with Docker** (use docker-compose.yml)

---

## ⚡ Quick Customization

### Change 3D model color:
Edit `Fiware/frontend/index.html` line ~190:
```javascript
color: 0x1e293b,  // ← Change to: 0xff0000 (red), 0x00ff00 (green), etc.
```

### Change safety thresholds:
Edit `sandbox/core/ParameterEngine.js` line ~30:
```javascript
peep_high: 15,      // ← Change warning threshold
peep_critical: 20,  // ← Change critical threshold
```

### Change update frequency:
Edit `Fiware/frontend/index.html` line ~450:
```javascript
setInterval(fetchState, 500);  // ← 500ms, change as needed
```

---

## 📱 Browser Compatibility

| Browser | Status |
|---------|--------|
| Chrome/Chromium | ✅ Fully supported |
| Firefox | ✅ Fully supported |
| Safari | ✅ Fully supported |
| Edge | ✅ Fully supported |
| IE 11 | ❌ Not supported |

---

## 🚨 Common Issues

**"Cannot connect to API"**
- Make sure Flask relay is running on port 5050
- Check: `curl http://localhost:5050/health`

**"3D model not showing"**
- Check browser console (F12)
- WebGL might be disabled
- Try a different browser

**"No data updates"**
- Dashboard polls every 500ms
- Check relay is getting data from your API
- Look at browser console Network tab

**"Sandbox mode not working"**
- Make sure JavaScript is enabled
- Check: http://localhost:8080/index.html loads

---

## 📚 Full Documentation

- `README.md` - Complete guide
- `ARCHITECTURE.md` - Technical deep dive (coming soon)
- `API.md` - Endpoint reference (coming soon)

---

## 🎓 For Your Presentation

**Show this flow:**
1. Open Dashboard
2. Show 3D model updating with live data
3. Open Sandbox and adjust parameters
4. Show alerts triggering at thresholds
5. Demonstrate color-coded risk visualization
6. Show sync with live system
7. Explain isolation/safety of sandbox

**Key talking points:**
- "Handloom-inspired modular architecture"
- "Real-time Three.js visualization"
- "Safety-first parameter validation"
- "Isolated sandbox for testing PPO recommendations"
- "Seamless integration with existing digital twin"

---

**You're ready to go! 🚀 Start with Step 1 above.**

Questions? Check README.md or Troubleshooting section.
