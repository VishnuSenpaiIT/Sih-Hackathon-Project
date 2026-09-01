"""
demo/video_demo.py — Live Video Traffic Analyzer
Smart Traffic Monitoring & Prediction System (SIH26222)

Feed ANY traffic video file through YOLOv8n and stream results live to the dashboard.

Usage:
    python -m demo.video_demo --video path/to/traffic.mp4
    python -m demo.video_demo --video path/to/traffic.mp4 --camera cam_01 --fps 10

What it does:
    1. Reads the video frame by frame with OpenCV
    2. Runs YOLOv8n object detection on each frame
    3. Draws bounding boxes + labels on the frame
    4. Sends the annotated frame to the backend MJPEG endpoint (shows in browser)
    5. POSTs detection results to /api/detections (live stats on dashboard)
    6. Dashboard WebSocket updates in real time — density, counts, classification
"""

import argparse
import base64
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import requests
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("VideoDemo")

# ── Backend endpoints ──────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api"

# ── COCO class → SIH class mapping (mirrors edge/traffic_analyzer.py) ─────────
COCO_MAP = {
    0: "pedestrian",
    1: "bike",
    2: "car",
    3: "bike",
    5: "bus",
    7: "truck",
}

CLASS_COLORS = {
    "car":        (52, 152, 219),   # blue
    "bus":        (231, 76,  60),   # red
    "truck":      (241, 196, 15),   # yellow
    "bike":       (46,  204, 113),  # green
    "pedestrian": (155, 89,  182),  # purple
}

VEHICLE_WEIGHTS = {
    "car": 1.0, "bus": 3.0, "truck": 3.0, "bike": 0.5, "pedestrian": 0.2
}


def calculate_density(class_counts, total_bbox_area, frame_area, max_threshold=25.0):
    if frame_area <= 0:
        return 0.0
    weighted = sum(class_counts.get(c, 0) * w for c, w in VEHICLE_WEIGHTS.items())
    count_score = min(1.0, weighted / max_threshold) * 60.0
    occ_score = min(1.0, total_bbox_area / frame_area) * 40.0
    return round(min(100.0, max(0.0, count_score + occ_score)), 2)


def encode_jpeg(frame: np.ndarray, quality: int = 75) -> bytes:
    """Encodes an OpenCV BGR frame as JPEG bytes."""
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


