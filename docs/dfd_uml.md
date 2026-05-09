# System Architecture & Diagrams

## 1. System Architecture (Component View)

```mermaid
graph TD
    subgraph ICU Environment
        V[Ventilator]
        P[Patient Monitor]
        C[Clinician]
    end

    subgraph Data Layer
        P -- CSV/Stream --> I[Ingestion Service]
        V -- CSV/Stream --> I
        I --> F[Feature Engineering Pipeline]
    end

    subgraph AI & Simulation Layer
        F --> LSTM[LSTM Forecasting Service]
        F --> DT[Digital Twin Service]
        LSTM -- Next SpO2 & Risk --> PPO[PPO Recommendation Engine]
        DT -- Simulation Delta & Risk --> PPO
    end

    subgraph Blockchain Audit Layer
        PPO -- Recommendation --> AB[Audit Bridge]
        C -- Accept/Override --> AB
        AB --> DB[(SQLite Hash Ledger)]
    end

    subgraph Presentation Layer
        API[FastAPI Backend]
        Dash[Real-time Dashboard UI]
    end

    PPO -.-> API
    LSTM -.-> API
    DT -.-> API
    AB -.-> API
    API <--> Dash
    Dash <--> C
```

---

## 2. Data Flow Diagram (DFD)

### Level 0: Context Diagram

```mermaid
graph TD
    C[Clinician]
    DS[ICU Monitors / Dataset]
    
    SYS((Ventilator Optimization <br> & Digital Twin System))
    
    DS -- Raw Vitals & Settings --> SYS
    SYS -- Predicted SpO2 & Risk --> C
    SYS -- Recommended Settings --> C
    C -- Accept/Override Action --> SYS
    SYS -- Audit Verification --> C
```

### Level 1: Main Process

```mermaid
graph TD
    DS[Dataset / Data Stream]
    C[Clinician]
    
    P1(1.0 Data Preprocessing)
    P2(2.0 LSTM Forecasting)
    P3(3.0 Digital Twin Simulation)
    P4(4.0 RL Recommendation Engine)
    P5(5.0 Dashboard Presentation)
    P6(6.0 Blockchain Audit Logging)
    
    D1[(Processed Features)]
    D2[(Audit Ledger)]
    
    DS --> P1
    P1 --> D1
    D1 --> P2
    D1 --> P3
    D1 --> P4
    
    P2 -- Next SpO2 & Risk --> P4
    P3 -- Simulated Outcomes --> P4
    
    P4 -- Recommendations --> P5
    P2 -- Forecast --> P5
    
    P5 --> C
    C -- Action Event --> P6
    P4 -- Logic Event --> P6
    P6 --> D2
```

---

## 3. UML Diagrams

### Use Case Diagram

```mermaid
usecaseDiagram
    actor Clinician
    actor "System/PPO" as System
    
    Clinician --> (View Patient Trajectory)
    Clinician --> (Review AI Recommendation)
    Clinician --> (Accept Recommendation)
    Clinician --> (Override Recommendation)
    Clinician --> (Verify Audit Chain Integrity)
    
    System --> (Generate Risk Forecast)
    System --> (Simulate Digital Twin)
    System --> (Propose Parameter Tweaks)
    System --> (Write Cryptographic Hash to Ledger)
```

### Sequence Diagram: Recommendation & Audit Flow

```mermaid
sequenceDiagram
    actor Clinician
    participant UI as Dashboard
    participant API as FastAPI
    participant AI as LSTM/PPO Engine
    participant Twin as Digital Twin
    participant Chain as Audit Ledger

    Clinician->>UI: Select Patient
    UI->>API: GET /history
    API-->>UI: Return recent vitals
    UI->>API: POST /recommend
    API->>AI: Predict risk & generate params
    AI->>Twin: Run What-If Simulation
    Twin-->>AI: Return simulated SpO2 delta
    AI-->>API: Confidence & Proposed Settings
    API->>Chain: Log Event (RECOMMENDATION)
    Chain-->>API: Return Block Hash
    API-->>UI: Display AI Co-Pilot UI
    
    Clinician->>UI: Clicks "Accept"
    UI->>API: POST /audit (Action: Accept)
    API->>Chain: Log Event (CLINICIAN_ACCEPT)
    Chain-->>API: Return Block Hash
    API-->>UI: Success
```

### Class Diagram: Core Backend Logic

```mermaid
classDiagram
    class DigitalTwin {
        +float compliance_factor
        +float uncertainty
        +calibrate(history: List[Dict])
        +simulate(proposed, current_spo2): Dict
        -_spo2_from_settings(): float
    }
    
    class PPOPolicy {
        +DigitalTwin twin
        +recommend(current, pred_spo2, risk): Dict
        -_compute_confidence(risk, twin_result): float
        -_clamp(value, param): float
    }
    
    class AuditBridge {
        +String ledger_path
        +log_event(event_type, payload, actor): Dict
        +verify_chain(): Tuple[bool, String]
        +get_trail(stay_id): List[Dict]
        -_sha256(data): String
    }
    
    class API_Server {
        +get_patient_history()
        +get_recommendation()
        +log_clinician_action()
    }
    
    API_Server --> DigitalTwin
    API_Server --> PPOPolicy
    API_Server --> AuditBridge
    PPOPolicy --> DigitalTwin
```
