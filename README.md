# Blockchain-Enabled Digital Twin Framework for Enhancing Ventilator Parameters

> A real-time, AI-driven decision-support system for mechanical ventilation that combines a **digital twin**, an **LSTM forecaster**, a **PPO reinforcement-learning agent**, and a **blockchain audit trail** — built as a final-year B.Tech major project.

![Status](https://img.shields.io/badge/status-Phase%208%20%E2%80%93%20Final%20Packaging-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/api-FastAPI-009688)
![License](https://img.shields.io/badge/license-Academic-lightgrey)

---

## Table of Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Documentation](#documentation)
- [Demo & Dashboard](#demo--dashboard)
- [Authors](#authors)

---

## What it does

Mechanical ventilators in ICUs are tuned manually, with limited foresight into how a parameter change will affect patient state. This project builds an **end-to-end clinical co-pilot** that:

1. **Ingests** live ventilator telemetry (real or simulated).
2. **Forecasts** SpO₂ and hypoxia/desaturation/multi-risk events with an **LSTM** (dual-head + multi-risk variants).
3. **Recommends** PEEP / FiO₂ / TidalVol adjustments using a **PPO** RL agent trained inside a **Digital Twin** environment with safety guards.
4. **Anchors** every recommendation event on an **immutable blockchain audit ledger** (off-chain hash chain + on-chain Solidity anchor).
5. **Visualizes** the live state, predictions, and audit trail on a real-time dashboard with **Prometheus + Grafana** observability.

---

## Architecture

```
                          ┌──────────────────────────────┐
                          │  Frontend Dashboard (HTML)   │
                          │  Live patient + forecasts    │
                          └──────────────┬───────────────┘
                                         │ REST/JSON
                                         ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                      FastAPI Service (api/)                   │
   │  /simulator  /twin/replay  /patient/{id}/recommend  /metrics  │
   └─────┬───────────────┬──────────────┬───────────────┬──────────┘
         │               │              │               │
         ▼               ▼              ▼               ▼
   Simulator        Digital Twin     LSTM Inference   PPO Policy
   (services/       (services/       (services/       (services/
    data_simulator)  digital_twin)    lstm_inference)  ppo_policy)
                          │              │               │
                          └──────────────┴───────┬───────┘
                                                 ▼
                                       Audit Bridge
                                       (services/audit_bridge)
                                                 │
                                  ┌──────────────┴───────────────┐
                                  ▼                              ▼
                       SQLite hash chain            Solidity AuditAnchor
                       (off-chain)                  (blockchain/)
```

A detailed component & dataflow walkthrough lives in [docs/architecture-decisions.md](docs/architecture-decisions.md), with diagrams in [docs/diagrams/](docs/diagrams/) and a full DFD/UML in [docs/dfd_uml.md](docs/dfd_uml.md).

---

## Key Features

- 🔁 **Digital Twin** — physiologically bounded patient model with safety guards ([services/digital_twin.py](services/digital_twin.py))
- 🧠 **LSTM Forecaster** — dual-head SpO₂ regression + hypoxia classification, plus a multi-risk variant ([services/lstm_inference.py](services/lstm_inference.py), [services/multi_risk_inference.py](services/multi_risk_inference.py))
- 🎯 **PPO RL Agent** — Stable-Baselines3 trained in the twin env, with rule-based safety layer ([services/ppo_policy.py](services/ppo_policy.py))
- 🔐 **Blockchain Audit** — off-chain SHA-256 hash chain + on-chain Solidity anchor (Hardhat) ([services/chain_anchor.py](services/chain_anchor.py), [blockchain/contracts/AuditAnchor.sol](blockchain/contracts/AuditAnchor.sol))
- 📈 **Observability** — `/metrics` for Prometheus, pre-provisioned Grafana dashboards ([deploy/](deploy/))
- 🧪 **Test Suite** — replay, safety, multi-risk, blockchain anchoring, simulator API ([tests/](tests/))
- 📦 **One-command Phase 1 pipeline** — `python pipelines/run_phase1.py` builds synthetic data + features end-to-end

---

## Tech Stack

| Layer            | Technology |
|------------------|------------|
| API              | FastAPI, Uvicorn, Pydantic |
| ML / Forecasting | TensorFlow / Keras (LSTM), scikit-learn |
| RL               | Stable-Baselines3 (PPO), Gymnasium custom env |
| Blockchain       | Solidity, Hardhat, web3.py |
| Storage          | SQLite (audit ledger), CSV / pickled features |
| Observability    | Prometheus, Grafana (Docker Compose) |
| Frontend         | Vanilla HTML/JS dashboard |
| Testing          | unittest, pytest |

---

## Project Structure

```
.
├── api/                 # FastAPI app — entrypoint: api/main.py
├── services/            # Core domain services (twin, LSTM, PPO, audit, simulator, metrics)
├── ml/                  # Training scripts (LSTM, multi-risk, PPO env). Artifacts gitignored.
├── pipelines/           # Feature engineering, run_phase1, evaluation, replay benchmark
├── blockchain/          # Solidity contracts, Hardhat config, deploy & test scripts
├── frontend/dashboard/  # Static HTML dashboard (talks to API on :8000)
├── deploy/              # Docker Compose (Prometheus + Grafana), provisioned dashboards
├── tests/               # Unit & integration tests
├── docs/                # Specs, diagrams, presentation, viva prep, research papers
├── reports/             # Model evaluation reports & ablation studies
├── scripts/             # One-off utilities (e.g. evaluation report generator)
├── requirements.txt     # Python dependencies
├── README.md            # ← you are here
├── RUNNING.md           # Step-by-step run guide (API, dashboard, Grafana, tests)
└── IMPLEMENTATION_LOG.md  # Full phase-by-phase implementation journal
```

---

## Quick Start

> **Full guide with troubleshooting:** [RUNNING.md](RUNNING.md)

### Prerequisites
- Python **3.10+** (3.11 / 3.12 recommended)
- Docker Desktop *(optional — only for the Grafana + Prometheus stack)*

### 1. Install
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Run the API
```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Sanity check:
- Root: <http://127.0.0.1:8000/>
- Health: <http://127.0.0.1:8000/health>
- Swagger: <http://127.0.0.1:8000/docs>

### 3. Open the dashboard
Open [`frontend/dashboard/index.html`](frontend/dashboard/index.html) in your browser. If `file://` is blocked, serve it:
```powershell
cd frontend/dashboard
python -m http.server 8080
# then open http://127.0.0.1:8080
```

### 4. Build synthetic data + train the LSTM *(optional but recommended)*
```powershell
python pipelines/run_phase1.py
$env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"
python ml/lstm_training.py
```
With trained artifacts, recommendations include `"lstm_forecast_source": "lstm_keras"` and the dashboard shows **Forecast: LSTM (Keras dual-head)**.

### 5. Start Grafana + Prometheus *(optional)*
```powershell
cd deploy
docker compose up -d
# Grafana:    http://localhost:3000  (admin / admin)
# Prometheus: http://localhost:9090
```

---

## Running Tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Selective digital-twin evaluation with strict CI-style gates:
```powershell
python pipelines/evaluate_digital_twin.py --fail-on-thresholds
```

---

## Documentation

| Document | What's inside |
|----------|---------------|
| [RUNNING.md](RUNNING.md) | Local run guide: API, dashboard, training, Grafana, tests |
| [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) | Phase-by-phase implementation journal (Phase 0 → 8) |
| [docs/architecture-decisions.md](docs/architecture-decisions.md) | High-level architecture & key design decisions |
| [docs/twin-model-spec.md](docs/twin-model-spec.md) | Digital twin specification & equations |
| [docs/event-schema.md](docs/event-schema.md) | Canonical telemetry event schema |
| [docs/safety-constraints.md](docs/safety-constraints.md) | Safety guards & clinical bounds |
| [docs/blockchain_ventilator_framework.md](docs/blockchain_ventilator_framework.md) | Blockchain audit design |
| [docs/multi_risk_integration_guide.md](docs/multi_risk_integration_guide.md) | Multi-risk LSTM head integration |
| [docs/failure-recovery.md](docs/failure-recovery.md) | Graceful degradation & recovery |
| [docs/demo-runbook.md](docs/demo-runbook.md) | Step-by-step demo script |
| [docs/diagrams/](docs/diagrams/) | DFD, UML, system architecture diagrams |
| [docs/presentation/](docs/presentation/) | Slide notes, viva prep, hindi viva |
| [reports/](reports/) | Model evaluation reports (LSTM, PPO, twin, multi-risk, ablation) |

Reference papers under [docs/](docs/) include the IEEE PSV-RL paper, the wind-turbine digital-twin paper, and the project report PDF.

---

## Demo & Dashboard

The dashboard polls `/recommend` every ~5 s, updating:
- Live SpO₂ vs LSTM-predicted next SpO₂
- Hypoxia probability & multi-risk gauges
- PPO recommendation (PEEP / FiO₂ / TidalVol)
- Audit chain hash for the latest event

A walk-through is in [docs/demo-runbook.md](docs/demo-runbook.md). Presentation-day notes: [docs/presentation/PRESENTATION_DAY.md](docs/presentation/PRESENTATION_DAY.md).

---

## Notes on Excluded Artifacts

To keep the repo lean, the following are **gitignored** and must be regenerated locally via the pipelines:

| Artifact | How to regenerate |
|----------|-------------------|
| `*.csv` raw / engineered datasets (~656 MB) | `python pipelines/run_phase1.py` and `python pipelines/feature_engineering.py` |
| `ml/**/*.pkl` feature tensors (~3.7 GB) | Same pipelines above |
| `*.keras` / `*.h5` trained models | `python ml/lstm_training.py`, `python ml/multi_risk_training.py`, `python ml/ppo_training.py` |
| Python venv (`.venv*/`) | `pip install -r requirements.txt` |
| `blockchain/audit_ledger.db*` | Created on first API call to `/audit/anchor` |

`.gitattributes` is pre-configured for Git LFS (`*.csv`, `*.h5`, `*.keras`, `*.pkl`) if you choose to push artifacts later.

---

## Authors

**Rishav Kumar** — final-year B.Tech, 8th semester major project.

For viva / academic context see [docs/viva_prep.md](docs/viva_prep.md) and the [final report](docs/final_report/).
