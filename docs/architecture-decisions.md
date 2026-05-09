# Architecture Decision Records (ADRs)

## ADR-001: Monorepo with Service-Oriented Modules

- **Status:** Accepted
- **Decision:** Keep simulator, API, ML pipeline, digital twin, PPO, and audit bridge in one repository with clear module separation.
- **Rationale:** Faster development for final-year timeline while preserving service boundaries for future split.
- **Consequence:** Easier local iteration; moderate coupling risk managed by folder/module boundaries.

## ADR-002: FastAPI as Integration Surface

- **Status:** Accepted
- **Decision:** Use FastAPI as the primary orchestration and serving layer for recommendations, streaming simulation, and audit endpoints.
- **Rationale:** Lightweight async framework with easy schema-first endpoint evolution.
- **Consequence:** API layer can later expose gRPC/REST gateway if needed.

## ADR-003: Synthetic-First Data Strategy

- **Status:** Accepted
- **Decision:** Implement configurable simulator profiles (normal/ARDS/COPD/unstable) before full live-feed coupling.
- **Rationale:** Enables reproducible experimentation and controlled scenario coverage.
- **Consequence:** Must maintain clear schema parity with eventual real telemetry interfaces.

## ADR-004: Canonical Event Schema Contract

- **Status:** Accepted
- **Decision:** Standardize telemetry payload fields and bounds in `docs/event-schema.md`, and validate generated records at runtime.
- **Rationale:** Prevents silent data drift and ingestion incompatibilities.
- **Consequence:** Schema changes require coordinated updates across simulator, ingestion, and model services.

## ADR-005: SQLite Hash-Linked Audit Ledger for Prototype

- **Status:** Accepted
- **Decision:** Use hash-linked event records in local SQLite via audit bridge for prototype immutability proof.
- **Rationale:** Practical and fast for local development while preserving integrity semantics.
- **Consequence:** Future migration path to smart contract chain required for production-grade deployment.

## ADR-006: CLI-Driven Reproducible Feature Pipeline

- **Status:** Accepted
- **Decision:** Parameterize feature engineering pipeline using CLI arguments for input path/output directory/sequence length.
- **Rationale:** Supports both historical and simulated datasets with one pipeline.
- **Consequence:** Requires runbook discipline and scripted invocation for repeatability.
