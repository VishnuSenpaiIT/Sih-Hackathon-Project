"""
Hackathon Demo Orchestrator (demo/hackathon_demo.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Orchestrates the 7-minute SIH live evaluation presentation flow:
1. System health verification
2. Video source selection (Live Mobile / Local Video / Synthetic Fallback)
3. End-to-end pipeline execution with real-time feedback
"""

import sys
import time
import requests
import logging

from demo.synthetic_traffic import stream_synthetic_traffic
from demo.mobile_camera import run_mobile_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HackathonDemo")


def verify_backend(url: str = "http://localhost:8000/api/health") -> bool:
    """Verifies that the FastAPI backend is running and healthy."""
    try:
        res = requests.get(url, timeout=2.0)
        return res.status_code == 200 and res.json().get("status") == "healthy"
    except Exception:
        return False


def print_banner():
    banner = """
    ========================================================================
        SIH 2026: SMART TRAFFIC MONITORING & PREDICTION SYSTEM (SIH26222)
                 Software-First Urban Traffic Intelligence
    ========================================================================
    """
    print(banner)


def main():
    print_banner()

    print("[Step 1/3] Checking Backend Health...")
    if not verify_backend():
        print("\n[!] Backend service is NOT currently running at http://localhost:8000.")
        print("    Please start the backend in a separate terminal:")
        print("    --> uvicorn backend.main:app --port 8000 --reload\n")
    else:
        print("[OK] Backend is healthy and listening on http://localhost:8000")

    print("\n[Step 2/3] Choose Ingestion Mode:")
    print("  1. Synthetic Traffic Generator (Zero-setup test & fallback)")
    print("  2. Smartphone / IP Camera Live Stream")
    print("  3. Exit")

    choice = input("\nEnter choice [1-3] (default 1): ").strip() or "1"

    if choice == "1":
        print("\n--> Launching Synthetic Traffic Simulation (Duration: 60s)...")
        print("--> Open the dashboard in your browser: http://localhost:5173\n")
        stream_synthetic_traffic(duration_sec=60.0)
    elif choice == "2":
        url = input("Enter Mobile Stream URL (e.g., http://192.168.1.5:8080/video): ").strip()
        if not url:
            print("No URL entered. Aborting.")
            return
        print(f"\n--> Ingesting from {url}...")
        print("--> Open the dashboard in your browser: http://localhost:5173\n")
        run_mobile_pipeline(stream_url=url)
    else:
        print("Exiting demo orchestrator.")


if __name__ == "__main__":
    main()
