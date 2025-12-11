"""Process metrics for memory, CPU, and system resource monitoring.

Extends prometheus_client process metrics with application-specific tracking.
"""

import gc
import logging
import os
import platform
import sys
import threading
import time
from typing import Optional

from prometheus_client import Gauge, Counter, REGISTRY

logger = logging.getLogger(__name__)


# ============================================================================
# Process Metrics
# ============================================================================

# Memory metrics
PROCESS_MEMORY_RSS = Gauge(
    "biometric_process_memory_rss_bytes",
    "Resident Set Size - memory actually used by process",
)

PROCESS_MEMORY_VMS = Gauge(
    "biometric_process_memory_vms_bytes",
    "Virtual Memory Size - total virtual memory used",
)

PROCESS_MEMORY_PERCENT = Gauge(
    "biometric_process_memory_percent",
    "Percentage of system memory used by process",
)

# CPU metrics
PROCESS_CPU_PERCENT = Gauge(
    "biometric_process_cpu_percent",
    "CPU usage percentage of process",
)

PROCESS_CPU_TIME_USER = Gauge(
    "biometric_process_cpu_user_seconds_total",
    "CPU time spent in user mode",
)

PROCESS_CPU_TIME_SYSTEM = Gauge(
    "biometric_process_cpu_system_seconds_total",
    "CPU time spent in system mode",
)

# Thread metrics
PROCESS_THREADS = Gauge(
    "biometric_process_threads",
    "Number of threads used by process",
)

# File descriptor metrics
PROCESS_FDS = Gauge(
    "biometric_process_open_fds",
    "Number of open file descriptors",
)

PROCESS_FDS_MAX = Gauge(
    "biometric_process_max_fds",
    "Maximum number of file descriptors",
)

# GC metrics
GC_COLLECTIONS = Counter(
    "biometric_gc_collections_total",
    "Total garbage collection runs",
    ["generation"],
)

GC_COLLECTED_OBJECTS = Counter(
    "biometric_gc_collected_objects_total",
    "Total objects collected by GC",
    ["generation"],
)

GC_UNCOLLECTABLE = Gauge(
    "biometric_gc_uncollectable_objects",
    "Number of uncollectable objects",
)

# Uptime
PROCESS_START_TIME = Gauge(
    "biometric_process_start_time_seconds",
    "Unix timestamp when process started",
)

PROCESS_UPTIME = Gauge(
    "biometric_process_uptime_seconds",
    "Process uptime in seconds",
)


