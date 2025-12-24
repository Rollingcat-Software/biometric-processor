"""Fast image hashing for cache key generation.

This module provides efficient image hashing functions for use as
cache keys in embedding caching.

Following:
- KISS: Simple, fast hashing without over-engineering
- Single Responsibility: Only handles image hashing
"""

import hashlib
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def compute_image_hash(
    image: np.ndarray,
    size: int = 16,
    use_dct: bool = False,
) -> str:
    """Compute a fast perceptual hash for an image.

    This function generates a hash that is:
    - Fast to compute (~1ms for typical images)
    - Relatively stable for similar images
    - Suitable for exact-match caching (not similarity search)

    For caching embeddings, we need exact matches since even small
    image changes can affect the embedding significantly.

    Args:
        image: Input image as numpy array (BGR or grayscale)
        size: Size to downsample to (default 16x16)
        use_dct: If True, use DCT-based hashing (slower but more robust)

    Returns:
        Hexadecimal hash string

    Note:
        This is NOT a perceptual hash for similarity matching.
        It's designed for fast, exact-match caching.
    """
    try:
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Downsample for speed
        small = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)

        if use_dct:
            # DCT-based hash (more robust but slower)
            return _compute_dct_hash(small)
        else:
            # Simple average hash (faster)
            return _compute_average_hash(small)

    except Exception as e:
        logger.warning(f"Image hash computation failed: {e}")
        # Fallback to raw bytes hash
        return hashlib.md5(image.tobytes()).hexdigest()


def _compute_average_hash(small_gray: np.ndarray) -> str:
    """Compute average hash (aHash).

    Fast and simple - compares each pixel to the mean.

    Args:
        small_gray: Small grayscale image

    Returns:
        Hexadecimal hash string
    """
    # Compute mean
    mean = np.mean(small_gray)

    # Create binary hash (1 if pixel > mean, else 0)
    binary = (small_gray > mean).flatten()

    # Convert to bytes
    hash_bytes = np.packbits(binary)

    # Convert to hex string
    return hash_bytes.tobytes().hex()


def _compute_dct_hash(small_gray: np.ndarray) -> str:
    """Compute DCT-based perceptual hash (pHash).

    More robust to minor changes but slower than average hash.

    Args:
        small_gray: Small grayscale image

    Returns:
        Hexadecimal hash string
    """
    # Convert to float for DCT
    float_img = np.float32(small_gray)

    # Apply DCT
    dct = cv2.dct(float_img)

    # Take top-left 8x8 (low frequency components)
    dct_low = dct[:8, :8]

    # Compute median (excluding DC component)
    median = np.median(dct_low[1:, 1:])

    # Create binary hash
    binary = (dct_low > median).flatten()

    # Convert to bytes
    hash_bytes = np.packbits(binary)

    return hash_bytes.tobytes().hex()


def compute_embedding_cache_key(
    image: np.ndarray,
    model_name: str,
    extra_params: Optional[dict] = None,
) -> str:
    """Compute cache key for embedding extraction.

    Combines image hash with model parameters to ensure cache hits
    only occur for identical configurations.

    Args:
        image: Input image
        model_name: Name of the embedding model
        extra_params: Additional parameters affecting the embedding

    Returns:
        Cache key string
    """
    # Get image hash
    img_hash = compute_image_hash(image)

    # Include model name in key
    key_parts = [img_hash, model_name]

    # Include extra parameters if provided
    if extra_params:
        param_str = "_".join(f"{k}={v}" for k, v in sorted(extra_params.items()))
        key_parts.append(param_str)

    return ":".join(key_parts)


def compute_face_region_hash(
    image: np.ndarray,
    bounding_box: tuple,
) -> str:
    """Compute hash for a specific face region.

    Useful when caching per-face results from multi-face images.

    Args:
        image: Full image
        bounding_box: (x, y, w, h) of face region

    Returns:
        Cache key string
    """
    x, y, w, h = bounding_box

    # Extract region
    face_region = image[y : y + h, x : x + w]

    # Compute hash of region
    region_hash = compute_image_hash(face_region)

    # Include bounding box in key for uniqueness
    return f"{region_hash}_{x}_{y}_{w}_{h}"
