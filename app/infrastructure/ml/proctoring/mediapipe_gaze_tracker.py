"""MediaPipe-based gaze tracker implementation for proctoring.

Uses MediaPipe Face Mesh (468 landmarks) to track gaze direction
and head pose for detecting if the user is looking at the screen.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.domain.entities.proctor_analysis import (
    GazeAnalysisResult,
    GazeDirection,
    HeadPose,
)
from app.domain.interfaces.gaze_tracker import IGazeTracker

logger = logging.getLogger(__name__)

# MediaPipe Face Mesh landmark indices for eyes
# Left eye (from viewer's perspective)
LEFT_EYE_INDICES = {
    "outer_corner": 33,
    "inner_corner": 133,
    "upper": [159, 158, 157, 173],
    "lower": [145, 144, 163, 7],
    "iris": [468, 469, 470, 471, 472],  # Iris landmarks (refine_landmarks=True)
}

# Right eye
RIGHT_EYE_INDICES = {
    "outer_corner": 263,
    "inner_corner": 362,
    "upper": [386, 385, 384, 398],
    "lower": [374, 373, 390, 249],
    "iris": [473, 474, 475, 476, 477],  # Iris landmarks
}

# Key face landmarks for head pose estimation
FACE_POSE_INDICES = {
    "nose_tip": 1,
    "chin": 152,
    "left_eye_corner": 33,
    "right_eye_corner": 263,
    "left_mouth_corner": 61,
    "right_mouth_corner": 291,
}


class MediaPipeGazeTracker(IGazeTracker):
    """Gaze tracker using MediaPipe Face Mesh.

    Detects head pose and gaze direction by analyzing:
    1. Head pose: Using facial landmarks (nose, eyes, chin)
    2. Gaze direction: Using iris position relative to eye corners
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        gaze_threshold: float = 0.3,
        head_pose_threshold: Tuple[float, float] = (20.0, 30.0),
    ) -> None:
        """Initialize MediaPipe gaze tracker.

        Args:
            min_detection_confidence: MediaPipe face detection confidence
            min_tracking_confidence: MediaPipe tracking confidence
            gaze_threshold: Threshold for determining if gaze is on screen
            head_pose_threshold: (pitch, yaw) thresholds for head pose
        """
        self._min_detection_confidence = min_detection_confidence
        self._min_tracking_confidence = min_tracking_confidence
        self._gaze_threshold = gaze_threshold
        self._pitch_threshold, self._yaw_threshold = head_pose_threshold
        self._face_mesh = None
        # Track off-screen start per session to avoid accumulating across sessions
        self._off_screen_start: Dict[str, Optional[datetime]] = {}

        logger.info(
            f"MediaPipeGazeTracker initialized: "
            f"gaze_threshold={gaze_threshold}, "
            f"head_pose_threshold={head_pose_threshold}"
        )

    def _get_face_mesh(self):
        """Lazy initialization of MediaPipe Face Mesh."""
        if self._face_mesh is None:
            try:
                import mediapipe as mp

                self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False,  # Video mode for tracking
                    max_num_faces=1,
                    refine_landmarks=True,  # Required for iris landmarks
                    min_detection_confidence=self._min_detection_confidence,
                    min_tracking_confidence=self._min_tracking_confidence,
                )
                logger.info("MediaPipe Face Mesh initialized for gaze tracking")
            except ImportError:
                logger.error("MediaPipe not installed. Run: pip install mediapipe")
                raise
        return self._face_mesh

    async def analyze(
        self,
        image: np.ndarray,
        session_id,
    ) -> GazeAnalysisResult:
        """Analyze image for gaze direction and head pose.

        Args:
            image: BGR image array
            session_id: Session being analyzed

        Returns:
            GazeAnalysisResult with head pose and gaze direction
        """
        timestamp = datetime.utcnow()

        # Convert BGR to RGB for MediaPipe
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]

        # Get facial landmarks
        face_mesh = self._get_face_mesh()
        results = face_mesh.process(rgb_image)

        if not results.multi_face_landmarks:
            logger.debug("No face detected for gaze tracking")
            duration = self._get_off_screen_duration(timestamp, is_off_screen=True, session_id=session_id)
            return GazeAnalysisResult(
                session_id=session_id,
                timestamp=timestamp,
                head_pose=None,
                gaze_direction=None,
                is_on_screen=False,
                confidence=0.0,
                duration_off_screen_sec=duration,
            )

        landmarks = results.multi_face_landmarks[0].landmark

        # Convert to pixel coordinates
        landmark_points = [(lm.x * w, lm.y * h, lm.z) for lm in landmarks]

        # Estimate head pose
        head_pose = self._estimate_head_pose(landmark_points, w, h)

        # Calculate gaze direction using iris
        gaze_direction = self._calculate_gaze_direction(landmark_points, w, h)

        # Determine if on screen
        is_on_screen = self._is_on_screen(head_pose, gaze_direction)
        confidence = self._calculate_confidence(landmarks)

        duration = self._get_off_screen_duration(timestamp, is_off_screen=not is_on_screen, session_id=session_id)

        logger.debug(
            f"Gaze analysis: on_screen={is_on_screen}, "
            f"head_pose=({head_pose.pitch:.1f}, {head_pose.yaw:.1f}), "
            f"gaze=({gaze_direction.x:.2f}, {gaze_direction.y:.2f})"
        )

        return GazeAnalysisResult(
            session_id=session_id,
            timestamp=timestamp,
            head_pose=head_pose,
            gaze_direction=gaze_direction,
            is_on_screen=is_on_screen,
            confidence=confidence,
            duration_off_screen_sec=duration,
        )

    async def get_head_pose(
        self,
        image: np.ndarray,
    ) -> Optional[HeadPose]:
        """Get head pose only (faster than full analysis).

        Args:
            image: BGR image array

        Returns:
            HeadPose or None if face not detected
        """
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]

        face_mesh = self._get_face_mesh()
        results = face_mesh.process(rgb_image)

        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0].landmark
        landmark_points = [(lm.x * w, lm.y * h, lm.z) for lm in landmarks]

        return self._estimate_head_pose(landmark_points, w, h)

    def is_available(self) -> bool:
        """Check if gaze tracker is available."""
        try:
            import mediapipe
            return True
        except ImportError:
            return False

    def _estimate_head_pose(
        self,
        landmarks: List[Tuple[float, float, float]],
        width: int,
        height: int,
    ) -> HeadPose:
        """Estimate head pose from landmarks using solvePnP.

        Args:
            landmarks: List of (x, y, z) landmark coordinates
            width: Image width
            height: Image height

        Returns:
            HeadPose with pitch, yaw, roll angles
        """
        # 3D model points (generic face model)
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye corner
            (225.0, 170.0, -135.0),      # Right eye corner
            (-150.0, -150.0, -125.0),    # Left mouth corner
            (150.0, -150.0, -125.0),     # Right mouth corner
        ], dtype=np.float64)

        # 2D image points
        image_points = np.array([
            landmarks[FACE_POSE_INDICES["nose_tip"]][:2],
            landmarks[FACE_POSE_INDICES["chin"]][:2],
            landmarks[FACE_POSE_INDICES["left_eye_corner"]][:2],
            landmarks[FACE_POSE_INDICES["right_eye_corner"]][:2],
            landmarks[FACE_POSE_INDICES["left_mouth_corner"]][:2],
            landmarks[FACE_POSE_INDICES["right_mouth_corner"]][:2],
        ], dtype=np.float64)

        # Camera matrix (approximation)
        focal_length = width
        center = (width / 2, height / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ], dtype=np.float64)

        # Assume no lens distortion
        dist_coeffs = np.zeros((4, 1))

        # Solve for pose
        success, rotation_vector, translation_vector = cv2.solvePnP(
            model_points,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            # Fallback to simple estimation
            return self._simple_head_pose(landmarks, width, height)

        # Convert rotation vector to angles
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        angles = self._rotation_matrix_to_euler(rotation_matrix)

        pitch, yaw, roll = angles
        return HeadPose(
            pitch=round(float(pitch), 1),
            yaw=round(float(yaw), 1),
            roll=round(float(roll), 1),
        )

    def _simple_head_pose(
        self,
        landmarks: List[Tuple[float, float, float]],
        width: int,
        height: int,
    ) -> HeadPose:
        """Simple head pose estimation fallback."""
        nose = landmarks[FACE_POSE_INDICES["nose_tip"]]
        left_eye = landmarks[FACE_POSE_INDICES["left_eye_corner"]]
        right_eye = landmarks[FACE_POSE_INDICES["right_eye_corner"]]
        chin = landmarks[FACE_POSE_INDICES["chin"]]

        # Yaw from nose position relative to eyes
        eye_center_x = (left_eye[0] + right_eye[0]) / 2
        yaw = (nose[0] - eye_center_x) / (width / 2) * 45

        # Pitch from nose vertical position
        face_height = chin[1] - (left_eye[1] + right_eye[1]) / 2
        expected_nose_y = (left_eye[1] + right_eye[1]) / 2 + face_height * 0.4
        pitch = (nose[1] - expected_nose_y) / face_height * 30

        # Roll from eye line angle
        dy = right_eye[1] - left_eye[1]
        dx = right_eye[0] - left_eye[0]
        roll = np.degrees(np.arctan2(dy, dx))

        return HeadPose(
            pitch=round(float(pitch), 1),
            yaw=round(float(yaw), 1),
            roll=round(float(roll), 1),
        )

    def _rotation_matrix_to_euler(self, R: np.ndarray) -> Tuple[float, float, float]:
        """Convert rotation matrix to Euler angles (pitch, yaw, roll)."""
        sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)

        if sy > 1e-6:
            pitch = np.arctan2(R[2, 1], R[2, 2])
            yaw = np.arctan2(-R[2, 0], sy)
            roll = np.arctan2(R[1, 0], R[0, 0])
        else:
            pitch = np.arctan2(-R[1, 2], R[1, 1])
            yaw = np.arctan2(-R[2, 0], sy)
            roll = 0

        return (
            np.degrees(pitch),
            np.degrees(yaw),
            np.degrees(roll),
        )

    def _calculate_gaze_direction(
        self,
        landmarks: List[Tuple[float, float, float]],
        width: int,
        height: int,
    ) -> GazeDirection:
        """Calculate gaze direction from iris position.

        Args:
            landmarks: Face landmarks
            width: Image width
            height: Image height

        Returns:
            GazeDirection with x, y components
        """
        try:
            # Get iris centers
            left_iris = self._get_iris_center(landmarks, LEFT_EYE_INDICES)
            right_iris = self._get_iris_center(landmarks, RIGHT_EYE_INDICES)

            # Get eye corners
            left_eye_outer = np.array(landmarks[LEFT_EYE_INDICES["outer_corner"]][:2])
            left_eye_inner = np.array(landmarks[LEFT_EYE_INDICES["inner_corner"]][:2])
            right_eye_outer = np.array(landmarks[RIGHT_EYE_INDICES["outer_corner"]][:2])
            right_eye_inner = np.array(landmarks[RIGHT_EYE_INDICES["inner_corner"]][:2])

            # Calculate iris position relative to eye (0 = outer, 1 = inner)
            left_ratio_x = self._calculate_ratio(
                left_iris[0], left_eye_outer[0], left_eye_inner[0]
            )
            right_ratio_x = self._calculate_ratio(
                right_iris[0], right_eye_inner[0], right_eye_outer[0]
            )

            # Average horizontal gaze (-1 = left, 0 = center, 1 = right)
            gaze_x = (left_ratio_x + right_ratio_x) / 2 - 0.5
            gaze_x = gaze_x * 2  # Scale to -1 to 1

            # Vertical gaze (using iris Y relative to eye height)
            left_eye_top = np.mean([landmarks[i][1] for i in LEFT_EYE_INDICES["upper"]])
            left_eye_bottom = np.mean([landmarks[i][1] for i in LEFT_EYE_INDICES["lower"]])
            right_eye_top = np.mean([landmarks[i][1] for i in RIGHT_EYE_INDICES["upper"]])
            right_eye_bottom = np.mean([landmarks[i][1] for i in RIGHT_EYE_INDICES["lower"]])

            left_ratio_y = self._calculate_ratio(
                left_iris[1], left_eye_top, left_eye_bottom
            )
            right_ratio_y = self._calculate_ratio(
                right_iris[1], right_eye_top, right_eye_bottom
            )

            gaze_y = (left_ratio_y + right_ratio_y) / 2 - 0.5
            gaze_y = -gaze_y * 2  # Invert and scale (up = positive)

            return GazeDirection(
                x=round(float(np.clip(gaze_x, -1, 1)), 3),
                y=round(float(np.clip(gaze_y, -1, 1)), 3),
            )

        except (IndexError, ValueError) as e:
            logger.warning(f"Gaze calculation failed: {e}")
            return GazeDirection(x=0.0, y=0.0)

    def _get_iris_center(
        self,
        landmarks: List[Tuple[float, float, float]],
        eye_indices: Dict,
    ) -> np.ndarray:
        """Get iris center from landmarks."""
        iris_indices = eye_indices["iris"]
        iris_points = [landmarks[i][:2] for i in iris_indices if i < len(landmarks)]

        if not iris_points:
            # Fallback: use eye corners center
            outer = landmarks[eye_indices["outer_corner"]][:2]
            inner = landmarks[eye_indices["inner_corner"]][:2]
            return np.array([(outer[0] + inner[0]) / 2, (outer[1] + inner[1]) / 2])

        return np.mean(iris_points, axis=0)

    def _calculate_ratio(self, value: float, start: float, end: float) -> float:
        """Calculate position ratio between two points."""
        if abs(end - start) < 1e-6:
            return 0.5
        return (value - start) / (end - start)

    def _is_on_screen(
        self,
        head_pose: HeadPose,
        gaze_direction: GazeDirection,
    ) -> bool:
        """Determine if user is looking at screen."""
        # Check head pose
        head_facing = head_pose.is_facing_camera(
            pitch_threshold=self._pitch_threshold,
            yaw_threshold=self._yaw_threshold,
        )

        # Check gaze direction
        gaze_centered = gaze_direction.is_on_screen(threshold=self._gaze_threshold)

        # Both should be true for high confidence
        return head_facing and gaze_centered

    def _calculate_confidence(self, landmarks) -> float:
        """Calculate detection confidence."""
        # Use visibility scores if available
        visibilities = [lm.visibility for lm in landmarks if hasattr(lm, 'visibility')]
        if visibilities:
            return float(np.mean(visibilities))
        return 0.9  # Default high confidence if landmarks detected

    def _get_off_screen_duration(
        self,
        current_time: datetime,
        is_off_screen: bool,
        session_id: str = None,
    ) -> float:
        """Track duration of continuous off-screen gaze per session."""
        session_key = str(session_id) if session_id else "default"

        if not is_off_screen:
            self._off_screen_start[session_key] = None
            return 0.0

        if self._off_screen_start.get(session_key) is None:
            self._off_screen_start[session_key] = current_time
            return 0.0

        return (current_time - self._off_screen_start[session_key]).total_seconds()
