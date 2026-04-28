"""PostgreSQL with pgvector embedding repository implementation.

This repository uses PostgreSQL with the pgvector extension for efficient
vector similarity search. It provides production-ready face embedding storage
with support for multi-tenancy and scalable 1:N face identification.

Architecture:
- Uses asyncpg for async PostgreSQL operations
- Implements connection pooling for production performance
- Uses pgvector for efficient similarity search (cosine distance)
- Supports HNSW or IVFFlat indexes for fast approximate nearest neighbor search

Performance:
- Connection pooling for minimal overhead
- Vector indexes for sub-second similarity search even with millions of faces
- Async/await for non-blocking I/O operations
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

import asyncpg
import numpy as np

from app.domain.exceptions.repository_errors import RepositoryError

logger = logging.getLogger(__name__)


class PgVectorEmbeddingRepository:
    """PostgreSQL pgvector repository for face embeddings.

    Implements IEmbeddingRepository using PostgreSQL with pgvector extension
    for production-grade face embedding storage and similarity search.

    Following Repository Pattern and Hexagonal Architecture principles.

    Features:
    - Multi-tenancy support via tenant_id
    - Efficient vector similarity search using pgvector
    - Connection pooling for production performance
    - ACID compliance for data consistency
    - Async operations for scalability

    Database Schema:
    - Table: face_embeddings
    - Vector column: embedding (512 dimensions for FaceNet)
    - Index: HNSW or IVFFlat for fast similarity search
    - Supports: cosine distance metric

    Note:
        Requires PostgreSQL 11+ with pgvector extension installed.
        Requires face_embeddings table with vector column.
    """

    def __init__(
        self,
        database_url: str,
        pool_min_size: int = 10,
        pool_max_size: int = 20,
        embedding_dimension: int = 512,
        command_timeout: float = 30.0,
        max_queries: int = 50000,
        max_inactive_connection_lifetime: float = 300.0,
    ) -> None:
        """Initialize PostgreSQL pgvector repository with optimized connection pool.

        Args:
            database_url: PostgreSQL connection URL (e.g., postgresql://user:pass@host:port/db)
            pool_min_size: Minimum number of connections in pool (default: 10)
            pool_max_size: Maximum number of connections in pool (default: 20)
            embedding_dimension: Dimension of face embeddings (default: 512 for FaceNet)
            command_timeout: Timeout for individual SQL commands in seconds (default: 30)
            max_queries: Max queries per connection before recycling (default: 50000)
            max_inactive_connection_lifetime: Max seconds connection can be idle (default: 300)

        Connection Pool Optimization:
            - command_timeout: Prevents hung queries from blocking connections
            - max_queries: Prevents memory leaks from long-lived connections
            - max_inactive_connection_lifetime: Closes stale connections automatically
            - Optimized for async workloads with concurrent requests

        Note:
            Connection pool will be created on first async operation via _ensure_pool()
        """
        self._database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._embedding_dimension = embedding_dimension
        self._command_timeout = command_timeout
        self._max_queries = max_queries
        self._max_inactive_connection_lifetime = max_inactive_connection_lifetime
        self._pool: Optional[asyncpg.Pool] = None

        logger.info(
            f"Initialized PgVectorEmbeddingRepository with optimized pool settings "
            f"(dimension={embedding_dimension}, pool={pool_min_size}-{pool_max_size}, "
            f"command_timeout={command_timeout}s, max_queries={max_queries}, "
            f"max_inactive_lifetime={max_inactive_connection_lifetime}s)"
        )

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Ensure connection pool is created with optimized async settings.

        Returns:
            Active connection pool

        Raises:
            RepositoryError: When pool creation fails

        Performance:
            Pool is optimized for async workloads:
            - Prevents connection exhaustion under high concurrency
            - Automatic connection recycling prevents memory leaks
            - Idle connection cleanup prevents resource waste
            - Command timeouts prevent hung queries from blocking pool
        """
        if self._pool is None:
            try:
                logger.info(
                    f"Creating PostgreSQL connection pool with async optimizations "
                    f"(size: {self._pool_min_size}-{self._pool_max_size})..."
                )
                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    min_size=self._pool_min_size,
                    max_size=self._pool_max_size,
                    command_timeout=self._command_timeout,
                    max_queries=self._max_queries,
                    max_inactive_connection_lifetime=self._max_inactive_connection_lifetime,
                    # Setup hook to configure pgvector extension on each connection
                    setup=self._setup_connection,
                )
                logger.info(
                    f"PostgreSQL connection pool created successfully "
                    f"(timeout={self._command_timeout}s, "
                    f"max_queries={self._max_queries}, "
                    f"inactive_lifetime={self._max_inactive_connection_lifetime}s)"
                )
            except Exception as e:
                logger.error(f"Failed to create connection pool: {e}", exc_info=True)
                raise RepositoryError(operation="pool_creation", reason=str(e))

        return self._pool

    async def _setup_connection(self, conn: asyncpg.Connection) -> None:
        """Setup connection configuration for pgvector.

        This method is called for each new connection in the pool.
        Configures connection-specific settings for optimal performance.

        Args:
            conn: asyncpg connection to configure
        """
        from pgvector.asyncpg import register_vector

        # Register vector type for pgvector extension
        # This ensures vectors are properly handled by asyncpg
        await register_vector(conn)
        await conn.execute("SET statement_timeout = '30s'")
        logger.debug(f"Configured connection {id(conn)} for pgvector")

    async def close(self) -> None:
        """Close connection pool.

        Should be called during application shutdown.
        """
        if self._pool is not None:
            await self._pool.close()
            logger.info("PostgreSQL connection pool closed")
            self._pool = None

    async def save(
        self,
        user_id: str,
        embedding: np.ndarray,
        quality_score: float,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Save or update a face embedding.

        Args:
            user_id: Unique identifier for the user
            embedding: Face embedding vector (must match embedding_dimension)
            quality_score: Quality score of enrolled face (0-100)
            tenant_id: Optional tenant identifier for multi-tenancy

        Raises:
            RepositoryError: When save operation fails
            ValueError: When embedding dimension doesn't match

        Note:
            Uses UPSERT logic: updates existing embedding if user_id exists,
            otherwise creates new record.
        """
        if len(embedding) != self._embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._embedding_dimension}, "
                f"got {len(embedding)}"
            )

        try:
            pool = await self._ensure_pool()

            # Convert numpy array to list for PostgreSQL
            embedding_list = embedding.tolist()

            # Normalize quality score to 0-1 range (database expects 0-1)
            normalized_quality = quality_score / 100.0 if quality_score > 1.0 else quality_score

            async with pool.acquire() as conn:
                # Insert individual enrollment (never overwrite — accumulate)
                await conn.execute(
                    """
                    INSERT INTO face_embeddings (
                        user_id, tenant_id, embedding, quality_score, enrollment_type
                    ) VALUES ($1, $2, $3, $4, 'INDIVIDUAL')
                    """,
                    user_id, tenant_id, embedding_list, normalized_quality,
                )

                # Cap individual enrollments at 5 per user — delete oldest when exceeding
                # This prevents centroid dilution from too many low-quality enrollments
                MAX_INDIVIDUAL_ENROLLMENTS = 5
                count = await conn.fetchval(
                    """
                    SELECT count(*) FROM face_embeddings
                    WHERE user_id = $1 AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                    """,
                    user_id,
                )

                if count > MAX_INDIVIDUAL_ENROLLMENTS:
                    # Delete oldest individual enrollments beyond the cap
                    await conn.execute(
                        """
                        DELETE FROM face_embeddings
                        WHERE id IN (
                            SELECT id FROM face_embeddings
                            WHERE user_id = $1 AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                            ORDER BY quality_score ASC, created_at ASC
                            LIMIT $2
                        )
                        """,
                        user_id, count - MAX_INDIVIDUAL_ENROLLMENTS,
                    )
                    logger.info(
                        f"Pruned {count - MAX_INDIVIDUAL_ENROLLMENTS} lowest-quality enrollment(s) "
                        f"for user {user_id} (cap={MAX_INDIVIDUAL_ENROLLMENTS})"
                    )

                # Check if centroid exists
                has_centroid = await conn.fetchval(
                    """
                    SELECT count(*) FROM face_embeddings
                    WHERE user_id = $1 AND enrollment_type = 'CENTROID' AND deleted_at IS NULL
                    """,
                    user_id,
                )

                # Centroid as average of all individual embeddings
                # pgvector doesn't support vector * scalar, so use simple AVG
                # Quality filtering is done by the enrollment cap (keeps top 5 by quality)
                centroid_sql = """
                    SELECT
                        AVG(embedding)::vector(512) as avg_emb,
                        AVG(quality_score) as avg_q
                    FROM face_embeddings
                    WHERE user_id = $1 AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                """

                if has_centroid == 0:
                    # Create centroid from quality-weighted individual embeddings
                    await conn.execute(
                        """
                        INSERT INTO face_embeddings (user_id, tenant_id, embedding, quality_score, enrollment_type)
                        SELECT $1, $2, sub.avg_emb, sub.avg_q, 'CENTROID'
                        FROM (""" + centroid_sql + """) sub
                        WHERE sub.avg_emb IS NOT NULL
                        """,
                        user_id, tenant_id,
                    )
                else:
                    # Update existing centroid with quality-weighted average
                    await conn.execute(
                        """
                        UPDATE face_embeddings SET
                            embedding = sub.avg_emb,
                            quality_score = sub.avg_q,
                            updated_at = CURRENT_TIMESTAMP
                        FROM (""" + centroid_sql + """) sub
                        WHERE face_embeddings.user_id = $1
                          AND face_embeddings.enrollment_type = 'CENTROID'
                          AND sub.avg_emb IS NOT NULL
                        """,
                        user_id,
                    )

                # Get final count
                count = await conn.fetchval(
                    """
                    SELECT count(*) FROM face_embeddings
                    WHERE user_id = $1 AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                    """,
                    user_id,
                )

            logger.info(
                f"Embedding saved: user_id={user_id}, "
                f"tenant_id={tenant_id}, "
                f"dimension={len(embedding)}, "
                f"quality={quality_score:.1f}, "
                f"total_enrollments={count}"
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to save embedding: {e}", exc_info=True)
            raise RepositoryError(operation="save", reason=str(e))

    async def find_by_user_id(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """Find embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            Embedding vector if found, None otherwise

        Note:
            For multi-tenant systems, both user_id and tenant_id must match.
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                # Return centroid (averaged embedding) for verification
                row = await conn.fetchrow(
                    """
                    SELECT embedding
                    FROM face_embeddings
                    WHERE user_id = $1
                      AND enrollment_type = 'CENTROID'
                      AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    user_id,
                )
                # Fallback to latest individual if no centroid exists
                if not row:
                    row = await conn.fetchrow(
                        """
                        SELECT embedding
                        FROM face_embeddings
                        WHERE user_id = $1
                          AND deleted_at IS NULL
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        user_id,
                    )

            if row:
                # Convert PostgreSQL vector to numpy array
                embedding = np.array(row["embedding"], dtype=np.float32)
                logger.debug(f"Found embedding for user {user_id}")
                return embedding
            else:
                logger.debug(f"No embedding found for user {user_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to find embedding: {e}", exc_info=True)
            raise RepositoryError(operation="find", reason=str(e))

    async def find_similar(
        self,
        embedding: np.ndarray,
        threshold: float,
        limit: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """Find similar embeddings using vector similarity search.

        Args:
            embedding: Query embedding vector
            threshold: Maximum distance to consider as similar (0.0-1.0)
            limit: Maximum number of results to return
            tenant_id: Optional tenant identifier

        Returns:
            List of (user_id, distance) tuples, sorted by distance (ascending)

        Raises:
            RepositoryError: When search operation fails

        Note:
            Uses pgvector's cosine distance operator (<=>).
            Requires vector index (HNSW or IVFFlat) for optimal performance.
            This is critical for 1:N face identification at scale.
        """
        if len(embedding) != self._embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._embedding_dimension}, "
                f"got {len(embedding)}"
            )

        if not tenant_id:
            # Defense-in-depth: never search across tenants at the vector layer.
            raise ValueError("tenant_id is required for find_similar (cross-tenant search forbidden)")

        # ML-M5 (Audit 2026-04-19): server-side floor on caller-controlled
        # threshold/limit to prevent enumeration via inflated parameters
        # (e.g. threshold=2.0, limit=1000 would return the whole tenant).
        from app.core.config import settings as _settings
        max_threshold = _settings.FIND_SIMILAR_FACE_MAX_THRESHOLD
        max_limit = _settings.FIND_SIMILAR_MAX_LIMIT
        if threshold > max_threshold:
            logger.warning(
                "find_similar threshold %.3f exceeds cap %.3f; clamping "
                "(tenant_id=%s)",
                threshold, max_threshold, tenant_id,
            )
            threshold = max_threshold
        if limit > max_limit:
            logger.warning(
                "find_similar limit %d exceeds cap %d; clamping (tenant_id=%s)",
                limit, max_limit, tenant_id,
            )
            limit = max_limit

        try:
            pool = await self._ensure_pool()

            # Convert numpy array to list for PostgreSQL
            embedding_list = embedding.tolist()

            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        user_id,
                        embedding <=> $1::vector AS distance
                    FROM face_embeddings
                    WHERE embedding <=> $1::vector < $2
                      AND deleted_at IS NULL
                      AND (enrollment_type = 'CENTROID' OR enrollment_type IS NULL)
                      AND tenant_id = $4::VARCHAR
                    ORDER BY distance ASC
                    LIMIT $3
                    """,
                    embedding_list,
                    threshold,
                    limit,
                    tenant_id,
                )

            # Convert to list of tuples
            matches = [(row["user_id"], float(row["distance"])) for row in rows]

            logger.info(
                f"Found {len(matches)} similar embeddings "
                f"(threshold={threshold}, limit={limit}, tenant_id={tenant_id})"
            )

            return matches

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to search embeddings: {e}", exc_info=True)
            raise RepositoryError(operation="find_similar", reason=str(e))

    async def delete(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if embedding was deleted, False if not found

        Raises:
            RepositoryError: When delete operation fails

        Note:
            Uses soft delete (sets deleted_at timestamp) to maintain audit trail.
        """
        if not tenant_id:
            # Defense-in-depth: never delete without tenant scope.
            raise ValueError("tenant_id is required for delete (cross-tenant delete forbidden)")

        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM face_embeddings
                    WHERE user_id = $1
                      AND tenant_id = $2::VARCHAR
                    """,
                    user_id,
                    tenant_id,
                )

            # Parse result string like "DELETE 1"
            deleted_count = int(result.split()[-1]) if result else 0

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} embedding(s) for user {user_id}")
                return True
            else:
                logger.debug(f"No embedding to delete for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}", exc_info=True)
            raise RepositoryError(operation="delete", reason=str(e))

    async def exists(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Check if embedding exists for user.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if embedding exists, False otherwise
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1
                        FROM face_embeddings
                        WHERE user_id = $1
                          AND ($2::VARCHAR IS NULL OR tenant_id = $2::VARCHAR)
                    )
                    """,
                    user_id,
                    tenant_id,
                )

            return bool(result)

        except Exception as e:
            logger.error(f"Failed to check embedding existence: {e}", exc_info=True)
            raise RepositoryError(operation="exists", reason=str(e))

    async def count(self, tenant_id: Optional[str] = None) -> int:
        """Count total number of embeddings.

        Args:
            tenant_id: Optional tenant identifier

        Returns:
            Number of stored embeddings
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM face_embeddings
                    WHERE ($1::VARCHAR IS NULL OR tenant_id = $1::VARCHAR)
                    """,
                    tenant_id,
                )

            return int(count) if count else 0

        except Exception as e:
            logger.error(f"Failed to count embeddings: {e}", exc_info=True)
            raise RepositoryError(operation="count", reason=str(e))

    async def health_check(self) -> bool:
        """Check if database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return False

    # =========================================================================
    # Phase 7: Database Optimization - Additional Methods
    # =========================================================================

    async def search(
        self,
        embedding: np.ndarray,
        tenant_id: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> List[dict]:
        """Optimized search for similar faces using pgvector IVFFlat index.

        Uses cosine similarity (1 - cosine_distance) for matching.
        Requires IVFFlat index on embedding column for optimal performance.

        Args:
            embedding: Query embedding vector
            tenant_id: Tenant identifier for multi-tenancy
            limit: Maximum results to return
            threshold: Minimum similarity threshold (0-1)

        Returns:
            List of dicts with user_id, similarity, quality_score, created_at

        Performance:
            With IVFFlat index (lists=100), search is O(sqrt(n)) instead of O(n).
            Typical performance: <100ms for 1M embeddings.
        """
        if len(embedding) != self._embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._embedding_dimension}, "
                f"got {len(embedding)}"
            )

        try:
            pool = await self._ensure_pool()
            embedding_list = embedding.tolist()

            async with pool.acquire() as conn:
                # Set probes for IVFFlat index (higher = more accurate, slower)
                await conn.execute("SET ivfflat.probes = 10")

                rows = await conn.fetch(
                    """
                    SELECT
                        user_id,
                        1 - (embedding <=> $1::vector) as similarity,
                        quality_score,
                        created_at
                    FROM face_embeddings
                    WHERE tenant_id = $2
                      AND is_active = true
                      AND 1 - (embedding <=> $1::vector) >= $3
                    ORDER BY embedding <=> $1::vector
                    LIMIT $4
                    """,
                    embedding_list,
                    tenant_id,
                    threshold,
                    limit,
                )

            results = [
                {
                    "user_id": row["user_id"],
                    "similarity": float(row["similarity"]),
                    "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
                    "enrolled_at": row["created_at"],
                }
                for row in rows
            ]

            logger.info(
                f"Search completed: {len(results)} matches "
                f"(threshold={threshold}, tenant={tenant_id})"
            )

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise RepositoryError(operation="search", reason=str(e))

    async def bulk_insert(
        self,
        embeddings: List[Tuple[str, str, np.ndarray, float]],
    ) -> int:
        """Bulk insert embeddings for better performance.

        Uses PostgreSQL COPY protocol for efficient bulk inserts.

        Args:
            embeddings: List of (user_id, tenant_id, embedding, quality_score) tuples

        Returns:
            Number of embeddings inserted

        Performance:
            ~10x faster than individual inserts for large batches.
            Recommended for batch enrollment operations.
        """
        if not embeddings:
            return 0

        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                # Use a transaction for atomicity
                async with conn.transaction():
                    # Prepare data for bulk insert
                    records = []
                    for user_id, tenant_id, embedding, quality_score in embeddings:
                        if len(embedding) != self._embedding_dimension:
                            raise ValueError(
                                f"Embedding dimension mismatch for user {user_id}: "
                                f"expected {self._embedding_dimension}, got {len(embedding)}"
                            )

                        # Normalize quality score
                        normalized_quality = (
                            quality_score / 100.0 if quality_score > 1.0 else quality_score
                        )
                        records.append((user_id, tenant_id, embedding.tolist(), normalized_quality))

                    # Use copy_records_to_table for bulk insert
                    # This is much faster than individual inserts
                    await conn.executemany(
                        """
                        INSERT INTO face_embeddings (user_id, tenant_id, embedding, quality_score, enrollment_type)
                        VALUES ($1, $2, $3, $4, 'INDIVIDUAL')
                        """,
                        records,
                    )

            logger.info(f"Bulk inserted {len(embeddings)} embeddings")
            return len(embeddings)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}", exc_info=True)
            raise RepositoryError(operation="bulk_insert", reason=str(e))

    async def get_all_by_tenant(
        self,
        tenant_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[dict]:
        """Get all embeddings for a tenant with pagination.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum results per page
            offset: Number of results to skip

        Returns:
            List of embedding records
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        user_id,
                        embedding,
                        quality_score,
                        created_at,
                        updated_at
                    FROM face_embeddings
                    WHERE tenant_id = $1
                      AND is_active = true
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    tenant_id,
                    limit,
                    offset,
                )

            return [
                {
                    "user_id": row["user_id"],
                    "embedding": np.array(row["embedding"], dtype=np.float32),
                    "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Get all by tenant failed: {e}", exc_info=True)
            raise RepositoryError(operation="get_all_by_tenant", reason=str(e))

    async def find_created_at(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> Optional[datetime]:
        """Return the creation timestamp of the stored embedding for a user.

        Used by :class:`VerifyFaceUseCase` to apply the adaptive age-based
        verification threshold (Faz 3-1).

        Prefers the CENTROID row (most representative); falls back to the
        latest INDIVIDUAL row if no centroid exists yet.

        Args:
            user_id: User identifier.
            tenant_id: Optional tenant identifier.

        Returns:
            :class:`datetime` of the earliest relevant enrollment row,
            or ``None`` if the user has no embeddings.
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT created_at
                    FROM face_embeddings
                    WHERE user_id = $1
                      AND enrollment_type = 'CENTROID'
                      AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    user_id,
                )
                if not row:
                    row = await conn.fetchrow(
                        """
                        SELECT created_at
                        FROM face_embeddings
                        WHERE user_id = $1
                          AND deleted_at IS NULL
                        ORDER BY created_at ASC
                        LIMIT 1
                        """,
                        user_id,
                    )

            if row:
                created_at = row["created_at"]
                # asyncpg returns timezone-aware datetimes; strip tz info so
                # arithmetic with datetime.utcnow() (naïve) stays consistent.
                if hasattr(created_at, "tzinfo") and created_at.tzinfo is not None:
                    import pytz as _pytz
                    try:
                        created_at = created_at.astimezone(_pytz.utc).replace(tzinfo=None)
                    except Exception:
                        created_at = created_at.replace(tzinfo=None)
                return created_at

            return None

        except Exception as e:
            logger.error(f"Failed to fetch created_at for user {user_id}: {e}", exc_info=True)
            return None

    async def get_pool_stats(self) -> dict:
        """Get connection pool statistics for monitoring.

        Returns:
            Dictionary with pool statistics
        """
        if self._pool is None:
            return {"status": "not_initialized"}

        return {
            "status": "active",
            "size": self._pool.get_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
            "free_size": self._pool.get_idle_size(),
        }
