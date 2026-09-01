"""
Test Video Analysis Engine
"""
import requests
import time
from pathlib import Path

BASE = "http://127.0.0.1:8000/api"

def test():
    print("--- 1. Checking initial status ---")
    r = requests.get(f"{BASE}/video-analysis/status")
    print("Status:", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 2. Triggering sample analysis ---")
    r = requests.post(f"{BASE}/video-analysis/sample?target_fps=15.0")
    print("Sample start:", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 3. Polling status during processing ---")
    for _ in range(6):
        time.sleep(0.6)
        r = requests.get(f"{BASE}/video-analysis/status")
        d = r.json()
        print(f"Frame {d.get('current_frame')}/{d.get('total_frames')} ({d.get('progress_percent')}%) | FPS: {d.get('fps')} | Density: {d.get('density')}% | Vehicles: {d.get('vehicle_count')} | Status: {d.get('status')}")

    print("\n--- 4. Checking camera stream registration ---")
    r = requests.get(f"{BASE}/streams/cam_upload")
    print("Camera stream:", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 5. Checking MJPEG stream endpoint ---")
    r = requests.get(f"{BASE}/streams/cam_upload/mjpeg", stream=True, timeout=3.0)
    assert r.status_code == 200
    chunk = next(r.iter_content(chunk_size=2048))
    print("MJPEG stream response received, first chunk size:", len(chunk))
    assert len(chunk) > 0

    print("\n--- 6. Checking historical detections saved to DB ---")
    r = requests.get(f"{BASE}/detections?camera_id=cam_upload&limit=5")
    print(f"Saved observations count: {len(r.json())}")
    if r.json():
        print("Sample observation:", r.json()[0])

    print("\n--- 7. Testing graceful stop ---")
    r = requests.post(f"{BASE}/video-analysis/stop")
    print("Stop response:", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 8. Testing file upload endpoint ---")
    sample_file = Path("demo/sample_videos/traffic_sample_01.mp4")
    with open(sample_file, "rb") as f:
        files = {"file": ("test_traffic_upload.mp4", f, "video/mp4")}
        r = requests.post(f"{BASE}/upload-video", files=files, params={"target_fps": 12.0})
    print("Upload response:", r.status_code, r.json())
    assert r.status_code == 200

    time.sleep(1.0)
    r = requests.get(f"{BASE}/video-analysis/status")
    print("Status after upload:", r.json())

    # Stop analysis after verifying upload started
    requests.post(f"{BASE}/video-analysis/stop")

    print("\n=== ALL VIDEO ANALYSIS TESTS PASSED! ===")

if __name__ == "__main__":
    test()
