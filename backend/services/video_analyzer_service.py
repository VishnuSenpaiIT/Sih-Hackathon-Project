"""
Video Analyzer Service (backend/services/video_analyzer_service.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Processes uploaded or sample traffic videos frame-by-frame:
- YOLOv8 vehicle detection with COCO class mapping
- Robust multi-object tracking (persistent integer track_id) via RobustIoUTracker
- Live frame annotation and in-memory MJPEG streaming
- Live WebSocket broadcasting for traffic telemetry and progress updates
- Relational database persistence of traffic observations
"""

import os
import sys
import time
import logging
import threading
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import cv2
import numpy as np

from edge.traffic_analyzer import (
    RobustIoUTracker,
    COCO_TRAFFIC_MAP,
    VEHICLE_WEIGHTS
)
from backend.utils.data_processor import (
    normalize_detection_payload,
    TrafficDetectionEvent
)
from backend.models.database import (
    SessionLocal,
    TrafficObservationModel,
    CameraModel
)
from backend.api.websocket import ws_manager

logger = logging.getLogger("VideoAnalyzerService")

# Storage directory for uploaded videos
UPLOAD_DIR = Path("uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Visual colors in OpenCV BGR format
CLASS_COLORS = {
    "car": (240, 160, 40),       # Blue / Cyan
    "bus": (60, 70, 230),        # Red / Coral
    "truck": (20, 200, 240),     # Yellow / Gold
    "bike": (70, 210, 60),       # Green / Emerald
    "pedestrian": (180, 80, 160) # Purple / Violet
}


def calculate_density(
    class_counts: Dict[str, int],
    total_bbox_area: float,
    frame_area: float,
    max_density_threshold: float = 25.0
) -> float:
    """Computes traffic density index on a 0-100 scale."""
    if frame_area <= 0:
        return 0.0
    weighted_units = sum(
        class_counts.get(cls_name, 0) * VEHICLE_WEIGHTS.get(cls_name, 1.0)
        for cls_name in VEHICLE_WEIGHTS
    )
    count_score = min(1.0, weighted_units / max_density_threshold) * 60.0
    occupancy_ratio = min(1.0, total_bbox_area / frame_area)
    occupancy_score = occupancy_ratio * 40.0
    return round(min(100.0, max(0.0, count_score + occupancy_score)), 2)


class VideoAnalyzerService:
    """
    Singleton service managing the background video analysis pipeline.
    Controls execution, tracking state, annotations, and client broadcasting.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VideoAnalyzerService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._model = None

        # State tracking fields
        self.is_running: bool = False
        self.is_paused: bool = False
        self.current_frame: int = 0
        self.total_frames: int = 0
        self.progress_percent: float = 0.0
        self.fps: float = 0.0
        self.camera_id: str = "cam_upload"
        self.filename: str = ""
        self.vehicle_count: int = 0
        self.density: float = 0.0
        self.class_counts: Dict[str, int] = {
            "car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0
        }
        self.status: str = "idle"  # idle, analyzing, completed, stopped, error
        self.error_message: Optional[str] = None

    def _get_model(self):
        """Lazy-loads or returns cached Ultralytics YOLO model."""
        if self._model is None:
            try:
                from ultralytics import YOLO
                logger.info("Initializing YOLO('yolov8n.pt') for video analysis...")
                self._model = YOLO("yolov8n.pt")
                logger.info("YOLO('yolov8n.pt') successfully loaded.")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                raise RuntimeError(f"YOLO model loading failed: {e}")
        return self._model

    def _push_frame(self, camera_id: str, jpeg_bytes: bytes):
        """Dispatches latest JPEG frame to the API route buffer for MJPEG streaming."""
        try:
            from backend.api.routes import push_video_frame
            push_video_frame(camera_id, jpeg_bytes)
        except Exception as e:
            logger.debug(f"Frame push warning: {e}")

    def _broadcast_sync(self, message: Dict[str, Any], camera_id: Optional[str] = None):
        """Sends WebSocket broadcast message safely across threads into the asyncio event loop."""
        target_loop = self._loop
        if target_loop is None:
            try:
                target_loop = asyncio.get_event_loop()
            except RuntimeError:
                target_loop = None

        if target_loop and target_loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(message=message, camera_id=camera_id),
                    target_loop
                )
            except Exception as e:
                logger.debug(f"WebSocket broadcast error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Returns snapshot of the current analysis engine state."""
        with self._state_lock:
            return {
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "status": self.status,
                "current_frame": self.current_frame,
                "total_frames": self.total_frames,
                "progress_percent": round(self.progress_percent, 1),
                "fps": round(self.fps, 1),
                "camera_id": self.camera_id,
                "filename": self.filename,
                "vehicle_count": self.vehicle_count,
                "density": round(self.density, 1),
                "class_counts": dict(self.class_counts),
                "error_message": self.error_message
            }

    def stop_analysis(self):
        """Signals active analysis thread to stop gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping active video analysis...")
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            # Wait up to 2 seconds for worker thread to stop
            self._worker_thread.join(timeout=2.0)

        with self._state_lock:
            self.is_running = False
            self.status = "stopped"

        # Broadcast stopped progress
        self._broadcast_sync(
            {
                "type": "analysis_progress",
                "data": {
                    "camera_id": self.camera_id,
                    "current_frame": self.current_frame,
                    "total_frames": self.total_frames,
                    "progress_percent": round(self.progress_percent, 1),
                    "fps": round(self.fps, 1),
                    "status": "stopped",
                    "filename": self.filename,
                    "vehicle_count": self.vehicle_count,
                    "density": round(self.density, 1)
                }
            },
            camera_id=self.camera_id
        )

    def start_analysis(
        self,
        video_path: str,
        camera_id: str = "cam_upload",
        target_fps: float = 10.0,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Dict[str, Any]:
        """
        Initiates asynchronous background video analysis.
        Stops any ongoing analysis before launching the new session.
        """
        video_path_obj = Path(video_path).resolve()
        if not video_path_obj.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Stop prior worker if active
        if self.is_running:
            self.stop_analysis()

        # Capture or assign asyncio loop
        if loop is not None:
            self._loop = loop
        else:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    self._loop = asyncio.get_event_loop()
                except Exception:
                    self._loop = None

        # Inspect video metadata
        cap = cv2.VideoCapture(str(video_path_obj))
        if not cap.isOpened():
            raise ValueError(f"OpenCV could not open video file: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = 1
        cap.release()

        # Reset states
        self._stop_event.clear()
        self._pause_event.clear()
        filename = video_path_obj.name

        with self._state_lock:
            self.is_running = True
            self.is_paused = False
            self.status = "analyzing"
            self.current_frame = 0
            self.total_frames = total_frames
            self.progress_percent = 0.0
            self.fps = target_fps
            self.camera_id = camera_id
            self.filename = filename
            self.vehicle_count = 0
            self.density = 0.0
            self.class_counts = {"car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0}
            self.error_message = None

        # Start processing in dedicated worker thread
        self._worker_thread = threading.Thread(
            target=self._process_video,
            args=(str(video_path_obj), camera_id, target_fps),
            daemon=True,
            name=f"VideoAnalyzer-{camera_id}"
        )
        self._worker_thread.start()

        logger.info(f"Video analysis started for {filename} ({total_frames} frames) on {camera_id}")

        return {
            "status": "started",
            "camera_id": camera_id,
            "filename": filename,
            "total_frames": total_frames
        }

    def _process_video(self, video_path: str, camera_id: str, target_fps: float):
        """Worker loop executing YOLO detection, tracking, visual annotation, and telemetry push."""
        cap = None
        try:
            model = self._get_model()
            tracker = RobustIoUTracker(iou_threshold=0.25, max_lost=15)

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open video stream: {video_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                total_frames = self.total_frames or 1

            frame_delay = 1.0 / max(1.0, target_fps)
            frame_id = 0
            stopped_early = False

            while not self._stop_event.is_set():
                frame_start = time.time()
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                frame_id += 1
                h, w = frame.shape[:2]
                frame_area = float(h * w)

                # 1. YOLOv8 Object Detection
                results = model.predict(
                    source=frame,
                    conf=0.35,
                    classes=list(COCO_TRAFFIC_MAP.keys()),
                    verbose=False
                )

                raw_detections: List[Dict[str, Any]] = []
                class_counts = {"car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0}
                total_bbox_area = 0.0

                if results and len(results) > 0:
                    boxes = results[0].boxes
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
                            raw_detections.append({
                                "track_id": None,
                                "class": mapped_class,
                                "confidence": round(conf, 3),
                                "bbox": bbox
                            })

                # 2. Multi-Object Tracking with persistent integer track_id
                tracked_detections = tracker.update(raw_detections)

                # 3. Density & Counts Calculation
                vehicle_count = (
                    class_counts["car"] +
                    class_counts["bus"] +
                    class_counts["truck"] +
                    class_counts["bike"]
                )
                density = calculate_density(class_counts, total_bbox_area, frame_area)
                queue_length = round(vehicle_count * 4.5, 1)

                # 4. Visual Annotations (Bounding Boxes, Track Labels, Density Bar, HUD)
                annotated = frame.copy()

                # Draw bounding boxes & labels
                for det in tracked_detections:
                    cls_name = det["class"]
                    conf = det["confidence"]
                    x1, y1, x2, y2 = [int(coord) for coord in det["bbox"]]
                    tid = det.get("track_id")
                    tid_label = f"#{tid}" if tid is not None else ""
                    color = CLASS_COLORS.get(cls_name, (200, 200, 200))

                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    label = f"{cls_name} {tid_label} {conf:.0%}".strip()
                    (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    tag_top = max(38, y1 - lh - 6)
                    cv2.rectangle(annotated, (x1, tag_top), (x1 + lw + 6, tag_top + lh + 6), color, -1)
                    cv2.putText(
                        annotated,
                        label,
                        (x1 + 3, tag_top + lh + 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (255, 255, 255),
                        1,
                        cv2.LINE_AA
                    )

                # Top HUD Banner
                overlay = annotated.copy()
                cv2.rectangle(overlay, (0, 0), (w, 36), (15, 20, 28), -1)
                cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

                hud_text = (
                    f"AI VISION | Vehicles: {vehicle_count} "
                    f"(Car:{class_counts['car']} Bus:{class_counts['bus']} "
                    f"Truck:{class_counts['truck']} Bike:{class_counts['bike']} "
                    f"Ped:{class_counts['pedestrian']})"
                )
                cv2.putText(
                    annotated,
                    hud_text,
                    (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (230, 235, 240),
                    1,
                    cv2.LINE_AA
                )

                # Density meter (top right)
                bar_w = 130
                bar_h = 14
                bx = w - bar_w - 12
                by = 11
                cv2.rectangle(annotated, (bx, by), (bx + bar_w, by + bar_h), (40, 45, 55), -1)
                fill_w = int(bar_w * (density / 100.0))
                bar_color = (
                    (60, 210, 80) if density < 50
                    else (20, 190, 240) if density < 75
                    else (50, 60, 230)
                )
                if fill_w > 0:
                    cv2.rectangle(annotated, (bx, by), (bx + fill_w, by + bar_h), bar_color, -1)
                cv2.putText(
                    annotated,
                    f"Density {density:.0f}%",
                    (bx - 85, 23),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (220, 225, 230),
                    1,
                    cv2.LINE_AA
                )

                # 5. Measure instantaneous processing and regulate FPS
                proc_time_ms = round((time.time() - frame_start) * 1000.0, 1)
                actual_fps = 1.0 / max(0.001, (time.time() - frame_start))

                # Bottom progress bar & stats overlay
                pct = min(100.0, (frame_id / max(1, total_frames)) * 100.0)
                prog_w = int(w * (pct / 100.0))
                cv2.rectangle(annotated, (0, h - 4), (prog_w, h), (0, 200, 255), -1)
                cv2.putText(
                    annotated,
                    f"Frame {frame_id}/{total_frames} ({pct:.0f}%) | {actual_fps:.1f} FPS",
                    (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (200, 200, 200),
                    1,
                    cv2.LINE_AA
                )

                # 6. Encode frame to JPEG and update MJPEG stream buffer
                ok, jpeg_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    self._push_frame(camera_id, jpeg_buf.tobytes())

                # 7. Normalize event payload
                now_iso = datetime.now(timezone.utc).isoformat()
                raw_event = {
                    "camera_id": camera_id,
                    "timestamp": now_iso,
                    "frame_id": frame_id,
                    "vehicle_count": vehicle_count,
                    "class_counts": class_counts,
                    "density": density,
                    "queue_length": queue_length,
                    "detections": tracked_detections,
                    "processing_time_ms": proc_time_ms
                }
                normalized = normalize_detection_payload(raw_event)

                # 8. Persist observation to relational database
                try:
                    with SessionLocal() as db:
                        obs = TrafficObservationModel(
                            camera_id=camera_id,
                            timestamp=datetime.fromisoformat(now_iso.replace("Z", "+00:00")),
                            frame_id=frame_id,
                            vehicle_count=vehicle_count,
                            cars=class_counts["car"],
                            buses=class_counts["bus"],
                            trucks=class_counts["truck"],
                            bikes=class_counts["bike"],
                            pedestrians=class_counts["pedestrian"],
                            density=density,
                            queue_length=queue_length,
                            processing_time_ms=proc_time_ms
                        )
                        db.add(obs)
                        db.commit()
                except Exception as db_err:
                    logger.warning(f"DB persist observation error: {db_err}")

                # 9. Update state
                with self._state_lock:
                    self.current_frame = frame_id
                    self.total_frames = total_frames
                    self.progress_percent = pct
                    self.fps = actual_fps
                    self.vehicle_count = vehicle_count
                    self.density = density
                    self.class_counts = class_counts

                # 10. Broadcast WebSocket events
                # Telemetry update
                self._broadcast_sync(
                    {"type": "traffic_update", "data": normalized},
                    camera_id=camera_id
                )
                # Progress update
                self._broadcast_sync(
                    {
                        "type": "analysis_progress",
                        "data": {
                            "camera_id": camera_id,
                            "current_frame": frame_id,
                            "total_frames": total_frames,
                            "progress_percent": round(pct, 1),
                            "fps": round(actual_fps, 1),
                            "status": "analyzing",
                            "filename": self.filename,
                            "vehicle_count": vehicle_count,
                            "density": density
                        }
                    },
                    camera_id=camera_id
                )

                # 11. Regulate playback pace to target FPS
                elapsed = time.time() - frame_start
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            if self._stop_event.is_set():
                stopped_early = True

            # Final state update
            final_status = "stopped" if stopped_early else "completed"
            with self._state_lock:
                self.is_running = False
                self.status = final_status
                self.progress_percent = 100.0 if not stopped_early else self.progress_percent

            # Broadcast final completion/stop status
            self._broadcast_sync(
                {
                    "type": "analysis_progress",
                    "data": {
                        "camera_id": camera_id,
                        "current_frame": self.current_frame,
                        "total_frames": self.total_frames,
                        "progress_percent": round(self.progress_percent, 1),
                        "fps": round(self.fps, 1),
                        "status": final_status,
                        "filename": self.filename,
                        "vehicle_count": self.vehicle_count,
                        "density": round(self.density, 1)
                    }
                },
                camera_id=camera_id
            )
            logger.info(f"Video analysis {final_status} for {self.filename} ({self.current_frame}/{total_frames} frames)")

        except Exception as e:
            logger.error(f"Video analysis failed with error: {e}", exc_info=True)
            with self._state_lock:
                self.is_running = False
                self.status = "error"
                self.error_message = str(e)
            self._broadcast_sync(
                {
                    "type": "analysis_progress",
                    "data": {
                        "camera_id": camera_id,
                        "current_frame": self.current_frame,
                        "total_frames": self.total_frames,
                        "progress_percent": round(self.progress_percent, 1),
                        "fps": 0.0,
                        "status": "error",
                        "filename": self.filename,
                        "error": str(e)
                    }
                },
                camera_id=camera_id
            )
        finally:
            if cap is not None and hasattr(cap, "release"):
                cap.release()


# Global singleton instance
video_analyzer_service = VideoAnalyzerService()
