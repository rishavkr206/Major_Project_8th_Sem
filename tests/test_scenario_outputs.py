import unittest

from tests.test_scenarios import run_all_scenarios


class ScenarioOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results = run_all_scenarios()

    def test_lstm_lengths_are_reported_every_1000_values(self) -> None:
        lengths = [r.observations for r in self.results["lstm_history_length"]]
        self.assertEqual(lengths, [1000, 2000, 3000, 4000, 5000])

    def test_infection_risk_increases_from_control_to_severe(self) -> None:
        control = self.results["control"][0]
        infections = self.results["health_status"]
        risks = [control.hypoxia_prob] + [case.hypoxia_prob for case in infections]
        self.assertLess(risks[0], risks[1])
        self.assertLess(risks[1], risks[2])
        self.assertLess(risks[2], risks[3])

    def test_weather_cases_include_ventilator_output_effects(self) -> None:
        low_pressure = next(
            case
            for case in self.results["weather_impact"]
            if case.metadata["weather_condition"] == "low_pressure"
        )
        self.assertEqual(low_pressure.alert_level, "WARNING")
        self.assertGreater(low_pressure.metadata["fio2_delta"], 0)
        self.assertGreater(low_pressure.metadata["peep_delta"], 0)

    def test_anomaly_cases_raise_warning_or_critical_alerts(self) -> None:
        for case in self.results["anomaly_detection"]:
            self.assertIn(case.alert_level, {"WARNING", "CRITICAL"})
            self.assertIn("anomaly_onset_sample", case.metadata)


if __name__ == "__main__":
    unittest.main()
