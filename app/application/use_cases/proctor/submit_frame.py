"""Submit frame for proctoring analysis use case."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np

from app.domain.entities.proctor_analysis import (
    AudioAnalysisResult,
    DeepfakeAnalysisResult,
    FrameAnalysisResult,
    GazeAnalysisResult,
    ObjectDetectionResult,
)
from app.domain.entities.proctor_incident import IncidentType, ProctorIncident
from app.domain.interfaces.audio_analyzer import IAudioAnalyzer
from app.domain.interfaces.deepfake_detector import IDeepfakeDetector
from app.domain.interfaces.gaze_tracker import IGazeTracker
from app.domain.interfaces.object_detector import IObjectDetector
from app.domain.interfaces.proctor_incident_repository import IProctorIncidentRepository
from app.domain.interfaces.proctor_session_repository import IProctorSessionRepository
from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreakerOpenError,
    DEEPFAKE_DETECTOR_BREAKER,
    FACE_VERIFIER_BREAKER,
    GAZE_TRACKER_BREAKER,
    OBJECT_DETECTOR_BREAKER,
    AUDIO_ANALYZER_BREAKER,
)
from app.infrastructure.resilience.session_rate_limiter import (
    RateLimitResult,
    SessionRateLimiter,
)

logger = logging.getLogger(__name__)


@dataclass
class SubmitFrameRequest:
    """Request to submit a frame for analysis."""

    session_id: UUID
    tenant_id: str
    frame: np.ndarray
    frame_number: int
    audio_data: Optional[bytes] = None
    audio_sample_rate: int = 16000


@dataclass
class SubmitFrameResponse:
    """Response from frame submission."""

    session_id: str
    frame_number: int
    risk_score: float
    face_detected: bool
    face_matched: bool
    incidents_created: int
    processing_time_ms: float
    analysis: Dict[str, Any]
    rate_limit: Optional[Dict[str, Any]] = None


class SubmitFrame:
    """Use case for submitting a frame for proctoring analysis."""

    def __init__(
        self,
        session_repository: IProctorSessionRepository,
        incident_repository: IProctorIncidentRepository,
        face_verifier=None,
        liveness_detector=None,
        gaze_tracker: Optional[IGazeTracker] = None,
        object_detector: Optional[IObjectDetector] = None,
        audio_analyzer: Optional[IAudioAnalyzer] = None,
        deepfake_detector: Optional[IDeepfakeDetector] = None,
        rate_limiter: Optional[SessionRateLimiter] = None,
        prohibited_objects: List[str] = None,
    ) -> None:
        """Initialize use case with analysis components."""
        self._session_repo = session_repository
        self._incident_repo = incident_repository
        self._face_verifier = face_verifier
        self._liveness_detector = liveness_detector
        self._gaze_tracker = gaze_tracker
        self._object_detector = object_detector
        self._audio_analyzer = audio_analyzer
        self._deepfake_detector = deepfake_detector
        self._rate_limiter = rate_limiter
        self._prohibited_objects = prohibited_objects or [
            "phone", "cell phone", "book", "laptop", "tablet", "person"
        ]

    async def execute(self, request: SubmitFrameRequest) -> SubmitFrameResponse:
        """Execute frame analysis.

        Args:
            request: Frame submission request

        Returns:
            Response with analysis results

        Raises:
            ValueError: If session not found or not active
        """
        start_time = time.time()

        # Check rate limit
        rate_limit_result = None
        if self._rate_limiter:
            rate_limit_result = await self._rate_limiter.check(request.session_id)
            if not rate_limit_result.allowed:
                # Create rate limit incident
                await self._create_incident(
                    request.session_id,
                    IncidentType.RATE_LIMIT_EXCEEDED,
                    0.9,
                    {"retry_after": rate_limit_result.retry_after},
                )
                raise ValueError(
                    f"Rate limit exceeded. Retry after {rate_limit_result.retry_after}s"
                )

        # Get session
        session = await self._session_repo.get_by_id(
            session_id=request.session_id,
            tenant_id=request.tenant_id,
        )

        if not session:
            raise ValueError(f"Session {request.session_id} not found")

        if not session.is_active():
            raise ValueError(
                f"Session {request.session_id} is not active. "
                f"Status: {session.status.value}"
            )

        # Run analyses in parallel
        analysis_result = await self._analyze_frame(
            session=session,
            frame=request.frame,
            frame_number=request.frame_number,
            audio_data=request.audio_data,
            audio_sample_rate=request.audio_sample_rate,
        )

        # Calculate risk and create incidents
        incidents_created = await self._process_analysis_results(
            session=session,
            analysis=analysis_result,
        )

        # Update session risk score
        new_risk = self._calculate_session_risk(session, analysis_result)
        session.update_risk_score(new_risk)
        await self._session_repo.save(session)

        processing_time = (time.time() - start_time) * 1000

        return SubmitFrameResponse(
            session_id=str(session.id),
            frame_number=request.frame_number,
            risk_score=session.risk_score,
            face_detected=analysis_result.face_detected,
            face_matched=analysis_result.face_matched,
            incidents_created=incidents_created,
            processing_time_ms=processing_time,
            analysis=analysis_result.to_dict(),
            rate_limit=rate_limit_result.to_dict() if rate_limit_result else None,
        )

    async def _analyze_frame(
        self,
        session,
        frame: np.ndarray,
        frame_number: int,
        audio_data: Optional[bytes],
        audio_sample_rate: int,
    ) -> FrameAnalysisResult:
        """Run all analyses on frame."""
        timestamp = datetime.utcnow()

        # Face verification with circuit breaker
        face_detected = False
        face_matched = False
        face_confidence = 0.0
        face_count = 0
        liveness_passed = False
        liveness_score = 0.0

        try:
            if self._face_verifier:
                result = await FACE_VERIFIER_BREAKER.call_async(
                    lambda: self._verify_face(frame, session),
                    fallback=lambda: self._default_face_result(),
                )
                face_detected = result.get("detected", False)
                face_matched = result.get("matched", False)
                face_confidence = result.get("confidence", 0.0)
                face_count = result.get("face_count", 0)
        except CircuitBreakerOpenError:
            logger.warning("Face verifier circuit breaker is open")

        try:
            if self._liveness_detector and face_detected:
                liveness_result = await self._liveness_detector.detect(frame)
                liveness_passed = liveness_result.is_live
                liveness_score = liveness_result.confidence
        except Exception as e:
            logger.error(f"Liveness detection failed: {e}")

        # Gaze tracking
        gaze_result = None
        if self._gaze_tracker and session.config.gaze_sensitivity > 0:
            try:
                gaze_result = await GAZE_TRACKER_BREAKER.call_async(
                    lambda: self._gaze_tracker.analyze(frame, session.id),
                    fallback=None,
                )
            except CircuitBreakerOpenError:
                logger.warning("Gaze tracker circuit breaker is open")

        # Object detection
        object_result = None
        if self._object_detector and session.config.enable_object_detection:
            try:
                object_result = await OBJECT_DETECTOR_BREAKER.call_async(
                    lambda: self._object_detector.detect(
                        frame, session.id, self._prohibited_objects
                    ),
                    fallback=None,
                )
            except CircuitBreakerOpenError:
                logger.warning("Object detector circuit breaker is open")

        # Audio analysis
        audio_result = None
        if (
            self._audio_analyzer
            and session.config.enable_audio_monitoring
            and audio_data
        ):
            try:
                audio_result = await AUDIO_ANALYZER_BREAKER.call_async(
                    lambda: self._audio_analyzer.analyze(
                        audio_data, audio_sample_rate, session.id
                    ),
                    fallback=None,
                )
            except CircuitBreakerOpenError:
                logger.warning("Audio analyzer circuit breaker is open")

        # Deepfake detection
        deepfake_result = None
        if self._deepfake_detector and session.config.enable_deepfake_detection:
            try:
                deepfake_result = await DEEPFAKE_DETECTOR_BREAKER.call_async(
                    lambda: self._deepfake_detector.detect(frame, session.id),
                    fallback=None,
                )
            except CircuitBreakerOpenError:
                logger.warning("Deepfake detector circuit breaker is open")

        return FrameAnalysisResult(
            session_id=session.id,
            timestamp=timestamp,
            frame_number=frame_number,
            face_detected=face_detected,
            face_matched=face_matched,
            face_confidence=face_confidence,
            face_count=face_count,
            liveness_passed=liveness_passed,
            liveness_score=liveness_score,
            gaze_result=gaze_result,
            object_result=object_result,
            audio_result=audio_result,
            deepfake_result=deepfake_result,
        )

    async def _verify_face(self, frame: np.ndarray, session) -> dict:
        """Verify face against baseline."""
        # This would call the actual face verifier
        # Placeholder implementation
        return {
            "detected": True,
            "matched": True,
            "confidence": 0.95,
            "face_count": 1,
        }

    def _default_face_result(self) -> dict:
        """Default result when face verifier is unavailable."""
        return {
            "detected": False,
            "matched": False,
            "confidence": 0.0,
            "face_count": 0,
        }

    async def _process_analysis_results(
        self,
        session,
        analysis: FrameAnalysisResult,
    ) -> int:
        """Process analysis results and create incidents."""
        incidents_created = 0

        # No face detected
        if not analysis.face_detected:
            await self._create_incident(
                session.id,
                IncidentType.FACE_NOT_DETECTED,
                0.9,
            )
            incidents_created += 1

        # Face not matched
        elif not analysis.face_matched and analysis.face_confidence > 0.5:
            await self._create_incident(
                session.id,
                IncidentType.FACE_NOT_MATCHED,
                analysis.face_confidence,
            )
            incidents_created += 1

        # Multiple faces
        if analysis.face_count > 1:
            await self._create_incident(
                session.id,
                IncidentType.MULTIPLE_FACES,
                0.95,
                {"face_count": analysis.face_count},
            )
            incidents_created += 1

        # Liveness failed
        if not analysis.liveness_passed and analysis.face_detected:
            await self._create_incident(
                session.id,
                IncidentType.LIVENESS_FAILED,
                1.0 - analysis.liveness_score,
            )
            incidents_created += 1

        # Deepfake detected
        if analysis.deepfake_result and analysis.deepfake_result.is_deepfake:
            await self._create_incident(
                session.id,
                IncidentType.DEEPFAKE_DETECTED,
                analysis.deepfake_result.confidence,
                {
                    "method": analysis.deepfake_result.detection_method,
                    "artifacts": analysis.deepfake_result.artifacts_found,
                },
            )
            incidents_created += 1

        # Gaze away
        if analysis.gaze_result and not analysis.gaze_result.is_on_screen:
            if analysis.gaze_result.duration_off_screen_sec > session.config.gaze_away_threshold_sec:
                await self._create_incident(
                    session.id,
                    IncidentType.GAZE_AWAY_PROLONGED,
                    analysis.gaze_result.confidence,
                    {"duration_sec": analysis.gaze_result.duration_off_screen_sec},
                )
                incidents_created += 1

        # Prohibited objects
        if analysis.object_result and analysis.object_result.has_prohibited_objects:
            for obj in analysis.object_result.get_prohibited_objects():
                incident_type = self._get_object_incident_type(obj.label)
                await self._create_incident(
                    session.id,
                    incident_type,
                    obj.confidence,
                    {"label": obj.label, "bbox": obj.bounding_box},
                )
                incidents_created += 1

        # Multiple voices
        if analysis.audio_result and analysis.audio_result.speaker_count > 1:
            await self._create_incident(
                session.id,
                IncidentType.MULTIPLE_VOICES,
                analysis.audio_result.confidence,
                {"speaker_count": analysis.audio_result.speaker_count},
            )
            incidents_created += 1

        return incidents_created

    async def _create_incident(
        self,
        session_id: UUID,
        incident_type: IncidentType,
        confidence: float,
        details: Dict[str, Any] = None,
    ) -> None:
        """Create and save an incident."""
        incident = ProctorIncident.create(
            session_id=session_id,
            incident_type=incident_type,
            confidence=confidence,
            details=details,
        )
        await self._incident_repo.save(incident)
        logger.info(f"Created incident {incident.id} of type {incident_type.value}")

    def _get_object_incident_type(self, label: str) -> IncidentType:
        """Map object label to incident type."""
        label_lower = label.lower()
        if "phone" in label_lower or "cell" in label_lower:
            return IncidentType.PHONE_DETECTED
        elif "book" in label_lower:
            return IncidentType.BOOK_DETECTED
        elif "person" in label_lower:
            return IncidentType.PERSON_IN_BACKGROUND
        elif label_lower in ("laptop", "tablet", "computer"):
            return IncidentType.ELECTRONIC_DEVICE
        else:
            return IncidentType.UNAUTHORIZED_OBJECT

    def _calculate_session_risk(
        self,
        session,
        analysis: FrameAnalysisResult,
    ) -> float:
        """Calculate updated session risk score."""
        frame_risk = analysis.calculate_risk_score()

        # Weighted moving average
        alpha = 0.3  # Weight for new frame
        new_risk = alpha * frame_risk + (1 - alpha) * session.risk_score

        return min(1.0, max(0.0, new_risk))
