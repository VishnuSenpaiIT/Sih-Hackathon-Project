# Sih-Hackathon-Project

## Smart Traffic Monitoring & Prediction System (SIH26222)

> Software-first, AI-powered urban traffic monitoring and prediction using existing CCTV infrastructure.

## Project Overview
- **Problem Statement ID:** SIH26222 (Transportation & Logistics / Smart Cities)
- **Organization:** AICTE Student Innovation
- **Core Principle:** Software-first, existing CCTV infrastructure, minimal additional hardware (~₹5,600 per edge node).
- **Primary AI/ML Stack:** YOLOv8n object detection (1–5 FPS, <100ms/frame), DeepSORT tracking, LSTM short-term forecasting.

## Architecture
```text
Existing CCTV (RTSP/ONVIF/Mobile)
       ↓
Edge Ingestion (OpenCV / Frame extraction at 1-5 FPS)
       ↓
AI Detection Layer (YOLOv8n: Car, Bus, Truck, Bike, Pedestrian)
       ↓
Data Processor (Density 0-100 scale, structured JSON contract)
       ↓
Storage & Analytics (PostgreSQL, optional InfluxDB / TimescaleDB)
       ↓
FastAPI Backend (REST API + WebSockets push updates)
       ↓
React + Vite Dashboard (Live feed, overlays, analytics, prediction charts)
```

## Repository Structure
```text
├── backend/            # FastAPI application, REST & WebSocket endpoints, DB models
├── edge/               # RTSP capture and edge AI inference pipelines
├── frontend/           # React + Vite lean dashboard
├── demo/               # Hackathon demo runner, mobile camera bridge, synthetic traffic
├── notebooks/          # Exploratory analysis and model training
├── docs/               # Architecture, API specifications, and JSON schemas
├── docker-compose.yml  # Containerized deployment
└── requirements.txt    # Python dependencies
```

## Quick Start (Local Development)

### 1. Backend Setup
```bash
# Optional virtualenv
python -m venv venv
# Windows: venv\Scripts\activate  |  Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 3. Edge / Ingestion Pipeline
```bash
python edge/traffic_analyzer.py
```
