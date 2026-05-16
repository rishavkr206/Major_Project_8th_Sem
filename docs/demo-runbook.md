# Live Demo Runbook

**Phase 8 deliverable** — Blockchain-Enabled Digital Twin Framework.
Use this script for in-person demos, viva, and recorded walk-throughs.

> **Total runtime:** ≈ 12 minutes for the full 3-scenario walkthrough,
> ≈ 4 minutes for the abbreviated viva version (Scenario 1 only).

---

## 0. Pre-flight (do this 10 minutes before the demo)

```powershell
# 1. From repo root
cd "Major Project"

# 2. Activate venv (Python 3.11 expected)
.\.venv311\Scripts\Activate.ps1

# 3. Confirm artifacts exist
Get-Item ml/models/lstm_model.keras
Get-Item ml/multi_risk/multi_risk_lstm.keras
Get-Item blockchain/audit_ledger.db   # may not exist yet — auto-created on first event

# 4. Start the API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

In a second terminal:

```powershell
# 5. Open the dashboard (static page hits the API on :8000)
Start-Process .\frontend\dashboard\index.html

# 6. Sanity-check the API
curl http://127.0.0.1:8000/health
```

If `/health` reports `lstm.model_loaded = false`, run:

```powershell
$env:LSTM_ARTIFACTS_DIR = "ml/simulated_phase1"
# then restart uvicorn
```

---

## 1. Scenario 1 — Predictive Save (4 min)

**Story:** patient on `ards` profile is trending toward hypoxia. The LSTM
sees it 3 hours early; the PPO recommends a small PEEP+FiO2 bump; the
Digital Twin validates the bump won't crash the patient; the clinician
accepts; the action is anchored to the audit chain.

1. In the dashboard, pick **Patient ID 30004018** from the dropdown.
2. Watch the SpO2 trend — point out the gentle decline.
3. Click **Get Recommendation**.
   - Show: `alert_level = WARNING`, `pred_next_spo2` ≈ 92, `hypoxia_prob`
     between 0.4 and 0.7.
   - Open the **Twin Simulation** panel — show the 1-hour
     forward trajectory band.
   - Open **Rationale** — show the line "MODERATE hypoxia risk —
     incremental PEEP and FiO2 increase".
4. Click **Accept**.
5. Open the **Audit Trail** panel — show the new `RECOMMENDATION` and
   `ACCEPT` blocks chained together.

**Talking points while clicking:**

- The LSTM dual-head model: Next_SpO2 MAE 1.53%, hypoxia AUROC 0.873.
- The Digital Twin clamped any out-of-bound proposed setting silently
  (point at the `applied` field if it differs from `proposed`).
- Every recommendation is one event in a SHA-256 hash chain — show
  `prev_hash` linking the two latest blocks.

---

## 2. Scenario 2 — Tamper Detection (3 min)

**Story:** simulate an attacker editing a past recommendation in the
SQLite ledger. Show the chain integrity check failing.

1. Stop the API briefly (Ctrl+C) so SQLite isn't write-locked.
2. In a Python REPL:
   ```python
   import sqlite3
   conn = sqlite3.connect("blockchain/audit_ledger.db")
   conn.execute("UPDATE audit_chain SET payload_json = '{\"tampered\":true}' WHERE block_id = 1")
   conn.commit()
   ```
3. Restart the API.
4. Hit `GET /audit/verify` from the dashboard's **Verify Chain** button.
   - Expect: `valid = false` with a message naming the tampered
     `block_id`.
5. Show how on-chain anchoring (Phase 5) makes this detectable from
   outside the institution as well: `POST /audit/anchor {"mode":"dry_run"}`
   returns the would-be chain hash, which any third party can compare
   against the on-chain `latestAnchor()` value.

**Restore for next demo:**

```powershell
git checkout blockchain/audit_ledger.db   # or rm + restart API
```

---

## 3. Scenario 3 — Failure-Mode Resilience (3 min)

**Story:** the LSTM model is unavailable. The system degrades to a
heuristic forecast and **does not** stop issuing recommendations. The
audit log distinguishes the two regimes for forensic purposes.

1. Move the LSTM artifact aside:
   ```powershell
   Move-Item ml\models\lstm_model.keras ml\models\lstm_model.keras.bak
   ```
2. Restart the API.
3. Click **Get Recommendation** for the same patient.
   - Show: response field `lstm_forecast_source = "heuristic"`.
   - Point out that `confidence` drops correspondingly.
   - The Digital Twin still simulates and clamps; safety is preserved.
4. Open the audit trail — show that the `RECOMMENDATION` event payload
   includes the source flag, so a reviewer can later filter out
   heuristic-mode events when computing model performance metrics.
5. Restore:
   ```powershell
   Move-Item ml\models\lstm_model.keras.bak ml\models\lstm_model.keras
   ```

---

## 4. Closing Slide Talking Points (2 min)

- **Three independent guarantees**: forecasting accuracy (LSTM),
  safety bound (Digital Twin), and forensic integrity (audit + on-chain
  anchor). No two are interchangeable — the ablation study makes this
  precise.
- **Headline numbers**: time in target SpO2 65.2% → 88.1%, hypoxia
  fraction 12.4% → 4.9%, alarms / 24h 14 → 3, audit traceability 0% →
  100%.
- **Inference latency** p95 = 73 ms; the SLA is 2 s.
- **Failure-mode posture**: every model has a documented degradation
  path; nothing in the pipeline single-points-of-fails the clinician's
  view of the patient.

---

## 5. Recovery Cheatsheet

| Symptom | Fix |
| --- | --- |
| `/health` says `dataset_index_loaded = false` | The auto-generated synthetic dataset will be created on first request to `/patient/{id}/history`. Wait ~2 s and retry. |
| Dashboard dropdown stuck on "Loading…" | API is not reachable — confirm uvicorn is running on port 8000 and CORS isn't blocked. |
| `lstm.load_error = "tensorflow not installed"` | `pip install tensorflow==2.15.*` then restart. |
| `/audit/anchor` returns 400 in `live` mode | Confirm `AUDIT_ANCHOR_RPC_URL`, `AUDIT_ANCHOR_PRIVATE_KEY`, `AUDIT_ANCHOR_CONTRACT` are set; or use `mode=dry_run`. |
| Tamper-detection demo broke the DB and you don't have a backup | `Remove-Item blockchain/audit_ledger.db*` and restart — the API will recreate an empty chain. |
