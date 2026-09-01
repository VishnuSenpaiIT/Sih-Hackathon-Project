from edge.traffic_analyzer import TrafficAnalyzer
import numpy as np

analyzer = TrafficAnalyzer()

custom = [
    {'class': 'car', 'confidence': 0.9, 'bbox': [100, 100, 200, 200]},
    {'class': 'bus', 'confidence': 0.85, 'bbox': [300, 150, 450, 280]},
]

frame = np.zeros((480, 640, 3), dtype=np.uint8)
for i in range(1, 4):
    result = analyzer.analyze_frame(frame, 'cam_test', i, custom_detections=custom)
    track_ids = [d['track_id'] for d in result['detections']]
    print("Frame", i, "- Vehicles:", result["vehicle_count"], "Density:", result["density"], "Track IDs:", track_ids)

print("Tracker persistent IDs OK" if len(set(track_ids)) == 2 else "WARNING: track_ids not consistent")
