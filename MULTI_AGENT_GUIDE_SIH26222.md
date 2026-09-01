# Multi-Agent Guide — Smart Traffic Monitoring & Prediction System (SIH26222)

Defines the agent roster, scope boundaries, and coordination rules for building this project with multiple specialized agents.

## Agent Roster

### 1. Orchestrator Agent
- Owns BUILD_ORDER and KICKOFF_PROTOCOL
- Assigns tasks to sub-agents in dependency order
- Resolves cross-agent conflicts (e.g., schema disagreements)
- Never writes feature code itself

### 2. Backend Agent
- Owns: `backend/` (FastAPI, routes, websocket, DB models, data_processor)
- Deliverables: REST + WebSocket API, Postgres/InfluxDB schema, camera_manager integration
- Must publish the detection JSON schema before Frontend/AI agents build against it

### 3. AI/ML Agent
- Owns: `edge/traffic_analyzer.py`, `notebooks/`, `backend/models/traffic_prediction.py`
- Deliverables: YOLOv8 detection wrapper, DeepSORT tracking, LSTM prediction model
- Reports detection accuracy & inference latency after each milestone

### 4. Frontend Agent
- Owns: `frontend/`
- Deliverables: Dashboard, live camera feed overlay, prediction charts, alerts UI
- Depends on Backend Agent's WebSocket contract — do not mock indefinitely; integrate as soon as the endpoint is live

### 5. DevOps Agent
- Owns: `docker-compose.yml`, Dockerfiles, edge deployment guide, CI basics
- Deliverables: one-command local spin-up, Raspberry Pi/Jetson deployment steps

### 6. Demo/Docs Agent
- Owns: `demo/`, `docs/`, presentation script
- Deliverables: `hackathon_demo.py`, synthetic fallback data, `architecture.md`, `api_reference.md`, slide outline

### 7. Hardware/Embedded Agent (Actuation Layer)
- Owns: `hardware/` folder exclusively
- Deliverables: `hardware/firmware/traffic_controller.ino` (non-blocking `millis()` state machine, zero `delay()`), `hardware/README.md` (pin map, wiring, flashing instructions)
- Enforces: Command protocol adherence ('G', 'Y', 'R', 'A', 'C', 'H' -> "OK"), ACCIDENT_OVERRIDE preemption, and plug-and-play synchronization with Backend's `MockArduinoController`
- Does not touch `backend/` or `frontend/`

## Coordination Rules
1. **Single source of truth for contracts** — the detection JSON schema and API route list live in one shared doc; any agent changing them must announce it before other agents consume the change.
2. **No silent scope creep** — an agent finding work outside its owned folder flags it to the Orchestrator rather than touching another agent's files.
3. **Status format** — every agent reports status as `DONE / BLOCKED / IN-PROGRESS` + one-line note. Blockers always name the dependency they're waiting on.
4. **Integration checkpoints** — after each BUILD_ORDER phase, all agents pause for an integration check before moving to the next phase.
5. **Demo priority** — if time runs short, the Demo/Docs Agent's needs (a working end-to-end path, even simplified) take priority over any single agent's "advanced feature" work.

## Communication Handoffs
| From → To | What's handed off |
|---|---|
| AI/ML → Backend | Detection JSON schema + sample payloads |
| Backend → Frontend | WebSocket URL, event shape, REST endpoint list |
| Backend → AI/ML | Storage confirmation for historical data (needed for LSTM training) |
| All → DevOps | requirements.txt / package.json / env vars needed in container |
| All → Demo/Docs | What's actually working, so the demo script doesn't promise features that aren't real |

## Escalation
If two agents' outputs conflict (e.g., Frontend expects a field Backend didn't send), the Orchestrator Agent decides the fix and updates the shared schema doc — agents don't unilaterally reinterpret the contract.
