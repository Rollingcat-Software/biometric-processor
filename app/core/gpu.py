"""GPU configuration for TensorFlow.

Configures TensorFlow GPU memory growth to prevent grabbing all VRAM
on startup. This is critical for laptop GPUs where VRAM is shared
with other processes and limited (8-16GB).
"""

import logging
import os

logger = logging.getLogger(__name__)


def configure_gpu() -> None:
    """Configure TensorFlow GPU settings.

    Enables memory growth so TensorFlow allocates VRAM on-demand
    instead of reserving all available memory at startup.

    This is safe to call even when no GPU is available — it will
    simply log that no GPUs were found and return.
    """
    # Check env var (set in .env.laptop and systemd service)
    allow_growth = os.getenv("TF_FORCE_GPU_ALLOW_GROWTH", "false").lower() == "true"

    try:
        import tensorflow as tf

        gpus = tf.config.list_physical_devices("GPU")

        if not gpus:
            logger.info("No GPU detected — running on CPU")
            return

        for gpu in gpus:
            if allow_growth:
                tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"GPU memory growth enabled for {gpu.name}")
            else:
                logger.info(f"GPU found: {gpu.name} (memory growth not enabled)")

        logger.info(f"TensorFlow GPU configuration complete: {len(gpus)} GPU(s) available")

    except RuntimeError as e:
        # Memory growth must be set before GPUs are initialized
        logger.warning(f"GPU configuration skipped (already initialized): {e}")
    except ImportError:
        logger.info("TensorFlow not available — GPU configuration skipped")
