"""
Traffic Prediction Service (backend/models/traffic_prediction.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Provides short-term traffic density and vehicle count forecasts using:
 - Trained LSTM/GRU weights when available (loads from disk)
 - Diurnal harmonic + exponential smoothing heuristic as graceful fallback
"""

import math
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("TrafficPredictor")

# Minimum observations required before ML or heuristic prediction is meaningful
MIN_HISTORY_POINTS = 3
# Path where trained model weights are persisted by the training notebook
MODEL_WEIGHTS_PATH = os.getenv("PREDICTION_MODEL_PATH", "notebooks/traffic_lstm_weights.npz")


class SimpleGRUCell:
    """
    Lightweight NumPy-based GRU cell.
    Avoids requiring PyTorch/TF at runtime — loads pretrained weights from .npz.
    Falls back to heuristic if weights file doesn't exist yet.
    """

    def __init__(self, input_size: int, hidden_size: int):
        self.input_size = input_size
        self.hidden_size = hidden_size
        # Initialize weights to identity-like values (safe untrained baseline)
        self.Wz = np.random.randn(hidden_size, input_size + hidden_size).astype(np.float32) * 0.01
        self.Wr = np.random.randn(hidden_size, input_size + hidden_size).astype(np.float32) * 0.01
        self.Wh = np.random.randn(hidden_size, input_size + hidden_size).astype(np.float32) * 0.01
        self.bz = np.zeros(hidden_size, dtype=np.float32)
        self.br = np.zeros(hidden_size, dtype=np.float32)
        self.bh = np.zeros(hidden_size, dtype=np.float32)
        self.W_out = np.random.randn(1, hidden_size).astype(np.float32) * 0.01
        self.b_out = np.zeros(1, dtype=np.float32)
        self._trained = False

    def load_weights(self, path: str) -> bool:
        """Loads pretrained GRU weights from .npz file."""
        try:
            data = np.load(path)
            self.Wz = data["Wz"]
            self.Wr = data["Wr"]
            self.Wh = data["Wh"]
            self.bz = data["bz"]
            self.br = data["br"]
            self.bh = data["bh"]
            self.W_out = data["W_out"]
            self.b_out = data["b_out"]
            self._trained = True
            logger.info(f"GRU weights loaded from {path}")
            return True
        except Exception as e:
            logger.info(f"GRU weights not available ({e}). Using heuristic mode.")
            return False

    def forward(self, X: np.ndarray) -> float:
        """
        Runs GRU forward pass over sequence X [seq_len, input_size].
        Returns scalar density prediction.
        """
        h = np.zeros(self.hidden_size, dtype=np.float32)
        for t in range(X.shape[0]):
            x = X[t]
            xh = np.concatenate([x, h])
            z = self._sigmoid(self.Wz @ xh + self.bz)
            r = self._sigmoid(self.Wr @ xh + self.br)
            xrh = np.concatenate([x, r * h])
            h_cand = np.tanh(self.Wh @ xrh + self.bh)
            h = (1 - z) * h + z * h_cand
        out = float((self.W_out @ h + self.b_out)[0])
        return out

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def _diurnal_correction(hour_of_day: float) -> float:
    """
    Returns a multiplicative diurnal factor based on typical urban traffic patterns.
    Peak at 08:00 and 18:00, trough at 03:00.
    """
    morning_peak = math.exp(-0.5 * ((hour_of_day - 8.0) / 2.0) ** 2)
    evening_peak = math.exp(-0.5 * ((hour_of_day - 18.0) / 2.0) ** 2)
    return 0.4 + 0.6 * max(morning_peak, evening_peak)


