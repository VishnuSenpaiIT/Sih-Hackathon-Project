"""
Hardware Signal Contract Tests (tests/test_hardware_signal_contract.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Verifies the exact shape, normalization boundaries, and extraction logic for:
1. Traffic density score (strictly normalized float 0.0 to 100.0).
2. Anomaly/accident override flag (is_anomaly: bool, default False).
3. Hardware command byte mapping per Section 3 & 11 of HARDWARE_INTEGRATION_SIH26222.md:
   - density < 33.0            -> 'G' (Low traffic density -> Green LED)
   - 33.0 <= density <= 66.0   -> 'Y' (Medium traffic density -> Yellow LED)
   - density > 66.0            -> 'R' (Heavy congestion -> Red LED)
   - is_anomaly == True        -> 'A' (Accident / collision override -> Flashing red + buzzer)
   - When anomaly clears       -> 'C' (Clear override, resume last traffic state)
"""

import pytest
import numpy as np
from pydantic import ValidationError

from backend.utils.data_processor import (
    TrafficDetectionEvent,
    normalize_detection_payload,
    map_density_to_hardware_command,
    resolve_hardware_command_transition,
    HARDWARE_CMD_GREEN,
    HARDWARE_CMD_YELLOW,
    HARDWARE_CMD_RED,
    HARDWARE_CMD_ANOMALY,
    HARDWARE_CMD_CLEAR_ANOMALY,
)
from edge.traffic_analyzer import TrafficAnalyzer, calculate_density as edge_calc_density
from backend.services.video_analyzer_service import calculate_density as service_calc_density


