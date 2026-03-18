"""Health probe implementations for Kubernetes-style readiness and liveness checks.

Provides detailed health checks for all infrastructure dependencies.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from app.core.metrics.infrastructure import (
    ComponentHealth,
    HealthStatus,
    get_infrastructure_monitor,
)

logger = logging.getLogger(__name__)


class DatabaseHealthChecker:
    """Health checker for PostgreSQL database connections."""

    def __init__(
        self,
        pool: Optional[Any] = None,
        timeout: float = 5.0,
    ):
        """Initialize the database health checker.

        Args:
            pool: asyncpg connection pool
            timeout: Health check timeout in seconds
        """
        self._pool = pool
        self._timeout = timeout
        self._monitor = get_infrastructure_monitor()

    def set_pool(self, pool: Any) -> None:
        """Set the database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool

    async def check(self) -> ComponentHealth:
        """Check database health.

        Returns:
            ComponentHealth with database status
        """
        if self._pool is None:
            self._monitor.set_db_connected(False)
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message="Database pool not initialized",
            )

        start_time = time.time()

        try:
            # Execute a simple query with timeout
            async with asyncio.timeout(self._timeout):
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")

            latency = (time.time() - start_time) * 1000

            # Record pool stats
            pool_size = self._pool.get_size()
            pool_free = self._pool.get_idle_size()
            pool_used = pool_size - pool_free

            self._monitor.record_db_pool_stats(
                pool_name="main",
                size=pool_size,
                available=pool_free,
                used=pool_used,
            )
            self._monitor.record_db_query_time("health_check", latency / 1000)
            self._monitor.set_db_connected(True)

            # Determine status based on pool utilization
            utilization = pool_used / max(pool_size, 1)
            if utilization > 0.9:
                status = HealthStatus.DEGRADED
                message = f"High pool utilization: {utilization:.0%}"
            else:
                status = HealthStatus.HEALTHY
                message = "Database connection healthy"

            return ComponentHealth(
                name="database",
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "pool_size": pool_size,
                    "pool_available": pool_free,
                    "pool_used": pool_used,
                    "utilization": f"{utilization:.0%}",
                },
            )

        except asyncio.TimeoutError:
            self._monitor.set_db_connected(False)
            self._monitor.record_db_connection_error("timeout")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start_time) * 1000,
                message=f"Database health check timed out after {self._timeout}s",
            )

        except Exception as e:
            self._monitor.set_db_connected(False)
            self._monitor.record_db_connection_error(type(e).__name__)
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start_time) * 1000,
                message=f"Database error: {str(e)}",
            )


class RedisHealthChecker:
    """Health checker for Redis connections."""

    def __init__(
        self,
        client: Optional[Any] = None,
        timeout: float = 2.0,
    ):
        """Initialize the Redis health checker.

        Args:
            client: Redis client instance
            timeout: Health check timeout in seconds
        """
        self._client = client
        self._timeout = timeout
        self._monitor = get_infrastructure_monitor()

    def set_client(self, client: Any) -> None:
        """Set the Redis client.

        Args:
            client: Redis client instance
        """
        self._client = client

    async def check(self) -> ComponentHealth:
        """Check Redis health.

        Returns:
            ComponentHealth with Redis status
        """
        if self._client is None:
            self._monitor.set_redis_connected(False)
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message="Redis client not initialized",
            )

        start_time = time.time()

        try:
            # Ping Redis with timeout
            async with asyncio.timeout(self._timeout):
                pong = await self._client.ping()

            latency = (time.time() - start_time) * 1000

            if not pong:
                self._monitor.set_redis_connected(False)
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency,
                    message="Redis ping failed",
                )

            # Get Redis info for additional metrics
            try:
                info = await self._client.info("memory")
                memory_used = info.get("used_memory", 0)
                self._monitor.record_redis_memory(memory_used)

                # Get key count
                db_info = await self._client.info("keyspace")
                for db_name, db_stats in db_info.items():
                    if db_name.startswith("db"):
                        keys = db_stats.get("keys", 0) if isinstance(db_stats, dict) else 0
                        self._monitor.record_redis_keys(db_name, keys)

            except Exception:
                memory_used = 0

            self._monitor.set_redis_connected(True)
            self._monitor.record_redis_latency(latency / 1000)

            # Check latency for degraded status
            if latency > 100:  # More than 100ms
                status = HealthStatus.DEGRADED
                message = f"High Redis latency: {latency:.1f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = "Redis connection healthy"

            return ComponentHealth(
                name="redis",
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "memory_used_bytes": memory_used,
                    "memory_used_human": f"{memory_used / 1024 / 1024:.1f}MB",
                },
            )

        except asyncio.TimeoutError:
            self._monitor.set_redis_connected(False)
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start_time) * 1000,
                message=f"Redis health check timed out after {self._timeout}s",
            )

        except Exception as e:
            self._monitor.set_redis_connected(False)
            logger.error(f"Redis health check failed: {e}")
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start_time) * 1000,
                message=f"Redis error: {str(e)}",
            )


