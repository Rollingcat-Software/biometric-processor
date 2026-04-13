"""Live camera analysis use case for real-time frame processing."""

import asyncio
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
    VerificationResult,
    SearchResult as LiveSearchResult,
    LandmarksResult,
)
from app.domain.exceptions.face_errors import FaceNotDetectedError, MultipleFacesError
from app.domain.exceptions.verification_errors import EmbeddingNotFoundError
from app.domain.interfaces.demographics_analyzer import IDemographicsAnalyzer
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator

logger = logging.getLogger(__name__)


class LiveCameraAnalysisUseCase:
    """Use case for real-time camera frame analysis.

    Processes individual frames and returns immediate feedback for:
    - Face detection
    - Quality assessment
    - Demographics (age, gender, emotion)
    - Liveness detection
    - Enrollment readiness
    - Face verification (1:1 matching)
    - Face search (1:N identification)
    - Facial landmarks
    """

    def __init__(
        self,
        detector: IFaceDetector,
        quality_assessor: IQualityAssessor,
        liveness_detector: Optional[ILivenessDetector] = None,
        embedding_extractor: Optional[IEmbeddingExtractor] = None,
        embedding_repository: Optional[IEmbeddingRepository] = None,
        similarity_calculator: Optional[ISimilarityCalculator] = None,
        demographics_analyzer: Optional[IDemographicsAnalyzer] = None,
        enable_demographics: bool = False,
    ):
        self._detector = detector
        self._quality_assessor = quality_assessor
        self._liveness_detector = liveness_detector
        self._extractor = embedding_extractor
        self._repository = embedding_repository
        self._similarity = similarity_calculator
        self._demographics_analyzer = demographics_analyzer
        self._enable_demographics = enable_demographics

        logger.info(
            "LiveCameraAnalysisUseCase initialized "
            "(demographics=%s)",
            "enabled" if enable_demographics and demographics_analyzer else "disabled",
        )

    async def analyze_frame(
        self,
        image: np.ndarray,
        mode: AnalysisMode,
        quality_threshold: float = 70.0,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> LiveAnalysisResponse:
        """Analyze a single camera frame.

        Args:
            image: Camera frame as numpy array
            mode: Analysis mode to run
            quality_threshold: Minimum quality score for enrollment
            user_id: User ID for verification mode
            tenant_id: Tenant ID for multi-tenancy

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
                    liveness = await self._analyze_liveness(face_region)
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

            # Step 6: Verification (1:1 matching)
            if mode == AnalysisMode.VERIFICATION:
                if not user_id:
                    response.error = "User ID required for verification mode"
                elif not self._extractor or not self._repository or not self._similarity:
                    logger.error(
                        "Verification dependencies not available: extractor=%s, repository=%s, similarity=%s",
                        self._extractor is not None,
                        self._repository is not None,
                        self._similarity is not None,
                    )
                    response.error = "Verification service not configured"
                else:
                    verification = await self._verify_face(face_region, user_id, tenant_id)
                    response.verification = verification

            # Step 7: Search (1:N identification)
            if mode == AnalysisMode.SEARCH:
                if not self._extractor or not self._repository or not self._similarity:
                    logger.error(
                        "Search dependencies not available: extractor=%s, repository=%s, similarity=%s",
                        self._extractor is not None,
                        self._repository is not None,
                        self._similarity is not None,
                    )
                    response.error = "Search service not configured"
                else:
                    search = await self._search_face(face_region, tenant_id)
                    response.search = search

            # Step 8: Landmarks
            if mode == AnalysisMode.LANDMARKS:
                if response.face and response.face.landmarks:
                    response.landmarks = LandmarksResult(
                        landmarks=response.face.landmarks,
                        num_landmarks=len(response.face.landmarks),
                        confidence=detection.confidence,
                    )
                else:
                    response.error = "Landmarks not available from detector"

            return response

        except Exception as e:
            logger.error(f"Error in live frame analysis: {str(e)}", exc_info=True)
            response.error = f"Analysis error: {str(e)}"
            return response

    async def _verify_face(
        self, face_image: np.ndarray, user_id: str, tenant_id: Optional[str]
    ) -> VerificationResult:
        """Verify face against enrolled user."""
        try:
            # Extract embedding from current frame
            current_embedding = await self._extractor.extract(face_image)

            # Get stored embedding
            stored_embedding = await self._repository.get_embedding(user_id, tenant_id)
            if stored_embedding is None:
                raise EmbeddingNotFoundError(f"No enrollment found for user: {user_id}")

            # Calculate similarity
            similarity = self._similarity.calculate_similarity(current_embedding, stored_embedding.embedding)
            threshold = 0.6  # Default threshold

            # Determine match
            match = similarity >= threshold

            return VerificationResult(
                match=match,
                confidence=similarity,
                similarity=similarity,
                threshold=threshold,
                user_id=user_id,
            )

        except EmbeddingNotFoundError:
            return VerificationResult(
                match=False,
                confidence=0.0,
                similarity=0.0,
                threshold=0.6,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            raise

    async def _search_face(
        self, face_image: np.ndarray, tenant_id: Optional[str]
    ) -> LiveSearchResult:
        """Search for face in database (1:N identification)."""
        try:
            # Extract embedding from current frame
            query_embedding = await self._extractor.extract(face_image)

            # Search in repository
            matches = await self._repository.search_similar(
                query_embedding,
                tenant_id=tenant_id,
                top_k=1,  # Just best match for live mode
                threshold=0.6,
            )

            if matches:
                best_match = matches[0]
                return LiveSearchResult(
                    found=True,
                    user_id=best_match.user_id,
                    confidence=best_match.distance,
                    similarity=best_match.distance,
                    num_candidates=1,
                )
            else:
                return LiveSearchResult(
                    found=False,
                    user_id=None,
                    confidence=0.0,
                    similarity=0.0,
                    num_candidates=0,
                )

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return LiveSearchResult(
                found=False,
                user_id=None,
                confidence=0.0,
                similarity=0.0,
                num_candidates=0,
            )

    async def _analyze_demographics(self, face_image: np.ndarray) -> DemographicsResult:
        """Analyze demographics from face image.

        Calls the real DemographicsAnalyzer when enabled and available.
        The analyzer is CPU-heavy (DeepFace), so it runs in a thread pool
        via asyncio.to_thread to avoid blocking the async event loop.

        When demographics are disabled (enable_demographics=False) or no
        analyzer is injected, returns an empty DemographicsResult immediately.
        """
        if not self._enable_demographics or self._demographics_analyzer is None:
            return DemographicsResult(
                age=None,
                age_range=None,
                gender=None,
                gender_confidence=None,
                emotion=None,
                emotion_scores=None,
            )

        try:
            # Run synchronous (CPU-bound) DeepFace call off the event loop
            result = await asyncio.to_thread(
                self._demographics_analyzer.analyze, face_image
            )

            age_range = (
                f"{result.age.range[0]}-{result.age.range[1]}"
                if result.age and result.age.range
                else None
            )
            emotion = result.emotion.dominant if result.emotion else None
            emotion_scores = result.emotion.all_probabilities if result.emotion else None

            return DemographicsResult(
                age=result.age.value if result.age else None,
                age_range=age_range,
                gender=result.gender.value if result.gender else None,
                gender_confidence=result.gender.confidence if result.gender else None,
                emotion=emotion,
                emotion_scores=emotion_scores,
            )

        except Exception as exc:
            logger.warning("Demographics analysis failed: %s", exc)
            return DemographicsResult(
                age=None,
                age_range=None,
                gender=None,
                gender_confidence=None,
                emotion=None,
                emotion_scores=None,
            )

    async def _analyze_liveness(self, face_image: np.ndarray) -> LivenessResult:
        """Analyze liveness from image.

        Args:
            face_image: Cropped face region

        Returns:
            Liveness analysis result
        """
        try:
            liveness_result = await self._liveness_detector.check_liveness(face_image)
            details = liveness_result.details or {}

            method = str(
                details.get("method")
                or details.get("face_roi_source")
                or details.get("fallback_reason")
                or liveness_result.challenge
            )

            checks = {
                "challenge_completed": liveness_result.challenge_completed,
            }
            scores = {}
            metadata = {}

            bool_detail_keys = (
                "texture_check",
                "depth_check",
                "eyes_open",
                "smiling",
                "deepface_veto_applied",
            )
            for key in bool_detail_keys:
                if key in details:
                    checks[key] = bool(details[key])

            score_detail_keys = (
                "texture",
                "lbp",
                "color",
                "frequency",
                "moire",
                "blink",
                "smile",
                "passive_score",
                "active_score",
                "combined_score",
                "backend_score",
                "antispoof_score",
            )
            for key in score_detail_keys:
                if key in details:
                    scores[key] = float(details[key])

            metadata_keys = (
                "face_roi_source",
                "fallback_reason",
                "antispoof_label",
            )
            for key in metadata_keys:
                if key in details:
                    metadata[key] = details[key]

            for key, value in details.items():
                if key in checks or key in scores or key in metadata:
                    continue
                if isinstance(value, bool):
                    checks[key] = value
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    scores[key] = float(value)
                else:
                    metadata[key] = value

            return LivenessResult(
                is_live=liveness_result.is_live,
                confidence=liveness_result.confidence,
                method=method,
                checks=checks,
                scores=scores,
                metadata=metadata,
            )

        except Exception as e:
            logger.warning(f"Liveness detection failed: {str(e)}")
            # Return conservative result
            return LivenessResult(
                is_live=False,
                confidence=0.0,
                method="error",
                checks={},
                scores={},
                metadata={"error": str(e)},
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
