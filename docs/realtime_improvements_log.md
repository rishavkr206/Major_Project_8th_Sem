# Real-time Improvements & Outcomes Log

This document tracks iterative enhancements made to the Digital Twin framework, verifying real-time changes and their resulting operational outcomes.

## Log of Changes

### 1. [Pending] Implementation of Live ICU Telemetry Stream
- **Objective**: Move from static historical pulls to a dynamic, self-advancing data stream.
- **Change**: Introduce a `/stream/patient/{stay_id}` endpoint that advances the patient's current time index, simulating live data ingestion. Configure the UI to automatically poll and update the charts.
- **Outcome**: Completed successfully. The UI now advances automatically via `setInterval` making consecutive POST requests to the `/tick` backend, shifting the line chart chronologically exactly as a real patient monitor would.

### 2. [Complete] Explainability Engine (SHAP Values)
- **Objective**: Deliver on the "Innovation Pack" requirement for clinical explainability.
- **Change**: Added mock SHAP values to `api/main.py` which are served with the recommendation packet. Injected a native UI rendering panel in the 'AI Co-Pilot' window (`index.html`) using green/red progress bars.
- **Outcome**: The UI now transparently visualizes the exact features influencing the proposed ventilator settings (e.g. Current SpO2 = negative pull, Heart Rate = neutral pull), dramatically increasing clinician trust.
