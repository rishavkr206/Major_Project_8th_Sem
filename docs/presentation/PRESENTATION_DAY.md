# 🎓 Presentation Day Cheatsheet

**Project:** Blockchain-Enabled Digital Twin Framework for Ventilator Optimization
**Audience:** Faculty / external examiner
**Total time:** ~15 min talk + ~5 min demo + ~10 min Q&A
**Read-time of this doc:** 5 min — keep this open in a second monitor.

---

## 🧭 0. Before You Walk In (T - 30 minutes)

Run this **once**, the day-of, in a quiet PowerShell window. If everything
prints OK, your laptop is presentation-ready.

```powershell
# 1. Open a PowerShell terminal at the project root
cd "C:\Users\risha\Downloads\Major Project\Major Project"

# 2. Activate the Python virtual environment
.\.venv311\Scripts\Activate.ps1
# (if that fails because of execution policy, run once:)
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# 3. Verify Python is the venv's Python
python -c "import sys; print(sys.executable)"
# Expect: ...\Major Project\.venv311\Scripts\python.exe

# 4. Verify all critical artifacts exist
Get-Item ml\models\lstm_model.keras
Get-Item ml\multi_risk\multi_risk_lstm.keras
Get-Item ml\simulated_phase1\scaler.pkl
# (audit_ledger.db is auto-created on first event — don't worry if missing)

# 5. Run the full test suite — must end with "OK"
python -m unittest discover -s tests -p "test_*.py"
# Expect: Ran 39 tests in <1s ... OK

# 6. Smoke-test the PPO env (no GPU, no SB3 needed)
python ml\ppo_training.py --smoke
# Expect: JSON with "smoke": true, "n_actions_executed": 48
```

If **any** step above fails, jump to **§ 8 Recovery Cheatsheet** at the
bottom of this doc.

---

## 🎤 1. Presentation Flow (slide-by-slide commands)

### Slide 1–3: Problem & Motivation (no commands)
> Talk through the slide deck in `docs/presentation/slides_notes.md`.
> No terminal needed.

### Slide 4: Architecture overview (no commands)
> Open `docs/diagrams/system-architecture.md` in a markdown preview if
> the examiner wants to see the architecture diagram.

### Slide 5: Data foundation (Phase 1) — show the simulator

```powershell
# Quick proof the simulator generates clinically valid records
python -c "from services.data_simulator import SimulationConfig, VentilatorDataSimulator; s = VentilatorDataSimulator(SimulationConfig(profile='ards', seed=42)); rec = s.next_record(stay_id=900001); print(rec)"
```

### Slide 6: Digital Twin (Phase 2) — deterministic replay

```powershell
# Standalone twin demo (prints a 4-step simulation under proposed PEEP/FiO2)
python -m services.digital_twin
```

### Slide 7: LSTM Forecasting (Phase 3)

```powershell
# Show the model is loaded and report its input shape
python -c "from services.lstm_inference import get_lstm_forecaster; import json; print(json.dumps(get_lstm_forecaster().status(), indent=2))"
```

### Slide 8: PPO Optimization Agent (Phase 4)

```powershell
# Show the rule-layer recommendation (Layer A, always live)
python -m services.ppo_policy

# Show the SB3 trainer's smoke path (Layer B verification)
python ml\ppo_training.py --smoke
```

### Slide 9: Blockchain Audit (Phase 5)

```powershell
# Demonstrate the off-chain hash chain
python -m services.audit_bridge

# Show what an on-chain anchor batch would look like (no blockchain needed)
python -m services.chain_anchor --mode dry_run
```

### Slide 10: Live Dashboard Demo

> 👉 Switch to **§ 2 Live Demo** (next section).

### Slide 11: Results

> Open these three files in a markdown viewer and walk through them:
>
> - `reports/benchmark-results.md`  (KPI table vs baselines)
> - `reports/ablation-study.md`     (component contribution)
> - `reports/model-evaluation-lstm.md` & `model-evaluation-ppo.md`

### Slide 12: Closing

> "Three independent guarantees — accuracy from the LSTM, safety from
> the Digital Twin, forensic integrity from the audit chain. The ablation
> study proves none of them is redundant."

---

## 🖥️ 2. Live Demo — Exact Commands (run in this order)

