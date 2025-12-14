"""Face comparison domain entities."""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from app.domain.entities.multi_face_result import BoundingBox, BoundingBoxResponse


@dataclass
class FaceInfo:
    """Information about a detected face.

    Attributes:
        detected: Whether face was detected
        quality_score: Face quality score
        bounding_box: Face bounding box
    """

    detected: bool
    quality_score: float
    bounding_box: Optional[BoundingBox] = None


@dataclass
class FaceComparisonResult:
    """Face comparison result.

    Attributes:
        match: Whether faces match
        similarity: Similarity score (0.0-1.0)
        distance: Distance score
        threshold: Threshold used
        confidence: Confidence level (high/medium/low)
        face1: First face information
        face2: Second face information
        message: Human-readable result message
    """

    match: bool
    similarity: float
    distance: float
    threshold: float
    confidence: str
    face1: FaceInfo
    face2: FaceInfo
    message: str


# Pydantic models for API responses


class FaceInfoResponse(BaseModel):
    """API response model for face info."""

    detected: bool
    quality_score: float
    bounding_box: Optional[BoundingBoxResponse] = None


class FaceComparisonResponse(BaseModel):
    """API response model for face comparison."""

    match: bool
    similarity: float
    distance: float
    threshold: float
    confidence: str
    face1: FaceInfoResponse
    face2: FaceInfoResponse
    message: str

    @classmethod
    def from_result(cls, result: FaceComparisonResult) -> "FaceComparisonResponse":
        """Create response from domain result."""
        face1_bbox = None
        if result.face1.bounding_box:
            face1_bbox = BoundingBoxResponse(
                x=result.face1.bounding_box.x,
                y=result.face1.bounding_box.y,
                width=result.face1.bounding_box.width,
                height=result.face1.bounding_box.height,
            )

        face2_bbox = None
        if result.face2.bounding_box:
            face2_bbox = BoundingBoxResponse(
                x=result.face2.bounding_box.x,
                y=result.face2.bounding_box.y,
                width=result.face2.bounding_box.width,
                height=result.face2.bounding_box.height,
            )

        return cls(
            match=result.match,
            similarity=result.similarity,
            distance=result.distance,
            threshold=result.threshold,
            confidence=result.confidence,
            face1=FaceInfoResponse(
                detected=result.face1.detected,
                quality_score=result.face1.quality_score,
                bounding_box=face1_bbox,
            ),
            face2=FaceInfoResponse(
                detected=result.face2.detected,
                quality_score=result.face2.quality_score,
                bounding_box=face2_bbox,
            ),
            message=result.message,
        )
