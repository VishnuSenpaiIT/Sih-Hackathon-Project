"""
Traffic Analyzer Subsystem (edge/traffic_analyzer.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Responsible for YOLOv8n object detection, multi-object tracking (persistent track_id),
class mapping (car, bus, truck, bike, pedestrian), and modular traffic density calculation (0-100 scale).
"""

import time
import logging
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger("TrafficAnalyzer")

# Standard COCO to SIH class mapping
COCO_TRAFFIC_MAP = {
    0: "pedestrian",  # person
    1: "bike",        # bicycle
    2: "car",         # car
    3: "bike",        # motorcycle
    5: "bus",         # bus
    7: "truck"        # truck
}

# Vehicle weights for density scoring
VEHICLE_WEIGHTS = {
    "car": 1.0,
    "bus": 3.0,
    "truck": 3.0,
    "bike": 0.5,
    "pedestrian": 0.2
}


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """
    Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2].
    """
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    if inter_area <= 0.0:
        return 0.0

    box1_area = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    box2_area = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    denom = box1_area + box2_area - inter_area

    if denom <= 0.0:
        return 0.0

    return inter_area / denom


def calculate_density(
    class_counts: Dict[str, int],
    total_bbox_area: float,
    frame_area: float,
    max_density_threshold: float = 25.0
) -> float:
    """
    Computes traffic density index strictly on a 0-100 scale.
    Combines weighted vehicle count load and roadway pixel occupancy ratio.
    """
    if frame_area <= 0:
        return 0.0

    # Weighted vehicle units
    weighted_units = sum(class_counts.get(cls_name, 0) * weight for cls_name, weight in VEHICLE_WEIGHTS.items())
    count_score = min(1.0, weighted_units / max_density_threshold) * 60.0

    # Area occupancy ratio (bounding box area / frame area)
    occupancy_ratio = min(1.0, total_bbox_area / frame_area)
    occupancy_score = occupancy_ratio * 40.0

    density = min(100.0, max(0.0, count_score + occupancy_score))
    return round(density, 2)


class Track:
    """Represents a single persistent tracked vehicle/object across frames."""

    def __init__(self, track_id: int, bbox: List[float], cls_name: str, confidence: float):
        self.track_id: int = track_id
        self.bbox: List[float] = [float(x) for x in bbox]
        self.cls_name: str = cls_name
        self.confidence: float = confidence
        self.hits: int = 1
        self.age: int = 1
        self.time_since_update: int = 0
        self.velocity: List[float] = [0.0, 0.0]  # [vx, vy] of center

    @property
    def center(self) -> Tuple[float, float]:
        cx = (self.bbox[0] + self.bbox[2]) / 2.0
        cy = (self.bbox[1] + self.bbox[3]) / 2.0
        return cx, cy

    def predict(self) -> List[float]:
        """Predicts expected bounding box based on estimated velocity."""
        vx, vy = self.velocity
        return [
            self.bbox[0] + vx,
            self.bbox[1] + vy,
            self.bbox[2] + vx,
            self.bbox[3] + vy
        ]

    def update(self, bbox: List[float], cls_name: str, confidence: float, momentum: float = 0.6):
        """Updates track state with a matched detection in the current frame."""
        old_cx, old_cy = self.center
        new_bbox = [float(x) for x in bbox]
        new_cx = (new_bbox[0] + new_bbox[2]) / 2.0
        new_cy = (new_bbox[1] + new_bbox[3]) / 2.0

        # Update smooth velocity vector
        inst_vx = new_cx - old_cx
        inst_vy = new_cy - old_cy
        self.velocity[0] = momentum * self.velocity[0] + (1.0 - momentum) * inst_vx
        self.velocity[1] = momentum * self.velocity[1] + (1.0 - momentum) * inst_vy

        self.bbox = new_bbox
        self.cls_name = cls_name
        self.confidence = confidence
        self.hits += 1
        self.age += 1
        self.time_since_update = 0


