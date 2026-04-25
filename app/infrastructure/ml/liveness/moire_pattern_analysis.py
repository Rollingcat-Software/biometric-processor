"""Shared moire-pattern analysis for screen replay and texture liveness checks."""

from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

DEFAULT_GABOR_KSIZE = (21, 21)
DEFAULT_GABOR_SIGMA = 5.0
DEFAULT_GABOR_LAMBDA = 10.0
DEFAULT_GABOR_GAMMA = 0.5
DEFAULT_GABOR_PSI = 0
DEFAULT_GABOR_THETAS = (0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4)
DEFAULT_RESPONSE_STD_THRESHOLD = 30.0


def build_default_moire_gabor_kernels() -> list[np.ndarray]:
    """Create the default Gabor bank used by the texture detectors."""
    return [
        cv2.getGaborKernel(
            ksize=DEFAULT_GABOR_KSIZE,
            sigma=DEFAULT_GABOR_SIGMA,
            theta=theta,
            lambd=DEFAULT_GABOR_LAMBDA,
            gamma=DEFAULT_GABOR_GAMMA,
            psi=DEFAULT_GABOR_PSI,
        )
        for theta in DEFAULT_GABOR_THETAS
    ]


def analyze_moire_pattern(
    gray: np.ndarray,
    *,
    gabor_kernels: Sequence[np.ndarray] | None = None,
    response_std_threshold: float = DEFAULT_RESPONSE_STD_THRESHOLD,
) -> dict[str, float | list[float]]:
    """Analyze periodic moire-like responses in a grayscale image.

    Returns normalized risk in [0,1] plus raw detector diagnostics.
    """
    kernels = list(gabor_kernels) if gabor_kernels is not None else build_default_moire_gabor_kernels()
    if gray is None or gray.size == 0 or not kernels:
        return {
            "moire_risk": 0.0,
            "moire_score": 100.0,
            "moire_response_count": 0.0,
            "moire_response_fraction": 0.0,
            "moire_response_std_mean": 0.0,
            "moire_response_std_max": 0.0,
            "moire_response_stds": [],
        }

    response_stds: list[float] = []
    strong_response_count = 0
    for kernel in kernels:
        filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
        response_std = float(np.std(filtered))
        response_stds.append(response_std)
        if response_std > response_std_threshold:
            strong_response_count += 1

    response_fraction = strong_response_count / max(len(kernels), 1)
    moire_risk = _clamp01(response_fraction)
    moire_score = 100.0 * (1.0 - moire_risk)

    return {
        "moire_risk": moire_risk,
        "moire_score": moire_score,
        "moire_response_count": float(strong_response_count),
        "moire_response_fraction": response_fraction,
        "moire_response_std_mean": float(np.mean(response_stds)) if response_stds else 0.0,
        "moire_response_std_max": float(np.max(response_stds)) if response_stds else 0.0,
        "moire_response_stds": response_stds,
    }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
