"""End proctor session use case."""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.domain.entities.proctor_session import SessionStatus, TerminationReason
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


@dataclass
class EndSessionRequest:
    """Request to end a proctoring session."""

    session_id: UUID
    tenant_id: str
    reason: Optional[str] = None  # "normal", "user", "proctor", or termination reason


@dataclass
class EndSessionResponse:
    """Response from ending a session."""

    session_id: str
    status: str
    ended_at: str
    duration_seconds: float
    termination_reason: Optional[str]
    final_risk_score: float
    total_incidents: int


class EndProctorSession:
    """Use case for ending a proctoring session."""

    def __init__(
        self,
        session_repository: IProctorSessionRepository,
    ) -> None:
        """Initialize use case."""
        self._repository = session_repository

    async def execute(self, request: EndSessionRequest) -> EndSessionResponse:
        """Execute the use case.

        Args:
            request: Session end request

        Returns:
            Response with final session details

        Raises:
            ValueError: If session not found or cannot be ended
        """
        logger.info(f"Ending proctoring session {request.session_id}")

        # Get session
        session = await self._repository.get_by_id(
            session_id=request.session_id,
            tenant_id=request.tenant_id,
        )

        if not session:
            raise ValueError(f"Session {request.session_id} not found")

        if session.is_terminal():
            raise ValueError(
                f"Session {request.session_id} is already ended. "
                f"Status: {session.status.value}"
            )

        # Determine termination type
        if request.reason:
            reason_map = {
                "normal": TerminationReason.NORMAL_COMPLETION,
                "user": TerminationReason.USER_ENDED,
                "proctor": TerminationReason.PROCTOR_ENDED,
                "identity_failure": TerminationReason.IDENTITY_FAILURE,
                "multiple_persons": TerminationReason.MULTIPLE_PERSONS,
                "critical_violation": TerminationReason.CRITICAL_VIOLATION,
                "deepfake": TerminationReason.DEEPFAKE_DETECTED,
                "technical": TerminationReason.TECHNICAL_FAILURE,
                "timeout": TerminationReason.TIMEOUT,
            }
            termination_reason = reason_map.get(
                request.reason.lower(),
                TerminationReason.NORMAL_COMPLETION,
            )

            if termination_reason == TerminationReason.NORMAL_COMPLETION:
                session.complete()
            else:
                session.terminate(termination_reason)
        else:
            session.complete()

        # Save session
        await self._repository.save(session)

        logger.info(
            f"Ended proctoring session {session.id} with status {session.status.value}"
        )

        return EndSessionResponse(
            session_id=str(session.id),
            status=session.status.value,
            ended_at=session.ended_at.isoformat() if session.ended_at else "",
            duration_seconds=session.get_duration_seconds(),
            termination_reason=(
                session.termination_reason.value if session.termination_reason else None
            ),
            final_risk_score=session.risk_score,
            total_incidents=session.incident_count,
        )


class PauseProctorSession:
    """Use case for pausing a proctoring session."""

    def __init__(self, session_repository: IProctorSessionRepository) -> None:
        self._repository = session_repository

    async def execute(self, session_id: UUID, tenant_id: str) -> dict:
        """Pause a session."""
        session = await self._repository.get_by_id(session_id, tenant_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.pause()
        await self._repository.save(session)

        return {
            "session_id": str(session.id),
            "status": session.status.value,
            "paused_at": session.paused_at.isoformat() if session.paused_at else None,
        }


class ResumeProctorSession:
    """Use case for resuming a proctoring session."""

    def __init__(self, session_repository: IProctorSessionRepository) -> None:
        self._repository = session_repository

    async def execute(self, session_id: UUID, tenant_id: str) -> dict:
        """Resume a session."""
        session = await self._repository.get_by_id(session_id, tenant_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.resume()
        await self._repository.save(session)

        return {
            "session_id": str(session.id),
            "status": session.status.value,
        }
