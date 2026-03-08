"""GPU configuration and detection module.

Provides utilities for detecting and configuring GPU devices for ML inference.
Supports NVIDIA CUDA GPUs and Apple Silicon (MPS).
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU information container.

    Attributes:
        available: Whether GPU is available for use
        device_count: Number of GPU devices detected
        device_names: List of GPU device names
        memory_total: Total memory in MB per device
        cuda_version: CUDA version string if available
    """

    available: bool
    device_count: int
    device_names: list[str]
    memory_total: list[int]  # MB per device
    cuda_version: Optional[str]

    def __str__(self) -> str:
        if not self.available:
            return "GPU: Not available"
        devices = ", ".join(
            f"{name} ({mem}MB)" for name, mem in zip(self.device_names, self.memory_total)
        )
        return f"GPU: {self.device_count} device(s) - {devices} (CUDA {self.cuda_version})"


def detect_gpu() -> GPUInfo:
    """Detect available GPU devices.

    Attempts to detect NVIDIA GPUs using PyTorch CUDA support.

    Returns:
        GPUInfo containing details about available GPUs
    """
    try:
        import torch

        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            device_names = [torch.cuda.get_device_name(i) for i in range(device_count)]
            memory_total = [
                torch.cuda.get_device_properties(i).total_memory // (1024 * 1024)
                for i in range(device_count)
            ]
            cuda_version = torch.version.cuda

            logger.info(f"GPU detected: {device_count} device(s)")
            for i, name in enumerate(device_names):
                logger.info(f"  GPU {i}: {name} ({memory_total[i]} MB)")

            return GPUInfo(
                available=True,
                device_count=device_count,
                device_names=device_names,
                memory_total=memory_total,
                cuda_version=cuda_version,
            )
    except ImportError:
        logger.warning("PyTorch not installed, GPU detection skipped")
    except Exception as e:
        logger.error(f"GPU detection failed: {e}")

    return GPUInfo(
        available=False,
        device_count=0,
        device_names=[],
        memory_total=[],
        cuda_version=None,
    )


def configure_tensorflow_gpu() -> bool:
    """Configure TensorFlow for GPU usage.

    Enables memory growth to prevent TensorFlow from allocating all GPU memory
    at startup, allowing other processes to use the GPU.

    Returns:
        True if GPU configuration was successful, False otherwise
    """
    try:
        import tensorflow as tf

        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            for gpu in gpus:
                # Enable memory growth to avoid allocating all GPU memory
                tf.config.experimental.set_memory_growth(gpu, True)
            logger.info(f"TensorFlow configured for {len(gpus)} GPU(s)")
            return True
    except ImportError:
        logger.warning("TensorFlow not installed, skipping GPU configuration")
    except Exception as e:
        logger.error(f"TensorFlow GPU configuration failed: {e}")

    return False


def get_torch_device() -> str:
    """Get the best available PyTorch device.

    Returns device string for PyTorch tensor operations:
    - "cuda:0" for NVIDIA GPU
    - "mps" for Apple Silicon
    - "cpu" as fallback

    Returns:
        Device string for use with torch.device()
    """
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
    except ImportError:
        pass

    return "cpu"


def get_onnx_providers() -> list[str]:
    """Get ONNX Runtime execution providers in priority order.

    Returns:
        List of provider names for ONNX Runtime InferenceSession
    """
    providers = []

    # Check for CUDA
    if USE_GPU:
        try:
            import onnxruntime as ort

            available_providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in available_providers:
                providers.append("CUDAExecutionProvider")
            if "TensorrtExecutionProvider" in available_providers:
                providers.insert(0, "TensorrtExecutionProvider")  # TensorRT is faster
        except ImportError:
            pass

    # CPU fallback
    providers.append("CPUExecutionProvider")

    return providers


def get_optimal_batch_size(gpu_memory_mb: int = 0) -> int:
    """Calculate optimal batch size based on available GPU memory.

    Args:
        gpu_memory_mb: Available GPU memory in MB. If 0, auto-detect.

    Returns:
        Recommended batch size for inference
    """
    if gpu_memory_mb == 0 and GPU_INFO and GPU_INFO.available:
        gpu_memory_mb = GPU_INFO.memory_total[0] if GPU_INFO.memory_total else 0

    if gpu_memory_mb == 0:
        return 1  # CPU fallback

    # Rough estimation based on typical face recognition models
    # ~500MB for model + ~100MB per batch item
    available_for_batch = max(0, gpu_memory_mb - 1000)  # Reserve 1GB for model
    batch_size = max(1, available_for_batch // 200)

    # Cap at reasonable maximum
    return min(batch_size, 32)


def clear_gpu_memory():
    """Clear GPU memory caches.

    Useful after large batch operations to free up memory.
    """
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.debug("GPU memory cache cleared")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to clear GPU memory: {e}")


def get_gpu_memory_usage() -> dict:
    """Get current GPU memory usage.

    Returns:
        Dictionary with memory stats per GPU device
    """
    result = {}

    try:
        import torch

        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) // (1024 * 1024)
                reserved = torch.cuda.memory_reserved(i) // (1024 * 1024)
                total = torch.cuda.get_device_properties(i).total_memory // (1024 * 1024)

                result[f"gpu_{i}"] = {
                    "allocated_mb": allocated,
                    "reserved_mb": reserved,
                    "total_mb": total,
                    "free_mb": total - reserved,
                    "utilization_percent": round(allocated / total * 100, 1) if total > 0 else 0,
                }
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to get GPU memory usage: {e}")

    return result


# =============================================================================
# Module Initialization
# =============================================================================

# Environment configuration
USE_GPU = os.getenv("USE_GPU", "true").lower() == "true"

# Initialize on import
GPU_INFO: Optional[GPUInfo] = None
TORCH_DEVICE: str = "cpu"

if USE_GPU:
    GPU_INFO = detect_gpu()
    if GPU_INFO.available:
        configure_tensorflow_gpu()
        TORCH_DEVICE = get_torch_device()
        logger.info(f"GPU enabled: {GPU_INFO}")
    else:
        logger.warning("GPU requested but not available, falling back to CPU")
else:
    logger.info("GPU disabled by configuration, using CPU")


def get_device_info() -> dict:
    """Get comprehensive device information for diagnostics.

    Returns:
        Dictionary containing GPU and CPU info
    """
    import platform

    info = {
        "use_gpu": USE_GPU,
        "torch_device": TORCH_DEVICE,
        "platform": platform.system(),
        "python_version": platform.python_version(),
    }

    if GPU_INFO:
        info["gpu"] = {
            "available": GPU_INFO.available,
            "device_count": GPU_INFO.device_count,
            "device_names": GPU_INFO.device_names,
            "memory_total_mb": GPU_INFO.memory_total,
            "cuda_version": GPU_INFO.cuda_version,
        }

        if GPU_INFO.available:
            info["gpu"]["memory_usage"] = get_gpu_memory_usage()

    return info
