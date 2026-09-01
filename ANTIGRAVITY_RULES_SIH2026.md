# ANTIGRAVITY RULES — Smart Traffic Monitoring & Prediction System

> These rules define the operating constraints for AI coding agents and automated development tools working on this project.

---

## 1. Core Rule

**Do not violate the project's PRD or SRD.**

All implementation decisions must preserve the documented product scope, system architecture, technology direction, performance targets, security requirements, and modular boundaries.

When a requirement is not defined, do not silently invent a major architectural decision. Keep the implementation modular and consistent with the existing project structure.

---

## 2. Source of Truth

The following project documents are authoritative:

```text
PRD_Smart_Traffic_SIH2026.md
SRD_Smart_Traffic_SIH2026.md
ANTIGRAVITY_RULES_SIH2026.md
```

When implementing a feature:

1. Read the relevant requirements first.
2. Follow existing architecture.
3. Preserve established interfaces.
4. Avoid unnecessary redesign.
5. Keep changes focused on the requested task.

---

## 3. Project Scope Rules

The core system is:

```text
Existing CCTV
    ↓
RTSP / ONVIF
    ↓
Video Ingestion
    ↓
AI Detection
    ↓
Traffic Analytics
    ↓
Data Storage
    ↓
Prediction
    ↓
Dashboard / Alerts
```

Do not replace this architecture with an unrelated architecture unless explicitly requested.

The primary product principle is:

**Software-first + existing CCTV + minimal additional hardware.**

---

## 4. Technology Rules

### Backend

Use:

```text
Python 3.10+
FastAPI
OpenCV
Ultralytics YOLOv8
PyTorch / TensorFlow
PostgreSQL
InfluxDB / TimescaleDB
Redis / Kafka
```

Do not introduce a replacement backend framework without explicit approval.

### Frontend

Use:

```text
React.js / Next.js
Chart.js / D3.js
Leaflet
WebSocket / Server-Sent Events
```

Do not replace the frontend stack merely for convenience.

### Deployment

Prefer:

```text
Docker
Docker Compose
AWS / GCP / Azure / On-Premise
Raspberry Pi 4 / NVIDIA Jetson Nano
```

Kubernetes remains optional.

---

## 5. Architecture Rules

Maintain clear separation between:

```text
Camera / Video Ingestion
AI Analysis
Data Processing
Storage
Prediction / Analytics
API
Frontend
Edge
Demo
```

Do not tightly couple:

- Camera capture to UI code.
- YOLO inference to database implementation.
- Prediction models to frontend components.
- Edge-specific logic to cloud-only services.

Each layer should have a clear responsibility.

---

## 6. Camera Rules

Camera sources shall be configuration-driven.

Never hard-code camera credentials or sensitive stream URLs.

Use environment variables or secure configuration for secrets.

The camera subsystem must account for:

- Connection failures.
- Stream interruptions.
- Invalid frames.
- Buffering.
- Automatic reconnection.

A camera failure must not unnecessarily crash the entire application.

---

## 7. RTSP / ONVIF Rules

The video pipeline shall support the project's RTSP/ONVIF direction.

Prefer efficient frame processing.

Target processing range:

```text
1–5 FPS
```

Do not process every source frame by default when doing so provides no product benefit.

Always associate processed frames and analytics with:

```text
camera_id
timestamp
```

---

## 8. AI Rules

### Object Detection

Primary detector:

```text
YOLOv8n
```

Initial traffic classes:

```text
car
bus
truck
bike
pedestrian
```

Do not silently change the detection model or class semantics.

### Tracking

Supported tracking approaches:

```text
DeepSORT
ByteTrack
```

Tracking must remain replaceable.

Do not make the rest of the application dependent on one tracker implementation.

---

## 9. Detection Output Rules

AI inference should produce structured data rather than UI-specific output.

Conceptual structure:

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

Keep model inference output separate from presentation formatting.

---

## 10. Traffic Analytics Rules

Traffic analytics must be derived from structured detection/tracking data.

Supported metrics include:

```text
vehicle count
vehicle type counts
traffic density
queue length
traffic flow
optional speed estimation
```

Traffic density uses the project's:

```text
0–100 scale
```

Keep the density algorithm modular so it can be improved without rewriting the ingestion or UI layers.

---

## 11. Prediction Rules

Prediction is a downstream analytics capability.

Supported model families:

```text
LSTM
GRU
Transformer
```

Initial hackathon target:

```text
approximately 1-hour traffic prediction
```

Product target:

```text
1–6 hour short-term prediction
```

Prediction models must not block the real-time detection pipeline.

Inference failures should degrade gracefully and should not make live vehicle detection unavailable.

---

