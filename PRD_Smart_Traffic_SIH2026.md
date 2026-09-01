# PRD — Smart Traffic Monitoring & Prediction System

## 1. Document Information

| Field | Specification |
|---|---|
| Product | Smart Traffic Monitoring & Prediction System |
| Problem Statement | SIH26222 (or related Transportation & Logistics PS) |
| Organization | AICTE Student Innovation |
| Theme | Transportation & Logistics / Smart Cities |
| Category | Hardware (Software-First Implementation) |
| Deadline | 20 September 2026 |
| Status | Development Phase 1 |
| Last Updated | September 1, 2026 |
| Companion Docs | `SRD_Smart_Traffic_SIH2026.md` (technical spec), `ANTIGRAVITY_RULES_SIH2026.md` (agent constraints) |

---

## 2. Purpose of This Document

This PRD defines **what** the product must do and **why**, for whom, and how success is measured. It is the product-level authority referenced by `ANTIGRAVITY_RULES_SIH2026.md`. The `SRD` defines **how** the system is technically built; this PRD should not be read as a substitute for it, and the SRD should not be read as a substitute for this.

Where this document and the SRD appear to conflict, the PRD governs product scope and priorities; the SRD governs technical implementation detail.

---

## 3. Problem Statement

> "Submit your ideas to address the growing pressures on the city's resources, transport networks, and logistic infrastructure."

### 3.1 Core Problem
Indian cities face:
- Increasing traffic congestion in urban areas.
- Inefficient use of existing CCTV infrastructure — cameras exist but produce no actionable analytics.
- Lack of real-time traffic data for planning or response.
- High cost of deploying new dedicated hardware sensors for traffic sensing.
- No intelligent, data-driven traffic management at most junctions.

### 3.2 Why Now
CCTV coverage at junctions is already widespread across most Indian cities, but that footage is watched, not analyzed. Commodity computer vision (YOLOv8-class detectors) has become accurate and cheap enough to run on low-cost edge hardware, closing the gap between "camera exists" and "camera is useful."

---

## 4. Product Vision

Turn a city's existing CCTV network into a live traffic-intelligence layer — without asking the city to buy new sensors — by adding a thin software + minimal-edge-hardware layer that watches, understands, and predicts traffic.

**Product principle (locked):** software-first, existing CCTV, minimal additional hardware. This principle is authoritative per `ANTIGRAVITY_RULES_SIH2026.md` §3 and should not be silently reinterpreted.

---

## 5. Target Users & Stakeholders

| User / Stakeholder | Need |
|---|---|
| Municipal traffic authorities | Real-time visibility into congestion; historical data for planning |
| Traffic police / control room operators | Live alerts on congestion/anomalies at monitored junctions |
| City planners | Historical + predictive traffic data to justify infrastructure decisions |
| SIH evaluators (immediate audience) | A working, demoable, technically credible solution within hackathon constraints |
| Future: emergency services | Green-corridor / priority routing input (future scope, not core) |

---

## 6. Goals & Success Metrics

### 6.1 Product Goals
1. Detect and classify vehicles from live camera/video input in real time.
2. Convert raw detections into a traffic-density measurement city staff can act on.
3. Predict near-term traffic conditions (short-horizon forecasting).
4. Present all of the above through a live, understandable dashboard.
5. Do all of this at a fraction of the cost of dedicated sensor hardware.

### 6.2 Success Metrics
| Metric | Target |
|---|---|
| Vehicle detection accuracy | > 85% |
| End-to-end latency (camera → dashboard) | < 2 seconds |
| AI processing time per frame | ~100 ms where hardware permits |
| Camera scalability | Architecture supports 100+ cameras |
| Deployment cost per junction (edge node) | ~₹5,600, vs ₹50,000+ for new CCTV / ₹1,00,000+ for IoT sensor networks |
| Prediction horizon (hackathon) | ~1 hour |
| Prediction horizon (product target) | 1–6 hours |
| Congestion reduction (aspirational, post-deployment) | 15–20% |

