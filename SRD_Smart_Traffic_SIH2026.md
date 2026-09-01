# SRD — Smart Traffic Monitoring & Prediction System

## 1. Document Information

| Field | Specification |
|---|---|
| System | Smart Traffic Monitoring & Prediction System |
| Problem Statement | SIH26222 / Transportation & Logistics |
| Theme | Transportation & Logistics / Smart Cities |
| Architecture | Software-first, AI-powered |
| Status | Development Phase 1 |
| Last Updated | September 1, 2026 |

---

## 2. System Purpose

The system shall transform existing CCTV infrastructure into an intelligent traffic-monitoring platform.

It shall ingest camera video, perform computer-vision analysis, convert observations into structured traffic data, store historical measurements, generate predictions, and expose real-time information through a web dashboard.

The system should require minimal additional hardware and support both edge and cloud/on-premise deployment.

---

## 3. High-Level Architecture

```text
┌──────────────────────────────────────────────┐
│              EXISTING CCTV CAMERAS           │
│       Traffic Junctions / Bus Stops /        │
│              Parking Locations                │
└──────────────────────┬───────────────────────┘
                       │
                       │ RTSP / ONVIF
                       ▼
┌──────────────────────────────────────────────┐
│             VIDEO INGESTION LAYER            │
│ OpenCV / FFmpeg                               │
│ Frame Extraction: 1–5 FPS                    │
│ Buffering / Reconnection / Stream Management │
└──────────────────────┬───────────────────────┘
                       │
                       │ Raw Frames
                       ▼
┌──────────────────────────────────────────────┐
│               AI ANALYSIS LAYER              │
│ YOLOv8 Detection                             │
│ Vehicle Classification                       │
│ Pedestrian Detection                         │
│ DeepSORT / ByteTrack Tracking                │
│ Density / Anomaly Analysis                   │
└──────────────────────┬───────────────────────┘
                       │
                       │ Structured JSON
                       ▼
┌──────────────────────────────────────────────┐
│          DATA PROCESSING & STORAGE           │
│ PostgreSQL                                   │
│ InfluxDB / TimescaleDB                       │
│ Redis / Kafka                                │
└──────────────────────┬───────────────────────┘
                       │
                       │ Analytics Data
                       ▼
┌──────────────────────────────────────────────┐
│          PREDICTION & ANALYTICS              │
│ LSTM / GRU / Transformer                     │
│ Congestion Forecasting                       │
│ Resource Optimization                        │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│             WEB DASHBOARD / API              │
│ React / Next.js                              │
│ REST + WebSocket / SSE                       │
│ Charts / Maps / Alerts                       │
└──────────────────────────────────────────────┘
```

---

## 4. System Components

### 4.1 Camera Manager

**Responsibility:** Maintain connections to configured video sources.

Requirements:

- Read RTSP streams.
- Support ONVIF-compatible camera sources where applicable.
- Maintain camera configuration.
- Buffer incoming frames.
- Reconnect after temporary failures.
- Expose camera health/status.
- Support multiple cameras.

Reference module:

```text
backend/utils/camera_manager.py
edge/camera_capture.py
```

---

### 4.2 Video Processing Pipeline

**Responsibility:** Convert camera streams into frames suitable for AI inference.

Requirements:

- Process frames at approximately 1–5 FPS.
- Avoid unnecessary frame processing.
- Handle dropped frames.
- Maintain timestamps.
- Associate every frame with a camera identifier.
- Provide frames to the AI inference pipeline.

Primary technologies:

- OpenCV
- FFmpeg

---

### 4.3 Object Detection Engine

**Responsibility:** Detect traffic objects.

Primary model:

- YOLOv8n

Supported categories:

- Car
- Bus
- Truck
- Bike
- Pedestrian

The detector shall produce structured detection information such as:

```json
{
  "camera_id": "camera_01",
  "timestamp": "2026-09-01T08:00:00",
  "detections": [
    {
      "class": "car",
      "confidence": 0.91,
      "bbox": [120, 80, 300, 240]
    }
  ]
}
```

---

## 5. Vehicle Tracking

The system shall support tracking detected vehicles between frames.

Supported approaches:

- DeepSORT
- ByteTrack

Tracking should provide stable object identifiers where possible.

Example conceptual output:

```json
{
  "track_id": 42,
  "class": "car",
  "camera_id": "camera_01",
  "timestamp": "2026-09-01T08:00:01"
}
```

---

## 6. Traffic Density Engine

The density engine shall transform object detections into a traffic-density measurement.

### Output

Density shall use a 0–100 scale.

The system may also calculate:

