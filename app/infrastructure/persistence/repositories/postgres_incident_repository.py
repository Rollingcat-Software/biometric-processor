"""PostgreSQL proctor incident repository."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from app.domain.entities.proctor_incident import (
    IncidentEvidence,
    IncidentSeverity,
    IncidentType,
    ProctorIncident,
    ReviewAction,
)
from app.domain.exceptions.repository_errors import RepositoryError
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository

logger = logging.getLogger(__name__)


class PostgresIncidentRepository(IProctorIncidentRepository):
    """PostgreSQL-backed proctor incident repository."""

    def __init__(self, pool) -> None:
        """Initialize with database connection pool."""
        self._pool = pool

    async def save(self, incident: ProctorIncident) -> None:
        """Save or update an incident."""
        try:
            query = """
                INSERT INTO proctor_incidents (
                    id, session_id, incident_type, severity, confidence,
                    details, reviewed, reviewed_at, reviewed_by,
                    review_action, review_notes, timestamp, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    severity = EXCLUDED.severity,
                    confidence = EXCLUDED.confidence,
                    details = EXCLUDED.details,
                    reviewed = EXCLUDED.reviewed,
                    reviewed_at = EXCLUDED.reviewed_at,
                    reviewed_by = EXCLUDED.reviewed_by,
                    review_action = EXCLUDED.review_action,
                    review_notes = EXCLUDED.review_notes
            """

            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    incident.id,
                    incident.session_id,
                    incident.incident_type.value,
                    incident.severity.value,
                    incident.confidence,
                    json.dumps(incident.details),
                    incident.reviewed,
                    incident.reviewed_at,
                    incident.reviewed_by,
                    incident.review_action.value if incident.review_action else None,
                    incident.review_notes,
                    incident.timestamp,
                )

            logger.debug(f"Saved incident {incident.id}")

        except Exception as e:
            logger.error(f"Failed to save incident {incident.id}: {e}")
            raise RepositoryError(f"Failed to save incident: {e}")

    async def get_by_id(self, incident_id: UUID) -> Optional[ProctorIncident]:
        """Get incident by ID."""
        query = """
            SELECT * FROM proctor_incidents WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, incident_id)

            if not row:
                return None

            incident = self._row_to_incident(row)

            # Load evidence
            incident.evidence = await self.get_evidence(incident_id)

            return incident

        except Exception as e:
            logger.error(f"Failed to get incident {incident_id}: {e}")
            raise RepositoryError(f"Failed to get incident: {e}")

    async def get_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorIncident]:
        """Get all incidents for a session."""
        query = """
            SELECT * FROM proctor_incidents
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT $2 OFFSET $3
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, session_id, limit, offset)

            return [self._row_to_incident(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get incidents for session {session_id}: {e}")
            raise RepositoryError(f"Failed to get incidents: {e}")

    async def get_by_session_and_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
        limit: int = 100,
    ) -> List[ProctorIncident]:
        """Get incidents by session and severity."""
        query = """
            SELECT * FROM proctor_incidents
            WHERE session_id = $1 AND severity = $2
            ORDER BY timestamp DESC
            LIMIT $3
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, session_id, severity.value, limit)

            return [self._row_to_incident(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get incidents by severity: {e}")
            raise RepositoryError(f"Failed to get incidents: {e}")

    async def get_unreviewed(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> List[ProctorIncident]:
        """Get unreviewed incidents for a session."""
        query = """
            SELECT * FROM proctor_incidents
            WHERE session_id = $1 AND reviewed = FALSE
            ORDER BY timestamp DESC
            LIMIT $2
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, session_id, limit)

            return [self._row_to_incident(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get unreviewed incidents: {e}")
            raise RepositoryError(f"Failed to get incidents: {e}")

    async def count_by_session(self, session_id: UUID) -> int:
        """Count incidents for a session."""
        query = """
            SELECT COUNT(*) FROM proctor_incidents WHERE session_id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query, session_id)

            return count or 0

        except Exception as e:
            logger.error(f"Failed to count incidents: {e}")
            raise RepositoryError(f"Failed to count incidents: {e}")

    async def count_by_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
    ) -> int:
        """Count incidents by severity."""
        query = """
            SELECT COUNT(*) FROM proctor_incidents
            WHERE session_id = $1 AND severity = $2
        """

        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query, session_id, severity.value)

            return count or 0

        except Exception as e:
            logger.error(f"Failed to count incidents by severity: {e}")
            raise RepositoryError(f"Failed to count incidents: {e}")

    async def mark_reviewed(
        self,
        incident_id: UUID,
        reviewer: str,
        action: ReviewAction,
        notes: Optional[str] = None,
    ) -> None:
        """Mark incident as reviewed."""
        query = """
            UPDATE proctor_incidents
            SET reviewed = TRUE,
                reviewed_at = NOW(),
                reviewed_by = $2,
                review_action = $3,
                review_notes = $4
            WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, incident_id, reviewer, action.value, notes)

        except Exception as e:
            logger.error(f"Failed to mark incident reviewed: {e}")
            raise RepositoryError(f"Failed to mark incident reviewed: {e}")

    async def add_evidence(
        self,
        incident_id: UUID,
        evidence: IncidentEvidence,
    ) -> None:
        """Add evidence to incident."""
        query = """
            INSERT INTO incident_evidence (
                id, incident_id, evidence_type, storage_url,
                thumbnail_url, metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    evidence.id,
                    incident_id,
                    evidence.evidence_type,
                    evidence.storage_url,
                    evidence.thumbnail_url,
                    json.dumps(evidence.metadata),
                    evidence.created_at,
                )

        except Exception as e:
            logger.error(f"Failed to add evidence: {e}")
            raise RepositoryError(f"Failed to add evidence: {e}")

    async def get_evidence(self, incident_id: UUID) -> List[IncidentEvidence]:
        """Get all evidence for an incident."""
        query = """
            SELECT * FROM incident_evidence
            WHERE incident_id = $1
            ORDER BY created_at
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, incident_id)

            return [self._row_to_evidence(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get evidence: {e}")
            raise RepositoryError(f"Failed to get evidence: {e}")

    async def get_recent_by_type(
        self,
        session_id: UUID,
        incident_type: IncidentType,
        within_seconds: int = 60,
    ) -> List[ProctorIncident]:
        """Get recent incidents of a specific type."""
        cutoff = datetime.utcnow() - timedelta(seconds=within_seconds)

        query = """
            SELECT * FROM proctor_incidents
            WHERE session_id = $1
                AND incident_type = $2
                AND timestamp > $3
            ORDER BY timestamp DESC
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, session_id, incident_type.value, cutoff)

            return [self._row_to_incident(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get recent incidents: {e}")
            raise RepositoryError(f"Failed to get incidents: {e}")

    async def delete_by_session(self, session_id: UUID) -> int:
        """Delete all incidents for a session."""
        # First delete evidence
        evidence_query = """
            DELETE FROM incident_evidence
            WHERE incident_id IN (
                SELECT id FROM proctor_incidents WHERE session_id = $1
            )
        """

        # Then delete incidents
        incident_query = """
            DELETE FROM proctor_incidents
            WHERE session_id = $1
            RETURNING id
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(evidence_query, session_id)
                rows = await conn.fetch(incident_query, session_id)

            return len(rows)

        except Exception as e:
            logger.error(f"Failed to delete incidents: {e}")
            raise RepositoryError(f"Failed to delete incidents: {e}")

    def _row_to_incident(self, row) -> ProctorIncident:
        """Convert database row to ProctorIncident entity."""
        review_action = None
        if row["review_action"]:
            review_action = ReviewAction(row["review_action"])

        details = json.loads(row["details"]) if row["details"] else {}

        return ProctorIncident(
            id=row["id"],
            session_id=row["session_id"],
            incident_type=IncidentType(row["incident_type"]),
            severity=IncidentSeverity(row["severity"]),
            confidence=row["confidence"],
            timestamp=row["timestamp"],
            details=details,
            evidence=[],  # Load separately
            reviewed=row["reviewed"],
            reviewed_at=row["reviewed_at"],
            reviewed_by=row["reviewed_by"],
            review_action=review_action,
            review_notes=row["review_notes"],
        )

    def _row_to_evidence(self, row) -> IncidentEvidence:
        """Convert database row to IncidentEvidence entity."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return IncidentEvidence(
            id=row["id"],
            incident_id=row["incident_id"],
            evidence_type=row["evidence_type"],
            storage_url=row["storage_url"],
            thumbnail_url=row["thumbnail_url"],
            metadata=metadata,
            created_at=row["created_at"],
        )
