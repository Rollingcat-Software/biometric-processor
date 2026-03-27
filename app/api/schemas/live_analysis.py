"""Schemas for live camera analysis WebSocket API."""

from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class AnalysisMode(str, Enum):
    """Live analysis mode selection."""

    FACE_DETECTION = "face_detection"  # Just detect face
    QUALITY_ONLY = "quality"  # Face + quality assessment
    DEMOGRAPHICS = "demographics"  # Face + demographics
    LIVENESS = "liveness"  # Face + liveness check
    ENROLLMENT_READY = "enrollment_ready"  # All checks for enrollment
    VERIFICATION = "verification"  # 1:1 face verification
    SEARCH = "search"  # 1:N face search/identification
    LANDMARKS = "landmarks"  # Facial landmark detection
    FULL_ANALYSIS = "full"  # Everything


class LiveAnalysisRequest(BaseModel):
    """Request to start live analysis session."""

    mode: AnalysisMode = Field(
        default=AnalysisMode.QUALITY_ONLY,
        description="Analysis mode to run"
    )
    user_id: Optional[str] = Field(
        None,
        description="User ID for enrollment mode"
    )
    tenant_id: Optional[str] = Field(
        None,
        description="Tenant ID for multi-tenancy"
    )
    frame_skip: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Skip every N frames for performance (0=process all)"
    )
    quality_threshold: float = Field(
        default=70.0,
        ge=0,
        le=100,
        description="Minimum quality score for enrollment ready"
    )


class FaceDetectionResult(BaseModel):
    """Face detection result."""

    detected: bool = Field(..., description="Whether face was detected")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    bbox: Optional[Dict[str, int]] = Field(None, description="Bounding box {x, y, width, height}")
    landmarks: Optional[Dict[str, Any]] = Field(None, description="Facial landmarks")


class QualityResult(BaseModel):
    """Image quality assessment result."""

    score: float = Field(..., ge=0, le=100, description="Overall quality score")
    is_acceptable: bool = Field(..., description="Meets quality threshold")
    issues: List[str] = Field(default_factory=list, description="Quality issues detected")
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Individual quality metrics (blur, brightness, etc.)"
    )


class DemographicsResult(BaseModel):
    """Demographics analysis result."""

    age: Optional[int] = Field(None, description="Estimated age")
    age_range: Optional[str] = Field(None, description="Age range (e.g., '25-32')")
    gender: Optional[str] = Field(None, description="Detected gender")
    gender_confidence: Optional[float] = Field(None, ge=0, le=1, description="Gender confidence")
    emotion: Optional[str] = Field(None, description="Dominant emotion")
    emotion_scores: Optional[Dict[str, float]] = Field(None, description="All emotion scores")


class LivenessResult(BaseModel):
    """Liveness detection result."""

    is_live: bool = Field(..., description="Whether face is live (real person)")
    confidence: float = Field(..., ge=0, le=1, description="Liveness confidence")
    method: str = Field(..., description="Liveness detection method used")
    checks: Dict[str, bool] = Field(
        default_factory=dict,
        description="Boolean liveness checks and flags"
    )
    scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Numeric liveness scores from the backend"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional backend metadata for observability and debugging"
    )


class EnrollmentReadyResult(BaseModel):
    """Enrollment readiness check result."""

    ready: bool = Field(..., description="Ready for enrollment")
    quality_met: bool = Field(..., description="Quality threshold met")
    liveness_met: bool = Field(..., description="Liveness check passed")
    face_detected: bool = Field(..., description="Face detected")
    recommendation: str = Field(..., description="User guidance message")


class VerificationResult(BaseModel):
    """Face verification result (1:1 matching)."""

    match: bool = Field(..., description="Whether faces match")
    confidence: float = Field(..., ge=0, le=1, description="Match confidence score")
    similarity: float = Field(..., ge=0, le=1, description="Face similarity score")
    threshold: float = Field(..., description="Threshold used for matching")
    user_id: str = Field(..., description="User ID being verified against")


class SearchResult(BaseModel):
    """Face search/identification result (1:N matching)."""

    found: bool = Field(..., description="Whether a match was found")
    user_id: Optional[str] = Field(None, description="Matched user ID")
    confidence: float = Field(..., ge=0, le=1, description="Match confidence")
    similarity: float = Field(..., ge=0, le=1, description="Best similarity score")
    num_candidates: int = Field(..., description="Number of candidates searched")


class LandmarksResult(BaseModel):
    """Facial landmarks detection result."""

    landmarks: Dict[str, List[float]] = Field(..., description="Landmark coordinates by name")
    num_landmarks: int = Field(..., description="Total number of landmarks")
    confidence: float = Field(..., ge=0, le=1, description="Landmark detection confidence")


class LiveAnalysisResponse(BaseModel):
    """Response for each analyzed frame."""

    frame_number: int = Field(..., description="Frame sequence number")
    timestamp: float = Field(..., description="Processing timestamp")
    processing_time_ms: float = Field(..., description="Time taken to process frame")

    # Analysis results (populated based on mode)
    face: Optional[FaceDetectionResult] = None
    quality: Optional[QualityResult] = None
    demographics: Optional[DemographicsResult] = None
    liveness: Optional[LivenessResult] = None
    enrollment_ready: Optional[EnrollmentReadyResult] = None
    verification: Optional[VerificationResult] = None
    search: Optional[SearchResult] = None
    landmarks: Optional[LandmarksResult] = None

    # Error handling
    error: Optional[str] = Field(None, description="Error message if processing failed")
    skipped: bool = Field(default=False, description="Frame was skipped for performance")


class SessionStats(BaseModel):
    """Session statistics."""

    frames_received: int = Field(default=0, description="Total frames received")
    frames_processed: int = Field(default=0, description="Frames actually processed")
    frames_skipped: int = Field(default=0, description="Frames skipped")
    average_processing_time_ms: float = Field(default=0, description="Average processing time")
    best_quality_score: float = Field(default=0, description="Best quality score seen")
    enrollment_ready_count: int = Field(default=0, description="Frames marked enrollment ready")