- Total vehicles.
- Vehicles by type.
- Queue length.
- Estimated traffic flow.
- Optional speed estimates.

The exact density calculation algorithm is implementation-specific and shall remain modular.

---

## 7. Anomaly Detection

The AI analysis layer shall provide a mechanism for detecting unusual traffic conditions.

Initial anomaly scope:

- Sudden congestion.
- Abnormal traffic density.
- Traffic-flow deviations.

Accident detection is considered an advanced future capability rather than a mandatory initial implementation.

---

## 8. Data Processing Layer

The data-processing layer shall normalize AI output into structured traffic events.

A traffic observation should conceptually contain:

```json
{
  "camera_id": "camera_01",
  "timestamp": "2026-09-01T08:00:05",
  "vehicle_count": 24,
  "cars": 16,
  "buses": 2,
  "trucks": 3,
  "bikes": 3,
  "pedestrians": 7,
  "density": 63
}
```

The processing layer shall:

- Validate incoming measurements.
- Add timestamps.
- Associate data with cameras.
- Aggregate observations.
- Prepare data for storage.
- Prepare data for prediction.

Reference module:

```text
backend/utils/data_processor.py
```

---

## 9. Storage Architecture

### PostgreSQL

Used for persistent application and historical data.

Potential records include:

- Camera metadata.
- Traffic observations.
- Prediction results.
- Alerts.
- System configuration.

### InfluxDB / TimescaleDB

Used for high-frequency time-series traffic measurements.

### Redis / Kafka

Used for real-time message/event transport where required.

The implementation may select the appropriate combination based on deployment requirements.

---

## 10. Backend API

The backend shall use:

- Python 3.10+
- FastAPI

### API Responsibilities

- Camera management.
- Traffic statistics.
- Historical data retrieval.
- Prediction retrieval.
- Alert retrieval.
- System health/status.
- Real-time data delivery.

### API Style

```text
REST API
+
WebSocket / Server-Sent Events
```

Reference modules:

```text
backend/main.py
backend/api/routes.py
backend/api/websocket.py
```

---

## 11. Real-Time Communication

The system shall support real-time dashboard updates.

Preferred mechanisms:

- WebSocket.
- Server-Sent Events where appropriate.

Real-time events may include:

```text
traffic_update
camera_status
prediction_update
congestion_alert
anomaly_alert
```

The communication layer shall avoid unnecessary polling where a push-based mechanism is appropriate.

---

## 12. Prediction Engine

The prediction engine shall consume historical traffic observations and generate short-term forecasts.

Supported model families:

- LSTM
- GRU
- Transformer

### Required Prediction Capability

- Hackathon target: approximately 1-hour traffic prediction.
- Product target: 1–6 hour short-term prediction.
- Daily/weekly traffic patterns may be incorporated for longer-term trend analysis.

Prediction output should be associated with:

- Camera.
- Forecast timestamp.
- Predicted traffic measure.
- Model/version information where applicable.

Reference module:

```text
backend/models/traffic_prediction.py
```

---

## 13. Analytics Engine

The analytics layer shall provide:

- Current traffic state.
- Historical trends.
- Traffic-flow prediction.
- Congestion forecasting.
- Resource optimization inputs.

Potential optimization technology:

- OR-Tools.
- Reinforcement learning.

Resource optimization is an analytical capability and should remain decoupled from the core detection pipeline.

---

## 14. Frontend System

The frontend shall use:

- React.js or Next.js.

### Main Components

```text
frontend/src/
├── App.jsx
├── components/
│   ├── Dashboard.jsx
│   ├── CameraFeed.jsx
│   └── PredictionChart.jsx
└── services/
    └── api.js
```

### Dashboard Requirements

The dashboard shall provide:

1. Live camera feed.
2. Detection overlays.
3. Vehicle counts.
4. Traffic density.
5. Historical charts.
6. Prediction graphs.
7. Alerts.
8. Multi-camera selection.
9. Map visualization where applicable.
10. Report export support.

---

## 15. Camera Feed Component

The camera-feed UI shall:

- Display a selected camera stream.
- Show detection overlays where available.
- Show camera status.
- Display relevant live traffic statistics.

The UI should distinguish unavailable/disconnected cameras from active cameras.

---

## 16. Prediction Visualization

The prediction interface shall visualize:

- Historical traffic measurements.
- Current traffic state.
- Forecast values.
- Forecast horizon.
- Congestion-related trends where available.

Charting technologies may include:

- Chart.js.
- D3.js.

---

## 17. Mapping

Leaflet may be used for geographic visualization.

The map layer can represent:

- Camera locations.
- Traffic conditions.
- Congestion areas.
- Camera health.

