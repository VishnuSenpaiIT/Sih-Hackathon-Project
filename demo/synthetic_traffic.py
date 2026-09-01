"""
Synthetic Traffic Generator (demo/synthetic_traffic.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Provides realistic synthetic traffic stream simulations for testing and hackathon backup demo.
Emits events strictly conforming to docs/schemas/detection_event.json.
"""

import time
import math
import random
import logging
from typing import Dict, Any
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyntheticTraffic")


def generate_synthetic_event(
    camera_id: str = "cam_synthetic_01",
    frame_id: int = 1,
    base_load: float = 0.5
) -> Dict[str, Any]:
    """
    Generates a deterministic yet organically fluctuating traffic detection payload.
    base_load: float between 0.1 (midnight) and 1.0 (rush hour).
    """
    # Fluctuate with sine wave + small noise
    t = time.time()
    cycle = (math.sin(t / 10.0) + 1.0) / 2.0  # 0.0 to 1.0
    effective_load = min(1.0, max(0.05, (base_load * 0.7) + (cycle * 0.3) + random.uniform(-0.05, 0.05)))

    # Vehicle counts scaling with load
    cars = int(25 * effective_load) + random.randint(0, 3)
    buses = int(4 * effective_load) + (1 if random.random() > 0.6 else 0)
    trucks = int(3 * effective_load) + (1 if random.random() > 0.7 else 0)
    bikes = int(12 * effective_load) + random.randint(0, 4)
    pedestrians = int(10 * effective_load) + random.randint(0, 3)

    total_vehicles = cars + buses + trucks + bikes
    density = round(min(100.0, (effective_load * 85.0) + random.uniform(-3.0, 5.0)), 1)
    queue_length = round(total_vehicles * 4.2, 1)

    # Generate synthetic bounding boxes
    detections = []
    for i in range(min(total_vehicles, 8)):
        detections.append({
            "track_id": 100 + i,
            "class": "car" if i % 2 == 0 else "bike",
            "confidence": round(random.uniform(0.78, 0.96), 2),
            "bbox": [
                round(random.uniform(50, 400), 1),
                round(random.uniform(100, 350), 1),
                round(random.uniform(450, 600), 1),
                round(random.uniform(380, 500), 1)
            ]
        })

    return {
        "camera_id": camera_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)),
        "frame_id": frame_id,
        "vehicle_count": total_vehicles,
        "class_counts": {
            "car": cars,
            "bus": buses,
            "truck": trucks,
            "bike": bikes,
            "pedestrian": pedestrians
        },
        "density": density,
        "queue_length": queue_length,
        "detections": detections,
        "processing_time_ms": round(random.uniform(28.0, 58.0), 1)
    }


def stream_synthetic_traffic(
    endpoint: str = "http://localhost:8000/api/detections",
    camera_id: str = "cam_01",
    fps: float = 2.0,
    duration_sec: float = 60.0
):
    """Streams generated traffic events to the backend ingestion endpoint."""
    interval = 1.0 / max(0.5, fps)
    start_time = time.time()
    frame_id = 1

    logger.info(f"Starting synthetic traffic stream to {endpoint} (Interval: {interval}s)...")

    while (time.time() - start_time) < duration_sec:
        payload = generate_synthetic_event(camera_id=camera_id, frame_id=frame_id)
        try:
            res = requests.post(endpoint, json=payload, timeout=2.0)
            if res.status_code == 200:
                logger.info(f"[Frame #{frame_id}] Ingested: {payload['vehicle_count']} vehicles | Density: {payload['density']}%")
            else:
                logger.warning(f"[Frame #{frame_id}] Server returned status {res.status_code}")
        except Exception as e:
            logger.error(f"Failed to post to backend: {e}")

        frame_id += 1
        time.sleep(interval)

    logger.info("Synthetic traffic stream simulation completed.")


if __name__ == "__main__":
    stream_synthetic_traffic(duration_sec=30.0)
