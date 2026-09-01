"""
Hardware Controller Interface (backend/hardware/controller_interface.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Defines the abstract base class contract for physical and simulated Arduino hardware controllers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Valid protocol commands per Hardware Integration specification:
# 'G': Low traffic density (Green LED on, others off)
# 'Y': Medium traffic density (Yellow LED on, others off)
# 'R': Heavy traffic density (Red LED on, others off)
# 'A': Accident/anomaly flagged (Accident override: flash red + buzzer pattern)
# 'C': Accident flag cleared (Exit override, resume last traffic density state)
# 'H': Heartbeat / connection check (Arduino echoes "OK")
VALID_COMMANDS = {"G", "Y", "R", "A", "C", "H"}


class HardwareController(ABC):
    """Abstract base class interface for hardware traffic signal controllers."""

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection to the hardware device. Returns True on success."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Terminates connection to the hardware device cleanly."""
        pass

    @abstractmethod
    def send_command(self, cmd: str) -> bool:
        """
        Sends a single-byte command to the controller.
        Valid commands: 'G', 'Y', 'R', 'A', 'C', 'H'.
        Returns True if transmission succeeded.
        """
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """
        Returns a dictionary representing current controller state:
        - connected: bool
        - mode: "simulated" | "real" | "offline"
        - last_command: Optional[str]
        - last_updated: str (ISO 8601 timestamp)
        - port: Optional[str]
        """
        pass

    @abstractmethod
    def is_real(self) -> bool:
        """Returns True if backed by physical hardware, False if mock/simulated."""
        pass
