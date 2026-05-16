"""
Digital Twin Simulation Service
Blockchain-Enabled Digital Twin Framework

Implements a simplified respiratory mechanics model that maps ventilator
settings (PEEP, FiO2, TidalVol) + patient vitals to predicted SpO2 trajectory.

Model basis:
  - PEEP provides alveolar recruitment → raises mean SpO2
  - FiO2 directly controls inspired oxygen fraction → primary SpO2 driver
  - TidalVol drives VT/kg ratio → too high induces VILI risk
  - Patient PaO2/FiO2 ratio is estimated from SpO2 via Severinghaus equation
"""

import numpy as np
from typing import Dict, List, Optional

# ─── Safety Bounds ────────────────────────────────────────────────────────────
SAFE_BOUNDS = {
    'PEEP':     (3.0,  20.0),   # cmH2O
    'FiO2':     (21.0, 100.0),  # percent
    'TidalVol': (200.0, 800.0), # mL
}

# ─── Physics Parameters ───────────────────────────────────────────────────────
PEEP_SPO2_COEF   = 0.35   # delta PEEP cmH2O → SpO2% effect
FIO2_SPO2_COEF   = 0.18   # delta FiO2% → SpO2% effect
TV_OPTIMAL       = 450.0  # mL optimal tidal volume plateau
TV_PENALTY_HIGH  = 0.005  # penalty per mL above optimal (barotrauma)
MEAN_REVERSION   = 0.45   # fraction of SpO2 gap corrected per step