## 12. Data Rules

Traffic observations must be structured and timestamped.

At minimum, traffic analytics should preserve camera identity and observation time.

Do not mix raw video storage with analytical traffic records unless explicitly required.

Use the intended storage roles:

```text
PostgreSQL
    application / historical relational data

InfluxDB / TimescaleDB
    high-frequency time-series data

Redis / Kafka
    real-time event/message transport
```

Do not store credentials in source code.

---

## 13. API Rules

The API layer uses FastAPI.

Keep API routes thin.

Business logic should remain in appropriate service/model modules rather than being placed entirely inside route handlers.

Support:

```text
REST
WebSocket / SSE
```

Real-time updates should use push-based communication where appropriate.

Do not create unnecessary polling loops.

---

## 14. Frontend Rules

The dashboard must represent the actual system state.

Do not create fake live statistics in production application code.

Demo-only simulation data must be clearly isolated inside the demo layer.

The frontend should consume backend APIs/events rather than directly accessing databases or model internals.

Keep components modular.

Primary dashboard concerns:

```text
Live camera
Vehicle detection
Traffic density
Historical data
Predictions
Alerts
Multi-camera selection
```

---

## 15. Real-Time Rules

The system targets:

```text
< 2 seconds end-to-end latency
```

Optimize the hot path before adding unnecessary features.

Where feasible, AI processing should move toward:

```text
~100 ms per frame
```

Do not sacrifice correctness merely to claim a latency number.

Measure performance rather than assuming it.

---

## 16. Scalability Rules

Design for multiple cameras from the beginning.

Target:

```text
100+ cameras
```

Camera registration should be configuration-driven.

Avoid global state that assumes only one camera.

Every camera-specific operation should be identifiable by camera ID.

---

## 17. Error Handling Rules

All external systems are unreliable.

Handle failures from:

- Cameras.
- Network connections.
- Databases.
- Message queues.
- AI inference.
- External services.

Use graceful degradation.

Examples:

```text
Camera disconnected
→ mark camera unavailable
→ attempt reconnection
→ keep other cameras running

Prediction unavailable
→ retain live analytics
→ report prediction unavailable
```

Never hide errors silently.

Provide useful logs without exposing secrets.

---

## 18. Security Rules

Never hard-code:

```text
passwords
API keys
database credentials
RTSP credentials
tokens
private keys
```

Use environment variables and secure configuration.

Do not commit `.env` files containing real secrets.

Validate API inputs.

Protect administrative functionality.

When future license-plate recognition is implemented, privacy safeguards are mandatory.

---

## 19. Privacy Rules

The core system should focus on traffic analytics rather than unnecessary personal identification.

Do not introduce personally identifying data collection unless required by an explicitly approved feature.

Future license-plate recognition must include privacy safeguards.

Do not expose sensitive camera credentials or private stream URLs through frontend responses or logs.

---

## 20. Code Quality Rules

Write:

- Clean code.
- Modular code.
- Readable code.
- Typed interfaces where practical.
- Useful comments.
- Function/class docstrings.
- Explicit error handling.

Avoid:

- Giant files.
- Giant functions.
- Duplicate logic.
- Dead code.
- Unnecessary abstractions.
- Hard-coded configuration.
- Hidden global state.

---

## 21. File Structure Rules

Respect the intended repository structure:

```text
smart-traffic-sih2026/
├── backend/
├── frontend/
├── edge/
├── demo/
├── notebooks/
└── docs/
```

Use:

```text
backend/models/
```

for AI/data model logic.

Use:

```text
backend/api/
```

for API and WebSocket endpoints.

Use:

```text
backend/utils/
```

for reusable infrastructure utilities.

Use:

```text
edge/
```

for edge-specific processing.

Use:

```text
demo/
```

for demonstrations, simulation, mobile-camera integration, and backup footage.

Do not place demo hacks inside production modules.

---

## 22. Dependency Rules

Do not add a dependency when the existing stack can reasonably solve the problem.

Before adding a package:

1. Confirm it is necessary.
2. Check whether an existing dependency already provides the capability.
3. Keep the dependency focused.
4. Update the appropriate dependency file.
5. Avoid abandoned or unnecessary libraries.

Do not silently upgrade core frameworks as part of an unrelated task.

---

## 23. Database Rules

Database access must remain isolated from API presentation logic.

Use migrations/schema management where applicable.

Do not destroy or reset existing data during normal development commands.

Never use destructive database operations as an automatic fallback.

---

## 24. Testing Rules

Critical functionality must be testable.

Prioritize tests for:

```text
camera configuration
stream management
reconnection
detection parsing
density calculation
API endpoints
prediction data processing
real-time events
```

