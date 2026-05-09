"""
Digital Twin Phase 2 evaluation runner.

Computes deterministic replay and calibration-oriented metrics for the current
DigitalTwin implementation.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

if __package__ is None or __package__ == "":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.digital_twin import DigitalTwin


@dataclass
class TwinScenario:
    name: str
    history_spo2_start: float
    baseline_peep: float
    baseline_fio2: float
    baseline_tidal_vol: float
    current_spo2: float
    proposed: Dict[str, float]
    expected_trend: str  # "up" or "down"


def build_history(spo2_start: float, peep: float, fio2: float, tidal_vol: float) -> List[Dict]:
    return [
        {
            "SpO2": spo2_start + (i * 0.12),
            "PEEP": peep,
            "FiO2": fio2,
            "TidalVol": tidal_vol,
            "HR": 92,
            "MAP": 74,
            "RespRate": 22,
        }
        for i in range(12)
    ]


def default_scenarios() -> List[TwinScenario]:
    return [
        TwinScenario(
            name="ARDS rescue strategy",
            history_spo2_start=87.5,
            baseline_peep=9.0,
            baseline_fio2=62.0,
            baseline_tidal_vol=420.0,
            current_spo2=88.3,
            proposed={"PEEP": 12.0, "FiO2": 78.0, "TidalVol": 420.0},
            expected_trend="up",
        ),
        TwinScenario(
            name="COPD conservative shift",
            history_spo2_start=92.0,
            baseline_peep=7.0,
            baseline_fio2=45.0,
            baseline_tidal_vol=500.0,
            current_spo2=92.6,
            proposed={"PEEP": 6.0, "FiO2": 40.0, "TidalVol": 480.0},
            expected_trend="down",
        ),
        TwinScenario(
            name="Boundary clamp stress",
            history_spo2_start=89.0,
            baseline_peep=8.0,
            baseline_fio2=55.0,
            baseline_tidal_vol=450.0,
            current_spo2=89.5,
            proposed={"PEEP": 80.0, "FiO2": 5.0, "TidalVol": 1600.0},
            expected_trend="down",
        ),
        TwinScenario(
            name="High volume warning path",
            history_spo2_start=90.5,
            baseline_peep=8.5,
            baseline_fio2=58.0,
            baseline_tidal_vol=520.0,
            current_spo2=91.2,
            proposed={"PEEP": 10.0, "FiO2": 65.0, "TidalVol": 720.0},
            expected_trend="up",
        ),
        TwinScenario(
            name="Oxygen wean stability check",
            history_spo2_start=96.0,
            baseline_peep=7.0,
            baseline_fio2=46.0,
            baseline_tidal_vol=460.0,
            current_spo2=96.4,
            proposed={"PEEP": 6.0, "FiO2": 38.0, "TidalVol": 450.0},
            expected_trend="down",
        ),
        TwinScenario(
            name="Mild recruitment optimization",
            history_spo2_start=91.0,
            baseline_peep=8.0,
            baseline_fio2=52.0,
            baseline_tidal_vol=440.0,
            current_spo2=91.5,
            proposed={"PEEP": 9.5, "FiO2": 60.0, "TidalVol": 430.0},
            expected_trend="up",
        ),
    ]


def evaluate(seed: int) -> Dict[str, float]:
    scenarios = default_scenarios()
    deterministic_deltas = []
    trend_hits = 0
    clamped_actions = 0
    replay_match_hits = 0
    tv_warning_hits = 0

    for idx, scenario in enumerate(scenarios):
        twin = DigitalTwin(stay_id=930000 + idx)
        twin.calibrate(
            build_history(
                scenario.history_spo2_start,
                scenario.baseline_peep,
                scenario.baseline_fio2,
                scenario.baseline_tidal_vol,
            )
        )

        deterministic = twin.simulate(
            proposed=scenario.proposed,
            current_spo2=scenario.current_spo2,
            steps=4,
            noise_scale=0.0,
        )
        delta = deterministic["delta_spo2"]
        deterministic_deltas.append(delta)

        if (scenario.expected_trend == "up" and delta >= 0) or (
            scenario.expected_trend == "down" and delta <= 0
        ):
            trend_hits += 1

        applied = deterministic["applied"]
        if applied != {
            "PEEP": round(scenario.proposed["PEEP"], 1),
            "FiO2": round(scenario.proposed["FiO2"], 1),
            "TidalVol": round(scenario.proposed["TidalVol"], 1),
        }:
            clamped_actions += 1

        if deterministic["tv_risk"]:
            tv_warning_hits += 1

        # Replay stability with seeded stochastic path
        rng_a = np.random.default_rng(seed + idx)
        rng_b = np.random.default_rng(seed + idx)
        out_a = twin.simulate(
            proposed=scenario.proposed,
            current_spo2=scenario.current_spo2,
            steps=4,
            noise_scale=1.0,
            rng=rng_a,
        )
        out_b = twin.simulate(
            proposed=scenario.proposed,
            current_spo2=scenario.current_spo2,
            steps=4,
            noise_scale=1.0,
            rng=rng_b,
        )
        if out_a["trajectory"] == out_b["trajectory"]:
            replay_match_hits += 1

    n = len(scenarios)
    mae = float(np.mean(np.abs(deterministic_deltas)))
    rmse = float(math.sqrt(np.mean(np.square(deterministic_deltas))))

    return {
        "scenario_count": float(n),
        "trend_direction_accuracy": 100.0 * trend_hits / n,
        "clamp_activation_rate": 100.0 * clamped_actions / n,
        "tv_warning_rate": 100.0 * tv_warning_hits / n,
        "replay_consistency": 100.0 * replay_match_hits / n,
        "mean_abs_delta_spo2": mae,
        "rmse_delta_spo2": rmse,
    }


def evaluate_thresholds(
    metrics: Dict[str, float],
    min_trend_accuracy: float,
    min_replay_consistency: float,
    max_mean_abs_delta_spo2: float,
    max_rmse_delta_spo2: float,
) -> List[Tuple[str, bool, float, float, str]]:
    checks = [
        (
            "trend_direction_accuracy",
            metrics["trend_direction_accuracy"] >= min_trend_accuracy,
            metrics["trend_direction_accuracy"],
            min_trend_accuracy,
            "min",
        ),
        (
            "replay_consistency",
            metrics["replay_consistency"] >= min_replay_consistency,
            metrics["replay_consistency"],
            min_replay_consistency,
            "min",
        ),
        (
            "mean_abs_delta_spo2",
            metrics["mean_abs_delta_spo2"] <= max_mean_abs_delta_spo2,
            metrics["mean_abs_delta_spo2"],
            max_mean_abs_delta_spo2,
            "max",
        ),
        (
            "rmse_delta_spo2",
            metrics["rmse_delta_spo2"] <= max_rmse_delta_spo2,
            metrics["rmse_delta_spo2"],
            max_rmse_delta_spo2,
            "max",
        ),
    ]
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate digital twin Phase 2 metrics")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-trend-accuracy", type=float, default=70.0)
    parser.add_argument("--min-replay-consistency", type=float, default=100.0)
    parser.add_argument("--max-mean-abs-delta-spo2", type=float, default=8.0)
    parser.add_argument("--max-rmse-delta-spo2", type=float, default=10.0)
    parser.add_argument(
        "--fail-on-thresholds",
        action="store_true",
        help="Exit non-zero when any threshold check fails",
    )
    args = parser.parse_args()

    metrics = evaluate(seed=args.seed)
    print("=" * 64)
    print("Digital Twin Phase 2 Evaluation")
    print("=" * 64)
    for key, value in metrics.items():
        if key.endswith("_count"):
            print(f"{key:28s}: {int(value)}")
        elif key.endswith("_spo2"):
            print(f"{key:28s}: {value:.3f}")
        else:
            print(f"{key:28s}: {value:.2f}%")

    checks = evaluate_thresholds(
        metrics=metrics,
        min_trend_accuracy=args.min_trend_accuracy,
        min_replay_consistency=args.min_replay_consistency,
        max_mean_abs_delta_spo2=args.max_mean_abs_delta_spo2,
        max_rmse_delta_spo2=args.max_rmse_delta_spo2,
    )
    print("-" * 64)
    print("Threshold checks")
    failed = False
    for name, passed, value, threshold, mode in checks:
        status = "PASS" if passed else "FAIL"
        if mode == "min":
            print(f"[{status}] {name}: {value:.3f} >= {threshold:.3f}")
        else:
            print(f"[{status}] {name}: {value:.3f} <= {threshold:.3f}")
        if not passed:
            failed = True
    print("=" * 64)

    if failed and args.fail_on_thresholds:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
