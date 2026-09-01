"""
Mobile Camera Stream Ingestion Bridge (demo/mobile_camera.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Enables quick pairing with standard smartphone IP camera apps (e.g., IP Webcam on Android/iOS)
to serve as a live CCTV feed for testing and hackathon demonstrations.
"""

import sys
import time
import logging
import cv2
import requests

from edge.camera_capture import CameraStream
from edge.traffic_analyzer import TrafficAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MobileCameraBridge")


def test_camera_reachability(url: str, timeout_sec: float = 3.0) -> bool:
    """Verifies that the mobile stream or HTTP endpoint is reachable."""
    logger.info(f"Testing reachability of mobile stream at: {url}")
    try:
        if url.startswith("http://") or url.startswith("https://"):
            res = requests.head(url, timeout=timeout_sec)
            return res.status_code < 400
        else:
            # RTSP check using OpenCV
            cap = cv2.VideoCapture(url)
            reachable = cap.isOpened()
            cap.release()
            return reachable
    except Exception as e:
        logger.warning(f"Reachability check failed: {e}")
        return False


def run_mobile_pipeline(
    stream_url: str,
    backend_ingest_url: str = "http://localhost:8000/api/detections",
    camera_id: str = "cam_mobile_demo",
    target_fps: float = 5.0
):
    """Captures frames from mobile camera and pipes detections to backend in real time."""
    logger.info(f"Initiating mobile pipeline for {camera_id}...")
    stream = CameraStream(
        camera_id=camera_id,
        stream_url=stream_url,
        target_fps=target_fps
    )

    if not stream.connect():
        logger.error(f"Cannot establish stream with {stream_url}. Please check WiFi / IP settings.")
        return

    analyzer = TrafficAnalyzer()

    try:
        for frame_id, timestamp, frame in stream.stream_frames():
            # Run inference
            result = analyzer.analyze_frame(
                frame=frame,
                camera_id=camera_id,
                frame_id=frame_id,
                timestamp=timestamp
            )

            # Ingest into backend API
            try:
                res = requests.post(backend_ingest_url, json=result, timeout=1.0)
                if res.status_code == 200:
                    logger.info(f"Frame #{frame_id} -> {result['vehicle_count']} vehicles | Density: {result['density']}% ({result['processing_time_ms']}ms)")
            except Exception as err:
                logger.debug(f"Backend post error: {err}")

    except KeyboardInterrupt:
        logger.info("Mobile camera capture stopped by user.")
    finally:
        stream.release()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = "http://192.168.1.100:8080/video"
        print(f"No stream URL provided. Defaulting to: {target_url}")
        print("Usage: python demo/mobile_camera.py <STREAM_URL>")

    run_mobile_pipeline(stream_url=target_url)
