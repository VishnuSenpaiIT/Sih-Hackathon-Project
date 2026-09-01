"""
Pipeline Integration & Unit Tests
Smart Traffic Monitoring & Prediction System (SIH26222)
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.utils.data_processor import (
    TrafficDetectionEvent,
    normalize_detection_payload,
    categorize_density_level
)
from edge.traffic_analyzer import TrafficAnalyzer


from backend.models.database import init_db


@pytest.fixture
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """Verifies the health check endpoint returns 200 and valid schema."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Smart Traffic" in data["system"]


def test_density_categorization():
    """Verifies density tier mapping logic."""
    assert categorize_density_level(10.0) == "LOW"
    assert categorize_density_level(40.0) == "MODERATE"
    assert categorize_density_level(70.0) == "HIGH"
    assert categorize_density_level(90.0) == "CRITICAL"


def test_detection_event_validation():
    """Verifies detection event normalization against contract."""
    sample_payload = {
        "camera_id": "test_cam_01",
        "timestamp": "2026-09-01T10:00:00Z",
        "frame_id": 42,
        "vehicle_count": 5,
        "class_counts": {
            "car": 3,
            "bus": 1,
            "truck": 0,
            "bike": 1,
            "pedestrian": 2
        },
        "density": 45.5,
        "queue_length": 22.5,
        "detections": [
            {
                "track_id": None,
                "class": "car",
                "confidence": 0.92,
                "bbox": [100.0, 150.0, 300.0, 350.0]
            }
        ],
        "processing_time_ms": 35.2
    }

    normalized = normalize_detection_payload(sample_payload)
    assert normalized["camera_id"] == "test_cam_01"
    assert normalized["congestion_level"] == "MODERATE"
    assert normalized["vehicle_count"] == 5
    assert len(normalized["detections"]) == 1


def test_ingestion_and_query_flow(client):
    """Verifies end-to-end ingestion and querying."""
    payload = {
        "camera_id": "test_cam_01",
        "timestamp": "2026-09-01T10:05:00Z",
        "frame_id": 1,
        "vehicle_count": 8,
        "class_counts": {
            "car": 6,
            "bus": 1,
            "truck": 0,
            "bike": 1,
            "pedestrian": 0
        },
        "density": 58.0,
        "queue_length": 36.0,
        "detections": [],
        "processing_time_ms": 42.0
    }

    # Post detection event
    post_res = client.post("/api/detections", json=payload)
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "success"

    # Query detection history
    get_res = client.get("/api/detections?camera_id=test_cam_01")
    assert get_res.status_code == 200
    history = get_res.json()
    assert len(history) >= 1
    assert history[0]["camera_id"] == "test_cam_01"
    assert history[0]["vehicle_count"] == 8


def test_traffic_analyzer_synthetic_frame():
    """Tests the TrafficAnalyzer with a blank synthetic frame."""
    analyzer = TrafficAnalyzer()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    result = analyzer.analyze_frame(
        frame=dummy_frame,
        camera_id="test_cam",
        frame_id=1
    )

    assert result["camera_id"] == "test_cam"
    assert result["density"] >= 0.0
    assert result["vehicle_count"] >= 0
    assert "class_counts" in result
