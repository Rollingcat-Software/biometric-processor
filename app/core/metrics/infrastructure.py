"""Infrastructure metrics for database, Redis, and ML models.

Provides health checks and metrics for all infrastructure dependencies.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from prometheus_client import Gauge, Counter, Info

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health status."""

    status: HealthStatus
    components: List[ComponentHealth]
    timestamp: float = field(default_factory=time.time)

    @property
    def is_ready(self) -> bool:
        """Check if system is ready to serve traffic."""
        critical_components = ["database", "redis"]
        for component in self.components:
            if component.name in critical_components:
                if component.status == HealthStatus.UNHEALTHY:
                    return False
        return True

    @property
    def is_live(self) -> bool:
        """Check if system is alive (basic liveness)."""
        return self.status != HealthStatus.UNHEALTHY


# ============================================================================
# Infrastructure Metrics
# ============================================================================

# Database metrics
DB_POOL_SIZE = Gauge(
    "biometric_db_pool_size",
    "Database connection pool size",
    ["pool_name"],
)

DB_POOL_AVAILABLE = Gauge(
    "biometric_db_pool_available",
    "Available connections in database pool",
    ["pool_name"],
)

DB_POOL_USED = Gauge(
    "biometric_db_pool_used",
    "Used connections in database pool",
    ["pool_name"],
)

DB_QUERY_TIME = Gauge(
    "biometric_db_query_latency_seconds",
    "Database query latency in seconds",
    ["operation"],
)

DB_CONNECTION_ERRORS = Counter(
    "biometric_db_connection_errors_total",
    "Total database connection errors",
    ["error_type"],
)

DB_CONNECTED = Gauge(
    "biometric_db_connected",
    "Database connection status (1=connected, 0=disconnected)",
)

# Redis metrics
REDIS_CONNECTED = Gauge(
    "biometric_redis_connected",
    "Redis connection status (1=connected, 0=disconnected)",
)

REDIS_LATENCY = Gauge(
    "biometric_redis_latency_seconds",
    "Redis ping latency in seconds",
)

REDIS_MEMORY_USED = Gauge(
    "biometric_redis_memory_used_bytes",
    "Redis memory usage in bytes",
)

REDIS_KEYS_COUNT = Gauge(
    "biometric_redis_keys_total",
    "Total keys in Redis",
    ["db"],
)

REDIS_OPERATIONS = Counter(
    "biometric_redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],
)

# ML Model metrics
MODEL_LOADED = Gauge(
    "biometric_ml_model_loaded",
    "ML model loading status (1=loaded, 0=not loaded)",
    ["model_name", "model_type"],
)

MODEL_LOAD_TIME = Gauge(
    "biometric_ml_model_load_time_seconds",
    "Time taken to load ML model",
    ["model_name"],
)

MODEL_MEMORY_USAGE = Gauge(
    "biometric_ml_model_memory_bytes",
    "Estimated memory usage of ML model",
    ["model_name"],
)

MODEL_LAST_USED = Gauge(
    "biometric_ml_model_last_used_timestamp",
    "Timestamp of last model usage",
    ["model_name"],
)

# System info
SYSTEM_INFO = Info(
    "biometric_system",
    "System information",
)