### 6.3 Demo-Level Success Criteria
The hackathon demo is considered successful if it shows, live, using a mobile phone as a stand-in CCTV feed:
- Real-time vehicle detection and counting.
- A traffic density readout.
- A short-term traffic forecast.
- The system architecture, explained clearly, in a 5–7 minute window.

---

## 7. Scope

### 7.1 In Scope (Core Product)
- Video ingestion from existing/CCTV-style camera sources (RTSP/ONVIF), including a mobile-camera path for demo purposes.
- Vehicle detection and classification (car, bus, truck, bike, pedestrian).
- Vehicle tracking across frames.
- Traffic density estimation (0–100 scale).
- Structured storage of traffic observations, historical and time-series.
- Short-term traffic prediction (1–6 hour horizon).
- Real-time web dashboard: live feed, detection overlay, density, historical charts, predictions, alerts, multi-camera selection.
- Multi-camera, configuration-driven scaling.
- Low-cost edge deployment path (Raspberry Pi 4 / Jetson Nano).
- Basic congestion/anomaly alerting.

### 7.2 Out of Scope for Core Product (Future Extensions)
Per `ANTIGRAVITY_RULES_SIH2026.md` §34, these are future capabilities and must not be treated as mandatory core functionality unless explicitly requested:
- Adaptive traffic signal control.
- Emergency vehicle priority / green corridors.
- Parking-space detection.
- Public transport arrival tracking.
- Air-quality correlation with traffic.
- Automated accident detection.
- License-plate recognition (requires privacy safeguards if ever implemented).
- Reckless-driving / behavioral analysis.
- Multi-modal transport integration.

### 7.3 Explicit Non-Goals
- This product does not aim to replace human traffic policing or control-room judgment — it augments it with data.
- This product does not collect or aim to collect personally identifying information as part of its core function (see Privacy, §11).
- This product does not require cities to purchase new camera hardware to obtain value.

---

## 8. Key Features (Product-Level)

### 8.1 Real-Time Analytics
- Vehicle detection by class (car, bus, truck, bike, pedestrian).
- Traffic density estimation (0–100 scale).
- Queue length detection.
- Optional speed estimation.

### 8.2 Predictive Capabilities
- Short-term prediction (1–6 hours ahead).
- Daily/weekly pattern recognition for longer-term trend context.
- Congestion forecasting.
- Resource-optimization suggestions (analytical output, not automated control).

### 8.3 Dashboard
- Live camera feed with detection overlay.
- Historical data charts.
- Prediction visualizations.
- Alerts/notifications for congestion or anomalies.
- Multi-camera switching.
- Report export (PDF, CSV).

---

## 9. User Stories

| As a... | I want to... | So that... |
|---|---|---|
| Control room operator | See live vehicle counts and density per junction | I can identify congestion as it happens |
| Traffic planner | View historical traffic trends per location | I can justify signal-timing or infrastructure changes |
| Control room operator | Receive an alert when congestion crosses a threshold | I can respond before it worsens |
| City official | See a 1–6 hour traffic forecast | I can pre-position resources or adjust signal timing proactively |
| Hackathon evaluator | See the full pipeline work live from a phone camera | I can trust the system works beyond slides |
| DevOps/deployment team | Add a new camera via configuration, not code changes | The system scales without redevelopment |

---

## 10. Constraints & Assumptions

### 10.1 Constraints
- Hackathon deadline: 20 September 2026 — the demo-ready subset must be prioritized over full product completeness.
- Must work using only existing/commodity hardware for demo purposes (laptop, mobile phone, internet).
- Deployment cost per node should stay near the ₹5,600 reference target; expensive infrastructure should not be introduced without clear technical justification (per `ANTIGRAVITY_RULES_SIH2026.md` §35).
- Technology stack is locked per `ANTIGRAVITY_RULES_SIH2026.md` §4 (FastAPI/Python backend, React/Next.js frontend, YOLOv8-based detection) — changes require explicit approval, not ad hoc substitution.

