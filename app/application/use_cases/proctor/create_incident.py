"""Create incident use case."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from app.domain.entities.proctor_incident import (
    IncidentSeverity,
    IncidentType,
    ProctorIncident,
    ReviewAction,
)
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


@dataclass
class CreateIncidentRequest:
    """Request to create an incident."""

    session_id: UUID
    tenant_id: str
    incident_type: str
    confidence: float
    severity: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class CreateIncidentResponse:
    """Response from creating an incident."""

    incident_id: str
    session_id: str
    incident_type: str
    severity: str
    confidence: float
    risk_contribution: float


class CreateIncident:
    """Use case for manually creating an incident."""

    def __init__(
        self,
        incident_repository: IProctorIncidentRepository,
        session_repository: IProctorSessionRepository,
    ) -> None:
        """Initialize use case."""
        self._incident_repo = incident_repository
        self._session_repo = session_repository

    async def execute(self, request: CreateIncidentRequest) -> CreateIncidentResponse:
        """Execute the use case."""
        logger.info(
            f"Creating incident for session {request.session_id}: {request.incident_type}"
        )

        # Validate session exists
        session = await self._session_repo.get_by_id(
            request.session_id, request.tenant_id
        )
        if not session:
            raise ValueError(f"Session {request.session_id} not found")

        # Parse incident type
        try:
            incident_type = IncidentType(request.incident_type)
        except ValueError:
            raise ValueError(f"Invalid incident type: {request.incident_type}")

        # Parse severity
        severity = None
        if request.severity:
            try:
                severity = IncidentSeverity(request.severity)
            except ValueError:
                raise ValueError(f"Invalid severity: {request.severity}")

        # Create incident
        incident = ProctorIncident.create(
            session_id=request.session_id,
            incident_type=incident_type,
            confidence=request.confidence,
            severity=severity,
            details=request.details,
        )

        # Save incident
        await self._incident_repo.save(incident)

        # Update session incident count
        session.record_incident()
        await self._session_repo.save(session)

        logger.info(f"Created incident {incident.id}")

        return CreateIncidentResponse(
            incident_id=str(incident.id),
            session_id=str(incident.session_id),
            incident_type=incident.incident_type.value,
            severity=incident.severity.value,
            confidence=incident.confidence,
            risk_contribution=incident.get_risk_contribution(),
        )


@dataclass
class ReviewIncidentRequest:
    """Request to review an incident."""

    incident_id: UUID
    reviewer: str
    action: str
    notes: Optional[str] = None


class ReviewIncident:
    """Use case for reviewing an incident."""

    def __init__(self, incident_repository: IProctorIncidentRepository) -> None:
        self._repository = incident_repository

    async def execute(self, request: ReviewIncidentRequest) -> dict:
        """Review an incident."""
        incident = await self._repository.get_by_id(request.incident_id)
        if not incident:
            raise ValueError(f"Incident {request.incident_id} not found")

        if incident.reviewed:
            raise ValueError(f"Incident {request.incident_id} already reviewed")

        try:
            action = ReviewAction(request.action)
        except ValueError:
            raise ValueError(f"Invalid review action: {request.action}")

        await self._repository.mark_reviewed(
            incident_id=request.incident_id,
            reviewer=request.reviewer,
            action=action,
            notes=request.notes,
        )

        return {
            "incident_id": str(request.incident_id),
            "reviewed": True,
            "reviewer": request.reviewer,
            "action": action.value,
        }
