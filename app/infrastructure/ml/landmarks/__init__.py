"""Facial landmark detection implementations."""

from app.infrastructure.ml.landmarks.mediapipe_landmarks import MediaPipeLandmarkDetector
from app.infrastructure.ml.landmarks.dlib_landmarks import DlibLandmarkDetector

__all__ = [
    "MediaPipeLandmarkDetector",
    "DlibLandmarkDetector",
]
