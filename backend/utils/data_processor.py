"""
Data Processor Subsystem (backend/utils/data_processor.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Validates, normalizes, and enriches detection events received from edge or local pipelines
into the standardized TrafficDetectionEvent schema.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class ClassCounts(BaseModel):
    car: int = Field(ge=0, default=0)
    bus: int = Field(ge=0, default=0)
    truck: int = Field(ge=0, default=0)
    bike: int = Field(ge=0, default=0)
    pedestrian: int = Field(ge=0, default=0)


class DetectionItem(BaseModel):
    track_id: Optional[int] = None
    class_name: str = Field(alias="class")
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[float] = Field(min_length=4, max_length=4)

    model_config = {
        "populate_by_name": True
    }


class TrafficDetectionEvent(BaseModel):
    camera_id: str
    timestamp: str
    frame_id: int = Field(ge=0, default=0)
    vehicle_count: int = Field(ge=0, default=0)
    class_counts: ClassCounts
    density: float = Field(ge=0.0, le=100.0)
    queue_length: float = Field(ge=0.0, default=0.0)
    detections: list[DetectionItem] = Field(default_factory=list)
    processing_time_ms: float = Field(ge=0.0, default=0.0)
    is_anomaly: bool = Field(default=False, description="Flag indicating accident/collision or stalled vehicle anomaly")

    @field_validator("timestamp")
    def validate_timestamp(cls, v: str) -> str:
        if not v:
            return datetime.now(timezone.utc).isoformat()
        return v


# Hardware Command Protocol Constants (Laptop -> Arduino)
HARDWARE_CMD_GREEN = "G"          # Low traffic density -> Green LED
HARDWARE_CMD_YELLOW = "Y"         # Medium traffic density -> Yellow LED
HARDWARE_CMD_RED = "R"            # Heavy congestion -> Red LED
HARDWARE_CMD_ANOMALY = "A"        # Accident / collision / stalled vehicle override -> Flashing red + buzzer
HARDWARE_CMD_CLEAR_ANOMALY = "C"  # Anomaly cleared -> Resume last traffic density state
HARDWARE_CMD_HEARTBEAT = "H"      # Heartbeat check -> Echoes 'OK'


def categorize_density_level(density: float) -> str:
    """Classifies 0-100 density score into standard urban traffic tiers."""
    if density < 25.0:
        return "LOW"
    elif density < 55.0:
        return "MODERATE"
    elif density < 80.0:
        return "HIGH"
    return "CRITICAL"


def map_density_to_hardware_command(density: float, is_anomaly: bool = False) -> str:
    """
    Maps traffic density (0.0 - 100.0) and anomaly status to single-byte hardware commands
    per Section 3 and Section 11 of HARDWARE_INTEGRATION_SIH26222.md:
      - is_anomaly == True        -> 'A' (Accident / stalled vehicle / collision override -> Flashing red + buzzer)
      - density < 33.0            -> 'G' (Low traffic density -> Green LED)
      - 33.0 <= density <= 66.0   -> 'Y' (Medium traffic density -> Yellow LED)
      - density > 66.0            -> 'R' (Heavy congestion -> Red LED)
    """
    if is_anomaly:
        return HARDWARE_CMD_ANOMALY
    if density < 33.0:
        return HARDWARE_CMD_GREEN
    elif density <= 66.0:
        return HARDWARE_CMD_YELLOW
    else:
        return HARDWARE_CMD_RED


def resolve_hardware_command_transition(
    density: float,
    is_anomaly: bool = False,
    prev_anomaly: bool = False
) -> tuple[str, ...]:
    """
    Resolves sequential hardware commands when taking state transitions into account.
    If an anomaly clears (prev_anomaly is True and is_anomaly is False):
      Yields ('C', normal_cmd) so hardware clears override and immediately applies normal state.
    """
    normal_cmd = map_density_to_hardware_command(density, is_anomaly=False)
    if is_anomaly:
        return (HARDWARE_CMD_ANOMALY,)
    if prev_anomaly and not is_anomaly:
        return (HARDWARE_CMD_CLEAR_ANOMALY, normal_cmd)
    return (normal_cmd,)


def normalize_detection_payload(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and enriches raw edge detection event against the shared schema contract.
    Throws ValidationError on schema violation.
    """
    event = TrafficDetectionEvent(**raw_event)
    data = event.model_dump(by_alias=True)
    data["congestion_level"] = categorize_density_level(event.density)
    data["hardware_command"] = map_density_to_hardware_command(event.density, event.is_anomaly)
    return data
