"""Client embedding observation repository (log-only).

Stores client-side pre-filter embeddings for offline analysis. These
embeddings are NEVER trusted for authentication decisions (D1 pre-filter
only). The primary enrollment/verification flow must not fail if logging
fails — all errors are swallowed with warning logs.

Follows the same asyncpg pool pattern as PgVectorVoiceRepository and
PgVectorEmbeddingRepository.
"""

import json
import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

CLIENT_EMBEDDING_DIM = 128


class ClientEmbeddingObservationRepository:
    """Log-only repository for client-provided embeddings.

    Table: client_embedding_observations
    Purpose: Offline analysis of client-side pre-filter quality; never used
             for authentication decisions.
    """

    def __init__(
        self,
        database_url: str,
        pool_min_size: int = 1,
        pool_max_size: int = 3,
        embedding_dimension: int = CLIENT_EMBEDDING_DIM,
    ) -> None:
        self._database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._embedding_dimension = embedding_dimension
        self._pool: Optional[asyncpg.Pool] = None

        logger.info(
            "Initialized ClientEmbeddingObservationRepository "
            f"(dim={embedding_dimension}, pool={pool_min_size}-{pool_max_size})"
        )

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Create connection pool on first use."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=self._pool_min_size,
                max_size=self._pool_max_size,
                command_timeout=10.0,
                setup=self._setup_connection,
            )
            logger.info("Client embedding observation pool created")
        return self._pool

    async def _setup_connection(self, conn: asyncpg.Connection) -> None:
        """Register pgvector type on each connection."""
        from pgvector.asyncpg import register_vector
        await register_vector(conn)

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def record(
        self,
        user_id: str,
        tenant_id: Optional[str],
        session_id: Optional[str],
        modality: str,
        flow: str,
        client_embedding_json: Optional[str],
        client_model_version: Optional[str] = None,
        server_embedding_ref: Optional[str] = None,
        device_platform: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Record a client embedding observation (log-only, never raises).

        Args:
            user_id: User identifier.
            tenant_id: Optional tenant UUID string.
            session_id: Optional session identifier.
            modality: 'face' or 'card'.
            flow: 'enroll' or 'verify'.
            client_embedding_json: JSON-encoded list[float] (128-dim), or None.
            client_model_version: Client-reported model version.
            server_embedding_ref: Optional UUID reference to server embedding.
            device_platform: Device platform string (e.g. 'web', 'android').
            user_agent: Raw User-Agent header.
        """
        # Parse & validate embedding — skip silently on any issue
        embedding_list: Optional[list] = None
        if client_embedding_json:
            try:
                parsed = json.loads(client_embedding_json)
                if not isinstance(parsed, list):
                    logger.debug("client_embedding is not a list; skipping")
                    return
                if len(parsed) != self._embedding_dimension:
                    logger.debug(
                        f"client_embedding dim mismatch: got {len(parsed)}, "
                        f"expected {self._embedding_dimension}; skipping"
                    )
                    return
                embedding_list = [float(x) for x in parsed]
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                logger.debug(f"Failed to parse client_embedding: {e}; skipping")
                return
        else:
            # No embedding provided — nothing to log
            return

        try:
            pool = await self._ensure_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO client_embedding_observations (
                        user_id, tenant_id, session_id, modality, flow,
                        client_embedding, client_model_version,
                        server_embedding_ref, device_platform, user_agent
                    ) VALUES (
                        $1::varchar, $2::uuid, $3::varchar, $4::varchar, $5::varchar,
                        $6, $7::varchar, $8::uuid, $9::varchar, $10
                    )
                    """,
                    user_id,
                    tenant_id,
                    session_id,
                    modality,
                    flow,
                    embedding_list,
                    client_model_version,
                    server_embedding_ref,
                    device_platform,
                    user_agent,
                )
            logger.debug(
                f"client_embedding observation recorded: "
                f"user_id={user_id}, modality={modality}, flow={flow}"
            )
        except Exception as e:
            # Log-only — never propagate to caller
            logger.warning(
                f"Failed to record client_embedding observation "
                f"(user_id={user_id}, modality={modality}, flow={flow}): {e}"
            )
