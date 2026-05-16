"""
Profile comparison tests — `normal` vs `lung_infected`.

Validates that the `lung_infected` profile (bacterial/viral pneumonia with
consolidative infiltrates) produces telemetry distributions distinguishable
from the `normal` baseline:

  - Lower mean SpO2
  - Higher mean HR (fever-driven tachycardia)
  - Higher mean RespRate (tachypnea)
  - Higher hypoxia incidence (Next_SpO2 < 90)
  - Twin calibrated on the infected stream estimates lower compliance

These assertions guard the simulator's clinical face validity. If someone
changes the profile baselines, the test will flag drift away from the
documented physiology.
"""

import statistics
import unittest

from services.data_simulator import (
    PROFILE_BASELINES,
    SimulationConfig,
    VentilatorDataSimulator,
    validate_record,
)
from services.digital_twin import DigitalTwin


STAY_ID = 920001
STEPS = 96  # 24 h at 15-min intervals


def _stream(profile: str, seed: int = 11):
    """Produce a list of valid telemetry records for one synthetic stay."""
    config = SimulationConfig(
        profile=profile,
        seed=seed,
        packet_loss_probability=0.0,   # deterministic for distribution checks
        artifact_probability=0.0,
    )
    sim = VentilatorDataSimulator(config=config)
    records = sim.generate_batch(stay_id=STAY_ID, steps=STEPS)
    for r in records:
        validate_record(r)
    return records


def _mean(records, field):
    return statistics.fmean(r[field] for r in records if r[field] is not None)


class LungInfectedProfileTests(unittest.TestCase):
    # ── Profile registration ────────────────────────────────────────────────
    def test_lung_infected_profile_registered(self):
        self.assertIn("lung_infected", PROFILE_BASELINES)
        baseline = PROFILE_BASELINES["lung_infected"]
        # Pneumonia presents with depressed SpO2 and elevated HR/RR
        self.assertLess(baseline["SpO2"], PROFILE_BASELINES["normal"]["SpO2"])
        self.assertGreater(baseline["HR"], PROFILE_BASELINES["normal"]["HR"])
        self.assertGreater(baseline["RespRate"], PROFILE_BASELINES["normal"]["RespRate"])

    def test_lung_infected_distinct_from_ards(self):
        # ARDS is the more severe hypoxemic-failure profile in the simulator.
        # Lung-infected (pneumonia) should sit between normal and ARDS on
        # SpO2/FiO2 burden so they are not interchangeable.
        infected = PROFILE_BASELINES["lung_infected"]
        ards = PROFILE_BASELINES["ards"]
        self.assertGreater(infected["SpO2"], ards["SpO2"])
        self.assertLess(infected["FiO2"], ards["FiO2"])

    # ── Empirical distribution checks ───────────────────────────────────────
    def test_infected_stream_has_lower_spo2_than_normal(self):
        normal = _stream("normal", seed=11)
        infected = _stream("lung_infected", seed=11)
        # The empirical gap (~2.8 SpO2 units over 24 h) is smaller than the
        # 7-unit baseline gap because `normal` saturates at the SpO2=100 ceiling
        # while `infected` drifts down. Threshold of 2.0 still puts the test
        # well outside what measurement noise (sigma=0.8) could produce.
        self.assertGreater(_mean(normal, "SpO2") - _mean(infected, "SpO2"), 2.0)

    def test_infected_stream_has_higher_hr_and_rr(self):
        normal = _stream("normal", seed=23)
        infected = _stream("lung_infected", seed=23)
        self.assertGreater(_mean(infected, "HR") - _mean(normal, "HR"), 15.0)
        self.assertGreater(_mean(infected, "RespRate") - _mean(normal, "RespRate"), 4.0)

    def test_infected_stream_has_higher_hypoxia_incidence(self):
        # Mirror the supervised-label rule from pipelines/simulated_ingestion.py:
        # Hypoxia_Risk = 1 when the next-step SpO2 falls below 90.
        normal = _stream("normal", seed=37)
        infected = _stream("lung_infected", seed=37)

        def hypoxia_rate(records):
            spo2 = [r["SpO2"] for r in records]
            future = spo2[1:]
            return sum(1 for v in future if v < 90.0) / max(len(future), 1)

        self.assertLess(hypoxia_rate(normal), 0.05)
        self.assertGreater(hypoxia_rate(infected), 0.20)

    # ── Twin calibration on infected vs normal ──────────────────────────────
    def test_twin_compliance_lower_on_infected_history(self):
        # The DigitalTwin estimates compliance from SpO2 variability:
        # higher variability → lower compliance_factor. An infected lung is
        # noisier, so this should produce a lower compliance estimate.
        normal_records = _stream("normal", seed=51)
        infected_records = _stream("lung_infected", seed=51)

        twin_normal = DigitalTwin(stay_id=STAY_ID)
        twin_normal.calibrate(normal_records)
        twin_infected = DigitalTwin(stay_id=STAY_ID)
        twin_infected.calibrate(infected_records)

        self.assertTrue(twin_normal.is_calibrated)
        self.assertTrue(twin_infected.is_calibrated)
        self.assertLessEqual(
            twin_infected.compliance_factor,
            twin_normal.compliance_factor,
            "Lung-infected calibration must yield compliance ≤ normal",
        )


if __name__ == "__main__":
    unittest.main()
