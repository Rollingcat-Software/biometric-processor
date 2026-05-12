"""MediaPipe-based facial landmark detector implementation.

Ported 2026-05-12 from the legacy ``mediapipe.solutions.face_mesh`` API to
``mediapipe.tasks.vision.FaceLandmarker``. The ``mp.solutions`` namespace was
removed in mediapipe 0.10.35; the new Tasks API requires a ``.task`` model
asset and exposes landmarks as ``result.face_landmarks[0][i].(x|y|z)``.
"""

import logging
from typing import List, Optional

import numpy as np

from app.domain.entities.face_landmarks import HeadPose, Landmark, LandmarkResult
from app.domain.exceptions.feature_errors import LandmarkError
from app.infrastructure.ml.landmarks.face_landmarker_loader import (
    create_face_landmarker,
    to_mp_image,
)

logger = logging.getLogger(__name__)


class MediaPipeLandmarkDetector:
    """Facial landmark detector using MediaPipe Face Landmarker (Tasks API).

    Detects 468 facial landmarks with optional 3D coordinates.
    """

    # Facial region indices for MediaPipe Face Mesh (canonical 468-pt topology;
    # indices are stable between the legacy face_mesh and the Tasks-API
    # face_landmarker outputs).
    REGIONS = {
        "left_eye": [33, 133, 160, 159, 158, 144, 145, 153],
        "right_eye": [362, 263, 387, 386, 385, 373, 374, 380],
        "nose": [1, 2, 3, 4, 5, 6, 168, 197, 195],
        "mouth": [61, 185, 40, 39, 37, 0, 267, 269, 270, 409],
        "left_eyebrow": [70, 63, 105, 66, 107, 55, 65],
        "right_eyebrow": [300, 293, 334, 296, 336, 285, 295],
        "face_oval": [
            10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
            397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
            172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
        ],
    }

    def __init__(self) -> None:
        """Initialize MediaPipe landmark detector."""
        self._face_landmarker = None
        logger.info("MediaPipeLandmarkDetector initialized (Tasks API)")

    def _get_face_landmarker(self):
        """Lazy load MediaPipe Face Landmarker (Tasks API)."""
        if self._face_landmarker is None:
            self._face_landmarker = create_face_landmarker(
                static_image_mode=True,
                num_faces=1,
                min_face_detection_confidence=0.5,
            )
            if self._face_landmarker is None:
                raise LandmarkError(
                    "MediaPipe FaceLandmarker unavailable — model asset missing or "
                    "Tasks API not importable. See logs for details."
                )
        return self._face_landmarker

    def detect(
        self, image: np.ndarray, include_3d: bool = False
    ) -> LandmarkResult:
        """Detect facial landmarks in image.

        Args:
            image: Face image as numpy array (RGB format)
            include_3d: Whether to include 3D coordinates

        Returns:
            LandmarkResult with detected landmarks

        Raises:
            LandmarkError: If detection fails
        """
        logger.debug(f"Starting landmark detection (include_3d={include_3d})")

        try:
            face_landmarker = self._get_face_landmarker()
            # Tasks API expects an mp.Image wrapping an RGB ndarray. Callers
            # of this method already pass RGB (see the docstring), so no
            # additional colour-space conversion is needed.
            mp_image = to_mp_image(image)
            result = face_landmarker.detect(mp_image)

            face_landmarks_list = result.face_landmarks or []
            if not face_landmarks_list:
                raise LandmarkError("No face landmarks detected")

            # Get first face landmarks. In the Tasks API each element is itself
            # a flat list of NormalizedLandmark (no `.landmark` attribute).
            face_landmarks = face_landmarks_list[0]
            height, width = image.shape[:2]

            # Extract landmarks
            landmarks = []
            for idx, lm in enumerate(face_landmarks):
                x = int(lm.x * width)
                y = int(lm.y * height)
                z = lm.z if include_3d else None

                landmarks.append(Landmark(id=idx, x=x, y=y, z=z))

            # Estimate head pose
            head_pose = self._estimate_head_pose(landmarks, width, height)

            result = LandmarkResult(
                model="mediapipe_468",
                landmark_count=len(landmarks),
                landmarks=landmarks,
                regions=self.REGIONS,
                head_pose=head_pose,
            )

            logger.info(f"Landmark detection complete: {len(landmarks)} landmarks")
            return result

        except LandmarkError:
            raise
        except Exception as e:
            logger.error(f"Landmark detection failed: {e}")
            raise LandmarkError(f"Landmark detection failed: {str(e)}")

    def _estimate_head_pose(
        self, landmarks: List[Landmark], width: int, height: int
    ) -> Optional[HeadPose]:
        """Estimate head pose from landmarks."""
        try:
            # Use nose tip and key facial points for estimation
            nose = landmarks[1]  # Nose tip
            left_eye = landmarks[33]  # Left eye corner
            right_eye = landmarks[263]  # Right eye corner
            chin = landmarks[152]  # Chin

            # Simple angle estimation
            # Yaw (left/right)
            eye_center_x = (left_eye.x + right_eye.x) / 2
            yaw = (nose.x - eye_center_x) / (width / 2) * 45

            # Pitch (up/down)
            face_height = chin.y - (left_eye.y + right_eye.y) / 2
            expected_nose_y = (left_eye.y + right_eye.y) / 2 + face_height * 0.4
            pitch = (nose.y - expected_nose_y) / face_height * 30

            # Roll (tilt)
            dy = right_eye.y - left_eye.y
            dx = right_eye.x - left_eye.x
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
        return 468

    def get_model_name(self) -> str:
        """Get name of the landmark model."""
        return "mediapipe_468"