class RobustIoUTracker:
    """
    High-speed, robust ByteTrack-style IoU multi-object tracker.
    Maintains persistent integer track IDs across frames with sub-millisecond overhead.
    """

    def __init__(self, iou_threshold: float = 0.25, max_lost: int = 15):
        self.iou_threshold = iou_threshold
        self.max_lost = max_lost
        self.next_track_id = 1
        self.tracks: List[Track] = []

    def reset(self):
        """Clears all active tracks and resets track ID sequence."""
        self.tracks.clear()
        self.next_track_id = 1

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Associates input detections with existing tracks.
        Assigns persistent track_id integers to each detection in-place.
        """
        if not detections and not self.tracks:
            return detections

        # Predict positions for existing tracks
        predicted_boxes = [t.predict() for t in self.tracks]

        unmatched_dets = set(range(len(detections)))
        unmatched_tracks = set(range(len(self.tracks)))
        matches: List[Tuple[int, int]] = []

        if self.tracks and detections:
            # Build IoU matrix: (num_tracks, num_detections)
            iou_matrix = np.zeros((len(self.tracks), len(detections)), dtype=np.float32)
            for t_idx, pred_box in enumerate(predicted_boxes):
                for d_idx, det in enumerate(detections):
                    det_box = det["bbox"]
                    # Prefer matching same or compatible classes
                    iou = calculate_iou(pred_box, det_box)
                    if self.tracks[t_idx].cls_name == det["class"]:
                        iou_matrix[t_idx, d_idx] = iou
                    else:
                        iou_matrix[t_idx, d_idx] = iou * 0.7  # Small penalty for class switch

            # Greedy matching in descending order of IoU
            flat_indices = np.argsort(-iou_matrix, axis=None)
            for idx in flat_indices:
                t_idx = int(idx // len(detections))
                d_idx = int(idx % len(detections))
                iou_val = iou_matrix[t_idx, d_idx]

                if iou_val < self.iou_threshold:
                    break

                if t_idx in unmatched_tracks and d_idx in unmatched_dets:
                    matches.append((t_idx, d_idx))
                    unmatched_tracks.remove(t_idx)
                    unmatched_dets.remove(d_idx)

        # Update matched tracks
        for t_idx, d_idx in matches:
            track = self.tracks[t_idx]
            det = detections[d_idx]
            track.update(det["bbox"], det["class"], det["confidence"])
            det["track_id"] = track.track_id

        # Mark unmatched tracks as lost or aging
        surviving_tracks: List[Track] = []
        for t_idx in unmatched_tracks:
            track = self.tracks[t_idx]
            track.time_since_update += 1
            track.age += 1
            if track.time_since_update <= self.max_lost:
                surviving_tracks.append(track)

        # Keep active matched tracks
        for t_idx, _ in matches:
            surviving_tracks.append(self.tracks[t_idx])

        # Create new tracks for unmatched detections
        for d_idx in unmatched_dets:
            det = detections[d_idx]
            new_track = Track(
                track_id=self.next_track_id,
                bbox=det["bbox"],
                cls_name=det["class"],
                confidence=det["confidence"]
            )
            self.next_track_id += 1
            surviving_tracks.append(new_track)
            det["track_id"] = new_track.track_id

        self.tracks = surviving_tracks
        return detections


class TrafficAnalyzer:
    """YOLOv8-based computer vision analyzer for traffic streams with multi-object tracking."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.40,
        iou_threshold: float = 0.25,
        max_lost: int = 15
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.tracker = RobustIoUTracker(iou_threshold=iou_threshold, max_lost=max_lost)
        self.model = None
        self._load_model()

    def _load_model(self):
        """Loads Ultralytics YOLOv8 model safely."""
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLOv8 model from {self.model_path}...")
            self.model = YOLO(self.model_path)
            logger.info("YOLOv8 model initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize Ultralytics YOLO ({e}). Running in lightweight mock/fallback mode.")
            self.model = None

    def reset_tracker(self):
        """Resets the internal tracking state."""
        self.tracker.reset()

    def calculate_density(
        self,
        class_counts: Dict[str, int],
        total_bbox_area: float,
        frame_area: float,
        max_density_threshold: float = 25.0
    ) -> float:
        """Computes traffic density index strictly on a 0-100 scale."""
        return calculate_density(class_counts, total_bbox_area, frame_area, max_density_threshold)

    def analyze_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        frame_id: int,
        timestamp: Optional[float] = None,
        custom_detections: Optional[List[Dict[str, Any]]] = None,
        is_anomaly: bool = False
    ) -> Dict[str, Any]:
        """
        Runs object detection and multi-object tracking on a single frame.
        Produces structured analytics including persistent track_ids.
        """
        start_time = time.time()
        timestamp = timestamp or start_time

        h, w = frame.shape[:2] if hasattr(frame, "shape") and len(frame.shape) >= 2 else (720, 1280)
        frame_area = float(h * w)

        detections: List[Dict[str, Any]] = []
        class_counts = {"car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0}
        total_bbox_area = 0.0

        if custom_detections is not None:
            # External or simulated detections provided (e.g. for testing)
            for d in custom_detections:
                cls_name = d.get("class", "car")
                bbox = d.get("bbox", [0, 0, 50, 50])
                conf = float(d.get("confidence", 0.9))
                box_area = max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
                total_bbox_area += box_area
                if cls_name in class_counts:
                    class_counts[cls_name] += 1
                detections.append({
                    "track_id": None,
                    "class": cls_name,
                    "confidence": round(conf, 3),
                    "bbox": [round(float(coord), 1) for coord in bbox]
                })
        elif self.model is not None:
            try:
                results = self.model.predict(
                    source=frame,
                    conf=self.confidence_threshold,
                    classes=list(COCO_TRAFFIC_MAP.keys()),
                    verbose=False
                )

                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        mapped_class = COCO_TRAFFIC_MAP.get(cls_id)

                        if mapped_class:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            bbox = [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]
                            box_area = max(0.0, (x2 - x1) * (y2 - y1))
                            total_bbox_area += box_area

                            class_counts[mapped_class] += 1
                            detections.append({
                                "track_id": None,
                                "class": mapped_class,
                                "confidence": round(conf, 3),
                                "bbox": bbox
                            })
            except Exception as e:
                logger.error(f"Inference error on frame {frame_id}: {e}")

        # Execute multi-object tracking to assign persistent integer track_id
        detections = self.tracker.update(detections)

        # Total motorized vehicles
        vehicle_count = class_counts["car"] + class_counts["bus"] + class_counts["truck"] + class_counts["bike"]
        density = self.calculate_density(class_counts, total_bbox_area, frame_area)
        processing_time_ms = round((time.time() - start_time) * 1000.0, 2)

        return {
            "camera_id": camera_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
            "frame_id": frame_id,
            "vehicle_count": vehicle_count,
            "class_counts": class_counts,
            "density": density,
            "queue_length": round(vehicle_count * 4.5, 1),  # Simple baseline queue estimate
            "detections": detections,
            "processing_time_ms": processing_time_ms,
            "is_anomaly": is_anomaly
        }
