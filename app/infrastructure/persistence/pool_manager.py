"""PostgreSQL connection pool manager."""

import logging
from typing import Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger(__name__)


class DatabasePoolManager:
    """Manage PostgreSQL connection pool lifecycle.

    Provides connection pooling, health checks, and graceful shutdown.
    Uses asyncpg for async PostgreSQL operations.
    """

    def __init__(
        self,
        database_url: str,
        min_size: int = 5,
        max_size: int = 20,
        max_queries: int = 50000,
        max_inactive_lifetime: int = 300,
        command_timeout: int = 60,
    ):
        """Initialize the pool manager.

        Args:
            database_url: PostgreSQL connection string
            min_size: Minimum pool size
            max_size: Maximum pool size
            max_queries: Max queries per connection before recycling
            max_inactive_lifetime: Max seconds a connection can be idle
            command_timeout: Default command timeout in seconds
        """
        if asyncpg is None:
            raise ImportError("asyncpg is required for PostgreSQL support")

        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._max_queries = max_queries
        self._max_inactive_lifetime = max_inactive_lifetime
        self._command_timeout = command_timeout
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Create and initialize the connection pool.

        Should be called during application startup.
        """
        if self._initialized:
            logger.warning("Pool already initialized")
            return

        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._database_url,
                min_size=self._min_size,
                max_size=self._max_size,
                max_queries=self._max_queries,
                max_inactive_connection_lifetime=self._max_inactive_lifetime,
                command_timeout=self._command_timeout,
            )
            self._initialized = True
            logger.info(
                f"Database pool initialized: min={self._min_size}, max={self._max_size}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self) -> None:
        """Close the connection pool gracefully.

        Should be called during application shutdown.
        """
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Database pool closed")

    async def health_check(self) -> bool:
        """Check if the database connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        if not self._pool:
            return False

        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    @property
    def pool(self) -> Optional[asyncpg.Pool]:
        """Get the connection pool.

        Returns:
            The asyncpg pool, or None if not initialized
        """
        return self._pool

    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized.

        Returns:
            True if initialized
        """
        return self._initialized

    def get_stats(self) -> dict:
        """Get pool statistics.

        Returns:
            Dictionary with pool stats
        """
        if not self._pool:
            return {
                "initialized": False,
                "size": 0,
                "free_size": 0,
                "used_size": 0,
            }

        return {
            "initialized": True,
            "size": self._pool.get_size(),
            "free_size": self._pool.get_idle_size(),
            "used_size": self._pool.get_size() - self._pool.get_idle_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
        }


# Global pool manager instance
_pool_manager: Optional[DatabasePoolManager] = None


def get_pool_manager() -> Optional[DatabasePoolManager]:
    """Get the global pool manager instance.

    Returns:
        The pool manager, or None if not configured
    """
    return _pool_manager


async def init_pool_manager(
    database_url: str,
    min_size: int = 5,
    max_size: int = 20,
) -> DatabasePoolManager:
    """Initialize the global pool manager.

    Args:
        database_url: PostgreSQL connection string
        min_size: Minimum pool size
        max_size: Maximum pool size

    Returns:
        Initialized pool manager
    """
    global _pool_manager

    if _pool_manager is not None:
        logger.warning("Pool manager already initialized, closing existing")
        await _pool_manager.close()

    _pool_manager = DatabasePoolManager(
        database_url=database_url,
        min_size=min_size,
        max_size=max_size,
    )
    await _pool_manager.initialize()

    return _pool_manager


async def close_pool_manager() -> None:
    """Close the global pool manager."""
    global _pool_manager

    if _pool_manager:
        await _pool_manager.close()
        _pool_manager = None
