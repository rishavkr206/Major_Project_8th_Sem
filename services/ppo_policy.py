"""
PPO Policy Service — Ventilator Parameter Recommendation Engine
Blockchain-Enabled Digital Twin Framework

Implements a safe, constrained ventilator recommendation engine.
In academic mode: uses a rule-based policy derived from ARDS Network and
lung-protective ventilation guidelines, augmented with digital twin validation.

Production note: Replace with a trained Stable-Baselines3 PPO agent loaded
from ml/models/ppo_policy.zip for full RL-based recommendations.
"""

import numpy as np
from typing import Dict, Tuple, Optional
from services.digital_twin import DigitalTwin, SAFE_BOUNDS

# ─── Safety Hard Bounds (absolute limits) ────────────────────────────────────
HARD_BOUNDS = {
    'PEEP':     (3.0,  20.0),
    'FiO2':     (21.0, 100.0),
    'TidalVol': (200.0, 800.0),
}

# ─── Action Steps (discrete increments) ──────────────────────────────────────
PEEP_STEP    = 1.0    # cmH2O per adjustment
FIO2_STEP    = 5.0    # percent per adjustment
TV_STEP      = 25.0   # mL per adjustment


class PPOPolicy:
    """
    Clinically constrained ventilator parameter recommendation engine.
    Combines rule-based safety logic with digital twin validation.
    """

    def __init__(self, twin: Optional[DigitalTwin] = None):
        self.twin = twin or DigitalTwin()

    def _clamp(self, value: float, param: str) -> float:
        lo, hi = HARD_BOUNDS[param]
        return float(np.clip(value, lo, hi))

    def _compute_confidence(
        self,
        hypoxia_prob: float,
        pred_spo2: float,
        twin_result: Dict,
    ) -> float:
        """
        Compute recommendation confidence score [0, 1].
        Based on: model certainty + twin predicted improvement.
        """
        # Higher model certainty → higher confidence
        model_certainty = 1.0 - abs(hypoxia_prob - 0.5) * 2  # peaks at 0.5 probability

        # Positive twin delta increases confidence
        delta = twin_result.get('delta_spo2', 0)
        twin_confidence = min(1.0, max(0, delta / 5.0 + 0.5))

        # Risk flag drops confidence
        risk_penalty = 0.3 if twin_result.get('risk_flag') else 0.0

        confidence = (0.5 * (1 - model_certainty) + 0.5 * twin_confidence) - risk_penalty
        return float(np.clip(confidence, 0.05, 0.99))

    def recommend(
        self,
        current_vitals: Dict,
        pred_spo2: float,
        hypoxia_prob: float,
        history: Optional[list] = None,
    ) -> Dict:
        """
        Generate a ventilator parameter recommendation.

        Args:
            current_vitals: dict with SpO2, PEEP, FiO2, TidalVol, HR, MAP, RespRate
            pred_spo2:      LSTM-predicted next SpO2 (unscaled)
            hypoxia_prob:   LSTM-predicted hypoxia probability [0,1]
            history:        list of recent observations for twin calibration

        Returns:
            Recommendation dict with proposed settings, confidence, rationale,
            twin simulation results, and safety flags.
        """
        # ── Calibrate twin ───────────────────────────────────────────────────
        if history:
            self.twin.calibrate(history)
        else:
            self.twin.baseline_spo2    = current_vitals.get('SpO2', 95.0)
            self.twin.last_PEEP        = current_vitals.get('PEEP', 5.0)
            self.twin.last_FiO2        = current_vitals.get('FiO2', 40.0)
            self.twin.last_TidalVol    = current_vitals.get('TidalVol', 450.0)

        curr_spo2   = float(current_vitals.get('SpO2', 95.0))
        curr_PEEP   = float(current_vitals.get('PEEP', 5.0))
        curr_FiO2   = float(current_vitals.get('FiO2', 40.0))
        curr_TV     = float(current_vitals.get('TidalVol', 450.0))
        curr_RR     = float(current_vitals.get('RespRate', 20.0))

        # ── Rule-based policy (ARDS Network inspired) ────────────────────────
        proposed_PEEP = curr_PEEP
        proposed_FiO2 = curr_FiO2
        proposed_TV   = curr_TV
        rationale     = []

        # Critical hypoxia → aggressive support
        if hypoxia_prob > 0.7 or curr_spo2 < 88:
            proposed_PEEP = self._clamp(curr_PEEP + PEEP_STEP * 2, 'PEEP')
            proposed_FiO2 = self._clamp(curr_FiO2 + FIO2_STEP * 2, 'FiO2')
            rationale.append("HIGH hypoxia risk — aggressive increase in PEEP and FiO2.")

        # Moderate risk → moderate increase
        elif hypoxia_prob > 0.4 or curr_spo2 < 93:
            proposed_PEEP = self._clamp(curr_PEEP + PEEP_STEP, 'PEEP')
            proposed_FiO2 = self._clamp(curr_FiO2 + FIO2_STEP, 'FiO2')
            rationale.append("MODERATE hypoxia risk — incremental PEEP and FiO2 increase.")

        # Predicted deterioration from LSTM
        elif pred_spo2 < curr_spo2 - 2:
            proposed_FiO2 = self._clamp(curr_FiO2 + FIO2_STEP, 'FiO2')
            rationale.append("LSTM predicts SpO2 decline — preemptive FiO2 increase.")

        # Recovering patient — wean support (lung-protective)
        elif curr_spo2 > 97 and curr_FiO2 > 40:
            proposed_FiO2 = self._clamp(curr_FiO2 - FIO2_STEP, 'FiO2')
            if curr_PEEP > 5:
                proposed_PEEP = self._clamp(curr_PEEP - PEEP_STEP, 'PEEP')
            rationale.append("Good oxygenation — weaning FiO2 (lung-protective strategy).")

        else:
            rationale.append("Patient stable — maintaining current settings.")

        # TidalVol: target 6 mL/kg IBW (assume 70kg → 420mL)
        if curr_TV > 550:
            proposed_TV = self._clamp(curr_TV - TV_STEP, 'TidalVol')
            rationale.append(f"High tidal volume ({curr_TV:.0f} mL) — reducing for VILI prevention.")
        elif curr_TV < 280:
            proposed_TV = self._clamp(curr_TV + TV_STEP, 'TidalVol')
            rationale.append("Low tidal volume — modest increase for adequate ventilation.")

        # High respiratory rate → check if TV is acceptable
        if curr_RR > 28 and proposed_TV < 400:
            proposed_TV = self._clamp(proposed_TV + TV_STEP, 'TidalVol')
            rationale.append("Elevated RR with low TV — adjusting to prevent breath stacking.")

        # ── Run digital twin simulation ───────────────────────────────────────
        proposed = {
            'PEEP':     proposed_PEEP,
            'FiO2':     proposed_FiO2,
            'TidalVol': proposed_TV,
        }
        twin_result = self.twin.simulate(proposed, curr_spo2, steps=4)

        # ── Confidence ────────────────────────────────────────────────────────
        confidence = self._compute_confidence(hypoxia_prob, pred_spo2, twin_result)

        # ── Safety checks ────────────────────────────────────────────────────
        safety_flags = []
        if proposed_FiO2 > 80:
            safety_flags.append("HIGH FiO2 (>80%) — monitor for O2 toxicity")
        if proposed_PEEP > 15:
            safety_flags.append("HIGH PEEP (>15 cmH2O) — monitor haemodynamics")
        if proposed_TV > 600:
            safety_flags.append("HIGH tidal volume — potential barotrauma risk")
        if twin_result.get('risk_flag'):
            safety_flags.append("Twin simulation predicts ongoing hypoxia — urgent review needed")

        return {
            'current': {
                'PEEP':     curr_PEEP,
                'FiO2':     curr_FiO2,
                'TidalVol': curr_TV,
                'SpO2':     curr_spo2,
            },
            'proposed': {
                'PEEP':     round(proposed_PEEP, 1),
                'FiO2':     round(proposed_FiO2, 1),
                'TidalVol': round(proposed_TV, 1),
            },
            'delta': {
                'PEEP':     round(proposed_PEEP - curr_PEEP, 1),
                'FiO2':     round(proposed_FiO2 - curr_FiO2, 1),
                'TidalVol': round(proposed_TV - curr_TV, 1),
            },
            'confidence':       round(confidence, 3),
            'hypoxia_prob':     round(hypoxia_prob, 4),
            'pred_next_spo2':   round(pred_spo2, 2),
            'twin_simulation':  twin_result,
            'rationale':        rationale,
            'safety_flags':     safety_flags,
            'alert_level': (
                'CRITICAL' if hypoxia_prob > 0.7 or curr_spo2 < 88 else
                'WARNING'  if hypoxia_prob > 0.4 or curr_spo2 < 93 else
                'STABLE'
            ),
        }


# ─── Standalone demo ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    policy = PPOPolicy()

    result = policy.recommend(
        current_vitals={'SpO2': 89, 'PEEP': 8, 'FiO2': 60, 'TidalVol': 400,
                        'HR': 105, 'MAP': 72, 'RespRate': 26},
        pred_spo2=88.5,
        hypoxia_prob=0.72,
    )

    import json
    print(json.dumps(result, indent=2))
