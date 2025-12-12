"""SQLAlchemy async session management.

Provides async database session factory and dependency injection.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://biometric:biometric@localhost:5432/biometric"
)

# Convert standard postgres URL to asyncpg format if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


class AsyncSessionFactory:
    """Factory for creating async database sessions.

    Manages database engine lifecycle and session creation.
    """

    def __init__(
        self,
        database_url: str = DATABASE_URL,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
    ):
        """Initialize session factory.

        Args:
            database_url: Database connection URL.
            echo: Enable SQL logging.
            pool_size: Connection pool size.
            max_overflow: Max connections above pool_size.
            pool_timeout: Timeout for getting connection.
            pool_recycle: Recycle connections after seconds.
            pool_pre_ping: Enable connection health checks.
        """
        self._database_url = database_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

        # Engine configuration
        self._engine_kwargs = {
            "echo": echo,
            "pool_pre_ping": pool_pre_ping,
            "pool_recycle": pool_recycle,
        }

        # Use queue pool for production, null pool for testing
        if os.getenv("TESTING", "").lower() == "true":
            self._engine_kwargs["poolclass"] = NullPool
        else:
            self._engine_kwargs.update({
                "pool_size": pool_size,
                "max_overflow": max_overflow,
                "pool_timeout": pool_timeout,
            })

    async def initialize(self) -> None:
        """Initialize database engine and session factory."""
        if self._engine is not None:
            return

        logger.info(f"Initializing database connection: {self._database_url[:50]}...")

        self._engine = create_async_engine(
            self._database_url,
            **self._engine_kwargs,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        logger.info("Database connection initialized")

    async def close(self) -> None:
        """Close database engine and release connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session context manager.

        Yields:
            Async database session.

        Raises:
            RuntimeError: If factory not initialized.
        """
        if self._session_factory is None:
            await self.initialize()

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @property
    def engine(self) -> Optional[AsyncEngine]:
        """Get the database engine."""
        return self._engine


# Global session factory instance
_session_factory: Optional[AsyncSessionFactory] = None


async def init_db(database_url: Optional[str] = None) -> AsyncSessionFactory:
    """Initialize the global database session factory.

    Args:
        database_url: Optional database URL override.

    Returns:
        Initialized session factory.
    """
    global _session_factory

    if _session_factory is None:
        url = database_url or DATABASE_URL
        _session_factory = AsyncSessionFactory(database_url=url)
        await _session_factory.initialize()

    return _session_factory


async def close_db() -> None:
    """Close the global database connection."""
    global _session_factory

    if _session_factory is not None:
        await _session_factory.close()
        _session_factory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for async database session.

    Yields:
        Async database session.

    Example:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    global _session_factory

    if _session_factory is None:
        await init_db()

    async with _session_factory.session() as session:
        yield session


# Alias for FastAPI dependency
get_db = get_async_session
