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

    Attributes:
        blur_score: Laplacian variance (higher = sharper)
        brightness: Normalized brightness (0.0-1.0)
        face_size: Face size in pixels
        face_angle: Face rotation angle in degrees
        occlusion: Occlusion percentage (0.0-1.0)
    """

    blur_score: float
    brightness: float
    face_size: int
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
    """API response model for quality metrics."""

    blur_score: float
    brightness: float
    face_size: int
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
