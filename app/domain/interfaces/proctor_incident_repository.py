"""Proctor incident repository interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.entities.proctor_incident import (
    IncidentEvidence,
    IncidentSeverity,
    IncidentType,
    ProctorIncident,
    ReviewAction,
)


class IProctorIncidentRepository(ABC):
    """Interface for proctor incident persistence."""

    @abstractmethod
    async def save(self, incident: ProctorIncident) -> None:
        """Save or update an incident."""
        pass

    @abstractmethod
    async def get_by_id(self, incident_id: UUID) -> Optional[ProctorIncident]:
        """Get incident by ID."""
        pass

    @abstractmethod
    async def get_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorIncident]:
        """Get all incidents for a session."""
        pass

    @abstractmethod
    async def get_by_session_and_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
        limit: int = 100,
    ) -> List[ProctorIncident]:
        """Get incidents by session and severity."""
        pass

    @abstractmethod
    async def get_unreviewed(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> List[ProctorIncident]:
        """Get unreviewed incidents for a session."""
        pass

    @abstractmethod
    async def count_by_session(self, session_id: UUID) -> int:
        """Count incidents for a session."""
        pass

    @abstractmethod
    async def count_by_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
    ) -> int:
        """Count incidents by severity."""
        pass

    @abstractmethod
    async def mark_reviewed(
        self,
        incident_id: UUID,
        reviewer: str,
        action: ReviewAction,
        notes: Optional[str] = None,
    ) -> None:
        """Mark incident as reviewed."""
        pass

    @abstractmethod
    async def add_evidence(
        self,
        incident_id: UUID,
        evidence: IncidentEvidence,
    ) -> None:
        """Add evidence to incident."""
        pass

    @abstractmethod
    async def get_evidence(self, incident_id: UUID) -> List[IncidentEvidence]:
        """Get all evidence for an incident."""
        pass

    @abstractmethod
    async def get_recent_by_type(
        self,
        session_id: UUID,
        incident_type: IncidentType,
        within_seconds: int = 60,
    ) -> List[ProctorIncident]:
        """Get recent incidents of a specific type."""
        pass

    @abstractmethod
    async def delete_by_session(self, session_id: UUID) -> int:
        """Delete all incidents for a session."""
        pass
