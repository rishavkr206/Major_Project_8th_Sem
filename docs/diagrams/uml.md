# UML Diagrams

## Use Case Diagram

```mermaid
usecaseDiagram
    actor Clinician
    actor System

    Clinician --> (View Patient State)
    Clinician --> (Review Recommendation)
    Clinician --> (Accept or Override Recommendation)
    Clinician --> (Inspect Audit Trail)

    System --> (Ingest Telemetry)
    System --> (Forecast Risk)
    System --> (Run Twin Simulation)
    System --> (Generate PPO Action)
    System --> (Write Audit Event)
```

## Sequence Diagram: Recommendation Cycle

```mermaid
sequenceDiagram
    actor Clinician
    participant Dashboard
    participant API
    participant LSTM
    participant Twin
    participant PPO
    participant Audit

    Clinician->>Dashboard: Request recommendation
    Dashboard->>API: POST recommend(payload)
    API->>LSTM: predict risk and next SpO2
    API->>Twin: simulate candidate settings
    LSTM-->>API: forecast output
    Twin-->>API: simulation delta and uncertainty
    API->>PPO: compute bounded action
    PPO-->>API: recommendation and confidence
    API->>Audit: log recommendation hash
    Audit-->>API: event proof
    API-->>Dashboard: recommendation + proof
    Clinician->>Dashboard: accept/override
    Dashboard->>API: POST audit(action)
    API->>Audit: append clinician event
```

## Class Diagram: Core Components

```mermaid
classDiagram
    class VentilatorDataSimulator {
        +next_record(stay_id)
        +generate_batch(stay_id, steps)
    }

    class DigitalTwin {
        +calibrate(history)
        +simulate(proposed, current_spo2)
    }

    class PPOPolicy {
        +recommend(current_vitals, pred_spo2, hypoxia_prob)
    }

    class AuditBridge {
        +log_event(event_type, stay_id, payload, actor)
        +verify_chain()
        +get_trail(stay_id)
    }

    class APIServer {
        +create_simulator_session()
        +simulator_next_record()
        +simulator_batch()
        +get_recommendation()
        +log_clinician_action()
    }

    APIServer --> VentilatorDataSimulator
    APIServer --> DigitalTwin
    APIServer --> PPOPolicy
    APIServer --> AuditBridge
```