### Step 1. Start the API server (Terminal 1)

```powershell
cd "C:\Users\risha\Downloads\Major Project\Major Project"
.\.venv311\Scripts\Activate.ps1

# Point at the simulated_phase1 artifacts so LSTM loads
$env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"

# Start the API — leave this terminal running
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Wait for:** `Application startup complete.` (can take ~30s on cold start
because it loads the patient CSV index).

### Step 2. Confirm the API is healthy (Terminal 2)

```powershell
# In a *new* PowerShell window
cd "C:\Users\risha\Downloads\Major Project\Major Project"

# Hit /health — should show lstm.model_loaded = true
curl http://127.0.0.1:8000/health
```

### Step 3. Open the dashboard

```powershell
# Easiest: open the static file directly in Edge/Chrome
Start-Process .\frontend\dashboard\index.html

# If browser blocks file:// — serve it instead (Terminal 3)
cd .\frontend\dashboard
python -m http.server 8080
# then open http://127.0.0.1:8080
```

### Step 4. Scenario 1 — Predictive Save (4 min)

**Click sequence in the dashboard:**
1. Pick **Patient 30004018** from the dropdown
2. Wait 5s for the SpO₂ trend to render
3. Click **Get Recommendation**
4. Show: `alert_level`, `pred_next_spo2`, `hypoxia_prob`, twin trajectory
5. Click **Accept**
6. Open the **Audit Trail** panel → show `prev_hash` linking blocks

**Talking points (memorize):**
> "The LSTM saw the SpO₂ decline 3 hours early — MAE of 1.5% on the
> test set. The Digital Twin verified the proposed PEEP+FiO2 bump
> wouldn't crash the patient. Every event is one block in a SHA-256
> hash chain — you can see `prev_hash` here links back to the previous
> event."

### Step 5. Scenario 2 — Tamper Detection (3 min)

```powershell
# In Terminal 2 — first stop the API in Terminal 1 with Ctrl+C
# Then tamper with the SQLite ledger:
python -c "import sqlite3; c = sqlite3.connect('blockchain/audit_ledger.db'); c.execute(\"UPDATE audit_chain SET payload_json = '{\\\"tampered\\\":true}' WHERE block_id = 1\"); c.commit(); print('TAMPERED block 1')"

# Restart the API (back in Terminal 1)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**In the dashboard:**
- Click **Verify Chain** button
- Show: `valid: false` with the offending `block_id` named

**Talking points:**
> "Even a one-byte edit to a single payload makes the entire downstream
> chain invalid because every `chain_hash = SHA256(prev_hash ‖
> payload_hash ‖ timestamp)`. Phase 5's on-chain anchor extends this
> guarantee outside our institution — anyone can verify the chain's
> integrity from the public blockchain."

```powershell
# Restore the ledger after the demo (Terminal 2)
Remove-Item blockchain\audit_ledger.db*
# (next API event will auto-create a fresh ledger)
```

### Step 6. Scenario 3 — Failure-Mode Resilience (3 min)

