# Deployment Guide — Smart Traffic Monitoring & Prediction System (SIH26222)

This guide covers local development, Docker Compose deployment, and edge deployment for low-cost hardware (Raspberry Pi 4 / NVIDIA Jetson Nano).

---

## 1. Local Development (Minimal Setup)

### Prerequisites
- Python 3.10+
- Node.js 18+

### Step-by-Step
```bash
# 1. Clone repository and navigate to root
cd "c:/Users/ksriv/OneDrive/Desktop/SIH FINAL/CODE"

# 2. Configure environment
cp .env.example .env

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Start Backend (in terminal 1)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Start Frontend (in terminal 2)
cd frontend
npm install
npm run dev

# 6. Open dashboard in browser
# http://localhost:5173
```

---

## 2. Docker Compose Deployment

To stand up the complete stack:
```bash
docker-compose up -d
```
Services exposed:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- PostgreSQL: `localhost:5432`

---

## 3. Edge Node Deployment (Raspberry Pi 4 / Jetson Nano)

Target hardware:
- Raspberry Pi 4 (4GB or 8GB RAM)
- MicroSD 32GB (Class 10 / A1)
- 5V 3A USB-C Power Supply

### Step-by-Step Edge Setup
```bash
# 1. Update OS packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-opencv

# 2. Clone repo and install edge dependencies
pip3 install -r requirements.txt --break-system-packages

# 3. Configure local camera stream in edge/config.json
nano edge/config.json

# 4. Run Edge Ingestion Node
python3 edge/traffic_analyzer.py
```
