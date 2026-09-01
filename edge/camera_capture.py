"""
Camera Capture Subsystem (edge/camera_capture.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Responsible for robust stream capture from RTSP, local video files, mobile streams,
or webcams with configurable FPS sampling and automatic reconnection logic.
"""

import time
import logging
from typing import Generator, Optional, Tuple
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CameraCapture")


class CameraStream:
    """Manages resilient frame extraction from a single video source."""

    def __init__(
        self,
        camera_id: str,
        stream_url: str,
        target_fps: float = 5.0,
        reconnect_delay_sec: float = 3.0,
        max_reconnect_attempts: int = 10,
    ):
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.target_fps = max(1.0, min(target_fps, 30.0))
        self.frame_interval = 1.0 / self.target_fps
        self.reconnect_delay_sec = reconnect_delay_sec
        self.max_reconnect_attempts = max_reconnect_attempts

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self.frame_count = 0
        self.is_connected = False

    def connect(self) -> bool:
        """Attempts to open the video capture stream."""
        if self.cap is not None:
            self.cap.release()

        logger.info(f"[{self.camera_id}] Connecting to stream: {self._sanitize_url(self.stream_url)}")

        # Handle numeric string for webcam device index
        source = int(self.stream_url) if self.stream_url.isdigit() else self.stream_url
        self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():
            logger.warning(f"[{self.camera_id}] Failed to open stream source.")
            self.is_connected = False
            return False

        self.is_connected = True
        logger.info(f"[{self.camera_id}] Stream connected successfully.")
        return True

    def _sanitize_url(self, url: str) -> str:
        """Sanitizes sensitive RTSP authentication credentials from logs."""
        if "@" in url and "://" in url:
            prefix, rest = url.split("://", 1)
            creds, address = rest.split("@", 1)
            return f"{prefix}://***:***@{address}"
        return url

    def stream_frames(self) -> Generator[Tuple[int, float, np.ndarray], None, None]:
        """
        Yields sampled frames at the designated target_fps.
        Yield tuple: (frame_id, timestamp_utc, frame_bgr)
        """
        self.is_running = True
        reconnect_attempts = 0

        while self.is_running:
            if self.cap is None or not self.cap.isOpened():
                if reconnect_attempts >= self.max_reconnect_attempts:
                    logger.error(f"[{self.camera_id}] Max reconnection attempts reached. Halting stream.")
                    break

                logger.info(f"[{self.camera_id}] Reconnecting in {self.reconnect_delay_sec}s (Attempt {reconnect_attempts + 1}/{self.max_reconnect_attempts})...")
                time.sleep(self.reconnect_delay_sec)
                reconnect_attempts += 1
                if not self.connect():
                    continue
                reconnect_attempts = 0

            start_time = time.time()
            ret, frame = self.cap.read()

            if not ret or frame is None:
                logger.warning(f"[{self.camera_id}] Empty or dropped frame received.")
                self.is_connected = False
                if self.cap:
                    self.cap.release()
                continue

            self.frame_count += 1
            timestamp = time.time()

            yield self.frame_count, timestamp, frame

            # Throttle to target FPS
            elapsed = time.time() - start_time
            sleep_duration = self.frame_interval - elapsed
            if sleep_duration > 0:
                time.sleep(sleep_duration)

    def release(self):
        """Releases the underlying OpenCV video capture resources."""
        self.is_running = False
        self.is_connected = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info(f"[{self.camera_id}] Stream released.")
