"""Unit tests for factory classes."""

import pytest
from unittest.mock import Mock, patch
import sys

# Mock DeepFace before importing anything that depends on it
sys.modules['deepface'] = Mock()
sys.modules['deepface.DeepFace'] = Mock()

from app.infrastructure.ml.factories.detector_factory import FaceDetectorFactory
from app.infrastructure.ml.detectors.deepface_detector import DeepFaceDetector


class TestFaceDetectorFactory:
    """Test FaceDetectorFactory."""

    def test_create_opencv_detector(self):
        """Test creating OpenCV detector."""
        detector = FaceDetectorFactory.create("opencv")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "opencv"

    def test_create_mtcnn_detector(self):
        """Test creating MTCNN detector."""
        detector = FaceDetectorFactory.create("mtcnn")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "mtcnn"

    def test_create_retinaface_detector(self):
        """Test creating RetinaFace detector."""
        detector = FaceDetectorFactory.create("retinaface")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "retinaface"

    def test_create_ssd_detector(self):
        """Test creating SSD detector."""
        detector = FaceDetectorFactory.create("ssd")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "ssd"

    def test_create_mediapipe_detector(self):
        """Test creating MediaPipe detector."""
        detector = FaceDetectorFactory.create("mediapipe")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "mediapipe"

    def test_create_yolov8_detector(self):
        """Test creating YOLOv8 detector."""
        detector = FaceDetectorFactory.create("yolov8")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "yolov8"

    def test_create_with_uppercase(self):
        """Test that detector type is case-insensitive."""
        detector = FaceDetectorFactory.create("MTCNN")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "mtcnn"

    def test_create_with_mixed_case(self):
        """Test with mixed case."""
        detector = FaceDetectorFactory.create("RetinaFace")

        assert isinstance(detector, DeepFaceDetector)
        assert detector._detector_backend == "retinaface"

    def test_create_with_kwargs(self):
        """Test creating detector with additional kwargs."""
        detector = FaceDetectorFactory.create("opencv", align=True)

        assert isinstance(detector, DeepFaceDetector)
        assert detector._align is True

    def test_create_unsupported_detector(self):
        """Test that creating unsupported detector raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported detector type"):
            FaceDetectorFactory.create("unsupported_detector")

    def test_create_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported detector type"):
            FaceDetectorFactory.create("")

    def test_get_available_detectors(self):
        """Test getting list of available detectors."""
        detectors = FaceDetectorFactory.get_available_detectors()

        assert isinstance(detectors, list)
        assert len(detectors) == 6
        assert "opencv" in detectors
        assert "mtcnn" in detectors
        assert "retinaface" in detectors
        assert "ssd" in detectors
        assert "mediapipe" in detectors
        assert "yolov8" in detectors

    def test_get_recommended_detector(self):
        """Test getting recommended detector."""
        recommended = FaceDetectorFactory.get_recommended_detector()

        assert recommended == "mtcnn"
        # Verify recommended detector is in available list
        assert recommended in FaceDetectorFactory.get_available_detectors()

    def test_create_all_available_detectors(self):
        """Test that all available detectors can be created."""
        available = FaceDetectorFactory.get_available_detectors()

        for detector_type in available:
            detector = FaceDetectorFactory.create(detector_type)
            assert isinstance(detector, DeepFaceDetector)
            assert detector._detector_backend == detector_type
