"""Image quality assessment implementation."""

import logging

import cv2
import numpy as np

from app.domain.entities.quality_assessment import QualityAssessment

logger = logging.getLogger(__name__)


class QualityAssessor:
    """Image quality assessor using OpenCV.

    Implements IQualityAssessor interface using computer vision techniques
    to assess image quality for face recognition.

    Quality Metrics:
    - Blur detection using Laplacian variance
    - Lighting assessment using mean brightness
    - Face size validation

    Following Single Responsibility Principle: Only handles quality assessment.
    """

    def __init__(
        self,
        blur_threshold: float = 100.0,
        min_face_size: int = 80,
        quality_threshold: float = 70.0,
    ) -> None:
        """Initialize quality assessor.

        Args:
            blur_threshold: Minimum acceptable blur score (Laplacian variance)
            min_face_size: Minimum acceptable face size in pixels
            quality_threshold: Minimum overall quality score (0-100)
        """
        self._blur_threshold = blur_threshold
        self._min_face_size = min_face_size
        self._quality_threshold = quality_threshold

        logger.info(
            f"Initialized QualityAssessor: "
            f"blur_threshold={blur_threshold}, "
            f"min_face_size={min_face_size}, "
            f"quality_threshold={quality_threshold}"
        )

    async def assess(self, face_image: np.ndarray) -> QualityAssessment:
        """Assess the quality of a face image.

        Args:
            face_image: Face image as numpy array (H, W, C)

        Returns:
            QualityAssessment with quality metrics

        Note:
            Quality score is calculated as weighted average of:
            - Blur score (40%)
            - Lighting score (30%)
            - Face size score (30%)

            When head pose can be estimated via facial landmarks, extreme poses
            (|yaw| > 30° or |pitch| > 25°) reduce the overall score by 30 %.
        """
        from typing import Optional as _Opt

        # Convert to grayscale for analysis
        if len(face_image.shape) == 3:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_image

        # 1. Blur detection using Laplacian variance
        blur_score = self._detect_blur(gray)

        # 2. Lighting assessment
        lighting_score = self._assess_lighting(gray)

        # 3. Face size
        h, w = face_image.shape[:2]
        face_size = min(h, w)

        # Calculate component scores (0-100)
        blur_quality = self._normalize_blur_score(blur_score)
        lighting_quality = self._normalize_lighting_score(lighting_score)
        size_quality = self._normalize_size_score(face_size)

        # Overall quality score (weighted average)
        overall_score = blur_quality * 0.4 + lighting_quality * 0.3 + size_quality * 0.3

        # 4. Pose estimation via MediaPipe face mesh (best-effort; no penalty on failure)
        yaw: _Opt[float] = None
        pitch: _Opt[float] = None
        pose_acceptable: _Opt[bool] = None

        try:
            yaw, pitch = self._estimate_pose(face_image)
            if yaw is not None and pitch is not None:
                pose_ok = abs(yaw) <= 30.0 and abs(pitch) <= 25.0
                pose_acceptable = pose_ok
                if not pose_ok:
                    overall_score = overall_score * 0.7
                    logger.info(
                        f"Pose penalty applied: yaw={yaw:.1f}°, pitch={pitch:.1f}° "
                        f"(thresholds: |yaw|≤30°, |pitch|≤25°)"
                    )
        except Exception as _pose_err:
            logger.debug(f"Pose estimation skipped: {_pose_err}")

        # Determine if acceptable
        # Hard reject: blur < 5 (completely unusable) or face too small
        # Accept with warning: blur 5-threshold (low quality but usable)
        # Accept: blur >= threshold
        hard_reject_blur = 5.0
        is_acceptable = (
            blur_score >= hard_reject_blur
            and face_size >= self._min_face_size
            and overall_score >= self._quality_threshold
        )

        logger.info(
            f"Quality assessment: "
            f"blur={blur_score:.1f}, "
            f"lighting={lighting_score:.1f}, "
            f"size={face_size}, "
            f"yaw={yaw}, "
            f"pitch={pitch}, "
            f"pose_acceptable={pose_acceptable}, "
            f"overall={overall_score:.1f}, "
            f"acceptable={is_acceptable}"
        )

        return QualityAssessment(
            score=overall_score,
            blur_score=blur_score,
            lighting_score=lighting_score,
            face_size=face_size,
            is_acceptable=is_acceptable,
            yaw=yaw,
            pitch=pitch,
            pose_acceptable=pose_acceptable,
        )

    @staticmethod
    def _estimate_pose(face_image: np.ndarray):
        """Estimate head yaw and pitch from facial landmarks using MediaPipe.

        Uses the 6-point face geometry approximation:
        nose tip, chin, left eye corner, right eye corner, left mouth corner,
        right mouth corner — enough for a Perspective-n-Point (PnP) solve.

        Args:
            face_image: BGR face crop (H, W, 3)

        Returns:
            Tuple (yaw_degrees, pitch_degrees) or (None, None) if unavailable.
        """
        try:
            import mediapipe as mp

            h, w = face_image.shape[:2]

            mp_face_mesh = mp.solutions.face_mesh
            with mp_face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=0.5,
            ) as face_mesh:
                rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)

            if not results.multi_face_landmarks:
                return None, None

            lm = results.multi_face_landmarks[0].landmark

            # 2D image points (selected canonical landmarks)
            # Indices: nose tip=1, chin=152, left eye left=33, right eye right=263,
            #          left mouth=61, right mouth=291
            image_points = np.array([
                [lm[1].x * w,   lm[1].y * h],    # Nose tip
                [lm[152].x * w, lm[152].y * h],  # Chin
                [lm[33].x * w,  lm[33].y * h],   # Left eye left corner
                [lm[263].x * w, lm[263].y * h],  # Right eye right corner
                [lm[61].x * w,  lm[61].y * h],   # Left mouth corner
                [lm[291].x * w, lm[291].y * h],  # Right mouth corner
            ], dtype=np.float64)

            # Generic 3D model points (canonical face)
            model_points = np.array([
                [0.0,     0.0,    0.0],    # Nose tip
                [0.0,   -330.0, -65.0],   # Chin
                [-225.0,  170.0, -135.0], # Left eye left corner
                [225.0,   170.0, -135.0], # Right eye right corner
                [-150.0, -150.0, -125.0], # Left mouth corner
                [150.0,  -150.0, -125.0], # Right mouth corner
            ], dtype=np.float64)

            focal_length = w
            center = (w / 2, h / 2)
            camera_matrix = np.array([
                [focal_length, 0,            center[0]],
                [0,            focal_length, center[1]],
                [0,            0,            1        ],
            ], dtype=np.float64)
            dist_coeffs = np.zeros((4, 1))

            _, rotation_vec, _ = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )

            rotation_mat, _ = cv2.Rodrigues(rotation_vec)
            proj_matrix = np.hstack((rotation_mat, np.zeros((3, 1))))
            _, _, _, _, _, _, euler = cv2.decomposeProjectionMatrix(proj_matrix)

            pitch_deg = float(euler[0])
            yaw_deg   = float(euler[1])

            return yaw_deg, pitch_deg

        except ImportError:
            return None, None

    def get_minimum_acceptable_score(self) -> float:
        """Get the minimum acceptable quality score.

        Returns:
            Minimum quality threshold (0-100)
        """
        return self._quality_threshold

    @staticmethod
    def _detect_blur(gray: np.ndarray) -> float:
        """Detect blur using Laplacian variance.

        Args:
            gray: Grayscale image

        Returns:
            Blur score (higher = sharper image)
            Typical ranges:
            - < 100: Very blurry (reject)
            - 100-500: Acceptable
            - > 500: Sharp (ideal)
        """
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return float(laplacian_var)

    @staticmethod
    def _assess_lighting(gray: np.ndarray) -> float:
        """Assess lighting quality.

        Args:
            gray: Grayscale image

        Returns:
            Lighting score (mean brightness)
            Typical ranges:
            - < 50: Too dark (reject)
            - 50-200: Good range
            - > 200: Too bright (may be acceptable)
        """
        mean_brightness = np.mean(gray)
        return float(mean_brightness)

    @staticmethod
    def _normalize_blur_score(blur_score: float) -> float:
        """Normalize blur score to 0-100 range.

        Args:
            blur_score: Raw Laplacian variance

        Returns:
            Normalized score (0-100)
        """
        # Map blur score to 0-100
        # 0-100: 0-50
        # 100-500: 50-100
        if blur_score < 100:
            return (blur_score / 100) * 50
        else:
            # Cap at 500 for normalization
            capped_score = min(blur_score, 500)
            return 50 + ((capped_score - 100) / 400) * 50

    @staticmethod
    def _normalize_lighting_score(lighting_score: float) -> float:
        """Normalize lighting score to 0-100 range.

        Args:
            lighting_score: Mean brightness (0-255)

        Returns:
            Normalized score (0-100)
        """
        # Ideal range: 80-180
        # Penalize too dark or too bright
        if lighting_score < 50:
            # Too dark
            return (lighting_score / 50) * 50
        elif lighting_score > 200:
            # Too bright
            return max(0, 100 - ((lighting_score - 200) / 55) * 50)
        else:
            # Good range
            # Peak at 130 (middle of ideal range)
            distance_from_ideal = abs(lighting_score - 130)
            return 100 - (distance_from_ideal / 80) * 20

    @staticmethod
    def _normalize_size_score(face_size: int) -> float:
        """Normalize face size score to 0-100 range.

        Args:
            face_size: Minimum dimension of face in pixels

        Returns:
            Normalized score (0-100)
        """
        # Map size to quality
        # < 50: Very poor (0-25)
        # 50-80: Poor (25-50)
        # 80-150: Good (50-100)
        # > 150: Excellent (100)
        if face_size < 50:
            return (face_size / 50) * 25
        elif face_size < 80:
            return 25 + ((face_size - 50) / 30) * 25
        elif face_size < 150:
            return 50 + ((face_size - 80) / 70) * 50
        else:
            return 100.0
