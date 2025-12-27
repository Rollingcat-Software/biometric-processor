"""PostgreSQL embedding repository with pgvector for similarity search."""

import ast
import logging
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np

from app.domain.exceptions.repository_errors import RepositoryError
from app.domain.interfaces.embedding_repository import IEmbeddingRepository

logger = logging.getLogger(__name__)


class PostgresEmbeddingRepository:
    """PostgreSQL-backed embedding repository using pgvector.

    Provides efficient vector similarity search using PostgreSQL's pgvector
    extension for production deployments.

    Requirements:
        - PostgreSQL 14+
        - pgvector extension installed
        - asyncpg for async database access

    Schema:
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE face_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) NOT NULL,
            tenant_id VARCHAR(255),
            embedding vector(512),
            quality_score FLOAT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, tenant_id)
        );
        CREATE INDEX ON face_embeddings USING ivfflat (embedding vector_cosine_ops);
    """

    def __init__(
        self,
        database_url: str,
        embedding_dimension: int = 512,
        pool_size: int = 10,
    ) -> None:
        """Initialize PostgreSQL repository.

        Args:
            database_url: PostgreSQL connection URL
            embedding_dimension: Dimension of embedding vectors
            pool_size: Connection pool size
        """
        self._database_url = database_url
        self._embedding_dimension = embedding_dimension
        self._pool_size = pool_size
        self._pool = None
        logger.info(
            f"PostgresEmbeddingRepository initialized "
            f"(dim={embedding_dimension}, pool_size={pool_size})"
        )

    async def _setup_connection(self, conn) -> None:
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
        logger.debug(f"Configured connection {id(conn)} for pgvector")

    async def connect(self) -> None:
        """Establish database connection pool.

        Raises:
            RepositoryError: If connection fails
        """
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=self._pool_size,
                setup=self._setup_connection,
            )
            logger.info("PostgreSQL connection pool established")
        except ImportError:
            raise RepositoryError(
                "asyncpg not installed. Install with: pip install asyncpg"
            )
        except Exception as e:
            raise RepositoryError(f"Failed to connect to PostgreSQL: {e}")

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def _ensure_connected(self) -> None:
        """Ensure connection pool is established."""
        if self._pool is None:
            await self.connect()

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
            embedding: Face embedding vector
            quality_score: Quality score of the enrolled face
            tenant_id: Optional tenant identifier

        Raises:
            RepositoryError: When save operation fails
        """
        await self._ensure_connected()

        # Convert numpy array to list for pgvector
        embedding_list = embedding.tolist()

        query = """
            INSERT INTO face_embeddings (user_id, tenant_id, embedding, quality_score, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (user_id, tenant_id)
            DO UPDATE SET
                embedding = $3,
                quality_score = $4,
                updated_at = NOW()
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    user_id,
                    tenant_id,
                    embedding_list,
                    quality_score,
                )
            logger.debug(f"Saved embedding for user_id={user_id}")
        except Exception as e:
            raise RepositoryError(f"Failed to save embedding: {e}")

    async def find_by_user_id(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """Find embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            Embedding vector if found, None otherwise
        """
        await self._ensure_connected()

        if tenant_id:
            query = """
                SELECT embedding::text FROM face_embeddings
                WHERE user_id = $1 AND tenant_id = $2
            """
            params = (user_id, tenant_id)
        else:
            query = """
                SELECT embedding::text FROM face_embeddings
                WHERE user_id = $1 AND tenant_id IS NULL
            """
            params = (user_id,)

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)

            if row is None:
                return None

            # Parse vector string back to numpy array
            embedding_str = row["embedding"]
            # Use ast.literal_eval() for safe parsing (prevents code injection)
            embedding_list = ast.literal_eval(embedding_str)  # pgvector returns as string
            return np.array(embedding_list, dtype=np.float32)

        except Exception as e:
            raise RepositoryError(f"Failed to find embedding: {e}")

    async def find_similar(
        self,
        embedding: np.ndarray,
        threshold: float,
        limit: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """Find similar embeddings using cosine distance.

        Args:
            embedding: Query embedding vector
            threshold: Maximum cosine distance to consider as similar
            limit: Maximum number of results
            tenant_id: Optional tenant identifier

        Returns:
            List of (user_id, distance) tuples, sorted by distance
        """
        await self._ensure_connected()

        embedding_list = embedding.tolist()

        if tenant_id:
            query = """
                SELECT user_id, embedding <=> $1 AS distance
                FROM face_embeddings
                WHERE tenant_id = $2
                  AND embedding <=> $1 < $3
                ORDER BY distance
                LIMIT $4
            """
            params = (embedding_list, tenant_id, threshold, limit)
        else:
            query = """
                SELECT user_id, embedding <=> $1 AS distance
                FROM face_embeddings
                WHERE tenant_id IS NULL
                  AND embedding <=> $1 < $2
                ORDER BY distance
                LIMIT $3
            """
            params = (embedding_list, threshold, limit)

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            return [(row["user_id"], float(row["distance"])) for row in rows]

        except Exception as e:
            raise RepositoryError(f"Failed to find similar embeddings: {e}")

    async def delete(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Delete embedding by user ID.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if deleted, False if not found
        """
        await self._ensure_connected()

        if tenant_id:
            query = """
                DELETE FROM face_embeddings
                WHERE user_id = $1 AND tenant_id = $2
            """
            params = (user_id, tenant_id)
        else:
            query = """
                DELETE FROM face_embeddings
                WHERE user_id = $1 AND tenant_id IS NULL
            """
            params = (user_id,)

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, *params)

            # Parse "DELETE n" to get count
            deleted = int(result.split()[-1])
            return deleted > 0

        except Exception as e:
            raise RepositoryError(f"Failed to delete embedding: {e}")

    async def exists(self, user_id: str, tenant_id: Optional[str] = None) -> bool:
        """Check if embedding exists for user.

        Args:
            user_id: User identifier
            tenant_id: Optional tenant identifier

        Returns:
            True if exists, False otherwise
        """
        await self._ensure_connected()

        if tenant_id:
            query = """
                SELECT EXISTS(
                    SELECT 1 FROM face_embeddings
                    WHERE user_id = $1 AND tenant_id = $2
                )
            """
            params = (user_id, tenant_id)
        else:
            query = """
                SELECT EXISTS(
                    SELECT 1 FROM face_embeddings
                    WHERE user_id = $1 AND tenant_id IS NULL
                )
            """
            params = (user_id,)

        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(query, *params)
            return result

        except Exception as e:
            raise RepositoryError(f"Failed to check existence: {e}")

    async def count(self, tenant_id: Optional[str] = None) -> int:
        """Count total embeddings.

        Args:
            tenant_id: Optional tenant identifier

        Returns:
            Number of embeddings
        """
        await self._ensure_connected()

        if tenant_id:
            query = "SELECT COUNT(*) FROM face_embeddings WHERE tenant_id = $1"
            params = (tenant_id,)
        else:
            query = "SELECT COUNT(*) FROM face_embeddings"
            params = ()

        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query, *params)
            return count or 0

        except Exception as e:
            raise RepositoryError(f"Failed to count embeddings: {e}")

    async def health_check(self) -> bool:
        """Check database connection health.

        Returns:
            True if healthy
        """
        try:
            await self._ensure_connected()
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
