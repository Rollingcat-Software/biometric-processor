"""Proctor session repository interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.domain.entities.proctor_session import ProctorSession, SessionStatus


class IProctorSessionRepository(ABC):
    """Interface for proctor session persistence."""

    @abstractmethod
    async def save(self, session: ProctorSession) -> None:
        """Save or update a proctoring session."""
        pass

    @abstractmethod
    async def get_by_id(self, session_id: UUID, tenant_id: str) -> Optional[ProctorSession]:
        """Get session by ID."""
        pass

    @abstractmethod
    async def get_by_exam_and_user(
        self,
        exam_id: str,
        user_id: str,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by exam and user."""
        pass

    @abstractmethod
    async def get_active_sessions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all active sessions for tenant."""
        pass

    @abstractmethod
    async def get_sessions_by_exam(
        self,
        exam_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for an exam."""
        pass

    @abstractmethod
    async def get_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for a user."""
        pass

    @abstractmethod
    async def get_sessions_by_status(
        self,
        status: SessionStatus,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get sessions by status."""
        pass

    @abstractmethod
    async def count_active_sessions(self, tenant_id: str) -> int:
        """Count active sessions for tenant."""
        pass

    @abstractmethod
    async def count_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        active_only: bool = True,
    ) -> int:
        """Count sessions for a user."""
        pass

    @abstractmethod
    async def update_risk_score(
        self,
        session_id: UUID,
        tenant_id: str,
        risk_score: float,
    ) -> None:
        """Update session risk score."""
        pass

    @abstractmethod
    async def update_status(
        self,
        session_id: UUID,
        tenant_id: str,
        status: SessionStatus,
    ) -> None:
        """Update session status."""
        pass

    @abstractmethod
    async def delete(self, session_id: UUID, tenant_id: str) -> bool:
        """Delete a session (soft delete or hard delete based on implementation)."""
        pass

    @abstractmethod
    async def get_expired_sessions(
        self,
        before: datetime,
        limit: int = 100,
    ) -> List[ProctorSession]:
        """Get sessions that have expired."""
        pass
