"""
Arduino Controller (backend/hardware/arduino_controller.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Serial bridge to Arduino Uno via PySerial:
- Auto-connects to specified or discovered COM port at 9600 baud
- Short write timeout (0.2s), read timeout (0.5s)
- send_command(cmd: str) sends single-byte ASCII + newline
- Handshake verification: sends 'H', waits up to 0.5s for 'OK' response
- is_real() returns True
- mode: 'real' (or 'offline' if disconnected or error)
- Clean disconnect and resilient exception handling
"""

import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

from backend.hardware.controller_interface import HardwareController, VALID_COMMANDS

logger = logging.getLogger("ArduinoController")


class ArduinoController(HardwareController):
    """
    Physical Arduino controller interfacing over USB serial.
    Implements single-byte ASCII protocol with handshake verification.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        write_timeout: float = 0.5,
        read_timeout: float = 1.5
    ):
        self.port: str = port
        self.baudrate: int = baudrate
        self.write_timeout: float = write_timeout
        self.read_timeout: float = read_timeout

        self._lock = threading.Lock()
        self._serial: Optional[Any] = None
        self.connected: bool = False
        self.mode: str = "offline"
        self.last_command: Optional[str] = None
        self.last_updated: str = datetime.now(timezone.utc).isoformat()
        self.last_error: Optional[str] = None

    def connect(self) -> bool:
        """
        Connects to the specified COM port, resets buffers,
        and performs handshake ('H' -> 'OK').
        """
        if serial is None:
            self.last_error = "pyserial not installed"
            logger.error(self.last_error)
            self.connected = False
            self.mode = "offline"
            return False

        with self._lock:
            # Clean up any existing connection
            if self._serial is not None:
                try:
                    if self._serial.is_open:
                        self._serial.close()
                except Exception:
                    pass
                self._serial = None

            try:
                logger.info(f"Connecting to Arduino on {self.port} at {self.baudrate} baud...")
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.read_timeout,
                    write_timeout=self.write_timeout
                )

                # Arduino Uno / CH340 resets on DTR toggle; allow 2.0s for bootloader to finish
                time.sleep(2.0)
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

                # Send Handshake 'H'
                self._serial.write(b"H\n")
                self._serial.flush()

                # Wait up to read_timeout for "OK" response
                start_time = time.time()
                handshake_ok = False
                while (time.time() - start_time) < self.read_timeout:
                    line = self._serial.readline().decode("ascii", errors="ignore").strip()
                    if "OK" in line:
                        handshake_ok = True
                        break
                    time.sleep(0.05)

                if handshake_ok:
                    self.connected = True
                    self.mode = "real"
                    self.last_command = "H"
                    self.last_updated = datetime.now(timezone.utc).isoformat()
                    self.last_error = None
                    logger.info(f"Arduino handshake confirmed on {self.port}.")
                    return True
                else:
                    logger.warning(f"Arduino handshake failed on {self.port} (no OK received).")
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                    self._serial = None
                    self.connected = False
                    self.mode = "offline"
                    self.last_error = "Handshake timed out / invalid response"
                    return False

            except Exception as e:
                logger.warning(f"Failed to open port {self.port}: {e}")
                if self._serial:
                    try:
                        self._serial.close()
                    except Exception:
                        pass
                    self._serial = None
                self.connected = False
                self.mode = "offline"
                self.last_error = str(e)
                self.last_updated = datetime.now(timezone.utc).isoformat()
                return False

    def disconnect(self) -> None:
        """Closes serial connection cleanly without throwing exceptions."""
        with self._lock:
            if self._serial is not None:
                try:
                    if self._serial.is_open:
                        self._serial.close()
                except Exception as e:
                    logger.debug(f"Exception during serial close on {self.port}: {e}")
                finally:
                    self._serial = None
            self.connected = False
            self.mode = "offline"
            self.last_updated = datetime.now(timezone.utc).isoformat()
            logger.info(f"Disconnected Arduino controller on {self.port}.")

    def send_command(self, cmd: str) -> bool:
        """
        Sends single-byte ASCII command followed by newline.
        Valid commands: 'G', 'Y', 'R', 'A', 'C', 'H'.
        """
        cmd_clean = cmd.strip().upper()
        if not cmd_clean or cmd_clean not in VALID_COMMANDS:
            logger.warning(f"Invalid hardware command '{cmd}' ignored.")
            return False

        with self._lock:
            if not self.connected or self._serial is None or not self._serial.is_open:
                self.connected = False
                self.mode = "offline"
                return False

            try:
                payload = f"{cmd_clean}\n".encode("ascii")
                self._serial.write(payload)
                self._serial.flush()
                self.last_command = cmd_clean
                self.last_updated = datetime.now(timezone.utc).isoformat()
                self.last_error = None
                return True
            except Exception as e:
                logger.warning(f"Failed to write command '{cmd_clean}' to {self.port}: {e}")
                self.connected = False
                self.mode = "offline"
                self.last_error = str(e)
                self.last_updated = datetime.now(timezone.utc).isoformat()
                try:
                    if self._serial:
                        self._serial.close()
                except Exception:
                    pass
                self._serial = None
                return False

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "connected": self.connected,
                "mode": self.mode,
                "last_command": self.last_command,
                "last_updated": self.last_updated,
                "port": self.port,
                "last_error": self.last_error
            }

    def is_real(self) -> bool:
        return True
