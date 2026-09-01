"""
API Routes (backend/api/routes.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Exposes REST endpoints for system health, camera streams, historical detections,
and stream ingestion.
"""

from datetime import datetime, timezone
import json
import os
import re
import asyncio
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.models.database import get_db, CameraModel, TrafficObservationModel
from backend.utils.data_processor import (
    TrafficDetectionEvent,
    normalize_detection_payload
)
from backend.api.websocket import ws_manager
from backend.services.video_analyzer_service import video_analyzer_service, UPLOAD_DIR
from backend.hardware.hardware_manager import hardware_manager

router = APIRouter()

# In-memory MJPEG frame buffer: camera_id → latest JPEG bytes
_mjpeg_frames: dict = {}


def push_video_frame(camera_id: str, jpeg_bytes: bytes):
    """Called by the video demo runner to update the latest frame for MJPEG streaming."""
    _mjpeg_frames[camera_id] = jpeg_bytes



@router.get("/health", tags=["System"])
def health_check():
    """System health check and operational status."""
    return {
        "status": "healthy",
        "system": "Smart Traffic Monitoring & Prediction System",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/hardware/status", tags=["Hardware"])
def get_hardware_status():
    """Retrieves physical/simulated Arduino traffic light hardware bridge status."""
    return hardware_manager.get_hardware_status()



@router.get("/streams", tags=["Cameras"])
def list_streams(db: Session = Depends(get_db)):
    """Lists all configured camera streams, syncing from edge/config.json if empty."""
    cameras = db.query(CameraModel).all()
    if not cameras:
        # Seed from edge/config.json if table is empty
        config_path = os.getenv("CONFIG_PATH", "edge/config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                for cam_data in config.get("cameras", []):
                    loc = cam_data.get("location", {})
                    cam = CameraModel(
                        id=cam_data["id"],
                        name=cam_data["name"],
                        stream_url=cam_data["stream_url"],
                        junction_name=loc.get("junction_name"),
                        latitude=loc.get("latitude"),
                        longitude=loc.get("longitude"),
                        enabled=cam_data.get("enabled", True),
                        fps=cam_data.get("fps", 5.0)
                    )
                    db.merge(cam)
                db.commit()
                cameras = db.query(CameraModel).all()
            except Exception as e:
                pass

    return [
        {
            "id": c.id,
            "name": c.name,
            "stream_url": c.stream_url,
            "junction_name": c.junction_name,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "enabled": c.enabled,
            "fps": c.fps
        }
        for c in cameras
    ]


@router.get("/streams/{camera_id}", tags=["Cameras"])
def get_stream(camera_id: str, db: Session = Depends(get_db)):
    """Retrieves metadata and status for a single camera source."""
    cam = db.query(CameraModel).filter(CameraModel.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")
    return {
        "id": cam.id,
        "name": cam.name,
        "stream_url": cam.stream_url,
        "junction_name": cam.junction_name,
        "latitude": cam.latitude,
        "longitude": cam.longitude,
        "enabled": cam.enabled,
        "fps": cam.fps
    }


@router.post("/detections", tags=["Ingestion"])
async def ingest_detection(raw_event: dict, db: Session = Depends(get_db)):
    """
    Ingests normalized detection event from Edge/CV pipeline,
    persists observation to database, and broadcasts to live WebSocket subscribers.
    """
    try:
        normalized = normalize_detection_payload(raw_event)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid detection payload: {e}")

    # Persist observation to relational DB
    obs = TrafficObservationModel(
        camera_id=normalized["camera_id"],
        timestamp=datetime.fromisoformat(normalized["timestamp"].replace("Z", "+00:00")),
        frame_id=normalized["frame_id"],
        vehicle_count=normalized["vehicle_count"],
        cars=normalized["class_counts"]["car"],
        buses=normalized["class_counts"]["bus"],
        trucks=normalized["class_counts"]["truck"],
        bikes=normalized["class_counts"]["bike"],
        pedestrians=normalized["class_counts"]["pedestrian"],
        density=normalized["density"],
        queue_length=normalized["queue_length"],
        processing_time_ms=normalized["processing_time_ms"]
    )
    db.add(obs)
    db.commit()

    # Actuate hardware controller on traffic change
    try:
        density_val = float(normalized.get("density", 0.0))
        is_anomaly = bool(raw_event.get("is_anomaly", False) or raw_event.get("anomaly", False))
        hardware_manager.process_traffic_event(density=density_val, is_anomaly=is_anomaly)
    except Exception:
        pass

    # Broadcast event in real-time to active WebSocket clients
    await ws_manager.broadcast(
        message={"type": "traffic_update", "data": normalized},
        camera_id=normalized["camera_id"]
    )

    return {"status": "success", "recorded_id": obs.id}


@router.post("/streams/{camera_id}/frame", tags=["Video"])
async def push_frame(camera_id: str, body: dict):
    """
    Receives a base64-encoded JPEG frame from the video demo runner.
    Stores it for MJPEG streaming to the browser.
    """
    import base64
    frame_b64 = body.get("frame_jpeg_b64", "")
    if not frame_b64:
        raise HTTPException(status_code=422, detail="Missing frame_jpeg_b64")
    try:
        jpeg_bytes = base64.b64decode(frame_b64)
        _mjpeg_frames[camera_id] = jpeg_bytes
        return {"status": "ok", "bytes": len(jpeg_bytes)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid frame data: {e}")


@router.head("/streams/{camera_id}/mjpeg", tags=["Video"])
async def mjpeg_stream_head(camera_id: str):
    """Probes MJPEG stream readiness without holding open a streaming body."""
    return Response(
        status_code=200,
        headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
    )


@router.get("/streams/{camera_id}/mjpeg", tags=["Video"])
async def mjpeg_stream(camera_id: str):
    """
    MJPEG stream endpoint — returns continuous multipart JPEG stream.
    The browser's <img src="/api/streams/cam_01/mjpeg"> will display live video.
    """
    async def frame_generator():
        boundary = b"--frame\r\n"
        while True:
            jpeg = _mjpeg_frames.get(camera_id)
            if jpeg:
                yield boundary
                yield b"Content-Type: image/jpeg\r\n"
                yield b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                yield jpeg
                yield b"\r\n"
            await asyncio.sleep(0.08)  # ~12 FPS cap for browser rendering

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/detections", tags=["Analytics"])
def get_detections(
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieves recent historical traffic observations."""
    query = db.query(TrafficObservationModel)
    if camera_id:
        query = query.filter(TrafficObservationModel.camera_id == camera_id)

    results = query.order_by(desc(TrafficObservationModel.timestamp)).limit(limit).all()

    return [
        {
            "id": r.id,
            "camera_id": r.camera_id,
            "timestamp": r.timestamp.isoformat(),
            "vehicle_count": r.vehicle_count,
            "cars": r.cars,
            "buses": r.buses,
            "trucks": r.trucks,
            "bikes": r.bikes,
            "pedestrians": r.pedestrians,
            "density": r.density,
            "queue_length": r.queue_length,
            "processing_time_ms": r.processing_time_ms
        }
        for r in results
    ]


@router.get("/predictions/{camera_id}", tags=["Predictions"])
def get_traffic_predictions(
    camera_id: str,
    horizon_hours: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db)
):
    """
    Generates short-term traffic forecasts (1 to 6+ hours) for the specified camera.
    Uses trained TrafficPredictor if available, with intelligent trend projection fallback.
    """
    # Fetch recent historical observations
    history = db.query(TrafficObservationModel)\
        .filter(TrafficObservationModel.camera_id == camera_id)\
        .order_by(desc(TrafficObservationModel.timestamp))\
        .limit(30)\
        .all()

    try:
        from backend.models.traffic_prediction import traffic_predictor
        return traffic_predictor.predict_horizon(camera_id=camera_id, history=history, horizon_hours=horizon_hours)
    except Exception:
        # Resilient heuristic trend generator if ML weights are initializing
        base_density = history[0].density if history else 45.0
        now = datetime.now(timezone.utc)
        forecast = []
        for h in range(1, horizon_hours + 1):
            import math
            future_time = now.timestamp() + (h * 3600)
            # Diurnal sinusoidal variation
            variation = math.sin((future_time / 3600.0) * (math.pi / 12.0)) * 15.0
            pred_density = round(min(100.0, max(5.0, base_density + variation)), 1)
            forecast.append({
                "hour_offset": h,
                "timestamp": datetime.fromtimestamp(future_time, timezone.utc).isoformat(),
                "predicted_density": pred_density,
                "predicted_vehicles": int(pred_density * 0.4),
                "confidence_lower": round(max(0.0, pred_density - 8.0), 1),
                "confidence_upper": round(min(100.0, pred_density + 8.0), 1)
            })

        return {
            "camera_id": camera_id,
            "horizon_hours": horizon_hours,
            "generated_at": now.isoformat(),
            "status": "active",
            "forecast": forecast
        }


# ── Video Upload & Live Analysis Endpoints ─────────────────────────────────────

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@router.post("/upload-video", tags=["Video Analysis"])
@router.post("/video-analysis/upload", tags=["Video Analysis"])
async def upload_video(
    file: UploadFile = File(...),
    target_fps: Optional[float] = Form(None),
    fps_query: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Uploads a video file, validates video format, saves to uploads/,
    registers 'cam_upload' in the database, and begins live YOLOv8 tracking analysis.
    """
    filename = file.filename or "uploaded_video.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
        )

    # Sanitize filename and save to uploads/
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(filename).name)
    save_path = UPLOAD_DIR / clean_name

    try:
        with open(save_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write uploaded video: {e}")

    fps = target_fps if target_fps is not None else (fps_query if fps_query is not None else 10.0)

    # Automatically register/update CameraModel for cam_upload
    cam = CameraModel(
        id="cam_upload",
        name=f"Uploaded: {clean_name}",
        stream_url="/api/streams/cam_upload/mjpeg",
        junction_name="Uploaded Video Analysis",
        latitude=28.6139,
        longitude=77.2090,
        enabled=True,
        fps=fps
    )
    db.merge(cam)
    db.commit()

    loop = asyncio.get_running_loop()
    try:
        res = video_analyzer_service.start_analysis(
            video_path=str(save_path),
            camera_id="cam_upload",
            target_fps=fps,
            loop=loop
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start video analysis: {e}")

    return {
        "status": "started",
        "camera_id": "cam_upload",
        "filename": clean_name,
        "total_frames": res.get("total_frames", 0)
    }


@router.post("/video-analysis/sample", tags=["Video Analysis"])
async def analyze_sample_video(
    target_fps: Optional[float] = Query(None),
    body: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """
    Quick start using existing demo/sample_videos/traffic_sample_01.mp4.
    Registers 'cam_upload' and starts live video analysis engine.
    """
    fps = target_fps
    if fps is None and body and isinstance(body, dict) and "target_fps" in body:
        try:
            fps = float(body["target_fps"])
        except Exception:
            fps = 10.0
    if fps is None:
        fps = 10.0

    sample_path = Path("demo/sample_videos/traffic_sample_01.mp4").resolve()
    if not sample_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Sample video demo/sample_videos/traffic_sample_01.mp4 not found"
        )

    # Register/update CameraModel for cam_upload
    cam = CameraModel(
        id="cam_upload",
        name="Uploaded: traffic_sample_01.mp4",
        stream_url="/api/streams/cam_upload/mjpeg",
        junction_name="Sample Traffic Stream",
        latitude=28.6139,
        longitude=77.2090,
        enabled=True,
        fps=target_fps
    )
    db.merge(cam)
    db.commit()

    loop = asyncio.get_running_loop()
    try:
        video_analyzer_service.start_analysis(
            video_path=str(sample_path),
            camera_id="cam_upload",
            target_fps=target_fps,
            loop=loop
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start sample analysis: {e}")

    return {
        "status": "started",
        "camera_id": "cam_upload",
        "filename": "traffic_sample_01.mp4"
    }


@router.get("/video-analysis/status", tags=["Video Analysis"])
def get_video_analysis_status():
    """Returns current analysis progress and telemetry from video_analyzer_service."""
    return video_analyzer_service.get_status()


@router.post("/video-analysis/stop", tags=["Video Analysis"])
def stop_video_analysis():
    """Stops active video analysis gracefully."""
    video_analyzer_service.stop_analysis()
    return {
        "status": "stopped",
        "progress": video_analyzer_service.get_status()
    }

