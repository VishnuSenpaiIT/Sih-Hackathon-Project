"""
Unit and Integration Tests for Phase 2 AI/ML Deliverables
Smart Traffic Monitoring & Prediction System (SIH26222)

Tests:
1. Multi-object tracking (persistent track_id across sequential frames, latency < 100ms)
2. TrafficPredictor (LSTM model forecasting, fallback heuristic, confidence intervals)
3. API /predictions integration
"""

import time
import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.database import init_db
from edge.traffic_analyzer import TrafficAnalyzer, calculate_iou, RobustIoUTracker
from backend.models.traffic_prediction import TrafficPredictor, traffic_predictor


@pytest.fixture
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_iou_calculation():
    """Verifies IoU bounding box overlap mathematics."""
    boxA = [100.0, 100.0, 200.0, 200.0]
    boxB = [150.0, 100.0, 250.0, 200.0]  # Half overlap horizontally
    iou = calculate_iou(boxA, boxB)
    assert 0.30 <= iou <= 0.36

    # Non-overlapping
    boxC = [300.0, 300.0, 400.0, 400.0]
    assert calculate_iou(boxA, boxC) == 0.0

    # Identical
    assert calculate_iou(boxA, boxA) == 1.0


def test_multiobject_tracking_persistence():
    """
    Verifies that moving vehicles maintain persistent track_id integers across frames.
    """
    analyzer = TrafficAnalyzer()
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Frame 1: Two vehicles appear
    dets_f1 = [
        {"class": "car", "bbox": [100.0, 200.0, 160.0, 260.0], "confidence": 0.92},
        {"class": "bike", "bbox": [400.0, 300.0, 430.0, 340.0], "confidence": 0.88}
    ]
    res1 = analyzer.analyze_frame(dummy_frame, "cam_01", frame_id=1, custom_detections=dets_f1)
    tracks_f1 = {d["class"]: d["track_id"] for d in res1["detections"]}
    car_id_f1 = tracks_f1["car"]
    bike_id_f1 = tracks_f1["bike"]

    assert car_id_f1 is not None and isinstance(car_id_f1, int)
    assert bike_id_f1 is not None and isinstance(bike_id_f1, int)
    assert car_id_f1 != bike_id_f1

    # Frame 2: Vehicles move slightly (e.g. +10 pixels x, +5 pixels y)
    dets_f2 = [
        {"class": "car", "bbox": [110.0, 205.0, 170.0, 265.0], "confidence": 0.94},
        {"class": "bike", "bbox": [408.0, 304.0, 438.0, 344.0], "confidence": 0.89}
    ]
    res2 = analyzer.analyze_frame(dummy_frame, "cam_01", frame_id=2, custom_detections=dets_f2)
    tracks_f2 = {d["class"]: d["track_id"] for d in res2["detections"]}

    # Persistent track IDs must match Frame 1
    assert tracks_f2["car"] == car_id_f1, f"Expected car track_id {car_id_f1}, got {tracks_f2['car']}"
    assert tracks_f2["bike"] == bike_id_f1, f"Expected bike track_id {bike_id_f1}, got {tracks_f2['bike']}"

    # Frame 3: Vehicles continue moving, and a new truck enters
    dets_f3 = [
        {"class": "car", "bbox": [120.0, 210.0, 180.0, 270.0], "confidence": 0.95},
        {"class": "bike", "bbox": [416.0, 308.0, 446.0, 348.0], "confidence": 0.90},
        {"class": "truck", "bbox": [600.0, 150.0, 750.0, 280.0], "confidence": 0.85}
    ]
    res3 = analyzer.analyze_frame(dummy_frame, "cam_01", frame_id=3, custom_detections=dets_f3)
    tracks_f3 = {d["class"]: d["track_id"] for d in res3["detections"]}

    assert tracks_f3["car"] == car_id_f1
    assert tracks_f3["bike"] == bike_id_f1
    # Truck must be assigned a new unique ID
    assert tracks_f3["truck"] not in (car_id_f1, bike_id_f1)


