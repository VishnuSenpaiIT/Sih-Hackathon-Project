# Hardware Integration — Laptop "Brain" / Arduino "Hands" (SIH26222)

## 1. Overview

This document adds a physical actuation layer to the Smart Traffic Monitoring & Prediction System: a single Arduino Uno, connected to the existing laptop/server over USB, that turns AI decisions into real-world signal changes (LEDs) and alerts (buzzer).

**Division of labor:**
- **Laptop (Brain):** existing YOLOv8 detection pipeline. No new AI work — it already computes vehicle counts, traffic density, and (per SRD anomaly detection scope) can flag stopped-vehicle/collision-pattern anomalies. This doc adds one new consumer of that output.
- **Arduino Uno (Hands):** listens over serial (USB) for simple status codes and drives LEDs + buzzer accordingly. It does no detection logic itself — it is a dumb, fast actuator.

This is an **additive** layer. The web dashboard, API, and prediction system must continue to work fully with the Arduino disconnected — hardware is an enhancement, not a dependency (see §9).

---

## 2. Where This Fits in the Existing Architecture

Per the SRD's layered architecture, this slots in as a new branch off the **AI Analysis Layer**, running in parallel with the existing **Data Processing & Storage Layer** — it does not replace or block either:

```
AI ANALYSIS LAYER (YOLOv8 detection, density, anomaly flags)
        │
        ├──────────────► DATA PROCESSING & STORAGE LAYER (unchanged)
        │
        └──────────────► HARDWARE BRIDGE (NEW)
                                │
                                │ Serial (USB), single-byte commands
                                ↓
                          ARDUINO UNO
                          (LEDs + Buzzer)
```

The Hardware Bridge reads the same density/anomaly output the Backend Agent's `data_processor.py` already produces — it does not introduce a second source of truth.

---

## 3. Command Protocol (Laptop → Arduino)

Single-byte serial commands, sent only on state *change* (not every frame) to keep the link lightweight:

| Byte | Meaning | Arduino Action |
|---|---|---|
| `G` | Low traffic density | Green LED on, others off |
| `Y` | Medium traffic density | Yellow LED on, others off |
| `R` | Heavy congestion | Red LED on, others off |
| `A` | Accident/anomaly flagged | Enter ACCIDENT_OVERRIDE: flash red + buzzer pattern |
| `C` | Accident flag cleared | Exit override, resume last traffic-density state |
| `H` | Heartbeat / connection check | Arduino echoes `OK` |

Density → letter mapping is computed on the laptop from the same 0–100 density scale already defined in the PRD/SRD (e.g., <33 → `G`, 33–66 → `Y`, >66 → `R`), so no new threshold logic is invented — it reuses the existing density output.

---

## 4. New Backend Module: Hardware Bridge

**Location:** `backend/hardware/arduino_controller.py`

**Responsibilities:**
- Open and hold one serial connection to the Arduino (pyserial), auto-detecting or config-specified port.
- Convert density score + anomaly flag into a command byte per §3.
- Write only on state change — never spam the serial line every frame.
- Non-blocking: serial writes must not stall the FastAPI event loop. Use a short write timeout and a background task/thread, never a blocking call inside a request handler.
- Reconnect logic: if the Arduino disconnects, retry on an interval; never crash the backend or block other endpoints.
- Expose current hardware state (connected/disconnected, last command sent) to the rest of the app.

**New API surface (kept minimal per the lightweight directive):**
- `GET /api/hardware/status` → `{ connected: bool, last_command: str, last_updated: ts }`
- WebSocket: existing detection broadcast gains one additional field, `hardware_state`, rather than a second socket.

---

## 5. Arduino Firmware Spec

**File:** `hardware/firmware/traffic_controller.ino`

**Hard rule (non-negotiable):** no `delay()` anywhere in the sketch. `delay()` blocks the loop and causes missed serial commands during an accident window — the exact failure mode this feature exists to avoid. All timing uses `millis()`-based non-blocking state machines.

**States:**
1. `NORMAL` — one of Green/Yellow/Red solid, per last received `G`/`Y`/`R`.
2. `ACCIDENT_OVERRIDE` — entered on `A`, highest priority, pre-empts `NORMAL` regardless of what traffic-state command arrives next (traffic commands are queued/ignored, not acted on, until `C` clears the override). Red LED flashes on a `millis()` timer; buzzer runs a non-blocking alarm pattern (e.g., on/off cycling via `millis()`, not `delay()`).
3. On `C` — exit override, resume whatever `NORMAL` state was last commanded (or request a fresh one from the laptop).

**Serial loop must, every iteration:**
- Check for incoming serial bytes (non-blocking `Serial.available()`).
- Update LED/buzzer timers based on elapsed `millis()`.
- Never wait — one loop iteration should take microseconds, so the Arduino is always listening.

---

## 6. Dashboard Integration (Frontend)

Add one small, lightweight status component — no new page, no new heavy dependency:

- **Hardware Status indicator** (e.g., a small badge in the existing Dashboard): connected/disconnected, current light color, accident-override banner when active.
- Data source: the `hardware_state` field already riding on the existing WebSocket broadcast (§4) — no second connection, no polling loop.
- If disconnected: badge shows "Hardware offline" and the rest of the dashboard (live feed, density, predictions) is entirely unaffected — this is a visibility widget, not a gate on the UI.

