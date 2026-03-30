"""GPU metrics collection for Prometheus.

Collects and exposes GPU metrics including memory usage, utilization,
and temperature for monitoring and alerting purposes.
"""

import asyncio
import subprocess
import logging
from typing import Optional

from prometheus_client import Gauge, Info

logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus Metrics
# =============================================================================

gpu_memory_used = Gauge(
    "biometric_gpu_memory_used_bytes",
    "GPU memory currently used",
    ["gpu_id", "gpu_name"],
)

gpu_memory_total = Gauge(
    "biometric_gpu_memory_total_bytes",
    "Total GPU memory",
    ["gpu_id", "gpu_name"],
)

gpu_memory_free = Gauge(
    "biometric_gpu_memory_free_bytes",
    "Free GPU memory",
    ["gpu_id", "gpu_name"],
)

gpu_utilization = Gauge(
    "biometric_gpu_utilization_percent",
    "GPU compute utilization percentage",
    ["gpu_id", "gpu_name"],
)

gpu_memory_utilization = Gauge(
    "biometric_gpu_memory_utilization_percent",
    "GPU memory utilization percentage",
    ["gpu_id", "gpu_name"],
)

gpu_temperature = Gauge(
    "biometric_gpu_temperature_celsius",
    "GPU temperature in Celsius",
    ["gpu_id", "gpu_name"],
)

gpu_power_usage = Gauge(
    "biometric_gpu_power_usage_watts",
    "GPU power usage in Watts",
    ["gpu_id", "gpu_name"],
)

gpu_info = Info("biometric_gpu", "GPU device information")

# =============================================================================
# Metrics Collection
# =============================================================================


def collect_gpu_metrics() -> bool:
    """Collect NVIDIA GPU metrics using nvidia-smi.

    This function queries nvidia-smi for GPU metrics and updates
    the Prometheus gauges. Should be called periodically (e.g., every 15s).

    Returns:
        True if metrics were collected successfully, False otherwise
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total,memory.free,"
                "utilization.gpu,utilization.memory,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            logger.warning(f"nvidia-smi failed: {result.stderr}")
            return False

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 9:
                continue

            (
                idx,
                name,
                mem_used,
                mem_total,
                mem_free,
                gpu_util,
                mem_util,
                temp,
                power,
            ) = parts

            labels = {"gpu_id": idx, "gpu_name": name}

            # Memory metrics (convert MB to bytes)
            gpu_memory_used.labels(**labels).set(int(float(mem_used)) * 1024 * 1024)
            gpu_memory_total.labels(**labels).set(int(float(mem_total)) * 1024 * 1024)
            gpu_memory_free.labels(**labels).set(int(float(mem_free)) * 1024 * 1024)

            # Utilization metrics
            gpu_utilization.labels(**labels).set(float(gpu_util))
            gpu_memory_utilization.labels(**labels).set(float(mem_util))

            # Temperature
            gpu_temperature.labels(**labels).set(float(temp))

            # Power usage (handle N/A for some GPUs)
            try:
                gpu_power_usage.labels(**labels).set(float(power))
            except ValueError:
                pass  # Power reading not available

        return True

    except FileNotFoundError:
        logger.debug("nvidia-smi not found, GPU metrics unavailable")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi timed out")
        return False
    except Exception as e:
        logger.error(f"GPU metrics collection failed: {e}")
        return False


def collect_gpu_metrics_torch() -> bool:
    """Collect GPU metrics using PyTorch.

    Alternative to nvidia-smi that works within the Python process.
    Provides less detail but doesn't require nvidia-smi binary.

    Returns:
        True if metrics were collected successfully, False otherwise
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return False

        for i in range(torch.cuda.device_count()):
            name = torch.cuda.get_device_name(i)
            props = torch.cuda.get_device_properties(i)

            labels = {"gpu_id": str(i), "gpu_name": name}

            # Memory metrics
            allocated = torch.cuda.memory_allocated(i)
            reserved = torch.cuda.memory_reserved(i)
            total = props.total_memory

            gpu_memory_used.labels(**labels).set(allocated)
            gpu_memory_total.labels(**labels).set(total)
            gpu_memory_free.labels(**labels).set(total - reserved)

            # Memory utilization
            if total > 0:
                gpu_memory_utilization.labels(**labels).set(
                    round(allocated / total * 100, 1)
                )

        return True

    except ImportError:
        logger.debug("PyTorch not available for GPU metrics")
        return False
    except Exception as e:
        logger.error(f"PyTorch GPU metrics collection failed: {e}")
        return False


def setup_gpu_info():
    """Set static GPU information metrics.

    Should be called once at startup to populate GPU info.
    """
    from app.core.gpu_config import GPU_INFO

    if GPU_INFO and GPU_INFO.available:
        gpu_info.info(
            {
                "cuda_version": GPU_INFO.cuda_version or "unknown",
                "device_count": str(GPU_INFO.device_count),
                "devices": ", ".join(GPU_INFO.device_names),
                "total_memory_mb": str(sum(GPU_INFO.memory_total)),
            }
        )
        logger.info("GPU info metrics configured")
    else:
        gpu_info.info(
            {
                "cuda_version": "N/A",
                "device_count": "0",
                "devices": "none",
                "total_memory_mb": "0",
            }
        )


# =============================================================================
# Background Metrics Collection
# =============================================================================

_metrics_task: Optional["asyncio.Task"] = None


async def start_gpu_metrics_collection(interval_seconds: float = 15.0):
    """Start background GPU metrics collection.

    Args:
        interval_seconds: How often to collect metrics (default 15s)
    """
    import asyncio

    global _metrics_task

    async def _collect_loop():
        while True:
            # Try nvidia-smi first, fall back to PyTorch
            if not collect_gpu_metrics():
                collect_gpu_metrics_torch()
            await asyncio.sleep(interval_seconds)

    if _metrics_task is None:
        _metrics_task = asyncio.create_task(_collect_loop())
        logger.info(f"GPU metrics collection started (interval: {interval_seconds}s)")


async def stop_gpu_metrics_collection():
    """Stop background GPU metrics collection."""
    global _metrics_task

    if _metrics_task:
        _metrics_task.cancel()
        try:
            await _metrics_task
        except asyncio.CancelledError:
            pass
        _metrics_task = None
        logger.info("GPU metrics collection stopped")


# =============================================================================
# Initialization
# =============================================================================


def initialize_gpu_metrics():
    """Initialize GPU metrics on module load.

    Sets up static info and performs initial metrics collection.
    """
    setup_gpu_info()
    collect_gpu_metrics() or collect_gpu_metrics_torch()


# Auto-initialize when imported
try:
    initialize_gpu_metrics()
except Exception as e:
    logger.warning(f"GPU metrics initialization failed: {e}")
