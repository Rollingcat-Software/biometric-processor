"""In-memory implementations of proctoring repositories.

These implementations are for development and testing purposes.
For production use, use PostgreSQL implementations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from app.domain.entities.proctor_incident import (
    IncidentEvidence,
    IncidentSeverity,
    IncidentType,
    ProctorIncident,
    ReviewAction,
)
from app.domain.entities.proctor_session import ProctorSession, SessionStatus
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


class InMemoryProctorSessionRepository(IProctorSessionRepository):
    """In-memory implementation of proctor session repository.

    Stores sessions in a dictionary keyed by (tenant_id, session_id).
    Not suitable for production use due to:
    - No persistence across restarts
    - No distributed access
    - Memory constraints with large datasets
    """

    def __init__(self) -> None:
        """Initialize the repository."""
        # Key: (tenant_id, session_id) -> ProctorSession
        self._sessions: Dict[tuple, ProctorSession] = {}
        logger.info("InMemoryProctorSessionRepository initialized")

    async def save(self, session: ProctorSession) -> None:
        """Save or update a proctoring session."""
        key = (session.tenant_id, session.id)
        self._sessions[key] = session
        logger.debug(f"Saved session {session.id} for tenant {session.tenant_id}")

    async def get_by_id(self, session_id: UUID, tenant_id: str) -> Optional[ProctorSession]:
        """Get session by ID."""
        key = (tenant_id, session_id)
        return self._sessions.get(key)

    async def get_by_exam_and_user(
        self,
        exam_id: str,
        user_id: str,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by exam and user."""
        for session in self._sessions.values():
            if (
                session.tenant_id == tenant_id
                and session.exam_id == exam_id
                and session.user_id == user_id
                and not session.is_terminal()
            ):
                return session
        return None

    async def get_active_sessions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all active sessions for tenant."""
        active = [
            s for s in self._sessions.values()
            if s.tenant_id == tenant_id and s.status == SessionStatus.ACTIVE
        ]
        active.sort(key=lambda s: s.created_at, reverse=True)
        return active[offset:offset + limit]

    async def get_sessions_by_exam(
        self,
        exam_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for an exam."""
        sessions = [
            s for s in self._sessions.values()
            if s.tenant_id == tenant_id and s.exam_id == exam_id
        ]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[offset:offset + limit]

    async def get_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for a user."""
        sessions = [
            s for s in self._sessions.values()
            if s.tenant_id == tenant_id and s.user_id == user_id
        ]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[offset:offset + limit]

    async def get_sessions_by_status(
        self,
        status: SessionStatus,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get sessions by status."""
        sessions = [
            s for s in self._sessions.values()
            if s.tenant_id == tenant_id and s.status == status
        ]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[offset:offset + limit]

    async def count_active_sessions(self, tenant_id: str) -> int:
        """Count active sessions for tenant."""
        return sum(
            1 for s in self._sessions.values()
            if s.tenant_id == tenant_id and s.status == SessionStatus.ACTIVE
        )

    async def count_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        active_only: bool = True,
    ) -> int:
        """Count sessions for a user."""
        return sum(
            1 for s in self._sessions.values()
            if s.tenant_id == tenant_id
            and s.user_id == user_id
            and (not active_only or s.status == SessionStatus.ACTIVE)
        )

    async def update_risk_score(
        self,
        session_id: UUID,
        tenant_id: str,
        risk_score: float,
    ) -> None:
        """Update session risk score."""
        session = await self.get_by_id(session_id, tenant_id)
        if session:
            session.update_risk_score(risk_score)
            await self.save(session)

    async def update_status(
        self,
        session_id: UUID,
        tenant_id: str,
        status: SessionStatus,
    ) -> None:
        """Update session status."""
        session = await self.get_by_id(session_id, tenant_id)
        if session:
            session.status = status
            await self.save(session)

    async def delete(self, session_id: UUID, tenant_id: str) -> bool:
        """Delete a session."""
        key = (tenant_id, session_id)
        if key in self._sessions:
            del self._sessions[key]
            logger.debug(f"Deleted session {session_id}")
            return True
        return False

    async def get_expired_sessions(
        self,
        before: datetime,
        limit: int = 100,
    ) -> List[ProctorSession]:
        """Get sessions that have expired."""
        expired = []
        for session in self._sessions.values():
            if session.is_terminal():
                continue
            if session.started_at and session.started_at < before:
                # Check if session exceeded timeout
                timeout = session.config.session_timeout_sec
                if (datetime.utcnow() - session.started_at).total_seconds() > timeout:
                    expired.append(session)
        return expired[:limit]


