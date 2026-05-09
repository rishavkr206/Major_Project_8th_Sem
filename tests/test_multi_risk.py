"""
Multi-Risk LSTM Test Suite
Tests the inference engine and API integration
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, Any

# Add repo root to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from services.multi_risk_inference import MultiRiskInferenceEngine
from pipelines.feature_engineering import (
    add_derived_features,
    add_ppo_state_reward_features,
)


def generate_dummy_history(n_steps: int = 12, base_spo2: float = 96.0) -> list:
    """Generate synthetic 3-hour history for testing."""
    history = []
    for i in range(n_steps):
        # Mild oscillation to simulate realistic variation
        offset = np.sin(i * 0.5) * 2
        record = {
            "HR": 85 + offset + np.random.randn() * 1.5,
            "MAP": 75 + offset * 0.5 + np.random.randn() * 1.2,
            "RespRate": 18 + offset * 0.3 + np.random.randn() * 0.8,
            "SpO2": base_spo2 + offset + np.random.randn() * 0.5,
            "PEEP": 5.0 + np.random.randn() * 0.2,
            "FiO2": 40.0 + np.random.randn() * 1.0,
            "TidalVol": 450 + offset * 2 + np.random.randn() * 10,
        }
        history.append(record)
    return history


def test_inference_engine():
    """Test basic inference engine functionality."""
    print("\n" + "=" * 70)
    print("TEST 1: Multi-Risk Inference Engine")
    print("=" * 70)
    
    engine = MultiRiskInferenceEngine()
    
    # Try to load
    if not engine.load():
        print("[SKIP] Model not trained yet. Run ml/multi_risk_training.py first.")
        return False
    
    print("[✓] Engine loaded successfully")
    
    # Test with random normalized sequence (standard normal distribution)
    # The model expects scaled data: mean=0, std=1
    print("\n  Testing with random normalized sequence...")
    X_test = np.random.randn(12, 102).astype(np.float32)
    
    try:
        results = engine.predict_sequence(X_test)
        
        print(f"    Next_SpO2: {results['Next_SpO2']['prediction']:.2f}")
        print(f"    Next_HR: {results['Next_HR']['prediction']:.1f}")
        print(f"    Hypoxia_Risk: {results['Hypoxia_Risk']['probability']:.4f}")
        print(f"    Tachycardia_Risk: {results['Tachycardia_Risk']['probability']:.4f}")
        print(f"    VILI_Risk: {results['VILI_Risk']['probability']:.4f}")
        
        print("\n[✓] Inference engine tests passed")
        return True
    except Exception as e:
        print(f"[✗] Inference failed: {e}")
        return False


def test_api_integration():
    """Test API endpoint integration (requires running server)."""
    print("\n" + "=" * 70)
    print("TEST 2: API Integration")
    print("=" * 70)
    
    try:
        import requests
    except ImportError:
        print("[SKIP] requests library not installed. Install with: pip install requests")
        return None
    
    # Try to reach API
    api_url = "http://127.0.0.1:9000"
    try:
        resp = requests.get(f"{api_url}/health", timeout=2)
        print(f"[✓] API server is running at {api_url}")
    except Exception as e:
        print(f"[SKIP] API server not running at {api_url}")
        print(f"       Start with: python -m uvicorn api.main:app --host 127.0.0.1 --port 9000")
        return None
    
    # Test /patient/{stay_id}/risks endpoint with synthetic data
    print("\n  Testing /patient/30004018/risks endpoint...")
    
    # Create 12 synthetic vital records (3 hours at 15-min intervals)
    history = [
        {
            "HR": 75 + np.random.randn() * 5,
            "MAP": 85 + np.random.randn() * 3,
            "RespRate": 16 + np.random.randn() * 2,
            "SpO2": 96 + np.random.randn() * 1,
            "PEEP": 5.0 + np.random.randn() * 0.5,
            "FiO2": 35.0 + np.random.randn() * 2,
            "TidalVol": 450 + np.random.randn() * 20,
        }
        for _ in range(12)
    ]
    
    payload = {"history": history}
    try:
        resp = requests.post(
            f"{api_url}/patient/30004018/risks",
            json=payload,
            timeout=10
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"[✓] Request successful (status={resp.status_code})")
            print(f"    Response keys: {list(result.keys())}")
            if "summary" in result:
                print(f"    High-risk flags: {result['summary'].get('high_risk_flags', [])}")
            return True
        else:
            print(f"[✗] Request failed (status={resp.status_code})")
            print(f"    Message: {resp.text}")
            return False
    except Exception as e:
        print(f"[✗] Request failed: {e}")
        return False


def test_evaluation_report():
    """Check if evaluation report was generated."""
    print("\n" + "=" * 70)
    print("TEST 3: Evaluation Report")
    print("=" * 70)
    
    report_path = os.path.join(REPO_ROOT, "reports", "model_evaluation_multi_risk.json")
    
    if not os.path.exists(report_path):
        print(f"[SKIP] Evaluation report not found at {report_path}")
        print("       This will be generated after model training completes.")
        return None
    
    with open(report_path, 'r') as fh:
        results = json.load(fh)
    
    print(f"[✓] Evaluation report found")
    print(f"\n  Regression Metrics (Next_*):")
    for target in ['Next_SpO2', 'Next_HR', 'Next_MAP', 'Next_RespRate', 'Next_TidalVol']:
        mae = results.get(f'{target}_mae', 'N/A')
        rmse = results.get(f'{target}_rmse', 'N/A')
        print(f"    {target:15s}: MAE={mae:8}, RMSE={rmse}")
    
    print(f"\n  Classification Metrics (Risk):")
    for target in ['Hypoxia_Risk', 'Tachycardia_Risk', 'Hypotension_Risk', 'Tachypnea_Risk', 'VILI_Risk']:
        auroc = results.get(f'{target}_auroc', 'N/A')
        f1 = results.get(f'{target}_f1_optimal', 'N/A')
        thresh = results.get(f'{target}_optimal_threshold', 'N/A')
        print(f"    {target:18s}: AUROC={auroc:8}, F1_opt={f1:8} @ thresh={thresh}")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  Multi-Risk LSTM Test Suite")
    print("=" * 70)
    
    results = {
        "inference_engine": None,
        "api_integration": None,
        "evaluation_report": None,
    }
    
    # Test 1: Inference Engine
    try:
        results["inference_engine"] = test_inference_engine()
    except Exception as e:
        print(f"[ERR] Inference engine test failed: {e}")
        results["inference_engine"] = False
    
    # Test 2: API Integration
    try:
        results["api_integration"] = test_api_integration()
    except Exception as e:
        print(f"[ERR] API integration test failed: {e}")
        results["api_integration"] = False
    
    # Test 3: Evaluation Report
    try:
        results["evaluation_report"] = test_evaluation_report()
    except Exception as e:
        print(f"[ERR] Evaluation report test failed: {e}")
        results["evaluation_report"] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("  Test Summary")
    print("=" * 70)
    for name, result in results.items():
        status = "✓ PASS" if result is True else "✗ FAIL" if result is False else "⊘ SKIP"
        print(f"  {name:30s}: {status}")
    
    passed = sum(1 for v in results.values() if v is True)
    total = len(results)
    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 70)


if __name__ == '__main__':
    main()
