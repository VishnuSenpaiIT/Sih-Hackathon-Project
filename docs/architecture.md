# System Architecture — Smart Traffic Monitoring & Prediction System (SIH26222)

## 1. Overview
The system is built on a **software-first** paradigm, using existing city CCTV cameras with minimal edge computing hardware (~₹5,600 per edge node) to produce real-time traffic detection, density estimation (0–100 scale), and predictive traffic forecasts.

## 2. Layered Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    EXISTING CCTV CAMERAS                     │
│  (City Traffic Junctions, Bus Stops, Parking Lots, etc.)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ RTSP / ONVIF / HTTP
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              VIDEO INGESTION LAYER (Edge / Cloud)            │
│  • RTSP Stream Capture (OpenCV)                             │
│  • Frame Extraction (1-5 FPS for compute efficiency)        │
│  • Stream Management (resilient auto-reconnect, buffering)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Raw Frames
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              AI ANALYSIS LAYER (Computer Vision)             │
│  • Object Detection: YOLOv8n (Target <100ms/frame)          │
│  • Classification: Car, Bus, Truck, Bike, Pedestrian        │
│  • Density Calculation: 0-100 scale (weighted occupancy)    │
│  • Tracking: DeepSORT / ByteTrack                           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Structured Event JSON
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              DATA PROCESSING & STORAGE LAYER                 │
│  • Pydantic validation & schema normalization               │
│  • PostgreSQL (Relational & Historical Observations)        │
│  • Optional InfluxDB / TimescaleDB (Time-series metrics)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Real-time & Stored Analytics
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  FASTAPI APPLICATION LAYER                  │
│  • Thin REST routes (/api/health, /api/streams, /api/stats) │
│  • High-throughput WebSocket broadcast (/ws)                │
└──────────────────────────────┬──────────────────────────────┘
                               │ Push Events & JSON
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   REACT + VITE DASHBOARD                    │
│  • Real-time Vehicle Counter                                │
│  • 0-100 Dynamic Density Gauge                              │
│  • Live Camera Selector & Stream Ingestion Monitor          │
│  • Minimal, zero-bloat system font architecture             │
└─────────────────────────────────────────────────────────────┘
```

## 3. Data Contracts
- **Detection Event Schema:** `docs/schemas/detection_event.json`
- **Camera Configuration Schema:** `docs/schemas/camera_config.json`
- **Edge Configuration:** `edge/config.json`
