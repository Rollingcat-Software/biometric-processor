"""PostgreSQL rate limit storage implementation.

Provides distributed rate limiting with PostgreSQL backend for
multi-instance deployments with shared state.
"""

import logging
import time
from typing import Optional

from app.domain.interfaces.rate_limit_storage import RateLimitInfo

logger = logging.getLogger(__name__)


class PostgresRateLimitStorage:
    """PostgreSQL-backed rate limit storage.

    Provides distributed rate limiting for multi-instance deployments.
    Uses PostgreSQL for shared state across application instances.

    Features:
        - Atomic increment operations using database transactions
        - Automatic window management with timestamp-based expiration
        - Tier-based rate limiting support
        - Connection pooling for performance

    Schema:
        CREATE TABLE rate_limits (
            key VARCHAR(255) PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            window_start BIGINT NOT NULL,
            tier VARCHAR(50) NOT NULL DEFAULT 'standard',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX ix_rate_limits_window_start ON rate_limits(window_start);
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 5,
        table_name: str = "rate_limits",
    ) -> None:
        """Initialize PostgreSQL rate limit storage.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Connection pool size
            table_name: Name of the rate limits table
        """
        self._database_url = database_url
        self._pool_size = pool_size
        self._table_name = table_name
        self._pool = None
        logger.info(
            f"PostgresRateLimitStorage initialized (pool_size={pool_size})"
        )

    async def connect(self) -> None:
        """Establish database connection pool.

        Raises:
            RuntimeError: If connection fails
        """
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=self._pool_size,
            )
            logger.info("PostgreSQL rate limit storage connection pool established")
        except ImportError:
            raise RuntimeError(
                "asyncpg not installed. Install with: pip install asyncpg"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to PostgreSQL: {e}")

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL rate limit storage connection pool closed")

    async def _ensure_connected(self) -> None:
        """Ensure connection pool is established."""
        if self._pool is None:
            await self.connect()

    async def increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitInfo:
        """Increment request count and return current limit info.

        Uses an upsert operation to atomically increment the counter
        or reset if the window has expired.

        Args:
            key: Unique key (tenant_id or API key)
            limit: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            Current rate limit information
        """
        await self._ensure_connected()

        current_time = int(time.time())
        window_start_threshold = current_time - window_seconds

        # Atomic upsert with conditional reset
        query = f"""
            INSERT INTO {self._table_name} (key, count, window_start, tier, updated_at)
            VALUES ($1, 1, $2, 'standard', NOW())
            ON CONFLICT (key) DO UPDATE SET
                count = CASE
                    WHEN {self._table_name}.window_start < $3 THEN 1
                    ELSE {self._table_name}.count + 1
                END,
                window_start = CASE
                    WHEN {self._table_name}.window_start < $3 THEN $2
                    ELSE {self._table_name}.window_start
                END,
                updated_at = NOW()
            RETURNING count, window_start, tier
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    key,
                    current_time,
                    window_start_threshold,
                )

            count = row["count"]
            window_start = row["window_start"]
            tier = row["tier"]

            remaining = max(0, limit - count)
            reset_at = window_start + window_seconds

            return RateLimitInfo(
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                tier=tier,
            )

        except Exception as e:
            logger.error(f"Rate limit increment failed: {e}")
            # Fail open - allow the request but log the error
            return RateLimitInfo(
                limit=limit,
                remaining=limit,
                reset_at=current_time + window_seconds,
                tier="standard",
            )

    async def get(self, key: str) -> Optional[RateLimitInfo]:
        """Get current rate limit info without incrementing.

        Args:
            key: Unique key

        Returns:
            Rate limit info or None if not found
        """
        await self._ensure_connected()

        query = f"""
            SELECT count, window_start, tier
            FROM {self._table_name}
            WHERE key = $1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, key)

            if row is None:
                return None

            # Default values
            limit = 60
            window_seconds = 60

            current_time = int(time.time())
            window_start = row["window_start"]
            reset_at = window_start + window_seconds

            # Check if window has expired
            if current_time >= reset_at:
                return RateLimitInfo(
                    limit=limit,
                    remaining=limit,
                    reset_at=current_time + window_seconds,
                    tier=row["tier"],
                )

            remaining = max(0, limit - row["count"])

            return RateLimitInfo(
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                tier=row["tier"],
            )

        except Exception as e:
            logger.error(f"Rate limit get failed: {e}")
            return None

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Unique key to reset
        """
        await self._ensure_connected()

        current_time = int(time.time())
        query = f"""
            UPDATE {self._table_name}
            SET count = 0, window_start = $2, updated_at = NOW()
            WHERE key = $1
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, key, current_time)
            logger.debug(f"Rate limit reset for key: {key}")
        except Exception as e:
            logger.error(f"Rate limit reset failed: {e}")

    async def get_all_keys(self) -> list:
        """Get all tracked keys.

        Returns:
            List of all keys being tracked
        """
        await self._ensure_connected()

        query = f"SELECT key FROM {self._table_name}"

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
            return [row["key"] for row in rows]
        except Exception as e:
            logger.error(f"Get all keys failed: {e}")
            return []

    async def set_tier(self, key: str, tier: str) -> None:
        """Set rate limit tier for a key.

        Args:
            key: Unique key
            tier: Tier name (free, standard, premium, unlimited)
        """
        await self._ensure_connected()

        current_time = int(time.time())
        query = f"""
            INSERT INTO {self._table_name} (key, count, window_start, tier, updated_at)
            VALUES ($1, 0, $2, $3, NOW())
            ON CONFLICT (key) DO UPDATE SET
                tier = $3,
                updated_at = NOW()
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, key, current_time, tier)
            logger.debug(f"Set tier for {key}: {tier}")
        except Exception as e:
            logger.error(f"Set tier failed: {e}")

    async def cleanup_expired(self, window_seconds: int = 3600) -> int:
        """Clean up expired rate limit entries.

        Args:
            window_seconds: Consider entries older than this as expired

        Returns:
            Number of entries removed
        """
        await self._ensure_connected()

        threshold = int(time.time()) - window_seconds
        query = f"""
            DELETE FROM {self._table_name}
            WHERE window_start < $1
        """

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, threshold)

            # Parse "DELETE n" to get count
            deleted = int(result.split()[-1])
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired rate limit entries")
            return deleted
        except Exception as e:
            logger.error(f"Cleanup expired failed: {e}")
            return 0

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
            logger.error(f"Rate limit storage health check failed: {e}")
            return False
