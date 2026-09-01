"""Continuous synthetic traffic loop — runs indefinitely for live demo."""
from demo.synthetic_traffic import stream_synthetic_traffic

if __name__ == "__main__":
    while True:
        stream_synthetic_traffic(
            endpoint="http://localhost:8000/api/detections",
            camera_id="cam_01",
            fps=2.0,
            duration_sec=3600  # 1 hour per loop
        )