class MLModelHealthChecker:
    """Health checker for ML model loading status."""

    def __init__(self):
        """Initialize the ML model health checker."""
        self._monitor = get_infrastructure_monitor()
        self._models: Dict[str, Dict[str, Any]] = {}

    def register_model(
        self,
        model_name: str,
        model_type: str,
        check_fn: Optional[callable] = None,
    ) -> None:
        """Register an ML model for health checking.

        Args:
            model_name: Model identifier
            model_type: Type of model
            check_fn: Optional function to check if model is ready
        """
        self._models[model_name] = {
            "type": model_type,
            "check_fn": check_fn,
            "loaded": False,
        }

    def set_model_loaded(
        self,
        model_name: str,
        loaded: bool,
        load_time: Optional[float] = None,
        memory_bytes: Optional[int] = None,
    ) -> None:
        """Update model loading status.

        Args:
            model_name: Model identifier
            loaded: Whether model is loaded
            load_time: Time taken to load model
            memory_bytes: Memory used by model
        """
        if model_name in self._models:
            self._models[model_name]["loaded"] = loaded
            model_type = self._models[model_name]["type"]
        else:
            model_type = "unknown"
            self._models[model_name] = {
                "type": model_type,
                "check_fn": None,
                "loaded": loaded,
            }

        self._monitor.set_model_loaded(model_name, model_type, loaded)

        if load_time is not None:
            self._monitor.record_model_load_time(model_name, load_time)

        if memory_bytes is not None:
            self._monitor.record_model_memory(model_name, memory_bytes)

    def check(self) -> ComponentHealth:
        """Check ML models health.

        Returns:
            ComponentHealth with models status
        """
        if not self._models:
            return ComponentHealth(
                name="ml_models",
                status=HealthStatus.HEALTHY,
                message="No models registered",
            )

        loaded_count = 0
        total_count = len(self._models)
        model_statuses = {}

        for model_name, model_info in self._models.items():
            is_loaded = model_info["loaded"]

            # Run custom check if available
            check_fn = model_info.get("check_fn")
            if check_fn is not None:
                try:
                    is_loaded = check_fn()
                except Exception as e:
                    logger.warning(f"Model check failed for {model_name}: {e}")
                    is_loaded = False

            model_statuses[model_name] = is_loaded
            if is_loaded:
                loaded_count += 1

            # Update metrics
            self._monitor.set_model_loaded(
                model_name,
                model_info["type"],
                is_loaded,
            )

        # Determine overall status
        if loaded_count == total_count:
            status = HealthStatus.HEALTHY
            message = f"All {total_count} models loaded"
        elif loaded_count > 0:
            status = HealthStatus.DEGRADED
            message = f"{loaded_count}/{total_count} models loaded"
        else:
            status = HealthStatus.UNHEALTHY
            message = "No models loaded"

        return ComponentHealth(
            name="ml_models",
            status=status,
            message=message,
            details={
                "models": model_statuses,
                "loaded_count": loaded_count,
                "total_count": total_count,
            },
        )


# Global health checker instances
_db_checker: Optional[DatabaseHealthChecker] = None
_redis_checker: Optional[RedisHealthChecker] = None
_model_checker: Optional[MLModelHealthChecker] = None


def get_db_health_checker() -> DatabaseHealthChecker:
    """Get the database health checker singleton."""
    global _db_checker
    if _db_checker is None:
        _db_checker = DatabaseHealthChecker()
    return _db_checker


def get_redis_health_checker() -> RedisHealthChecker:
    """Get the Redis health checker singleton."""
    global _redis_checker
    if _redis_checker is None:
        _redis_checker = RedisHealthChecker()
    return _redis_checker


def get_model_health_checker() -> MLModelHealthChecker:
    """Get the ML model health checker singleton."""
    global _model_checker
    if _model_checker is None:
        _model_checker = MLModelHealthChecker()
    return _model_checker


def setup_health_checks() -> None:
    """Setup all health checks with the infrastructure monitor."""
    monitor = get_infrastructure_monitor()

    # Register health checks
    monitor.register_health_check("database", get_db_health_checker().check)
    monitor.register_health_check("redis", get_redis_health_checker().check)
    monitor.register_health_check("ml_models", get_model_health_checker().check)

    logger.info("Health checks registered")