Map support is part of the dashboard visualization layer and does not alter the core video-processing architecture.

---

## 18. Edge System

The edge layer shall support low-cost local processing.

Reference structure:

```text
edge/
├── camera_capture.py
├── traffic_analyzer.py
└── config.json
```

Possible hardware:

- Raspberry Pi 4.
- NVIDIA Jetson Nano.

The edge layer should reduce unnecessary transmission of raw video when local inference is appropriate.

---

## 19. Camera Configuration

Camera addition should be configuration-driven.

Conceptual configuration:

```json
{
  "cameras": [
    {
      "id": "camera_01",
      "name": "Junction A",
      "stream_url": "<RTSP_STREAM>",
      "enabled": true
    }
  ]
}
```

Credentials and secrets must not be hard-coded into source files.

---

## 20. Performance Requirements

### Latency

Target:

```text
< 2 seconds end-to-end
```

### AI Processing

The project targets optimized real-time processing, with approximately:

```text
< 100 ms per frame
```

where hardware and model configuration permit.

### Frame Rate

Processing target:

```text
1–5 FPS
```

The pipeline should prioritize useful analytics over processing every available source frame.

---

## 21. Scalability Requirements

The architecture shall support:

- One camera for development/demo.
- Multiple cameras for production-style testing.
- Target capability of 100+ cameras.

Scaling should be achieved through modular processing and configuration-driven camera registration.

---

## 22. Reliability Requirements

The system shall gracefully handle:

- Camera disconnects.
- Temporary network failures.
- Invalid frames.
- Dropped frames.
- Backend service interruptions where possible.

Camera reconnection should occur without requiring manual application restart whenever feasible.

---

## 23. Security Requirements

The system shall:

- Protect RTSP credentials.
- Avoid hard-coded secrets.
- Provide API authentication for protected deployments.
- Secure real-time communication where deployed over untrusted networks.
- Consider privacy safeguards for future license-plate recognition.

---

## 24. Testing Requirements

Critical components should have automated tests.

Priority areas:

- Camera configuration.
- Stream-management behavior.
- Detection-data parsing.
- Density calculation.
- API endpoints.
- Prediction-data processing.
- Real-time event delivery.

Testing should include failure conditions such as camera disconnection and malformed data.

---

## 25. Deployment

### Local Development

```text
Backend:
Python 3.10+
FastAPI
Uvicorn

Frontend:
Node.js 18+
React / Next.js
```

### Containerized Deployment

Docker and Docker Compose are supported.

Conceptual services:

```text
backend
frontend
postgres
timeseries-db
redis
```

Additional services may be introduced when required.

### Production Options

- AWS.
- GCP.
- Azure.
- On-premise infrastructure.
- Edge deployment.

Kubernetes is optional for larger-scale orchestration.

---

## 26. Repository Structure

```text
smart-traffic-sih2026/
├── README.md
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── backend/
├── frontend/
├── edge/
├── demo/
├── notebooks/
└── docs/
```

The repository should preserve separation between backend, frontend, edge, demo, ML experimentation, and documentation.

---

## 27. Demo Requirements

The demo shall be capable of operating with a mobile camera as the practical video source.

Backup traffic footage and synthetic traffic may be used if live camera input is unavailable.

Demo sequence:

```text
Problem
  ↓
Live Camera
  ↓
Vehicle Detection
  ↓
Traffic Density
  ↓
Prediction
  ↓
Architecture
  ↓
Future Scope / Q&A
```

---

## 28. Technical Acceptance Criteria

The initial system is technically acceptable when it can demonstrate:

- A working camera/video input.
- Successful vehicle detection.
- Vehicle classification.
- Real-time vehicle counting.
- Traffic-density calculation.
- Data delivery to the backend.
- Dashboard display of live statistics.
- Historical traffic data storage.
- Traffic prediction demonstration.
- Camera switching/multi-camera structure.
- Congestion/anomaly alert representation.

---

## 29. Future Technical Extensions

The architecture should allow future integration of:

- Adaptive traffic signal optimization.
- Emergency vehicle priority.
- Parking-space detection.
- Public transport tracking.
- Air-quality correlation.
- Accident detection.
- Privacy-aware license-plate recognition.
- Reckless-driving detection.
- Multi-modal transportation analytics.

These capabilities are extensions and should not be coupled tightly to the initial detection pipeline.

---

## 30. Source Boundary

This SRD is derived from the supplied Smart Traffic Monitoring & Prediction System project specification. Where the specification gives alternatives (for example, InfluxDB/TimescaleDB or Redis/Kafka), this document preserves those alternatives rather than treating one as mandatory.
