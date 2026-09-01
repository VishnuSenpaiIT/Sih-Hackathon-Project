# Sub-Agent Task Breakdown — Smart Traffic Monitoring & Prediction System (SIH26222)

Granular task lists per agent, ordered to match `BUILD_ORDER_SIH26222.md` phases. Each task should be checked off as DONE before the agent moves to the next.

## 🧭 Orchestrator Agent
- [ ] Maintain BUILD_ORDER phase tracker
- [ ] Assign tasks per kickoff protocol
- [ ] Resolve schema/contract conflicts
- [ ] Run integration checkpoints after each phase
- [ ] Keep a running blocker log

## 🔧 Backend Agent
**Phase 0**
- [x] Scaffold `backend/` folder structure
- [x] Draft detection-event JSON schema, share with AI/ML + Frontend agents

**Phase 1**
- [x] `backend/utils/data_processor.py` — normalize CV output into schema
- [x] `backend/main.py` + `api/routes.py` — `/health`, `/streams`, `/detections`
- [x] `backend/models/database.py` — Postgres models + SQLite local fallback
- [x] `backend/api/websocket.py` — live detection broadcast

**Phase 2**
- [x] Store tracked-object history for LSTM training data
- [x] `backend/models/traffic_prediction.py` — serve prediction model output via API
- [x] Multi-camera routing (`/streams/{camera_id}`)
- [x] `backend/hardware/controller_interface.py` — shared HardwareController interface
- [x] `backend/hardware/mock_controller.py` — simulated Arduino controller
- [x] `backend/hardware/arduino_controller.py` — real pyserial controller
- [x] `backend/hardware/hardware_manager.py` — auto-detect loop, live swap, safe handshake
- [x] `GET /api/hardware/status` endpoint
- [x] Add `hardware_state` field to existing WebSocket broadcast

**Phase 3**
- [ ] API auth (basic token) for demo safety
- [ ] `docs/api_reference.md`

## 🤖 AI/ML Agent
**Phase 1**
- [x] `edge/traffic_analyzer.py` — YOLOv8n inference wrapper, target <100ms/frame
- [x] Vehicle classification: car/bus/truck/bike/pedestrian
- [x] Density estimation function (0–100 scale)
- [x] Confirm density score (0-100) + anomaly flag shape for `hardware_manager.py` consumption

**Phase 2**
- [x] Integrate DeepSORT or ByteTrack for cross-frame tracking
- [x] `notebooks/model_training.ipynb` — train LSTM on stored historical data
- [x] Export trained model for `traffic_prediction.py` to consume
- [x] Report accuracy (target >85%) and latency after each milestone

**Phase 3**
- [ ] Optimize inference for Raspberry Pi / Jetson Nano
- [ ] Basic anomaly/congestion flag logic

## 🔌 Hardware/Embedded Agent
**Phase 1 (Simulation & Protocol Specification)**
- [x] Review and freeze command protocol ('G', 'Y', 'R', 'A', 'C', 'H')
- [x] Cross-check `mock_controller.py` matches real firmware behavior

**Phase 2 (Firmware & Hardware Bench Setup)**
- [x] `hardware/firmware/traffic_controller.ino` — NORMAL + ACCIDENT_OVERRIDE, non-blocking `millis()`, zero `delay()`, 'H'->'OK' handshake
- [x] `hardware/README.md` — pin map, wiring diagram, upload/flashing instructions
- [x] Self-verify non-blocking loop (<100us) & accident preemption

## 🎨 Frontend Agent
**Phase 1**
- [x] `App.jsx` shell + routing
- [x] `CameraFeed.jsx` — live feed + detection overlay
- [x] `services/api.js` — WebSocket + REST client
- [x] `Dashboard.jsx` — live vehicle count display

**Phase 2**
- [x] `PredictionChart.jsx` — 1–6hr forecast visualization (Pure SVG/React, Zero-bloat)
- [x] Multi-camera switcher UI (tabs with live status & density indicators)
- [ ] Congestion heatmap view
- [x] Hardware status badge (`Simulated` / `Connected` / `Offline`) in dashboard header consuming `hardware_state`
- [x] Confirm rest of dashboard renders identically in all three states


**Phase 3**
- [ ] Alert/notification component
- [ ] Export report button (PDF/CSV)
- [ ] Polish pass for demo (loading states, error states on camera disconnect)

## 🐳 DevOps Agent
**Phase 0**
- [x] `docker-compose.yml` stub (Postgres, InfluxDB, Redis, backend, frontend)
- [x] `.env.example`

**Phase 1**
- [x] Backend + frontend Dockerfiles
- [x] Local one-command spin-up verified

**Phase 2**
- [ ] Edge deployment guide for Raspberry Pi 4 / Jetson Nano
- [ ] Resource sizing notes (RAM/CPU per camera node)

**Phase 3**
- [x] `docs/deployment_guide.md`
- [ ] Basic health-check/restart-on-failure for camera streams

## 🎤 Demo/Docs Agent
**Phase 3 (primary, but observes earlier phases)**
- [x] `demo/synthetic_traffic.py` — fallback if live camera fails
- [x] `demo/hackathon_demo.py` — orchestrates the 7-min demo flow
- [x] `demo/mobile_camera.py` — phone-as-CCTV bridge
- [x] Record backup sample videos
- [x] `docs/architecture.md`
- [x] Slide deck outline (problem → solution → architecture → demo → impact → future scope)
- [x] Rehearsal script matching the 7-minute timing in the project doc

## Cross-Agent Definition of Done (per phase)
A phase is not "done" until:
1. All owning agents' checkboxes are checked
2. Orchestrator has run an integration checkpoint
3. The relevant BUILD_ORDER checkpoint (e.g., "live camera → dashboard") actually works end-to-end
