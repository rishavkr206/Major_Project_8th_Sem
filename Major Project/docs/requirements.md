# Requirements Specification

## Purpose

Define functional and non-functional requirements for the blockchain-enabled digital twin ventilator decision support system.

## Functional Requirements

- **FR-01 Data ingestion:** System shall ingest patient vitals and ventilator settings from simulator or dataset stream in near real time.
- **FR-02 Schema validation:** System shall validate incoming telemetry against canonical event schema before downstream processing.
- **FR-03 Feature extraction:** System shall generate sequence features suitable for LSTM forecasting and PPO policy inputs.
- **FR-04 Forecasting:** System shall estimate short-horizon respiratory risk indicators, including `Next_SpO2` and hypoxia risk.
- **FR-05 Digital twin simulation:** System shall run what-if simulations for proposed ventilator parameter changes.
- **FR-06 Recommendation generation:** System shall provide safe, bounded ventilator setting recommendations.
- **FR-07 Clinician interaction:** System shall support recommendation acceptance, rejection, and override capture.
- **FR-08 Auditability:** System shall record recommendation and clinician action events with immutable verification metadata.
- **FR-09 Dashboard visibility:** System shall display trajectory/history, recommendations, confidence, and audit trail status.
- **FR-10 Verification endpoint:** System shall expose an endpoint to verify integrity of audit chain records.

## Non-Functional Requirements

- **NFR-01 Latency:** Inference and recommendation path target under 2 seconds for prototype environment.
- **NFR-02 Reliability:** Pipeline must tolerate packet loss and noisy telemetry without crashing.
- **NFR-03 Reproducibility:** Synthetic data generation and feature splits must be reproducible via seeded configuration.
- **NFR-04 Security baseline:** Audit records must include deterministic hash linkage for tamper evidence.
- **NFR-05 Maintainability:** Core services must be modular (API, simulator, twin, policy, audit).
- **NFR-06 Testability:** API simulator lifecycle must have automated tests for core success/failure paths.

## Assumptions

- Prototype operates in clinician-in-the-loop mode (no autonomous actuation).
- Initial implementation targets simulated/historical data, not live hospital integration.
- SQLite-backed audit ledger is acceptable for prototype traceability.

## Traceability to Current Implementation

- Implemented: FR-01, FR-02, FR-03 (pipeline path), FR-06 (existing PPO service), FR-08, FR-10.
- In progress: FR-04 and FR-05 integration refinement into full end-to-end API flow.
- Pending: advanced dashboard and deployment orchestration hardening for final integration phase.
