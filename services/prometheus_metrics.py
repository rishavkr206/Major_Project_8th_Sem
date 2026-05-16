"""
Prometheus metrics for Grafana — time series of observed vitals vs LSTM forecast.

Install: pip install prometheus-client

Scrape from Docker Prometheus: run API with --host 0.0.0.0 so host.docker.internal:8000 reaches /metrics.
"""

from __future__ import annotations

from typing import Tuple

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

    _HAS_PROM = True
except ImportError:
    _HAS_PROM = False

if _HAS_PROM:
    # Gauges update on each /recommend; Prometheus scrape timestamps form the time series.
    OBSERVED_SPO2 = Gauge(
        "ventilator_observed_spo2",
        "Last observed SpO2 (%) from co-pilot /recommend payload",
    )
    LSTM_PRED_NEXT_SPO2 = Gauge(
        "ventilator_lstm_predicted_next_spo2",
        "Model-predicted next SpO2 (%) (Keras LSTM when active, else heuristic)",
    )
    LSTM_HYPOXIA_PROB = Gauge(
        "ventilator_lstm_hypoxia_probability",
        "Hypoxia risk probability [0,1] fed to policy",
    )
    LSTM_KERAS_ACTIVE = Gauge(
        "ventilator_lstm_keras_active",
        "1 if last /recommend used Keras LSTM inference, else 0",
    )
    LAST_STAY_ID = Gauge(
        "ventilator_recommend_stay_id",
        "stay_id on the most recent /recommend call",
    )


def record_recommendation_metrics(
    stay_id: int,
    observed_spo2: float,
    pred_next_spo2: float,
    hypoxia_prob: float,
    lstm_source: str,
) -> None:
    if not _HAS_PROM:
        return
    LAST_STAY_ID.set(float(stay_id))
    OBSERVED_SPO2.set(float(observed_spo2))
    LSTM_PRED_NEXT_SPO2.set(float(pred_next_spo2))
    LSTM_HYPOXIA_PROB.set(float(hypoxia_prob))
    LSTM_KERAS_ACTIVE.set(1.0 if lstm_source == "lstm_keras" else 0.0)


def metrics_response() -> Tuple[bytes, str]:
    """Body and Content-Type for GET /metrics."""
    if not _HAS_PROM:
        return (
            b"# prometheus_client not installed; pip install prometheus-client\n",
            "text/plain; charset=utf-8",
        )
    return generate_latest(), CONTENT_TYPE_LATEST


def prometheus_available() -> bool:
    return _HAS_PROM
