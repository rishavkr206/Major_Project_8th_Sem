"""
Digital Twin — physiological safety regression tests.

Closes the open item on docs/safety-constraints.md:
  "Automated safety regression tests for edge-case physiological extremes."

These tests assert that the twin behaves correctly under:
  - extreme proposed settings (clamped to safe bounds)
  - extreme calibration histories (very low / very high SpO2)
  - degenerate inputs (empty history, single-point history)
  - invalid simulate() arguments (negative steps / noise_scale)
  - SpO2 trajectory clipping (never < 60 or > 100)
  - tidal-volume risk warning on barotrauma-range volumes
  - hypoxia risk_flag on settings that cannot maintain SpO2 >= 90
"""

import unittest

import numpy as np

from services.digital_twin import DigitalTwin, SAFE_BOUNDS


def _history(spo2_start: float, peep: float, fio2: float, tv: float, n: int = 12):
    return [
        {
            "SpO2": spo2_start + (i * 0.1),
            "PEEP": peep,
            "FiO2": fio2,
            "TidalVol": tv,
            "HR": 90,
            "MAP": 75,
            "RespRate": 20,
        }
        for i in range(n)
    ]


class DigitalTwinSafetyExtremes(unittest.TestCase):
    # ── Proposed settings extremes ──────────────────────────────────────────
    def test_extreme_high_proposed_clamped_to_upper_bounds(self):
        twin = DigitalTwin(stay_id=950001)
        twin.calibrate(_history(92.0, 8.0, 50.0, 450.0))
        out = twin.simulate(
            proposed={"PEEP": 1e6, "FiO2": 1e6, "TidalVol": 1e6},
            current_spo2=92.0,
            steps=4,
            noise_scale=0.0,
        )
        self.assertEqual(out["applied"]["PEEP"], SAFE_BOUNDS["PEEP"][1])
        self.assertEqual(out["applied"]["FiO2"], SAFE_BOUNDS["FiO2"][1])
        self.assertEqual(out["applied"]["TidalVol"], SAFE_BOUNDS["TidalVol"][1])

    def test_extreme_low_proposed_clamped_to_lower_bounds(self):
        twin = DigitalTwin(stay_id=950002)
        twin.calibrate(_history(92.0, 8.0, 50.0, 450.0))
        out = twin.simulate(
            proposed={"PEEP": -50, "FiO2": -50, "TidalVol": -50},
            current_spo2=92.0,
            steps=4,
            noise_scale=0.0,
        )
        self.assertEqual(out["applied"]["PEEP"], SAFE_BOUNDS["PEEP"][0])
        self.assertEqual(out["applied"]["FiO2"], SAFE_BOUNDS["FiO2"][0])
        self.assertEqual(out["applied"]["TidalVol"], SAFE_BOUNDS["TidalVol"][0])

    def test_negative_infinity_proposed_handled(self):
        twin = DigitalTwin(stay_id=950003)
        twin.calibrate(_history(94.0, 7.0, 45.0, 440.0))
        out = twin.simulate(
            proposed={"PEEP": float("-inf"), "FiO2": float("-inf"), "TidalVol": float("-inf")},
            current_spo2=94.0,
            steps=2,
            noise_scale=0.0,
        )
        # All values must be finite and inside hard bounds
        for k, v in out["applied"].items():
            self.assertTrue(np.isfinite(v), f"{k} is not finite")
            lo, hi = SAFE_BOUNDS[k]
            self.assertGreaterEqual(v, lo)
            self.assertLessEqual(v, hi)

    # ── Calibration extremes ────────────────────────────────────────────────
    def test_calibration_with_severely_hypoxic_history(self):
        twin = DigitalTwin(stay_id=950004)
        twin.calibrate(_history(72.0, 14.0, 90.0, 380.0))  # very sick lung
        self.assertTrue(twin.is_calibrated)
        # Severely sick lung → low compliance factor
        self.assertLessEqual(twin.compliance_factor, 1.0)
        self.assertGreater(twin.uncertainty, 0.0)

    def test_calibration_with_supranormal_history(self):
        twin = DigitalTwin(stay_id=950005)
        twin.calibrate(_history(100.0, 5.0, 30.0, 480.0))
        self.assertTrue(twin.is_calibrated)
        self.assertGreaterEqual(twin.baseline_spo2, 99.0)

    def test_empty_history_keeps_defaults(self):
        twin = DigitalTwin(stay_id=950006)
        twin.calibrate([])  # no history
        # Empty history is a no-op — twin retains constructor defaults
        self.assertFalse(twin.is_calibrated)
        # Simulation should still work using defaults
        out = twin.simulate(
            proposed={"PEEP": 8, "FiO2": 50, "TidalVol": 450},
            current_spo2=95.0,
            steps=3,
            noise_scale=0.0,
        )
        self.assertEqual(len(out["trajectory"]), 4)

    def test_single_point_history_does_not_crash(self):
        twin = DigitalTwin(stay_id=950007)
        twin.calibrate(_history(94.0, 8.0, 50.0, 450.0, n=1))
        self.assertTrue(twin.is_calibrated)
        # std on a single point is 0, but uncertainty should still have a floor
        self.assertGreaterEqual(twin.uncertainty, 0.5)

    # ── simulate() input validation ─────────────────────────────────────────
    def test_zero_steps_rejected(self):
        twin = DigitalTwin(stay_id=950008)
        twin.calibrate(_history(95.0, 6.0, 35.0, 460.0))
        with self.assertRaises(ValueError):
            twin.simulate(
                proposed={"PEEP": 6, "FiO2": 35, "TidalVol": 460},
                current_spo2=95.0,
                steps=0,
                noise_scale=0.0,
            )

    def test_negative_noise_scale_rejected(self):
        twin = DigitalTwin(stay_id=950009)
        twin.calibrate(_history(95.0, 6.0, 35.0, 460.0))
        with self.assertRaises(ValueError):
            twin.simulate(
                proposed={"PEEP": 6, "FiO2": 35, "TidalVol": 460},
                current_spo2=95.0,
                steps=4,
                noise_scale=-0.1,
            )

    # ── Output bound enforcement ────────────────────────────────────────────
    def test_trajectory_never_exceeds_physiological_bounds(self):
        twin = DigitalTwin(stay_id=950010)
        twin.calibrate(_history(99.5, 5.0, 30.0, 460.0))
        out = twin.simulate(
            proposed={"PEEP": 20, "FiO2": 100, "TidalVol": 200},
            current_spo2=99.9,
            steps=12,
            noise_scale=2.0,  # large noise
            rng=np.random.default_rng(42),
        )
        for v in out["trajectory"]:
            self.assertGreaterEqual(v, 60.0)
            self.assertLessEqual(v, 100.0)

    def test_trajectory_clipped_above_60_under_severe_hypoxia(self):
        twin = DigitalTwin(stay_id=950011)
        twin.calibrate(_history(70.0, 12.0, 80.0, 400.0))
        out = twin.simulate(
            proposed={"PEEP": 3, "FiO2": 21, "TidalVol": 800},  # worst possible support
            current_spo2=62.0,
            steps=12,
            noise_scale=0.0,
        )
        for v in out["trajectory"]:
            self.assertGreaterEqual(v, 60.0)

    # ── Risk flag semantics ─────────────────────────────────────────────────
    def test_high_tidal_volume_raises_tv_risk(self):
        twin = DigitalTwin(stay_id=950012)
        twin.calibrate(_history(92.0, 8.0, 55.0, 460.0))
        out = twin.simulate(
            proposed={"PEEP": 8, "FiO2": 60, "TidalVol": 720.0},
            current_spo2=92.0,
            steps=3,
            noise_scale=0.0,
        )
        self.assertTrue(out["tv_risk"], "TidalVol > 600 must raise tv_risk")

    def test_safe_tidal_volume_does_not_raise_tv_risk(self):
        twin = DigitalTwin(stay_id=950013)
        twin.calibrate(_history(92.0, 8.0, 55.0, 460.0))
        out = twin.simulate(
            proposed={"PEEP": 8, "FiO2": 60, "TidalVol": 450.0},
            current_spo2=92.0,
            steps=3,
            noise_scale=0.0,
        )
        self.assertFalse(out["tv_risk"], "TidalVol <= 600 must NOT raise tv_risk")

    def test_severe_hypoxia_settings_raise_risk_flag(self):
        twin = DigitalTwin(stay_id=950014)
        twin.calibrate(_history(85.0, 10.0, 75.0, 400.0))
        out = twin.simulate(
            proposed={"PEEP": 3, "FiO2": 21, "TidalVol": 400},  # remove all support
            current_spo2=85.0,
            steps=8,
            noise_scale=0.0,
        )
        # mean_spo2 is computed over trajectory[1:]; setting an already low
        # patient back to room-air with minimal PEEP must keep mean < 90
        self.assertLess(out["mean_spo2"], 90.0)
        self.assertTrue(out["risk_flag"])

    # ── Output structure contract ───────────────────────────────────────────
    def test_simulate_returns_required_keys(self):
        twin = DigitalTwin(stay_id=950015)
        twin.calibrate(_history(94.0, 8.0, 55.0, 450.0))
        out = twin.simulate(
            proposed={"PEEP": 9, "FiO2": 60, "TidalVol": 440},
            current_spo2=94.0,
            steps=4,
            noise_scale=0.0,
        )
        for key in (
            "trajectory", "upper_band", "lower_band",
            "mean_spo2", "delta_spo2", "uncertainty",
            "risk_flag", "tv_risk", "applied",
        ):
            self.assertIn(key, out, f"missing key {key} in simulate() output")
        self.assertEqual(len(out["trajectory"]), 5)  # current + 4 steps
        self.assertEqual(len(out["upper_band"]), 5)
        self.assertEqual(len(out["lower_band"]), 5)
        # Bands must bracket the trajectory
        for v, u, l in zip(out["trajectory"], out["upper_band"], out["lower_band"]):
            self.assertGreaterEqual(u, v - 1e-6)
            self.assertLessEqual(l, v + 1e-6)

    def test_uncertainty_band_width_is_positive(self):
        twin = DigitalTwin(stay_id=950016)
        twin.calibrate(_history(94.0, 8.0, 55.0, 450.0))
        out = twin.simulate(
            proposed={"PEEP": 9, "FiO2": 60, "TidalVol": 440},
            current_spo2=94.0,
            steps=4,
            noise_scale=0.0,
        )
        for u, l in zip(out["upper_band"], out["lower_band"]):
            self.assertGreater(u - l, 0.0)


if __name__ == "__main__":
    unittest.main()
