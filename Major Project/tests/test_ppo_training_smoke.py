"""
Smoke tests for the Phase 4 PPO training pipeline.

These do NOT exercise stable-baselines3 or gymnasium (they may be absent in
CI). They cover:
  - reward shaping invariants
  - the smoke() driver which simulates an episode end-to-end with random
    actions through DigitalTwin + VentilatorDataSimulator
  - action-table / safety-bound consistency
"""

import unittest

import numpy as np

from ml.ppo_training import (
    ACTION_TABLE,
    N_ACTIONS,
    OBS_KEYS,
    compute_reward,
    smoke,
)
from services.digital_twin import SAFE_BOUNDS


class PPOTrainingSmokeTests(unittest.TestCase):

    # ── Reward shape invariants ─────────────────────────────────────────────
    def test_reward_target_band_is_positive(self):
        for spo2 in (94.0, 96.0, 98.0):
            r = compute_reward(spo2, peep=8.0, fio2=40.0, tv=400.0)
            self.assertGreater(r, 0.0, f"reward should be positive in target band at {spo2}")

    def test_reward_hypoxia_is_strongly_negative(self):
        r = compute_reward(85.0, peep=8.0, fio2=40.0, tv=400.0)
        self.assertLess(r, -5.0)

    def test_reward_vili_penalty_active(self):
        base = compute_reward(96.0, peep=8.0, fio2=40.0, tv=400.0)
        penal = compute_reward(96.0, peep=8.0, fio2=40.0, tv=700.0)
        self.assertLess(penal, base, "high TV must lower reward")

    def test_reward_high_peep_penalty_active(self):
        base = compute_reward(96.0, peep=10.0, fio2=40.0, tv=400.0)
        penal = compute_reward(96.0, peep=18.0, fio2=40.0, tv=400.0)
        self.assertLess(penal, base, "high PEEP must lower reward")

    # ── Action table integrity ──────────────────────────────────────────────
    def test_action_table_size_matches_constant(self):
        self.assertEqual(N_ACTIONS, len(ACTION_TABLE))

    def test_action_table_steps_within_one_clinical_increment(self):
        for name, dpeep, dfio2, dtv in ACTION_TABLE:
            self.assertLessEqual(abs(dpeep), 1.0, f"{name} PEEP step too big")
            self.assertLessEqual(abs(dfio2), 5.0, f"{name} FiO2 step too big")
            self.assertLessEqual(abs(dtv), 25.0, f"{name} TV step too big")

    # ── Smoke driver end-to-end (no SB3 needed) ─────────────────────────────
    def test_smoke_runs_and_stays_in_bounds(self):
        out = smoke()
        self.assertTrue(out["smoke"])
        self.assertEqual(out["n_actions_executed"], 48)
        # Reward is bounded (no NaNs, no infs).
        self.assertTrue(np.isfinite(out["total_reward"]))
        # Final SpO2 is a real saturation reading.
        self.assertGreaterEqual(out["final_spo2"], 60.0)
        self.assertLessEqual(out["final_spo2"], 100.0)

    def test_obs_keys_match_safe_bounds_subset(self):
        # The bounded obs keys must include the parameters we hard-clamp.
        for k in ("PEEP", "FiO2", "TidalVol"):
            self.assertIn(k, OBS_KEYS)
            self.assertIn(k, SAFE_BOUNDS)


if __name__ == "__main__":
    unittest.main()