def draw_detections(frame: np.ndarray, detections: list, density: float, fps: float) -> np.ndarray:
    """Draws bounding boxes, labels, density bar, and FPS onto the frame."""
    vis = frame.copy()
    h, w = vis.shape[:2]

    for det in detections:
        cls = det["class"]
        conf = det["confidence"]
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        tid = det.get("track_id", "?")
        color = CLASS_COLORS.get(cls, (200, 200, 200))

        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        label = f"{cls} #{tid} {conf:.0%}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(vis, (x1, y1 - lh - 6), (x1 + lw + 4, y1), color, -1)
        cv2.putText(vis, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # Density bar overlay (top-right corner)
    bar_w = 180
    bar_h = 16
    bx, by = w - bar_w - 12, 12
    cv2.rectangle(vis, (bx, by), (bx + bar_w, by + bar_h), (40, 40, 40), -1)
    fill_w = int(bar_w * density / 100.0)
    bar_color = (52, 220, 90) if density < 60 else (241, 196, 15) if density < 75 else (231, 76, 60)
    cv2.rectangle(vis, (bx, by), (bx + fill_w, by + bar_h), bar_color, -1)
    cv2.putText(vis, f"Density {density:.0f}%", (bx, by - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

    # FPS badge
    cv2.putText(vis, f"{fps:.1f} fps", (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)

    return vis


def push_frame_to_backend(camera_id: str, jpeg_bytes: bytes, session: requests.Session):
    """Sends annotated JPEG frame to backend for MJPEG browser streaming."""
    b64 = base64.b64encode(jpeg_bytes).decode()
    try:
        session.post(
            f"{API_BASE}/streams/{camera_id}/frame",
            json={"frame_jpeg_b64": b64},
            timeout=0.5
        )
    except Exception:
        pass  # Non-critical — skip if backend busy


def post_detections(camera_id: str, result: dict, session: requests.Session):
    """Posts frame detection results to backend ingestion endpoint."""
    import time as _time
    payload = {
        "camera_id": camera_id,
        "timestamp": result["timestamp"],
        "frame_id": result["frame_id"],
        "vehicle_count": result["vehicle_count"],
        "class_counts": result["class_counts"],
        "density": result["density"],
        "queue_length": result["queue_length"],
        "detections": result["detections"],
        "processing_time_ms": result["processing_time_ms"]
    }
    try:
        session.post(f"{API_BASE}/detections", json=payload, timeout=1.0)
    except Exception as e:
        logger.warning(f"Failed to post detections: {e}")


def run_video_demo(
    video_path: str,
    camera_id: str = "cam_01",
    target_fps: float = 10.0,
    loop: bool = True,
    show_window: bool = False
):
    """Main video demo loop."""
    # Try to load YOLO
    model = None
    tracker = None
    try:
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        logger.info("YOLOv8n loaded successfully ✓")
    except Exception as e:
        logger.warning(f"YOLO not available ({e}) — using OpenCV background subtraction fallback")

    # Try to import tracker
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from edge.traffic_analyzer import RobustIoUTracker
        tracker = RobustIoUTracker(iou_threshold=0.25, max_lost=15)
        logger.info("IoU tracker initialized ✓")
    except Exception as e:
        logger.warning(f"Tracker unavailable: {e}")

    # Background subtractor as YOLO fallback
    bg_sub = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=50, detectShadows=False)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = 1.0 / target_fps
    frame_id = 0

    logger.info(f"Video: {video_path} | {total_frames} frames @ {src_fps:.0f} fps source")
    logger.info(f"Streaming to dashboard at {target_fps} fps → http://localhost:5173")
    logger.info(f"Camera: {camera_id} | MJPEG preview: http://localhost:8000/api/streams/{camera_id}/mjpeg")
    logger.info("Press Ctrl+C to stop\n")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    run = True
    while run:
        loop_start = time.time()
        ret, frame = cap.read()

        if not ret:
            if loop:
                logger.info("Video ended — looping from start")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if tracker:
                    tracker.reset()
                frame_id = 0
                continue
            else:
                logger.info("Video playback complete.")
                break

        frame_id += 1
        h, w = frame.shape[:2]
        frame_area = float(h * w)

        detections = []
        class_counts = {"car": 0, "bus": 0, "truck": 0, "bike": 0, "pedestrian": 0}
        total_bbox_area = 0.0
        t_start = time.time()

        if model is not None:
            # ── Real YOLO inference ──────────────────────────────────────────
            results = model.predict(
                source=frame,
                conf=0.40,
                classes=list(COCO_MAP.keys()),
                verbose=False
            )
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    mapped = COCO_MAP.get(cls_id)
                    if not mapped:
                        continue
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    bbox = [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]
                    total_bbox_area += max(0, (x2 - x1) * (y2 - y1))
                    class_counts[mapped] += 1
                    detections.append({
                        "track_id": None,
                        "class": mapped,
                        "confidence": round(conf, 3),
                        "bbox": bbox
                    })
        else:
            # ── OpenCV background subtraction fallback ───────────────────────
            fg_mask = bg_sub.apply(frame)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 800:
                    continue
                x, y, bw, bh = cv2.boundingRect(cnt)
                aspect = bw / max(bh, 1)
                cls = "car" if aspect > 1.2 else "pedestrian"
                total_bbox_area += area
                class_counts[cls] += 1
                detections.append({
                    "track_id": None,
                    "class": cls,
                    "confidence": 0.70,
                    "bbox": [float(x), float(y), float(x + bw), float(y + bh)]
                })

        # Run IoU tracker if available
        if tracker and detections:
            detections = tracker.update(detections)

        proc_ms = round((time.time() - t_start) * 1000, 1)
        density = calculate_density(class_counts, total_bbox_area, frame_area)
        vehicle_count = class_counts["car"] + class_counts["bus"] + class_counts["truck"] + class_counts["bike"]

        import time as _t
        ts = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
        result = {
            "camera_id": camera_id,
            "timestamp": ts,
            "frame_id": frame_id,
            "vehicle_count": vehicle_count,
            "class_counts": class_counts,
            "density": density,
            "queue_length": round(vehicle_count * 4.5, 1),
            "detections": detections,
            "processing_time_ms": proc_ms
        }

        # Draw annotations on frame
        elapsed = time.time() - loop_start
        actual_fps = 1.0 / max(elapsed, 0.001)
        annotated = draw_detections(frame, detections, density, actual_fps)

        # Push annotated frame to MJPEG endpoint
        jpeg = encode_jpeg(annotated, quality=70)
        push_frame_to_backend(camera_id, jpeg, session)

        # Post detection data to dashboard
        post_detections(camera_id, result, session)

        if frame_id % 20 == 0 or frame_id == 1:
            logger.info(
                f"Frame {frame_id:>5} | {vehicle_count:>2} vehicles | "
                f"Density: {density:>5.1f}% | {proc_ms:>5.1f}ms | "
                f"Cars:{class_counts['car']} Buses:{class_counts['bus']} "
                f"Trucks:{class_counts['truck']} Bikes:{class_counts['bike']}"
            )

        # Optional local preview window
        if show_window:
            cv2.imshow("Traffic Demo - Press Q to stop", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        # Throttle to target FPS
        elapsed = time.time() - loop_start
        sleep_time = frame_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    cap.release()
    if show_window:
        cv2.destroyAllWindows()
    session.close()
    logger.info("Video demo finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Video Traffic Demo for SIH26222")
    parser.add_argument(
        "--video", "-v", required=True,
        help="Path to traffic video file (MP4, AVI, MOV, etc.)"
    )
    parser.add_argument(
        "--camera", "-c", default="cam_01",
        help="Camera ID to assign (default: cam_01)"
    )
    parser.add_argument(
        "--fps", "-f", type=float, default=10.0,
        help="Target analysis FPS (default: 10)"
    )
    parser.add_argument(
        "--no-loop", action="store_true",
        help="Don't loop the video — stop after one pass"
    )
    parser.add_argument(
        "--window", "-w", action="store_true",
        help="Show local OpenCV preview window"
    )
    args = parser.parse_args()

    run_video_demo(
        video_path=args.video,
        camera_id=args.camera,
        target_fps=args.fps,
        loop=not args.no_loop,
        show_window=args.window
    )
