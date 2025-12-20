"""WebSocket components for real-time proctoring."""

from app.api.websocket.connection_manager import ConnectionManager
from app.api.websocket.frame_handler import WebSocketFrameHandler

__all__ = ["ConnectionManager", "WebSocketFrameHandler"]
