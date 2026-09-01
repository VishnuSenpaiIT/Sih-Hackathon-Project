"""
Comprehensive Hardware Bridge Automated Tests (tests/test_hardware_bridge.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Tests:
1. MockArduinoController lifecycle, commands, and memory log
2. ArduinoController interface contract, validation, and handshake
3. HardwareManager singleton, on-change dispatch filter, auto-detect loop, live-swap, and fallback
4. FastAPI REST API endpoint GET /api/hardware/status
5. Detection ingestion hardware actuation hook
6. WebSocket broadcast hardware_state attachment
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.hardware.controller_interface import HardwareController, VALID_COMMANDS
from backend.hardware.mock_controller import MockArduinoController
from backend.hardware.arduino_controller import ArduinoController
from backend.hardware.hardware_manager import HardwareManager, hardware_manager
from backend.main import app
from backend.api.websocket import ws_manager


# ─────────────────────────────────────────────────────────────────────────────
# 1. Controller Interface & Mock Controller Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_valid_commands_set():
    assert VALID_COMMANDS == {"G", "Y", "R", "A", "C", "H"}


def test_mock_controller_lifecycle():
    mock_ctrl = MockArduinoController(max_history=5)
    assert mock_ctrl.is_real() is False
    assert mock_ctrl.connected is True
    assert mock_ctrl.mode == "simulated"

    # Test get_state format
    state = mock_ctrl.get_state()
    assert state["connected"] is True
    assert state["mode"] == "simulated"
    assert state["port"] is None
    assert "last_command" in state
    assert "last_updated" in state

    # Test command sending
    assert mock_ctrl.send_command("G") is True
    assert mock_ctrl.last_command == "G"

    # Test Heartbeat 'H' responds with OK in log
    assert mock_ctrl.send_command("H") is True
    state = mock_ctrl.get_state()
    assert state["last_command"] == "H"
    assert len(state["recent_history"]) == 2
    assert state["recent_history"][-1]["command"] == "H"
    assert state["recent_history"][-1]["response"] == "OK"

    # Test invalid command rejected
    assert mock_ctrl.send_command("INVALID") is False
    assert mock_ctrl.send_command("Z") is False

    # Test disconnect and reconnect
    mock_ctrl.disconnect()
    assert mock_ctrl.connected is False
    assert mock_ctrl.mode == "offline"

    mock_ctrl.connect()
    assert mock_ctrl.connected is True
    assert mock_ctrl.mode == "simulated"


def test_mock_controller_history_bounding():
    mock_ctrl = MockArduinoController(max_history=3)
    for cmd in ["G", "Y", "R", "A"]:
        mock_ctrl.send_command(cmd)
    assert len(mock_ctrl.command_log) == 3
    assert [entry["command"] for entry in mock_ctrl.command_log] == ["Y", "R", "A"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Arduino Controller Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_arduino_controller_contract():
    ctrl = ArduinoController(port="COM99")
    assert ctrl.is_real() is True
    assert ctrl.connected is False
    assert ctrl.mode == "offline"
    assert ctrl.port == "COM99"

    state = ctrl.get_state()
    assert state["connected"] is False
    assert state["mode"] == "offline"
    assert state["port"] == "COM99"

    # Cannot send command while offline
    assert ctrl.send_command("G") is False

    # Invalid command rejected
    assert ctrl.send_command("XYZ") is False

    # Disconnect when not connected does not throw
    ctrl.disconnect()
    assert ctrl.connected is False


@patch("serial.Serial")
def test_arduino_controller_handshake_success(mock_serial_cls):
    """Verifies that connect() properly verifies handshake 'H' -> 'OK'."""
    mock_instance = MagicMock()
    mock_instance.is_open = True
    mock_instance.readline.return_value = b"OK\r\n"
    mock_serial_cls.return_value = mock_instance

    with patch("time.sleep", return_value=None):
        ctrl = ArduinoController(port="COM5")
        success = ctrl.connect()

    assert success is True
    assert ctrl.connected is True
    assert ctrl.mode == "real"
    assert ctrl.last_command == "H"

    # Send valid command
    with patch("time.sleep", return_value=None):
        assert ctrl.send_command("G") is True
        mock_instance.write.assert_called_with(b"G\n")
        assert ctrl.last_command == "G"

    # Clean disconnect
    ctrl.disconnect()
    assert ctrl.connected is False
    assert ctrl.mode == "offline"
    mock_instance.close.assert_called()


@patch("serial.Serial")
def test_arduino_controller_handshake_timeout(mock_serial_cls):
    """Verifies that connect() handles missing 'OK' and sets offline."""
    mock_instance = MagicMock()
    mock_instance.is_open = True
    mock_instance.readline.return_value = b"UNKNOWN\r\n"
    mock_serial_cls.return_value = mock_instance

    with patch("time.sleep", return_value=None):
        ctrl = ArduinoController(port="COM5", read_timeout=0.1)
        success = ctrl.connect()

    assert success is False
    assert ctrl.connected is False
    assert ctrl.mode == "offline"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Hardware Manager Tests (On-Change, State Transitions, Auto-Detect)
# ─────────────────────────────────────────────────────────────────────────────

def test_hardware_manager_default_mode():
    mgr = HardwareManager()
    status = mgr.get_hardware_status()
    assert status["connected"] is True
    assert status["mode"] == "simulated"
    assert status["is_real"] is False
    assert status["auto_detect_enabled"] is True


def test_hardware_manager_on_change_filtering():
    """Verifies commands are ONLY sent on state change, never spammed per-frame."""
    mgr = HardwareManager()
    mgr.last_dispatched_command = None
    mgr.mock_controller.command_log.clear()

    # 1. First event: density 15.0 (< 33) -> 'G'
    cmd1 = mgr.process_traffic_event(density=15.0, is_anomaly=False)
    assert cmd1 == "G"
    assert mgr.last_dispatched_command == "G"
    assert len(mgr.mock_controller.command_log) == 1

    # 2. Next frame: same tier (density 20.0 -> still 'G') -> SKIPPED (None)
    cmd2 = mgr.process_traffic_event(density=20.0, is_anomaly=False)
    assert cmd2 is None
    assert len(mgr.mock_controller.command_log) == 1  # No duplicate send

    # 3. State transition: density 45.0 (33-66) -> 'Y'
    cmd3 = mgr.process_traffic_event(density=45.0, is_anomaly=False)
    assert cmd3 == "Y"
    assert mgr.last_dispatched_command == "Y"
    assert len(mgr.mock_controller.command_log) == 2

    # 4. State transition: density 85.0 (> 66) -> 'R'
    cmd4 = mgr.process_traffic_event(density=85.0, is_anomaly=False)
    assert cmd4 == "R"
    assert mgr.last_dispatched_command == "R"
    assert len(mgr.mock_controller.command_log) == 3

    # 5. Anomaly override: is_anomaly=True -> 'A'
    cmd5 = mgr.process_traffic_event(density=85.0, is_anomaly=True)
    assert cmd5 == "A"
    assert mgr.last_dispatched_command == "A"
    assert len(mgr.mock_controller.command_log) == 4

    # 6. Duplicate anomaly frame -> SKIPPED
    cmd6 = mgr.process_traffic_event(density=90.0, is_anomaly=True)
    assert cmd6 is None
    assert len(mgr.mock_controller.command_log) == 4

    # 7. Anomaly clears: is_anomaly=False -> Sends 'C' then 'G' (clears override)
    cmd7 = mgr.process_traffic_event(density=10.0, is_anomaly=False)
    assert cmd7 == "G"
    # Verify 'C' was sent before 'G'
    recent_cmds = [entry["command"] for entry in mgr.mock_controller.command_log[-2:]]
    assert recent_cmds == ["C", "G"]


def test_hardware_manager_live_swap_and_fallback():
    mgr = HardwareManager()
    initial_ctrl = mgr.active_controller
    assert initial_ctrl.is_real() is False

    # Mock a real Arduino controller
    mock_real = MagicMock(spec=ArduinoController)
    mock_real.is_real.return_value = True
    mock_real.connected = True
    mock_real.send_command.return_value = True
    mock_real.get_state.return_value = {
        "connected": True,
        "mode": "real",
        "last_command": "G",
        "last_updated": "2026-09-01T12:00:00Z",
        "port": "COM3"
    }

    # Test live swap to real
    mgr._swap_to_real(mock_real)
    assert mgr.active_controller.is_real() is True
    status = mgr.get_hardware_status()
    assert status["is_real"] is True
    assert status["mode"] == "real"
    assert status["port"] == "COM3"

    # Test automatic fallback to mock
    mgr._fallback_to_mock()
    assert mgr.active_controller.is_real() is False
    status = mgr.get_hardware_status()
    assert status["is_real"] is False
    assert status["mode"] == "simulated"


# ─────────────────────────────────────────────────────────────────────────────
# 4. REST API Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_api_hardware_status_endpoint():
    client = TestClient(app)
    response = client.get("/api/hardware/status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert "mode" in data
    assert data["mode"] in ["simulated", "real", "offline"]
    assert "last_command" in data
    assert "last_updated" in data
    assert "port" in data
    assert "is_real" in data
    assert "auto_detect_enabled" in data


def test_api_detections_actuates_hardware():
    client = TestClient(app)
    hardware_manager.last_dispatched_command = None

    payload = {
        "camera_id": "cam_test_hw",
        "timestamp": "2026-09-01T12:00:00Z",
        "frame_id": 1,
        "vehicle_count": 2,
        "class_counts": {"car": 2, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0},
        "density": 18.0,
        "queue_length": 5.0,
        "detections": []
    }

    resp = client.post("/api/detections", json=payload)
    assert resp.status_code == 200
    assert hardware_manager.last_dispatched_command == "G"


# ─────────────────────────────────────────────────────────────────────────────
# 5. WebSocket Broadcast Hardware State Attachment
# ─────────────────────────────────────────────────────────────────────────────

def test_websocket_broadcast_hardware_state():
    import asyncio
    from unittest.mock import AsyncMock

    async def _test():
        mock_ws = MagicMock()
        mock_ws.send_text = AsyncMock()

        ws_manager.active_connections["all"] = [mock_ws]

        msg = {
            "type": "traffic_update",
            "data": {
                "camera_id": "cam_01",
                "density": 45.0
            }
        }

        # Run broadcast
        await ws_manager.broadcast(msg)

        assert mock_ws.send_text.called
        sent_payload = mock_ws.send_text.call_args[0][0]
        import json
        parsed = json.loads(sent_payload)

        assert "hardware_state" in parsed
        assert parsed["hardware_state"]["connected"] is True
        assert parsed["hardware_state"]["mode"] in ["simulated", "real", "offline"]
        assert "hardware_state" in parsed["data"]

        # Cleanup
        ws_manager.active_connections["all"] = []

    asyncio.run(_test())

