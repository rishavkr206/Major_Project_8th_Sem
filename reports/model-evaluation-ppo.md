# PPO Optimization Agent — Model Evaluation Report

**Phase 4 deliverable** — Blockchain-Enabled Digital Twin Framework
**Last updated:** 2026-05-09
**Trainable model artifact:** `ml/models/ppo_policy.zip` (produced by
`ml/ppo_training.py`; not committed)
**Runtime policy code:** `services/ppo_policy.py`

---

## 1. Two-Layer Policy Design

The recommendation engine deliberately separates a **safety-constrained
clinical layer** from the **learned policy layer**:

1. **Layer A — `services/ppo_policy.PPOPolicy`** (always live).
   Rule-based ARDS-Network-inspired adjustments with hard safety bounds,
   digital-twin validation, and explicit rationale strings. This is what
   ships to clinicians and is what every audit-log event captures.

2. **Layer B — Stable-Baselines3 PPO agent** (trained via
   `ml/ppo_training.py`). A `gymnasium.Discrete(9)` action space over
   clinician-style adjustments, run inside a `VentilatorTwinEnv` whose
   dynamics are driven by the Phase-2 `DigitalTwin` and ground truth from
   the Phase-1 `VentilatorDataSimulator`.

The rationale for this split is documented in `docs/safety-constraints.md`:
the PPO agent is **never** allowed to bypass Layer A's hard bounds, and
its proposed action is rejected if it falls outside `HARD_BOUNDS` after
clamping. This trades some on-paper return for a strong upper bound on
unsafe action probability.

---

## 2. Environment Specification

| Field | Value |
| --- | --- |
| Observation | `[SpO2, PEEP, FiO2, TidalVol, HR, MAP, RespRate]`, dtype float32 |
| Action space | `Discrete(9)` — `HOLD`, ±step on PEEP/FiO2/TV, plus `DEESC`/`ESCAL` combos |
| Step size | PEEP ±1 cmH2O, FiO2 ±5%, TV ±25 mL |
| Episode length | 96 steps (24h @ 15 min) |
| Warmup history | 24 steps for twin calibration |
| Termination | Hard fail at SpO2 < 80 |
| Profiles trained on | `normal`, `ards`, `copd` (round-robined across n_envs) |

Reward shaping (full source: `ml/ppo_training.compute_reward`):

```
+1.0   in target band (94–98%)
-5.0   hypoxia penalty (<90%), scaled by depth
-0.6+  VILI penalty (TV > 600 mL)
-0.4+  PEEP penalty (> 15 cmH2O)
-0.3+  FiO2 toxicity penalty (> 80%)
-0.3   hyperoxia drift (SpO2 > 99 with FiO2 > 60)
```

---

## 3. Headline Results (vs Clinical Baselines)

Sourced from `reports/benchmark-results.md` (regression-tested via
`tests/test_digital_twin_safety.py` and `tests/test_digital_twin_replay.py`).

| Metric | Static Protocol | Rule-Based Twin (Layer A only) | **PPO + Twin (Layer A + B)** |
| --- | --- | --- | --- |
| Avg time in hypoxia (<90%) | 12.4% | 8.2% | **4.9%** |
| Time in target SpO2 (94–98%) | 65.2% | 76.5% | **88.1%** |
| Alarms / 24h / patient | 14 | 8 | **3** |
| Audit traceability | 0% | 100% | **100%** |

Ablation (also in `reports/ablation-study.md`):

- **Without Digital Twin** the agent triggered hypotension alerts in 14% of
  cases by recommending unsafe PEEP escalations. The Digital Twin clamped
  these.
- **Without LSTM forecaster** the system became reactive only and time in
  target SpO2 fell from 88.1% to 74.2%.

---

## 4. Smoke / Acceptance Test

`ml/ppo_training.py --smoke` exercises the env contract with random
actions and no SB3 dependency. It confirms:

- 48 random actions execute without raising.
- All actions stay within `SAFE_BOUNDS` after clamping.
- The simulator + twin handoff produces a finite SpO2 trajectory.
- Action-distribution histogram is logged for sanity checking.

This path is what CI runs; full RL training is run manually because of its
wall-clock cost.

---

## 5. Training Loop Details

```bash
python ml/ppo_training.py --timesteps 50000 --n-envs 4 \
       --profile-mix normal,ards,copd --seed 42
```

| Hyperparameter | Value |
| --- | --- |
| Algorithm | PPO (Stable-Baselines3 ≥ 2.0) |
| Policy net | `MlpPolicy`, `[128, 128]` |
| Learning rate | 3e-4 |
| `n_steps` per rollout | 256 |
| Batch size | 64 |
| Gamma | 0.99 |
| Vector envs | 4 (DummyVecEnv + VecMonitor) |

Artifacts written:

- `ml/models/ppo_policy.zip` — SB3 model archive.
- `ml/models/ppo_train_metadata.json` — config, action table, train wall time.

---

## 6. Safety Behaviors

The recommendation pipeline (`api/main.get_recommendation`) enforces the
following invariants regardless of which policy layer fires:

- All proposed `(PEEP, FiO2, TidalVol)` are clamped to `HARD_BOUNDS` in
  `services/ppo_policy.PPOPolicy._clamp`.
- Every recommendation runs through `DigitalTwin.simulate(...)` and the
  twin's `risk_flag` and `tv_risk` are appended to the recommendation
  payload as `safety_flags`.
- `alert_level ∈ {STABLE, WARNING, CRITICAL}` is derived from
  `(curr_spo2, hypoxia_prob)` and surfaced in the dashboard so a
  clinician override is always one click away.
- Every recommendation event is appended to the off-chain hash chain
  (`services/audit_bridge.AuditBridge.log_event`) with `event_type =
  RECOMMENDATION`, and Phase-5 anchoring (`services/chain_anchor`)
  commits the chain tip on-chain in batches.

---

## 7. Open Questions / Deferred Work

- We currently report ablation numbers from an internal scenario sweep,
  not from a third-party clinical replay corpus. Re-running on
  PhysioNet's MIMIC-IV waveform subset is on the Phase 7 backlog.
- The reward function does not yet penalize **action churn** (frequent
  small adjustments). In informal testing the agent prefers `HOLD`
  ~60% of the time, but adding an explicit churn term would make this
  property monotone in the hyperparameter.
- Layer B's policy outputs are not yet shown to the clinician as a
  separate "AI suggestion" alongside Layer A's rule-based recommendation.
  This is a UI deliverable for Phase 6.

---

## 8. Sign-Off Criteria for Phase 4 (Met)

- [x] PPO training script runs against the Phase-2 twin environment.
- [x] Discrete action space restricted to safe clinician-style steps.
- [x] All proposed actions guaranteed inside `HARD_BOUNDS`.
- [x] Smoke path runs without GPU / SB3 (`--smoke`).
- [x] Trained agent + rule-based fallback wired into `api/main` and
      logged to the audit ledger.
- [x] Time-in-target SpO2 ≥ 85% on simulated ARDS profile — **88.1%**.
- [x] Hypoxia fraction ≤ 6% on simulated ARDS profile — **4.9%**.
