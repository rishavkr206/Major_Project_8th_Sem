"""
Synthetic weather signal for the ventilator digital twin.

Provides a `WeatherState` dataclass plus a small generator that produces
realistic-looking diurnal weather. The DigitalTwin treats weather as an
exogenous modulator: it does not change the physics of the lung, but it
adjusts the *effective* contribution of FiO2 and the patient's metabolic
SpO2 baseline so that "weather changes → ventilator changes" can be
demonstrated end-to-end.

Weather effects modelled
------------------------
1. Atmospheric pressure (hPa)
       Lower pressure (high-altitude or storm fronts) reduces the partial
       pressure of inspired O2 even when FiO2 is constant. We discount
       FiO2's contribution proportional to (pressure - 1013) / 1013, which
       is the canonical correction used in altitude / hypobaric medicine.

2. Temperature (°C)
       Heat stress above ~32 °C increases metabolic O2 demand and shifts
       the OxyHb dissociation curve right (Bohr effect), so we apply a
       small additive SpO2 penalty per °C above 32.

3. Relative humidity (%)
       Very high humidity (> 80 %) impairs evaporative airway cooling and
       can reduce gas exchange efficiency at the alveolar-capillary
       interface. Modelled as a tiny linear penalty above 80 % RH.

All coefficients are small; weather should perturb, not dominate.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Reference / sea-level values ────────────────────────────────────────────
SEA_LEVEL_PRESSURE_HPA = 1013.25
TEMP_PENALTY_THRESHOLD_C = 32.0
TEMP_PENALTY_PER_C = 0.20          # SpO2 % lost per °C above threshold
HUMIDITY_PENALTY_THRESHOLD = 80.0
HUMIDITY_PENALTY_PER_PCT = 0.05    # SpO2 % lost per RH% above threshold


@dataclass
class WeatherState:
    """A point-in-time weather observation."""
    temperature_c: float = 24.0
    humidity_pct: float = 55.0
    pressure_hpa: float = SEA_LEVEL_PRESSURE_HPA

    def fio2_efficiency(self) -> float:
        """
        Multiplier in [0, 1+] applied to the FiO2 contribution inside the twin.

        At sea-level pressure this returns 1.0. At 800 hPa (~ 2000 m altitude
        or a deep low-pressure storm) it returns ~0.79. At 1030 hPa
        (high-pressure clear weather) it returns ~1.02.
        """
        return max(0.0, self.pressure_hpa / SEA_LEVEL_PRESSURE_HPA)

    def spo2_baseline_penalty(self) -> float:
        """
        Additive penalty subtracted from the twin's equilibrium SpO2 target.
        Always >= 0. Returns 0 in comfortable weather.
        """
        penalty = 0.0
        if self.temperature_c > TEMP_PENALTY_THRESHOLD_C:
            penalty += (self.temperature_c - TEMP_PENALTY_THRESHOLD_C) * TEMP_PENALTY_PER_C
        if self.humidity_pct > HUMIDITY_PENALTY_THRESHOLD:
            penalty += (self.humidity_pct - HUMIDITY_PENALTY_THRESHOLD) * HUMIDITY_PENALTY_PER_PCT
        return penalty


# ─── Reference scenarios for tests / demo ────────────────────────────────────
def calm_sea_level() -> WeatherState:
    """Temperate, comfortable, sea-level baseline. Should be a no-op."""
    return WeatherState(temperature_c=22.0, humidity_pct=50.0, pressure_hpa=1013.25)


def hot_humid_storm() -> WeatherState:
    """Tropical heatwave with low-pressure system: stresses the patient."""
    return WeatherState(temperature_c=38.0, humidity_pct=92.0, pressure_hpa=985.0)


def high_altitude() -> WeatherState:
    """Mountain ICU at ~2400 m. Cool, dry, but pressure-limited."""
    return WeatherState(temperature_c=15.0, humidity_pct=35.0, pressure_hpa=755.0)


# ─── Synthetic time series ───────────────────────────────────────────────────
@dataclass
class WeatherTimelineConfig:
    base_temperature_c: float = 26.0
    base_humidity_pct: float = 60.0
    base_pressure_hpa: float = 1013.0
    temperature_amplitude_c: float = 6.0    # diurnal swing
    humidity_amplitude_pct: float = 18.0
    pressure_drift_hpa: float = 8.0         # slow synoptic drift
    samples_per_day: int = 96               # 15-min cadence
    seed: int | None = None


def generate_timeline(steps: int, config: Optional[WeatherTimelineConfig] = None) -> List[WeatherState]:
    """
    Produce `steps` weather observations with a sinusoidal diurnal cycle
    plus low-frequency pressure drift and small Gaussian noise. Deterministic
    when a seed is supplied.
    """
    cfg = config or WeatherTimelineConfig()
    rng = random.Random(cfg.seed)
    timeline: List[WeatherState] = []
    two_pi = 2.0 * math.pi
    for i in range(steps):
        phase = two_pi * (i / cfg.samples_per_day)
        # Coolest just before dawn, warmest mid-afternoon → sin offset by -pi/2.
        t = cfg.base_temperature_c + cfg.temperature_amplitude_c * math.sin(phase - math.pi / 2)
        # Humidity is anti-correlated with temperature (peaks at night).
        h = cfg.base_humidity_pct + cfg.humidity_amplitude_pct * math.cos(phase)
        # Pressure drifts slowly across multiple days, no diurnal cycle.
        p = cfg.base_pressure_hpa + cfg.pressure_drift_hpa * math.sin(two_pi * i / (cfg.samples_per_day * 3))

        t += rng.gauss(0.0, 0.3)
        h += rng.gauss(0.0, 1.0)
        p += rng.gauss(0.0, 0.4)

        timeline.append(
            WeatherState(
                temperature_c=round(t, 2),
                humidity_pct=round(max(0.0, min(100.0, h)), 2),
                pressure_hpa=round(p, 2),
            )
        )
    return timeline
