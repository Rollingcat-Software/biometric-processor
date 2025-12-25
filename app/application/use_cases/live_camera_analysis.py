"""Live camera analysis use case for real-time frame processing."""

import logging
from typing import Optional

import numpy as np

from app.api.schemas.live_analysis import (
    AnalysisMode,
    LiveAnalysisResponse,
    FaceDetectionResult,
    QualityResult,
    DemographicsResult,
    LivenessResult,
    EnrollmentReadyResult,
)
from app.domain.exceptions.face_errors import FaceNotDetectedError, MultipleFacesError
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor

logger = logging.getLogger(__name__)


class LiveCameraAnalysisUseCase:
    """Use case for real-time camera frame analysis.

    Processes individual frames and returns immediate feedback for:
    - Face detection
    - Quality assessment
    - Demographics (age, gender, emotion)
    - Liveness detection
    - Enrollment readiness
    """

    def __init__(
        self,
        detector: IFaceDetector,
        quality_assessor: IQualityAssessor,
        liveness_detector: Optional[ILivenessDetector] = None,
    ):
        self._detector = detector
        self._quality_assessor = quality_assessor
        self._liveness_detector = liveness_detector

        logger.info("LiveCameraAnalysisUseCase initialized")

    async def analyze_frame(
        self,
        image: np.ndarray,
        mode: AnalysisMode,
        quality_threshold: float = 70.0,
    ) -> LiveAnalysisResponse:
        """Analyze a single camera frame.

        Args:
            image: Camera frame as numpy array
            mode: Analysis mode to run
            quality_threshold: Minimum quality score for enrollment

        Returns:
            Analysis results based on mode
        """
        response = LiveAnalysisResponse(
            frame_number=0,  # Will be set by session
            timestamp=0,  # Will be set by session
            processing_time_ms=0,  # Will be set by session
        )

        try:
            # Step 1: Detect face (required for all modes)
            try:
                detection = await self._detector.detect(image)
                response.face = FaceDetectionResult(
                    detected=True,
                    confidence=detection.confidence,
                    bbox={
                        "x": detection.x,
                        "y": detection.y,
                        "width": detection.width,
                        "height": detection.height,
                    },
                    landmarks=detection.landmarks if hasattr(detection, 'landmarks') else None,
                )

                # Extract face region for further analysis
                face_region = detection.get_face_region(image)

            except FaceNotDetectedError:
                response.face = FaceDetectionResult(
                    detected=False,
                    confidence=0.0,
                )
                response.error = "No face detected"
                return response

            except MultipleFacesError:
                response.face = FaceDetectionResult(
                    detected=False,
                    confidence=0.0,
                )
                response.error = "Multiple faces detected - please ensure only one face in frame"
                return response

            # Step 2: Quality assessment (for most modes)
            if mode in [
                AnalysisMode.QUALITY_ONLY,
                AnalysisMode.ENROLLMENT_READY,
                AnalysisMode.FULL_ANALYSIS,
            ]:
                quality = await self._quality_assessor.assess(face_region)
                response.quality = QualityResult(
                    score=quality.score,
                    is_acceptable=quality.is_acceptable,
                    issues=quality.get_issues(),
                    metrics={
                        "blur_score": quality.blur_score if hasattr(quality, 'blur_score') else 0,
                        "brightness_score": quality.brightness_score if hasattr(quality, 'brightness_score') else 0,
                        "sharpness_score": quality.sharpness_score if hasattr(quality, 'sharpness_score') else 0,
                    },
                )

            # Step 3: Demographics (if requested)
            if mode in [AnalysisMode.DEMOGRAPHICS, AnalysisMode.FULL_ANALYSIS]:
                demographics = await self._analyze_demographics(face_region)
                response.demographics = demographics

            # Step 4: Liveness detection (if requested)
            if mode in [
                AnalysisMode.LIVENESS,
                AnalysisMode.ENROLLMENT_READY,
                AnalysisMode.FULL_ANALYSIS,
            ]:
                if self._liveness_detector:
                    liveness = await self._analyze_liveness(image, detection)
                    response.liveness = liveness
                else:
                    response.liveness = LivenessResult(
                        is_live=True,  # Default to true if no detector
                        confidence=0.5,
                        method="none",
                        checks={"passive": True},
                    )

            # Step 5: Enrollment readiness check
            if mode == AnalysisMode.ENROLLMENT_READY:
                response.enrollment_ready = self._check_enrollment_ready(
                    response, quality_threshold
                )

            return response

        except Exception as e:
            logger.error(f"Error in live frame analysis: {str(e)}", exc_info=True)
            response.error = f"Analysis error: {str(e)}"
            return response

    async def _analyze_demographics(self, face_image: np.ndarray) -> DemographicsResult:
        """Analyze demographics from face image.

        Note: This is a placeholder. Integrate with DeepFace or similar.
        """
        # TODO: Integrate with actual demographics analyzer
        # For now, return placeholder data
        return DemographicsResult(
            age=None,
            age_range=None,
            gender=None,
            gender_confidence=None,
            emotion=None,
            emotion_scores=None,
        )

    async def _analyze_liveness(
        self, image: np.ndarray, detection
    ) -> LivenessResult:
        """Analyze liveness from image.

        Args:
            image: Full frame
            detection: Face detection result

        Returns:
            Liveness analysis result
        """
        try:
            # Use the liveness detector if available
            liveness_result = await self._liveness_detector.detect(image)

            return LivenessResult(
                is_live=liveness_result.is_live,
                confidence=liveness_result.confidence,
                method=liveness_result.method if hasattr(liveness_result, 'method') else "passive",
                checks={
                    "texture": liveness_result.texture_check if hasattr(liveness_result, 'texture_check') else True,
                    "depth": liveness_result.depth_check if hasattr(liveness_result, 'depth_check') else True,
                },
            )

        except Exception as e:
            logger.warning(f"Liveness detection failed: {str(e)}")
            # Return conservative result
            return LivenessResult(
                is_live=False,
                confidence=0.0,
                method="error",
                checks={"error": str(e)},
            )

    def _check_enrollment_ready(
        self, response: LiveAnalysisResponse, quality_threshold: float
    ) -> EnrollmentReadyResult:
        """Check if frame is ready for enrollment.

        Args:
            response: Current analysis response
            quality_threshold: Minimum quality score

        Returns:
            Enrollment readiness result with guidance
        """
        # Check face detection
        face_detected = response.face and response.face.detected
        if not face_detected:
            return EnrollmentReadyResult(
                ready=False,
                face_detected=False,
                quality_met=False,
                liveness_met=False,
                recommendation="Please position your face in the frame",
            )

        # Check quality
        quality_met = False
        if response.quality:
            quality_met = response.quality.score >= quality_threshold

        # Check liveness
        liveness_met = False
        if response.liveness:
            liveness_met = response.liveness.is_live and response.liveness.confidence > 0.5

        # Generate recommendation
        recommendation = self._generate_recommendation(
            face_detected, quality_met, liveness_met, response
        )

        # Overall readiness
        ready = face_detected and quality_met and liveness_met

        return EnrollmentReadyResult(
            ready=ready,
            face_detected=face_detected,
            quality_met=quality_met,
            liveness_met=liveness_met,
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self,
        face_detected: bool,
        quality_met: bool,
        liveness_met: bool,
        response: LiveAnalysisResponse,
    ) -> str:
        """Generate user guidance message.

        Args:
            face_detected: Whether face was detected
            quality_met: Whether quality threshold is met
            liveness_met: Whether liveness check passed
            response: Analysis response with details

        Returns:
            Human-readable guidance message
        """
        if not face_detected:
            return "❌ No face detected - center your face in the frame"

        if not liveness_met:
            return "⚠️ Liveness check failed - make sure you're a real person, not a photo"

        if not quality_met and response.quality:
            # Provide specific quality guidance
            issues = response.quality.issues
            if "blur" in " ".join(issues).lower():
                return "⚠️ Image too blurry - hold steady and improve lighting"
            elif "dark" in " ".join(issues).lower() or "bright" in " ".join(issues).lower():
                return "⚠️ Lighting issue - adjust brightness"
            elif "distance" in " ".join(issues).lower():
                return "⚠️ Move closer to the camera"
            else:
                return f"⚠️ Quality too low ({response.quality.score:.1f}) - improve lighting and hold steady"

        # All checks passed
        return "✅ Perfect! Frame ready for enrollment"
