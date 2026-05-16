"""
Test 3 — ventilator behaviour changes based on weather.

Demonstrates that when the digital twin runs the *same* proposed ventilator
settings under different ambient weather conditions, the predicted SpO2
trajectory diverges in the direction the physiology predicts:

  - Low pressure (storm / altitude) → reduced effective FiO2 → lower SpO2
  - High temperature + humidity     → metabolic / Bohr penalty → lower SpO2
  - Calm sea-level weather          → no change vs the no-weather case

We also check the synthetic weather timeline generator produces
deterministic, bounded output and obeys its diurnal structure.
"""

import unittest

import numpy as np

from services.digital_twin import DigitalTwin
from services.weather import (
    WeatherState,
    WeatherTimelineConfig,
    calm_sea_level,
    generate_timeline,
    high_altitude,
    hot_humid_storm,
)


def _calibrated_twin(stay_id: int = 990001) -> DigitalTwin:
    twin = DigitalTwin(stay_id=stay_id)
    history = [
        {
            "SpO2": 94.0 + (i * 0.05),
            "PEEP": 8.0,
            "FiO2": 55.0,
            "TidalVol": 440.0,
            "HR": 95,
            "MAP": 78,
            "RespRate": 22,
        }
        for i in range(12)
    ]
    twin.calibrate(history)
    return twin


def _sim(twin: DigitalTwin, weather, seed: int = 7):
    return twin.simulate(
        proposed={"PEEP": 10.0, "FiO2": 70.0, "TidalVol": 440.0},
        current_spo2=92.0,
        steps=8,
        noise_scale=0.0,                       # deterministic so the assertions are tight
        rng=np.random.default_rng(seed),
        weather=weather,
    )


class WeatherCoefficientTests(unittest.TestCase):
    """Pure-physics checks on WeatherState — independent of the twin."""

    def test_sea_level_is_a_no_op(self):
        w = calm_sea_level()
        self.assertAlmostEqual(w.fio2_efficiency(), 1.0, places=2)
        self.assertEqual(w.spo2_baseline_penalty(), 0.0)

    def test_low_pressure_reduces_fio2_efficiency(self):
        self.assertLess(high_altitude().fio2_efficiency(), 0.80)
        self.assertLess(hot_humid_storm().fio2_efficiency(), 1.0)

    def test_heat_and_humidity_add_positive_penalty(self):
        # storm scenario hits both temp (38°C) and humidity (92%) thresholds
        self.assertGreater(hot_humid_storm().spo2_baseline_penalty(), 1.0)
        # cool dry altitude triggers neither
        self.assertEqual(high_altitude().spo2_baseline_penalty(), 0.0)


class TwinWeatherIntegrationTests(unittest.TestCase):
    """End-to-end: identical settings + different weather → different output."""

    def test_no_weather_matches_calm_weather(self):
        # A calm sea-level WeatherState should reproduce the no-weather result
        # to within rounding noise. This is the safety net guaranteeing the
        # weather hook is opt-in and side-effect-free at baseline.
        twin = _calibrated_twin()
        baseline = _sim(twin, weather=None)
        twin = _calibrated_twin()
        calm = _sim(twin, weather=calm_sea_level())
        self.assertAlmostEqual(baseline["mean_spo2"], calm["mean_spo2"], delta=0.05)

    def test_low_pressure_lowers_predicted_spo2(self):
        twin = _calibrated_twin()
        baseline = _sim(twin, weather=None)
        twin = _calibrated_twin()
        altitude = _sim(twin, weather=high_altitude())
        # FiO2 raised by 15 above calibrated baseline; at 755/1013 efficiency
        # the contribution shrinks by ~25%, so the equilibrium target drops
        # several SpO2 units. We require at least 0.5 to be safely above noise.
        self.assertLess(altitude["mean_spo2"], baseline["mean_spo2"] - 0.5)

    def test_storm_lowers_predicted_spo2_by_more_than_altitude(self):
        # Storm = low pressure AND heat/humidity penalty → strictly worse than
        # altitude (which only has the pressure effect).
        twin = _calibrated_twin()
        altitude = _sim(twin, weather=high_altitude())
        twin = _calibrated_twin()
        storm = _sim(twin, weather=hot_humid_storm())
        self.assertLess(storm["mean_spo2"], altitude["mean_spo2"])

    def test_simulate_output_includes_weather_summary(self):
        twin = _calibrated_twin()
        out = _sim(twin, weather=hot_humid_storm())
        self.assertIn("weather", out)
        for key in ("temperature_c", "humidity_pct", "pressure_hpa",
                    "fio2_efficiency", "spo2_baseline_penalty"):
            self.assertIn(key, out["weather"])

    def test_simulate_output_omits_weather_when_none(self):
        twin = _calibrated_twin()
        out = _sim(twin, weather=None)
        self.assertNotIn("weather", out)


class WeatherTimelineTests(unittest.TestCase):
    """Determinism + structure checks on the synthetic weather generator."""

    def test_timeline_is_deterministic_with_seed(self):
        cfg = WeatherTimelineConfig(seed=2026)
        a = generate_timeline(48, cfg)
        b = generate_timeline(48, WeatherTimelineConfig(seed=2026))
        self.assertEqual(a, b)

    def test_timeline_values_stay_in_realistic_envelopes(self):
        timeline = generate_timeline(96, WeatherTimelineConfig(seed=5))
        for w in timeline:
            self.assertIsInstance(w, WeatherState)
            self.assertTrue(-10.0 < w.temperature_c < 60.0)
            self.assertTrue(0.0 <= w.humidity_pct <= 100.0)
            self.assertTrue(800.0 < w.pressure_hpa < 1080.0)

    def test_timeline_has_diurnal_temperature_swing(self):
        # Over a full day the temperature range should span at least a third
        # of the configured diurnal amplitude (12 °C peak-to-peak default).
        cfg = WeatherTimelineConfig(seed=9, samples_per_day=96, temperature_amplitude_c=6.0)
        timeline = generate_timeline(96, cfg)
        temps = [w.temperature_c for w in timeline]
        self.assertGreater(max(temps) - min(temps), 4.0)


if __name__ == "__main__":
    unittest.main()
