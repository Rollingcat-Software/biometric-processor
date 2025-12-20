"""WebSocket connection manager for proctoring sessions."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    websocket: WebSocket
    session_id: UUID
    tenant_id: str
    user_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    frames_sent: int = 0
    is_monitor: bool = False  # True if this is a proctor monitoring the session


class ConnectionManager:
    """Manage WebSocket connections for proctoring sessions.

    Thread-safe manager for handling multiple concurrent WebSocket connections.
    Supports:
    - One primary connection per session (exam-taker)
    - Multiple monitor connections per session (proctors)
    - Broadcast capabilities for incidents
    """

    def __init__(
        self,
        max_connections_per_session: int = 3,
        heartbeat_interval: int = 30,
    ):
        self._connections: Dict[UUID, List[ConnectionInfo]] = {}
        self._monitors: Dict[UUID, Set[WebSocket]] = {}
        self._max_per_session = max_connections_per_session
        self._heartbeat_interval = heartbeat_interval
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        session_id: UUID,
        tenant_id: str,
        user_id: str,
        is_monitor: bool = False,
    ) -> bool:
        """Accept and register a WebSocket connection.

        Args:
            websocket: The WebSocket connection
            session_id: Proctoring session ID
            tenant_id: Tenant identifier
            user_id: User identifier
            is_monitor: True if connection is for monitoring

        Returns:
            True if connection was accepted, False otherwise
        """
        async with self._lock:
            # Check connection limit
            existing = self._connections.get(session_id, [])
            if len(existing) >= self._max_per_session:
                logger.warning(
                    f"Connection limit reached for session {session_id}"
                )
                return False

            # Accept the connection
            await websocket.accept()

            # Create connection info
            conn_info = ConnectionInfo(
                websocket=websocket,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                is_monitor=is_monitor,
            )

            # Register connection
            if session_id not in self._connections:
                self._connections[session_id] = []
            self._connections[session_id].append(conn_info)

            # Track monitors separately
            if is_monitor:
                if session_id not in self._monitors:
                    self._monitors[session_id] = set()
                self._monitors[session_id].add(websocket)

            logger.info(
                f"WebSocket connected: session={session_id}, "
                f"user={user_id}, monitor={is_monitor}"
            )

            return True

    async def disconnect(self, websocket: WebSocket, session_id: UUID) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket to remove
            session_id: Associated session ID
        """
        async with self._lock:
            if session_id in self._connections:
                self._connections[session_id] = [
                    c for c in self._connections[session_id]
                    if c.websocket != websocket
                ]
                if not self._connections[session_id]:
                    del self._connections[session_id]

            if session_id in self._monitors:
                self._monitors[session_id].discard(websocket)
                if not self._monitors[session_id]:
                    del self._monitors[session_id]

            logger.info(f"WebSocket disconnected: session={session_id}")

    async def send_result(
        self,
        session_id: UUID,
        result: dict,
    ) -> None:
        """Send frame analysis result to session connections.

        Args:
            session_id: Target session
            result: Analysis result to send
        """
        message = {
            "type": "result",
            "session_id": str(session_id),
            "payload": result,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }

        await self._send_to_session(session_id, message)

    async def send_incident(
        self,
        session_id: UUID,
        incident: dict,
    ) -> None:
        """Send incident notification to all session connections.

        Args:
            session_id: Target session
            incident: Incident data to send
        """
        message = {
            "type": "incident",
            "session_id": str(session_id),
            "payload": incident,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }

        await self._send_to_session(session_id, message)
        await self._broadcast_to_monitors(session_id, message)

    async def send_warning(
        self,
        session_id: UUID,
        warning_type: str,
        message_text: str,
    ) -> None:
        """Send a warning message to the session.

        Args:
            session_id: Target session
            warning_type: Type of warning
            message_text: Warning message
        """
        message = {
            "type": "warning",
            "session_id": str(session_id),
            "payload": {
                "warning_type": warning_type,
                "message": message_text,
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }

        await self._send_to_session(session_id, message)

    async def send_error(
        self,
        websocket: WebSocket,
        error_code: str,
        error_message: str,
    ) -> None:
        """Send error message to specific connection.

        Args:
            websocket: Target connection
            error_code: Error code
            error_message: Error description
        """
        message = {
            "type": "error",
            "payload": {
                "code": error_code,
                "message": error_message,
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send error: {e}")

    async def broadcast_to_monitors(
        self,
        session_id: UUID,
        message: dict,
    ) -> None:
        """Broadcast message to all monitors watching a session.

        Args:
            session_id: Session being monitored
            message: Message to broadcast
        """
        await self._broadcast_to_monitors(session_id, message)

    async def _send_to_session(
        self,
        session_id: UUID,
        message: dict,
    ) -> None:
        """Send message to all connections for a session."""
        connections = self._connections.get(session_id, [])
        disconnected = []

        for conn_info in connections:
            try:
                await conn_info.websocket.send_json(message)
                conn_info.last_activity = datetime.utcnow()
            except WebSocketDisconnect:
                disconnected.append(conn_info.websocket)
            except Exception as e:
                logger.error(f"Failed to send to session {session_id}: {e}")
                disconnected.append(conn_info.websocket)

        # Clean up disconnected
        for ws in disconnected:
            await self.disconnect(ws, session_id)

    async def _broadcast_to_monitors(
        self,
        session_id: UUID,
        message: dict,
    ) -> None:
        """Broadcast to monitor connections only."""
        monitors = self._monitors.get(session_id, set())
        disconnected = []

        for ws in monitors:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(ws)
            except Exception as e:
                logger.error(f"Failed to broadcast to monitor: {e}")
                disconnected.append(ws)

        # Clean up disconnected monitors
        for ws in disconnected:
            await self.disconnect(ws, session_id)

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())

    def get_session_connection_count(self, session_id: UUID) -> int:
        """Get number of connections for a specific session."""
        return len(self._connections.get(session_id, []))

    def get_active_sessions(self) -> List[UUID]:
        """Get list of sessions with active connections."""
        return list(self._connections.keys())

    def is_session_connected(self, session_id: UUID) -> bool:
        """Check if a session has any active connections."""
        return session_id in self._connections and len(self._connections[session_id]) > 0

    async def update_activity(self, session_id: UUID, websocket: WebSocket) -> None:
        """Update last activity timestamp for a connection."""
        connections = self._connections.get(session_id, [])
        for conn_info in connections:
            if conn_info.websocket == websocket:
                conn_info.last_activity = datetime.utcnow()
                conn_info.frames_sent += 1
                break

    def get_connection_stats(self, session_id: UUID) -> Optional[dict]:
        """Get statistics for a session's connections."""
        connections = self._connections.get(session_id)
        if not connections:
            return None

        return {
            "connection_count": len(connections),
            "monitor_count": len(self._monitors.get(session_id, set())),
            "connections": [
                {
                    "user_id": c.user_id,
                    "is_monitor": c.is_monitor,
                    "connected_at": c.connected_at.isoformat(),
                    "last_activity": c.last_activity.isoformat(),
                    "frames_sent": c.frames_sent,
                }
                for c in connections
            ],
        }
