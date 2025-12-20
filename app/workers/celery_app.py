"""Celery application configuration.

This module configures Celery for distributed task processing.
Supports Redis as both broker and result backend.
"""

import os
import logging
from celery import Celery
from kombu import Queue, Exchange

logger = logging.getLogger(__name__)

# Redis connection settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_RESULT_BACKEND = os.getenv("REDIS_RESULT_BACKEND", REDIS_URL)

# Create Celery app
celery_app = Celery(
    "biometric_processor",
    broker=REDIS_URL,
    backend=REDIS_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=540,  # 9 minutes soft limit

    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    worker_max_tasks_per_child=100,

    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,

    # Queue settings
    task_default_queue="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("high_priority", Exchange("high_priority"), routing_key="high_priority"),
        Queue("batch", Exchange("batch"), routing_key="batch"),
        Queue("proctoring", Exchange("proctoring"), routing_key="proctoring"),
        Queue("reports", Exchange("reports"), routing_key="reports"),
    ),

    # Task routing
    task_routes={
        "app.workers.tasks.batch_enroll_task": {"queue": "batch"},
        "app.workers.tasks.batch_verify_task": {"queue": "batch"},
        "app.workers.tasks.process_frame_task": {"queue": "proctoring"},
        "app.workers.tasks.analyze_session_task": {"queue": "proctoring"},
        "app.workers.tasks.generate_report_task": {"queue": "reports"},
        "app.workers.tasks.cleanup_expired_sessions_task": {"queue": "default"},
    },

    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-expired-sessions": {
            "task": "app.workers.tasks.cleanup_expired_sessions_task",
            "schedule": 3600.0,  # Run every hour
        },
        "generate-daily-reports": {
            "task": "app.workers.tasks.generate_report_task",
            "schedule": 86400.0,  # Run daily
            "args": ["daily"],
        },
    },

    # Monitoring and events
    worker_send_task_events=True,
    task_send_sent_event=True,
)


def get_celery_app() -> Celery:
    """Get the Celery application instance.

    Returns:
        Configured Celery app.
    """
    return celery_app


def check_celery_health() -> dict:
    """Check Celery worker health.

    Returns:
        Dictionary with health status and worker info.
    """
    try:
        # Ping workers
        inspect = celery_app.control.inspect()
        ping_result = inspect.ping()

        if ping_result:
            workers = list(ping_result.keys())
            active_tasks = inspect.active()

            return {
                "status": "healthy",
                "workers": len(workers),
                "worker_names": workers,
                "active_tasks": sum(
                    len(tasks) for tasks in (active_tasks or {}).values()
                ),
            }
        else:
            return {
                "status": "unhealthy",
                "workers": 0,
                "error": "No workers responding",
            }
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return {
            "status": "error",
            "workers": 0,
            "error": str(e),
        }
