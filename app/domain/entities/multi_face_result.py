"""Multi-face detection domain entities."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from pydantic import BaseModel


@dataclass
class BoundingBox:
    """Bounding box for detected face.

    Attributes:
        x: X coordinate of top-left corner
        y: Y coordinate of top-left corner
        width: Box width
        height: Box height
    """

    x: int
    y: int
    width: int
    height: int


@dataclass
class BasicLandmarks:
    """Basic facial landmarks (5 points).

    Attributes:
        left_eye: Left eye center coordinates
        right_eye: Right eye center coordinates
        nose: Nose tip coordinates
        mouth_left: Left mouth corner coordinates
        mouth_right: Right mouth corner coordinates
    """

    left_eye: Tuple[int, int]
    right_eye: Tuple[int, int]
    nose: Tuple[int, int]
    mouth_left: Tuple[int, int]
    mouth_right: Tuple[int, int]


@dataclass
class DetectedFace:
    """Individual detected face information.

    Attributes:
        face_id: Index of face in detection result
        bounding_box: Face bounding box
        confidence: Detection confidence score
        quality_score: Face quality score
        landmarks: Basic facial landmarks
    """

    face_id: int
    bounding_box: BoundingBox
    confidence: float
    quality_score: float
    landmarks: Optional[BasicLandmarks] = None


@dataclass
class MultiFaceResult:
    """Multi-face detection result.

    Attributes:
        face_count: Number of faces detected
        faces: List of detected faces
        image_width: Original image width
        image_height: Original image height
    """

    face_count: int
    faces: List[DetectedFace] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0


# Pydantic models for API responses


class BoundingBoxResponse(BaseModel):
    """API response model for bounding box."""

    x: int
    y: int
    width: int
    height: int


class BasicLandmarksResponse(BaseModel):
    """API response model for basic landmarks."""

    left_eye: List[int]
    right_eye: List[int]
    nose: List[int]
    mouth_left: List[int]
    mouth_right: List[int]


class DetectedFaceResponse(BaseModel):
    """API response model for detected face."""

    face_id: int
    bounding_box: BoundingBoxResponse
    confidence: float
    quality_score: float
    landmarks: Optional[BasicLandmarksResponse] = None


class MultiFaceResponse(BaseModel):
    """API response model for multi-face detection."""

    face_count: int
    faces: List[DetectedFaceResponse]
    image_dimensions: dict

    @classmethod
    def from_result(cls, result: MultiFaceResult) -> "MultiFaceResponse":
        """Create response from domain result."""
        faces = []
        for f in result.faces:
            landmarks = None
            if f.landmarks:
                landmarks = BasicLandmarksResponse(
                    left_eye=list(f.landmarks.left_eye),
                    right_eye=list(f.landmarks.right_eye),
                    nose=list(f.landmarks.nose),
                    mouth_left=list(f.landmarks.mouth_left),
                    mouth_right=list(f.landmarks.mouth_right),
                )
            faces.append(
                DetectedFaceResponse(
                    face_id=f.face_id,
                    bounding_box=BoundingBoxResponse(
                        x=f.bounding_box.x,
                        y=f.bounding_box.y,
                        width=f.bounding_box.width,
                        height=f.bounding_box.height,
                    ),
                    confidence=f.confidence,
                    quality_score=f.quality_score,
                    landmarks=landmarks,
                )
            )
        return cls(
            face_count=result.face_count,
            faces=faces,
            image_dimensions={
                "width": result.image_width,
                "height": result.image_height,
            },
        )
