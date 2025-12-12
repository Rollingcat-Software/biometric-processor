"""PostgreSQL proctor session repository."""

import json
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import numpy as np

from app.domain.entities.proctor_session import (
    ProctorSession,
    SessionConfig,
    SessionStatus,
    TerminationReason,
)
from app.domain.exceptions.repository_errors import RepositoryError
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository

logger = logging.getLogger(__name__)


class PostgresSessionRepository(IProctorSessionRepository):
    """PostgreSQL-backed proctor session repository."""

    def __init__(self, pool) -> None:
        """Initialize with database connection pool."""
        self._pool = pool

    async def save(self, session: ProctorSession) -> None:
        """Save or update a proctoring session."""
        try:
            # Convert embedding to list for JSON storage if present
            embedding_list = None
            if session.baseline_embedding is not None:
                embedding_list = session.baseline_embedding.tolist()

            query = """
                INSERT INTO proctor_sessions (
                    id, exam_id, user_id, tenant_id, status, risk_score,
                    config, metadata, baseline_embedding, verification_count,
                    verification_failures, incident_count, total_gaze_away_sec,
                    termination_reason, created_at, started_at, ended_at, paused_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    risk_score = EXCLUDED.risk_score,
                    config = EXCLUDED.config,
                    metadata = EXCLUDED.metadata,
                    baseline_embedding = EXCLUDED.baseline_embedding,
                    verification_count = EXCLUDED.verification_count,
                    verification_failures = EXCLUDED.verification_failures,
                    incident_count = EXCLUDED.incident_count,
                    total_gaze_away_sec = EXCLUDED.total_gaze_away_sec,
                    termination_reason = EXCLUDED.termination_reason,
                    started_at = EXCLUDED.started_at,
                    ended_at = EXCLUDED.ended_at,
                    paused_at = EXCLUDED.paused_at,
                    updated_at = NOW()
            """

            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    session.id,
                    session.exam_id,
                    session.user_id,
                    session.tenant_id,
                    session.status.value,
                    session.risk_score,
                    json.dumps(session.config.to_dict()),
                    json.dumps(session.metadata),
                    json.dumps(embedding_list) if embedding_list else None,
                    session.verification_count,
                    session.verification_failures,
                    session.incident_count,
                    session.total_gaze_away_sec,
                    session.termination_reason.value if session.termination_reason else None,
                    session.created_at,
                    session.started_at,
                    session.ended_at,
                    session.paused_at,
                )

            logger.debug(f"Saved session {session.id}")

        except Exception as e:
            logger.error(f"Failed to save session {session.id}: {e}")
            raise RepositoryError(f"Failed to save session: {e}")

    async def get_by_id(
        self,
        session_id: UUID,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by ID."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE id = $1 AND tenant_id = $2
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, session_id, tenant_id)

            if not row:
                return None

            return self._row_to_session(row)

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise RepositoryError(f"Failed to get session: {e}")

    async def get_by_exam_and_user(
        self,
        exam_id: str,
        user_id: str,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by exam and user."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE exam_id = $1 AND user_id = $2 AND tenant_id = $3
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, exam_id, user_id, tenant_id)

            if not row:
                return None

            return self._row_to_session(row)

        except Exception as e:
            logger.error(f"Failed to get session for exam {exam_id}, user {user_id}: {e}")
            raise RepositoryError(f"Failed to get session: {e}")

    async def get_active_sessions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all active sessions for tenant."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE tenant_id = $1 AND status IN ('active', 'flagged')
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, tenant_id, limit, offset)

            return [self._row_to_session(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            raise RepositoryError(f"Failed to get active sessions: {e}")

    async def get_sessions_by_exam(
        self,
        exam_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for an exam."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE exam_id = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, exam_id, tenant_id, limit, offset)

            return [self._row_to_session(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get sessions for exam {exam_id}: {e}")
            raise RepositoryError(f"Failed to get sessions: {e}")

    async def get_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all sessions for a user."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE user_id = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, user_id, tenant_id, limit, offset)

            return [self._row_to_session(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {e}")
            raise RepositoryError(f"Failed to get sessions: {e}")

    async def get_sessions_by_status(
        self,
        status: SessionStatus,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get sessions by status."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE status = $1 AND tenant_id = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, status.value, tenant_id, limit, offset)

            return [self._row_to_session(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get sessions by status {status}: {e}")
            raise RepositoryError(f"Failed to get sessions: {e}")

    async def count_active_sessions(self, tenant_id: str) -> int:
        """Count active sessions for tenant."""
        query = """
            SELECT COUNT(*) FROM proctor_sessions
            WHERE tenant_id = $1 AND status IN ('active', 'flagged')
        """

        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query, tenant_id)

            return count or 0

        except Exception as e:
            logger.error(f"Failed to count active sessions: {e}")
            raise RepositoryError(f"Failed to count sessions: {e}")

    async def count_sessions_by_user(
        self,
        user_id: str,
        tenant_id: str,
        active_only: bool = True,
    ) -> int:
        """Count sessions for a user."""
        if active_only:
            query = """
                SELECT COUNT(*) FROM proctor_sessions
                WHERE user_id = $1 AND tenant_id = $2 AND status IN ('active', 'flagged')
            """
        else:
            query = """
                SELECT COUNT(*) FROM proctor_sessions
                WHERE user_id = $1 AND tenant_id = $2
            """

        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query, user_id, tenant_id)

            return count or 0

        except Exception as e:
            logger.error(f"Failed to count sessions for user {user_id}: {e}")
            raise RepositoryError(f"Failed to count sessions: {e}")

    async def update_risk_score(
        self,
        session_id: UUID,
        tenant_id: str,
        risk_score: float,
    ) -> None:
        """Update session risk score."""
        query = """
            UPDATE proctor_sessions
            SET risk_score = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, risk_score, session_id, tenant_id)

        except Exception as e:
            logger.error(f"Failed to update risk score for {session_id}: {e}")
            raise RepositoryError(f"Failed to update risk score: {e}")

    async def update_status(
        self,
        session_id: UUID,
        tenant_id: str,
        status: SessionStatus,
    ) -> None:
        """Update session status."""
        query = """
            UPDATE proctor_sessions
            SET status = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, status.value, session_id, tenant_id)

        except Exception as e:
            logger.error(f"Failed to update status for {session_id}: {e}")
            raise RepositoryError(f"Failed to update status: {e}")

    async def delete(self, session_id: UUID, tenant_id: str) -> bool:
        """Delete a session."""
        query = """
            DELETE FROM proctor_sessions
            WHERE id = $1 AND tenant_id = $2
            RETURNING id
        """

        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(query, session_id, tenant_id)

            return result is not None

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise RepositoryError(f"Failed to delete session: {e}")

    async def get_expired_sessions(
        self,
        before: datetime,
        limit: int = 100,
    ) -> List[ProctorSession]:
        """Get sessions that have expired."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE status IN ('active', 'paused', 'flagged')
            AND created_at < $1
            LIMIT $2
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, before, limit)

            return [self._row_to_session(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get expired sessions: {e}")
            raise RepositoryError(f"Failed to get expired sessions: {e}")

    def _row_to_session(self, row) -> ProctorSession:
        """Convert database row to ProctorSession entity."""
        # Parse config
        config_dict = json.loads(row["config"]) if row["config"] else {}
        config = SessionConfig.from_dict(config_dict)

        # Parse metadata
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        # Parse embedding
        embedding = None
        if row["baseline_embedding"]:
            embedding_list = json.loads(row["baseline_embedding"])
            embedding = np.array(embedding_list, dtype=np.float32)

        # Parse termination reason
        termination_reason = None
        if row["termination_reason"]:
            termination_reason = TerminationReason(row["termination_reason"])

        return ProctorSession(
            id=row["id"],
            exam_id=row["exam_id"],
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            config=config,
            status=SessionStatus(row["status"]),
            risk_score=row["risk_score"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            paused_at=row["paused_at"],
            baseline_embedding=embedding,
            verification_count=row["verification_count"],
            verification_failures=row["verification_failures"],
            incident_count=row["incident_count"],
            total_gaze_away_sec=row["total_gaze_away_sec"],
            termination_reason=termination_reason,
            metadata=metadata,
        )
