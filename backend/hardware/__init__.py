"""
Hardware Bridge Package (backend/hardware/__init__.py)
Smart Traffic Monitoring & Prediction System (SIH26222)
"""

from backend.hardware.controller_interface import HardwareController, VALID_COMMANDS
from backend.hardware.mock_controller import MockArduinoController
from backend.hardware.arduino_controller import ArduinoController
from backend.hardware.hardware_manager import HardwareManager, hardware_manager

__all__ = [
    "HardwareController",
    "VALID_COMMANDS",
    "MockArduinoController",
    "ArduinoController",
    "HardwareManager",
    "hardware_manager",
]
