"""Start proctor session use case."""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import numpy as np

from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


@dataclass
class StartSessionRequest:
    """Request to start a proctoring session."""

    session_id: UUID
    tenant_id: str
    baseline_image: Optional[np.ndarray] = None  # Optional if user has stored embedding


@dataclass
class StartSessionResponse:
    """Response from starting a session."""

    session_id: str
    status: str
    started_at: str
    has_baseline: bool


class StartProctorSession:
    """Use case for starting a proctoring session."""

    def __init__(
        self,
        session_repository: IProctorSessionRepository,
        embedding_repository: IEmbeddingRepository,
        embedding_extractor=None,
    ) -> None:
        """Initialize use case.

        Args:
            session_repository: Repository for session persistence
            embedding_repository: Repository for embeddings
            embedding_extractor: Service to extract face embeddings
        """
        self._session_repo = session_repository
        self._embedding_repo = embedding_repository
        self._embedding_extractor = embedding_extractor

    async def execute(self, request: StartSessionRequest) -> StartSessionResponse:
        """Execute the use case.

        Args:
            request: Session start request

        Returns:
            Response with started session details

        Raises:
            ValueError: If session not found or cannot be started
        """
        logger.info(f"Starting proctoring session {request.session_id}")

        # Get session
        session = await self._session_repo.get_by_id(
            session_id=request.session_id,
            tenant_id=request.tenant_id,
        )

        if not session:
            raise ValueError(f"Session {request.session_id} not found")

        if not session.can_start():
            raise ValueError(
                f"Session {request.session_id} cannot be started. "
                f"Current status: {session.status.value}"
            )

        # Get baseline embedding
        baseline_embedding = None

        # Try to get existing embedding for user
        existing_embedding = await self._embedding_repo.find_by_user_id(
            user_id=session.user_id,
            tenant_id=session.tenant_id,
        )

        if existing_embedding is not None:
            baseline_embedding = existing_embedding
            logger.info(f"Using existing embedding for user {session.user_id}")
        elif request.baseline_image is not None and self._embedding_extractor:
            # Extract from provided image
            baseline_embedding = await self._embedding_extractor.extract(
                request.baseline_image
            )
            logger.info(f"Extracted new embedding for user {session.user_id}")
        else:
            raise ValueError(
                "No baseline embedding available. Either provide a baseline_image "
                "or ensure user has a stored embedding."
            )

        # Start session
        session.start(baseline_embedding)

        # Save session
        await self._session_repo.save(session)

        logger.info(f"Started proctoring session {session.id}")

        return StartSessionResponse(
            session_id=str(session.id),
            status=session.status.value,
            started_at=session.started_at.isoformat() if session.started_at else "",
            has_baseline=baseline_embedding is not None,
        )
