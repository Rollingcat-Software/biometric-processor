"""Use case for starting an active gesture liveness session.

Mirrors :class:`StartActiveLivenessUseCase` but binds the gesture manager.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.api.schemas.active_liveness import ActiveLivenessResponse
from app.api.schemas.gesture_liveness import GestureLivenessConfig
from app.application.services.active_gesture_liveness_manager import (
    ActiveGestureLivenessManager,
)
from app.domain.interfaces.active_liveness_session_repository import (
    IActiveLivenessSessionRepository,
)

logger = logging.getLogger(__name__)


class StartActiveGestureLivenessUseCase:
    """Create and persist a new active gesture liveness session."""

    def __init__(
        self,
        manager: ActiveGestureLivenessManager,
        session_repository: IActiveLivenessSessionRepository,
    ) -> None:
        self._manager = manager
        self._session_repository = session_repository
        logger.info("StartActiveGestureLivenessUseCase initialised")

    async def execute(
        self, config: Optional[GestureLivenessConfig] = None
    ) -> ActiveLivenessResponse:
        session = self._manager.create_session(config=config)
        await self._session_repository.save(session)
        return self._manager.build_response(session=session)


__all__ = ["StartActiveGestureLivenessUseCase"]
