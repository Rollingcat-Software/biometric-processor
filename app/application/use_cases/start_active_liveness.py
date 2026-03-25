"""Use case for starting an active liveness session."""

import logging
from typing import Optional

from app.api.schemas.active_liveness import (
    ActiveLivenessConfig,
    ActiveLivenessResponse,
)
from app.application.services.active_liveness_manager import ActiveLivenessManager
from app.domain.interfaces.active_liveness_session_repository import IActiveLivenessSessionRepository

logger = logging.getLogger(__name__)


class StartActiveLivenessUseCase:
    """Create and persist a new active liveness session."""

    def __init__(
        self,
        manager: ActiveLivenessManager,
        session_repository: IActiveLivenessSessionRepository,
    ) -> None:
        self._manager = manager
        self._session_repository = session_repository
        logger.info("StartActiveLivenessUseCase initialized")

    async def execute(
        self,
        config: Optional[ActiveLivenessConfig] = None,
    ) -> ActiveLivenessResponse:
        session = self._manager.create_session(config=config)
        await self._session_repository.save(session)
        return self._manager.build_response(session=session)
