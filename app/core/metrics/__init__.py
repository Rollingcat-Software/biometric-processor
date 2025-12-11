"""Prometheus metrics for monitoring and observability.

This module provides comprehensive metrics collection including:
- HTTP request metrics (count, latency, active requests)
- Face operation metrics (enrollment, verification, detection)
- ML inference timing
- Infrastructure metrics (database, Redis, models)
- Process metrics (memory, CPU, GC)
- Health probes (readiness, liveness)
"""

from app.core.metrics.prometheus import (
    MetricsCollector,
    get_metrics,
    init_metrics,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    ACTIVE_REQUESTS,
    FACE_OPERATIONS,
    ML_INFERENCE_TIME,
    EMBEDDING_STORAGE_SIZE,
    ERROR_COUNT,
    RATE_LIMIT_HITS,
)

from app.core.metrics.infrastructure import (
    InfrastructureMonitor,
    get_infrastructure_monitor,
    HealthStatus,
    ComponentHealth,
    SystemHealth,
    # Database metrics
    DB_POOL_SIZE,
    DB_POOL_AVAILABLE,
    DB_POOL_USED,
    DB_QUERY_TIME,
    DB_CONNECTION_ERRORS,
    DB_CONNECTED,
    # Redis metrics
    REDIS_CONNECTED,
    REDIS_LATENCY,
    REDIS_MEMORY_USED,
    REDIS_KEYS_COUNT,
    REDIS_OPERATIONS,
    # Model metrics
    MODEL_LOADED,
    MODEL_LOAD_TIME,
    MODEL_MEMORY_USAGE,
    MODEL_LAST_USED,
)

from app.core.metrics.health_probes import (
    DatabaseHealthChecker,
    RedisHealthChecker,
    MLModelHealthChecker,
    get_db_health_checker,
    get_redis_health_checker,
    get_model_health_checker,
    setup_health_checks,
)

from app.core.metrics.process import (
    ProcessMetricsCollector,
    get_process_collector,
    start_process_metrics,
    stop_process_metrics,
    PROCESS_MEMORY_RSS,
    PROCESS_MEMORY_VMS,
    PROCESS_MEMORY_PERCENT,
    PROCESS_CPU_PERCENT,
    PROCESS_CPU_TIME_USER,
    PROCESS_CPU_TIME_SYSTEM,
    PROCESS_THREADS,
    PROCESS_FDS,
    PROCESS_UPTIME,
)

__all__ = [
    # Core metrics
    "MetricsCollector",
    "get_metrics",
    "init_metrics",
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "ACTIVE_REQUESTS",
    "FACE_OPERATIONS",
    "ML_INFERENCE_TIME",
    "EMBEDDING_STORAGE_SIZE",
    "ERROR_COUNT",
    "RATE_LIMIT_HITS",
    # Infrastructure
    "InfrastructureMonitor",
    "get_infrastructure_monitor",
    "HealthStatus",
    "ComponentHealth",
    "SystemHealth",
    # Database metrics
    "DB_POOL_SIZE",
    "DB_POOL_AVAILABLE",
    "DB_POOL_USED",
    "DB_QUERY_TIME",
    "DB_CONNECTION_ERRORS",
    "DB_CONNECTED",
    # Redis metrics
    "REDIS_CONNECTED",
    "REDIS_LATENCY",
    "REDIS_MEMORY_USED",
    "REDIS_KEYS_COUNT",
    "REDIS_OPERATIONS",
    # Model metrics
    "MODEL_LOADED",
    "MODEL_LOAD_TIME",
    "MODEL_MEMORY_USAGE",
    "MODEL_LAST_USED",
    # Health probes
    "DatabaseHealthChecker",
    "RedisHealthChecker",
    "MLModelHealthChecker",
    "get_db_health_checker",
    "get_redis_health_checker",
    "get_model_health_checker",
    "setup_health_checks",
    # Process metrics
    "ProcessMetricsCollector",
    "get_process_collector",
    "start_process_metrics",
    "stop_process_metrics",
    "PROCESS_MEMORY_RSS",
    "PROCESS_MEMORY_VMS",
    "PROCESS_MEMORY_PERCENT",
    "PROCESS_CPU_PERCENT",
    "PROCESS_CPU_TIME_USER",
    "PROCESS_CPU_TIME_SYSTEM",
    "PROCESS_THREADS",
    "PROCESS_FDS",
    "PROCESS_UPTIME",
]
