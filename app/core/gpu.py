"""GPU configuration for TensorFlow.

Configures TensorFlow GPU memory growth and VRAM limits to prevent
grabbing all VRAM on startup. Critical for laptop GPUs with limited
VRAM (e.g., GTX 1650 with 4GB).
"""

import logging
import os

logger = logging.getLogger(__name__)


def configure_gpu() -> None:
    """Configure TensorFlow GPU settings.

    Behavior depends on environment variables:
    - TF_FORCE_GPU_ALLOW_GROWTH=true: Allocate VRAM on-demand
    - GPU_VRAM_LIMIT_MB=3072: Hard cap on VRAM usage (in MB)

    When GPU_VRAM_LIMIT_MB is set, a virtual device is created with
    that memory limit. This takes precedence over memory growth since
    both cannot be active simultaneously.

    This is safe to call even when no GPU is available — it will
    simply log that no GPUs were found and return.
    """
    allow_growth = os.getenv("TF_FORCE_GPU_ALLOW_GROWTH", "false").lower() == "true"
    vram_limit_mb = _get_vram_limit()

    try:
        import tensorflow as tf

        gpus = tf.config.list_physical_devices("GPU")

        if not gpus:
            logger.info("No GPU detected — running on CPU")
            return

        for gpu in gpus:
            if vram_limit_mb and vram_limit_mb > 0:
                tf.config.set_logical_device_configuration(
                    gpu,
                    [tf.config.LogicalDeviceConfiguration(memory_limit=vram_limit_mb)],
                )
                logger.info(
                    f"GPU VRAM limit set to {vram_limit_mb}MB for {gpu.name}"
                )
            elif allow_growth:
                tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"GPU memory growth enabled for {gpu.name}")
            else:
                logger.info(f"GPU found: {gpu.name} (no memory constraints set)")

        logger.info(f"TensorFlow GPU configuration complete: {len(gpus)} GPU(s) available")

    except RuntimeError as e:
        # Memory growth / logical device config must be set before GPUs are initialized
        logger.warning(f"GPU configuration skipped (already initialized): {e}")
    except ImportError:
        logger.info("TensorFlow not available — GPU configuration skipped")


def _get_vram_limit() -> int | None:
    """Read GPU_VRAM_LIMIT_MB from environment.

    Returns:
        VRAM limit in MB, or None if not set / invalid.
    """
    raw = os.getenv("GPU_VRAM_LIMIT_MB")
    if not raw:
        return None
    try:
        limit = int(raw)
        if limit <= 0:
            return None
        return limit
    except ValueError:
        logger.warning(f"Invalid GPU_VRAM_LIMIT_MB value: {raw!r}")
        return None