```powershell
# Move the LSTM aside (simulate model failure)
Move-Item ml\models\lstm_model.keras ml\models\lstm_model.keras.bak

# Restart API in Terminal 1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**In the dashboard:**
- Click **Get Recommendation** for the same patient
- Show response field `lstm_forecast_source = "heuristic"`
- Point at lower **confidence** value
- Twin still simulates → safety preserved

**Talking points:**
> "We never single-point-of-fail on the clinician's view. If the LSTM is
> down, we degrade to a heuristic — but the response *flags* this so
> any downstream analysis can filter heuristic-mode events out of
> performance metrics."

```powershell
# Restore the LSTM
Move-Item ml\models\lstm_model.keras.bak ml\models\lstm_model.keras
```

### Step 7. Anchor demo (optional, 1 min)

```powershell
# Show the dry-run anchor output — what would be posted on-chain
curl -X POST -H "Content-Type: application/json" -d '{\"mode\":\"dry_run\"}' http://127.0.0.1:8000/audit/anchor
```

---

## 📊 3. Faculty Q&A — Likely Questions & Pre-Built Commands

### Q: "How accurate is your LSTM?"
```powershell
# Show the saved evaluation JSON
type reports\model_evaluation_lstm.json
```
> "MAE 1.53% on next-step SpO₂. AUROC 0.873 on 3-hour-ahead hypoxia
> prediction. End-to-end inference p95 is 73 ms against a 2-second SLA.
> Full breakdown in `reports/model-evaluation-lstm.md`."

### Q: "How do you know the system is safe?"
```powershell
# Show the safety test suite passing
python -m unittest tests.test_digital_twin_safety -v
```
> "Every recommendation is clamped to hard ICU bounds before it reaches
> the dashboard. The Digital Twin then simulates the proposed action
> and sets a `risk_flag` if it predicts ongoing hypoxia. The clamp +
> simulation is regression-tested — see `tests/test_digital_twin_safety.py`."

### Q: "What if the blockchain is unavailable?"
> "Phase 5 has two layers. The off-chain SHA-256 hash chain in SQLite is
> always live and tamper-evident on its own. The Solidity contract
> `AuditAnchor.sol` adds **external verifiability** by anchoring the
> chain tip on-chain in batches. If the chain is offline, we keep
> batching in `dry_run` mode and post the backlog when the chain
> comes back — no off-chain data is ever lost."

### Q: "Did you really train a PPO agent?"
```powershell
python ml\ppo_training.py --smoke
```
> "The trainer is `ml/ppo_training.py`. The environment wraps the
> Phase-2 Digital Twin in a Gymnasium interface with a 9-action
> discrete space — clinician-style adjustments only, never raw motor
> control. We use SB3 PPO with `MlpPolicy [128, 128]`. The
> rule-based Layer A is always the safety net underneath."

### Q: "Can I see the Solidity contract pass its tests?"
```powershell
cd blockchain
npm install   # one-time, ~2 min
npx hardhat test
```
> "Six contract tests — covers happy path, non-contiguous range,
> empty hash rejection, non-writer rejection, verify(), and ownership
> rotation immutability. Same suite runs in CI."

### Q: "What's the contribution of each component?"
```powershell
type reports\ablation-study.md | Select-Object -First 60
```
> "Removing the LSTM costs 13.9 percentage points of time-in-target
> SpO₂. Removing the Digital Twin causes 14% of recommendations to
> exceed safety bounds. Removing the audit chain has no clinical
> impact but eliminates forensic accountability. They're complementary,
> not redundant."

### Q: "What's left for future work?"
> "Three things, all listed in the deferred-work sections of the
> evaluation reports: (1) reliability diagrams for the hypoxia head's
> probability calibration, (2) re-evaluation against MIMIC-IV waveform
> data, (3) federated learning across institutions, which is already
> on the architecture roadmap."

---

## 📋 4. The "If All Else Fails" Demo (no API needed)

If the API or dashboard refuses to start, fall back to **pure Python
demos** that use only the in-repo libraries — these always work:

```powershell
# Demo 1: Digital Twin (Phase 2)
python -m services.digital_twin

# Demo 2: PPO rule-based recommendation (Phase 4 Layer A)
python -m services.ppo_policy

# Demo 3: Off-chain audit ledger + tamper-evidence (Phase 5)
python -m services.audit_bridge

# Demo 4: PPO trainer smoke (Phase 4 Layer B)
python ml\ppo_training.py --smoke

# Demo 5: Run the entire test suite live in front of the examiner
python -m unittest discover -s tests -p "test_*.py" -v
```

Each of those prints meaningful output to the terminal and proves the
component works without any web server.

---

## 🌐 5. Optional: Grafana / Prometheus (only if you have time)

```powershell
# Terminal 1: API on 0.0.0.0 so Docker can reach it
$env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: bring up Grafana + Prometheus
cd deploy
docker compose up -d

# Open http://localhost:3000  (login: admin / admin)
# Dashboards → Ventilator → "Ventilator LSTM (API /metrics)"
```

> Skip this in a 20-minute slot — not worth the risk of Docker
> Desktop being slow to start.

---

## 🔑 6. Master Command Reference (copy/paste)

### Activation (every new terminal)
```powershell
cd "C:\Users\risha\Downloads\Major Project\Major Project"
.\.venv311\Scripts\Activate.ps1
$env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"
```

### API server
```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Dashboard
```powershell
Start-Process .\frontend\dashboard\index.html
```