class InMemoryProctorIncidentRepository(IProctorIncidentRepository):
    """In-memory implementation of proctor incident repository.

    Stores incidents in a dictionary keyed by incident_id.
    Also maintains a secondary index by session_id for fast lookups.
    """

    def __init__(self) -> None:
        """Initialize the repository."""
        # Key: incident_id -> ProctorIncident
        self._incidents: Dict[UUID, ProctorIncident] = {}
        # Index: session_id -> List[incident_id]
        self._session_index: Dict[UUID, List[UUID]] = {}
        # Evidence storage: incident_id -> List[IncidentEvidence]
        self._evidence: Dict[UUID, List[IncidentEvidence]] = {}
        logger.info("InMemoryProctorIncidentRepository initialized")

    async def save(self, incident: ProctorIncident) -> None:
        """Save or update an incident."""
        self._incidents[incident.id] = incident

        # Update session index
        if incident.session_id not in self._session_index:
            self._session_index[incident.session_id] = []
        if incident.id not in self._session_index[incident.session_id]:
            self._session_index[incident.session_id].append(incident.id)

        # Store evidence
        if incident.evidence:
            self._evidence[incident.id] = incident.evidence

        logger.debug(f"Saved incident {incident.id} for session {incident.session_id}")

    async def get_by_id(self, incident_id: UUID) -> Optional[ProctorIncident]:
        """Get incident by ID."""
        incident = self._incidents.get(incident_id)
        if incident:
            # Attach evidence
            incident.evidence = self._evidence.get(incident_id, [])
        return incident

    async def get_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorIncident]:
        """Get all incidents for a session."""
        incident_ids = self._session_index.get(session_id, [])
        incidents = [
            self._incidents[iid] for iid in incident_ids
            if iid in self._incidents
        ]
        incidents.sort(key=lambda i: i.timestamp, reverse=True)
        return incidents[offset:offset + limit]

    async def get_by_session_and_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
        limit: int = 100,
    ) -> List[ProctorIncident]:
        """Get incidents by session and severity."""
        incidents = await self.get_by_session(session_id, limit=1000)
        filtered = [i for i in incidents if i.severity == severity]
        return filtered[:limit]

    async def get_unreviewed(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> List[ProctorIncident]:
        """Get unreviewed incidents for a session."""
        incidents = await self.get_by_session(session_id, limit=1000)
        unreviewed = [i for i in incidents if not i.reviewed]
        return unreviewed[:limit]

    async def count_by_session(self, session_id: UUID) -> int:
        """Count incidents for a session."""
        return len(self._session_index.get(session_id, []))

    async def count_by_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
    ) -> int:
        """Count incidents by severity."""
        incident_ids = self._session_index.get(session_id, [])
        return sum(
            1 for iid in incident_ids
            if iid in self._incidents and self._incidents[iid].severity == severity
        )

    async def mark_reviewed(
        self,
        incident_id: UUID,
        reviewer: str,
        action: ReviewAction,
        notes: Optional[str] = None,
    ) -> None:
        """Mark incident as reviewed."""
        incident = await self.get_by_id(incident_id)
        if incident:
            incident.mark_reviewed(reviewer, action, notes)
            await self.save(incident)

    async def add_evidence(
        self,
        incident_id: UUID,
        evidence: IncidentEvidence,
    ) -> None:
        """Add evidence to incident."""
        if incident_id not in self._evidence:
            self._evidence[incident_id] = []
        self._evidence[incident_id].append(evidence)

        # Also update the incident object if in memory
        incident = self._incidents.get(incident_id)
        if incident:
            incident.add_evidence(evidence)

    async def get_evidence(self, incident_id: UUID) -> List[IncidentEvidence]:
        """Get all evidence for an incident."""
        return self._evidence.get(incident_id, [])

    async def get_recent_by_type(
        self,
        session_id: UUID,
        incident_type: IncidentType,
        within_seconds: int = 60,
    ) -> List[ProctorIncident]:
        """Get recent incidents of a specific type."""
        cutoff = datetime.utcnow() - timedelta(seconds=within_seconds)
        incidents = await self.get_by_session(session_id, limit=1000)
        recent = [
            i for i in incidents
            if i.incident_type == incident_type and i.timestamp >= cutoff
        ]
        return recent

    async def delete_by_session(self, session_id: UUID) -> int:
        """Delete all incidents for a session."""
        incident_ids = self._session_index.get(session_id, [])
        count = len(incident_ids)

        for iid in incident_ids:
            if iid in self._incidents:
                del self._incidents[iid]
            if iid in self._evidence:
                del self._evidence[iid]

        if session_id in self._session_index:
            del self._session_index[session_id]

        logger.debug(f"Deleted {count} incidents for session {session_id}")
        return count
