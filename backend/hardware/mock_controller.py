"""
Mock Arduino Controller (backend/hardware/mock_controller.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

In-memory mock controller simulating Arduino hardware actuation:
- Simulates state changes in memory with a timestamped command log
- is_real() returns False
- mode returns "simulated" (or "offline" if explicitly disconnected)
- Responds to 'H' (Heartbeat) with state OK
- Non-blocking, instant response, always available for plug-and-play simulation
"""

import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from backend.hardware.controller_interface import HardwareController, VALID_COMMANDS


class MockArduinoController(HardwareController):
    """
    In-memory simulation of the Arduino traffic controller.
    Fulfills plug-and-play requirement when physical Arduino is not connected.
    """

    def __init__(self, max_history: int = 100):
        self._lock = threading.Lock()
        self.connected: bool = True
        self.mode: str = "simulated"
        self.port: Optional[str] = None
        self.last_command: Optional[str] = None
        self.last_updated: str = datetime.now(timezone.utc).isoformat()
        self.command_log: List[Dict[str, Any]] = []
        self.max_history: int = max_history

    def connect(self) -> bool:
        with self._lock:
            self.connected = True
            self.mode = "simulated"
            self.last_updated = datetime.now(timezone.utc).isoformat()
            return True

    def disconnect(self) -> None:
        with self._lock:
            self.connected = False
            self.mode = "offline"
            self.last_updated = datetime.now(timezone.utc).isoformat()

    def send_command(self, cmd: str) -> bool:
        cmd_clean = cmd.strip().upper()
        if not cmd_clean or cmd_clean not in VALID_COMMANDS:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.last_command = cmd_clean
            self.last_updated = now_iso

            # For heartbeat 'H', response is OK; for others, ACK
            resp = "OK" if cmd_clean == "H" else "ACK"
            log_entry = {
                "command": cmd_clean,
                "timestamp": now_iso,
                "response": resp
            }
            self.command_log.append(log_entry)
            if len(self.command_log) > self.max_history:
                self.command_log.pop(0)

        return True

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "connected": self.connected,
                "mode": self.mode,
                "last_command": self.last_command,
                "last_updated": self.last_updated,
                "port": self.port,
                "log_count": len(self.command_log),
                "recent_history": list(self.command_log[-10:])
            }

    def is_real(self) -> bool:
        return False
