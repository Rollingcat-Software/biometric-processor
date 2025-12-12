"""WebSocket routes for real-time proctoring."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)

from app.api.websocket.connection_manager import ConnectionManager
from app.api.websocket.frame_handler import WebSocketFrameHandler
from app.api.dependencies.proctor import (
    get_proctor_session_repository,
    get_submit_frame_use_case,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["proctoring-websocket"])

# Singleton connection manager
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the connection manager singleton."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager(
            max_connections_per_session=getattr(
                settings, "PROCTOR_WS_MAX_CONNECTIONS_PER_SESSION", 3
            ),
            heartbeat_interval=getattr(
                settings, "PROCTOR_WS_HEARTBEAT_INTERVAL_SEC", 30
            ),
        )
    return _connection_manager


async def authenticate_websocket(
    websocket: WebSocket,
    token: str,
) -> tuple[str, str]:
    """Authenticate WebSocket connection.

    Args:
        websocket: The WebSocket connection
        token: Authentication token

    Returns:
        Tuple of (tenant_id, user_id)

    Raises:
        WebSocketException if authentication fails
    """
    # For now, simple token validation
    # In production, this would validate JWT or API key
    if not token or len(token) < 10:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    # Extract tenant from query params or token
    tenant_id = websocket.query_params.get("tenant_id", "default")
    user_id = websocket.query_params.get("user_id", "anonymous")

    return tenant_id, user_id


@router.websocket("/proctoring/sessions/{session_id}/stream")
async def websocket_stream(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(..., description="Authentication token"),
    monitor: bool = Query(False, description="Connect as monitor"),
):
    """WebSocket endpoint for real-time frame streaming.

    Connection flow:
    1. Client connects with session_id and auth token
    2. Server validates token and session access
    3. Client sends binary frames or JSON messages
    4. Server responds with analysis results
    5. Server pushes incidents in real-time

    Message Types (Client -> Server):
    - Binary: Raw image bytes (JPEG/PNG)
    - JSON {"type": "ping"}: Heartbeat
    - JSON {"type": "frame", "payload": {"frame_base64": "..."}}: Base64 frame

    Message Types (Server -> Client):
    - {"type": "result", "payload": {...}}: Frame analysis result
    - {"type": "incident", "payload": {...}}: New incident detected
    - {"type": "warning", "payload": {...}}: Warning message
    - {"type": "pong"}: Heartbeat response
    - {"type": "error", "payload": {...}}: Error message
    """
    manager = get_connection_manager()
    repository = get_proctor_session_repository()
    frame_use_case = get_submit_frame_use_case()

    # Authenticate
    try:
        tenant_id, user_id = await authenticate_websocket(websocket, token)
    except WebSocketException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Validate session exists and belongs to tenant
    session = await repository.get_by_id(session_id, tenant_id)
    if not session:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"WebSocket rejected: session {session_id} not found")
        return

    # Check session status
    if session.status.value not in ("active", "flagged"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"WebSocket rejected: session {session_id} not active")
        return

    # Connect
    connected = await manager.connect(
        websocket=websocket,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        is_monitor=monitor,
    )

    if not connected:
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    # Create frame handler
    handler = WebSocketFrameHandler(
        submit_frame_use_case=frame_use_case,
        max_frame_size=getattr(settings, "PROCTOR_WS_MAX_FRAME_SIZE_BYTES", 5_000_000),
    )

    try:
        while True:
            # Receive message (binary or text)
            message = await websocket.receive()

            if "bytes" in message:
                # Binary frame
                try:
                    result = await handler.handle_binary_frame(
                        data=message["bytes"],
                        session_id=session_id,
                        tenant_id=tenant_id,
                    )

                    # Send result
                    await manager.send_result(
                        session_id=session_id,
                        result={
                            "frame_number": result.frame_number,
                            "risk_score": result.risk_score,
                            "face_detected": result.face_detected,
                            "face_matched": result.face_matched,
                            "incidents_created": result.incidents_created,
                            "processing_time_ms": result.processing_time_ms,
                            "analysis": result.analysis,
                            "rate_limit": result.rate_limit,
                        },
                    )

                    # Update activity
                    await manager.update_activity(session_id, websocket)

                except ValueError as e:
                    await manager.send_error(
                        websocket=websocket,
                        error_code="INVALID_FRAME",
                        error_message=str(e),
                    )
                except Exception as e:
                    logger.error(f"Frame processing error: {e}")
                    await manager.send_error(
                        websocket=websocket,
                        error_code="PROCESSING_ERROR",
                        error_message="Failed to process frame",
                    )

            elif "text" in message:
                # JSON message
                import json

                try:
                    data = json.loads(message["text"])
                    response = await handler.handle_json_message(
                        message=data,
                        session_id=session_id,
                        tenant_id=tenant_id,
                    )
                    await websocket.send_json(response)

                except json.JSONDecodeError:
                    await manager.send_error(
                        websocket=websocket,
                        error_code="INVALID_JSON",
                        error_message="Invalid JSON message",
                    )
                except ValueError as e:
                    await manager.send_error(
                        websocket=websocket,
                        error_code="INVALID_MESSAGE",
                        error_message=str(e),
                    )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket, session_id)


@router.get("/proctoring/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_connection_manager()

    return {
        "total_connections": manager.get_connection_count(),
        "active_sessions": len(manager.get_active_sessions()),
        "sessions": [
            {
                "session_id": str(sid),
                "connections": manager.get_session_connection_count(sid),
            }
            for sid in manager.get_active_sessions()
        ],
    }
