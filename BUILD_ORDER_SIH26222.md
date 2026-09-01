# Build Order — Smart Traffic Monitoring & Prediction System (SIH26222)

Purpose: defines the exact sequence in which modules must be built so each agent's output is available when the next agent needs it. No agent starts a task whose dependencies aren't marked ✅ Done.

## Phase 0 — Foundation (must complete first)
- [x] 1. Repo scaffold (folder structure per project doc) ✅ Done
- [x] 2. `.env.example`, `requirements.txt`, `docker-compose.yml` stubs ✅ Done
- [x] 3. Shared config schema (`edge/config.json` shape agreed by all agents) ✅ Done
- [x] 4. Shared data contract: JSON schema for detection events (used by CV → Backend → Frontend) ✅ Done

## Phase 1 — Core Pipeline (Week 1-2)
Order matters — each step unblocks the next:
- [x] 1. Camera Manager (`edge/camera_capture.py`) — RTSP/mobile stream reader → raw frames ✅ Done
- [x] 2. YOLOv8 detection wrapper (`edge/traffic_analyzer.py`) — frames → detections ✅ Done
- [x] 3. Data Processor (`backend/utils/data_processor.py`) — detections → structured JSON matching shared schema ✅ Done
- [x] 4. FastAPI skeleton (`backend/main.py`, `api/routes.py`) — expose `/health`, `/streams`, `/detections` ✅ Done
- [x] 5. DB models + migrations (`backend/models/database.py`) — Postgres + SQLite fallback ✅ Done
- [x] 6. WebSocket broadcast (`backend/api/websocket.py`) — push live detection data ✅ Done
- [x] 7. React dashboard skeleton (`frontend/src/App.jsx`) — connect to WebSocket, render raw counts ✅ Done

**Checkpoint:** live camera → detection → dashboard number updates end-to-end. (Ready for verification)

## Phase 2 — Advanced Features (Week 3-4)
- [x] 1. DeepSORT/ByteTrack tracking (depends on Phase 1 step 2) ✅ Done
- [x] 2. LSTM training notebook (`notebooks/model_training.ipynb`) — depends on stored historical data from step 1.5 ✅ Done
- [x] 3. Prediction service (`backend/models/traffic_prediction.py`) — depends on step 2 ✅ Done
4. `PredictionChart.jsx` — depends on step 3
5. Multi-camera config support — depends on Phase 0 step 3
6. Edge optimization pass for Raspberry Pi — depends on all Phase 1 CV code

## Phase 3 — Demo Hardening (Week 5)
1. Synthetic traffic fallback (`demo/synthetic_traffic.py`)
2. `hackathon_demo.py` orchestration script
3. Sample backup videos
4. Docs pass (`api_reference.md`, `deployment_guide.md`)
5. Slide deck + demo video

## Hard Dependencies Table
| Building | Needs |
|---|---|
| Backend API | Shared data schema (Phase 0) |
| Frontend dashboard | Backend WebSocket live |
| Prediction model | A few hours of stored detection data |
| Multi-camera dashboard | Multi-camera config support |
| Demo script | Everything in Phase 1 + fallback video |

## Rule
An agent that hits a missing dependency stops and reports the blocker in its status update — it does not stub around it silently.
