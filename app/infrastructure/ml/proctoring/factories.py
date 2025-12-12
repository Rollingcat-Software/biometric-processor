"""Factories for proctoring ML components.

Provides factory functions to create configured instances of
proctoring analysis components.
"""

import logging
from typing import Optional, Set

from app.domain.interfaces.audio_analyzer import IAudioAnalyzer
from app.domain.interfaces.deepfake_detector import IDeepfakeDetector
from app.domain.interfaces.gaze_tracker import IGazeTracker
from app.domain.interfaces.object_detector import IObjectDetector

from app.infrastructure.ml.proctoring.basic_audio_analyzer import BasicAudioAnalyzer
from app.infrastructure.ml.proctoring.mediapipe_gaze_tracker import MediaPipeGazeTracker
from app.infrastructure.ml.proctoring.texture_deepfake_detector import TextureDeepfakeDetector
from app.infrastructure.ml.proctoring.yolo_object_detector import YOLOObjectDetector

logger = logging.getLogger(__name__)


class GazeTrackerFactory:
    """Factory for creating gaze tracker instances."""

    @staticmethod
    def create(
        gaze_threshold: float = 0.3,
        head_pose_threshold: tuple = (20.0, 30.0),
        **kwargs,
    ) -> IGazeTracker:
        """Create a gaze tracker instance.

        Args:
            gaze_threshold: Threshold for on-screen gaze detection
            head_pose_threshold: (pitch, yaw) thresholds
            **kwargs: Additional arguments for MediaPipe

        Returns:
            IGazeTracker implementation
        """
        logger.info(
            f"Creating MediaPipeGazeTracker: "
            f"gaze_threshold={gaze_threshold}"
        )
        return MediaPipeGazeTracker(
            gaze_threshold=gaze_threshold,
            head_pose_threshold=head_pose_threshold,
            **kwargs,
        )


class ObjectDetectorFactory:
    """Factory for creating object detector instances."""

    MODELS = {
        "nano": "yolov8n.pt",
        "small": "yolov8s.pt",
        "medium": "yolov8m.pt",
        "large": "yolov8l.pt",
    }

    @staticmethod
    def create(
        model_size: str = "nano",
        confidence_threshold: float = 0.5,
        max_persons_allowed: int = 1,
        custom_prohibited: Optional[Set[str]] = None,
        **kwargs,
    ) -> IObjectDetector:
        """Create an object detector instance.

        Args:
            model_size: Model size (nano, small, medium, large)
            confidence_threshold: Detection confidence threshold
            max_persons_allowed: Maximum persons allowed in frame
            custom_prohibited: Additional prohibited object labels
            **kwargs: Additional arguments

        Returns:
            IObjectDetector implementation
        """
        model_name = ObjectDetectorFactory.MODELS.get(model_size, "yolov8n.pt")

        logger.info(
            f"Creating YOLOObjectDetector: "
            f"model={model_name}, threshold={confidence_threshold}"
        )
        return YOLOObjectDetector(
            model_name=model_name,
            confidence_threshold=confidence_threshold,
            max_persons_allowed=max_persons_allowed,
            custom_prohibited=custom_prohibited,
            **kwargs,
        )


class DeepfakeDetectorFactory:
    """Factory for creating deepfake detector instances."""

    @staticmethod
    def create(
        deepfake_threshold: float = 0.6,
        temporal_window: int = 10,
        **kwargs,
    ) -> IDeepfakeDetector:
        """Create a deepfake detector instance.

        Args:
            deepfake_threshold: Threshold for deepfake classification
            temporal_window: Number of frames for temporal analysis
            **kwargs: Additional arguments

        Returns:
            IDeepfakeDetector implementation
        """
        logger.info(
            f"Creating TextureDeepfakeDetector: "
            f"threshold={deepfake_threshold}"
        )
        return TextureDeepfakeDetector(
            deepfake_threshold=deepfake_threshold,
            temporal_window=temporal_window,
            **kwargs,
        )


class AudioAnalyzerFactory:
    """Factory for creating audio analyzer instances."""

    @staticmethod
    def create(
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        **kwargs,
    ) -> IAudioAnalyzer:
        """Create an audio analyzer instance.

        Args:
            sample_rate: Audio sample rate in Hz
            vad_threshold: Voice activity detection threshold
            **kwargs: Additional arguments

        Returns:
            IAudioAnalyzer implementation
        """
        logger.info(
            f"Creating BasicAudioAnalyzer: "
            f"sample_rate={sample_rate}"
        )
        return BasicAudioAnalyzer(
            sample_rate=sample_rate,
            vad_threshold=vad_threshold,
            **kwargs,
        )


class ProctorMLFactory:
    """Unified factory for all proctoring ML components."""

    @staticmethod
    def create_all(
        gaze_threshold: float = 0.3,
        object_model: str = "nano",
        object_threshold: float = 0.5,
        max_persons: int = 1,
        deepfake_threshold: float = 0.6,
        audio_sample_rate: int = 16000,
    ) -> dict:
        """Create all proctoring ML components with default config.

        Args:
            gaze_threshold: Gaze detection threshold
            object_model: YOLO model size
            object_threshold: Object detection threshold
            max_persons: Maximum allowed persons
            deepfake_threshold: Deepfake detection threshold
            audio_sample_rate: Audio sample rate

        Returns:
            Dictionary with all ML components
        """
        return {
            "gaze_tracker": GazeTrackerFactory.create(
                gaze_threshold=gaze_threshold
            ),
            "object_detector": ObjectDetectorFactory.create(
                model_size=object_model,
                confidence_threshold=object_threshold,
                max_persons_allowed=max_persons,
            ),
            "deepfake_detector": DeepfakeDetectorFactory.create(
                deepfake_threshold=deepfake_threshold
            ),
            "audio_analyzer": AudioAnalyzerFactory.create(
                sample_rate=audio_sample_rate
            ),
        }
