"""Create proctor session use case."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.domain.entities.proctor_session import ProctorSession, SessionConfig
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


@dataclass
class CreateSessionRequest:
    """Request to create a proctoring session."""

    exam_id: str
    user_id: str
    tenant_id: str
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CreateSessionResponse:
    """Response from creating a session."""

    session_id: str
    exam_id: str
    user_id: str
    status: str
    config: Dict[str, Any]


class CreateProctorSession:
    """Use case for creating a new proctoring session."""

    def __init__(
        self,
        session_repository: IProctorSessionRepository,
        max_sessions_per_user: int = 1,
    ) -> None:
        """Initialize use case.

        Args:
            session_repository: Repository for session persistence
            max_sessions_per_user: Maximum concurrent sessions per user
        """
        self._repository = session_repository
        self._max_sessions_per_user = max_sessions_per_user

    async def execute(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """Execute the use case.

        Args:
            request: Session creation request

        Returns:
            Response with created session details

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            f"Creating proctoring session for exam={request.exam_id}, user={request.user_id}"
        )

        # Check for existing active sessions
        active_count = await self._repository.count_sessions_by_user(
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            active_only=True,
        )

        if active_count >= self._max_sessions_per_user:
            raise ValueError(
                f"User {request.user_id} already has {active_count} active sessions. "
                f"Maximum allowed: {self._max_sessions_per_user}"
            )

        # Check for existing session for same exam
        existing = await self._repository.get_by_exam_and_user(
            exam_id=request.exam_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )

        if existing and not existing.is_terminal():
            raise ValueError(
                f"Session already exists for exam {request.exam_id} "
                f"and user {request.user_id} with status: {existing.status.value}"
            )

        # Parse config
        config = SessionConfig()
        if request.config:
            config = SessionConfig.from_dict(request.config)

        # Create session
        session = ProctorSession.create(
            exam_id=request.exam_id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            config=config,
            metadata=request.metadata,
        )

        # Save session
        await self._repository.save(session)

        logger.info(f"Created proctoring session {session.id}")

        return CreateSessionResponse(
            session_id=str(session.id),
            exam_id=session.exam_id,
            user_id=session.user_id,
            status=session.status.value,
            config=session.config.to_dict(),
        )
