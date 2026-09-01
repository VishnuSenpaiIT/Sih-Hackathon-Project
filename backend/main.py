"""
FastAPI Application Entry Point (backend/main.py)
Smart Traffic Monitoring & Prediction System (SIH26222)
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from backend.models.database import init_db
from backend.api.routes import router as api_router
from backend.api.websocket import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    yield


app = FastAPI(
    title="Smart Traffic Monitoring & Prediction API",
    description="Software-first, AI-powered traffic intelligence layer for SIH26222",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware configuration
allowed_origins_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API router under /api
app.include_router(api_router, prefix="/api")


# Mount WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, camera_id: str = None):
    await ws_manager.connect(websocket, camera_id)
    try:
        while True:
            # Accept any message type (text or binary) for keep-alive
            # Browser may send ping frames or nothing — just keep the loop alive
            try:
                await websocket.receive()
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket, camera_id)


@app.get("/")
def root():
    return {
        "project": "Smart Traffic Monitoring & Prediction System (SIH26222)",
        "api_docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
