"""Get session report use case."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import UUID

from app.domain.entities.proctor_incident import IncidentSeverity
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


@dataclass
class SessionReport:
    """Comprehensive session report."""

    session_id: str
    exam_id: str
    user_id: str
    status: str
    duration_seconds: float
    risk_score: float
    verification_count: int
    verification_failures: int
    verification_success_rate: float
    total_incidents: int
    incidents_by_severity: Dict[str, int]
    critical_incidents: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    summary: str


class GetSessionReport:
    """Use case for generating a comprehensive session report."""

    def __init__(
        self,
        session_repository: IProctorSessionRepository,
        incident_repository: IProctorIncidentRepository,
    ) -> None:
        """Initialize use case."""
        self._session_repo = session_repository
        self._incident_repo = incident_repository

    async def execute(self, session_id: UUID, tenant_id: str) -> SessionReport:
        """Generate session report."""
        logger.info(f"Generating report for session {session_id}")

        # Get session
        session = await self._session_repo.get_by_id(session_id, tenant_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get all incidents
        incidents = await self._incident_repo.get_by_session(session_id, limit=1000)

        # Count by severity
        severity_counts = {s.value: 0 for s in IncidentSeverity}
        for incident in incidents:
            severity_counts[incident.severity.value] += 1

        # Get critical incidents
        critical_incidents = [
            incident.to_dict()
            for incident in incidents
            if incident.severity == IncidentSeverity.CRITICAL
        ]

        # Build timeline
        timeline = []
        if session.started_at:
            timeline.append({
                "timestamp": session.started_at.isoformat(),
                "event": "session_started",
            })

        for incident in sorted(incidents, key=lambda x: x.timestamp):
            timeline.append({
                "timestamp": incident.timestamp.isoformat(),
                "event": "incident",
                "type": incident.incident_type.value,
                "severity": incident.severity.value,
            })

        if session.ended_at:
            timeline.append({
                "timestamp": session.ended_at.isoformat(),
                "event": "session_ended",
                "reason": session.termination_reason.value if session.termination_reason else None,
            })

        # Generate summary
        summary = self._generate_summary(session, incidents, severity_counts)

        return SessionReport(
            session_id=str(session.id),
            exam_id=session.exam_id,
            user_id=session.user_id,
            status=session.status.value,
            duration_seconds=session.get_duration_seconds(),
            risk_score=session.risk_score,
            verification_count=session.verification_count,
            verification_failures=session.verification_failures,
            verification_success_rate=session.get_verification_success_rate(),
            total_incidents=len(incidents),
            incidents_by_severity=severity_counts,
            critical_incidents=critical_incidents,
            timeline=timeline,
            summary=summary,
        )

    def _generate_summary(
        self,
        session,
        incidents,
        severity_counts: Dict[str, int],
    ) -> str:
        """Generate human-readable summary."""
        parts = []

        # Overall status
        if session.risk_score < 0.3:
            parts.append("Session completed with low risk indicators.")
        elif session.risk_score < 0.6:
            parts.append("Session completed with moderate risk indicators that may require review.")
        else:
            parts.append("Session flagged with high risk indicators requiring immediate review.")

        # Critical incidents
        if severity_counts["critical"] > 0:
            parts.append(
                f"CRITICAL: {severity_counts['critical']} critical incident(s) detected."
            )

        # Verification
        if session.verification_failures > 0:
            parts.append(
                f"Identity verification failed {session.verification_failures} time(s) "
                f"out of {session.verification_count} attempts."
            )

        # Duration
        duration_min = session.get_duration_seconds() / 60
        parts.append(f"Total session duration: {duration_min:.1f} minutes.")

        return " ".join(parts)


class ListSessionIncidents:
    """Use case for listing incidents in a session."""

    def __init__(self, incident_repository: IProctorIncidentRepository) -> None:
        self._repository = incident_repository

    async def execute(
        self,
        session_id: UUID,
        severity: str = None,
        reviewed: bool = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List incidents with optional filters."""
        if severity:
            try:
                sev = IncidentSeverity(severity)
                incidents = await self._repository.get_by_session_and_severity(
                    session_id, sev, limit
                )
            except ValueError:
                raise ValueError(f"Invalid severity: {severity}")
        elif reviewed is False:
            incidents = await self._repository.get_unreviewed(session_id, limit)
        else:
            incidents = await self._repository.get_by_session(session_id, limit, offset)

        return [incident.to_dict() for incident in incidents]
