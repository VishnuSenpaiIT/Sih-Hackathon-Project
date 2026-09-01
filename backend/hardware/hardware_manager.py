"""
Hardware Manager (backend/hardware/hardware_manager.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Singleton hardware coordinator:
- Starts by default with MockArduinoController (Plug-and-play simulation requirement)
- Runs background auto-detection loop every 5 seconds:
  * Scans for Arduino VID/PID signatures or ARDUINO_PORT env var
  * Performs handshake ('H' -> 'OK')
  * Live-swaps active controller to ArduinoController with zero downtime
  * Automatic fallback to MockArduinoController on disconnect/unplug without crashing
- process_traffic_event(density: float, is_anomaly: bool = False):
  * Computes 'A' if anomaly, else 'G' (<33), 'Y' (33-66), 'R' (>66)
  * Dispatches ONLY on state changes (on-change only, not per-frame)
- Exposes get_hardware_status() for REST API and WebSocket broadcasts
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List

try:
    import serial.tools.list_ports
except ImportError:
    pass

from backend.hardware.controller_interface import HardwareController
from backend.hardware.mock_controller import MockArduinoController
from backend.hardware.arduino_controller import ArduinoController
from backend.utils.data_processor import (
    map_density_to_hardware_command,
    resolve_hardware_command_transition,
    HARDWARE_CMD_ANOMALY,
    HARDWARE_CMD_CLEAR_ANOMALY,
)

logger = logging.getLogger("HardwareManager")

# Known USB-to-UART / Arduino Vendor IDs
KNOWN_ARDUINO_VIDS = {
    0x2341,  # Arduino SA
    0x2A03,  # Arduino SRL
    0x1A86,  # QinHeng Electronics (CH340/CH341)
    0x0403,  # FTDI
    0x10C4,  # Silicon Labs CP210x
}

# Substrings in port description indicating Arduino / compatible board
PORT_DESCRIPTION_KEYWORDS = ["arduino", "ch340", "usb-serial", "usb serial"]


class HardwareManager:
    """
    Singleton manager orchestrating traffic light hardware actuation and auto-detection.
    """

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(HardwareManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._running: bool = False

        # Default to plug-and-play simulation mock controller
        self.mock_controller = MockArduinoController()
        self.active_controller: HardwareController = self.mock_controller

        # Tracking state
        self.last_dispatched_command: Optional[str] = None
        self.last_density: Optional[float] = None
        self.is_anomaly: bool = False

        # Start auto-detection background thread
        self.start()

    def start(self):
        """Starts background auto-detection thread if not already running."""
        with self._lock:
            if self._running:
                return
            self._stop_event.clear()
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._auto_detect_loop,
                name="HardwareAutoDetectThread",
                daemon=True
            )
            self._worker_thread.start()
            logger.info("HardwareManager background auto-detection loop started.")

    def stop(self):
        """Stops background loop and disconnects controllers cleanly."""
        with self._lock:
            self._running = False
            self._stop_event.set()
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=2.0)
            self.active_controller.disconnect()
            logger.info("HardwareManager stopped.")

    def _discover_candidate_ports(self) -> List[str]:
        """Scans system serial ports for Arduino signatures or checks ARDUINO_PORT env."""
        candidates = []

        # 1. Check explicit environment override
        env_port = os.getenv("ARDUINO_PORT", "").strip()
        if env_port:
            candidates.append(env_port)

        # 2. Check system serial ports
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                # Check VID
                if p.vid is not None and p.vid in KNOWN_ARDUINO_VIDS:
                    if p.device not in candidates:
                        candidates.append(p.device)
                    continue

                # Check description
                desc = (p.description or "").lower()
                if any(kw in desc for kw in PORT_DESCRIPTION_KEYWORDS):
                    if p.device not in candidates:
                        candidates.append(p.device)
        except Exception as e:
            logger.debug(f"Port scanning error: {e}")

        return candidates

    def _auto_detect_loop(self):
        """Background thread executing periodic port discovery and health monitoring."""
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    is_currently_real = self.active_controller.is_real()
                    active_state = self.active_controller.get_state()

                if is_currently_real:
                    # Check if the real controller has dropped or disconnected
                    if not active_state.get("connected", False):
                        logger.warning("Active physical Arduino connection lost. Falling back to Mock controller.")
                        self._fallback_to_mock()
                    else:
                        # Quick sanity check: verify port still exists in system
                        try:
                            import serial.tools.list_ports
                            available_devices = {p.device for p in serial.tools.list_ports.comports()}
                            curr_port = active_state.get("port")
                            if curr_port and curr_port not in available_devices:
                                logger.warning(f"Arduino port {curr_port} unplugged. Falling back to Mock.")
                                self._fallback_to_mock()
                        except Exception:
                            pass
                else:
                    # Currently on Mock controller: check if an Arduino has been plugged in
                    candidates = self._discover_candidate_ports()
                    for cand_port in candidates:
                        logger.debug(f"Attempting probe on candidate Arduino port {cand_port}...")
                        cand_controller = ArduinoController(port=cand_port)
                        if cand_controller.connect():
                            logger.info(f"Physical Arduino detected on {cand_port}! Live-swapping controller...")
                            self._swap_to_real(cand_controller)
                            break

            except Exception as e:
                logger.debug(f"Error in hardware auto-detection loop: {e}")

            # Sleep 5 seconds between checks (interruptible)
            self._stop_event.wait(5.0)

    def _swap_to_real(self, real_controller: ArduinoController):
        """Zero-downtime swap from Mock to Physical controller."""
        with self._lock:
            old_controller = self.active_controller
            self.active_controller = real_controller
            old_controller.disconnect()

            # Resend last state so physical LEDs immediately match system state
            if self.last_dispatched_command:
                try:
                    self.active_controller.send_command(self.last_dispatched_command)
                except Exception as e:
                    logger.debug(f"Error synchronizing physical controller state: {e}")

    def _fallback_to_mock(self):
        """Zero-downtime fallback to Mock controller on disconnection."""
        with self._lock:
            if self.active_controller.is_real():
                try:
                    self.active_controller.disconnect()
                except Exception:
                    pass
            self.mock_controller.connect()
            self.active_controller = self.mock_controller

            # Resend last state to mock log
            if self.last_dispatched_command:
                self.mock_controller.send_command(self.last_dispatched_command)

    def process_traffic_event(self, density: float, is_anomaly: bool = False) -> Optional[str]:
        """
        Computes byte command: 'A' if anomaly, else 'G' (<33), 'Y' (33-66), 'R' (>66).
        Dispatches ONLY on state changes (on-change only, not per frame).
        Returns the dispatched command string if sent, or None if skipped (unchanged).
        """
        with self._lock:
            self.last_density = density
            self.is_anomaly = is_anomaly

            if is_anomaly:
                target_cmd = "A"
            else:
                if density < 33.0:
                    target_cmd = "G"
                elif density <= 66.0:
                    target_cmd = "Y"
                else:
                    target_cmd = "R"

            # On-change filter: Only dispatch if state differs from last sent
            if target_cmd == self.last_dispatched_command:
                return None

            # If transitioning out of anomaly override, clear override ('C') first
            if self.last_dispatched_command == "A" and target_cmd != "A":
                self.active_controller.send_command("C")

            # Dispatch target command
            success = self.active_controller.send_command(target_cmd)
            if success:
                self.last_dispatched_command = target_cmd
                return target_cmd

            return None

    def send_manual_command(self, cmd: str) -> bool:
        """Sends an explicit single-byte command, updating last dispatched."""
        with self._lock:
            success = self.active_controller.send_command(cmd)
            if success:
                self.last_dispatched_command = cmd.strip().upper()
            return success

    def get_hardware_status(self) -> Dict[str, Any]:
        """
        Returns full hardware status telemetry:
        - connected: bool
        - mode: "simulated" | "real" | "offline"
        - last_command: Optional[str]
        - last_updated: str (ISO 8601 timestamp)
        - port: Optional[str]
        - is_real: bool
        - last_density: Optional[float]
        - is_anomaly: bool
        - last_dispatched_command: Optional[str]
        - auto_detect_enabled: bool
        """
        with self._lock:
            state = dict(self.active_controller.get_state())
            state["is_real"] = self.active_controller.is_real()
            state["last_density"] = self.last_density
            state["is_anomaly"] = self.is_anomaly
            state["last_dispatched_command"] = self.last_dispatched_command
            state["auto_detect_enabled"] = self._running
            return state


# Singleton instance exported for application-wide use
hardware_manager = HardwareManager()