class InfrastructureMonitor:
    """Monitor infrastructure health and collect metrics.

    Provides health checks for database, Redis, and ML models.
    """

    def __init__(self):
        """Initialize the infrastructure monitor."""
        self._health_checks: Dict[str, Callable] = {}
        self._model_status: Dict[str, bool] = {}
        self._initialized = False

    def init(
        self,
        python_version: str,
        platform: str,
        cpu_count: int,
    ) -> None:
        """Initialize system info metrics.

        Args:
            python_version: Python version string
            platform: Platform/OS name
            cpu_count: Number of CPUs
        """
        if self._initialized:
            return

        SYSTEM_INFO.info({
            "python_version": python_version,
            "platform": platform,
            "cpu_count": str(cpu_count),
        })
        self._initialized = True
        logger.info("Infrastructure monitor initialized")

    def register_health_check(
        self,
        name: str,
        check_fn: Callable[[], ComponentHealth],
    ) -> None:
        """Register a health check function.

        Args:
            name: Component name
            check_fn: Async or sync function returning ComponentHealth
        """
        self._health_checks[name] = check_fn
        logger.debug(f"Registered health check: {name}")

    async def check_health(self) -> SystemHealth:
        """Run all health checks and return system health.

        Returns:
            SystemHealth with all component statuses
        """
        components = []
        overall_status = HealthStatus.HEALTHY

        for name, check_fn in self._health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_fn):
                    health = await check_fn()
                else:
                    health = check_fn()
                components.append(health)

                if health.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif health.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED

            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                components.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                ))
                overall_status = HealthStatus.UNHEALTHY

        return SystemHealth(
            status=overall_status,
            components=components,
        )

    # =========================================================================
    # Database Metrics
    # =========================================================================

    def record_db_pool_stats(
        self,
        pool_name: str,
        size: int,
        available: int,
        used: int,
    ) -> None:
        """Record database connection pool statistics.

        Args:
            pool_name: Pool identifier
            size: Total pool size
            available: Available connections
            used: Used connections
        """
        DB_POOL_SIZE.labels(pool_name=pool_name).set(size)
        DB_POOL_AVAILABLE.labels(pool_name=pool_name).set(available)
        DB_POOL_USED.labels(pool_name=pool_name).set(used)

    def record_db_query_time(self, operation: str, duration: float) -> None:
        """Record database query latency.

        Args:
            operation: Query operation type
            duration: Query duration in seconds
        """
        DB_QUERY_TIME.labels(operation=operation).set(duration)

    def record_db_connection_error(self, error_type: str) -> None:
        """Record a database connection error.

        Args:
            error_type: Type of error
        """
        DB_CONNECTION_ERRORS.labels(error_type=error_type).inc()

    def set_db_connected(self, connected: bool) -> None:
        """Set database connection status.

        Args:
            connected: Whether database is connected
        """
        DB_CONNECTED.set(1 if connected else 0)

    # =========================================================================
    # Redis Metrics
    # =========================================================================

    def set_redis_connected(self, connected: bool) -> None:
        """Set Redis connection status.

        Args:
            connected: Whether Redis is connected
        """
        REDIS_CONNECTED.set(1 if connected else 0)

    def record_redis_latency(self, latency: float) -> None:
        """Record Redis ping latency.

        Args:
            latency: Ping latency in seconds
        """
        REDIS_LATENCY.set(latency)

    def record_redis_memory(self, bytes_used: int) -> None:
        """Record Redis memory usage.

        Args:
            bytes_used: Memory usage in bytes
        """
        REDIS_MEMORY_USED.set(bytes_used)

    def record_redis_keys(self, db: str, count: int) -> None:
        """Record Redis key count.

        Args:
            db: Database number
            count: Number of keys
        """
        REDIS_KEYS_COUNT.labels(db=db).set(count)

    def record_redis_operation(self, operation: str, success: bool) -> None:
        """Record a Redis operation.

        Args:
            operation: Operation type
            success: Whether operation succeeded
        """
        status = "success" if success else "failure"
        REDIS_OPERATIONS.labels(operation=operation, status=status).inc()

    # =========================================================================
    # ML Model Metrics
    # =========================================================================

    def set_model_loaded(
        self,
        model_name: str,
        model_type: str,
        loaded: bool,
    ) -> None:
        """Set ML model loading status.

        Args:
            model_name: Model identifier
            model_type: Type of model (detector, recognizer, etc.)
            loaded: Whether model is loaded
        """
        MODEL_LOADED.labels(model_name=model_name, model_type=model_type).set(
            1 if loaded else 0
        )
        self._model_status[model_name] = loaded

    def record_model_load_time(self, model_name: str, duration: float) -> None:
        """Record model loading time.

        Args:
            model_name: Model identifier
            duration: Load time in seconds
        """
        MODEL_LOAD_TIME.labels(model_name=model_name).set(duration)

    def record_model_memory(self, model_name: str, bytes_used: int) -> None:
        """Record model memory usage.

        Args:
            model_name: Model identifier
            bytes_used: Memory usage in bytes
        """
        MODEL_MEMORY_USAGE.labels(model_name=model_name).set(bytes_used)

    def record_model_used(self, model_name: str) -> None:
        """Record model usage timestamp.

        Args:
            model_name: Model identifier
        """
        MODEL_LAST_USED.labels(model_name=model_name).set(time.time())

    def get_model_status(self) -> Dict[str, bool]:
        """Get all model loading statuses.

        Returns:
            Dictionary of model_name -> loaded status
        """
        return self._model_status.copy()


# Singleton instance
_infrastructure_monitor: Optional[InfrastructureMonitor] = None


def get_infrastructure_monitor() -> InfrastructureMonitor:
    """Get the global infrastructure monitor instance.

    Returns:
        InfrastructureMonitor singleton
    """
    global _infrastructure_monitor
    if _infrastructure_monitor is None:
        _infrastructure_monitor = InfrastructureMonitor()
    return _infrastructure_monitor