class TrafficPredictor:
    """
    Traffic forecasting engine supporting both ML-based GRU inference
    and a resilient diurnal heuristic fallback.
    """

    HIDDEN_SIZE = 32
    INPUT_SIZE = 3   # [density, vehicle_count, hour_sin_cos combined]
    SEQ_LEN = 12     # 12 observations at 5-min intervals = 1 hour of context

    def __init__(self):
        self.gru = SimpleGRUCell(input_size=self.INPUT_SIZE, hidden_size=self.HIDDEN_SIZE)
        self._try_load_weights()

    def _try_load_weights(self):
        if os.path.exists(MODEL_WEIGHTS_PATH):
            self.gru.load_weights(MODEL_WEIGHTS_PATH)

    def _build_sequence(self, history: List[Any]) -> np.ndarray:
        """
        Converts ORM observation rows into a normalized GRU input sequence.
        Pads with mean values if fewer than SEQ_LEN rows are available.
        """
        rows = list(reversed(history[-self.SEQ_LEN:]))
        mean_density = np.mean([r.density for r in rows]) if rows else 45.0
        mean_count = np.mean([r.vehicle_count for r in rows]) if rows else 15.0

        seq = []
        for row in rows:
            ts = row.timestamp if hasattr(row.timestamp, "hour") else datetime.now(timezone.utc)
            hour = ts.hour + ts.minute / 60.0
            hour_sin = math.sin(2 * math.pi * hour / 24.0)
            density_norm = row.density / 100.0
            count_norm = min(1.0, row.vehicle_count / 80.0)
            seq.append([density_norm, count_norm, hour_sin])

        # Pad if shorter than SEQ_LEN
        while len(seq) < self.SEQ_LEN:
            seq.insert(0, [mean_density / 100.0, min(1.0, mean_count / 80.0), 0.0])

        return np.array(seq, dtype=np.float32)

    def predict_horizon(
        self,
        camera_id: str,
        history: List[Any],
        horizon_hours: int = 6
    ) -> Dict[str, Any]:
        """
        Generates a multi-step traffic forecast for the specified horizon.
        Returns forecast dict conforming to the prediction response schema.
        """
        now = datetime.now(timezone.utc)
        base_density = history[0].density if history else 45.0
        base_count = history[0].vehicle_count if history else 15.0

        model_used = "heuristic_diurnal"

        if self.gru._trained and len(history) >= MIN_HISTORY_POINTS:
            try:
                X = self._build_sequence(history)
                gru_delta = self.gru.forward(X)  # Raw GRU output is a density delta
                model_used = "gru_pretrained"
            except Exception as e:
                logger.warning(f"GRU inference failed: {e}. Falling back to heuristic.")
                gru_delta = 0.0
        else:
            gru_delta = 0.0

        forecast = []
        for h in range(1, horizon_hours + 1):
            future_ts = now + timedelta(hours=h)
            future_hour = future_ts.hour + future_ts.minute / 60.0
            diurnal_scale = _diurnal_correction(future_hour)

            if model_used == "gru_pretrained":
                pred_density = round(min(100.0, max(5.0, base_density + gru_delta * h * 0.5)), 1)
            else:
                # Heuristic: trend from base smoothed with diurnal
                current_hour = now.hour + now.minute / 60.0
                current_scale = max(0.1, _diurnal_correction(current_hour))
                pred_density = round(min(100.0, max(5.0, base_density * (diurnal_scale / current_scale))), 1)

            pred_count = int(pred_density * 0.45)
            confidence_margin = round(5.0 + h * 2.0, 1)  # Wider interval for further horizons

            forecast.append({
                "hour_offset": h,
                "timestamp": future_ts.isoformat(),
                "predicted_density": pred_density,
                "predicted_vehicles": pred_count,
                "confidence_lower": round(max(0.0, pred_density - confidence_margin), 1),
                "confidence_upper": round(min(100.0, pred_density + confidence_margin), 1)
            })

        # Congestion summary
        peak = max(forecast, key=lambda x: x["predicted_density"])

        return {
            "camera_id": camera_id,
            "horizon_hours": horizon_hours,
            "generated_at": now.isoformat(),
            "model_used": model_used,
            "status": "active",
            "peak_hour_offset": peak["hour_offset"],
            "peak_predicted_density": peak["predicted_density"],
            "forecast": forecast
        }


# Module-level singleton — imported lazily by routes.py
traffic_predictor = TrafficPredictor()
