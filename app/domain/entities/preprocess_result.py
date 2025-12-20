"""Image preprocessing domain entities."""

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class PreprocessOptions:
    """Options for image preprocessing.

    Attributes:
        auto_rotate: Whether to fix EXIF orientation
        max_size: Maximum dimension in pixels
        normalize: Whether to apply histogram equalization
        denoise: Whether to apply denoising
        color_correct: Whether to apply white balance
    """

    auto_rotate: bool = True
    max_size: int = 1920
    normalize: bool = True
    denoise: bool = False
    color_correct: bool = False


@dataclass
class PreprocessResult:
    """Image preprocessing result.

    Attributes:
        image: Preprocessed image array
        original_size: Original image dimensions (width, height)
        new_size: New image dimensions (width, height)
        was_rotated: Whether image was rotated
        rotation_angle: Rotation angle applied (degrees)
        operations_applied: List of operations applied
    """

    image: np.ndarray
    original_size: Tuple[int, int]
    new_size: Tuple[int, int]
    was_rotated: bool = False
    rotation_angle: int = 0
    operations_applied: List[str] = field(default_factory=list)
