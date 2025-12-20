"""In-memory proctoring repositories for development/testing.

These implementations store data in memory and are suitable for
development and testing. For production, use PostgreSQL implementations.
"""

import logging
from collections import defaultdict
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
    """In-memory implementation of proctoring session repository."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._sessions: Dict[UUID, ProctorSession] = {}
        self._by_tenant: Dict[str, Dict[UUID, ProctorSession]] = defaultdict(dict)
        logger.info("InMemoryProctorSessionRepository initialized")

    async def save(self, session: ProctorSession) -> None:
        """Save or update a proctoring session."""
        self._sessions[session.id] = session
        self._by_tenant[session.tenant_id][session.id] = session
        logger.debug(f"Session saved: {session.id}")

    async def get_by_id(
        self,
        session_id: UUID,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by ID."""
        session = self._by_tenant.get(tenant_id, {}).get(session_id)
        return session

    async def get_by_exam_and_user(
        self,
        exam_id: str,
        user_id: str,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by exam and user."""
        for session in self._by_tenant.get(tenant_id, {}).values():
            if session.exam_id == exam_id and session.user_id == user_id:
                return session
        return None

    async def get_active_sessions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all active sessions for tenant."""
        active_statuses = {SessionStatus.ACTIVE, SessionStatus.INITIALIZING}
        sessions = [
            s for s in self._by_tenant.get(tenant_id, {}).values()
            if s.status in active_statuses
        ]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[offset:offset + limit]

    async def get_sessions_by_exam(
        self,
        exam_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for an exam."""
        sessions = [
            s for s in self._by_tenant.get(tenant_id, {}).values()
            if s.exam_id == exam_id
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
            s for s in self._by_tenant.get(tenant_id, {}).values()
            if s.user_id == user_id
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
            s for s in self._by_tenant.get(tenant_id, {}).values()
            if s.status == status
        ]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[offset:offset + limit]

    async def count_active_sessions(self, tenant_id: str) -> int:
        """Count active sessions for tenant."""
        active_statuses = {SessionStatus.ACTIVE, SessionStatus.INITIALIZING}
        return sum(
            1 for s in self._by_tenant.get(tenant_id, {}).values()
            if s.status in active_statuses
        )

    async def count_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        active_only: bool = True,
    ) -> int:
        """Count sessions for a user."""
        active_statuses = {SessionStatus.ACTIVE, SessionStatus.INITIALIZING}
        count = 0
        for s in self._by_tenant.get(tenant_id, {}).values():
            if s.user_id == user_id:
                if not active_only or s.status in active_statuses:
                    count += 1
        return count

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
            # Use appropriate state transition method
            if status == SessionStatus.ACTIVE:
                session.start()
            elif status == SessionStatus.PAUSED:
                session.pause()
            elif status == SessionStatus.COMPLETED:
                session.complete()
            await self.save(session)

    async def delete(self, session_id: UUID, tenant_id: str) -> bool:
        """Delete a session."""
        if session_id in self._by_tenant.get(tenant_id, {}):
            del self._by_tenant[tenant_id][session_id]
            if session_id in self._sessions:
                del self._sessions[session_id]
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
            if session.status in {SessionStatus.ACTIVE, SessionStatus.INITIALIZING}:
                if session.created_at < before:
                    expired.append(session)

        expired.sort(key=lambda s: s.created_at)
        return expired[:limit]


class InMemoryProctorIncidentRepository(IProctorIncidentRepository):
    """In-memory implementation of proctoring incident repository."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._incidents: Dict[UUID, ProctorIncident] = {}
        self._by_session: Dict[UUID, List[UUID]] = defaultdict(list)
        self._evidence: Dict[UUID, List[IncidentEvidence]] = defaultdict(list)
        logger.info("InMemoryProctorIncidentRepository initialized")

    async def save(self, incident: ProctorIncident) -> None:
        """Save or update an incident."""
        is_new = incident.id not in self._incidents
        self._incidents[incident.id] = incident

        if is_new:
            self._by_session[incident.session_id].append(incident.id)

        logger.debug(f"Incident saved: {incident.id}")

    async def get_by_id(self, incident_id: UUID) -> Optional[ProctorIncident]:
        """Get incident by ID."""
        return self._incidents.get(incident_id)

    async def get_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorIncident]:
        """Get all incidents for a session."""
        incident_ids = self._by_session.get(session_id, [])
        incidents = [
            self._incidents[iid]
            for iid in incident_ids
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
        return len(self._by_session.get(session_id, []))

    async def count_by_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
    ) -> int:
        """Count incidents by severity."""
        incidents = await self.get_by_session(session_id, limit=10000)
        return sum(1 for i in incidents if i.severity == severity)

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
        incident = await self.get_by_id(incident_id)
        if incident:
            incident.add_evidence(evidence)
            self._evidence[incident_id].append(evidence)
            await self.save(incident)

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
        incident_ids = self._by_session.get(session_id, [])
        count = 0
        for iid in incident_ids:
            if iid in self._incidents:
                del self._incidents[iid]
                count += 1
            if iid in self._evidence:
                del self._evidence[iid]

        if session_id in self._by_session:
            del self._by_session[session_id]

        return count
