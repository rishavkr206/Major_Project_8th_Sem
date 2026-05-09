"""
Multi-Risk LSTM Inference Engine
Blockchain-Enabled Digital Twin Framework
Predict 5 clinical risks + next-step vitals from ventilator sequences
"""

import os
import pickle
import json
import numpy as np
import warnings
warnings.filterwarnings('ignore')

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

# Navigate from services/ to repo root to ml/multi_risk/
SERVICES_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SERVICES_DIR, ".."))
MULTI_RISK_DIR = os.path.join(REPO_ROOT, "ml", "multi_risk")
MODEL_PATH = os.path.join(MULTI_RISK_DIR, "multi_risk_lstm.keras")

# Target column names (must match training)
REG_TARGETS = ["Next_SpO2", "Next_HR", "Next_MAP", "Next_RespRate", "Next_TidalVol"]
CLS_TARGETS = ["Hypoxia_Risk", "Tachycardia_Risk", "Hypotension_Risk", "Tachypnea_Risk", "VILI_Risk", "Shock_Risk"]

# Risk thresholds for classification
RISK_THRESHOLDS = {
    "Hypoxia_Risk": 0.5,
    "Tachycardia_Risk": 0.5,
    "Hypotension_Risk": 0.5,
    "Tachypnea_Risk": 0.5,
    "VILI_Risk": 0.5,
    "Shock_Risk": 0.5,  # tune via risk_thresholds.json after training
}


class MultiRiskInferenceEngine:
    """Multi-task LSTM inference for 5 clinical risks."""
    
    def __init__(self, model_path: str = MODEL_PATH, multi_risk_dir: str = MULTI_RISK_DIR):
        self.model_path = model_path
        self.multi_risk_dir = multi_risk_dir
        self.model = None
        self.scaler = None
        self.y_reg_mean = None
        self.y_reg_std = None
        self.feature_cols = None
        self.metadata = None
        self.ready = False
    
    @staticmethod
    def _create_focal_loss(gamma=1.5, alpha=0.8):
        """Create focal loss function for loading (for legacy models)."""
        def loss(y_true, y_pred):
            y_true = tf.cast(y_true, tf.float32)
            y_pred = tf.clip_by_value(y_pred, 1e-7, 1.0 - 1e-7)
            pt = tf.where(tf.equal(y_true, 1), y_pred, 1 - y_pred)
            alpha_t = tf.where(tf.equal(y_true, 1), alpha, 1 - alpha)
            return -tf.reduce_mean(alpha_t * tf.pow(1 - pt, gamma) * tf.math.log(pt))
        loss.__name__ = f'focal_loss_g{gamma}_a{alpha}'
        return loss
        
    def load(self) -> bool:
        """Load model and scaling artifacts."""
        try:
            # Load model
            if not os.path.exists(self.model_path):
                print(f"[ERR] Model not found: {self.model_path}")
                return False
            
            print(f"[LOAD] Loading multi-risk LSTM from {self.model_path}")
            
            # Provide custom objects for legacy focal loss (if model uses it)
            custom_objects = {
                'focal_loss_g1.5_a0.8': self._create_focal_loss(gamma=1.5, alpha=0.8),
                'focal_loss_g1.5_a0.7': self._create_focal_loss(gamma=1.5, alpha=0.7),
                'focal_loss_g1.0_a0.8': self._create_focal_loss(gamma=1.0, alpha=0.8),
                # Standard losses (always available in Keras)
                'binary_crossentropy': 'binary_crossentropy',
                'mse': 'mse',
            }
            
            try:
                # First try without custom objects (for standard models)
                self.model = tf.keras.models.load_model(self.model_path, safe_mode=False)
            except Exception:
                # Fall back to custom objects if needed
                self.model = tf.keras.models.load_model(
                    self.model_path, 
                    custom_objects=custom_objects,
                    safe_mode=False
                )
            
            # Load scaler and targets
            with open(os.path.join(self.multi_risk_dir, 'scaler.pkl'), 'rb') as fh:
                self.scaler = pickle.load(fh)
            
            with open(os.path.join(self.multi_risk_dir, 'y_reg_mean.pkl'), 'rb') as fh:
                self.y_reg_mean = pickle.load(fh)
            
            with open(os.path.join(self.multi_risk_dir, 'y_reg_std.pkl'), 'rb') as fh:
                self.y_reg_std = pickle.load(fh)
            
            with open(os.path.join(self.multi_risk_dir, 'feature_cols.pkl'), 'rb') as fh:
                self.feature_cols = pickle.load(fh)
            
            with open(os.path.join(self.multi_risk_dir, 'risk_thresholds.json'), 'r') as fh:
                self.metadata = json.load(fh)
            
            self.ready = True
            print("[OK] Multi-risk LSTM loaded and ready")
            return True
        except Exception as e:
            print(f"[ERR] Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def predict_sequence(self, X_seq: np.ndarray) -> dict:
        """
        Predict risks for a single 3D sequence [seq_len, n_features].
        
        Args:
            X_seq: numpy array of shape [seq_len, n_features]
            
        Returns:
            dict with regression predictions (next vitals) and classification
            probabilities (risk predictions)
        """
        if not self.ready:
            raise RuntimeError("Engine not ready. Call load() first.")
        
        if X_seq.ndim != 2:
            raise ValueError(f"Expected 2D sequence, got {X_seq.ndim}D")
        
        # Scale and batch
        X_scaled = self.scaler.transform(X_seq.reshape(-1, X_seq.shape[1])).reshape(1, *X_seq.shape).astype(np.float32)
        
        # Predict
        pred_dict = self.model.predict(X_scaled, verbose=0)
        
        # Deserialize predictions
        results = {}
        
        # Regression: inverse-scale next vitals
        for i, target in enumerate(REG_TARGETS):
            pred_scaled = float(pred_dict[target][0, 0])
            pred_unscaled = pred_scaled * self.y_reg_std[i] + self.y_reg_mean[i]
            results[target] = {
                "prediction": round(float(pred_unscaled), 2),
                "scaled_pred": round(float(pred_scaled), 4),
            }
        
        # Classification: risks and probabilities
        for i, target in enumerate(CLS_TARGETS):
            prob = float(pred_dict[target][0, 0])
            threshold = RISK_THRESHOLDS.get(target, 0.5)
            risk = int(prob > threshold)
            results[target] = {
                "probability": round(float(prob), 4),
                "risk": risk,
                "threshold": threshold,
            }
        
        return results


def main():
    """Test inference engine."""
    engine = MultiRiskInferenceEngine()
    if not engine.load():
        return
    
    print("\n[TEST] Multi-Risk Inference Engine Loaded")
    print(f"       Regression targets: {REG_TARGETS}")
    print(f"       Classification targets: {CLS_TARGETS}")
    print(f"       Features: {len(engine.feature_cols)}")
    print(f"       Metadata: {json.dumps(engine.metadata, indent=2, default=str)}")


if __name__ == '__main__':
    main()
