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

    @field_validator("timestamp")
    def validate_timestamp(cls, v: str) -> str:
        if not v:
            return datetime.now(timezone.utc).isoformat()
        return v


def categorize_density_level(density: float) -> str:
    """Classifies 0-100 density score into standard urban traffic tiers."""
    if density < 25.0:
        return "LOW"
    elif density < 55.0:
        return "MODERATE"
    elif density < 80.0:
        return "HIGH"
    return "CRITICAL"


def normalize_detection_payload(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates and enriches raw edge detection event against the shared schema contract.
    Throws ValidationError on schema violation.
    """
    event = TrafficDetectionEvent(**raw_event)
    data = event.model_dump(by_alias=True)
    data["congestion_level"] = categorize_density_level(event.density)
    return data
