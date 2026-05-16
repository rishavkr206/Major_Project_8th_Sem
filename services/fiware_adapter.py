import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx

DEFAULT_FIWARE_BASE_URL = "http://localhost:1026"
DEFAULT_FIWARE_API_VERSION = "ld"  # use ngsi-ld by default; set FIWARE_API_VERSION=v2 for NGSI v2
DEFAULT_FIWARE_SERVICE = "openiot"
DEFAULT_FIWARE_SERVICE_PATH = "/"


class FiwareAdapter:
    """Simple FIWARE Orion adapter for digital twin telemetry and twin state sync."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        service: Optional[str] = None,
        service_path: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("FIWARE_BASE_URL", DEFAULT_FIWARE_BASE_URL)).rstrip("/")
        self.api_version = (api_version or os.getenv("FIWARE_API_VERSION", DEFAULT_FIWARE_API_VERSION)).lower()
        self.service = service or os.getenv("FIWARE_SERVICE", DEFAULT_FIWARE_SERVICE)
        self.service_path = service_path or os.getenv("FIWARE_SERVICE_PATH", DEFAULT_FIWARE_SERVICE_PATH)
        self.enabled = os.getenv("FIWARE_ENABLED", "true").strip().lower() not in ("0", "false", "no")
        self.client = httpx.Client(timeout=10.0)

    def _headers(self) -> Dict[str, str]:
        if self.api_version == "ld":
            headers = {
                "Content-Type": "application/ld+json; charset=utf-8",
                "Link": "<https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld>; rel=\"http://www.w3.org/ns/json-ld#context\"; type=\"application/ld+json\"",
            }
        else:
            headers = {"Content-Type": "application/json"}

        if self.service:
            headers["Fiware-Service"] = self.service
        if self.service_path:
            headers["Fiware-ServicePath"] = self.service_path
        return headers

    def _entity_id(self, stay_id: int) -> str:
        if self.api_version == "ld":
            return f"urn:ngsi-ld:VentilatorTwin:{stay_id}"
        return f"VentilatorTwin:{stay_id}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_entity_payload(
        self,
        stay_id: int,
        attributes: Dict[str, Any],
        observed_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        observed_at = observed_at or self._now()
        entity: Dict[str, Any] = {
            "id": self._entity_id(stay_id),
            "type": "VentilatorTwin",
        }

        for key, value in attributes.items():
            if self.api_version == "ld":
                entity[key] = {
                    "type": "Property",
                    "value": value,
                    "observedAt": observed_at,
                }
            else:
                entity[key] = {"value": value}

        return entity

    def _post(self, path: str, payload: Any) -> httpx.Response:
        if not self.enabled:
            raise RuntimeError("FIWARE integration is disabled by FIWARE_ENABLED=false")
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        return self.client.post(url, json=payload, headers=self._headers())

    def health_check(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "reachable": False, "detail": "FIWARE integration disabled"}

        try:
            if self.api_version == "ld":
                response = self.client.get(
                    f"{self.base_url}/ngsi-ld/v1/entities?limit=1",
                    headers=self._headers(),
                    timeout=5.0,
                )
            else:
                response = self.client.get(
                    f"{self.base_url}/v2/entities?options=count",
                    headers=self._headers(),
                    timeout=5.0,
                )
            return {
                "enabled": True,
                "reachable": response.status_code in (200, 204),
                "status_code": response.status_code,
                "detail": response.text,
            }
        except Exception as exc:
            return {"enabled": True, "reachable": False, "detail": str(exc)}

    def publish_entity(self, stay_id: int, attributes: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False

        payload = self._build_entity_payload(stay_id, attributes)
        try:
            if self.api_version == "ld":
                response = self._post("/ngsi-ld/v1/entityOperations/upsert", payload)
            else:
                response = self._post("/v2/entities?options=upsert", payload)

            if response.status_code not in (200, 201, 204):
                raise RuntimeError(
                    f"FIWARE publish failed: {response.status_code} {response.text}"
                )
            return True
        except Exception as exc:
            raise RuntimeError(f"FIWARE publish error: {exc}") from exc

    def publish_patient_history(self, stay_id: int, history: List[Dict[str, Any]]) -> bool:
        if not self.enabled or not history:
            return False

        latest = history[-1]
        payload = {
            "SpO2": latest.get("SpO2"),
            "PEEP": latest.get("PEEP"),
            "FiO2": latest.get("FiO2"),
            "TidalVol": latest.get("TidalVol"),
            "HR": latest.get("HR"),
            "MAP": latest.get("MAP"),
            "RespRate": latest.get("RespRate"),
            "observationSource": "patient-history",
            "historyLength": len(history),
        }
        return self.publish_entity(stay_id, payload)

    def publish_twin_simulation(
        self,
        stay_id: int,
        result: Dict[str, Any],
        current_vitals: Dict[str, Any],
        twin_state: Dict[str, Any],
        history_length: int = 0,
    ) -> bool:
        if not self.enabled:
            return False

        payload = {
            "SpO2": current_vitals.get("SpO2"),
            "PEEP": current_vitals.get("PEEP"),
            "FiO2": current_vitals.get("FiO2"),
            "TidalVol": current_vitals.get("TidalVol"),
            "HR": current_vitals.get("HR"),
            "MAP": current_vitals.get("MAP"),
            "RespRate": current_vitals.get("RespRate"),
            "complianceFactor": twin_state.get("compliance_factor"),
            "baselineSpO2": twin_state.get("baseline_spo2"),
            "lastPEEP": twin_state.get("last_PEEP"),
            "lastFiO2": twin_state.get("last_FiO2"),
            "lastTidalVol": twin_state.get("last_TidalVol"),
            "uncertainty": twin_state.get("uncertainty"),
            "isCalibrated": twin_state.get("is_calibrated"),
            "trajectory": result.get("trajectory"),
            "upperBand": result.get("upper_band"),
            "lowerBand": result.get("lower_band"),
            "meanSpO2": result.get("mean_spo2"),
            "deltaSpO2": result.get("delta_spo2"),
            "riskFlag": result.get("risk_flag"),
            "tvRisk": result.get("tv_risk"),
            "appliedPEEP": result.get("applied", {}).get("PEEP"),
            "appliedFiO2": result.get("applied", {}).get("FiO2"),
            "appliedTidalVol": result.get("applied", {}).get("TidalVol"),
            "eventSource": "digital-twin-replay",
            "historyLength": history_length,
        }
        return self.publish_entity(stay_id, payload)

    def publish_recommendation(
        self,
        stay_id: int,
        result: Dict[str, Any],
        current_vitals: Dict[str, Any],
        history_length: int = 0,
    ) -> bool:
        if not self.enabled:
            return False

        payload = {
            "SpO2": current_vitals.get("SpO2"),
            "PEEP": current_vitals.get("PEEP"),
            "FiO2": current_vitals.get("FiO2"),
            "TidalVol": current_vitals.get("TidalVol"),
            "HR": current_vitals.get("HR"),
            "MAP": current_vitals.get("MAP"),
            "RespRate": current_vitals.get("RespRate"),
            "predNextSpO2": result.get("pred_next_spo2"),
            "hypoxiaProb": result.get("hypoxia_prob"),
            "lstmSource": result.get("lstm_forecast_source"),
            "proposedPEEP": result.get("proposed", {}).get("PEEP"),
            "proposedFiO2": result.get("proposed", {}).get("FiO2"),
            "proposedTidalVol": result.get("proposed", {}).get("TidalVol"),
            "deltaPEEP": result.get("delta", {}).get("PEEP"),
            "deltaFiO2": result.get("delta", {}).get("FiO2"),
            "deltaTidalVol": result.get("delta", {}).get("TidalVol"),
            "alertLevel": result.get("alert_level"),
            "riskFlags": result.get("safety_flags"),
            "eventSource": "ppo-recommendation",
            "historyLength": history_length,
        }
        return self.publish_entity(stay_id, payload)