def test_density_bounds_and_normalization():
    """
    Verifies that density calculation strictly yields a normalized float between 0.0 and 100.0
    computed from weighted vehicle count load and bounding box occupancy ratio.
    """
    frame_area = 1280.0 * 720.0  # standard 720p frame

    # 1. Zero vehicles
    empty_counts = {"car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0}
    d_empty_edge = edge_calc_density(empty_counts, total_bbox_area=0.0, frame_area=frame_area)
    d_empty_svc = service_calc_density(empty_counts, total_bbox_area=0.0, frame_area=frame_area)
    assert d_empty_edge == 0.0
    assert d_empty_svc == 0.0
    assert isinstance(d_empty_edge, float)

    # 2. Extreme saturation (50 heavy vehicles filling entire frame)
    heavy_counts = {"car": 10, "bus": 20, "truck": 20, "bike": 0, "pedestrian": 0}
    d_sat_edge = edge_calc_density(heavy_counts, total_bbox_area=frame_area * 1.5, frame_area=frame_area)
    d_sat_svc = service_calc_density(heavy_counts, total_bbox_area=frame_area * 1.5, frame_area=frame_area)
    assert d_sat_edge == 100.0
    assert d_sat_svc == 100.0
    assert isinstance(d_sat_edge, float)

    # 3. Moderate realistic traffic
    moderate_counts = {"car": 8, "bus": 1, "truck": 1, "bike": 2, "pedestrian": 1}
    # 20% area coverage
    bbox_area = frame_area * 0.20
    d_mod = edge_calc_density(moderate_counts, total_bbox_area=bbox_area, frame_area=frame_area)
    assert 0.0 < d_mod < 100.0
    assert isinstance(d_mod, float)


def test_traffic_detection_event_is_anomaly_default():
    """
    Verifies that TrafficDetectionEvent schema explicitly supports an optional
    is_anomaly flag with default=False.
    """
    base_payload = {
        "camera_id": "cam_junction_01",
        "timestamp": "2026-09-01T12:00:00Z",
        "frame_id": 100,
        "vehicle_count": 6,
        "class_counts": {"car": 4, "bus": 1, "truck": 0, "bike": 1, "pedestrian": 0},
        "density": 42.5,
        "queue_length": 27.0,
        "detections": []
    }

    # When omitted, is_anomaly must default to False
    event = TrafficDetectionEvent(**base_payload)
    assert event.is_anomaly is False
    assert isinstance(event.density, float)
    assert 0.0 <= event.density <= 100.0

    # When provided explicitly as True
    payload_with_anomaly = dict(base_payload)
    payload_with_anomaly["is_anomaly"] = True
    event_anomaly = TrafficDetectionEvent(**payload_with_anomaly)
    assert event_anomaly.is_anomaly is True


def test_density_schema_validation():
    """Verifies that Pydantic enforces the 0.0 to 100.0 boundary constraint."""
    valid_payload = {
        "camera_id": "cam_01",
        "timestamp": "2026-09-01T12:00:00Z",
        "frame_id": 1,
        "vehicle_count": 0,
        "class_counts": {"car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0},
        "density": 100.0,
        "is_anomaly": False
    }
    # Exactly 100.0 and 0.0 must be accepted
    ev_100 = TrafficDetectionEvent(**valid_payload)
    assert ev_100.density == 100.0

    valid_payload["density"] = 0.0
    ev_0 = TrafficDetectionEvent(**valid_payload)
    assert ev_0.density == 0.0

    # Negative density must fail validation
    with pytest.raises(ValidationError):
        invalid_negative = dict(valid_payload, density=-0.1)
        TrafficDetectionEvent(**invalid_negative)

    # Over 100.0 must fail validation
    with pytest.raises(ValidationError):
        invalid_over = dict(valid_payload, density=100.1)
        TrafficDetectionEvent(**invalid_over)


def test_hardware_command_threshold_mapping():
    """
    Verifies strict threshold mapping to single-byte hardware commands:
      - density < 33.0          -> 'G'
      - 33.0 <= density <= 66.0 -> 'Y'
      - density > 66.0          -> 'R'
      - is_anomaly == True      -> 'A' (override)
    """
    # Low density -> 'G'
    assert map_density_to_hardware_command(0.0) == HARDWARE_CMD_GREEN
    assert map_density_to_hardware_command(15.2) == HARDWARE_CMD_GREEN
    assert map_density_to_hardware_command(32.99) == HARDWARE_CMD_GREEN

    # Medium density -> 'Y'
    assert map_density_to_hardware_command(33.0) == HARDWARE_CMD_YELLOW
    assert map_density_to_hardware_command(50.0) == HARDWARE_CMD_YELLOW
    assert map_density_to_hardware_command(66.0) == HARDWARE_CMD_YELLOW

    # Heavy density -> 'R'
    assert map_density_to_hardware_command(66.01) == HARDWARE_CMD_RED
    assert map_density_to_hardware_command(85.0) == HARDWARE_CMD_RED
    assert map_density_to_hardware_command(100.0) == HARDWARE_CMD_RED

    # Anomaly Override -> 'A' regardless of density value
    assert map_density_to_hardware_command(10.0, is_anomaly=True) == HARDWARE_CMD_ANOMALY
    assert map_density_to_hardware_command(50.0, is_anomaly=True) == HARDWARE_CMD_ANOMALY
    assert map_density_to_hardware_command(95.0, is_anomaly=True) == HARDWARE_CMD_ANOMALY


def test_hardware_command_transition_clearing():
    """
    Verifies transition logic when anomaly clears:
      When anomaly clears (prev_anomaly=True, is_anomaly=False) -> ('C', normal_cmd)
      (Clear override, resume last traffic state)
    """
    # Steady normal state
    assert resolve_hardware_command_transition(20.0, is_anomaly=False, prev_anomaly=False) == ('G',)
    assert resolve_hardware_command_transition(45.0, is_anomaly=False, prev_anomaly=False) == ('Y',)
    assert resolve_hardware_command_transition(75.0, is_anomaly=False, prev_anomaly=False) == ('R',)

    # Entering anomaly override
    assert resolve_hardware_command_transition(20.0, is_anomaly=True, prev_anomaly=False) == ('A',)
    assert resolve_hardware_command_transition(75.0, is_anomaly=True, prev_anomaly=True) == ('A',)

    # Anomaly cleared: emits ('C', resume_state)
    cleared_low = resolve_hardware_command_transition(20.0, is_anomaly=False, prev_anomaly=True)
    assert cleared_low == ('C', 'G')

    cleared_med = resolve_hardware_command_transition(55.0, is_anomaly=False, prev_anomaly=True)
    assert cleared_med == ('C', 'Y')

    cleared_high = resolve_hardware_command_transition(80.0, is_anomaly=False, prev_anomaly=True)
    assert cleared_high == ('C', 'R')


def test_normalized_payload_contains_hardware_signals():
    """
    Verifies that normalize_detection_payload enriches data with both is_anomaly
    and the corresponding hardware_command byte.
    """
    raw_event = {
        "camera_id": "cam_live_01",
        "timestamp": "2026-09-01T12:30:00Z",
        "frame_id": 420,
        "vehicle_count": 12,
        "class_counts": {"car": 9, "bus": 2, "truck": 1, "bike": 0, "pedestrian": 0},
        "density": 72.4,
        "queue_length": 54.0,
        "detections": [],
        "processing_time_ms": 38.5,
        "is_anomaly": False
    }

    normalized = normalize_detection_payload(raw_event)
    assert normalized["is_anomaly"] is False
    assert normalized["density"] == 72.4
    assert normalized["hardware_command"] == HARDWARE_CMD_RED
    assert normalized["congestion_level"] == "HIGH"

    # Test with anomaly flagged
    raw_event["is_anomaly"] = True
    normalized_anomaly = normalize_detection_payload(raw_event)
    assert normalized_anomaly["is_anomaly"] is True
    assert normalized_anomaly["hardware_command"] == HARDWARE_CMD_ANOMALY


def test_edge_traffic_analyzer_emits_is_anomaly():
    """Verifies TrafficAnalyzer.analyze_frame returns is_anomaly cleanly."""
    analyzer = TrafficAnalyzer()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame without anomaly flag
    res_normal = analyzer.analyze_frame(dummy_frame, camera_id="cam_test", frame_id=1)
    assert res_normal["is_anomaly"] is False
    assert 0.0 <= res_normal["density"] <= 100.0

    # Frame with anomaly flag passed
    res_anomaly = analyzer.analyze_frame(dummy_frame, camera_id="cam_test", frame_id=2, is_anomaly=True)
    assert res_anomaly["is_anomaly"] is True
