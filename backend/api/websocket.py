"""
WebSocket Broadcast Subsystem (backend/api/websocket.py)
Smart Traffic Monitoring & Prediction System (SIH26222)

Handles real-time push events to dashboard clients for live detection, density, and alert metrics.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("WebSocketManager")


class ConnectionManager:
    """Manages active WebSocket subscriptions by camera_id."""

    def __init__(self):
        # camera_id -> list of active websockets. "all" represents global subscribers.
        self.active_connections: Dict[str, List[WebSocket]] = {"all": []}

    async def connect(self, websocket: WebSocket, camera_id: Optional[str] = None):
        await websocket.accept()
        cam_key = camera_id if camera_id else "all"
        if cam_key not in self.active_connections:
            self.active_connections[cam_key] = []
        self.active_connections[cam_key].append(websocket)
        logger.info(f"Client connected to stream channel: {cam_key} (Total: {len(self.active_connections[cam_key])})")

    def disconnect(self, websocket: WebSocket, camera_id: Optional[str] = None):
        cam_key = camera_id if camera_id else "all"
        if cam_key in self.active_connections and websocket in self.active_connections[cam_key]:
            self.active_connections[cam_key].remove(websocket)
            logger.info(f"Client disconnected from channel: {cam_key}")

    async def broadcast(self, message: Dict[str, Any], camera_id: Optional[str] = None):
        """Broadcasts event payload to matching subscribers and global listeners."""
        payload_str = json.dumps(message)
        targets = list(self.active_connections.get("all", []))
        if camera_id and camera_id in self.active_connections:
            targets.extend([ws for ws in self.active_connections[camera_id] if ws not in targets])

        dead_connections = []
        for connection in targets:
            try:
                await connection.send_text(payload_str)
            except Exception as e:
                logger.warning(f"Error sending message to client: {e}")
                dead_connections.append(connection)

        # Cleanup failed connections
        for dead in dead_connections:
            for key in self.active_connections:
                if dead in self.active_connections[key]:
                    self.active_connections[key].remove(dead)


ws_manager = ConnectionManager()
