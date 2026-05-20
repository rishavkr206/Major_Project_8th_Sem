# 2-Minute Viva Script (Click-by-Click)

Use this exactly during your faculty demo. Speak slowly and keep your mouse actions synchronized with each line.

## 0:00-0:15 | Opening

"Good morning. This project is a blockchain-enabled digital twin framework for ventilator optimization. It combines time-series forecasting, AI recommendation support, twin-based safety simulation, and tamper-evident audit logging."

"I will show a live end-to-end run in under two minutes."

## 0:15-0:30 | System Is Live

Action:
- Open `http://127.0.0.1:8001/health`

Say:
"This endpoint confirms the backend is running, dataset is loaded, and model artifact status is available."

"So first, we validate system readiness before clinical workflow."

## 0:30-1:00 | Frontend Overview

Action:
- Open `http://127.0.0.1:5173`
- Go to Live ICU page

Say:
"This is the main React clinical dashboard."

"Here we can observe patient vitals, model forecast context, PPO-based recommendation, and digital twin simulation output in one operator view."

"The purpose is decision support, not autonomous control. Clinician remains in charge."

## 1:00-1:25 | Recommendation + Safety Layer

Action:
- Select a patient
- Trigger recommendation flow

Say:
"When a recommendation is generated, the policy proposes adjustments, for example FiO2 or PEEP changes."

"Before trusting this action, the digital twin simulates physiological response."

"If risk is detected, confidence drops and the recommendation is flagged. So safety is enforced before action."

## 1:25-1:45 | Validation + Metrics

Action:
- Open Test Lab tab
- Open Model Metrics tab

Say:
"Test Lab runs deterministic scenarios to check behavior under controlled conditions."

"Model Metrics shows evaluation reports, so this is evidence-backed performance rather than only visual output."

## 1:45-2:00 | Audit + Closing

Action:
- Open Audit/System tab

Say:
"Every recommendation and clinician action is captured in a tamper-evident chain for accountability and medico-legal traceability."

"In summary: prediction, recommendation, simulation-based safety, and auditability are integrated in one workflow."

"Thank you. I can now explain architecture, model choices, and deployment."

---

# 30-Second Backup Script (If Time Is Cut)

"This system provides ICU decision support for ventilator management. We stream patient vitals, forecast risk, generate PPO recommendations, validate them in a digital twin before use, and log all actions in a tamper-evident audit chain. The result is safer, explainable, and accountable AI-assisted ventilation workflow."

---

# Faculty Q&A One-Liners

## Why digital twin?
"To test AI recommendations in a physiological sandbox before clinical acceptance, reducing unsafe actions."

## Why blockchain-like audit?
"To make recommendation history tamper-evident for accountability and post-event traceability."

## Is clinician replaced?
"No. This is decision support. Final decision always remains with clinician."

## Is this real-time?
"Yes for inference-level decision support. The architecture supports near real-time bedside workflow."

## What is your key contribution?
"Integrating forecasting, RL recommendation, twin safety validation, and tamper-evident auditing into one practical pipeline."
