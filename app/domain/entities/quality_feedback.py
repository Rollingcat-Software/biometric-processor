"""Quality feedback domain entities."""

from dataclasses import dataclass, field
from typing import List

from pydantic import BaseModel


@dataclass
class QualityIssue:
    """Individual quality issue detected in image.

    Attributes:
        code: Issue code (e.g., BLUR_DETECTED, FACE_TOO_SMALL)
        severity: Issue severity (high, medium, low)
        message: Human-readable description
        value: Measured value
        threshold: Required threshold
        suggestion: Actionable suggestion for user
    """

    code: str
    severity: str
    message: str
    value: float
    threshold: float
    suggestion: str


@dataclass
class QualityMetrics:
    """Detailed quality metrics for an image.

    All metrics are normalized to 0-100 scale for consistent display.

    Attributes:
        blur_score: Sharpness score (0-100, higher = sharper)
        brightness: Brightness score (0-100, 50 = optimal)
        face_size: Face size score (0-100, based on 200px reference)
        face_angle: Frontal alignment score (0-100, 100 = frontal, 0 = tilted)
        occlusion: Occlusion score (0-100, 0 = no occlusion, 100 = fully occluded)
    """

    blur_score: float
    brightness: float
    face_size: float  # Changed from int to float for normalized value
    face_angle: float
    occlusion: float


@dataclass
class QualityFeedback:
    """Complete quality feedback result.

    Attributes:
        overall_score: Aggregate quality score (0-100)
        passed: Whether quality requirements are met
        issues: List of detected quality issues
        metrics: Detailed quality metrics
    """

    overall_score: float
    passed: bool
    issues: List[QualityIssue] = field(default_factory=list)
    metrics: QualityMetrics = None


# Pydantic models for API responses


class QualityIssueResponse(BaseModel):
    """API response model for quality issue."""

    code: str
    severity: str
    message: str
    value: float
    threshold: float
    suggestion: str


class QualityMetricsResponse(BaseModel):
    """API response model for quality metrics.

    All values are normalized to 0-100 scale.
    """

    blur_score: float
    brightness: float
    face_size: float  # Changed from int to float (normalized)
    face_angle: float
    occlusion: float


class QualityFeedbackResponse(BaseModel):
    """API response model for quality feedback."""

    overall_score: float
    passed: bool
    issues: List[QualityIssueResponse]
    metrics: QualityMetricsResponse

    @classmethod
    def from_result(cls, result: QualityFeedback) -> "QualityFeedbackResponse":
        """Create response from domain result."""
        return cls(
            overall_score=result.overall_score,
            passed=result.passed,
            issues=[
                QualityIssueResponse(
                    code=i.code,
                    severity=i.severity,
                    message=i.message,
                    value=i.value,
                    threshold=i.threshold,
                    suggestion=i.suggestion,
                )
                for i in result.issues
            ],
            metrics=QualityMetricsResponse(
                blur_score=result.metrics.blur_score,
                brightness=result.metrics.brightness,
                face_size=result.metrics.face_size,
                face_angle=result.metrics.face_angle,
                occlusion=result.metrics.occlusion,
            ),
        )
