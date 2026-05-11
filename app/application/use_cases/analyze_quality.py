"""Analyze quality use case."""

import logging

import cv2
import numpy as np

from app.application.services.occlusion_detector import (
    OcclusionAssessment,
    detect_occlusion,
    has_critical_occlusion,
)
from app.domain.entities.quality_feedback import (
    QualityFeedback,
    QualityIssue,
    QualityMetrics,
)
from app.domain.exceptions.face_errors import FaceNotFoundError
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor

logger = logging.getLogger(__name__)


class AnalyzeQualityUseCase:
    """Use case for analyzing image quality with detailed feedback.

    Provides actionable feedback on why an image fails quality checks.
    """

    # Quality issue codes and thresholds (normalized 0-100 scale)
    BLUR_THRESHOLD = 50.0  # Normalized: 50+ is acceptable
    BRIGHTNESS_LOW = 30.0  # Normalized: 30-90 is good range
    BRIGHTNESS_HIGH = 90.0
    MIN_FACE_SIZE = 40.0  # Normalized: 40+ is acceptable (80px/200px*100)
    MAX_FACE_RATIO = 0.8
    MAX_FACE_ANGLE = 70.0  # Normalized: 70+ is frontal (inverse scale)
    MAX_OCCLUSION = 20.0  # Normalized: <20% occlusion

    def __init__(
        self,
        detector: IFaceDetector,
        quality_assessor: IQualityAssessor,
    ) -> None:
        """Initialize analyze quality use case.

        Args:
            detector: Face detector implementation
            quality_assessor: Quality assessor implementation
        """
        self._detector = detector
        self._quality_assessor = quality_assessor
        logger.info("AnalyzeQualityUseCase initialized")

    async def execute(self, image: np.ndarray) -> QualityFeedback:
        """Execute quality analysis.

        Args:
            image: Input image as numpy array (RGB format)

        Returns:
            QualityFeedback with detailed analysis

        Raises:
            FaceNotFoundError: When no face is detected
        """
        logger.info("Starting quality analysis")

        # Detect face first
        detection_result = await self._detector.detect(image)
        if not detection_result.found:
            raise FaceNotFoundError("No face detected in image")

        # Calculate metrics (also returns the structured occlusion payload
        # so downstream code can surface region/reason without recomputing).
        metrics, occlusion_assessment = self._calculate_metrics(
            image, detection_result
        )

        # Identify issues (uses the assessment for region-level detail)
        issues = self._identify_issues(
            metrics, image.shape, occlusion_assessment
        )

        # Calculate overall score
        overall_score = self._calculate_overall_score(metrics)

        # Determine pass/fail
        passed = len([i for i in issues if i.severity == "high"]) == 0

        result = QualityFeedback(
            overall_score=overall_score,
            passed=passed,
            issues=issues,
            metrics=metrics,
        )

        logger.info(
            f"Quality analysis complete: score={overall_score:.1f}, passed={passed}"
        )
        return result

    def _calculate_metrics(
        self, image: np.ndarray, detection_result
    ) -> tuple[QualityMetrics, OcclusionAssessment]:
        """Calculate quality metrics from image.

        Returns normalized metrics (0-100) for consistent frontend display
        plus the structured occlusion assessment for downstream callers.
        """
        # Convert to grayscale for blur detection
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Blur score (Laplacian variance) - normalize to 0-100
        raw_blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Map 0-100 raw → 0-50, 100-500 raw → 50-100 (same as quality assessor)
        if raw_blur < 100:
            blur_score = (raw_blur / 100) * 50
        else:
            capped_blur = min(raw_blur, 500)
            blur_score = 50 + ((capped_blur - 100) / 400) * 50

        # Brightness (normalized to 0-100)
        brightness = (np.mean(gray) / 255.0) * 100

        # Face size - normalize to 0-100 (based on 200px reference)
        if detection_result.bounding_box:
            x, y, w, h = detection_result.bounding_box
            raw_face_size = max(w, h)
            face_size = min(100, (raw_face_size / 200) * 100)
        else:
            face_size = 0

        # Face angle (estimate from landmarks if available) - keep as percentage of max angle
        face_angle = 0.0
        if hasattr(detection_result, "landmarks") and detection_result.landmarks:
            # Simple angle estimation from eye positions
            left_eye = detection_result.landmarks.get("left_eye")
            right_eye = detection_result.landmarks.get("right_eye")
            if left_eye and right_eye:
                dy = right_eye[1] - left_eye[1]
                dx = right_eye[0] - left_eye[0]
                raw_angle = abs(np.degrees(np.arctan2(dy, dx)))
                # Normalize to 0-100 (0 degrees = 100%, 30+ degrees = 0%)
                face_angle = max(0, 100 - (raw_angle / 30) * 100)

        # Occlusion — region-based detector (T2-B, INVESTIGATION 2026-05-07
        # P1). Replaces the prior hardcoded 0.0 which made sunglasses, masks
        # and hand-over-mouth pass the quality gate. The detector returns a
        # structured payload {"score": 0..1, "regions": [...], "reason": str}
        # which we surface on QualityMetrics.occlusion_details and project
        # onto the legacy 0-100 ``occlusion`` percentage for back-compat.
        # detect_occlusion expects BGR; image is documented RGB so we flip.
        if detection_result.bounding_box is not None:
            x, y, w, h = detection_result.bounding_box
            face_crop_rgb = image[y : y + h, x : x + w]
            face_crop_bgr = cv2.cvtColor(face_crop_rgb, cv2.COLOR_RGB2BGR)
            occlusion_assessment = detect_occlusion(face_crop_bgr)
        else:
            occlusion_assessment = OcclusionAssessment(score=0.0)
        occlusion = float(occlusion_assessment.score) * 100.0

        metrics = QualityMetrics(
            blur_score=blur_score,
            brightness=brightness,
            face_size=face_size,
            face_angle=face_angle,
            occlusion=occlusion,
            occlusion_details=occlusion_assessment.to_dict(),
        )
        return metrics, occlusion_assessment

    def _identify_issues(
        self,
        metrics: QualityMetrics,
        image_shape: tuple,
        occlusion_assessment: OcclusionAssessment | None = None,
    ) -> list[QualityIssue]:
        """Identify quality issues from metrics."""
        issues = []

        # Check blur
        if metrics.blur_score < self.BLUR_THRESHOLD:
            issues.append(
                QualityIssue(
                    code="BLUR_DETECTED",
                    severity="high",
                    message="Image is too blurry",
                    value=metrics.blur_score,
                    threshold=self.BLUR_THRESHOLD,
                    suggestion="Use a stable camera or better lighting",
                )
            )

        # Check brightness
        if metrics.brightness < self.BRIGHTNESS_LOW:
            issues.append(
                QualityIssue(
                    code="LOW_BRIGHTNESS",
                    severity="high",
                    message="Image is too dark",
                    value=metrics.brightness,
                    threshold=self.BRIGHTNESS_LOW,
                    suggestion="Move to a brighter area or add lighting",
                )
            )
        elif metrics.brightness > self.BRIGHTNESS_HIGH:
            issues.append(
                QualityIssue(
                    code="HIGH_BRIGHTNESS",
                    severity="medium",
                    message="Image is too bright",
                    value=metrics.brightness,
                    threshold=self.BRIGHTNESS_HIGH,
                    suggestion="Reduce lighting or avoid direct light",
                )
            )

        # Check face size
        if metrics.face_size < self.MIN_FACE_SIZE:
            issues.append(
                QualityIssue(
                    code="FACE_TOO_SMALL",
                    severity="high",
                    message="Face is too small in frame",
                    value=metrics.face_size,
                    threshold=self.MIN_FACE_SIZE,
                    suggestion="Move closer to the camera",
                )
            )

        max_face_size = min(image_shape[0], image_shape[1]) * self.MAX_FACE_RATIO
        if metrics.face_size > max_face_size:
            issues.append(
                QualityIssue(
                    code="FACE_TOO_LARGE",
                    severity="medium",
                    message="Face is too close",
                    value=metrics.face_size,
                    threshold=max_face_size,
                    suggestion="Move further from the camera",
                )
            )

        # Check face angle
        if metrics.face_angle > self.MAX_FACE_ANGLE:
            issues.append(
                QualityIssue(
                    code="FACE_ANGLE",
                    severity="medium",
                    message="Face is not frontal",
                    value=metrics.face_angle,
                    threshold=self.MAX_FACE_ANGLE,
                    suggestion="Face the camera directly",
                )
            )

        # Check occlusion — T2-B contract: fail if score > 0.5 (= legacy
        # 50 on the 0-100 scale) OR any critical region (eyes) is flagged.
        # We also keep the legacy MAX_OCCLUSION (20%) threshold as a soft
        # warning so partial occlusion still surfaces.
        critical = (
            occlusion_assessment is not None
            and has_critical_occlusion(occlusion_assessment)
        )
        if critical or metrics.occlusion > self.MAX_OCCLUSION:
            regions: list[str] = (
                list(occlusion_assessment.regions)
                if occlusion_assessment is not None
                else []
            )
            reason = (
                occlusion_assessment.reason
                if occlusion_assessment is not None
                else None
            )
            severity = "high" if critical else "medium"
            message = "Face is partially covered"
            suggestion = "Remove any objects covering your face"
            if regions:
                pretty = ", ".join(sorted(set(regions)))
                message = f"Face is partially covered ({pretty})"
            if reason and "eyes" in reason:
                suggestion = "Remove sunglasses or anything blocking your eyes"
            elif reason and "mask" in reason:
                suggestion = "Remove face mask or covering"
            elif reason and "hand" in reason:
                suggestion = "Move your hand away from your face"
            issues.append(
                QualityIssue(
                    code="OCCLUSION",
                    severity=severity,
                    message=message,
                    value=metrics.occlusion,
                    threshold=self.MAX_OCCLUSION,
                    suggestion=suggestion,
                )
            )

        return issues

    def _calculate_overall_score(self, metrics: QualityMetrics) -> float:
        """Calculate overall quality score (0-100).

        Metrics are already normalized to 0-100, so just calculate weighted average.
        """
        # Weighted scoring
        weights = {
            "blur": 0.3,
            "brightness": 0.2,
            "face_size": 0.25,
            "face_angle": 0.15,
            "occlusion": 0.1,
        }

        # Metrics are already normalized to 0-100
        blur_score = metrics.blur_score

        # Brightness: optimal at 50, penalize deviation
        brightness_score = 100 - abs(metrics.brightness - 50) * 2

        # Face size already normalized
        face_size_score = metrics.face_size

        # Angle already normalized (100 = frontal, 0 = tilted)
        angle_score = metrics.face_angle

        # Occlusion already normalized (0 = no occlusion, 100 = fully occluded)
        occlusion_score = 100 - metrics.occlusion

        # Weighted average
        overall = (
            weights["blur"] * blur_score
            + weights["brightness"] * brightness_score
            + weights["face_size"] * face_size_score
            + weights["face_angle"] * angle_score
            + weights["occlusion"] * occlusion_score
        )

        return round(max(0, min(100, overall)), 1)
