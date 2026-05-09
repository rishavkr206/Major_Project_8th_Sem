"""
Ventilator telemetry simulator for Phase 1 implementation.

Generates synthetic patient streams with configurable disease profiles,
measurement noise, drift, and packet loss behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Dict, List


PROFILE_BASELINES: Dict[str, Dict[str, float]] = {
    "normal": {
        "HR": 82.0,
        "MAP": 78.0,
        "RespRate": 18.0,
        "SpO2": 97.0,
        "PEEP": 6.0,
        "FiO2": 35.0,
        "TidalVol": 460.0,
    },
    "ards": {
        "HR": 104.0,
        "MAP": 72.0,
        "RespRate": 28.0,
        "SpO2": 88.0,
        "PEEP": 11.0,
        "FiO2": 70.0,
        "TidalVol": 380.0,
    },
    "copd": {
        "HR": 96.0,
        "MAP": 80.0,
        "RespRate": 25.0,
        "SpO2": 91.0,
        "PEEP": 8.0,
        "FiO2": 45.0,
        "TidalVol": 500.0,
    },
    "unstable": {
        "HR": 112.0,
        "MAP": 68.0,
        "RespRate": 30.0,
        "SpO2": 86.0,
        "PEEP": 10.0,
        "FiO2": 78.0,
        "TidalVol": 420.0,
    },
}

CLINICAL_BOUNDS: Dict[str, tuple[float, float]] = {
    "HR": (35.0, 220.0),
    "MAP": (35.0, 145.0),
    "RespRate": (6.0, 55.0),
    "SpO2": (55.0, 100.0),
    "PEEP": (3.0, 20.0),
    "FiO2": (21.0, 100.0),
    "TidalVol": (200.0, 800.0),
}

MEASUREMENT_SIGMA: Dict[str, float] = {
    "HR": 2.5,
    "MAP": 1.8,
    "RespRate": 1.3,
    "SpO2": 0.8,
    "PEEP": 0.2,
    "FiO2": 0.7,
    "TidalVol": 8.0,
}

REQUIRED_EVENT_FIELDS = (
    "stay_id",
    "charttime",
    "HR",
    "MAP",
    "RespRate",
    "SpO2",
    "PEEP",
    "FiO2",
    "TidalVol",
)


@dataclass
class SimulationConfig:
    profile: str = "normal"
    interval_minutes: int = 15
    packet_loss_probability: float = 0.03
    artifact_probability: float = 0.02
    trend_strength: float = 0.05
    seed: int | None = None


class VentilatorDataSimulator:
    """Synthetic telemetry generator aligned with project feature schema."""

    def __init__(self, config: SimulationConfig):
        if config.profile not in PROFILE_BASELINES:
            raise ValueError(
                f"Unsupported profile '{config.profile}'. "
                f"Use one of: {', '.join(PROFILE_BASELINES)}"
            )
        self.config = config
        self._rng = random.Random(config.seed)
        self._state = dict(PROFILE_BASELINES[config.profile])
        self._step = 0
        self._anchor_time = datetime.now(timezone.utc).replace(microsecond=0)

    def _bounded(self, name: str, value: float) -> float:
        lo, hi = CLINICAL_BOUNDS[name]
        return max(lo, min(hi, value))

    def _profile_drift(self) -> Dict[str, float]:
        direction = -1.0 if self.config.profile in ("normal", "copd") else 1.0
        strength = self.config.trend_strength * (1 + (self._step / 200.0))
        return {
            "HR": direction * strength * 0.8,
            "MAP": -direction * strength * 0.5,
            "RespRate": direction * strength * 0.4,
            "SpO2": -direction * strength * 0.5,
            "PEEP": 0.03 * direction,
            "FiO2": 0.08 * direction,
            "TidalVol": -0.25 * direction,
        }

    def _artifact_adjustment(self, metric: str, value: float) -> float:
        if self._rng.random() > self.config.artifact_probability:
            return value
        if metric == "SpO2":
            return value - self._rng.uniform(3.0, 8.0)
        if metric == "MAP":
            return value + self._rng.uniform(8.0, 15.0)
        if metric == "RespRate":
            return value + self._rng.uniform(4.0, 10.0)
        return value + self._rng.uniform(-5.0, 5.0)

    def next_record(self, stay_id: int) -> Dict[str, float | str | int]:
        self._step += 1
        drift = self._profile_drift()
        output: Dict[str, float | str | int] = {"stay_id": stay_id}

        timestamp = self._anchor_time + timedelta(
            minutes=self._step * self.config.interval_minutes
        )
        output["charttime"] = timestamp.isoformat()

        for metric, current in self._state.items():
            noisy = current + drift[metric]
            noisy += self._rng.gauss(0.0, MEASUREMENT_SIGMA[metric])
            noisy = self._artifact_adjustment(metric, noisy)
            bounded = self._bounded(metric, noisy)
            rounded = round(bounded, 2)
            self._state[metric] = rounded
            output[metric] = rounded

        if self._rng.random() < self.config.packet_loss_probability:
            missing_field = self._rng.choice(
                ["SpO2", "MAP", "RespRate", "HR", "PEEP", "FiO2", "TidalVol"]
            )
            output[missing_field] = None

        return output

    def generate_batch(self, stay_id: int, steps: int) -> List[Dict[str, float | str | int]]:
        return [self.next_record(stay_id=stay_id) for _ in range(steps)]


def validate_record(record: Dict[str, float | str | int | None]) -> None:
    """Raise ValueError when a generated telemetry record violates schema/bounds."""
    missing = [field for field in REQUIRED_EVENT_FIELDS if field not in record]
    if missing:
        raise ValueError(f"Telemetry schema missing fields: {missing}")

    stay_id = record["stay_id"]
    if not isinstance(stay_id, int) or stay_id <= 0:
        raise ValueError("stay_id must be a positive integer")

    charttime = record["charttime"]
    if not isinstance(charttime, str) or "T" not in charttime:
        raise ValueError("charttime must be an ISO-8601 timestamp string")

    for metric, (lo, hi) in CLINICAL_BOUNDS.items():
        value = record[metric]
        if value is None:
            continue
        if not isinstance(value, (int, float)):
            raise ValueError(f"{metric} must be numeric or null")
        if value < lo or value > hi:
            raise ValueError(f"{metric} out of bounds: {value} not in [{lo}, {hi}]")
