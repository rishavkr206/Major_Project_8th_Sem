"""
Deterministic demo test scenarios for terminal, API, dashboard, and Grafana.

These are presentation-oriented clinical simulations. They do not replace
clinical validation; they make the model and digital-twin behavior explainable
for repeatable demos.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

import numpy as np


@dataclass
class TestResult:
    scenario_name: str
    test_type: str
    history_length: int
    observations: int
    pred_spo2: float
    hypoxia_prob: float
    lstm_source: str
    alert_level: str
    key_findings: List[str]
    metadata: Dict[str, Any]
    predicted_vitals: Dict[str, float] = field(default_factory=dict)
    risk_predictions: Dict[str, Dict[str, float | int]] = field(default_factory=dict)


def _extended_outputs(
    history: List[Dict[str, Any]],
    pred_spo2: float,
    hypoxia_prob: float,
    alert_level: str,
) -> tuple[Dict[str, float], Dict[str, Dict[str, float | int]]]:
    recent = history[-50:] if len(history) >= 50 else history
    mean = lambda key: float(np.mean([float(row[key]) for row in recent]))
    next_hr = mean("HR")
    next_map = mean("MAP")
    next_rr = mean("RespRate")
    next_tv = mean("TidalVol")
    mean_peep = mean("PEEP")
    mean_fio2 = mean("FiO2")

    tachy_prob = float(np.clip((next_hr - 90.0) / 45.0, 0.02, 0.96))
    hypotension_prob = float(np.clip((75.0 - next_map) / 25.0, 0.02, 0.96))
    tachypnea_prob = float(np.clip((next_rr - 18.0) / 18.0, 0.02, 0.96))
    vili_prob = float(np.clip((mean_peep - 10.0) / 10.0 + (next_tv - 480.0) / 360.0, 0.02, 0.96))
    shock_prob = float(np.clip((tachy_prob * 0.35) + (hypotension_prob * 0.45) + (hypoxia_prob * 0.20), 0.02, 0.96))
    if alert_level == "CRITICAL":
        shock_prob = max(shock_prob, 0.62)

    predicted_vitals = {
        "Next_SpO2": round(float(pred_spo2), 2),
        "Next_HR": round(next_hr, 1),
        "Next_MAP": round(next_map, 1),
        "Next_RespRate": round(next_rr, 1),
        "Next_TidalVol": round(next_tv, 1),
        "Mean_PEEP": round(mean_peep, 1),
        "Mean_FiO2": round(mean_fio2, 1),
    }
    risks = {
        "Hypoxia_Risk": hypoxia_prob,
        "Tachycardia_Risk": tachy_prob,
        "Hypotension_Risk": hypotension_prob,
        "Tachypnea_Risk": tachypnea_prob,
        "VILI_Risk": vili_prob,
        "Shock_Risk": shock_prob,
    }
    risk_predictions = {
        name: {"probability": round(float(prob), 4), "risk": int(prob >= 0.5), "threshold": 0.5}
        for name, prob in risks.items()
    }
    return predicted_vitals, risk_predictions


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _record(
    *,
    spo2: float,
    hr: float,
    map_value: float,
    resp_rate: float,
    peep: float,
    fio2: float,
    tidal_vol: float,
) -> Dict[str, float]:
    return {
        "SpO2": float(np.clip(spo2, 70.0, 100.0)),
        "HR": float(np.clip(hr, 40.0, 180.0)),
        "MAP": float(np.clip(map_value, 45.0, 130.0)),
        "RespRate": float(np.clip(resp_rate, 6.0, 45.0)),
        "PEEP": float(np.clip(peep, 0.0, 24.0)),
        "FiO2": float(np.clip(fio2, 21.0, 100.0)),
        "TidalVol": float(np.clip(tidal_vol, 120.0, 750.0)),
    }


def _basic_prediction(history: List[Dict[str, Any]], severity_bias: float = 0.0) -> tuple[float, float]:
    spo2 = np.array([float(h["SpO2"]) for h in history], dtype=float)
    rr = np.array([float(h["RespRate"]) for h in history], dtype=float)
    hr = np.array([float(h["HR"]) for h in history], dtype=float)
    fio2 = np.array([float(h["FiO2"]) for h in history], dtype=float)
    peep = np.array([float(h["PEEP"]) for h in history], dtype=float)

    recent_spo2 = float(np.mean(spo2[-50:]))
    trend = float(spo2[-1] - spo2[max(0, len(spo2) - 200)])
    pred_spo2 = recent_spo2 + (trend / 60.0) - severity_bias

    oxygen_support = np.clip((np.mean(fio2[-50:]) - 21.0) / 79.0, 0.0, 1.0)
    peep_support = np.clip((np.mean(peep[-50:]) - 5.0) / 15.0, 0.0, 1.0)
    physiology_load = np.clip((np.mean(rr[-50:]) - 16.0) / 18.0, 0.0, 1.0)
    tachy_load = np.clip((np.mean(hr[-50:]) - 90.0) / 50.0, 0.0, 1.0)
    hypoxia_load = np.clip((94.0 - pred_spo2) / 12.0, 0.0, 1.0)
    hypoxia_prob = 0.03 + 0.55 * hypoxia_load + 0.18 * physiology_load + 0.14 * oxygen_support + 0.10 * tachy_load + 0.05 * peep_support
    return float(np.clip(pred_spo2, 70.0, 100.0)), float(np.clip(hypoxia_prob, 0.0, 0.98))


def _alert(hypoxia_prob: float, pred_spo2: float) -> str:
    if hypoxia_prob >= 0.70 or pred_spo2 < 88.0:
        return "CRITICAL"
    if hypoxia_prob >= 0.25 or pred_spo2 < 94.0:
        return "WARNING"
    return "STABLE"


class HealthyPersonScenario:
    """Baseline control: stable vitals and low ventilator support."""

    @staticmethod
    def generate_history(length: int, seed: int = 101) -> List[Dict[str, Any]]:
        rng = _rng(seed + length)
        history = []
        for i in range(length):
            circadian = np.sin(i / 96.0) * 0.25
            history.append(
                _record(
                    spo2=rng.normal(97.3 + circadian, 0.45),
                    hr=rng.normal(72, 4),
                    map_value=rng.normal(86, 3),
                    resp_rate=rng.normal(14, 1.1),
                    peep=rng.normal(5.0, 0.15),
                    fio2=rng.normal(21.0, 0.2),
                    tidal_vol=rng.normal(455, 18),
                )
            )
        return history

    @staticmethod
    def test_lstm_output(history: List[Dict[str, Any]], label: str = "Healthy Person (Control)") -> TestResult:
        pred_spo2, hypoxia_prob = _basic_prediction(history)
        alert_level = _alert(hypoxia_prob, pred_spo2)
        predicted_vitals, risk_predictions = _extended_outputs(history, pred_spo2, hypoxia_prob, alert_level)
        spo2_values = [h["SpO2"] for h in history]
        return TestResult(
            scenario_name=label,
            test_type="control" if "Control" in label else "health_status",
            history_length=len(history),
            observations=len(history),
            pred_spo2=pred_spo2,
            hypoxia_prob=hypoxia_prob,
            lstm_source="scenario_lstm_surrogate",
            alert_level=alert_level,
            key_findings=[
                f"Mean SpO2 {np.mean(spo2_values):.1f}% with low variation",
                "Hypoxia probability stays in the low-risk band",
                "HR, MAP, and respiratory rate remain inside normal demo limits",
                "Acts as the control case for comparison with infection/weather/anomaly cases",
            ],
            metadata={
                "mean_spo2": round(float(np.mean(spo2_values)), 2),
                "std_spo2": round(float(np.std(spo2_values)), 2),
                "min_spo2": round(float(np.min(spo2_values)), 2),
                "max_spo2": round(float(np.max(spo2_values)), 2),
            },
            predicted_vitals=predicted_vitals,
            risk_predictions=risk_predictions,
        )


class LungInfectionScenario:
    """Respiratory infection: worsening gas exchange and rising support."""

    @staticmethod
    def generate_history(length: int, infection_severity: str = "moderate", seed: int = 202) -> List[Dict[str, Any]]:
        rng = _rng(seed + length + len(infection_severity))
        severity_cfg = {
            "mild": {"decline": 3.5, "hr": 88, "rr": 18, "fio2": 34, "peep": 7.0, "bias": 0.6},
            "moderate": {"decline": 9.0, "hr": 101, "rr": 23, "fio2": 56, "peep": 10.0, "bias": 1.6},
            "severe": {"decline": 15.0, "hr": 119, "rr": 29, "fio2": 78, "peep": 14.0, "bias": 3.0},
        }[infection_severity]
        history = []
        for i in range(length):
            progress = i / max(length - 1, 1)
            history.append(
                _record(
                    spo2=rng.normal(96.0 - severity_cfg["decline"] * progress, 0.65),
                    hr=rng.normal(severity_cfg["hr"] + 10.0 * progress, 5.5),
                    map_value=rng.normal(83.0 - 9.0 * progress, 4.5),
                    resp_rate=rng.normal(severity_cfg["rr"] + 4.0 * progress, 2.0),
                    peep=rng.normal(severity_cfg["peep"] + 2.0 * progress, 0.35),
                    fio2=rng.normal(severity_cfg["fio2"] + 10.0 * progress, 2.0),
                    tidal_vol=rng.normal(430.0 - 35.0 * progress, 24.0),
                )
            )
        return history

    @staticmethod
    def test_lstm_output(history: List[Dict[str, Any]], severity: str = "moderate") -> TestResult:
        bias = {"mild": 0.6, "moderate": 1.6, "severe": 3.0}[severity]
        pred_spo2, hypoxia_prob = _basic_prediction(history, severity_bias=bias)
        alert_level = _alert(hypoxia_prob, pred_spo2)
        predicted_vitals, risk_predictions = _extended_outputs(history, pred_spo2, hypoxia_prob, alert_level)
        spo2_values = [h["SpO2"] for h in history]
        return TestResult(
            scenario_name=f"Lung Infection ({severity.title()})",
            test_type="health_status",
            history_length=len(history),
            observations=len(history),
            pred_spo2=pred_spo2,
            hypoxia_prob=hypoxia_prob,
            lstm_source="scenario_lstm_surrogate",
            alert_level=alert_level,
            key_findings=[
                f"SpO2 trend {spo2_values[0]:.1f}% -> {spo2_values[-1]:.1f}%",
                f"Predicted hypoxia risk {(hypoxia_prob * 100):.1f}%",
                "Higher respiratory rate and heart rate increase the risk score",
                "Ventilator support rises through FiO2 and PEEP escalation",
            ],
            metadata={
                "severity": severity,
                "spo2_trend_per_sample": round(float((spo2_values[-1] - spo2_values[0]) / len(history)), 5),
                "mean_recent_fio2": round(float(np.mean([h["FiO2"] for h in history[-50:]])), 2),
                "mean_recent_peep": round(float(np.mean([h["PEEP"] for h in history[-50:]])), 2),
            },
            predicted_vitals=predicted_vitals,
            risk_predictions=risk_predictions,
        )


class WeatherImpactScenario:
    """Weather/environment test: changes that perturb oxygenation and ventilator output."""

    WEATHER_EFFECTS = {
        "normal": {"label": "Normal Conditions", "spo2_delta": 0.0, "fio2_delta": 0.0, "peep_delta": 0.0, "tv_delta": 0.0},
        "high_humidity": {"label": "High Humidity (>80%)", "spo2_delta": -1.1, "fio2_delta": 3.0, "peep_delta": 0.5, "tv_delta": -8.0},
        "high_temperature": {"label": "High Temperature (>30C)", "spo2_delta": -0.8, "fio2_delta": 2.0, "peep_delta": 0.2, "tv_delta": -5.0},
        "low_pressure": {"label": "Low Atmospheric Pressure (<950 hPa)", "spo2_delta": -1.7, "fio2_delta": 5.0, "peep_delta": 0.8, "tv_delta": -12.0},
    }

    @classmethod
    def generate_history(cls, length: int, weather: str = "normal", seed: int = 303) -> List[Dict[str, Any]]:
        rng = _rng(seed + length + len(weather))
        effect = cls.WEATHER_EFFECTS[weather]
        history = []
        for i in range(length):
            drift = (i / max(length - 1, 1)) * effect["spo2_delta"] * 0.4
            history.append(
                _record(
                    spo2=rng.normal(96.4 + effect["spo2_delta"] + drift, 0.55),
                    hr=rng.normal(76 + abs(effect["spo2_delta"]) * 1.5, 4),
                    map_value=rng.normal(84, 3.5),
                    resp_rate=rng.normal(15 + abs(effect["spo2_delta"]) * 0.7, 1.5),
                    peep=rng.normal(6.0 + effect["peep_delta"], 0.2),
                    fio2=rng.normal(24.0 + effect["fio2_delta"], 1.0),
                    tidal_vol=rng.normal(445.0 + effect["tv_delta"], 18.0),
                )
            )
        return history

    @classmethod
    def test_lstm_output(cls, history: List[Dict[str, Any]], weather: str = "normal") -> TestResult:
        effect = cls.WEATHER_EFFECTS[weather]
        pred_spo2, hypoxia_prob = _basic_prediction(history, severity_bias=max(0.0, abs(effect["spo2_delta"]) * 0.25))
        alert_level = _alert(hypoxia_prob, pred_spo2)
        predicted_vitals, risk_predictions = _extended_outputs(history, pred_spo2, hypoxia_prob, alert_level)
        spo2_values = [h["SpO2"] for h in history]
        return TestResult(
            scenario_name=f"Weather Impact: {effect['label']}",
            test_type="weather_impact",
            history_length=len(history),
            observations=len(history),
            pred_spo2=pred_spo2,
            hypoxia_prob=hypoxia_prob,
            lstm_source="scenario_lstm_surrogate",
            alert_level=alert_level,
            key_findings=[
                f"Weather-adjusted mean SpO2 {np.mean(spo2_values):.1f}%",
                f"Expected ventilator response: FiO2 +{effect['fio2_delta']:.1f}, PEEP +{effect['peep_delta']:.1f}",
                f"Tidal volume effect {effect['tv_delta']:.1f} mL from compliance/environment pressure",
                "Low pressure and high humidity produce the strongest demo impact",
            ],
            metadata={
                "weather_condition": weather,
                "spo2_delta": effect["spo2_delta"],
                "fio2_delta": effect["fio2_delta"],
                "peep_delta": effect["peep_delta"],
                "tidal_volume_delta_ml": effect["tv_delta"],
                "mean_spo2": round(float(np.mean(spo2_values)), 2),
            },
            predicted_vitals=predicted_vitals,
            risk_predictions=risk_predictions,
        )


class AnomalyScenario:
    """Ventilator/equipment or acute clinical anomaly tests."""

    @staticmethod
    def generate_history(length: int, anomaly_type: str = "disconnect", seed: int = 404) -> List[Dict[str, Any]]:
        rng = _rng(seed + length + len(anomaly_type))
        onset = max(int(length * 0.6), 50)
        history = []
        for i in range(length):
            if i < onset:
                history.append(
                    _record(
                        spo2=rng.normal(96.6, 0.45),
                        hr=rng.normal(73, 4),
                        map_value=rng.normal(85, 3),
                        resp_rate=rng.normal(14, 1.1),
                        peep=rng.normal(5.5, 0.15),
                        fio2=rng.normal(24, 0.8),
                        tidal_vol=rng.normal(452, 18),
                    )
                )
                continue

            progress = (i - onset) / max(length - onset - 1, 1)
            if anomaly_type == "disconnect":
                row = _record(
                    spo2=rng.normal(90.0 - 10.0 * progress, 1.8),
                    hr=rng.normal(105 + 18 * progress, 6),
                    map_value=rng.normal(75 - 8 * progress, 5),
                    resp_rate=rng.normal(22 + 5 * progress, 2.3),
                    peep=rng.normal(0.5, 0.3),
                    fio2=rng.normal(21.0, 0.4),
                    tidal_vol=rng.normal(150, 30),
                )
            elif anomaly_type == "obstruction":
                row = _record(
                    spo2=rng.normal(91.0 - 6.5 * progress, 1.4),
                    hr=rng.normal(96 + 12 * progress, 6),
                    map_value=rng.normal(78 - 5 * progress, 4),
                    resp_rate=rng.normal(20 + 4 * progress, 2.0),
                    peep=rng.normal(18.0, 0.8),
                    fio2=rng.normal(90.0, 2.5),
                    tidal_vol=rng.normal(210, 25),
                )
            elif anomaly_type == "sensor_drift":
                row = _record(
                    spo2=rng.normal(100.8 + 1.5 * progress, 0.8),
                    hr=rng.normal(73, 4),
                    map_value=rng.normal(85, 3),
                    resp_rate=rng.normal(14, 1.1),
                    peep=rng.normal(5.5, 0.15),
                    fio2=rng.normal(24, 0.8),
                    tidal_vol=rng.normal(452, 18),
                )
            else:
                row = _record(
                    spo2=rng.normal(95.0, 3.0),
                    hr=rng.normal(75, 12),
                    map_value=rng.normal(84, 8),
                    resp_rate=rng.normal(15, 3),
                    peep=rng.choice([2.0, 5.5, 18.0, 24.0]),
                    fio2=rng.choice([21.0, 35.0, 70.0, 100.0]),
                    tidal_vol=rng.normal(360, 95),
                )
            history.append(row)
        return history

    @staticmethod
    def test_lstm_output(history: List[Dict[str, Any]], anomaly_type: str = "disconnect") -> TestResult:
        pred_spo2, base_prob = _basic_prediction(history, severity_bias=2.2)
        spo2_values = [h["SpO2"] for h in history]
        onset = max(int(len(history) * 0.6), 50)
        anomaly_labels = {
            "disconnect": "Tube Disconnect / Ventilator Failure",
            "obstruction": "Airway Obstruction",
            "sensor_drift": "SpO2 Sensor Drift",
            "calibration_loss": "Ventilator Calibration Loss",
        }
        hypoxia_prob = 0.45 if anomaly_type == "sensor_drift" else max(base_prob, 0.78)
        alert = "WARNING" if anomaly_type == "sensor_drift" else "CRITICAL"
        predicted_vitals, risk_predictions = _extended_outputs(history, pred_spo2, hypoxia_prob, alert)
        return TestResult(
            scenario_name=f"Anomaly: {anomaly_labels.get(anomaly_type, anomaly_type)}",
            test_type="anomaly_detection",
            history_length=len(history),
            observations=len(history),
            pred_spo2=pred_spo2,
            hypoxia_prob=float(np.clip(hypoxia_prob, 0.0, 0.98)),
            lstm_source="scenario_lstm_surrogate",
            alert_level=alert,
            key_findings=[
                f"Anomaly onset at sample {onset}",
                f"Pre/post SpO2 mean {np.mean(spo2_values[:onset]):.1f}% -> {np.mean(spo2_values[onset:]):.1f}%",
                f"Detected pattern: {anomaly_type}",
                "Requires clinician review before accepting ventilator changes",
            ],
            metadata={
                "anomaly_type": anomaly_type,
                "anomaly_onset_sample": onset,
                "spo2_pre_anomaly": round(float(np.mean(spo2_values[:onset])), 2),
                "spo2_post_anomaly": round(float(np.mean(spo2_values[onset:])), 2),
            },
            predicted_vitals=predicted_vitals,
            risk_predictions=risk_predictions,
        )


class LSTMHistoryLengthScenario:
    """LSTM output every 1000 values, 2000 values, and so on."""

    LENGTHS = [1000, 2000, 3000, 4000, 5000]

    @classmethod
    def test_all_lengths(cls) -> List[TestResult]:
        results = []
        for length in cls.LENGTHS:
            history = HealthyPersonScenario.generate_history(length)
            result = HealthyPersonScenario.test_lstm_output(history, label=f"LSTM Window Test ({length} values)")
            result.test_type = "lstm_history_length"
            result.key_findings = [
                f"Processed {length} sequential ventilator values",
                f"Predicted next SpO2 {result.pred_spo2:.1f}%",
                f"Hypoxia probability {(result.hypoxia_prob * 100):.1f}%",
                "Output remains stable as history length increases in the control stream",
            ]
            result.metadata["window_values"] = length
            results.append(result)
        return results


def run_all_scenarios() -> Dict[str, List[TestResult]]:
    """Execute all demo scenarios and return dashboard-ready groups."""
    return {
        "control": [
            HealthyPersonScenario.test_lstm_output(
                HealthyPersonScenario.generate_history(2000),
                label="Healthy Person (Baseline Control)",
            )
        ],
        "lstm_history_length": LSTMHistoryLengthScenario.test_all_lengths(),
        "health_status": [
            LungInfectionScenario.test_lstm_output(
                LungInfectionScenario.generate_history(2000, severity),
                severity,
            )
            for severity in ["mild", "moderate", "severe"]
        ],
        "weather_impact": [
            WeatherImpactScenario.test_lstm_output(
                WeatherImpactScenario.generate_history(2000, weather),
                weather,
            )
            for weather in ["normal", "high_humidity", "high_temperature", "low_pressure"]
        ],
        "anomaly_detection": [
            AnomalyScenario.test_lstm_output(
                AnomalyScenario.generate_history(2000, anomaly),
                anomaly,
            )
            for anomaly in ["disconnect", "obstruction", "sensor_drift", "calibration_loss"]
        ],
    }


def results_to_dict(results: Dict[str, List[TestResult]]) -> Dict[str, List[Dict[str, Any]]]:
    return {category: [asdict(result) for result in test_results] for category, test_results in results.items()}


def format_console_report(results: Dict[str, List[TestResult]]) -> str:
    lines = []
    lines.append("")
    lines.append("=" * 88)
    lines.append("VENTILATOR LSTM / RISK / WEATHER / ANOMALY TEST CASES".center(88))
    lines.append("=" * 88)
    for category, test_results in results.items():
        lines.append("")
        lines.append(category.upper().replace("_", " ").center(88))
        lines.append("-" * 88)
        for result in test_results:
            lines.append(f"{result.scenario_name}")
            lines.append(
                f"  type={result.test_type} | observations={result.observations} | "
                f"pred_spo2={result.pred_spo2:.1f}% | hypoxia={result.hypoxia_prob * 100:.1f}% | "
                f"alert={result.alert_level} | source={result.lstm_source}"
            )
            for finding in result.key_findings:
                lines.append(f"  - {finding}")
            lines.append(f"  metadata={json.dumps(result.metadata, sort_keys=True)}")
            lines.append("")
    lines.append("=" * 88)
    return "\n".join(lines)


if __name__ == "__main__":
    scenario_results = run_all_scenarios()
    print(format_console_report(scenario_results))
