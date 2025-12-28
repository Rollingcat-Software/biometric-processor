"""Active liveness challenge manager.

Manages the sequence of liveness challenges and detects user responses.
"""

import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.api.schemas.active_liveness import (
    ActiveLivenessConfig,
    ActiveLivenessResponse,
    ActiveLivenessSession,
    Challenge,
    ChallengeResult,
    ChallengeStatus,
    ChallengeType,
    get_challenge_instruction,
)

logger = logging.getLogger(__name__)

# MediaPipe Face Landmarker landmark indices (478 landmarks total)
# These are the same as the old Face Mesh indices
LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
MOUTH_CORNER_LEFT = 61
MOUTH_CORNER_RIGHT = 291
UPPER_LIP_CENTER = 13
LOWER_LIP_CENTER = 14
LEFT_EYEBROW = [70, 63, 105, 66, 107]
RIGHT_EYEBROW = [336, 296, 334, 293, 300]
NOSE_TIP = 1
LEFT_EAR = 234
RIGHT_EAR = 454


class ActiveLivenessManager:
    """Manages active liveness challenge sessions."""

    def __init__(
        self,
        blink_threshold: float = 0.21,
        smile_threshold: float = 0.4,
        head_turn_threshold: float = 0.15,
        mouth_open_threshold: float = 0.5,
        eyebrow_threshold: float = 0.08,
    ):
        """Initialize the challenge manager.

        Args:
            blink_threshold: EAR threshold below which eyes are considered closed
            smile_threshold: MAR threshold above which mouth is smiling
            head_turn_threshold: Head pose threshold for turn detection
            mouth_open_threshold: MAR threshold for open mouth detection
            eyebrow_threshold: Threshold for eyebrow raise detection
        """
        self._blink_threshold = blink_threshold
        self._smile_threshold = smile_threshold
        self._head_turn_threshold = head_turn_threshold
        self._mouth_open_threshold = mouth_open_threshold
        self._eyebrow_threshold = eyebrow_threshold

        self._face_landmarker = None
        self._session: Optional[ActiveLivenessSession] = None
        self._challenge_start_time: Optional[float] = None
        self._baseline_ear: Optional[float] = None
        self._baseline_mar: Optional[float] = None
        self._blink_detected = False
        self._last_ear = 0.3

        logger.info("ActiveLivenessManager initialized")

    def _get_face_landmarker(self):
        """Lazy initialization of MediaPipe Face Landmarker (new Tasks API)."""
        if self._face_landmarker is None:
            try:
                import mediapipe as mp
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision

                # Find the model file
                model_path = Path(__file__).parent.parent.parent.parent / "models" / "face_landmarker.task"
                if not model_path.exists():
                    # Try alternate location
                    alt_paths = [
                        Path("models/face_landmarker.task"),
                        Path("C:/Users/hp/Documents/GitHub/Rollingcat-Software/biometric-processor/models/face_landmarker.task"),
                    ]
                    for alt in alt_paths:
                        if alt.exists():
                            model_path = alt
                            break
                    else:
                        raise FileNotFoundError(f"Face landmarker model not found. Expected at: {model_path}")

                logger.info(f"Loading face landmarker model from: {model_path}")

                # Configure the face landmarker
                base_options = python.BaseOptions(model_asset_path=str(model_path))
                options = vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=1,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                    output_face_blendshapes=True,  # For smile/blink detection
                )
                self._face_landmarker = vision.FaceLandmarker.create_from_options(options)
                logger.info("MediaPipe Face Landmarker initialized for active liveness")
            except ImportError as e:
                logger.error(f"MediaPipe not installed: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Face Landmarker: {e}")
                raise
        return self._face_landmarker

    def create_session(self, config: Optional[ActiveLivenessConfig] = None) -> ActiveLivenessSession:
        """Create a new active liveness session.

        Args:
            config: Session configuration

        Returns:
            New session with challenges
        """
        if config is None:
            config = ActiveLivenessConfig()

        # Generate challenges
        challenges = self._generate_challenges(config)

        self._session = ActiveLivenessSession(
            session_id=str(uuid.uuid4()),
            challenges=challenges,
            current_challenge_index=0,
            started_at=time.time(),
        )

        self._challenge_start_time = time.time()
        self._baseline_ear = None
        self._baseline_mar = None
        self._blink_detected = False

        logger.info(f"Created active liveness session: {self._session.session_id} with {len(challenges)} challenges")

        return self._session

    def _generate_challenges(self, config: ActiveLivenessConfig) -> List[Challenge]:
        """Generate a list of challenges based on config.

        Args:
            config: Session configuration

        Returns:
            List of challenges
        """
        if config.required_challenges:
            challenge_types = config.required_challenges[:config.num_challenges]
        else:
            # Default challenge pool - simpler ones first
            available = [
                ChallengeType.BLINK,
                ChallengeType.SMILE,
                ChallengeType.TURN_LEFT,
                ChallengeType.TURN_RIGHT,
            ]

            if config.randomize:
                random.shuffle(available)

            challenge_types = available[:config.num_challenges]

        challenges = []
        for ct in challenge_types:
            challenges.append(Challenge(
                type=ct,
                instruction=get_challenge_instruction(ct),
                timeout_seconds=config.challenge_timeout,
            ))

        return challenges

    def get_current_challenge(self) -> Optional[Challenge]:
        """Get the current challenge.

        Returns:
            Current challenge or None if session complete
        """
        if self._session is None or self._session.is_complete:
            return None

        if self._session.current_challenge_index >= len(self._session.challenges):
            return None

        return self._session.challenges[self._session.current_challenge_index]

    async def process_frame(self, image: np.ndarray) -> ActiveLivenessResponse:
        """Process a frame and check for challenge completion.

        Args:
            image: Camera frame (BGR format)

        Returns:
            Active liveness response with current state
        """
        if self._session is None:
            return ActiveLivenessResponse(
                instruction="No active session. Start a new session.",
                feedback="",
            )

        current_challenge = self.get_current_challenge()

        if current_challenge is None:
            # Session complete
            return self._create_completion_response()

        # Update challenge status
        if current_challenge.status == ChallengeStatus.PENDING:
            current_challenge.status = ChallengeStatus.IN_PROGRESS
            self._challenge_start_time = time.time()

        # Calculate time remaining
        elapsed = time.time() - (self._challenge_start_time or time.time())
        time_remaining = max(0, current_challenge.timeout_seconds - elapsed)

        # Check timeout
        if time_remaining <= 0:
            current_challenge.attempts += 1
            if current_challenge.attempts >= current_challenge.max_attempts:
                current_challenge.status = ChallengeStatus.FAILED
                self._advance_to_next_challenge()
            else:
                # Reset for another attempt
                self._challenge_start_time = time.time()
                time_remaining = current_challenge.timeout_seconds

            return self._create_response(
                current_challenge,
                time_remaining,
                feedback="Time's up! Try again." if current_challenge.status != ChallengeStatus.FAILED else "Challenge failed.",
            )

        # Detect challenge completion
        detection = await self._detect_challenge(image, current_challenge.type)

        feedback = ""
        if detection.detected:
            current_challenge.status = ChallengeStatus.COMPLETED
            current_challenge.confidence = detection.confidence
            feedback = "Great job! ✓"
            self._advance_to_next_challenge()
        else:
            # Provide guidance
            feedback = self._get_guidance(current_challenge.type, detection)

        return self._create_response(
            current_challenge,
            time_remaining,
            detection=detection,
            feedback=feedback,
        )

    def _advance_to_next_challenge(self):
        """Move to the next challenge or complete session."""
        if self._session is None:
            return

        self._session.current_challenge_index += 1
        self._challenge_start_time = time.time()
        self._blink_detected = False

        if self._session.current_challenge_index >= len(self._session.challenges):
            self._complete_session()

    def _complete_session(self):
        """Mark the session as complete and calculate score."""
        if self._session is None:
            return

        self._session.completed_at = time.time()
        self._session.is_complete = True

        # Calculate score
        completed = sum(1 for c in self._session.challenges if c.status == ChallengeStatus.COMPLETED)
        total = len(self._session.challenges)

        self._session.overall_score = (completed / total) * 100 if total > 0 else 0
        self._session.passed = completed >= (total * 0.6)  # 60% pass threshold

        logger.info(
            f"Session complete: {completed}/{total} challenges passed, "
            f"score={self._session.overall_score:.1f}, passed={self._session.passed}"
        )

    async def _detect_challenge(
        self,
        image: np.ndarray,
        challenge_type: ChallengeType,
    ) -> ChallengeResult:
        """Detect if the user is performing the challenge.

        Args:
            image: Camera frame
            challenge_type: Type of challenge to detect

        Returns:
            Detection result
        """
        import mediapipe as mp

        # Convert BGR to RGB for MediaPipe
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        face_landmarker = self._get_face_landmarker()
        results = face_landmarker.detect(mp_image)

        if not results.face_landmarks:
            return ChallengeResult(
                challenge_type=challenge_type,
                detected=False,
                confidence=0.0,
                details={"error": "No face detected"},
            )

        # Get landmarks from the first face
        face_landmarks = results.face_landmarks[0]
        h, w = image.shape[:2]

        # Convert to pixel coordinates (landmarks are normalized 0-1)
        points = [(int(lm.x * w), int(lm.y * h)) for lm in face_landmarks]

        # Get blendshapes if available (for smile/blink detection)
        blendshapes = {}
        if results.face_blendshapes and len(results.face_blendshapes) > 0:
            for bs in results.face_blendshapes[0]:
                blendshapes[bs.category_name] = bs.score

        # Detect based on challenge type
        if challenge_type == ChallengeType.BLINK:
            return self._detect_blink(points, face_landmarks, blendshapes)
        elif challenge_type == ChallengeType.SMILE:
            return self._detect_smile(points, blendshapes)
        elif challenge_type == ChallengeType.TURN_LEFT:
            return self._detect_head_turn(face_landmarks, "left")
        elif challenge_type == ChallengeType.TURN_RIGHT:
            return self._detect_head_turn(face_landmarks, "right")
        elif challenge_type == ChallengeType.OPEN_MOUTH:
            return self._detect_mouth_open(points, blendshapes)
        elif challenge_type == ChallengeType.RAISE_EYEBROWS:
            return self._detect_eyebrow_raise(points, face_landmarks, blendshapes)
        else:
            return ChallengeResult(
                challenge_type=challenge_type,
                detected=False,
                confidence=0.0,
                details={"error": f"Unknown challenge: {challenge_type}"},
            )

    def _calculate_ear(self, points: List[Tuple[int, int]], eye_indices: List[int]) -> float:
        """Calculate Eye Aspect Ratio."""
        try:
            p1 = np.array(points[eye_indices[0]])
            p2 = np.array(points[eye_indices[1]])
            p3 = np.array(points[eye_indices[2]])
            p4 = np.array(points[eye_indices[3]])
            p5 = np.array(points[eye_indices[4]])
            p6 = np.array(points[eye_indices[5]])

            vertical_1 = np.linalg.norm(p2 - p6)
            vertical_2 = np.linalg.norm(p3 - p5)
            horizontal = np.linalg.norm(p1 - p4)

            if horizontal == 0:
                return 0.0

            return float((vertical_1 + vertical_2) / (2.0 * horizontal))
        except (IndexError, ValueError):
            return 0.0

    def _calculate_mar(self, points: List[Tuple[int, int]]) -> float:
        """Calculate Mouth Aspect Ratio."""
        try:
            left_corner = np.array(points[MOUTH_CORNER_LEFT])
            right_corner = np.array(points[MOUTH_CORNER_RIGHT])
            upper_lip = np.array(points[UPPER_LIP_CENTER])
            lower_lip = np.array(points[LOWER_LIP_CENTER])

            horizontal = np.linalg.norm(right_corner - left_corner)
            vertical = np.linalg.norm(lower_lip - upper_lip)

            if horizontal == 0:
                return 0.0

            return float(vertical / horizontal)
        except (IndexError, ValueError):
            return 0.0

    def _detect_blink(self, points: List[Tuple[int, int]], landmarks, blendshapes: dict) -> ChallengeResult:
        """Detect eye blink using blendshapes or EAR fallback."""
        # Try using blendshapes first (more accurate)
        if blendshapes:
            left_blink = blendshapes.get("eyeBlinkLeft", 0)
            right_blink = blendshapes.get("eyeBlinkRight", 0)
            avg_blink = (left_blink + right_blink) / 2.0

            # Detect blink: eyes closed (high blink score) then opened
            eyes_closed = avg_blink > 0.5  # Threshold for eyes closed

            if eyes_closed and not self._blink_detected:
                self._blink_detected = True
            elif not eyes_closed and self._blink_detected:
                # Blink complete - eyes were closed and now open
                self._blink_detected = False
                return ChallengeResult(
                    challenge_type=ChallengeType.BLINK,
                    detected=True,
                    confidence=min(1.0, avg_blink + 0.3),
                    details={"blink_score": avg_blink, "method": "blendshapes"},
                )

            return ChallengeResult(
                challenge_type=ChallengeType.BLINK,
                detected=False,
                confidence=0.0,
                details={"blink_score": avg_blink, "eyes_closed": eyes_closed, "blink_started": self._blink_detected},
            )

        # Fallback to EAR-based detection
        left_ear = self._calculate_ear(points, LEFT_EYE_INDICES)
        right_ear = self._calculate_ear(points, RIGHT_EYE_INDICES)
        avg_ear = (left_ear + right_ear) / 2.0

        # Set baseline on first detection
        if self._baseline_ear is None and avg_ear > 0.2:
            self._baseline_ear = avg_ear

        # Detect blink: eyes closed then opened
        eyes_closed = avg_ear < self._blink_threshold

        if eyes_closed and not self._blink_detected:
            self._blink_detected = True
        elif not eyes_closed and self._blink_detected:
            # Blink complete - eyes were closed and now open
            confidence = min(1.0, (self._baseline_ear or 0.3) / avg_ear) if avg_ear > 0 else 0.5
            self._blink_detected = False
            return ChallengeResult(
                challenge_type=ChallengeType.BLINK,
                detected=True,
                confidence=confidence,
                details={"ear": avg_ear, "baseline": self._baseline_ear, "method": "ear"},
            )

        self._last_ear = avg_ear

        return ChallengeResult(
            challenge_type=ChallengeType.BLINK,
            detected=False,
            confidence=0.0,
            details={"ear": avg_ear, "eyes_closed": eyes_closed, "blink_started": self._blink_detected},
        )

    def _detect_smile(self, points: List[Tuple[int, int]], blendshapes: dict) -> ChallengeResult:
        """Detect smile using blendshapes or MAR fallback."""
        # Try using blendshapes first (more accurate)
        if blendshapes:
            left_smile = blendshapes.get("mouthSmileLeft", 0)
            right_smile = blendshapes.get("mouthSmileRight", 0)
            avg_smile = (left_smile + right_smile) / 2.0

            detected = avg_smile > 0.4  # Threshold for smile
            confidence = min(1.0, avg_smile) if detected else 0.0

            return ChallengeResult(
                challenge_type=ChallengeType.SMILE,
                detected=detected,
                confidence=confidence,
                details={"smile_score": avg_smile, "method": "blendshapes"},
            )

        # Fallback to MAR-based detection
        mar = self._calculate_mar(points)

        # Set baseline
        if self._baseline_mar is None:
            self._baseline_mar = mar

        # Calculate smile intensity relative to baseline
        if self._baseline_mar and self._baseline_mar > 0:
            smile_ratio = mar / self._baseline_mar
        else:
            smile_ratio = mar / 0.3

        detected = mar > self._smile_threshold and smile_ratio > 1.3
        confidence = min(1.0, smile_ratio - 1.0) if detected else 0.0

        return ChallengeResult(
            challenge_type=ChallengeType.SMILE,
            detected=detected,
            confidence=confidence,
            details={"mar": mar, "baseline": self._baseline_mar, "ratio": smile_ratio, "method": "mar"},
        )

    def _detect_head_turn(self, landmarks, direction: str) -> ChallengeResult:
        """Detect head turn left or right."""
        # Use nose tip and ear positions to estimate head pose
        nose = landmarks[NOSE_TIP]
        left_ear = landmarks[LEFT_EAR]
        right_ear = landmarks[RIGHT_EAR]

        # Calculate horizontal offset ratio
        nose_x = nose.x
        left_x = left_ear.x
        right_x = right_ear.x

        # Center position between ears
        center_x = (left_x + right_x) / 2

        # How much nose deviates from center
        deviation = nose_x - center_x

        if direction == "left":
            # For left turn, nose should be to the right of center (positive deviation)
            detected = deviation > self._head_turn_threshold
            confidence = min(1.0, deviation / 0.2) if detected else 0.0
        else:  # right
            # For right turn, nose should be to the left of center (negative deviation)
            detected = deviation < -self._head_turn_threshold
            confidence = min(1.0, abs(deviation) / 0.2) if detected else 0.0

        return ChallengeResult(
            challenge_type=ChallengeType.TURN_LEFT if direction == "left" else ChallengeType.TURN_RIGHT,
            detected=detected,
            confidence=confidence,
            details={"deviation": deviation, "direction": direction},
        )

    def _detect_mouth_open(self, points: List[Tuple[int, int]], blendshapes: dict) -> ChallengeResult:
        """Detect mouth open wide using blendshapes or MAR fallback."""
        # Try using blendshapes first (more accurate)
        if blendshapes:
            jaw_open = blendshapes.get("jawOpen", 0)

            detected = jaw_open > 0.4  # Threshold for open mouth
            confidence = min(1.0, jaw_open) if detected else 0.0

            return ChallengeResult(
                challenge_type=ChallengeType.OPEN_MOUTH,
                detected=detected,
                confidence=confidence,
                details={"jaw_open": jaw_open, "method": "blendshapes"},
            )

        # Fallback to MAR
        mar = self._calculate_mar(points)

        detected = mar > self._mouth_open_threshold
        confidence = min(1.0, mar / 0.7) if detected else 0.0

        return ChallengeResult(
            challenge_type=ChallengeType.OPEN_MOUTH,
            detected=detected,
            confidence=confidence,
            details={"mar": mar, "method": "mar"},
        )

    def _detect_eyebrow_raise(self, points: List[Tuple[int, int]], landmarks, blendshapes: dict) -> ChallengeResult:
        """Detect eyebrow raise using blendshapes or landmark fallback."""
        # Try using blendshapes first (more accurate)
        if blendshapes:
            inner_up = blendshapes.get("browInnerUp", 0)
            outer_up_left = blendshapes.get("browOuterUpLeft", 0)
            outer_up_right = blendshapes.get("browOuterUpRight", 0)
            avg_brow = (inner_up + outer_up_left + outer_up_right) / 3.0

            detected = avg_brow > 0.3  # Threshold for raised eyebrows
            confidence = min(1.0, avg_brow) if detected else 0.0

            return ChallengeResult(
                challenge_type=ChallengeType.RAISE_EYEBROWS,
                detected=detected,
                confidence=confidence,
                details={"brow_raise_score": avg_brow, "method": "blendshapes"},
            )

        # Fallback to landmark-based detection
        try:
            left_brow_y = np.mean([landmarks[i].y for i in LEFT_EYEBROW])
            right_brow_y = np.mean([landmarks[i].y for i in RIGHT_EYEBROW])
            avg_brow_y = (left_brow_y + right_brow_y) / 2

            # Eye center
            left_eye_y = landmarks[LEFT_EYE_INDICES[0]].y
            right_eye_y = landmarks[RIGHT_EYE_INDICES[0]].y
            avg_eye_y = (left_eye_y + right_eye_y) / 2

            # Eyebrow-eye distance (in normalized coords, eyebrows above eyes = smaller y)
            distance = avg_eye_y - avg_brow_y

            detected = distance > self._eyebrow_threshold
            confidence = min(1.0, distance / 0.12) if detected else 0.0

            return ChallengeResult(
                challenge_type=ChallengeType.RAISE_EYEBROWS,
                detected=detected,
                confidence=confidence,
                details={"brow_eye_distance": distance, "method": "landmarks"},
            )
        except (IndexError, AttributeError):
            return ChallengeResult(
                challenge_type=ChallengeType.RAISE_EYEBROWS,
                detected=False,
                confidence=0.0,
                details={"error": "Could not calculate eyebrow position"},
            )

    def _get_guidance(self, challenge_type: ChallengeType, detection: ChallengeResult) -> str:
        """Get guidance message based on detection state."""
        details = detection.details

        if challenge_type == ChallengeType.BLINK:
            if details.get("blink_started"):
                return "Good, now open your eyes!"
            return "Blink your eyes slowly"

        elif challenge_type == ChallengeType.SMILE:
            ratio = details.get("ratio", 0)
            if ratio > 1.1:
                return "Almost there, smile wider!"
            return "Give a natural smile"

        elif challenge_type in (ChallengeType.TURN_LEFT, ChallengeType.TURN_RIGHT):
            direction = "left" if challenge_type == ChallengeType.TURN_LEFT else "right"
            deviation = abs(details.get("deviation", 0))
            if deviation > 0.05:
                return f"Keep turning {direction}..."
            return f"Turn your head to the {direction}"

        elif challenge_type == ChallengeType.OPEN_MOUTH:
            mar = details.get("mar", 0)
            if mar > 0.3:
                return "Open wider!"
            return "Open your mouth wide"

        elif challenge_type == ChallengeType.RAISE_EYEBROWS:
            return "Raise your eyebrows high"

        return ""

    def _create_response(
        self,
        challenge: Challenge,
        time_remaining: float,
        detection: Optional[ChallengeResult] = None,
        feedback: str = "",
    ) -> ActiveLivenessResponse:
        """Create response for current frame."""
        if self._session is None:
            return ActiveLivenessResponse()

        completed = sum(1 for c in self._session.challenges if c.status == ChallengeStatus.COMPLETED)
        total = len(self._session.challenges)
        progress = completed / total if total > 0 else 0

        return ActiveLivenessResponse(
            current_challenge=challenge,
            challenge_progress=progress,
            time_remaining=time_remaining,
            detection=detection,
            challenges_completed=completed,
            challenges_total=total,
            session_complete=False,
            session_passed=False,
            overall_score=0.0,
            instruction=challenge.instruction,
            feedback=feedback,
        )

    def _create_completion_response(self) -> ActiveLivenessResponse:
        """Create response for completed session."""
        if self._session is None:
            return ActiveLivenessResponse(
                session_complete=True,
                instruction="Session complete",
            )

        completed = sum(1 for c in self._session.challenges if c.status == ChallengeStatus.COMPLETED)
        total = len(self._session.challenges)

        if self._session.passed:
            instruction = "All challenges completed! Liveness verified. ✓"
            feedback = f"Passed {completed}/{total} challenges"
        else:
            instruction = "Session complete. Please try again."
            feedback = f"Only {completed}/{total} challenges passed"

        return ActiveLivenessResponse(
            current_challenge=None,
            challenge_progress=1.0,
            time_remaining=0,
            challenges_completed=completed,
            challenges_total=total,
            session_complete=True,
            session_passed=self._session.passed,
            overall_score=self._session.overall_score,
            instruction=instruction,
            feedback=feedback,
        )

    def reset(self):
        """Reset the manager state."""
        self._session = None
        self._challenge_start_time = None
        self._baseline_ear = None
        self._baseline_mar = None
        self._blink_detected = False
