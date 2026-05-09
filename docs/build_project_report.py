"""
Build a comprehensive PDF project report.

Output: docs/Project_Report.pdf
Run:    python docs/build_project_report.py
"""

from __future__ import annotations

import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_PATH = os.path.join(REPO_ROOT, "docs", "Project_Report.pdf")


# ─── Styles ──────────────────────────────────────────────────────────────────
def build_styles():
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1e3a8a"),
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=base["Normal"],
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=20,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=12,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1e40af"),
        spaceBefore=10,
        spaceAfter=6,
    )
    h3 = ParagraphStyle(
        "H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=body,
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=2,
    )
    code = ParagraphStyle(
        "Code",
        parent=base["Code"],
        fontName="Courier",
        fontSize=9,
        leading=12,
        leftIndent=10,
        backColor=colors.HexColor("#0f172a"),
        textColor=colors.HexColor("#e2e8f0"),
        borderPadding=4,
        spaceAfter=8,
    )
    note = ParagraphStyle(
        "Note",
        parent=body,
        fontSize=9,
        textColor=colors.HexColor("#475569"),
        leading=12,
    )
    return {
        "title": title,
        "subtitle": subtitle,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "body": body,
        "bullet": bullet,
        "code": code,
        "note": note,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────
def p(text: str, style):
    return Paragraph(text, style)


def b(text: str, style):
    return Paragraph(f"&bull;&nbsp; {text}", style)


def tbl(data, col_widths=None, header=True, zebra=True, font_size=9):
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
    ]
    if header:
        style_cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), font_size),
        ]
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == (1 if header else 0):
                style_cmds.append(
                    ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f1f5f9"))
                )
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style_cmds))
    return t


# ─── Page decoration ─────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    page_num = canvas.getPageNumber()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawRightString(
        A4[0] - 1.5 * cm,
        1.0 * cm,
        f"Page {page_num}",
    )
    canvas.drawString(
        1.5 * cm,
        1.0 * cm,
        "Blockchain-Enabled Digital Twin Framework — Final Year Major Project",
    )
    canvas.line(1.5 * cm, 1.4 * cm, A4[0] - 1.5 * cm, 1.4 * cm)
    canvas.restoreState()


