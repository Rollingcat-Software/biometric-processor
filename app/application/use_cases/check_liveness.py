"""Liveness check use case."""

import json
import logging
from dataclasses import replace
from typing import Any

import cv2

from app.core.config import get_settings
from app.domain.entities.liveness_result import LivenessResult
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.liveness_detector import ILivenessDetector

logger = logging.getLogger(__name__)
calibration_logger = logging.getLogger("liveness_calibration")
settings = get_settings()
DEEPFACE_VETO_CONFIDENCE_THRESHOLD = 0.85
FACE_CROP_BLUR_THRESHOLD = 50.0


def _to_json_safe(value: Any) -> Any:
    """Convert numpy/scalar-rich payloads into JSON-serializable primitives."""
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _to_json_safe(item())
        except Exception:
            pass

    return str(value)


class CheckLivenessUseCase:
    """Use case for checking liveness of a face.

    This use case orchestrates the following steps:
    1. Detect face in image
    2. Perform liveness check

    Following Single Responsibility Principle: Only handles liveness check orchestration.
    Dependencies are injected for testability (Dependency Inversion Principle).

    Note:
        Uses TextureLivenessDetector for passive liveness detection.
        Active liveness (smile/blink) is planned for future implementation.
    """

    def __init__(
        self,
        detector: IFaceDetector,
        liveness_detector: ILivenessDetector,
    ) -> None:
        """Initialize liveness check use case.

        Args:
            detector: Face detector implementation
            liveness_detector: Liveness detector implementation
        """
        self._detector = detector
        self._liveness_detector = liveness_detector

        logger.info("CheckLivenessUseCase initialized")

    async def execute(self, image_path: str) -> LivenessResult:
        """Execute liveness check.

        Args:
            image_path: Path to image file

        Returns:
            LivenessResult with liveness check outcome

        Raises:
            FaceNotDetectedError: When no face is found
            MultipleFacesError: When multiple faces are found
            LivenessCheckError: When liveness check fails
        """
        logger.info("Starting liveness check")

        # Step 1: Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Step 2: Detect face (to ensure there's a face before liveness check)
        logger.debug("Step 1/2: Detecting face...")
        detection = await self._detector.detect(image)

        logger.debug(f"Face detected with confidence: {detection.confidence:.2f}")

        # Step 3: Perform liveness check
        logger.debug("Step 2/2: Checking liveness...")
        face_region = detection.get_face_region(image)
        gray_face = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray_face, cv2.CV_64F).var())

        if blur_score < FACE_CROP_BLUR_THRESHOLD:
            logger.warning(
                "low_quality_crop",
                extra={
                    "blur_score": blur_score,
                    "blur_threshold": FACE_CROP_BLUR_THRESHOLD,
                },
            )

        liveness_result = await self._liveness_detector.check_liveness(face_region)

        antispoof_score = detection.antispoof_score
        antispoof_label = detection.antispoof_label
        deepface_spoof_detected = (
            settings.ANTI_SPOOFING_ENABLED
            and antispoof_label == "spoof"
            and antispoof_score is not None
            and antispoof_score >= settings.ANTI_SPOOFING_THRESHOLD
        )

        if deepface_spoof_detected and liveness_result.confidence < DEEPFACE_VETO_CONFIDENCE_THRESHOLD:
            logger.warning(
                "DeepFace anti-spoof veto applied: antispoof_score=%.3f, liveness_confidence=%.3f",
                antispoof_score,
                liveness_result.confidence,
            )
            updated_details = {
                **liveness_result.details,
                "blur_score": blur_score,
                "antispoof_score": antispoof_score,
                "antispoof_label": antispoof_label,
                "deepface_veto_applied": True,
            }
            liveness_result = replace(
                liveness_result,
                is_live=False,
                details=updated_details,
            )
        else:
            liveness_result = replace(
                liveness_result,
                details={
                    **liveness_result.details,
                    "blur_score": blur_score,
                    "antispoof_score": antispoof_score,
                    "antispoof_label": antispoof_label,
                    "deepface_veto_applied": False,
                },
            )

        calibration_payload = _to_json_safe({
            "event": "liveness_calibration",
            "score": liveness_result.score,
            "is_live": liveness_result.is_live,
            "confidence": liveness_result.confidence,
            "backend": settings.get_liveness_backend(),
            "mode": settings.LIVENESS_MODE,
            "threshold": settings.LIVENESS_THRESHOLD,
            "sub_scores": {
                "texture": liveness_result.details.get("texture"),
                "lbp": liveness_result.details.get("lbp"),
                "color": liveness_result.details.get("color"),
                "blink": liveness_result.details.get("blink"),
                "smile": liveness_result.details.get("smile"),
                "passive_score": liveness_result.details.get("passive_score"),
                "passive_reliability": liveness_result.details.get("passive_reliability"),
                "active_score": liveness_result.details.get("active_score"),
                "antispoof": liveness_result.details.get("antispoof_score"),
            },
            "face_roi_source": liveness_result.details.get("face_roi_source"),
            "blur_score": liveness_result.details.get("blur_score"),
            "skin_coverage": liveness_result.details.get("skin_coverage"),
            "quality_score": liveness_result.details.get("quality_score"),
            "evidence_sufficiency": liveness_result.details.get("evidence_sufficiency"),
            "passive_weight": liveness_result.details.get("passive_weight"),
            "active_weight": liveness_result.details.get("active_weight"),
            "signal_reliability": {
                "texture": liveness_result.details.get("texture_reliability"),
                "lbp": liveness_result.details.get("lbp_reliability"),
                "color": liveness_result.details.get("color_reliability"),
            },
            "effective_weights": {
                "texture": liveness_result.details.get("effective_texture_weight"),
                "lbp": liveness_result.details.get("effective_lbp_weight"),
                "color": liveness_result.details.get("effective_color_weight"),
            },
        })

        calibration_logger.info(
            "liveness_calibration",
            extra={
                "event_type": "liveness_calibration",
                "payload": calibration_payload,
            },
        )

        logger.info(json.dumps(calibration_payload))

        logger.info(
            "liveness_check",
            extra={
                "score": liveness_result.score,
                "confidence": liveness_result.confidence,
                "is_live": liveness_result.is_live,
                "threshold": settings.LIVENESS_THRESHOLD,
                "backend": settings.get_liveness_backend(),
                "mode": settings.LIVENESS_MODE,
                "challenge": liveness_result.challenge,
                "challenge_completed": liveness_result.challenge_completed,
                "texture_score": liveness_result.details.get("texture"),
                "lbp_score": liveness_result.details.get("lbp"),
                "color_score": liveness_result.details.get("color"),
                "frequency_score": liveness_result.details.get("frequency"),
                "moire_score": liveness_result.details.get("moire"),
                "blink_score": liveness_result.details.get("blink"),
                "smile_score": liveness_result.details.get("smile"),
                "passive_score": liveness_result.details.get("passive_score"),
                "active_score": liveness_result.details.get("active_score"),
                "antispoof_score": antispoof_score,
                "antispoof_label": antispoof_label,
                "deepface_veto_applied": liveness_result.details.get("deepface_veto_applied"),
                "antispoof_threshold": settings.ANTI_SPOOFING_THRESHOLD,
                "face_detection_confidence": detection.confidence,
                "blur_score": liveness_result.details.get("blur_score"),
                "blur_threshold": FACE_CROP_BLUR_THRESHOLD,
            },
        )

        logger.info(
            f"Liveness check completed: "
            f"is_live={liveness_result.is_live}, "
            f"score={liveness_result.score:.1f}, "
            f"challenge={liveness_result.challenge}"
        )

        return liveness_result
