"""
Smoke tests for the LSTM dataset-size study orchestrator.

We do NOT launch TensorFlow training here; the sweep itself is expensive
and runs on demand from the CLI. These tests guard the pure-Python helpers
inside `pipelines/lstm_dataset_size_study.py` so a refactor of the row-budget
math doesn't silently produce datasets that miss the requested target.
"""

import importlib
import os
import unittest


MOD = importlib.import_module("pipelines.lstm_dataset_size_study")


class SolveStaysStepsTests(unittest.TestCase):
    def test_realised_rows_within_tolerance(self):
        # Target is per-CSV; the simulator drops the final row of each stay
        # when computing Next_SpO2, so realised = stays * profiles * (steps - 1).
        for target in (500, 1000, 2000, 4000):
            stays, steps = MOD._solve_stays_steps(target, n_profiles=4)
            realised = stays * 4 * (steps - 1)
            # Allow ±25% — the helper trades exactness for clean stays/steps.
            self.assertGreater(realised, target * 0.75,
                               f"target={target}: realised={realised} too low")
            self.assertLess(realised, target * 1.6,
                            f"target={target}: realised={realised} too high")

    def test_returns_at_least_one_stay(self):
        stays, steps = MOD._solve_stays_steps(50, n_profiles=4)
        self.assertGreaterEqual(stays, 1)
        self.assertGreaterEqual(steps, 2)

    def test_rejects_target_smaller_than_profile_count(self):
        with self.assertRaises(ValueError):
            MOD._solve_stays_steps(2, n_profiles=4)


class WriteMarkdownTests(unittest.TestCase):
    def test_writes_table_with_one_row_per_run(self):
        report = {
            "generated_at": "2026-05-10T00:00:00+00:00",
            "profiles": ["normal", "ards"],
            "seq_len": 12,
            "epochs": 4,
            "seed": 42,
            "runs": [
                {
                    "target_rows": 1000,
                    "realised_rows": 992,
                    "train_seconds": 12.5,
                    "metrics": {
                        "next_spo2_mae": 1.2,
                        "next_spo2_rmse": 1.7,
                        "hypoxia_auroc": 0.81,
                        "hypoxia_f1_optimal": 0.42,
                        "hypoxia_optimal_threshold": 0.35,
                    },
                },
            ],
        }
        out = os.path.join(os.path.dirname(__file__), "_tmp_size_report.md")
        try:
            MOD.write_markdown(report, out)
            with open(out, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("LSTM Accuracy vs Dataset Size", content)
            self.assertIn("1,000", content)              # row count formatted
            self.assertIn("0.81", content)               # AUROC made it through
        finally:
            if os.path.exists(out):
                os.remove(out)


if __name__ == "__main__":
    unittest.main()
