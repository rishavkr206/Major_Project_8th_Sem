import unittest

from fastapi.testclient import TestClient

from api.main import app


class SimulatorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_create_session_and_fetch_next_record(self) -> None:
        create_resp = self.client.post(
            "/simulator/session/910001",
            params={
                "profile": "ards",
                "packet_loss_probability": 0.02,
                "artifact_probability": 0.01,
                "trend_strength": 0.05,
                "seed": 101,
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        payload = create_resp.json()
        self.assertEqual(payload["status"], "created")
        session_key = payload["session_key"]

        next_resp = self.client.get(
            f"/simulator/session/{session_key}/next",
            params={"stay_id": 910001},
        )
        self.assertEqual(next_resp.status_code, 200)
        record = next_resp.json()["record"]
        for required in [
            "stay_id",
            "charttime",
            "HR",
            "MAP",
            "RespRate",
            "SpO2",
            "PEEP",
            "FiO2",
            "TidalVol",
        ]:
            self.assertIn(required, record)

    def test_batch_limits_and_not_found_handling(self) -> None:
        missing_session_resp = self.client.get(
            "/simulator/session/missing:session:key/batch",
            params={"stay_id": 910001, "steps": 10},
        )
        self.assertEqual(missing_session_resp.status_code, 404)

        create_resp = self.client.post(
            "/simulator/session/910002",
            params={"profile": "normal", "seed": 202},
        )
        self.assertEqual(create_resp.status_code, 200)
        session_key = create_resp.json()["session_key"]

        invalid_steps_resp = self.client.get(
            f"/simulator/session/{session_key}/batch",
            params={"stay_id": 910002, "steps": 0},
        )
        self.assertEqual(invalid_steps_resp.status_code, 400)

        ok_steps_resp = self.client.get(
            f"/simulator/session/{session_key}/batch",
            params={"stay_id": 910002, "steps": 6},
        )
        self.assertEqual(ok_steps_resp.status_code, 200)
        records = ok_steps_resp.json()["records"]
        self.assertEqual(len(records), 6)

    def test_twin_replay_endpoint_deterministic_and_validation(self) -> None:
        history = [
            {
                "SpO2": 91.0 + (i * 0.1),
                "PEEP": 8.0,
                "FiO2": 55.0,
                "TidalVol": 450.0,
                "HR": 90,
                "MAP": 75,
                "RespRate": 20,
            }
            for i in range(12)
        ]

        deterministic_resp = self.client.post(
            "/twin/replay",
            json={
                "stay_id": 910050,
                "history": history,
                "proposed": {"PEEP": 10.0, "FiO2": 65.0, "TidalVol": 430.0},
                "current_spo2": 92.0,
                "steps": 4,
                "noise_scale": 0.0,
            },
        )
        self.assertEqual(deterministic_resp.status_code, 200)
        body = deterministic_resp.json()
        self.assertEqual(body["mode"], "deterministic")
        self.assertIn("result", body)
        self.assertIn("trajectory", body["result"])
        self.assertEqual(len(body["result"]["trajectory"]), 5)

        invalid_steps_resp = self.client.post(
            "/twin/replay",
            json={
                "history": history,
                "proposed": {"PEEP": 10.0, "FiO2": 65.0, "TidalVol": 430.0},
                "steps": 0,
            },
        )
        self.assertEqual(invalid_steps_resp.status_code, 400)

    def test_twin_replay_writes_twin_sim_audit_event(self) -> None:
        """Phase 5 wiring: every /twin/replay call must append a TWIN_SIM audit block."""
        stay_id = 910099
        history = [
            {
                "SpO2": 92.0 + (i * 0.1),
                "PEEP": 8.0,
                "FiO2": 55.0,
                "TidalVol": 450.0,
                "HR": 90,
                "MAP": 75,
                "RespRate": 20,
            }
            for i in range(12)
        ]
        replay_resp = self.client.post(
            "/twin/replay",
            json={
                "stay_id": stay_id,
                "history": history,
                "proposed": {"PEEP": 11.0, "FiO2": 60.0, "TidalVol": 440.0},
                "current_spo2": 92.5,
                "steps": 4,
                "noise_scale": 0.0,
            },
        )
        self.assertEqual(replay_resp.status_code, 200)

        trail_resp = self.client.get(f"/patient/{stay_id}/audit_trail")
        self.assertEqual(trail_resp.status_code, 200)
        trail = trail_resp.json()["trail"]
        twin_blocks = [b for b in trail if b["event_type"] == "TWIN_SIM"]
        self.assertGreaterEqual(len(twin_blocks), 1, "TWIN_SIM block should be appended")
        self.assertEqual(twin_blocks[0]["actor"], "SYSTEM_TWIN")

        # Whole chain must still verify after the new block is appended.
        verify_resp = self.client.get("/audit/verify")
        self.assertEqual(verify_resp.status_code, 200)
        self.assertTrue(verify_resp.json()["valid"], "audit chain must remain valid after TWIN_SIM")

    def test_demo_scenarios_endpoint_returns_control_and_length_cases(self) -> None:
        resp = self.client.get("/tests/run-scenarios")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "success")
        self.assertIn("control", body["results"])
        self.assertEqual(len(body["results"]["control"]), 1)
        control = body["results"]["control"][0]
        self.assertIn("predicted_vitals", control)
        self.assertIn("risk_predictions", control)
        self.assertIn("Next_HR", control["predicted_vitals"])
        self.assertIn("Shock_Risk", control["risk_predictions"])

        lengths = [
            item["observations"]
            for item in body["results"]["lstm_history_length"]
        ]
        self.assertEqual(lengths, [1000, 2000, 3000, 4000, 5000])

        categories = ["health_status", "weather_impact", "anomaly_detection"]
        for category in categories:
            self.assertGreater(len(body["results"][category]), 0)
            for result in body["results"][category]:
                self.assertIn(result["alert_level"], {"STABLE", "WARNING", "CRITICAL"})
                self.assertGreaterEqual(result["hypoxia_prob"], 0.0)
                self.assertLessEqual(result["hypoxia_prob"], 1.0)

    def test_model_evaluation_endpoint_returns_saved_metrics(self) -> None:
        resp = self.client.get("/model/evaluation")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "success")
        self.assertIn("lstm_dual_head", body["reports"])
        self.assertIn("multi_risk_lstm", body["reports"])
        self.assertIn("next_spo2_mae", body["reports"]["lstm_dual_head"])
        self.assertIn("Next_HR_mae", body["reports"]["multi_risk_lstm"])


if __name__ == "__main__":
    unittest.main()
