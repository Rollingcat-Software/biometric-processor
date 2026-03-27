"""Use case for processing active liveness frames."""

import logging
import time

import cv2

from app.api.schemas.active_liveness import ActiveLivenessResponse
from app.application.services.active_liveness_manager import ActiveLivenessManager
from app.domain.interfaces.active_liveness_session_repository import IActiveLivenessSessionRepository

logger = logging.getLogger(__name__)


class ActiveLivenessSessionNotFoundError(Exception):
    """Raised when an active liveness session cannot be found."""


class ActiveLivenessSessionExpiredError(Exception):
    """Raised when an active liveness session has expired."""


class ProcessActiveLivenessFrameUseCase:
    """Process a frame for an existing active liveness session."""

    def __init__(
        self,
        manager: ActiveLivenessManager,
        session_repository: IActiveLivenessSessionRepository,
    ) -> None:
        self._manager = manager
        self._session_repository = session_repository
        logger.info("ProcessActiveLivenessFrameUseCase initialized")

    async def execute(self, session_id: str, image_path: str) -> ActiveLivenessResponse:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Failed to load the uploaded image")

        async def handle_session(session):
            current_time = time.time()

            if self._manager.is_expired(session, now=current_time):
                raise ActiveLivenessSessionExpiredError("Active liveness session has expired")

            if session.is_complete:
                return self._manager.build_response(session=session)

            session.last_activity_at = current_time
            return await self._manager.process_frame(session=session, image=image)

        try:
            response = await self._session_repository.mutate(session_id, handle_session)
        except ActiveLivenessSessionExpiredError:
            await self._session_repository.delete(session_id)
            raise
        if response is None:
            raise ActiveLivenessSessionNotFoundError("Active liveness session not found")

        return response