def test_tracking_latency_under_100ms():
    """
    Verifies that per-frame analyzer processing latency stays well under 100ms.
    """
    analyzer = TrafficAnalyzer()
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    latencies = []
    for f_idx in range(1, 21):
        # 10 objects per frame with random motions
        dets = [
            {
                "class": "car" if i % 2 == 0 else "bus",
                "bbox": [50.0 + i * 60 + f_idx * 2, 100.0 + i * 20, 100.0 + i * 60 + f_idx * 2, 160.0 + i * 20],
                "confidence": 0.9
            }
            for i in range(10)
        ]
        start = time.time()
        res = analyzer.analyze_frame(dummy_frame, "cam_bench", frame_id=f_idx, custom_detections=dets)
        latency = (time.time() - start) * 1000.0
        latencies.append(latency)

    avg_latency = np.mean(latencies)
    max_latency = np.max(latencies)
    print(f"Tracking Benchmark: Avg = {avg_latency:.2f}ms, Max = {max_latency:.2f}ms")
    assert avg_latency < 100.0, f"Average latency {avg_latency:.2f}ms exceeded 100ms limit"
    assert max_latency < 150.0


def test_tracker_reset():
    """Verifies that reset_tracker() resets internal track sequence."""
    analyzer = TrafficAnalyzer()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    dets = [{"class": "car", "bbox": [50.0, 50.0, 100.0, 100.0], "confidence": 0.9}]
    res = analyzer.analyze_frame(dummy_frame, "cam_01", frame_id=1, custom_detections=dets)
    first_id = res["detections"][0]["track_id"]
    assert first_id == 1

    analyzer.reset_tracker()
    res_after = analyzer.analyze_frame(dummy_frame, "cam_01", frame_id=1, custom_detections=dets)
    assert res_after["detections"][0]["track_id"] == 1


def test_traffic_predictor_fallback():
    """
    Verifies graceful fallback mode when history is empty or contains insufficient samples.
    """
    predictor = TrafficPredictor()
    res = predictor.predict_horizon(camera_id="cam_sparse", history=[], horizon_hours=6)

    assert res["status"] == "fallback"
    assert res["camera_id"] == "cam_sparse"
    assert res["horizon_hours"] == 6
    assert len(res["forecast"]) == 6

    for step in res["forecast"]:
        assert 1 <= step["hour_offset"] <= 6
        assert 0.0 <= step["predicted_density"] <= 100.0
        assert step["predicted_vehicles"] >= 0
        assert step["confidence_lower"] <= step["predicted_density"] <= step["confidence_upper"]


def test_traffic_predictor_lstm_model():
    """
    Verifies LSTM sequential model prediction when sufficient history is provided.
    """
    predictor = TrafficPredictor()
    # 12 historical observation samples (simulating hourly updates)
    history = [
        {
            "timestamp": f"2026-09-01T{h:02d}:00:00Z",
            "density": float(40.0 + (h * 2.5)),
            "vehicle_count": int(15 + h)
        }
        for h in range(8, 20)
    ]

    start = time.time()
    res = predictor.predict_horizon(camera_id="cam_active", history=history, horizon_hours=6)
    inference_ms = (time.time() - start) * 1000.0

    print(f"Prediction Inference Latency: {inference_ms:.2f}ms")
    assert inference_ms < 50.0  # Must be fast
    assert res["status"] == "model"
    assert res["camera_id"] == "cam_active"
    assert len(res["forecast"]) == 6

    for step in res["forecast"]:
        assert 0.0 <= step["predicted_density"] <= 100.0
        assert step["predicted_vehicles"] >= 1
        assert step["confidence_lower"] <= step["predicted_density"] <= step["confidence_upper"]


def test_predictions_api_route(client):
    """
    Verifies the FastAPI `/api/predictions/{camera_id}` endpoint integration.
    """
    response = client.get("/api/predictions/cam_route_test?horizon_hours=6")
    assert response.status_code == 200
    data = response.json()
    assert "camera_id" in data
    assert "horizon_hours" in data
    assert data["horizon_hours"] == 6
    assert "forecast" in data
    assert len(data["forecast"]) == 6
    assert data["forecast"][0]["predicted_density"] >= 0.0
