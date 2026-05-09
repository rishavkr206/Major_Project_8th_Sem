# Ablation Study — Component Contribution Analysis

**Phase 7 deliverable** — Blockchain-Enabled Digital Twin Framework
**Last updated:** 2026-05-09

This document complements `reports/benchmark-results.md` (which compares
the full system against external baselines) by isolating the contribution
of **each internal component** through systematic removal.

---

## 1. Configurations Under Test

| ID | Digital Twin | LSTM Forecaster | PPO Layer B | Audit + On-chain Anchor |
| --- | --- | --- | --- | --- |
| A0 (full system) | ✓ | ✓ | ✓ | ✓ |
| A1 (no twin)     | ✗ | ✓ | ✓ | ✓ |
| A2 (no LSTM)     | ✓ | ✗ | ✓ | ✓ |
| A3 (no PPO)      | ✓ | ✓ | ✗ (rule layer only) | ✓ |
| A4 (no audit)    | ✓ | ✓ | ✓ | ✗ |
| A5 (rule-only baseline) | ✗ | ✗ | ✗ (rule layer only) | ✓ |

All configurations were exercised against the same simulated cohort:
12 ARDS profile stays × 96 steps (24 h @ 15 min sampling), seed 42.

---

## 2. Headline Results

| Config | Time in target SpO2 (94–98%) | Hypoxia time (<90%) | Mean alarms / 24h | Unsafe actions clamped |
| --- | --- | --- | --- | --- |
| **A0 (full)** | **88.1%** | **4.9%** | **3** | 0 |
| A1 (no twin)  | 80.4% | 7.1% | 6 | **14% of actions clamped externally would have been unsafe** |
| A2 (no LSTM)  | 74.2% | 9.6% | 9 | 0 |
| A3 (no PPO)   | 76.5% | 8.2% | 8 | 0 |
| A4 (no audit) | 88.1% | 4.9% | 3 | 0 (operationally identical to A0; differs only off-clinical) |
| A5 (rule baseline) | 65.2% | 12.4% | 14 | 0 |

---

## 3. Per-Component Contribution

### 3.1 Digital Twin (A0 vs A1)

- **+7.7 pp** time in target.
- **−2.2 pp** hypoxia.
- **14% of recommended actions** would have exceeded a safety bound
  (PEEP escalations causing simulated hypotension) without twin
  pre-validation. The twin is therefore the dominant **safety**
  contributor, not the dominant **performance** contributor.

### 3.2 LSTM Forecaster (A0 vs A2)

- **+13.9 pp** time in target.
- **−4.7 pp** hypoxia.
- **−6** alarms / 24h.
- The LSTM is the dominant **performance** contributor: removing it
  forces the system into reactive control, where parameters only adjust
  *after* desaturation, not *before*. This is the largest single delta in
  the table.

### 3.3 PPO Layer B (A0 vs A3)

- **+11.6 pp** time in target.
- **−3.3 pp** hypoxia.
- **−5** alarms / 24h.
- The PPO agent picks **smaller, more frequent adjustments** than the
  rule layer alone, which is why the alarm count drops so much: most
  alarms in A3 were "approaching threshold" trends that the rule layer
  did not adjust early enough.

### 3.4 Audit + On-chain Anchor (A0 vs A4)

- **No clinical-metric difference**, by design.
- **Failure-mode difference:** in A4 we cannot retroactively prove a
  recommendation set was issued by the system at a particular time,
  cannot prove the off-chain ledger was not edited, and cannot run
  Phase-5's `verify_chain()` integrity check against an on-chain anchor.
- This is a regulatory / forensic capability, not a clinical KPI.

### 3.5 Rule-only baseline (A5)

- The naked baseline. Establishes the lower bound: a system with **none**
  of our contributions delivers 65.2% time in target and 12.4% hypoxia
  fraction, comparable to a static ARDSnet protocol.

---

## 4. Sensitivity to Profile

Same A0/A2/A3 lineup, run separately on `normal`, `ards`, and `copd`
profiles (12 stays each). Numbers are **time in target SpO2 (94–98%)**:

| Profile | A0 (full) | A2 (no LSTM) | A3 (no PPO) |
| --- | --- | --- | --- |
| normal | 96.4% | 91.2% | 92.8% |
| ards   | 88.1% | 74.2% | 76.5% |
| copd   | 81.7% | 67.9% | 71.2% |

The LSTM and PPO contributions both **grow** with profile difficulty —
they are most useful precisely on the patients who matter most.

---

## 5. Failure-Recovery Coupling

For each component, what happens if it **fails at runtime** (rather than
being absent at design time):

| Failure | Detected by | Fallback path |
| --- | --- | --- |
| LSTM artifact missing | `LSTMForecaster.status()` | Heuristic SpO2 estimate; `lstm_forecast_source = "heuristic"` set in response and Prometheus metric |
| Twin calibration NaN | `DigitalTwin.calibrate` zero-history guard | Twin uses last cached `(PEEP, FiO2, TV)` baseline; `is_calibrated = False` flagged |
| PPO Layer B import error | `try/except ImportError` in trainer | Layer A (rule policy) continues unaffected |
| Audit DB lock | SQLite WAL mode | Subsequent inserts queue; integrity preserved |
| On-chain RPC failure | `chain_anchor.post_anchor_onchain` raises | `dry_run` mode keeps batching; no off-chain data lost |

These are tested by `tests/test_digital_twin_safety.py` and
`tests/test_digital_twin_replay.py`.

---

## 6. Conclusions

1. **Performance** is dominated by the LSTM forecaster.
2. **Safety** is dominated by the Digital Twin.
3. **Trust / forensic** is dominated by the audit + on-chain anchor.
4. **PPO Layer B** delivers a meaningful but incremental gain on top of
   the rule-based Layer A — its main contribution is fewer, smaller
   adjustments rather than fundamentally different decisions.
5. The components are **complementary** rather than redundant: removing
   any one of them produces a measurable degradation in a different
   axis than removing the others. The system is therefore minimal in
   the sense that no component can be cut without giving up something
   that no other component recovers.

---

## 7. Reproducibility

All ablation runs are driven by:

```bash
python pipelines/historical_replay_benchmark.py --ablation A0 A1 A2 A3 A5 \
       --profiles normal,ards,copd --stays-per-profile 12 --steps 96 --seed 42
```

Outputs go to `reports/twin_historical_replay.json`, which is the source
of truth for the numbers above.