# ─── Content ─────────────────────────────────────────────────────────────────
def build_story(s):
    story = []

    # Title page
    story.append(Spacer(1, 4 * cm))
    story.append(p("Blockchain-Enabled Digital Twin Framework", s["title"]))
    story.append(p("for Enhancing Ventilator Parameters", s["title"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(p("Comprehensive Project Report", s["subtitle"]))
    story.append(Spacer(1, 1 * cm))
    story.append(
        tbl(
            [
                ["Project Type", "B.Tech. Final-Year Major Project (Semester 8)"],
                ["Domain", "Critical Care AI · Digital Twins · Blockchain Audit"],
                ["Stack", "Python · FastAPI · TensorFlow · NumPy · SQLite · Chart.js · Docker"],
                ["Status", "Phase 2 (Digital Twin) complete · ~62% overall"],
                ["Document Date", date.today().isoformat()],
            ],
            col_widths=[4.5 * cm, 11.5 * cm],
            header=False,
            zebra=True,
            font_size=10,
        )
    )
    story.append(Spacer(1, 1.5 * cm))
    story.append(
        p(
            "<i>An AI-driven, blockchain-trusted digital twin co-pilot for ventilator "
            "optimization that brings predictive safety, adaptive control, and immutable "
            "clinical accountability to ICU respiratory care.</i>",
            s["subtitle"],
        )
    )
    story.append(PageBreak())

    # ─── 1. Executive summary ────────────────────────────────────────────────
    story.append(p("1. Executive Summary", s["h1"]))
    story.append(
        p(
            "This project builds a real-time decision-support platform for ICU "
            "ventilator management. The system continuously ingests patient telemetry, "
            "uses an LSTM neural network to forecast short-term respiratory deterioration, "
            "uses a patient-specific digital twin to simulate the effect of any proposed "
            "ventilator setting change, and uses a reinforcement-learning-shaped policy to "
            "recommend safer settings. Every recommendation and every clinician action is "
            "appended to a tamper-evident SHA-256 hash chain, giving auditors a "
            "cryptographically verifiable trail of who changed what and when.",
            s["body"],
        )
    )
    story.append(
        p(
            "The work is scoped as a <b>clinician-in-the-loop prototype</b>: the system "
            "<i>recommends</i> changes; the clinician approves, overrides, or rejects them. "
            "There is no autonomous actuation of the ventilator. This keeps the system "
            "academically demonstrable while remaining within ethical bounds.",
            s["body"],
        )
    )
    story.append(p("1.1 Mission Statement", s["h2"]))
    story.append(
        p(
            "Deliver a clinician-in-the-loop decision support system that improves "
            "patient-ventilator synchronization, reduces avoidable ventilation risks, "
            "and provides trusted, explainable, and scalable infrastructure for modern "
            "ICUs.",
            s["body"],
        )
    )
    story.append(p("1.2 Target Performance KPIs", s["h2"]))
    story.append(
        tbl(
            [
                ["KPI", "Target", "Current Status"],
                ["Inference + recommendation latency", "< 2 seconds at edge", "Achieved (~10 ms /twin/replay)"],
                ["Asynchrony risk model AUROC", "> 0.85", "Pending Phase 3 closeout"],
                ["Prediction error improvement vs baseline", ">= 20%", "Pending Phase 7 ablation study"],
                ["Audit coverage of system events", "100%", "Achieved for RECOMMENDATION + TWIN_SIM"],
                ["Simulated asynchrony reduction vs static baseline", ">= 25%", "Pending Phase 7"],
            ],
            col_widths=[6 * cm, 4 * cm, 6 * cm],
        )
    )

    # ─── 2. Problem & motivation ─────────────────────────────────────────────
    story.append(p("2. Problem Statement and Motivation", s["h1"]))
    story.append(
        p(
            "Mechanical ventilation is one of the most common life-support interventions "
            "in modern ICUs, yet the choice of ventilator parameters (PEEP, FiO<sub>2</sub>, "
            "Tidal Volume, respiratory rate) is highly patient-specific and time-varying. "
            "Suboptimal settings lead to volutrauma, barotrauma, ventilator-induced lung "
            "injury (VILI), patient-ventilator asynchrony, and prolonged ICU stays.",
            s["body"],
        )
    )
    story.append(
        p(
            "Standard clinical workflows rely on intermittent manual review of vitals "
            "and protocolized rules of thumb (e.g. ARDSnet). They struggle in three "
            "specific ways:",
            s["body"],
        )
    )
    story.append(b("<b>Reactive, not predictive</b> &mdash; a desaturation event is detected only after it begins.", s["bullet"]))
    story.append(b("<b>One-size-fits-all settings</b> &mdash; protocolized rules ignore patient-specific lung mechanics that vary across ARDS / COPD / post-op profiles.", s["bullet"]))
    story.append(b("<b>Limited traceability</b> &mdash; once a parameter change is made there is no cryptographically verifiable record of who made the change, why, and on what evidence.", s["bullet"]))
    story.append(
        p(
            "This project addresses all three by combining <b>short-horizon LSTM "
            "forecasting</b>, a <b>patient-specific digital twin</b> for what-if "
            "simulation, a <b>safety-constrained policy engine</b> for recommendations, "
            "and a <b>blockchain-style audit chain</b> for immutable clinical traceability.",
            s["body"],
        )
    )

    # ─── 3. System architecture ──────────────────────────────────────────────
    story.append(p("3. System Architecture", s["h1"]))
    story.append(
        p(
            "The system is organised into six logical layers. The data layer ingests "
            "synthetic or historical patient telemetry into a canonical event schema. "
            "The AI layer runs an LSTM forecaster (Bi-LSTM dual-head, regression + "
            "binary hypoxia risk). The digital-twin layer simulates the effect of "
            "candidate ventilator settings on SpO<sub>2</sub>. The policy layer applies "
            "ARDSnet-inspired safety rules, validated through twin simulation. The "
            "audit layer commits SHA-256-linked records to a SQLite-backed hash chain. "
            "The presentation layer is a FastAPI service plus a static dashboard with "
            "Chart.js, Tailwind, and a Prometheus/Grafana metrics pipeline.",
            s["body"],
        )
    )
    story.append(p("3.1 Layer Map", s["h2"]))
    story.append(
        tbl(
            [
                ["Layer", "Responsibility", "Implementation"],
                ["Data", "Ingestion, canonical schema, validation, feature extraction", "services/data_simulator.py, pipelines/feature_engineering.py"],
                ["AI - Forecast", "Short-horizon SpO2 + hypoxia risk prediction", "ml/lstm_training.py, services/lstm_inference.py"],
                ["AI - Twin", "Patient-specific what-if simulation", "services/digital_twin.py"],
                ["AI - Policy", "Bounded recommendation generation", "services/ppo_policy.py"],
                ["Audit", "Tamper-evident hash chain", "services/audit_bridge.py"],
                ["API", "Service orchestration over REST", "api/main.py (FastAPI)"],
                ["Presentation", "Real-time dashboard + Grafana metrics", "frontend/dashboard/index.html, deploy/"],
            ],
            col_widths=[3 * cm, 6 * cm, 7 * cm],
        )
    )

    story.append(p("3.2 End-to-End Execution Loop", s["h2"]))
    steps = [
        "1. Capture live or simulated ventilator + vitals streams.",
        "2. Validate, align, and transform records into canonical features.",
        "3. Update the digital twin's calibration window for the patient.",
        "4. Run the LSTM forecaster for next-step SpO2 and hypoxia probability.",
        "5. Generate a candidate ventilator parameter set via the policy engine.",
        "6. Run the digital twin to simulate the candidate's effect for 4 steps (1 hour).",
        "7. Apply hard-bound clamps and compute confidence + safety flags.",
        "8. Surface the recommendation in the dashboard for clinician review.",
        "9. Log the recommendation event to the hash chain immediately.",
        "10. On clinician Accept / Override / Reject, append a second event linking to step 9.",
        "11. Optionally run a /twin/replay debug call; that also writes a TWIN_SIM event.",
        "12. Feed clinician outcomes back to the next LSTM training cycle (offline).",
    ]
    for stext in steps:
        story.append(p(stext, s["bullet"]))

    story.append(PageBreak())

    # ─── 4. Technology stack ─────────────────────────────────────────────────
    story.append(p("4. Technology Stack", s["h1"]))
    story.append(
        tbl(
            [
                ["Concern", "Tool / Library", "Why chosen"],
                ["Language", "Python 3.11 / 3.12", "Mature ML ecosystem, FastAPI ergonomics"],
                ["Web framework", "FastAPI 0.115 + uvicorn", "Async, OpenAPI docs free, type hints"],
                ["Forecasting model", "TensorFlow / Keras", "Bi-LSTM with dual head, focal loss"],
                ["Numerical core", "NumPy + pandas", "Time-series + feature engineering"],
                ["Twin model", "Pure NumPy", "Sub-millisecond, deterministic, no GPU"],
                ["Audit ledger", "SQLite + hashlib (SHA-256)", "Self-contained, ACID, easy to demo"],
                ["Visualisation", "Tailwind CSS + Chart.js", "Single-file dashboard, no build step"],
                ["Metrics", "prometheus-client", "Grafana scrape /metrics for live charts"],
                ["Container", "Docker Compose", "Reproducible Grafana + Prometheus stack"],
                ["CI", "GitHub Actions", "Twin Quality Gate workflow"],
                ["Tests", "unittest + httpx TestClient", "Stdlib-only, no extra deps"],
            ],
            col_widths=[3.5 * cm, 5 * cm, 7.5 * cm],
        )
    )

    # ─── 5. Repository structure ─────────────────────────────────────────────
    story.append(p("5. Repository Structure", s["h1"]))
    story.append(
        p(
            "Project root: <b>Major Project/</b>",
            s["body"],
        )
    )
    story.append(
        p(
            "<font face='Courier' size='8'>"
            "Major Project/<br/>"
            "+- README.md, RUNNING.md, requirements.txt<br/>"
            "+- api/main.py                    -- FastAPI surface (~16 endpoints)<br/>"
            "+- services/<br/>"
            "|   +- digital_twin.py            -- core respiratory mechanics model<br/>"
            "|   +- ppo_policy.py              -- safety-constrained recommender<br/>"
            "|   +- data_simulator.py          -- 4-profile telemetry generator<br/>"
            "|   +- lstm_inference.py          -- lazy-loaded Keras model<br/>"
            "|   +- audit_bridge.py            -- SHA-256 hash chain ledger<br/>"
            "|   +- prometheus_metrics.py      -- /metrics gauges<br/>"
            "+- ml/<br/>"
            "|   +- lstm_training.py           -- Bi-LSTM dual-head trainer<br/>"
            "|   +- models/lstm_model.keras    -- trained checkpoint<br/>"
            "|   +- simulated_phase1/          -- scaler + feature pickles<br/>"
            "+- pipelines/<br/>"
            "|   +- run_phase1.py              -- one-command synth + features<br/>"
            "|   +- simulated_ingestion.py     -- synthetic dataset builder<br/>"
            "|   +- feature_engineering.py     -- derived/lag/PPO features<br/>"
            "|   +- evaluate_digital_twin.py   -- 6-scenario gate<br/>"
            "|   +- historical_replay_benchmark.py -- real-data Phase-2 gate (NEW)<br/>"
            "+- frontend/dashboard/index.html  -- single-file Tailwind UI<br/>"
            "+- deploy/                        -- Grafana + Prometheus compose<br/>"
            "+- blockchain/audit_ledger.db     -- SQLite hash chain<br/>"
            "+- tests/                         -- unittest suite (23 tests)<br/>"
            "+- docs/                          -- specs, ADRs, diagrams, reports<br/>"
            "+- reports/                       -- evaluation outputs (JSON + MD)<br/>"
            "</font>",
            s["body"],
        )
    )

    # ─── 6. Phase progress ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(p("6. Phase-by-Phase Progress", s["h1"]))
    story.append(
        p(
            "The project plan defines nine phases. Current status is summarised below.",
            s["body"],
        )
    )
    story.append(
        tbl(
            [
                ["Phase", "Title", "% Done", "Status"],
                ["0", "Setup & Governance", "100%", "DONE"],
                ["1", "Data Foundation & Simulation", "100%", "DONE"],
                ["2", "Digital Twin V1", "100%", "DONE (this session)"],
                ["3", "LSTM Forecasting Engine", "70%", "Trained; needs eval report"],
                ["4", "PPO Optimization Agent", "25%", "Rule-based stand-in only"],
                ["5", "Blockchain Trust & Audit", "60%", "Hash chain + TWIN_SIM wired"],
                ["6", "Integration & Real-Time Dashboard", "55%", "Dashboard live; full compose pending"],
                ["7", "Validation, Benchmarking & Hardening", "10%", "Stub only"],
                ["8", "Final Packaging", "5%", "Pending"],
                ["", "OVERALL", "~62%", "Mid-stage"],
            ],
            col_widths=[1.5 * cm, 6.5 * cm, 2 * cm, 6 * cm],
        )
    )

    story.append(p("6.1 Phase 0 - Setup & Governance", s["h2"]))
    story.append(p("Deliverables completed:", s["body"]))
    for x in [
        "docs/requirements.md - functional + non-functional requirements",
        "docs/safety-constraints.md - hard parameter bounds + safety rules",
        "docs/architecture-decisions.md - ADRs for monorepo, FastAPI, synthetic-first, SQLite ledger, etc.",
        "docs/diagrams/ - architecture, DFD level-0/1, UML use case + sequence + class",
        "Implementation log embedded in README.md",
    ]:
        story.append(b(x, s["bullet"]))

    story.append(p("6.2 Phase 1 - Data Foundation & Simulation", s["h2"]))
    story.append(p("Synthetic telemetry simulator with four clinical profiles:", s["body"]))
    story.append(
        tbl(
            [
                ["Profile", "Baseline SpO2", "Baseline PEEP", "Baseline FiO2", "Trend"],
                ["normal", "97", "6", "35", "stable"],
                ["ards", "88", "11", "70", "drifting worse"],
                ["copd", "91", "8", "45", "stable / mild"],
                ["unstable", "86", "10", "78", "drifting worse, fastest"],
            ],
            col_widths=[3 * cm, 3 * cm, 3 * cm, 3 * cm, 4 * cm],
        )
    )
    story.append(
        p(
            "Each profile applies Gaussian measurement noise per metric, progressive "
            "drift, randomized artifact spikes, and packet-loss simulation by nulling "
            "one critical field. Records are validated against a canonical schema "
            "(<i>docs/event-schema.md</i>) before downstream feature engineering. The "
            "feature pipeline produces lag, derived, PPO-state-reward and trend "
            "features (~102 columns) and saves train/val/test splits as pickles for "
            "the LSTM trainer.",
            s["body"],
        )
    )

    story.append(p("6.3 Phase 2 - Digital Twin V1 (closed in this session)", s["h2"]))
    story.append(
        p(
            "The digital twin is a patient-specific virtual replica of respiratory "
            "mechanics. It is calibrated from the patient's last 12 telemetry rows "
            "and predicts the SpO<sub>2</sub> response to any proposed (PEEP, "
            "FiO<sub>2</sub>, TidalVol) tuple over a configurable horizon.",
            s["body"],
        )
    )
    story.append(p("Physics model (simplified):", s["h3"]))
    story.append(b("FiO<sub>2</sub>: each +1% above calibrated baseline contributes ~0.18 SpO<sub>2</sub> pp times compliance.", s["bullet"]))
    story.append(b("PEEP: each +1 cmH<sub>2</sub>O above baseline contributes ~0.35 SpO<sub>2</sub> pp times compliance (alveolar recruitment).", s["bullet"]))
    story.append(b("TidalVol: above 450 mL a quadratic-style penalty (volutrauma / VILI) reduces equilibrium SpO<sub>2</sub>.", s["bullet"]))
    story.append(b("Compliance factor: estimated from SpO<sub>2</sub> standard deviation in the calibration window (higher variability -> lower compliance).", s["bullet"]))
    story.append(b("Mean reversion: 45% of the gap to the equilibrium target is closed every 15 minutes.", s["bullet"]))
    story.append(b("Determinism: with noise_scale=0 (or a seeded RNG) the trajectory is byte-identical between runs.", s["bullet"]))

    story.append(p("Hard safety bounds (clamped before simulation):", s["h3"]))
    story.append(
        tbl(
            [
                ["Parameter", "Lower bound", "Upper bound", "Unit"],
                ["PEEP", "3.0", "20.0", "cmH2O"],
                ["FiO2", "21.0", "100.0", "%"],
                ["TidalVol", "200.0", "800.0", "mL"],
                ["SpO2 (output)", "60.0", "100.0", "% (clipping)"],
            ],
            col_widths=[5 * cm, 3.5 * cm, 3.5 * cm, 4 * cm],
        )
    )

    story.append(p("Items completed in this session:", s["h3"]))
    items = [
        ("pipelines/historical_replay_benchmark.py", "Walk-forward replay on 100 real ICU patients from clean_full_data_v2.csv. Closes Phase 2 exit criterion: 'Twin can reproduce historical trajectory with acceptable error'."),
        ("tests/test_digital_twin_safety.py", "16 edge-case physiological safety tests (clamping at +-infinity, severe hypoxic / supranormal calibration, empty/single-point history, invalid simulate args, trajectory bound clipping, risk-flag semantics)."),
        ("api/main.py - /twin/replay TWIN_SIM hook", "Every replay now appends a SYSTEM_TWIN authored block to the audit chain. Test asserts block presence and chain re-verification."),
        ("frontend/dashboard/index.html - Twin Replay panel", "New collapsible debug panel with PEEP/FiO2/TV/steps/noise/seed inputs, mini chart with bands, applied (post-clamp) settings display, mean/delta/uncertainty/compliance readouts, and clamp warning."),
        ("frontend/dashboard/index.html - main chart bands", "Upper/lower uncertainty band rendered as translucent shaded area around the twin trajectory."),
        ("docs/phase2-summary.md", "Single-page traceability map: spec -> impl -> tests -> eval -> gate -> CI -> dashboard surface."),
        (".github/workflows/twin-quality-gate.yml", "Extended CI to run the new safety tests and historical-replay gate; auto-generates synthetic data on fresh runners."),
        ("requirements.txt", "Pinned starlette to fastapi-compatible range to fix a pre-existing import break."),
    ]
    for fname, desc in items:
        story.append(p(f"<b>{fname}</b> &mdash; {desc}", s["bullet"]))

    story.append(p("Phase 2 evaluation results:", s["h3"]))
    story.append(
        tbl(
            [
                ["Metric", "Value", "Threshold", "Status"],
                ["Synthetic - trend_direction_accuracy", "100.00%", ">= 70%", "PASS"],
                ["Synthetic - replay_consistency", "100.00%", ">= 100%", "PASS"],
                ["Synthetic - mean_abs_delta_spo2", "1.495", "<= 8.0", "PASS"],
                ["Synthetic - rmse_delta_spo2", "1.723", "<= 10.0", "PASS"],
                ["Historical (real ICU) - teacher_forced.mae_avg", "1.69 pp", "<= 4.0", "PASS"],
                ["Historical (real ICU) - free_running.mae_avg", "2.87 pp", "<= 6.0", "PASS"],
                ["Historical patients evaluated", "100", "-", "-"],
                ["Test suite", "23 / 23", "all pass", "PASS"],
            ],
            col_widths=[8 * cm, 3 * cm, 2.5 * cm, 2.5 * cm],
        )
    )

    story.append(PageBreak())

    story.append(p("6.4 Phase 3 - LSTM Forecasting Engine", s["h2"]))
    story.append(
        p(
            "Bidirectional 2-layer LSTM with two output heads: a regression head for "
            "Next_SpO<sub>2</sub> and a sigmoid classification head for Hypoxia_Risk "
            "(SpO<sub>2</sub> &lt; 90 in the next step). The model uses focal loss "
            "with gamma=1.5 and alpha=0.8 on the classification head to compensate for "
            "class imbalance (positive rate ~72% on the synthetic Phase-1 split). The "
            "regression head uses MSE; classification head is weighted 8x in the "
            "combined loss. Adam, batch 256, early stopping on val_loss, ReduceLROnPlateau.",
            s["body"],
        )
    )
    story.append(p("Architecture summary:", s["h3"]))
    arch = [
        "Input: (sequence_length, n_features) - default 12 timesteps x ~102 features",
        "Bi-LSTM 256 with 0.4 dropout + L2 regularisation -> LayerNorm",
        "Bi-LSTM 128 (return_sequences=False) -> BatchNorm",
        "Dense(128, relu) -> Dropout -> Dense(64, relu) shared bottleneck",
        "Reg head: Dense(64) -> Dense(32) -> Dense(1) for Next_SpO2",
        "Cls head: Dense(64) -> Dense(32) -> Dense(1, sigmoid) for Hypoxia_Risk",
    ]
    for a in arch:
        story.append(b(a, s["bullet"]))

    story.append(p("Status: model trained, inference service operational, evaluation JSON exists. Pending: a publication-ready model-evaluation-lstm.md with calibration plots, PR/ROC curves, and KPI verification (AUROC > 0.85).", s["body"]))

    story.append(p("6.5 Phase 4 - PPO Optimization Agent", s["h2"]))
    story.append(
        p(
            "Currently a rule-based, ARDSnet-inspired clinical policy that acts as a "
            "drop-in replacement for a future Stable-Baselines3 PPO agent. The rules: "
            "if hypoxia_prob &gt; 0.7 or SpO<sub>2</sub> &lt; 88 then aggressively "
            "raise PEEP and FiO<sub>2</sub>; in the moderate band raise them "
            "incrementally; on predicted decline from the LSTM raise FiO<sub>2</sub> "
            "preemptively; on stable high SpO<sub>2</sub> wean FiO<sub>2</sub> per "
            "lung-protective practice. TidalVol is reduced when above 550 mL "
            "(barotrauma) and increased when below 280 mL (under-ventilation). "
            "Confidence is computed from model certainty + twin-predicted improvement, "
            "minus a penalty for any twin risk flag.",
            s["body"],
        )
    )
    story.append(
        p(
            "Pending: real PPO trained against the digital twin wrapped as a "
            "gymnasium environment, reward shaping doc (docs/reward-design.md), "
            "constraint-violation safety test suite, and benchmark against the "
            "current rule-based policy.",
            s["body"],
        )
    )

    story.append(p("6.6 Phase 5 - Blockchain Trust & Audit Layer", s["h2"]))
    story.append(
        p(
            "Append-only SHA-256 hash chain backed by SQLite. Each block contains: "
            "block_id, prev_hash, chain_hash, timestamp, stay_id, event_type, actor, "
            "payload_json, payload_hash. The chain hash is "
            "<font face='Courier'>SHA256(prev_hash || payload_hash || timestamp)</font>, "
            "ensuring any tampering with prior blocks is immediately detectable by "
            "/audit/verify. Event types defined: RECOMMENDATION, ACCEPT, OVERRIDE, "
            "REJECT, ALERT, TWIN_SIM, MODEL_INFER. Currently emitted: RECOMMENDATION, "
            "ACCEPT, OVERRIDE, REJECT, TWIN_SIM. Pending: emitting ALERT and "
            "MODEL_INFER, an off-chain/on-chain consistency policy doc, and "
            "(optional) a Solidity contract on a local Anvil/Ganache node.",
            s["body"],
        )
    )

    story.append(p("6.7 Phase 6 - Integration & Real-Time Dashboard", s["h2"]))
    story.append(
        p(
            "Single-file static dashboard (frontend/dashboard/index.html, ~700 LOC) "
            "showing: live vitals tiles, patient trajectory chart with twin prediction "
            "and uncertainty bands, current ventilator settings bars, AI Co-Pilot "
            "panel with proposed deltas / rationale / safety flags / SHAP-style "
            "impact bars / Accept-Override buttons, the new Twin Replay (Debug) "
            "panel, and the audit-trail timeline (with TWIN_SIM blocks rendering as "
            "purple flask icons). The Grafana + Prometheus stack in deploy/ scrapes "
            "/metrics for live SpO<sub>2</sub>-vs-LSTM-prediction time series. "
            "Pending: full-stack docker-compose (currently only Grafana + Prometheus "
            "are containerised), real SHAP values from the Keras model, and a "
            "docs/integration-architecture.md.",
            s["body"],
        )
    )

    story.append(p("6.8 Phase 7 - Validation, Benchmarking, Hardening", s["h2"]))
    story.append(p("Pending. Will produce three artefacts:", s["body"]))
    story.append(b("Latency / load benchmark with packet-loss and delay scenarios.", s["bullet"]))
    story.append(b("Ablation study: twin vs no-twin, LSTM-only vs LSTM+PPO, with vs without audit overhead.", s["bullet"]))
    story.append(b("Failure playbooks (twin unavailable / audit unavailable / LSTM artifacts missing).", s["bullet"]))

    story.append(p("6.9 Phase 8 - Final Packaging", s["h2"]))
    story.append(p("Pending. Final-report PDF, presentation deck, demo runbook, viva Q&A bank.", s["body"]))

    story.append(PageBreak())

    # ─── 7. Component deep-dive ─────────────────────────────────────────────
    story.append(p("7. Component Deep Dive", s["h1"]))

    story.append(p("7.1 Data Simulator", s["h2"]))
    story.append(
        p(
            "<b>File:</b> services/data_simulator.py. Class "
            "<i>VentilatorDataSimulator</i> driven by a <i>SimulationConfig</i> "
            "(profile, interval_minutes, packet_loss_probability, "
            "artifact_probability, trend_strength, seed). Produces records with "
            "{stay_id, charttime, HR, MAP, RespRate, SpO2, PEEP, FiO2, TidalVol}. "
            "Profile drift, measurement Gaussian noise, randomized artifact spikes "
            "(SpO<sub>2</sub> dips, MAP/RR jumps), and packet loss "
            "(field=null) are applied. <i>validate_record()</i> enforces the "
            "canonical schema in docs/event-schema.md.",
            s["body"],
        )
    )

    story.append(p("7.2 Digital Twin", s["h2"]))
    story.append(
        p(
            "<b>File:</b> services/digital_twin.py. Methods: <i>calibrate(history)</i>, "
            "<i>simulate(proposed, current_spo2, steps, noise_scale, rng)</i>. "
            "Output dict contains trajectory, upper_band, lower_band, mean_spo2, "
            "delta_spo2, uncertainty, risk_flag, tv_risk, applied (post-clamp settings).",
            s["body"],
        )
    )
    story.append(p("Sample API call:", s["h3"]))
    story.append(
        p(
            "<font face='Courier' size='8'>curl -X POST http://127.0.0.1:8000/twin/replay "
            "-H 'Content-Type: application/json' -d "
            "'{\"stay_id\":910050,\"proposed\":{\"PEEP\":10,\"FiO2\":65,\"TidalVol\":430},"
            "\"steps\":4,\"noise_scale\":0}'</font>",
            s["note"],
        )
    )

    story.append(p("7.3 LSTM Forecaster", s["h2"]))
    story.append(
        p(
            "<b>Files:</b> services/lstm_inference.py (lazy loader + inference), "
            "ml/lstm_training.py (training script). The forecaster auto-discovers "
            "artefacts from $LSTM_ARTIFACTS_DIR or ml/simulated_phase1/ or ml/. "
            "It returns (pred_next_spo2_unscaled, hypoxia_prob) when at least "
            "max(40, seq_len + 12) raw history rows are available; otherwise the API "
            "falls back to a deterministic vitals-only heuristic.",
            s["body"],
        )
    )

    story.append(p("7.4 PPO Policy", s["h2"]))
    story.append(
        p(
            "<b>File:</b> services/ppo_policy.py. The recommend() method takes "
            "current vitals + LSTM forecast + (optional) history; it calibrates the "
            "twin, applies the rule-based safety policy, runs a 4-step twin "
            "simulation on the proposed settings, computes a confidence score in "
            "[0.05, 0.99], and returns proposed settings, deltas vs current, "
            "rationale strings, safety_flags, and an alert_level enum "
            "(STABLE / WARNING / CRITICAL).",
            s["body"],
        )
    )

    story.append(p("7.5 Blockchain Audit Bridge", s["h2"]))
    story.append(
        p(
            "<b>File:</b> services/audit_bridge.py. Methods: <i>log_event()</i>, "
            "<i>get_trail(stay_id)</i>, <i>get_all()</i>, <i>verify_chain()</i>, "
            "<i>stats()</i>. Storage in blockchain/audit_ledger.db with WAL journal. "
            "verify_chain() walks every block and recomputes the chain hash; any "
            "mismatch is reported with the first broken block id.",
            s["body"],
        )
    )

    story.append(p("7.6 API Endpoints", s["h2"]))
    story.append(
        tbl(
            [
                ["Method", "Path", "Purpose"],
                ["GET", "/", "Service banner and helpful links"],
                ["GET", "/health", "Dataset + LSTM artifact status"],
                ["GET", "/metrics", "Prometheus scrape (Grafana)"],
                ["GET", "/patients", "List patient stay_ids"],
                ["GET", "/patient/{id}/history", "Recent vitals (CSV-backed or simulator)"],
                ["POST", "/patient/{id}/tick", "Advance the streaming cursor"],
                ["POST", "/patient/{id}/recommend", "Full pipeline: LSTM + twin + policy"],
                ["POST", "/patient/{id}/audit", "Log Accept/Override/Reject"],
                ["GET", "/patient/{id}/audit_trail", "Patient's audit blocks"],
                ["GET", "/audit/verify", "Verify whole chain integrity"],
                ["POST", "/twin/replay", "Debug deterministic / seeded twin replay (NEW emits TWIN_SIM)"],
                ["POST", "/simulator/session/{stay_id}", "Create simulator session"],
                ["GET", "/simulator/session/{key}/next", "Fetch next simulated record"],
                ["GET", "/simulator/session/{key}/batch", "Fetch N simulated records"],
            ],
            col_widths=[1.5 * cm, 5 * cm, 9.5 * cm],
        )
    )

    story.append(PageBreak())

    # ─── 8. Tests & evaluation summary ──────────────────────────────────────
    story.append(p("8. Test & Evaluation Summary", s["h1"]))
    story.append(
        tbl(
            [
                ["Test File", "Coverage", "Result"],
                ["tests/test_simulator_api.py", "Simulator session + /twin/replay + TWIN_SIM audit + chain verify", "4 / 4 PASS"],
                ["tests/test_digital_twin_replay.py", "Deterministic replay + bound clamping + seeded RNG", "3 / 3 PASS"],
                ["tests/test_digital_twin_safety.py", "16 edge-case physiological extremes", "16 / 16 PASS"],
                ["TOTAL", "", "23 / 23 PASS"],
            ],
            col_widths=[6 * cm, 8 * cm, 2 * cm],
        )
    )
    story.append(p("Quality gates (CI-enforced):", s["h2"]))
    story.append(
        tbl(
            [
                ["Gate command", "Latest result"],
                ["python pipelines/evaluate_digital_twin.py --fail-on-thresholds", "PASS (all 4 thresholds)"],
                ["python pipelines/historical_replay_benchmark.py --fail-on-thresholds", "PASS (teacher 1.69 pp, free 2.87 pp)"],
                ["python -m unittest discover -s tests -p test_*.py", "PASS (23 / 23)"],
            ],
            col_widths=[10 * cm, 6 * cm],
        )
    )

    # ─── 9. How to run ──────────────────────────────────────────────────────
    story.append(p("9. How to Run", s["h1"]))
    story.append(p("9.1 First-time install", s["h2"]))
    story.append(
        p(
            "<font face='Courier' size='9'>"
            "cd 'Major Project'<br/>"
            "python -m pip install --upgrade pip<br/>"
            "python -m pip install -r requirements.txt<br/>"
            "</font>",
            s["body"],
        )
    )
    story.append(p("9.2 Reproducible Phase-1 dataset", s["h2"]))
    story.append(p("<font face='Courier' size='9'>python pipelines/run_phase1.py</font>", s["body"]))
    story.append(p("9.3 Train the LSTM (optional, for real model in dashboard)", s["h2"]))
    story.append(
        p(
            "<font face='Courier' size='9'>"
            "$env:LSTM_ARTIFACTS_DIR = 'ml\\simulated_phase1'<br/>"
            "python ml/lstm_training.py<br/>"
            "</font>",
            s["body"],
        )
    )
    story.append(p("9.4 Start the API", s["h2"]))
    story.append(
        p(
            "<font face='Courier' size='9'>"
            "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000<br/>"
            "# open http://127.0.0.1:8000/docs for Swagger<br/>"
            "</font>",
            s["body"],
        )
    )
    story.append(p("9.5 Open the dashboard", s["h2"]))
    story.append(
        p(
            "Open <font face='Courier'>frontend/dashboard/index.html</font> directly, or "
            "serve the folder with "
            "<font face='Courier'>python -m http.server 8080</font> and open "
            "<font face='Courier'>http://127.0.0.1:8080</font>.",
            s["body"],
        )
    )
    story.append(p("9.6 Run all tests", s["h2"]))
    story.append(
        p(
            "<font face='Courier' size='9'>python -m unittest discover -s tests -p \"test_*.py\"</font>",
            s["body"],
        )
    )
    story.append(p("9.7 Run both quality gates", s["h2"]))
    story.append(
        p(
            "<font face='Courier' size='9'>"
            "python pipelines/evaluate_digital_twin.py --fail-on-thresholds<br/>"
            "python pipelines/historical_replay_benchmark.py --fail-on-thresholds<br/>"
            "</font>",
            s["body"],
        )
    )
    story.append(p("9.8 Grafana / Prometheus stack (optional)", s["h2"]))
    story.append(
        p(
            "<font face='Courier' size='9'>"
            "cd deploy<br/>"
            "docker compose up -d<br/>"
            "# Grafana http://localhost:3000 admin/admin<br/>"
            "</font>",
            s["body"],
        )
    )

    story.append(PageBreak())

    # ─── 10. Risks & mitigations ────────────────────────────────────────────
    story.append(p("10. Risks and Mitigations", s["h1"]))
    story.append(
        tbl(
            [
                ["Risk", "Mitigation in code today"],
                ["Data quality - missing or noisy fields", "Schema validation + interpolation + fall-back heuristic when min_history_points not met"],
                ["Model drift", "LSTM service reports artifact dir + load_error in /health; retraining is one CLI invocation"],
                ["Unsafe recommendation", "Hard bounds clamped in twin and policy; CRITICAL alert + safety_flags strings; clinician-in-the-loop required"],
                ["Latency", "Twin is pure NumPy (sub-ms); LSTM lazy-loaded once at first inference"],
                ["Audit overhead", "SQLite WAL journal; payload hashed once per call; verify_chain is a single linear scan"],
                ["Tampering with audit DB", "SHA-256 chain links every block; verify_chain identifies first broken block"],
            ],
            col_widths=[5 * cm, 11 * cm],
        )
    )

    # ─── 11. Innovation pack ────────────────────────────────────────────────
    story.append(p("11. Innovation Highlights", s["h1"]))
    bullets = [
        "Deterministic + seeded-stochastic twin replay - byte-identical regression checks across code changes (rare in clinical-AI prototypes).",
        "Two-tier evaluation - synthetic-scenario gate plus real-data historical-trajectory gate, both CI-enforced.",
        "Edge-case safety regression battery - 16 tests bombarding the twin with infinities, empty calibration, severe hypoxia, etc.",
        "TWIN_SIM events on the audit chain - every what-if call is itself an immutable record, not just the final recommendation.",
        "Single-file dashboard - no React build pipeline, minimum reviewer friction.",
        "Heuristic LSTM fallback - if Keras artefacts are absent the API still produces sane forecasts so the demo never breaks.",
        "Same-port Prometheus /metrics - Grafana sees gauges live without a sidecar exporter.",
    ]
    for x in bullets:
        story.append(b(x, s["bullet"]))

    # ─── 12. What's next ────────────────────────────────────────────────────
    story.append(p("12. Roadmap (Recommended Next Steps)", s["h1"]))
    story.append(
        tbl(
            [
                ["Priority", "Task", "Effort"],
                ["1", "Phase 3 closeout - reports/model-evaluation-lstm.md with calibration plot, ROC/PR, KPI verification", "1-2 days"],
                ["2", "Phase 7 ablation harness - latency, packet-loss, twin vs no-twin, LSTM-only vs LSTM+PPO", "3-5 days"],
                ["3", "Phase 4 real PPO via Stable-Baselines3 in twin gym env, plus reward-design.md", "5-7 days"],
                ["4", "Phase 6 polish - full docker-compose, real SHAP, integration-architecture.md", "2-3 days"],
                ["5", "Phase 5 polish - emit ALERT + MODEL_INFER events, onchain-offchain-policy.md", "1-2 days"],
                ["6", "Phase 8 packaging - final report, presentation deck, demo runbook, viva Q&A", "5-7 days"],
            ],
            col_widths=[1.6 * cm, 11.4 * cm, 3 * cm],
        )
    )

    # ─── 13. Glossary ────────────────────────────────────────────────────────
    story.append(p("13. Glossary", s["h1"]))
    story.append(
        tbl(
            [
                ["Term", "Definition"],
                ["PEEP", "Positive End-Expiratory Pressure (cmH2O). Keeps alveoli open during exhalation."],
                ["FiO2", "Fraction of Inspired Oxygen (%). 21% is room air; 100% is pure oxygen."],
                ["Tidal Volume (TV)", "Volume of air delivered per breath (mL). Lung-protective target ~6 mL/kg IBW."],
                ["SpO2", "Pulse oximeter reading - peripheral oxygen saturation (%). Normal 95-100."],
                ["Hypoxia", "Insufficient oxygen at tissue level. Operationally: SpO2 < 90%."],
                ["ARDS", "Acute Respiratory Distress Syndrome. Stiff, leaky lungs; low compliance."],
                ["COPD", "Chronic Obstructive Pulmonary Disease. Air-trapping; lower SpO2 baseline."],
                ["VILI", "Ventilator-Induced Lung Injury - barotrauma / volutrauma from over-distension."],
                ["LSTM", "Long Short-Term Memory recurrent neural network. Used here for time-series SpO2 forecasting."],
                ["PPO", "Proximal Policy Optimization - on-policy RL algorithm. Currently a rule-based stand-in."],
                ["AUROC", "Area Under the Receiver Operating Characteristic curve. Project KPI target > 0.85."],
                ["Hash chain", "Linked SHA-256 blocks where each block hash depends on the previous block - any tampering is detectable."],
                ["Digital twin", "Mathematical model of a specific physical entity (here a patient's lungs)."],
            ],
            col_widths=[3.5 * cm, 12.5 * cm],
        )
    )

    # ─── 14. Acknowledgements ────────────────────────────────────────────────
    story.append(p("14. Closing Notes", s["h1"]))
    story.append(
        p(
            "This document is a snapshot of the project state as of "
            f"{date.today().isoformat()}. The repository is the source of truth - "
            "all numbers in this report can be reproduced by running the commands in "
            "Section 9. Phase 2 (Digital Twin) is fully closed; the next focus is "
            "Phase 3 LSTM evaluation report writing, followed by the Phase 7 "
            "ablation study which will produce the headline KPIs against which the "
            "project's success criteria are graded.",
            s["body"],
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        p(
            "<i>End of report.</i>",
            s["subtitle"],
        )
    )

    return story


def main():
    s = build_styles()
    doc = BaseDocTemplate(
        OUT_PATH,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.8 * cm,
        title="Blockchain-Enabled Digital Twin - Project Report",
        author="Rishav Kumar",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main",
    )
    template = PageTemplate(id="all", frames=[frame], onPage=on_page)
    doc.addPageTemplates([template])

    story = build_story(s)
    doc.build(story)

    size = os.path.getsize(OUT_PATH)
    print(f"Wrote {OUT_PATH} ({size/1024:.1f} kB)")


if __name__ == "__main__":
    main()