---

## 7. Fallback & Safety Rules

1. The system must run correctly with **no Arduino attached** — detection, storage, prediction, and dashboard all function standalone. Hardware is additive.
2. Serial writes are fire-and-forget from the backend's perspective with a short timeout; a stalled/missing Arduino must never hang a request or the WebSocket broadcast.
3. `delay()` is banned in the firmware, full stop (§5).
4. Accident override always takes priority over routine traffic-state updates on the Arduino side — this must be enforced in firmware state logic, not assumed from send order.
5. Command sends are on-change only, not per-frame, to avoid saturating the serial link and to keep the integration genuinely lightweight.

---

## 8. Updated Project Structure

```
smart-traffic-sih2026/
├── backend/
│   └── hardware/
│       └── arduino_controller.py      # NEW — serial bridge, non-blocking
├── hardware/                          # NEW top-level folder
│   ├── firmware/
│   │   └── traffic_controller.ino     # NEW — Arduino sketch (millis()-based)
│   └── README.md                      # Wiring diagram, pin map, setup steps
```

---

## 9. Where This Sits in BUILD_ORDER

This is an **addition to Phase 2 (Advanced Features, Week 3-4)** — it depends on the density/anomaly output that already exists by the end of Phase 1, and it must not block or be blocked by the LSTM prediction work happening in the same phase.

New Phase 2 line item:
- **2.7 Hardware Bridge + Arduino firmware** — depends on Phase 1 step 3 (`data_processor.py` density output) and Phase 1 step 2 (detection/anomaly signal). Independent of prediction work (2.2–2.4); can run in parallel with it.

---

## 10. Multi-Agent Enforcement (Antigravity 2.0)

**This feature must not be implemented by a single agent end-to-end.** It touches four separate ownership boundaries from `MULTI_AGENT_GUIDE_SIH26222.md`, and must be split across sub-agents accordingly — this is a hard rule for this feature, not a suggestion:

| Agent | Owns | Deliverable for this feature |
|---|---|---|
| **AI/ML Agent** | Density/anomaly signal | Confirms/exposes the density score + anomaly flag `arduino_controller.py` will consume — no new detection logic, just a clean read of existing output |
| **Backend Agent** | `backend/hardware/arduino_controller.py`, API/WebSocket changes | Non-blocking serial bridge, `/api/hardware/status`, `hardware_state` field on the existing broadcast |
| **Hardware/Embedded Agent (NEW ROLE)** | `hardware/firmware/traffic_controller.ino`, `hardware/README.md` | Non-blocking `millis()` firmware implementing the command protocol in §3, wiring documentation |
| **Frontend Agent** | Dashboard hardware badge | Status widget consuming `hardware_state`, per §6 |

### New Agent: Hardware/Embedded Agent
Add to the roster in `MULTI_AGENT_GUIDE_SIH26222.md`:
- **Owns:** `hardware/` folder exclusively.
- **Deliverables:** Arduino firmware, wiring/pin documentation, serial protocol conformance to §3.
- **Reports:** confirms firmware conforms to the non-blocking rule (§5) before marking DONE — this is a required self-check, not optional.
- **Does not** touch `backend/` or `frontend/` — it hands off the finalized serial protocol to the Backend Agent and waits for that contract to be confirmed before finalizing firmware command parsing.

### Coordination Rule for This Feature
The Orchestrator Agent must confirm all four agents above are assigned before this feature is marked "in progress." If only one or two agents are active, the Orchestrator flags this as a scope violation per `MULTI_AGENT_GUIDE_SIH26222.md` §"No silent scope creep" — one agent quietly writing the whole hardware stack (AI signal + backend bridge + firmware + UI) defeats the ownership/contract model the rest of the project relies on, even if it would "work."

---

## 11. Task Checklist (add to SUBAGENT_TASKS_SIH26222.md, Phase 2)

**AI/ML Agent**
- [ ] Confirm density score + anomaly flag are exposed in a stable, documented shape for the Hardware Bridge to consume

**Backend Agent**
- [ ] `backend/hardware/arduino_controller.py` — non-blocking serial bridge, on-change command sends
- [ ] `GET /api/hardware/status`
- [ ] Add `hardware_state` field to existing WebSocket broadcast
- [ ] Reconnect/retry logic; confirm backend never blocks on a missing Arduino

**Hardware/Embedded Agent**
- [ ] `hardware/firmware/traffic_controller.ino` — NORMAL + ACCIDENT_OVERRIDE states, `millis()` only, zero `delay()` calls
- [ ] `hardware/README.md` — pin map, wiring diagram, upload instructions
- [ ] Self-verify: override always pre-empts routine state changes

**Frontend Agent**
- [ ] Hardware status badge on Dashboard (connected/disconnected, current light, override banner)
- [ ] Confirm rest of dashboard renders normally with hardware disconnected

---

## 12. Source Boundary

This document is an addition layered onto the existing `SRD_Smart_Traffic_SIH2026.md` architecture and `BUILD_ORDER_SIH26222.md` Phase 2 — it does not modify the core software pipeline, only adds a consumer of its existing output. The command protocol, non-blocking firmware requirement, and brain/hands division of labor are taken directly from the hardware concept as provided; the API shape, dashboard integration, fallback rules, and multi-agent split are new, derived to keep this feature consistent with the project's existing lightweight and multi-agent build constraints.
