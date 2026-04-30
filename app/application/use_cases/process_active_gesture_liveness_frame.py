"""Use case for processing a single active gesture liveness frame.

Mirrors :class:`ProcessActiveLivenessFrameUseCase` but accepts a
``GestureFramePayload`` (JSON with client-extracted landmarks + anti-spoof
scores) instead of a raw image path. The server does not run MediaPipe hand
inference.
"""

from __future__ import annotations

import logging
import time

from app.api.schemas.active_liveness import ActiveLivenessResponse
from app.api.schemas.gesture_liveness import GestureFramePayload
from app.application.services.active_gesture_liveness_manager import (
    ActiveGestureLivenessManager,
)
from app.domain.interfaces.active_liveness_session_repository import (
    IActiveLivenessSessionRepository,
)


class ActiveLivenessSessionNotFoundError(Exception):
    """Raised when an active liveness session cannot be found.

    Redeclared here (matches ``process_active_liveness_frame``) to keep the
    gesture use case decoupled from cv2-importing modules.
    """


class ActiveLivenessSessionExpiredError(Exception):
    """Raised when an active liveness session has expired."""


class InvalidModalityError(Exception):
    """Raised when a session's modality does not match the use case.

    Specifically, when the gesture frame endpoint is called with a session
    whose ``modality != "gesture"`` (e.g. a face-modality session opened via
    ``/liveness/active/start``). This is a 400-class error — the session
    exists but the caller is sending it to the wrong endpoint.
    """


logger = logging.getLogger(__name__)


class ProcessActiveGestureLivenessFrameUseCase:
    """Process a single gesture-modality frame for an existing session."""

    def __init__(
        self,
        manager: ActiveGestureLivenessManager,
        session_repository: IActiveLivenessSessionRepository,
    ) -> None:
        self._manager = manager
        self._session_repository = session_repository
        logger.info("ProcessActiveGestureLivenessFrameUseCase initialised")

    async def execute(
        self, session_id: str, payload: GestureFramePayload
    ) -> ActiveLivenessResponse:
        async def handle_session(session):
            current_time = time.time()

            if self._manager.is_expired(session, now=current_time):
                raise ActiveLivenessSessionExpiredError(
                    "Active gesture liveness session has expired"
                )

            # P6.9 #5: explicit modality guard. Previously a face-modality
            # session masqueraded as "not found" (404) here; surface the
            # mismatch as an actionable 400 so callers can correct the
            # endpoint they're hitting.
            if session.modality != "gesture":
                raise InvalidModalityError(
                    f"Session modality is '{session.modality}', expected 'gesture'. "
                    "Use /liveness/active/frame for face-modality sessions."
                )

            if session.is_complete:
                return self._manager.build_response(session=session)

            session.last_activity_at = current_time
            return await self._manager.process_frame(
                session=session, landmarks_payload=payload
            )

        try:
            response = await self._session_repository.mutate(session_id, handle_session)
        except ActiveLivenessSessionExpiredError:
            await self._session_repository.delete(session_id)
            raise

        if response is None:
            raise ActiveLivenessSessionNotFoundError(
                "Active gesture liveness session not found"
            )
        return response


__all__ = [
    "ProcessActiveGestureLivenessFrameUseCase",
    "ActiveLivenessSessionExpiredError",
    "ActiveLivenessSessionNotFoundError",
    "InvalidModalityError",
]
