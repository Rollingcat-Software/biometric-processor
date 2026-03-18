"""Proctoring analysis result entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID



@dataclass(frozen=True)
class HeadPose:
    """Head orientation in 3D space."""

    pitch: float  # Nodding: negative = down, positive = up
    yaw: float    # Turning: negative = left, positive = right
    roll: float   # Tilting: negative = left, positive = right

    def is_facing_camera(
        self,
        pitch_threshold: float = 20.0,
        yaw_threshold: float = 30.0,
    ) -> bool:
        """Check if head is generally facing the camera."""
        return abs(self.pitch) < pitch_threshold and abs(self.yaw) < yaw_threshold

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {"pitch": self.pitch, "yaw": self.yaw, "roll": self.roll}


@dataclass(frozen=True)
class GazeDirection:
    """Eye gaze direction vector."""

    x: float  # Horizontal: negative = left, positive = right
    y: float  # Vertical: negative = down, positive = up

    def is_on_screen(self, threshold: float = 0.3) -> bool:
        """Check if gaze is approximately on screen."""
        return abs(self.x) < threshold and abs(self.y) < threshold

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {"x": self.x, "y": self.y}


@dataclass
class GazeAnalysisResult:
    """Result of gaze tracking analysis."""

    session_id: UUID
    timestamp: datetime
    head_pose: Optional[HeadPose]
    gaze_direction: Optional[GazeDirection]
    is_on_screen: bool
    confidence: float
    duration_off_screen_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "head_pose": self.head_pose.to_dict() if self.head_pose else None,
            "gaze_direction": self.gaze_direction.to_dict() if self.gaze_direction else None,
            "is_on_screen": self.is_on_screen,
            "confidence": self.confidence,
            "duration_off_screen_sec": self.duration_off_screen_sec,
        }


@dataclass
class DetectedObject:
    """A detected object in frame."""

    label: str
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # x, y, width, height
    is_prohibited: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bounding_box": list(self.bounding_box),
            "is_prohibited": self.is_prohibited,
        }


@dataclass
class ObjectDetectionResult:
    """Result of object detection analysis."""

    session_id: UUID
    timestamp: datetime
    objects: List[DetectedObject]
    has_prohibited_objects: bool
    frame_quality: float

    def get_prohibited_objects(self) -> List[DetectedObject]:
        """Get list of prohibited objects."""
        return [obj for obj in self.objects if obj.is_prohibited]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "objects": [obj.to_dict() for obj in self.objects],
            "has_prohibited_objects": self.has_prohibited_objects,
            "prohibited_count": len(self.get_prohibited_objects()),
            "frame_quality": self.frame_quality,
        }


@dataclass
class AudioAnalysisResult:
    """Result of audio analysis."""

    session_id: UUID
    timestamp: datetime
    has_voice_activity: bool
    speaker_count: int
    confidence: float
    is_suspicious: bool
    audio_level_db: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "has_voice_activity": self.has_voice_activity,
            "speaker_count": self.speaker_count,
            "confidence": self.confidence,
            "is_suspicious": self.is_suspicious,
            "audio_level_db": self.audio_level_db,
        }


@dataclass
class DeepfakeAnalysisResult:
    """Result of deepfake detection analysis."""

    session_id: UUID
    timestamp: datetime
    is_deepfake: bool
    confidence: float
    detection_method: str  # "frequency", "texture", "temporal", "ensemble"
    artifacts_found: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "is_deepfake": self.is_deepfake,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "artifacts_found": self.artifacts_found,
        }


@dataclass
class VerificationEvent:
    """Single verification event."""

    id: UUID
    session_id: UUID
    timestamp: datetime
    face_detected: bool
    face_matched: bool
    confidence: float
    liveness_score: Optional[float] = None
    quality_score: Optional[float] = None
    face_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "face_detected": self.face_detected,
            "face_matched": self.face_matched,
            "confidence": self.confidence,
            "liveness_score": self.liveness_score,
            "quality_score": self.quality_score,
            "face_count": self.face_count,
        }


@dataclass
class FrameAnalysisResult:
    """Aggregated result of full frame analysis."""

    session_id: UUID
    timestamp: datetime
    frame_number: int

    # Verification
    face_detected: bool
    face_matched: bool
    face_confidence: float
    face_count: int

    # Liveness
    liveness_passed: bool
    liveness_score: float

    # Gaze
    gaze_result: Optional[GazeAnalysisResult] = None

    # Objects
    object_result: Optional[ObjectDetectionResult] = None

    # Audio
    audio_result: Optional[AudioAnalysisResult] = None

    # Deepfake
    deepfake_result: Optional[DeepfakeAnalysisResult] = None

    # Quality
    frame_quality: float = 1.0

    # Processing
    processing_time_ms: float = 0.0

    def calculate_risk_score(self) -> float:
        """Calculate aggregated risk score for this frame."""
        risk = 0.0
        weights_sum = 0.0

        # Face not matched - high risk
        if not self.face_matched and self.face_detected:
            risk += 0.8
            weights_sum += 1.0

        # Multiple faces - critical
        if self.face_count > 1:
            risk += 1.0
            weights_sum += 1.0

        # Liveness failed
        if not self.liveness_passed:
            risk += 0.7
            weights_sum += 1.0

        # Deepfake detected - critical
        if self.deepfake_result and self.deepfake_result.is_deepfake:
            risk += 1.0 * self.deepfake_result.confidence
            weights_sum += 1.0

        # Gaze off screen
        if self.gaze_result and not self.gaze_result.is_on_screen:
            risk += 0.3 * self.gaze_result.confidence
            weights_sum += 0.5

        # Prohibited objects
        if self.object_result and self.object_result.has_prohibited_objects:
            prohibited = self.object_result.get_prohibited_objects()
            max_confidence = max(obj.confidence for obj in prohibited) if prohibited else 0
            risk += 0.6 * max_confidence
            weights_sum += 1.0

        # Multiple voices
        if self.audio_result and self.audio_result.speaker_count > 1:
            risk += 0.5 * self.audio_result.confidence
            weights_sum += 0.5

        if weights_sum == 0:
            return 0.0

        return min(1.0, risk / weights_sum)

    def has_critical_issues(self) -> bool:
        """Check if frame has critical issues."""
        if self.face_count > 1:
            return True
        if self.deepfake_result and self.deepfake_result.is_deepfake:
            return True
        if not self.face_matched and self.face_detected and self.face_confidence > 0.8:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": str(self.session_id),
            "timestamp": self.timestamp.isoformat(),
            "frame_number": self.frame_number,
            "face_detected": self.face_detected,
            "face_matched": self.face_matched,
            "face_confidence": self.face_confidence,
            "face_count": self.face_count,
            "liveness_passed": self.liveness_passed,
            "liveness_score": self.liveness_score,
            "gaze": self.gaze_result.to_dict() if self.gaze_result else None,
            "objects": self.object_result.to_dict() if self.object_result else None,
            "audio": self.audio_result.to_dict() if self.audio_result else None,
            "deepfake": self.deepfake_result.to_dict() if self.deepfake_result else None,
            "frame_quality": self.frame_quality,
            "risk_score": self.calculate_risk_score(),
            "has_critical_issues": self.has_critical_issues(),
            "processing_time_ms": self.processing_time_ms,
        }