Include failure cases.

A feature is not considered complete merely because the happy path works.

---

## 25. Logging Rules

Logs should help diagnose:

```text
camera status
stream failures
AI inference failures
database failures
prediction failures
API failures
```

Never log:

```text
passwords
API keys
authentication tokens
RTSP credentials
private secrets
```

Use appropriate log levels.

Avoid excessive per-frame logging in production.

---

## 26. Configuration Rules

Configuration must be externalized wherever practical.

Examples:

```text
camera URLs
database URLs
model paths
confidence thresholds
frame rates
service ports
feature flags
```

Use:

```text
.env
config.json
environment variables
```

according to the component's needs.

Provide safe example configuration without real credentials.

---

## 27. Demo Rules

The demo must be isolated from production logic.

Supported demo inputs:

```text
mobile camera
sample traffic videos
synthetic traffic
```

The demo should demonstrate the actual product pipeline whenever possible.

Do not fake a feature and present it as a working production capability.

If simulation is necessary, clearly label it as simulation.

---

## 28. AI Model Rules

Model files should not be unnecessarily embedded in application source code.

Model configuration should be replaceable.

Inference code should expose a stable interface so the underlying model can be changed without rewriting the entire application.

Model confidence thresholds should be configurable.

---

## 29. Performance Rules

When performance is poor:

1. Measure the bottleneck.
2. Optimize the bottleneck.
3. Re-measure.
4. Preserve correctness.

Potential optimization areas:

- Frame sampling.
- Model size.
- Batch processing.
- Resolution.
- Tracking frequency.
- Async processing.
- Queue management.
- Edge/cloud workload distribution.

Do not prematurely optimize unrelated components.

---

## 30. Change Rules

For every requested code change:

1. Understand the affected subsystem.
2. Make the smallest coherent change.
3. Preserve existing APIs unless a breaking change is explicitly requested.
4. Update related tests.
5. Update documentation when behavior changes.
6. Check for regressions.

Do not rewrite working modules without a concrete reason.

---

## 31. Breaking Change Rules

Avoid breaking:

```text
API contracts
data formats
camera configuration
frontend/backend interfaces
database schemas
```

If a breaking change is unavoidable, update every affected consumer in the same change.

Do not leave the repository in a partially migrated state.

---

## 32. Documentation Rules

Important behavior must be documented.

Maintain documentation for:

```text
architecture
API reference
deployment
camera configuration
AI pipeline
prediction pipeline
environment configuration
```

Every public or important function should have a useful docstring.

Documentation must describe actual behavior, not intended behavior that has not been implemented.

---

## 33. Notebook Rules

Notebooks are for:

```text
model training
experimentation
data analysis
exploration
```

Production code should not depend directly on notebook execution.

Reusable logic discovered in notebooks should be moved into appropriate project modules.

---

## 34. Future Feature Rules

The following are future extensions and must not be treated as mandatory core functionality unless explicitly requested:

```text
adaptive traffic signal optimization
emergency vehicle priority
parking-space detection
public transport tracking
air-quality integration
accident detection
license-plate recognition
reckless-driving detection
multi-modal transport integration
```

Do not implement future features at the expense of completing the core traffic-monitoring pipeline.

---

## 35. Cost Rules

The project is designed around minimal additional hardware.

Do not introduce expensive infrastructure without a clear technical requirement.

Reference deployment target:

```text
~₹5,600 per edge node
```

The system should continue to support a development/demo mode using existing:

```text
laptop / PC
mobile phone
internet connection
```

---

## 36. AI Agent Behavior Rules

When an AI coding agent is asked to modify the project:

### MUST

- Read relevant project files before changing them.
- Follow the PRD and SRD.
- Inspect existing code before creating duplicate functionality.
- Preserve architecture.
- Keep changes focused.
- Handle errors.
- Avoid secrets.
- Add/update tests where relevant.
- Explain meaningful assumptions.

### MUST NOT

- Invent unsupported requirements.
- Rewrite the entire project unnecessarily.
- Replace the technology stack without approval.
- Hard-code credentials.
- Put demo-only logic into production modules.
- Claim a feature works without verifying it.
- Remove working functionality without justification.
- Introduce unrelated dependencies.
- Ignore existing interfaces.

---

## 37. Completion Rule

A task is complete only when:

```text
Implementation
    +
Integration
    +
Error Handling
    +
Relevant Tests
    +
Documentation (when needed)
```

are addressed appropriately for the requested scope.

---

## 38. Final Principle

**Build the simplest reliable implementation that satisfies the documented Smart Traffic Monitoring & Prediction System requirements, while preserving modularity, real-time performance, scalability, security, and demo readiness.**
