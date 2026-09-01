# API Reference — Smart Traffic Monitoring & Prediction System (SIH26222)

Base URL: `http://localhost:8000/api`  
Interactive Swagger Docs: `http://localhost:8000/docs`

---

## 1. System Health

### `GET /health`
Returns system status, active version, and server UTC timestamp.

**Response `200 OK`:**
```json
{
  "status": "healthy",
  "system": "Smart Traffic Monitoring & Prediction System",
  "version": "1.0.0",
  "timestamp": "2026-09-01T10:00:00.000000+00:00"
}
```

---

## 2. Cameras & Streams

### `GET /streams`
Lists all registered camera sources. Automatically syncs with `edge/config.json` if table is empty.

**Response `200 OK`:**
```json
[
  {
    "id": "cam_01",
    "name": "Connaught Place Junction",
    "stream_url": "demo/sample_videos/traffic_sample_01.mp4",
    "junction_name": "Outer Circle Junction",
    "latitude": 28.6315,
    "longitude": 77.2167,
    "enabled": true,
    "fps": 5.0
  }
]
```

---

## 3. Detection Ingestion & Analytics

### `POST /detections`
Ingests a structured detection event from Edge / CV pipeline, stores observation in relational DB, and broadcasts event to live WebSocket subscribers.

**Payload:** Conforms to `docs/schemas/detection_event.json`.

**Response `200 OK`:**
```json
{
  "status": "success",
  "recorded_id": 42
}
```

### `GET /detections`
Query recent historical traffic observations.

**Query Parameters:**
- `camera_id` (optional, string): Filter by specific camera.
- `limit` (optional, integer, default: 50, max: 500): Number of observations to retrieve.

**Response `200 OK`:** Array of observation records ordered by timestamp descending.

---

## 4. Real-Time WebSockets

### `ws://localhost:8000/ws`
Stream endpoint for real-time dashboard subscriptions.

**Query Parameters:**
- `camera_id` (optional, string): Filter messages for a specific camera, or omit to subscribe to all cameras.

**Sample Message:**
```json
{
  "type": "traffic_update",
  "data": {
    "camera_id": "cam_01",
    "timestamp": "2026-09-01T10:00:00Z",
    "frame_id": 105,
    "vehicle_count": 18,
    "class_counts": {
      "car": 12,
      "bus": 2,
      "truck": 1,
      "bike": 3,
      "pedestrian": 4
    },
    "density": 46.5,
    "queue_length": 81.0,
    "congestion_level": "MODERATE",
    "processing_time_ms": 42.1
  }
}
```