class DigitalTwin:
    """
    Patient-specific digital twin for respiratory mechanics simulation.
    Calibrated from recent observation window to estimate patient compliance.
    """

    def __init__(self, stay_id: int = None):
        self.stay_id         = stay_id
        self.compliance_factor = 1.0  # patient lung compliance (0.5=poor, 1.5=good)
        self.baseline_spo2   = 98.0
        self.last_PEEP       = 5.0
        self.last_FiO2       = 40.0
        self.last_TidalVol   = 450.0
        self.is_calibrated   = False
        self.uncertainty     = 1.5    # ±1 SpO2 unit default

    def calibrate(self, history: List[Dict]) -> None:
        """
        Fit twin parameters from recent patient history (last N observations).
        history: list of dicts with keys HR, MAP, RespRate, SpO2, PEEP, FiO2, TidalVol
        """
        if not history:
            return

        recent = history[-12:]  # last 3 hours
        spo2s  = [r['SpO2'] for r in recent]
        peeps  = [r['PEEP'] for r in recent]
        fio2s  = [r['FiO2'] for r in recent]

        self.baseline_spo2 = float(np.mean(spo2s))
        self.last_PEEP     = float(np.mean(peeps))
        self.last_FiO2     = float(np.mean(fio2s))
        self.last_TidalVol = float(np.mean([r['TidalVol'] for r in recent]))

        # Estimate compliance from SpO2 variability
        spo2_std = float(np.std(spo2s)) if len(spo2s) > 1 else 1.0
        # Higher variability → less stable lung → lower compliance
        self.compliance_factor = max(0.4, 1.0 - spo2_std / 20.0)
        self.uncertainty = max(0.5, spo2_std * 0.8 + 0.5)
        self.is_calibrated = True

    def _spo2_from_settings(
        self,
        PEEP: float,
        FiO2: float,
        TidalVol: float,
        current_spo2: float,
    ) -> float:
        """
        Predict equilibrium SpO2 given ventilator settings.
        Uses simplified ALI/ARDS-inspired response model.
        """
        # FiO2 and PEEP are modeled as changes from calibrated baseline settings.
        fio2_delta = FiO2 - self.last_FiO2
        peep_delta = PEEP - self.last_PEEP
        fio2_contribution = fio2_delta * FIO2_SPO2_COEF * self.compliance_factor
        peep_contribution = peep_delta * PEEP_SPO2_COEF * self.compliance_factor

        # TidalVol penalty (VILI above optimal)
        tv_delta = max(0, TidalVol - TV_OPTIMAL)
        tv_penalty = tv_delta * TV_PENALTY_HIGH

        # Target equilibrium SpO2 anchored to calibrated baseline.
        spo2_target = self.baseline_spo2 + fio2_contribution + peep_contribution - tv_penalty
        spo2_target = np.clip(spo2_target, 60.0, 100.0)

        # Mean reversion from current value
        spo2_next = current_spo2 + MEAN_REVERSION * (spo2_target - current_spo2)
        return float(np.clip(spo2_next, 60.0, 100.0))

    def simulate(
        self,
        proposed: Dict[str, float],
        current_spo2: float,
        steps: int = 4,
        noise_scale: float = 1.0,
        rng: Optional[np.random.Generator] = None,
    ) -> Dict:
        """
        Run what-if simulation for proposed ventilator changes.

        Args:
            proposed:    dict with PEEP, FiO2, TidalVol (proposed new settings)
            current_spo2: current observed SpO2
            steps:       number of 15-min steps to simulate (default=4 = 1 hour)
            noise_scale: multiplicative factor for uncertainty noise (0 disables noise)
            rng:         optional numpy random generator for deterministic replay tests

        Returns:
            dict with trajectory, mean, uncertainty, delta, risk_flag
        """
        if steps < 1:
            raise ValueError("steps must be >= 1")
        if noise_scale < 0:
            raise ValueError("noise_scale must be >= 0")

        # Clamp proposed values to safe bounds
        PEEP     = float(np.clip(proposed.get('PEEP', self.last_PEEP),     *SAFE_BOUNDS['PEEP']))
        FiO2     = float(np.clip(proposed.get('FiO2', self.last_FiO2),     *SAFE_BOUNDS['FiO2']))
        TidalVol = float(np.clip(proposed.get('TidalVol', self.last_TidalVol), *SAFE_BOUNDS['TidalVol']))

        trajectory = [current_spo2]
        spo2_now   = current_spo2
        generator = rng if rng is not None else np.random.default_rng()

        for _ in range(steps):
            spo2_now = self._spo2_from_settings(PEEP, FiO2, TidalVol, spo2_now)
            # Add calibration noise
            noise = float(generator.normal(0, self.uncertainty * 0.3 * noise_scale))
            trajectory.append(round(float(np.clip(spo2_now + noise, 60, 100)), 2))

        mean_spo2   = float(np.mean(trajectory[1:]))
        delta       = round(mean_spo2 - current_spo2, 2)
        upper_band  = [round(min(100, v + self.uncertainty), 2) for v in trajectory]
        lower_band  = [round(max(60, v - self.uncertainty), 2)  for v in trajectory]

        # Risk flags
        risk_flag   = mean_spo2 < 90.0
        tv_risk     = TidalVol > 600.0   # high tidal volume warning

        return {
            'trajectory':   trajectory,
            'upper_band':   upper_band,
            'lower_band':   lower_band,
            'mean_spo2':    round(mean_spo2, 2),
            'delta_spo2':   delta,
            'uncertainty':  round(self.uncertainty, 2),
            'risk_flag':    risk_flag,
            'tv_risk':      tv_risk,
            'applied': {
                'PEEP': round(PEEP, 1),
                'FiO2': round(FiO2, 1),
                'TidalVol': round(TidalVol, 1),
            }
        }

    def current_settings_as_baseline(self) -> Dict:
        """Return current (last calibrated) settings as baseline for comparison."""
        return {
            'PEEP':     self.last_PEEP,
            'FiO2':     self.last_FiO2,
            'TidalVol': self.last_TidalVol,
        }


# ─── Standalone demo ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    twin = DigitalTwin(stay_id=30004018)

    # Mock calibration history
    sample_history = [
        {'SpO2': 94 + i * 0.3, 'PEEP': 8, 'FiO2': 60, 'TidalVol': 370,
         'HR': 90, 'MAP': 75, 'RespRate': 20} for i in range(12)
    ]
    twin.calibrate(sample_history)
    print(f"Calibrated twin — compliance={twin.compliance_factor:.2f}, uncertainty=±{twin.uncertainty:.2f}")

    # Simulate proposed change: increase PEEP and FiO2
    result = twin.simulate(
        proposed={'PEEP': 10, 'FiO2': 70, 'TidalVol': 400},
        current_spo2=94.0,
        steps=4,
    )
    print("\nSimulation result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