class ProcessMetricsCollector:
    """Collector for process-level metrics.

    Periodically collects memory, CPU, and other process metrics.
    """

    def __init__(self, collection_interval: float = 15.0):
        """Initialize the process metrics collector.

        Args:
            collection_interval: Interval between metric collections in seconds
        """
        self._interval = collection_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()
        self._last_gc_stats = {0: 0, 1: 0, 2: 0}

        # Set start time
        PROCESS_START_TIME.set(self._start_time)

        # Check for psutil availability
        self._psutil_available = False
        try:
            import psutil
            self._psutil_available = True
            self._process = psutil.Process()
        except ImportError:
            logger.warning(
                "psutil not available - process metrics will be limited. "
                "Install with: pip install psutil"
            )
            self._process = None

    def start(self) -> None:
        """Start background metric collection."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._collection_loop,
            daemon=True,
            name="ProcessMetricsCollector",
        )
        self._thread.start()
        logger.info(f"Process metrics collector started (interval: {self._interval}s)")

    def stop(self) -> None:
        """Stop background metric collection."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Process metrics collector stopped")

    def _collection_loop(self) -> None:
        """Background collection loop."""
        while self._running:
            try:
                self.collect()
            except Exception as e:
                logger.error(f"Error collecting process metrics: {e}")

            time.sleep(self._interval)

    def collect(self) -> None:
        """Collect all process metrics."""
        self._collect_uptime()
        self._collect_gc_metrics()
        self._collect_thread_metrics()

        if self._psutil_available:
            self._collect_memory_metrics()
            self._collect_cpu_metrics()
            self._collect_fd_metrics()
        else:
            self._collect_basic_memory_metrics()

    def _collect_uptime(self) -> None:
        """Collect uptime metric."""
        uptime = time.time() - self._start_time
        PROCESS_UPTIME.set(uptime)

    def _collect_gc_metrics(self) -> None:
        """Collect garbage collection metrics."""
        gc_stats = gc.get_stats()

        for gen, stats in enumerate(gc_stats):
            collections = stats.get("collections", 0)
            collected = stats.get("collected", 0)

            # Calculate delta since last collection
            prev_collections = self._last_gc_stats.get(gen, 0)
            if collections > prev_collections:
                GC_COLLECTIONS.labels(generation=str(gen)).inc(
                    collections - prev_collections
                )
            self._last_gc_stats[gen] = collections

            # Record collected objects
            GC_COLLECTED_OBJECTS.labels(generation=str(gen))._value.set(collected)

        # Uncollectable objects
        GC_UNCOLLECTABLE.set(len(gc.garbage))

    def _collect_thread_metrics(self) -> None:
        """Collect thread metrics."""
        PROCESS_THREADS.set(threading.active_count())

    def _collect_memory_metrics(self) -> None:
        """Collect memory metrics using psutil."""
        try:
            mem_info = self._process.memory_info()
            PROCESS_MEMORY_RSS.set(mem_info.rss)
            PROCESS_MEMORY_VMS.set(mem_info.vms)

            mem_percent = self._process.memory_percent()
            PROCESS_MEMORY_PERCENT.set(mem_percent)

        except Exception as e:
            logger.debug(f"Error collecting memory metrics: {e}")

    def _collect_basic_memory_metrics(self) -> None:
        """Collect basic memory metrics without psutil."""
        try:
            # Try to read from /proc on Linux
            if platform.system() == "Linux":
                with open(f"/proc/{os.getpid()}/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_kb = int(line.split()[1])
                            PROCESS_MEMORY_RSS.set(rss_kb * 1024)
                        elif line.startswith("VmSize:"):
                            vms_kb = int(line.split()[1])
                            PROCESS_MEMORY_VMS.set(vms_kb * 1024)
        except Exception:
            pass

    def _collect_cpu_metrics(self) -> None:
        """Collect CPU metrics using psutil."""
        try:
            cpu_percent = self._process.cpu_percent()
            PROCESS_CPU_PERCENT.set(cpu_percent)

            cpu_times = self._process.cpu_times()
            PROCESS_CPU_TIME_USER.set(cpu_times.user)
            PROCESS_CPU_TIME_SYSTEM.set(cpu_times.system)

        except Exception as e:
            logger.debug(f"Error collecting CPU metrics: {e}")

    def _collect_fd_metrics(self) -> None:
        """Collect file descriptor metrics."""
        try:
            if platform.system() != "Windows":
                num_fds = self._process.num_fds()
                PROCESS_FDS.set(num_fds)

                # Get max FDs
                import resource
                soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                PROCESS_FDS_MAX.set(soft_limit)

        except Exception as e:
            logger.debug(f"Error collecting FD metrics: {e}")


# Singleton instance
_process_collector: Optional[ProcessMetricsCollector] = None


def get_process_collector() -> ProcessMetricsCollector:
    """Get the global process metrics collector.

    Returns:
        ProcessMetricsCollector singleton
    """
    global _process_collector
    if _process_collector is None:
        _process_collector = ProcessMetricsCollector()
    return _process_collector


def start_process_metrics(interval: float = 15.0) -> ProcessMetricsCollector:
    """Start collecting process metrics.

    Args:
        interval: Collection interval in seconds

    Returns:
        ProcessMetricsCollector instance
    """
    collector = get_process_collector()
    collector._interval = interval
    collector.start()
    return collector


def stop_process_metrics() -> None:
    """Stop collecting process metrics."""
    collector = get_process_collector()
    collector.stop()
