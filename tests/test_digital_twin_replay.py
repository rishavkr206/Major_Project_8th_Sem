import unittest

import numpy as np

from services.digital_twin import DigitalTwin


def _history(spo2_start: float, peep: float, fio2: float, tv: float):
    return [
        {
            "SpO2": spo2_start + (i * 0.15),
            "PEEP": peep,
            "FiO2": fio2,
            "TidalVol": tv,
            "HR": 90,
            "MAP": 75,
            "RespRate": 20,
        }
        for i in range(12)
    ]


class DigitalTwinReplayTests(unittest.TestCase):
    def test_simulation_is_deterministic_when_noise_disabled(self) -> None:
        twin = DigitalTwin(stay_id=920001)
        twin.calibrate(_history(92.0, 8.0, 55.0, 420.0))

        out_a = twin.simulate(
            proposed={"PEEP": 10.0, "FiO2": 70.0, "TidalVol": 420.0},
            current_spo2=92.5,
            steps=4,
            noise_scale=0.0,
        )
        out_b = twin.simulate(
            proposed={"PEEP": 10.0, "FiO2": 70.0, "TidalVol": 420.0},
            current_spo2=92.5,
            steps=4,
            noise_scale=0.0,
        )

        self.assertEqual(out_a["trajectory"], out_b["trajectory"])
        self.assertEqual(out_a["mean_spo2"], out_b["mean_spo2"])

    def test_proposed_settings_are_clamped_to_safe_bounds(self) -> None:
        twin = DigitalTwin(stay_id=920002)
        twin.calibrate(_history(90.0, 7.0, 50.0, 450.0))

        out = twin.simulate(
            proposed={"PEEP": 99.0, "FiO2": 5.0, "TidalVol": 9999.0},
            current_spo2=90.0,
            steps=3,
            noise_scale=0.0,
        )
        applied = out["applied"]
        self.assertEqual(applied["PEEP"], 20.0)
        self.assertEqual(applied["FiO2"], 21.0)
        self.assertEqual(applied["TidalVol"], 800.0)

    def test_seeded_rng_replay_is_stable(self) -> None:
        twin = DigitalTwin(stay_id=920003)
        twin.calibrate(_history(89.0, 9.0, 60.0, 430.0))

        rng_a = np.random.default_rng(1234)
        rng_b = np.random.default_rng(1234)
        out_a = twin.simulate(
            proposed={"PEEP": 11.0, "FiO2": 65.0, "TidalVol": 430.0},
            current_spo2=89.5,
            steps=5,
            noise_scale=1.0,
            rng=rng_a,
        )
        out_b = twin.simulate(
            proposed={"PEEP": 11.0, "FiO2": 65.0, "TidalVol": 430.0},
            current_spo2=89.5,
            steps=5,
            noise_scale=1.0,
            rng=rng_b,
        )
        self.assertEqual(out_a["trajectory"], out_b["trajectory"])


if __name__ == "__main__":
    unittest.main()
