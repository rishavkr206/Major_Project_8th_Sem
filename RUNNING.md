# How to run this project

Short guide for running the API, dashboard, pipelines, and tests from the **repository root** (`Major Project/`).

## Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended) with `python` and `pip` on your PATH  
- **Git** (optional, for cloning)  
- **Docker Desktop** (or Docker Engine + Compose v2) — **only** for the **Grafana + Prometheus** stack in `deploy/`; it is not installed via pip.

## 1. Install dependencies

Open a terminal in the project root, then:

```powershell
cd "path\to\Major Project"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

That file installs **API + tests + Prometheus metrics + TensorFlow + scikit-learn** (everything needed for **LSTM training/inference** and the **Grafana** `/metrics` time series). If you prefer minimal API-only installs, see comments inside `requirements.txt` (not split in repo — keep one file for class demos).

**`prometheus-client`** powers **`GET /metrics`** for Grafana/Prometheus (see **Grafana** below). If it is missing, `/metrics` still responds with a short text comment.

### Train the LSTM so the dashboard uses the real model

By default the co-pilot uses **heuristic** `pred_next_spo2` / `hypoxia_prob` unless a trained **Keras** model and the **feature pickles** from `pipelines/feature_engineering.py` are present. With artifacts in place, responses include **`"lstm_forecast_source": "lstm_keras"`** and the dashboard shows **Forecast: LSTM (Keras dual-head)**.

1. Build synthetic data + feature artifacts (writes `data/simulated_phase1.csv` and `ml/simulated_phase1/*.pkl`):

   ```powershell
   python pipelines\run_phase1.py
   ```

2. Train (reads/writes under the directory in **`LSTM_ARTIFACTS_DIR`**, default `ml/`):

   ```powershell
   $env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"
   python ml\lstm_training.py
   ```

3. Restart the API with the same **`LSTM_ARTIFACTS_DIR`** if your pickles are not in `ml/`:

   ```powershell
   $env:LSTM_ARTIFACTS_DIR = "$(Resolve-Path '.\ml\simulated_phase1')"
   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```

Check **`GET /health`** → **`lstm`** (artifact paths, `model_loaded`). Inference searches, in order: **`LSTM_ARTIFACTS_DIR`**, `ml/simulated_phase1/`, then `ml/`.

## 2. Run the API server

Always start the server from the **project root** so imports like `services.*` resolve correctly.

```powershell
cd "path\to\Major Project"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Use **`--host 0.0.0.0`** when **Docker / Prometheus** will scrape **`/metrics`** (Grafana subsection below). For local-only browser use, **`127.0.0.1`** is also fine.

- **Root (sanity check):** http://127.0.0.1:8000/ — returns JSON with links (not `{"detail":"Not Found"}`).  
- **Quick status:** http://127.0.0.1:8000/health — dataset path, row count, sample `stay_id`, and **LSTM artifact status**.  
- **Swagger UI:** http://127.0.0.1:8000/docs  
- **ReDoc:** http://127.0.0.1:8000/redoc  

**Note:** Avoid `python api/main.py` unless you set `PYTHONPATH` to the project root; `python -m uvicorn api.main:app` is the supported way.

**Startup time:** On first launch the app may load index data from `clean_full_data_v2.csv` (if present). That can take **over a minute** on large files; wait until the log shows `Application startup complete`.

**Dataset:** If `clean_full_data_v2.csv` is in the project root, that file is used. Otherwise the API uses `data/simulated_phase1.csv` when present. If neither exists, on **first startup** it **creates** `data/demo_ventilator_data.csv` (synthetic simulator data) so the dashboard patient/history endpoints work without downloading a large ICU extract.

### Grafana + Prometheus (LSTM / SpO₂ time series)

The API exposes Prometheus text on **`GET /metrics`** (gauges updated on each **`POST /patient/{id}/recommend`**). Prometheus scrapes that every few seconds so **Grafana** can plot **observed SpO₂ vs LSTM-predicted next SpO₂**, hypoxia risk, and whether Keras was used.

**Requirements:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2), `prometheus-client` installed in the same Python as uvicorn.

1. Start the API so Docker can reach it from the host (**`0.0.0.0`** is important on Windows):

   ```powershell
   cd "path\to\Major Project"
   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```

2. In another terminal, start the stack from **`deploy/`**:

   ```powershell
   cd "path\to\Major Project\deploy"
   docker compose up -d
   ```

3. Open **Grafana:** http://localhost:3000 — login **`admin` / `admin`** (change password when prompted).

4. **Dashboards → folder “Ventilator” → “Ventilator LSTM (API /metrics)”** (auto-provisioned).

5. Keep the **HTML dashboard** open so `/recommend` runs periodically (~5s); each call updates gauges and Prometheus stores a new sample at scrape time.

**URLs:** Grafana http://localhost:3000 · Prometheus UI http://localhost:9090 · probe metrics http://127.0.0.1:8000/metrics  

**Linux:** if `host.docker.internal` does not resolve from the Prometheus container, edit `deploy/prometheus/prometheus.yml` and set `targets` to your host gateway IP (often `172.17.0.1:8000`).

## 3. Run the dashboard (frontend)

The dashboard is a static page that talks to the API at **http://localhost:8000**.

1. Start the API (section 2).  
2. Open `frontend/dashboard/index.html` in your browser (Chrome or Edge).

If the browser blocks requests from `file://`, serve the folder:

```powershell
cd "path\to\Major Project\frontend\dashboard"
python -m http.server 8080
```

Then open http://127.0.0.1:8080 — keep the API on port **8000**.

## 4. Phase 1 pipeline (synthetic data + features)

From the project root:

```powershell
python pipelines/run_phase1.py
```

Expected: `data/simulated_phase1.csv` and artifacts under `ml/simulated_phase1/`.  
Options: `python pipelines/run_phase1.py --help` (e.g. `--stays-per-profile`, `--steps-per-stay`, `--seed`, `--seq-len`).

## 5. Unit tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 6. Digital twin evaluation (optional)

```powershell
python pipelines/evaluate_digital_twin.py
```

Strict CI-style gate (non-zero exit if thresholds fail):

```powershell
python pipelines/evaluate_digital_twin.py --fail-on-thresholds
```

## 7. Example API call (twin replay)

With the server running:

```bash
curl -X POST "http://127.0.0.1:8000/twin/replay" -H "Content-Type: application/json" -d "{\"stay_id\":910050,\"proposed\":{\"PEEP\":10,\"FiO2\":65,\"TidalVol\":430},\"steps\":4,\"noise_scale\":0}"
```

On Windows PowerShell you can use `Invoke-RestMethod` instead of `curl` if preferred.

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| `ModuleNotFoundError: No module named 'services'` | Run uvicorn from the **project root**, not from inside `api/`. |
| `ModuleNotFoundError: No module named 'fastapi'` | Run section 1 installs again. |
| Browser or health check **times out** on `/docs` | Wait for startup to finish (large CSV); retry with a longer timeout (e.g. 30–120 s). |
| Port 8000 in use | Change port: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8001` and update `API_BASE` in `frontend/dashboard/index.html` to match. |

## Related docs

- High-level plan, phases, and implementation log: `README.md`  
- Debug / replay workflow: `docs/debug-workflow.md`  
- Event schema: `docs/event-schema.md`