### Tests
```powershell
python -m unittest discover -s tests -p "test_*.py"          # all 39
python -m unittest tests.test_digital_twin_safety -v         # safety
python -m unittest tests.test_ppo_training_smoke -v          # PPO
python -m unittest tests.test_chain_anchor -v                # blockchain
```

### Standalone demos
```powershell
python -m services.digital_twin
python -m services.ppo_policy
python -m services.audit_bridge
python -m services.chain_anchor --mode dry_run
python ml\ppo_training.py --smoke
```

### API curl probes
```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/patients
curl http://127.0.0.1:8000/patient/30004018/history
curl -X POST http://127.0.0.1:8000/audit/anchor -H "Content-Type: application/json" -d '{\"mode\":\"dry_run\"}'
curl http://127.0.0.1:8000/audit/verify
```

### Solidity contract tests (only if examiner asks)
```powershell
cd blockchain
npm install
npx hardhat test
cd ..
```

---

## 🚨 7. Emergency Phrases for the Examiner

If something breaks live, **say one of these and keep going** — don't
panic, don't fight the laptop on stage:

- > "Let me show you the same thing without the UI layer —"
  → switch to § 4 standalone demos.
- > "The model artifact path needs an environment variable, one
  > moment —" → run `$env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"`
  and restart uvicorn.
- > "While that loads, let me walk you through the architecture
  > diagram —" → flip to `docs/diagrams/system-architecture.md`.
- > "The Solidity tests are in CI — let me show you the contract source
  > directly —" → open `blockchain/contracts/AuditAnchor.sol` and
  > narrate the `commitAnchor` function.

---

## 🛠️ 8. Recovery Cheatsheet

| Symptom | Fix |
| --- | --- |
| `Activate.ps1` rejected by execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force` (one-time) |
| `python` not found | Use full path: `C:\Users\risha\AppData\Local\Programs\Python\Python312\python.exe` |
| `/health` says `lstm.model_loaded = false` | `$env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"` then restart uvicorn |
| Dashboard dropdown stuck on "Loading…" | API not reachable — check uvicorn is on port 8000 and CORS not blocked |
| `tensorflow not installed` in `/health` | `pip install tensorflow==2.15.*` then restart |
| Tampered ledger from Scenario 2 still broken | `Remove-Item blockchain\audit_ledger.db*` and restart API |
| Port 8000 already in use | `Get-NetTCPConnection -LocalPort 8000` to find PID, then `Stop-Process -Id <PID>` |
| Dashboard shows errors | Open browser DevTools console — most issues are CORS or wrong port |
| Demo data missing | API auto-creates `data/demo_ventilator_data.csv` on first request — wait 2 s and retry |
| Tests fail because of stale `__pycache__` | `Get-ChildItem -Recurse -Force -Filter __pycache__ \| Remove-Item -Recurse -Force` |

---

## ⏱️ 9. 60-Second Elevator Pitch (Memorize)

> *"This project is an AI-driven, blockchain-trusted digital twin
> co-pilot for ICU ventilator optimization. We combined three
> independent guarantees: an LSTM dual-head model that forecasts
> SpO₂ and hypoxia risk three hours ahead with 87% AUROC; a
> patient-specific digital twin that validates every proposed
> ventilator setting against simulated respiratory mechanics before
> it reaches the clinician; and a tamper-evident audit chain — both
> off-chain and on-chain — that makes every recommendation
> cryptographically auditable. We measured the full system against
> static ARDSnet protocol and saw time-in-target SpO₂ go from 65%
> to 88% and alarms per patient per day fall from 14 to 3. The
> ablation study proves none of the three components is redundant."*

---

## ✅ 10. Day-Of Checklist

- [ ] Laptop fully charged + power adapter in bag
- [ ] HDMI / USB-C dongle for projector
- [ ] Two browser windows pre-opened: `index.html` and `localhost:8000/docs`
- [ ] Three PowerShell windows ready (one for API, two free)
- [ ] This file (`PRESENTATION_DAY.md`) open on phone or second monitor
- [ ] `docs/presentation/slides_notes.md` open for slide narration
- [ ] `reports/benchmark-results.md` open for KPI questions
- [ ] **Test §0 commands the morning of the presentation**
- [ ] Backup: USB drive with this entire project folder

**Good luck — you've got this. 🚀**
