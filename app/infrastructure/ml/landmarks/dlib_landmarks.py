"""Dlib-based facial landmark detector implementation."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.domain.entities.face_landmarks import HeadPose, Landmark, LandmarkResult
from app.domain.exceptions.feature_errors import LandmarkError

logger = logging.getLogger(__name__)


class DlibLandmarkDetector:
    """Facial landmark detector using dlib's 68-point model.

    Detects 68 facial landmarks using dlib's pre-trained shape predictor.
    This is a classic model widely used in face analysis applications.
    """

    # Dlib 68-point landmark regions
    REGIONS = {
        "jaw": list(range(0, 17)),
        "right_eyebrow": list(range(17, 22)),
        "left_eyebrow": list(range(22, 27)),
        "nose_bridge": list(range(27, 31)),
        "nose_tip": list(range(31, 36)),
        "right_eye": list(range(36, 42)),
        "left_eye": list(range(42, 48)),
        "outer_lip": list(range(48, 60)),
        "inner_lip": list(range(60, 68)),
    }

    # Default shape predictor model path
    DEFAULT_MODEL_PATH = "models/shape_predictor_68_face_landmarks.dat"

    def __init__(
        self,
        model_path: Optional[str] = None,
        upsample_num: int = 1,
    ) -> None:
        """Initialize dlib landmark detector.

        Args:
            model_path: Path to shape_predictor_68_face_landmarks.dat file.
                       If None, uses default path.
            upsample_num: Number of times to upsample image for face detection.
                         Higher values find smaller faces but are slower.

        Raises:
            LandmarkError: If model file not found or dlib not installed.
        """
        self._model_path = model_path or self.DEFAULT_MODEL_PATH
        self._upsample_num = upsample_num
        self._predictor = None
        self._detector = None
        self._initialized = False

        logger.info(
            f"DlibLandmarkDetector initialized: model={self._model_path}, "
            f"upsample={upsample_num}"
        )

    def _initialize(self) -> None:
        """Lazy initialization of dlib models."""
        if self._initialized:
            return

        try:
            import dlib
        except ImportError:
            raise LandmarkError(
                "dlib is not installed. Install with: pip install dlib"
            )

        # Check model file exists
        model_file = Path(self._model_path)
        if not model_file.exists():
            # Try relative to project root
            alt_paths = [
                Path(__file__).parent.parent.parent.parent.parent / self._model_path,
                Path.cwd() / self._model_path,
            ]
            for alt_path in alt_paths:
                if alt_path.exists():
                    model_file = alt_path
                    break
            else:
                logger.warning(
                    f"Model file not found: {self._model_path}. "
                    "Download from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
                )
                raise LandmarkError(
                    f"Shape predictor model not found: {self._model_path}. "
                    "Download the model from dlib's website."
                )

        try:
            self._detector = dlib.get_frontal_face_detector()
            self._predictor = dlib.shape_predictor(str(model_file))
            self._initialized = True
            logger.info(f"Dlib models loaded from {model_file}")
        except Exception as e:
            raise LandmarkError(f"Failed to load dlib models: {e}")

    def detect(
        self, image: np.ndarray, include_3d: bool = False
    ) -> LandmarkResult:
        """Detect facial landmarks in image.

        Args:
            image: Face image as numpy array (RGB format)
            include_3d: Whether to include 3D coordinates (not supported by dlib 68)

        Returns:
            LandmarkResult with detected landmarks

        Raises:
            LandmarkError: If detection fails
        """
        logger.debug("Starting dlib landmark detection")

        try:
            self._initialize()

            # Convert to grayscale for dlib
            if len(image.shape) == 3:
                import cv2
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image

            # Detect faces
            faces = self._detector(gray, self._upsample_num)

            if len(faces) == 0:
                raise LandmarkError("No face detected in image")

            # Get landmarks for first face
            face = faces[0]
            shape = self._predictor(gray, face)

            # Extract landmarks
            landmarks = []
            for idx in range(68):
                point = shape.part(idx)
                landmarks.append(
                    Landmark(
                        id=idx,
                        x=point.x,
                        y=point.y,
                        z=None,  # dlib 68 model doesn't provide Z coordinates
                    )
                )

            # Estimate head pose
            height, width = image.shape[:2]
            head_pose = self._estimate_head_pose(landmarks, width, height)

            result = LandmarkResult(
                model="dlib_68",
                landmark_count=68,
                landmarks=landmarks,
                regions=self.REGIONS,
                head_pose=head_pose,
            )

            logger.info(f"Dlib landmark detection complete: {len(landmarks)} landmarks")
            return result

        except LandmarkError:
            raise
        except Exception as e:
            logger.error(f"Dlib landmark detection failed: {e}")
            raise LandmarkError(f"Landmark detection failed: {str(e)}")

    def _estimate_head_pose(
        self, landmarks: List[Landmark], width: int, height: int
    ) -> Optional[HeadPose]:
        """Estimate head pose from 68-point landmarks.

        Uses key facial landmarks:
        - Nose tip (point 30)
        - Left eye corners (36, 39)
        - Right eye corners (42, 45)
        - Chin (point 8)

        Args:
            landmarks: List of detected landmarks
            width: Image width
            height: Image height

        Returns:
            Estimated head pose or None if estimation fails
        """
        try:
            # Key landmarks for pose estimation
            nose_tip = landmarks[30]
            left_eye_outer = landmarks[36]
            left_eye_inner = landmarks[39]
            right_eye_inner = landmarks[42]
            right_eye_outer = landmarks[45]
            chin = landmarks[8]

            # Eye centers
            left_eye_x = (left_eye_outer.x + left_eye_inner.x) / 2
            left_eye_y = (left_eye_outer.y + left_eye_inner.y) / 2
            right_eye_x = (right_eye_inner.x + right_eye_outer.x) / 2
            right_eye_y = (right_eye_inner.y + right_eye_outer.y) / 2

            eye_center_x = (left_eye_x + right_eye_x) / 2
            eye_center_y = (left_eye_y + right_eye_y) / 2

            # Yaw (left/right rotation)
            yaw = (nose_tip.x - eye_center_x) / (width / 2) * 45

            # Pitch (up/down rotation)
            face_height = chin.y - eye_center_y
            expected_nose_y = eye_center_y + face_height * 0.4
            pitch = (nose_tip.y - expected_nose_y) / face_height * 30

            # Roll (head tilt)
            dy = right_eye_y - left_eye_y
            dx = right_eye_x - left_eye_x
            roll = np.degrees(np.arctan2(dy, dx))

            return HeadPose(
                pitch=round(pitch, 1),
                yaw=round(yaw, 1),
                roll=round(roll, 1),
            )

        except Exception as e:
            logger.warning(f"Head pose estimation failed: {e}")
            return None

    def get_landmark_count(self) -> int:
        """Get number of landmarks this detector provides."""
        return 68

    def get_model_name(self) -> str:
        """Get name of the landmark model."""
        return "dlib_68"

    def get_eye_landmarks(self, landmarks: List[Landmark]) -> Dict[str, List[Landmark]]:
        """Get eye-specific landmarks for EAR calculation.

        Args:
            landmarks: Full list of 68 landmarks

        Returns:
            Dictionary with left_eye and right_eye landmark lists
        """
        return {
            "left_eye": [landmarks[i] for i in self.REGIONS["left_eye"]],
            "right_eye": [landmarks[i] for i in self.REGIONS["right_eye"]],
        }

    def get_mouth_landmarks(self, landmarks: List[Landmark]) -> Dict[str, List[Landmark]]:
        """Get mouth-specific landmarks for MAR calculation.

        Args:
            landmarks: Full list of 68 landmarks

        Returns:
            Dictionary with outer_lip and inner_lip landmark lists
        """
        return {
            "outer_lip": [landmarks[i] for i in self.REGIONS["outer_lip"]],
            "inner_lip": [landmarks[i] for i in self.REGIONS["inner_lip"]],
        }