### 10.2 Assumptions
- Cities generally already operate CCTV at traffic junctions with RTSP/ONVIF-compatible or comparable output.
- Network connectivity between camera sites and processing (edge or cloud) is available, if intermittently.
- A single low-cost edge device (Raspberry Pi 4 / Jetson Nano) is a reasonable unit of deployment per junction.
- Initial detection accuracy target (>85%) is achievable with YOLOv8n on typical traffic footage without custom retraining, though retraining remains an option if needed.

---

## 11. Non-Functional Requirements (Product-Level Summary)

Full technical detail lives in the SRD; product-level expectations are:

| Category | Expectation |
|---|---|
| Performance | Near real-time (<2s end-to-end); system should feel "live," not batch |
| Scalability | Adding a camera should be a config change, not a redeploy |
| Reliability | A single camera going offline must not take down monitoring for other cameras |
| Security | No hard-coded credentials anywhere; RTSP/API secrets externalized |
| Privacy | No unnecessary personal-data collection; any future license-plate work requires privacy safeguards |
| Cost | Stay close to the ₹5,600/node reference; avoid unjustified infrastructure spend |
| Demo integrity | Simulated/synthetic data must be clearly isolated from and never presented as live production behavior |

---

## 12. Milestones (Product View)

Aligned with `BUILD_ORDER_SIH26222.md`; this table gives the product-facing framing of the same phases.

| Phase | Window | Product Outcome |
|---|---|---|
| Phase 1 — Core Development | Week 1–2 | Live camera → detection → basic dashboard, working end-to-end |
| Phase 2 — Advanced Features | Week 3–4 | Tracking, 1-hour prediction, multi-camera dashboard, edge deployment guide |
| Phase 3 — Hackathon Demo Prep | Week 5 | Polished 5–7 min demo, slide deck, demo video, documented repository |
| Phase 4 — Post-Hackathon (future) | Beyond deadline | Future extensions per §7.2, as separately scoped and approved |

---

## 13. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Live camera/network fails during demo | High — demo credibility | Backup sample videos + synthetic traffic fallback (per SRD §27, ANTIGRAVITY_RULES §27) |
| Detection accuracy below target on real-world footage | Medium | Use YOLOv8n baseline first; keep model swappable (ANTIGRAVITY_RULES §28) |
| Prediction model needs more historical data than available by demo time | Medium | Scope hackathon prediction target down to ~1 hour; use synthetic/historical seed data if needed |
| Scope creep into future features (§7.2) | Medium | Explicit non-goals section + ANTIGRAVITY_RULES §34 enforcement |
| Team runs out of time before full multi-camera support | Low–Medium | BUILD_ORDER prioritizes single-camera end-to-end pipeline first; multi-camera is Phase 2 |

---

## 14. Open Questions

- Final confirmation of the exact SIH problem-statement ID (currently recorded as SIH26222 or a related Transportation & Logistics PS — to be confirmed against the official SIH portal listing).
- Target city/junction for any real-world pilot footage, if used instead of purely synthetic/mobile demo data.
- Whether resource-optimization suggestions (§8.2) are presented as read-only recommendations only, or eventually feed into any control system (currently: read-only, no automated control, per non-goals).

---

## 15. Source Boundary

This PRD is derived from the supplied Smart Traffic Monitoring & Prediction System project specification (`SIH2026_Smart_Traffic_Project.md`) and is structured to sit alongside `SRD_Smart_Traffic_SIH2026.md` as the pair of documents referenced by `ANTIGRAVITY_RULES_SIH2026.md` §2. Where the source material presented options (e.g., InfluxDB or TimescaleDB, Redis or Kafka), this document defers to the SRD for the preserved alternatives and does not mandate one over the other.
