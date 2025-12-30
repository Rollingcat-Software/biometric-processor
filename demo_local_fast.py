#!/usr/bin/env python3
"""
Biometric Demo - FAST Real-Time Version
=========================================
Ultra-optimized for 20-30+ FPS real-time performance.

KEY OPTIMIZATIONS:
    1. Direct OpenCV Haar Cascade for face detection (~20ms vs 400ms DeepFace)
    2. MediaPipe reuse - detection from landmarks (already loaded)
    3. DeepFace ONLY for embeddings (when needed)
    4. Aggressive frame skipping for heavy operations
    5. Minimal cache intervals (fast detection allows this)

Performance Target: 20-30+ FPS

Usage:
    python demo_local_fast.py                    # All features
    python demo_local_fast.py --mode face        # Face detection only
    python demo_local_fast.py --profile          # Show performance metrics

Controls:
    q - Quit  |  m - Cycle modes  |  e - Enroll  |  l - Liveness puzzle
    d - Delete all  |  c - Card  |  r - Record  |  p - Profiler  |  h - Help
"""

import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from collections import deque
import pickle

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("FastDemo")


# =============================================================================
# PERFORMANCE PROFILER
# =============================================================================

class Profiler:
    """Minimal performance profiler."""

    def __init__(self):
        self.metrics: Dict[str, deque] = {}
        self.enabled = False

    def time(self, name: str):
        """Context manager for timing."""
        return ProfilerContext(self, name)

    def record(self, name: str, ms: float):
        if name not in self.metrics:
            self.metrics[name] = deque(maxlen=60)
        self.metrics[name].append(ms)

    def get_avg(self, name: str) -> float:
        if name in self.metrics and self.metrics[name]:
            return sum(self.metrics[name]) / len(self.metrics[name])
        return 0

    def draw(self, frame: np.ndarray):
        if not self.enabled:
            return

        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 45), (250, 45 + len(self.metrics) * 18 + 25), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)

        cv2.putText(frame, "PROFILER", (15, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        y = 80
        for name, vals in sorted(self.metrics.items()):
            avg = sum(vals) / len(vals) if vals else 0
            color = (0, 255, 0) if avg < 30 else (0, 255, 255) if avg < 60 else (0, 0, 255)
            cv2.putText(frame, f"{name}: {avg:.1f}ms", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
            y += 18


class ProfilerContext:
    def __init__(self, profiler: Profiler, name: str):
        self.profiler = profiler
        self.name = name
        self.start = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        ms = (time.perf_counter() - self.start) * 1000
        self.profiler.record(self.name, ms)


# =============================================================================
# FAST FACE DETECTOR (MediaPipe Tasks API - handles rotated faces!)
# =============================================================================

class FastFaceDetector:
    """Fast face detection using MediaPipe Tasks API (NOT Solutions API).

    ADVANTAGES over Haar Cascade:
    - Detects rotated faces (up to ~45 degrees yaw) - NOT just frontal!
    - GPU accelerated when available
    - Better accuracy with similar speed (~15-25ms)

    Performance: ~15-25ms vs ~300-400ms for DeepFace.extract_faces
    """

    _instance = None
    _detector = None
    _mp = None
    _use_tasks = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load_detector()
        return cls._instance

    @classmethod
    def _load_detector(cls):
        """Load MediaPipe Face Detection using Tasks API."""
        if cls._detector is None:
            try:
                import mediapipe as mp
                cls._mp = mp

                # Use Tasks API (works in newer MediaPipe versions)
                if hasattr(mp, 'tasks'):
                    from mediapipe.tasks import python as tasks
                    from mediapipe.tasks.python import vision
                    import urllib.request

                    model_path = "blaze_face_short_range.tflite"
                    if not os.path.exists(model_path):
                        logger.info("Downloading BlazeFace model for face detection...")
                        url = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
                        urllib.request.urlretrieve(url, model_path)

                    opts = vision.FaceDetectorOptions(
                        base_options=tasks.BaseOptions(model_asset_path=model_path),
                        min_detection_confidence=0.5
                    )
                    cls._detector = vision.FaceDetector.create_from_options(opts)
                    cls._use_tasks = True
                    logger.info("Loaded MediaPipe Tasks Face Detector (handles rotated faces)")
                    return

                # Fallback to Solutions API if Tasks not available
                if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_detection'):
                    cls._detector = mp.solutions.face_detection.FaceDetection(
                        model_selection=0, min_detection_confidence=0.5
                    )
                    cls._use_tasks = False
                    logger.info("Loaded MediaPipe Solutions Face Detection")
                    return

                raise RuntimeError("No MediaPipe face detection available")

            except Exception as e:
                logger.warning(f"MediaPipe Face Detection failed, falling back to Haar: {e}")
                # Fallback to Haar
                opencv_data = os.path.join(cv2.__path__[0], "data")
                cascade_path = os.path.join(opencv_data, "haarcascade_frontalface_alt2.xml")
                cls._detector = cv2.CascadeClassifier(cascade_path)
                cls._mp = None
                cls._use_tasks = False
                logger.info(f"Loaded Haar Cascade fallback: {cascade_path}")

    def detect(self, frame: np.ndarray, scale_factor: float = 1.1, min_neighbors: int = 4,
               min_size: Tuple[int, int] = (30, 30)) -> List[Dict]:
        """Detect faces in frame - supports rotated faces!

        Returns list of dicts with 'facial_area' and 'confidence' keys
        (compatible with DeepFace format).
        """
        h, w = frame.shape[:2]
        results = []

        if self._mp is not None and self._use_tasks:
            # MediaPipe Tasks API - handles rotated faces!
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            detections = self._detector.detect(mp_img)

            if detections.detections:
                for detection in detections.detections:
                    bbox = detection.bounding_box
                    x = bbox.origin_x
                    y = bbox.origin_y
                    fw = bbox.width
                    fh = bbox.height

                    # Clamp to frame bounds
                    x = max(0, x)
                    y = max(0, y)
                    fw = min(fw, w - x)
                    fh = min(fh, h - y)

                    if fw > 30 and fh > 30:
                        results.append({
                            'facial_area': {'x': x, 'y': y, 'w': fw, 'h': fh},
                            'confidence': detection.categories[0].score if detection.categories else 0.9,
                        })

        elif self._mp is not None and not self._use_tasks:
            # MediaPipe Solutions API fallback
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            detections = self._detector.process(rgb)

            if detections.detections:
                for detection in detections.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    fw = int(bbox.width * w)
                    fh = int(bbox.height * h)

                    x = max(0, x)
                    y = max(0, y)
                    fw = min(fw, w - x)
                    fh = min(fh, h - y)

                    if fw > 30 and fh > 30:
                        results.append({
                            'facial_area': {'x': x, 'y': y, 'w': fw, 'h': fh},
                            'confidence': detection.score[0] if detection.score else 0.9,
                        })
        else:
            # Haar fallback (frontal only)
            max_width = 640
            if w > max_width:
                scale = max_width / w
                small = cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                scale = 1.0
                small = frame

            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            faces = self._detector.detectMultiScale(
                gray, scaleFactor=scale_factor, minNeighbors=min_neighbors,
                minSize=min_size, flags=cv2.CASCADE_SCALE_IMAGE
            )

            for (x, y, fw, fh) in faces:
                results.append({
                    'facial_area': {
                        'x': int(x / scale), 'y': int(y / scale),
                        'w': int(fw / scale), 'h': int(fh / scale)
                    },
                    'confidence': 0.95,
                })

        return results


# =============================================================================
# FAST QUALITY & LIVENESS (Optimized)
# =============================================================================

class FastQualityAssessor:
    """Minimal quality assessment - fast and simple."""

    def __init__(self, blur_threshold: float = 100.0):
        self.blur_threshold = blur_threshold

    def assess(self, face_img: np.ndarray) -> Dict[str, Any]:
        if face_img is None or face_img.size == 0:
            return {'score': 0, 'issues': ['No image']}

        h, w = face_img.shape[:2]
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY) if len(face_img.shape) == 3 else face_img

        # Blur score (Laplacian variance)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(100, (lap_var / self.blur_threshold) * 100)

        # Size score
        size_score = min(100, min(h, w) / 80 * 50)

        # Brightness
        brightness = np.mean(gray)
        bright_ok = 50 < brightness < 200

        issues = []
        if blur_score < 50:
            issues.append('Blurry')
        if size_score < 50:
            issues.append('Small')
        if not bright_ok:
            issues.append('Dark' if brightness < 50 else 'Bright')

        score = (blur_score + size_score + (100 if bright_ok else 50)) / 3

        return {'score': score, 'blur': blur_score, 'size': size_score, 'issues': issues}


class FastLivenessDetector:
    """Fast liveness detection - texture + color + naturalness analysis.

    FIXED: Previous algorithm penalized real skin (low saturation).
    Real faces have: moderate saturation (40-100), natural texture, skin tone colors.
    Print attacks have: high saturation OR grayscale, flat texture, unnatural colors.
    """

    _gabor_kernels = None

    def __init__(self, threshold: float = 50.0):
        self.threshold = threshold
        if FastLivenessDetector._gabor_kernels is None:
            FastLivenessDetector._gabor_kernels = [
                cv2.getGaborKernel((21, 21), 5.0, theta, 10.0, 0.5, 0)
                for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]
            ]

    def check(self, face_img: np.ndarray) -> Dict[str, Any]:
        if face_img is None or face_img.size == 0:
            return {'is_live': False, 'score': 0}

        try:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)

            # 1. Texture score - real faces have natural texture variation
            # Laplacian variance measures edge sharpness/texture detail
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Scale: 50-500+ is good for real faces, <30 is flat (print)
            texture = min(100, max(0, (lap_var - 20) / 3))

            # 2. Color naturalness - FIXED: Real skin has MODERATE saturation!
            hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
            sat_mean = np.mean(hsv[:, :, 1])
            # Real skin saturation is typically 40-100 (0-255 scale)
            # Too low (<30) = grayscale/washed out | Too high (>150) = oversaturated print
            if 30 <= sat_mean <= 120:
                color = 100  # Good natural range
            elif sat_mean < 30:
                color = max(0, sat_mean * 2)  # Penalty for too gray
            else:
                color = max(0, 100 - (sat_mean - 120) * 0.8)  # Penalty for oversaturated

            # 3. Skin tone check - hue should be in skin range (0-50 or 330-360 in OpenCV: 0-25)
            hue_mean = np.mean(hsv[:, :, 0])
            skin_tone = 100 if (hue_mean < 25 or hue_mean > 165) else max(0, 100 - abs(hue_mean - 15) * 3)

            # 4. Moire/pattern detection (print artifacts)
            moire = 100
            for kernel in self._gabor_kernels:
                gabor_std = np.std(cv2.filter2D(gray, cv2.CV_64F, kernel))
                # Print attacks often show periodic patterns with high std
                if gabor_std > 40:
                    moire -= 20

            # 5. Local contrast variation - real faces have varying texture across regions
            h, w = gray.shape
            if h >= 20 and w >= 20:
                regions = [
                    gray[:h//2, :w//2], gray[:h//2, w//2:],
                    gray[h//2:, :w//2], gray[h//2:, w//2:]
                ]
                variances = [np.var(r) for r in regions]
                var_range = max(variances) - min(variances)
                # Real faces have different texture in different regions
                local_var = min(100, var_range / 10)
            else:
                local_var = 50

            # Combined score with adjusted weights
            score = (texture * 0.25 + color * 0.25 + skin_tone * 0.15 +
                    moire * 0.20 + local_var * 0.15)

            return {'is_live': score >= self.threshold, 'score': score}
        except Exception:
            return {'is_live': False, 'score': 0}


# =============================================================================
# BIOMETRIC PUZZLE - Active Liveness Challenge System
# =============================================================================

class BiometricPuzzle:
    """Biometric Puzzle - Challenge-Response Liveness Detection.

    Extended challenge pool with multiple detection methods:
    - Eye actions: Blink, Blink Left, Blink Right
    - Mouth actions: Smile, Open Mouth
    - Head movements: Turn Left/Right, Look Up/Down
    - Dynamic actions: Nod, Shake Head, Raise Eyebrows
    """

    # MediaPipe Face Mesh landmark indices
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    UPPER_LIP = 13
    LOWER_LIP = 14
    MOUTH_LEFT = 61
    MOUTH_RIGHT = 291
    LEFT_EYEBROW = [70, 63, 105, 66, 107]
    RIGHT_EYEBROW = [300, 293, 334, 296, 336]
    LEFT_EYE_CENTER = 468  # iris
    RIGHT_EYE_CENTER = 473  # iris
    NOSE_TIP = 1
    CHIN = 152

    # Challenge definitions: (display_name, key, icon)
    # Note: Left/Right are from USER's perspective (mirrored camera)
    CHALLENGES = {
        'BLINK': ('Close Both Eyes', 'blink', '😌'),
        'CLOSE_LEFT': ('Close YOUR Left Eye', 'close_left', '😉'),
        'CLOSE_RIGHT': ('Close YOUR Right Eye', 'close_right', '😉'),
        'SMILE': ('Smile Wide (Show Teeth)', 'smile', '😁'),
        'OPEN_MOUTH': ('Open Mouth Wide', 'open_mouth', '😮'),
        'TURN_LEFT': ('Turn Head Left', 'turn_left', '👈'),
        'TURN_RIGHT': ('Turn Head Right', 'turn_right', '👉'),
        'LOOK_UP': ('Look Up (Chin Up)', 'look_up', '👆'),
        'LOOK_DOWN': ('Look Down (Chin Down)', 'look_down', '👇'),
        'RAISE_BOTH_BROWS': ('Raise Both Eyebrows', 'raise_both', '🤨'),
        'RAISE_LEFT_BROW': ('Raise YOUR Left Eyebrow', 'raise_left', '🤔'),
        'RAISE_RIGHT_BROW': ('Raise YOUR Right Eyebrow', 'raise_right', '🧐'),
        'NOD': ('Nod Your Head', 'nod', '↕️'),
        'SHAKE_HEAD': ('Shake Your Head', 'shake_head', '↔️'),
    }

    # Thresholds - STRICT values to prevent false positives
    EAR_THRESHOLD = 0.22  # Above this = eye open
    EAR_CLOSED_THRESHOLD = 0.17  # Must go BELOW this for closed eye
    SMILE_CORNER_THRESHOLD = 0.05  # Lip corner raise (stricter)
    SMILE_WIDTH_THRESHOLD = 0.60  # Mouth must widen significantly (stricter)
    MOUTH_OPEN_THRESHOLD = 0.12  # Mouth open ratio
    YAW_THRESHOLD = 20    # Degrees for turn left/right
    PITCH_THRESHOLD = 12  # Degrees for look up/down
    EYEBROW_RAISE_THRESHOLD = 1.20  # Both eyebrows ratio (VERY strict!)
    SINGLE_BROW_THRESHOLD = 1.25  # Single eyebrow raise (VERY strict!)

    def __init__(self, num_challenges: int = 3):
        self.num_challenges = num_challenges
        self.challenges = []
        self.current_idx = 0
        self.is_active = False
        self.is_complete = False
        self.passed = False

        # Detection state
        self._hold_start = 0
        self._hold_duration = 0.6  # Seconds to hold action
        self._action_detected = False

        # For dynamic challenges (nod, shake)
        self._motion_history = deque(maxlen=30)
        self._baseline_eyebrow_dist = None

        # Results
        self.results = []

    def start(self, challenge_types: List[str] = None):
        """Start a new puzzle with random or specified challenges."""
        import random

        if challenge_types:
            self.challenges = challenge_types[:self.num_challenges]
        else:
            # Random selection from pool - balanced mix of challenge types
            simple_pool = [
                'BLINK', 'CLOSE_LEFT', 'CLOSE_RIGHT',           # Eye challenges
                'SMILE', 'OPEN_MOUTH',                          # Mouth challenges
                'TURN_LEFT', 'TURN_RIGHT',                      # Head turn challenges
                'LOOK_UP', 'LOOK_DOWN',                         # Head tilt challenges
                'RAISE_BOTH_BROWS', 'RAISE_LEFT_BROW', 'RAISE_RIGHT_BROW',  # Eyebrow challenges
            ]
            self.challenges = random.sample(simple_pool, min(self.num_challenges, len(simple_pool)))

        self.current_idx = 0
        self.is_active = True
        self.is_complete = False
        self.passed = False
        self._hold_start = 0
        self._action_detected = False
        self._baseline_eyebrow_dist = None
        self.results = []

        logger.info(f"Biometric Puzzle started: {self.challenges}")

    def stop(self):
        """Stop the puzzle."""
        self.is_active = False
        self.is_complete = True
        logger.info(f"Biometric Puzzle stopped. Results: {self.results}")

    def get_current_challenge(self) -> Optional[Dict]:
        """Get current challenge info."""
        if not self.is_active or self.current_idx >= len(self.challenges):
            return None

        challenge_key = self.challenges[self.current_idx]
        name, func, icon = self.CHALLENGES.get(challenge_key, ('Unknown', 'unknown', '?'))

        return {
            'key': challenge_key,
            'name': name,
            'icon': icon,
            'index': self.current_idx,
            'total': len(self.challenges),
        }

    def calculate_ear(self, landmarks: List[Tuple[int, int]], eye_indices: List[int]) -> float:
        """Calculate Eye Aspect Ratio (EAR).

        EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        Low EAR = eye closed, High EAR = eye open
        """
        try:
            p1 = np.array(landmarks[eye_indices[0]])
            p2 = np.array(landmarks[eye_indices[1]])
            p3 = np.array(landmarks[eye_indices[2]])
            p4 = np.array(landmarks[eye_indices[3]])
            p5 = np.array(landmarks[eye_indices[4]])
            p6 = np.array(landmarks[eye_indices[5]])

            vertical_1 = np.linalg.norm(p2 - p6)
            vertical_2 = np.linalg.norm(p3 - p5)
            horizontal = np.linalg.norm(p1 - p4)

            if horizontal == 0:
                return 0.3  # Default open

            return (vertical_1 + vertical_2) / (2.0 * horizontal)
        except (IndexError, ValueError):
            return 0.3

    def calculate_mar(self, landmarks: List[Tuple[int, int]]) -> float:
        """Calculate Mouth Aspect Ratio (MAR) - for mouth OPEN detection.

        MAR = vertical / horizontal
        High MAR = mouth open
        """
        try:
            left = np.array(landmarks[self.MOUTH_LEFT])
            right = np.array(landmarks[self.MOUTH_RIGHT])
            upper = np.array(landmarks[self.UPPER_LIP])
            lower = np.array(landmarks[self.LOWER_LIP])

            horizontal = np.linalg.norm(right - left)
            vertical = np.linalg.norm(lower - upper)

            if horizontal == 0:
                return 0.0

            return vertical / horizontal
        except (IndexError, ValueError):
            return 0.0

    def calculate_smile(self, landmarks: List[Tuple[int, int]]) -> Tuple[float, float]:
        """Calculate smile score based on lip corner position.

        When smiling:
        - Mouth corners move UP (Y decreases)
        - Mouth corners move OUT (width increases)

        Returns: (corner_raise_ratio, width_ratio) relative to face height
        """
        try:
            # Get mouth landmarks
            left_corner = np.array(landmarks[self.MOUTH_LEFT])
            right_corner = np.array(landmarks[self.MOUTH_RIGHT])
            upper_lip = np.array(landmarks[self.UPPER_LIP])
            lower_lip = np.array(landmarks[self.LOWER_LIP])

            # Get face reference points
            nose_tip = np.array(landmarks[self.NOSE_TIP])
            chin = np.array(landmarks[self.CHIN])

            # Face height for normalization
            face_height = np.linalg.norm(chin - nose_tip)
            if face_height == 0:
                return 0.0, 0.0

            # Mouth center Y
            mouth_center_y = (upper_lip[1] + lower_lip[1]) / 2

            # Corner raise = how much corners are above mouth center
            # (lower Y = higher position, so negative means raised)
            left_raise = mouth_center_y - left_corner[1]
            right_raise = mouth_center_y - right_corner[1]
            avg_raise = (left_raise + right_raise) / 2

            # Normalize by face height
            corner_raise_ratio = avg_raise / face_height

            # Mouth width ratio
            mouth_width = np.linalg.norm(right_corner - left_corner)
            width_ratio = mouth_width / face_height

            return corner_raise_ratio, width_ratio
        except (IndexError, ValueError):
            return 0.0, 0.0

    def calculate_eyebrow_raise(self, landmarks: List[Tuple[int, int]]) -> Tuple[float, float, float]:
        """Calculate eyebrow raise ratio compared to baseline.

        Returns: (both_ratio, left_ratio, right_ratio)
        Note: Left/Right from USER's perspective (mirrored camera)
        - MediaPipe LEFT_EYE = user's left eye (appears on left of screen when mirrored)
        """
        try:
            # Average eyebrow Y position
            left_brow_y = np.mean([landmarks[i][1] for i in self.LEFT_EYEBROW])
            right_brow_y = np.mean([landmarks[i][1] for i in self.RIGHT_EYEBROW])

            # Average eye Y position
            left_eye_y = np.mean([landmarks[i][1] for i in self.LEFT_EYE])
            right_eye_y = np.mean([landmarks[i][1] for i in self.RIGHT_EYE])

            # Distance from eyebrow to eye (larger = raised more)
            left_dist = left_eye_y - left_brow_y
            right_dist = right_eye_y - right_brow_y
            avg_dist = (left_dist + right_dist) / 2

            # Set baseline on first call
            if self._baseline_eyebrow_dist is None:
                self._baseline_eyebrow_dist = {'left': left_dist, 'right': right_dist, 'avg': avg_dist}
                return 1.0, 1.0, 1.0

            base = self._baseline_eyebrow_dist
            both_ratio = avg_dist / base['avg'] if base['avg'] > 0 else 1.0
            left_ratio = left_dist / base['left'] if base['left'] > 0 else 1.0
            right_ratio = right_dist / base['right'] if base['right'] > 0 else 1.0

            return both_ratio, left_ratio, right_ratio
        except (IndexError, ValueError):
            return 1.0, 1.0, 1.0

    def check_challenge(self, landmarks: List[Tuple[int, int]], yaw: float, pitch: float) -> Dict:
        """Check if current challenge is being performed.

        Returns dict with: detected (bool), progress (0-100), message (str)
        """
        if not self.is_active or self.current_idx >= len(self.challenges):
            return {'detected': False, 'progress': 0, 'message': 'No active challenge'}

        challenge = self.challenges[self.current_idx]

        # Calculate metrics
        # Note: In mirrored camera, user's left eye = MediaPipe LEFT_EYE = left side of screen
        left_ear = self.calculate_ear(landmarks, self.LEFT_EYE)
        right_ear = self.calculate_ear(landmarks, self.RIGHT_EYE)
        avg_ear = (left_ear + right_ear) / 2
        mar = self.calculate_mar(landmarks)
        smile_raise, smile_width = self.calculate_smile(landmarks)
        brow_both, brow_left, brow_right = self.calculate_eyebrow_raise(landmarks)

        # Track motion for dynamic challenges
        self._motion_history.append((yaw, pitch, time.time()))

        # Check based on challenge type
        detected = False
        message = ""

        if challenge == 'BLINK':
            # Close both eyes - STRICT threshold
            detected = avg_ear < self.EAR_CLOSED_THRESHOLD
            message = f"EAR: {avg_ear:.2f} (need <{self.EAR_CLOSED_THRESHOLD})" + (" ✓" if detected else "")

        elif challenge == 'CLOSE_LEFT':
            # User's LEFT eye in mirror = MediaPipe RIGHT_EYE (swapped!)
            # When camera is mirrored, anatomical mapping is reversed
            detected = right_ear < self.EAR_CLOSED_THRESHOLD and left_ear > self.EAR_THRESHOLD
            message = f"YourL:{right_ear:.2f} YourR:{left_ear:.2f}" + (" ✓" if detected else " - Close YOUR left!")

        elif challenge == 'CLOSE_RIGHT':
            # User's RIGHT eye in mirror = MediaPipe LEFT_EYE (swapped!)
            detected = left_ear < self.EAR_CLOSED_THRESHOLD and right_ear > self.EAR_THRESHOLD
            message = f"YourL:{right_ear:.2f} YourR:{left_ear:.2f}" + (" ✓" if detected else " - Close YOUR right!")

        elif challenge == 'SMILE':
            # Smile: corners raised AND mouth widened - STRICT
            is_corners_raised = smile_raise > self.SMILE_CORNER_THRESHOLD
            is_mouth_wide = smile_width > self.SMILE_WIDTH_THRESHOLD
            detected = is_corners_raised and is_mouth_wide
            message = f"Raise:{smile_raise:.3f}>{self.SMILE_CORNER_THRESHOLD} W:{smile_width:.2f}>{self.SMILE_WIDTH_THRESHOLD}" + (" ✓" if detected else "")

        elif challenge == 'OPEN_MOUTH':
            detected = mar > self.MOUTH_OPEN_THRESHOLD
            message = f"Open: {mar:.2f}" + (" ✓" if detected else f" - Need >{self.MOUTH_OPEN_THRESHOLD}")

        elif challenge == 'TURN_LEFT':
            detected = yaw < -self.YAW_THRESHOLD
            message = f"Yaw: {yaw:.0f}°" + (" ✓" if detected else f" - Need <{-self.YAW_THRESHOLD}°")

        elif challenge == 'TURN_RIGHT':
            detected = yaw > self.YAW_THRESHOLD
            message = f"Yaw: {yaw:.0f}°" + (" ✓" if detected else f" - Need >{self.YAW_THRESHOLD}°")

        elif challenge == 'LOOK_UP':
            # Tilt head back (chin up) = negative pitch in MediaPipe
            detected = pitch < -self.PITCH_THRESHOLD
            message = f"Pitch: {pitch:.0f}°" + (" ✓" if detected else f" - Chin UP! Need <{-self.PITCH_THRESHOLD}°")

        elif challenge == 'LOOK_DOWN':
            # Tilt head forward (chin down) = positive pitch in MediaPipe
            detected = pitch > self.PITCH_THRESHOLD
            message = f"Pitch: {pitch:.0f}°" + (" ✓" if detected else f" - Chin DOWN! Need >{self.PITCH_THRESHOLD}°")

        elif challenge == 'RAISE_BOTH_BROWS':
            detected = brow_both > self.EYEBROW_RAISE_THRESHOLD
            message = f"Both: {brow_both:.2f}x (need >{self.EYEBROW_RAISE_THRESHOLD})" + (" ✓" if detected else "")

        elif challenge == 'RAISE_LEFT_BROW':
            # User's LEFT brow = MediaPipe LEFT brow (NOT swapped for eyebrows!)
            detected = brow_left > self.SINGLE_BROW_THRESHOLD and brow_right < self.EYEBROW_RAISE_THRESHOLD
            message = f"L:{brow_left:.2f} R:{brow_right:.2f} (need L>{self.SINGLE_BROW_THRESHOLD})" + (" ✓" if detected else "")

        elif challenge == 'RAISE_RIGHT_BROW':
            # User's RIGHT brow = MediaPipe RIGHT brow (NOT swapped for eyebrows!)
            detected = brow_right > self.SINGLE_BROW_THRESHOLD and brow_left < self.EYEBROW_RAISE_THRESHOLD
            message = f"L:{brow_left:.2f} R:{brow_right:.2f} (need R>{self.SINGLE_BROW_THRESHOLD})" + (" ✓" if detected else "")

        elif challenge == 'NOD':
            detected = self._check_nod()
            message = "Nod your head up and down" + (" ✓" if detected else "")

        elif challenge == 'SHAKE_HEAD':
            detected = self._check_shake()
            message = "Shake your head left and right" + (" ✓" if detected else "")

        # Handle hold timer
        if detected:
            if not self._action_detected:
                self._hold_start = time.time()
                self._action_detected = True

            hold_time = time.time() - self._hold_start
            progress = min(100, (hold_time / self._hold_duration) * 100)

            if hold_time >= self._hold_duration:
                # Challenge completed!
                self._advance_challenge()
                return {'detected': True, 'progress': 100, 'message': 'Completed!', 'completed': True}

            return {'detected': True, 'progress': progress, 'message': message}
        else:
            self._action_detected = False
            self._hold_start = time.time()
            return {'detected': False, 'progress': 0, 'message': message}

    def _check_nod(self) -> bool:
        """Check for nodding motion (pitch oscillation)."""
        if len(self._motion_history) < 20:
            return False

        pitches = [p for _, p, _ in self._motion_history]
        pitch_range = max(pitches) - min(pitches)
        return pitch_range > 25  # Need 25 degrees of pitch movement

    def _check_shake(self) -> bool:
        """Check for head shake motion (yaw oscillation)."""
        if len(self._motion_history) < 20:
            return False

        yaws = [y for y, _, _ in self._motion_history]
        yaw_range = max(yaws) - min(yaws)
        return yaw_range > 35  # Need 35 degrees of yaw movement

    def _advance_challenge(self):
        """Move to next challenge or complete puzzle."""
        self.results.append({
            'challenge': self.challenges[self.current_idx],
            'passed': True,
            'time': time.time()
        })

        self.current_idx += 1
        self._action_detected = False
        self._hold_start = 0
        self._baseline_eyebrow_dist = None
        self._motion_history.clear()

        if self.current_idx >= len(self.challenges):
            self.is_complete = True
            self.is_active = False
            self.passed = True
            logger.info("Biometric Puzzle PASSED - All challenges completed!")
        else:
            logger.info(f"Challenge {self.current_idx}/{len(self.challenges)}: {self.challenges[self.current_idx]}")


# =============================================================================
# FACE DATABASE
# =============================================================================

class FaceDB:
    """Simple face database."""

    def __init__(self, path: str = "face_db.pkl"):
        self.path = path
        self.faces: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'rb') as f:
                    self.faces = pickle.load(f)
                logger.info(f"Loaded {len(self.faces)} enrolled faces")
            except Exception:
                self.faces = {}

    def save(self):
        with open(self.path, 'wb') as f:
            pickle.dump(self.faces, f)

    def enroll(self, name: str, embedding: np.ndarray, thumb: np.ndarray):
        self.faces[name] = {
            'embeddings': [embedding],
            'thumbnail': thumb,
            'enrolled_at': datetime.now().isoformat()
        }
        self.save()

    def add_embedding(self, name: str, emb: np.ndarray):
        if name in self.faces:
            embs = self.faces[name].get('embeddings', [])
            if len(embs) >= 5:
                embs.pop(0)
            embs.append(emb)
            self.faces[name]['embeddings'] = embs
            self.save()

    def search(self, emb: np.ndarray, threshold: float = 0.5) -> Optional[Tuple[str, float]]:
        best_name, best_sim = None, 0
        emb = np.array(emb).flatten()

        for name, data in self.faces.items():
            for stored in data.get('embeddings', []):
                stored = np.array(stored).flatten()
                if len(emb) == len(stored):
                    norm_a, norm_b = np.linalg.norm(emb), np.linalg.norm(stored)
                    if norm_a > 0 and norm_b > 0:
                        sim = np.dot(emb, stored) / (norm_a * norm_b)
                        if sim > best_sim and sim >= threshold:
                            best_sim, best_name = sim, name

        return (best_name, best_sim) if best_name else None


# =============================================================================
# FACE TRACKER
# =============================================================================

class FaceTracker:
    """Simple centroid-based face tracker."""

    def __init__(self, max_gone: int = 15):
        self.next_id = 0
        self.tracks: Dict[int, Dict] = {}
        self.max_gone = max_gone

    def update(self, detections: List[Dict]) -> Dict[int, Dict]:
        if not detections:
            for tid in list(self.tracks.keys()):
                self.tracks[tid]['gone'] += 1
                if self.tracks[tid]['gone'] > self.max_gone:
                    del self.tracks[tid]
            return {}

        centroids = []
        for d in detections:
            a = d.get('facial_area', {})
            cx = a.get('x', 0) + a.get('w', 0) // 2
            cy = a.get('y', 0) + a.get('h', 0) // 2
            centroids.append((cx, cy))

        if not self.tracks:
            result = {}
            for i, d in enumerate(detections):
                self.tracks[self.next_id] = {'centroid': centroids[i], 'gone': 0}
                result[self.next_id] = d
                self.next_id += 1
            return result

        used = set()
        result = {}

        for tid, track in list(self.tracks.items()):
            tc = track['centroid']
            best_j, best_d = -1, float('inf')

            for j, nc in enumerate(centroids):
                if j not in used:
                    d = np.sqrt((tc[0] - nc[0])**2 + (tc[1] - nc[1])**2)
                    if d < best_d and d < 120:
                        best_d, best_j = d, j

            if best_j >= 0:
                self.tracks[tid]['centroid'] = centroids[best_j]
                self.tracks[tid]['gone'] = 0
                result[tid] = detections[best_j]
                used.add(best_j)
            else:
                self.tracks[tid]['gone'] += 1
                if self.tracks[tid]['gone'] > self.max_gone:
                    del self.tracks[tid]

        for j, d in enumerate(detections):
            if j not in used:
                self.tracks[self.next_id] = {'centroid': centroids[j], 'gone': 0}
                result[self.next_id] = d
                self.next_id += 1

        return result


# =============================================================================
# CARD DETECTOR (Lazy Load)
# =============================================================================

class CardDetector:
    """YOLO card detector with lazy loading."""

    CARD_LABELS = {
        'tc_kimlik': 'Turkish ID',
        'ehliyet': 'License',
        'pasaport': 'Passport',
        'ogrenci_karti': 'Student',
    }

    def __init__(self):
        self._model = None
        self._available = None

    def _load(self):
        if self._model is not None:
            return self._model

        model_path = "app/core/card_type_model/best.pt"
        if not os.path.exists(model_path):
            self._available = False
            return None

        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            self._available = True
            logger.info("YOLO card model loaded")
            return self._model
        except Exception as e:
            logger.warning(f"Card detection unavailable: {e}")
            self._available = False
            return None

    def detect(self, frame: np.ndarray) -> Dict:
        model = self._load()
        if model is None:
            return {'detected': False}

        try:
            h, w = frame.shape[:2]

            # OPTIMIZATION: Resize to 480px width AND use smaller inference size
            # This reduces YOLO inference time significantly on CPU
            max_width = 480
            if w > max_width:
                scale = max_width / w
                small = cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                scale = 1.0
                small = frame

            # Use imgsz=320 for faster CPU inference (default is 640)
            results = model(small, conf=0.45, verbose=False, imgsz=320)
            if len(results[0].boxes) == 0:
                return {'detected': False}

            best = max(results[0].boxes, key=lambda b: float(b.conf[0]))
            cls_id = int(best.cls[0])
            conf = float(best.conf[0])
            name = model.names[cls_id]

            # Scale box back to original size
            box = best.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = int(box[0]/scale), int(box[1]/scale), int(box[2]/scale), int(box[3]/scale)

            return {
                'detected': True,
                'class': name,
                'label': self.CARD_LABELS.get(name, name),
                'confidence': conf,
                'box': (x1, y1, x2, y2),
            }
        except Exception:
            return {'detected': False}

    def is_available(self) -> bool:
        if self._available is None:
            self._load()
        return self._available or False


# =============================================================================
# EMBEDDING EXTRACTOR (DeepFace - Only when needed)
# =============================================================================

class EmbeddingExtractor:
    """DeepFace embedding extractor - used ONLY for enrollment/verification."""

    _deepface = None

    def __init__(self, model: str = "Facenet512"):
        self.model = model
        if EmbeddingExtractor._deepface is None:
            from deepface import DeepFace
            EmbeddingExtractor._deepface = DeepFace
            logger.info(f"DeepFace loaded for embeddings (model={model})")

    def extract(self, face_img: np.ndarray) -> Optional[np.ndarray]:
        """Extract embedding from face image."""
        if face_img is None or face_img.size == 0 or min(face_img.shape[:2]) < 48:
            return None

        try:
            results = self._deepface.represent(
                img_path=face_img,
                model_name=self.model,
                enforce_detection=False,
                detector_backend="skip",  # CRITICAL: Skip detection, we already have face
            )
            if results:
                return np.array(results[0]['embedding'])
        except Exception as e:
            logger.debug(f"Embedding extraction failed: {e}")
        return None


# =============================================================================
# MAIN DEMO
# =============================================================================

class FastBiometricDemo:
    """Ultra-fast biometric demo targeting 20-30+ FPS."""

    MODES = ["all", "face", "quality", "demographics", "landmarks", "liveness", "puzzle", "enroll", "verify", "card"]

    def __init__(self, camera: int = 0, mode: str = "all", profile: bool = False):
        self.camera = camera
        self.mode = mode
        self.mode_idx = self.MODES.index(mode) if mode in self.MODES else 0

        # State
        self.paused = False
        self.recording = False
        self.video_writer = None
        self.show_help = False

        # Performance
        self.fps = 0.0
        self.frame_times = deque(maxlen=30)
        self.profiler = Profiler()
        self.profiler.enabled = profile

        # Components
        self.detector = FastFaceDetector()
        self.quality = FastQualityAssessor()
        self.liveness = FastLivenessDetector()
        self.tracker = FaceTracker()
        self.face_db = FaceDB()
        self.card_detector = CardDetector()
        self.embedding_extractor = None  # Lazy load

        # MediaPipe for landmarks
        self._mp = None
        self._mp_mesh = None

        # DeepFace for demographics (lazy)
        self._deepface = None

        # Caching - SHORT intervals since detection is fast now!
        self._demo_cache = {}
        self._demo_interval = 2.0  # Demographics still slow, cache longer
        self._last_demo_time = 0

        self._verify_cache = {}
        self._verify_interval = 2.0
        self._last_verify_time = 0

        self._live_cache = {}  # Liveness cache per face

        self._landmarks_cache = []
        self._last_landmarks = 0

        self._card_cache = {'result': None, 'time': 0}

        # Enrollment
        self._enrolling = False
        self._enroll_name = ""
        self._enroll_embeddings = []
        self._enroll_step = 0
        self._enroll_poses = [
            ("STRAIGHT", 0, 0, 12),
            ("LEFT", -25, 0, 15),
            ("RIGHT", 25, 0, 15),
            ("UP", 0, 18, 15),
            ("DOWN", 0, -18, 15),
        ]
        self._hold_start = 0
        self._cur_yaw = 0
        self._cur_pitch = 0

        # Stability tracking for enrollment
        self._face_positions = deque(maxlen=10)  # Track last 10 face positions
        self._stability_threshold = 15  # Max pixels of movement allowed
        self._is_stable = False
        self._stability_score = 0.0

        # Biometric Puzzle - liveness challenge system
        self.puzzle = BiometricPuzzle(num_challenges=3)
        self._enroll_phase = 0  # 0=not enrolling, 1=puzzle phase, 2=capture phase

        # Stats
        self.stats = {'frames': 0, 'faces': 0, 'enrolled': len(self.face_db.faces)}

        # Colors
        self.C = {
            'green': (0, 255, 0), 'red': (0, 0, 255), 'yellow': (0, 255, 255),
            'cyan': (255, 255, 0), 'white': (255, 255, 255), 'black': (0, 0, 0),
            'orange': (0, 165, 255),
        }

    def _load_mediapipe(self):
        """Load MediaPipe for landmarks."""
        if self._mp_mesh is not None:
            return True

        try:
            import mediapipe as mp
            self._mp = mp

            # Try Tasks API first
            if hasattr(mp, 'tasks'):
                try:
                    from mediapipe.tasks import python as tasks
                    from mediapipe.tasks.python import vision

                    model_path = "face_landmarker.task"
                    if not os.path.exists(model_path):
                        import urllib.request
                        logger.info("Downloading face landmarker model...")
                        url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
                        urllib.request.urlretrieve(url, model_path)

                    opts = vision.FaceLandmarkerOptions(
                        base_options=tasks.BaseOptions(model_asset_path=model_path),
                        num_faces=5
                    )
                    self._mp_mesh = vision.FaceLandmarker.create_from_options(opts)
                    self._mp_tasks = True
                    logger.info("MediaPipe Tasks API ready")
                    return True
                except Exception as e:
                    logger.debug(f"Tasks API failed: {e}")

            # Fallback to Solutions API
            if hasattr(mp, 'solutions'):
                self._mp_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False, max_num_faces=5,
                    refine_landmarks=True, min_detection_confidence=0.5
                )
                self._mp_tasks = False
                logger.info("MediaPipe Solutions API ready")
                return True

        except Exception as e:
            logger.warning(f"MediaPipe unavailable: {e}")

        return False

    def _load_deepface(self):
        """Load DeepFace for demographics."""
        if self._deepface is None:
            from deepface import DeepFace
            self._deepface = DeepFace
        return self._deepface

    def detect_landmarks(self, frame: np.ndarray) -> List[List[Tuple[int, int]]]:
        """Detect facial landmarks."""
        now = time.time()
        if now - self._last_landmarks < 0.05:  # 50ms cache - faster landmark updates!
            return self._landmarks_cache

        if not self._load_mediapipe():
            return []

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            if self._mp_tasks:
                mp_img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                results = self._mp_mesh.detect(mp_img)
                if results.face_landmarks:
                    self._landmarks_cache = [
                        [(int(lm.x * w), int(lm.y * h)) for lm in face]
                        for face in results.face_landmarks
                    ]
                else:
                    self._landmarks_cache = []
            else:
                results = self._mp_mesh.process(rgb)
                if results.multi_face_landmarks:
                    self._landmarks_cache = [
                        [(int(lm.x * w), int(lm.y * h)) for lm in face.landmark]
                        for face in results.multi_face_landmarks
                    ]
                else:
                    self._landmarks_cache = []

            self._last_landmarks = now
        except Exception:
            pass

        return self._landmarks_cache

    def estimate_pose(self, landmarks: List[Tuple[int, int]], size: Tuple[int, int]) -> Tuple[float, float]:
        """Estimate head pose (yaw, pitch) from landmarks."""
        if not landmarks or len(landmarks) < 468:
            return 0, 0

        try:
            nose = landmarks[1]
            left_eye = landmarks[33]
            right_eye = landmarks[263]
            left_mouth = landmarks[61]
            right_mouth = landmarks[291]

            eye_cx = (left_eye[0] + right_eye[0]) / 2
            eye_dist = abs(right_eye[0] - left_eye[0])
            yaw = ((nose[0] - eye_cx) / eye_dist * 60) if eye_dist > 0 else 0

            eye_cy = (left_eye[1] + right_eye[1]) / 2
            mouth_cy = (left_mouth[1] + right_mouth[1]) / 2
            face_h = mouth_cy - eye_cy
            mid_y = (eye_cy + mouth_cy) / 2
            pitch = ((nose[1] - mid_y) / face_h * 60) if face_h > 0 else 0

            return max(-45, min(45, yaw)), max(-35, min(35, pitch))
        except Exception:
            return 0, 0

    def analyze_demographics(self, frame: np.ndarray, region: Dict) -> Dict:
        """Analyze demographics with caching."""
        now = time.time()
        key = f"{region['x']//50}_{region['y']//50}"

        if key in self._demo_cache and now - self._demo_cache[key]['t'] < self._demo_interval:
            return self._demo_cache[key]['d']

        if now - self._last_demo_time < 1.5:  # Throttle
            return self._demo_cache.get(key, {}).get('d', {})

        self._last_demo_time = now

        try:
            x, y, w, h = region['x'], region['y'], region['w'], region['h']
            pad = 15
            x, y = max(0, x - pad), max(0, y - pad)
            face = frame[y:y+h+2*pad, x:x+w+2*pad]

            if face.size == 0 or face.shape[0] < 48:
                return {}

            df = self._load_deepface()
            results = df.analyze(face, actions=['age', 'gender', 'emotion'],
                                enforce_detection=False, detector_backend='skip', silent=True)

            if results:
                r = results[0] if isinstance(results, list) else results
                data = {
                    'age': int(r.get('age', 0)),
                    'gender': 'M' if r.get('dominant_gender') == 'Man' else 'F',
                    'emotion': r.get('dominant_emotion', '?')[:6]
                }
                self._demo_cache[key] = {'d': data, 't': now}
                return data
        except Exception:
            pass

        return self._demo_cache.get(key, {}).get('d', {})

    def verify_face(self, frame: np.ndarray, region: Dict, face_id: int) -> Optional[Tuple[str, float]]:
        """Verify face against database."""
        now = time.time()
        key = str(face_id)

        if key in self._verify_cache and now - self._verify_cache[key]['t'] < self._verify_interval:
            return self._verify_cache[key]['m']

        if now - self._last_verify_time < 1.5:
            return self._verify_cache.get(key, {}).get('m')

        self._last_verify_time = now

        # Get face image
        x, y, w, h = region['x'], region['y'], region['w'], region['h']
        pad = 25
        x, y = max(0, x - pad), max(0, y - pad)
        face_img = frame[y:y+h+2*pad, x:x+w+2*pad]

        # Extract embedding
        if self.embedding_extractor is None:
            self.embedding_extractor = EmbeddingExtractor()

        emb = self.embedding_extractor.extract(face_img)
        if emb is None:
            return self._verify_cache.get(key, {}).get('m')

        match = self.face_db.search(emb, threshold=0.45)
        self._verify_cache[key] = {'m': match, 't': now}
        return match

    def detect_card(self, frame: np.ndarray) -> Dict:
        """Detect card with caching."""
        now = time.time()
        if now - self._card_cache['time'] < 0.15:  # Cache for 150ms (~7 FPS for card detection)
            return self._card_cache['result'] or {'detected': False}

        result = self.card_detector.detect(frame)
        self._card_cache = {'result': result, 'time': now}
        return result

    # =========================================================================
    # DRAWING
    # =========================================================================

    def draw_face(self, frame, face, fid, info, color):
        a = face.get('facial_area', {})
        x, y, w, h = a.get('x', 0), a.get('y', 0), a.get('w', 100), a.get('h', 100)

        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

        # Corners
        c = min(w, h) // 4
        for px, py, dx, dy in [(x,y,1,1), (x+w,y,-1,1), (x,y+h,1,-1), (x+w,y+h,-1,-1)]:
            cv2.line(frame, (px, py), (px+c*dx, py), color, 3)
            cv2.line(frame, (px, py), (px, py+c*dy), color, 3)

        # ID badge
        cv2.rectangle(frame, (x, y-22), (x+35, y), color, -1)
        cv2.putText(frame, f"#{fid}", (x+3, y-6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.C['white'], 1)

        # Info panel
        if info:
            lines = [f"{k}:{v}" for k, v in info.items()]
            panel_w = max(len(l) * 8 for l in lines) + 10
            panel_h = len(lines) * 16 + 8

            px = x + w + 5
            if px + panel_w > frame.shape[1]:
                px = max(0, x - panel_w - 5)

            overlay = frame.copy()
            cv2.rectangle(overlay, (px, y), (px+panel_w, y+panel_h), self.C['black'], -1)
            cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

            for i, line in enumerate(lines):
                cv2.putText(frame, line, (px+4, y+14+i*16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.C['white'], 1)

    def draw_landmarks(self, frame, landmarks):
        """Draw facial landmarks with full 468 points like original demo."""
        if not landmarks:
            return

        for points in landmarks:
            # Face contour (jawline + forehead)
            contour_indices = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
                             397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
                             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10]

            # Draw face contour
            for i in range(len(contour_indices) - 1):
                if contour_indices[i] < len(points) and contour_indices[i+1] < len(points):
                    pt1 = points[contour_indices[i]]
                    pt2 = points[contour_indices[i+1]]
                    cv2.line(frame, pt1, pt2, self.C['cyan'], 1)

            # Left eye outline
            left_eye = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246, 33]
            for i in range(len(left_eye) - 1):
                if left_eye[i] < len(points) and left_eye[i+1] < len(points):
                    cv2.line(frame, points[left_eye[i]], points[left_eye[i+1]], self.C['green'], 1)

            # Right eye outline
            right_eye = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466, 263]
            for i in range(len(right_eye) - 1):
                if right_eye[i] < len(points) and right_eye[i+1] < len(points):
                    cv2.line(frame, points[right_eye[i]], points[right_eye[i+1]], self.C['green'], 1)

            # Lips outer
            lips_outer = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185, 61]
            for i in range(len(lips_outer) - 1):
                if lips_outer[i] < len(points) and lips_outer[i+1] < len(points):
                    cv2.line(frame, points[lips_outer[i]], points[lips_outer[i+1]], self.C['red'], 1)

            # Nose
            nose = [168, 6, 197, 195, 5, 4, 1, 19, 94, 2]
            for i in range(len(nose) - 1):
                if nose[i] < len(points) and nose[i+1] < len(points):
                    cv2.line(frame, points[nose[i]], points[nose[i+1]], self.C['yellow'], 1)

            # Left eyebrow
            left_brow = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
            for i in range(len(left_brow) - 1):
                if left_brow[i] < len(points) and left_brow[i+1] < len(points):
                    cv2.line(frame, points[left_brow[i]], points[left_brow[i+1]], self.C['white'], 1)

            # Right eyebrow
            right_brow = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
            for i in range(len(right_brow) - 1):
                if right_brow[i] < len(points) and right_brow[i+1] < len(points):
                    cv2.line(frame, points[right_brow[i]], points[right_brow[i+1]], self.C['white'], 1)

            # Draw key landmark points (bigger circles for important points)
            key_points = [
                # Left eye
                (33, self.C['green']), (133, self.C['green']),
                (160, self.C['green']), (144, self.C['green']),
                # Right eye
                (362, self.C['green']), (263, self.C['green']),
                (387, self.C['green']), (373, self.C['green']),
                # Nose
                (1, self.C['yellow']), (4, self.C['yellow']),
                # Mouth
                (61, self.C['red']), (291, self.C['red']),
                (0, self.C['red']), (17, self.C['red']),
            ]

            for idx, color in key_points:
                if idx < len(points):
                    cv2.circle(frame, points[idx], 3, color, -1)

            # Draw ALL 468 points (small dots)
            for i, (x, y) in enumerate(points):
                cv2.circle(frame, (x, y), 1, (150, 200, 200), -1)

    def draw_card(self, frame, card):
        if not card.get('detected'):
            return

        x1, y1, x2, y2 = card['box']
        cv2.rectangle(frame, (x1, y1), (x2, y2), self.C['cyan'], 3)
        label = f"{card['label']} ({card['confidence']*100:.0f}%)"
        cv2.rectangle(frame, (x1, y1-25), (x1+len(label)*10, y1), self.C['cyan'], -1)
        cv2.putText(frame, label, (x1+3, y1-7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.C['black'], 2)

    def draw_status_bar(self, frame):
        """Draw top status bar like original demo."""
        h, w = frame.shape[:2]

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 40), self.C['black'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Mode
        mode_color = self.C['cyan'] if self.mode not in ['enroll', 'card'] else self.C['orange']
        cv2.putText(frame, f"Mode: {self.mode.upper()}", (10, 28), font, 0.6, mode_color, 2)

        # Recording indicator
        if self.recording:
            cv2.circle(frame, (200, 20), 8, self.C['red'], -1)
            cv2.putText(frame, "REC", (215, 28), font, 0.5, self.C['red'], 2)

        # Paused indicator
        if self.paused:
            cv2.putText(frame, "PAUSED", (280, 28), font, 0.5, self.C['yellow'], 2)

        # FPS with color coding
        fps_color = self.C['green'] if self.fps >= 15 else self.C['yellow'] if self.fps >= 8 else self.C['red']
        cv2.putText(frame, f"FPS: {self.fps:.1f}", (w - 100, 28), font, 0.5, fps_color, 1)

        # Enrolled count
        enrolled = len(self.face_db.faces)
        if enrolled > 0:
            cv2.putText(frame, f"Enrolled: {enrolled}", (w - 220, 28), font, 0.5, self.C['green'], 1)

        # Help hint
        cv2.putText(frame, "'h' help | 'e' enroll | 'p' profiler", (w//2 - 120, 28), font, 0.4, self.C['white'], 1)

    def draw_stats_panel(self, frame):
        """Draw statistics panel at bottom right."""
        h, w = frame.shape[:2]
        stats_lines = [
            f"Frames: {self.stats['frames']}",
            f"Faces: {self.stats['faces']}",
            f"Enrolled: {self.stats['enrolled']}",
        ]

        panel_w, panel_h = 130, len(stats_lines) * 20 + 15
        overlay = frame.copy()
        cv2.rectangle(overlay, (w - panel_w - 10, h - panel_h - 10), (w - 10, h - 10), self.C['black'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        for i, line in enumerate(stats_lines):
            cv2.putText(frame, line, (w - panel_w, h - panel_h + 20 + i*20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.C['white'], 1)

    def draw_enrolled_faces(self, frame):
        """Draw thumbnails of enrolled faces at bottom left."""
        if not self.face_db.faces:
            return

        h, w = frame.shape[:2]
        thumb_size = 50
        margin = 5
        start_x = 10
        start_y = h - thumb_size - 10

        for i, (name, data) in enumerate(list(self.face_db.faces.items())[:5]):
            thumb = data.get('thumbnail')
            if thumb is not None:
                try:
                    thumb_resized = cv2.resize(thumb, (thumb_size, thumb_size))
                    x = start_x + i * (thumb_size + margin)
                    frame[start_y:start_y+thumb_size, x:x+thumb_size] = thumb_resized
                    cv2.rectangle(frame, (x, start_y), (x+thumb_size, start_y+thumb_size), self.C['green'], 1)
                    cv2.putText(frame, name[:6], (x, start_y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.C['white'], 1)
                except Exception:
                    pass

    def draw_help(self, frame):
        if not self.show_help:
            return

        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (40, 40), (w-40, h-40), self.C['black'], -1)
        cv2.addWeighted(overlay, 0.92, frame, 0.08, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, "FAST BIOMETRIC DEMO", (60, 80), font, 0.8, self.C['cyan'], 2)

        lines = [
            "", "CONTROLS:", "  q - Quit", "  m - Cycle modes", "  e - Enroll face",
            "  l - Liveness puzzle", "  d - Delete all enrolled", "  c - Card detection",
            "  r - Toggle recording", "  p - Toggle profiler", "  h - This help", "  Space - Pause",
            "", "OPTIMIZATIONS:",
            "  - Direct OpenCV Haar (~20ms vs 400ms)",
            "  - MediaPipe reuse for landmarks",
            "  - DeepFace only for embeddings",
            "  - Short cache intervals",
            "", f"MODES: {' | '.join(self.MODES)}"
        ]

        y = 110
        for line in lines:
            color = self.C['yellow'] if line.endswith(':') else self.C['white']
            cv2.putText(frame, line, (60, y), font, 0.4, color, 1)
            y += 20

    def _draw_head_placeholder(self, frame, target_yaw, target_pitch):
        """Draw a head silhouette placeholder showing expected pose."""
        h, w = frame.shape[:2]

        # Head placeholder position (center of frame)
        cx, cy = w // 2, h // 2 + 40
        head_w, head_h = 180, 220

        # Calculate offset based on target pose
        offset_x = int(target_yaw * 2)  # Horizontal shift for yaw
        offset_y = int(target_pitch * 2)  # Vertical shift for pitch (FIXED: removed negation)

        # Draw head oval outline
        head_color = (100, 100, 100)  # Gray for placeholder

        # Draw the head silhouette (ellipse)
        cv2.ellipse(frame, (cx + offset_x, cy + offset_y), (head_w // 2, head_h // 2),
                   0, 0, 360, head_color, 2)

        # Draw face guidelines
        # Vertical center line (nose)
        nose_offset = int(target_yaw * 1.5)
        cv2.line(frame, (cx + nose_offset, cy - 60 + offset_y),
                (cx + nose_offset, cy + 40 + offset_y), head_color, 1)

        # Eyes line
        eye_y = cy - 30 + offset_y
        cv2.line(frame, (cx - 50 + offset_x, eye_y), (cx + 50 + offset_x, eye_y), head_color, 1)

        # Draw direction arrow
        arrow_len = 50
        if abs(target_yaw) > 5:  # Horizontal arrow for left/right
            arrow_x = cx + (arrow_len if target_yaw > 0 else -arrow_len)
            cv2.arrowedLine(frame, (cx, cy - 100), (arrow_x, cy - 100),
                           self.C['cyan'], 3, tipLength=0.3)

        if abs(target_pitch) > 5:  # Vertical arrow for up/down (FIXED: reversed direction)
            # Positive pitch = tilt head UP (look up) = arrow points UP on screen
            # Negative pitch = tilt head DOWN (look down) = arrow points DOWN on screen
            arrow_y = cy - 100 + (arrow_len if target_pitch > 0 else -arrow_len)
            cv2.arrowedLine(frame, (cx, cy - 100), (cx, arrow_y),
                           self.C['cyan'], 3, tipLength=0.3)

        # Draw position text
        if target_yaw < -5:
            cv2.putText(frame, "LEFT", (cx - 100, cy - 120), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, self.C['cyan'], 2)
        elif target_yaw > 5:
            cv2.putText(frame, "RIGHT", (cx + 40, cy - 120), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, self.C['cyan'], 2)

        # FIXED: Reversed UP/DOWN labels to match actual pose direction
        if target_pitch > 5:
            cv2.putText(frame, "DOWN", (cx - 35, cy + 130), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, self.C['cyan'], 2)
        elif target_pitch < -5:
            cv2.putText(frame, "UP", (cx - 20, cy - 140), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, self.C['cyan'], 2)

    def draw_puzzle(self, frame, challenge_result: Dict = None):
        """Draw biometric puzzle UI."""
        h, w = frame.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Show completion screen if puzzle just finished
        if self.puzzle.is_complete and self.mode == "puzzle":
            overlay = frame.copy()
            cv2.rectangle(overlay, (w//4, h//3), (3*w//4, 2*h//3), self.C['black'], -1)
            cv2.addWeighted(overlay, 0.9, frame, 0.1, 0, frame)

            if self.puzzle.passed:
                cv2.putText(frame, "PUZZLE PASSED!", (w//4 + 50, h//2 - 20),
                           font, 1.0, self.C['green'], 2)
            else:
                cv2.putText(frame, "PUZZLE ENDED", (w//4 + 70, h//2 - 20),
                           font, 1.0, self.C['yellow'], 2)

            cv2.putText(frame, "Press L to try again", (w//4 + 60, h//2 + 30),
                       font, 0.6, self.C['cyan'], 1)
            return

        if not self.puzzle.is_active:
            return

        challenge = self.puzzle.get_current_challenge()

        if not challenge:
            return

        # Draw overlay panel at top
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 200), self.C['black'], -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Title
        title = "BIOMETRIC PUZZLE" if self.mode == "puzzle" else "LIVENESS CHECK"
        cv2.putText(frame, title, (20, 35), font, 0.8, self.C['cyan'], 2)

        # Challenge counter
        cv2.putText(frame, f"Challenge {challenge['index']+1}/{challenge['total']}",
                   (w - 180, 35), font, 0.6, self.C['white'], 1)

        # Progress bar (overall)
        overall_progress = challenge['index'] / challenge['total']
        cv2.rectangle(frame, (20, 50), (w-20, 70), self.C['white'], 2)
        cv2.rectangle(frame, (22, 52), (22 + int((w-44) * overall_progress), 68),
                     self.C['green'], -1)

        # Current challenge display
        cv2.putText(frame, challenge['name'], (20, 110), font, 1.0, self.C['yellow'], 2)

        # Challenge result/feedback
        if challenge_result:
            progress = challenge_result.get('progress', 0)
            detected = challenge_result.get('detected', False)
            message = challenge_result.get('message', '')

            # Detection status
            status_color = self.C['green'] if detected else self.C['orange']
            cv2.putText(frame, message, (20, 145), font, 0.5, status_color, 1)

            # Hold progress bar
            if detected and progress > 0:
                cv2.putText(frame, f"HOLD! {progress:.0f}%", (20, 175), font, 0.6, self.C['green'], 2)
                cv2.rectangle(frame, (150, 160), (350, 180), self.C['white'], 2)
                cv2.rectangle(frame, (152, 162), (152 + int(196 * progress/100), 178),
                             self.C['green'], -1)
        else:
            # No face detected - show waiting message
            cv2.putText(frame, "Looking for face... Position yourself in frame",
                       (20, 145), font, 0.5, self.C['red'], 1)

        # Visual guide for current challenge
        self._draw_puzzle_guide(frame, challenge['key'])

        # ESC to cancel
        cv2.putText(frame, "ESC to cancel", (20, 195), font, 0.4, self.C['red'], 1)

    def _draw_puzzle_guide(self, frame, challenge_key: str):
        """Draw visual guide for the current challenge."""
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2 + 50

        # Draw guide based on challenge type
        guide_color = self.C['cyan']

        if challenge_key == 'BLINK':
            # Draw eye icons
            cv2.ellipse(frame, (cx - 50, cy), (30, 15), 0, 0, 360, guide_color, 2)
            cv2.ellipse(frame, (cx + 50, cy), (30, 15), 0, 0, 360, guide_color, 2)
            cv2.putText(frame, "CLOSE", (cx - 35, cy + 50), cv2.FONT_HERSHEY_SIMPLEX,
                       0.6, guide_color, 2)

        elif challenge_key == 'BLINK_LEFT':
            cv2.ellipse(frame, (cx - 50, cy), (30, 15), 0, 0, 360, guide_color, 2)
            cv2.line(frame, (cx - 80, cy), (cx - 20, cy), guide_color, 2)  # Closed left
            cv2.ellipse(frame, (cx + 50, cy), (30, 15), 0, 0, 360, (100, 100, 100), 2)

        elif challenge_key == 'BLINK_RIGHT':
            cv2.ellipse(frame, (cx - 50, cy), (30, 15), 0, 0, 360, (100, 100, 100), 2)
            cv2.ellipse(frame, (cx + 50, cy), (30, 15), 0, 0, 360, guide_color, 2)
            cv2.line(frame, (cx + 20, cy), (cx + 80, cy), guide_color, 2)  # Closed right

        elif challenge_key == 'SMILE':
            # Draw smile arc
            cv2.ellipse(frame, (cx, cy + 20), (60, 30), 0, 0, 180, guide_color, 3)

        elif challenge_key == 'OPEN_MOUTH':
            # Draw open mouth
            cv2.ellipse(frame, (cx, cy + 20), (40, 50), 0, 0, 360, guide_color, 3)

        elif challenge_key in ['TURN_LEFT', 'TURN_RIGHT']:
            # Draw arrow
            direction = -1 if challenge_key == 'TURN_LEFT' else 1
            cv2.arrowedLine(frame, (cx, cy), (cx + direction * 80, cy),
                           guide_color, 4, tipLength=0.3)

        elif challenge_key == 'LOOK_UP':
            # Chin UP = look at ceiling
            cv2.ellipse(frame, (cx, cy), (50, 60), -20, 0, 360, guide_color, 2)
            cv2.arrowedLine(frame, (cx, cy - 70), (cx - 30, cy - 110), guide_color, 3, tipLength=0.3)
            cv2.putText(frame, "CHIN UP", (cx - 45, cy + 90), cv2.FONT_HERSHEY_SIMPLEX,
                       0.6, guide_color, 2)

        elif challenge_key == 'LOOK_DOWN':
            # Chin DOWN = look at floor
            cv2.ellipse(frame, (cx, cy), (50, 60), 20, 0, 360, guide_color, 2)
            cv2.arrowedLine(frame, (cx, cy + 70), (cx + 30, cy + 110), guide_color, 3, tipLength=0.3)
            cv2.putText(frame, "CHIN DOWN", (cx - 60, cy - 80), cv2.FONT_HERSHEY_SIMPLEX,
                       0.6, guide_color, 2)

        elif challenge_key == 'RAISE_BOTH_BROWS':
            # Draw both eyebrows raised
            cv2.ellipse(frame, (cx - 40, cy - 30), (30, 10), -10, 0, 180, guide_color, 3)
            cv2.ellipse(frame, (cx + 40, cy - 30), (30, 10), 10, 0, 180, guide_color, 3)
            cv2.arrowedLine(frame, (cx - 40, cy - 35), (cx - 40, cy - 70), guide_color, 2, tipLength=0.3)
            cv2.arrowedLine(frame, (cx + 40, cy - 35), (cx + 40, cy - 70), guide_color, 2, tipLength=0.3)
            cv2.putText(frame, "BOTH UP", (cx - 45, cy + 50), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, guide_color, 2)

        elif challenge_key == 'RAISE_LEFT_BROW':
            # User's left eyebrow (appears on left of mirrored screen)
            cv2.ellipse(frame, (cx - 40, cy - 40), (30, 10), -10, 0, 180, guide_color, 3)  # Left up
            cv2.ellipse(frame, (cx + 40, cy - 20), (30, 10), 10, 0, 180, (100, 100, 100), 2)  # Right normal
            cv2.arrowedLine(frame, (cx - 40, cy - 45), (cx - 40, cy - 75), guide_color, 2, tipLength=0.3)
            cv2.putText(frame, "YOUR LEFT", (cx - 60, cy + 50), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, guide_color, 2)

        elif challenge_key == 'RAISE_RIGHT_BROW':
            # User's right eyebrow (appears on right of mirrored screen)
            cv2.ellipse(frame, (cx - 40, cy - 20), (30, 10), -10, 0, 180, (100, 100, 100), 2)  # Left normal
            cv2.ellipse(frame, (cx + 40, cy - 40), (30, 10), 10, 0, 180, guide_color, 3)  # Right up
            cv2.arrowedLine(frame, (cx + 40, cy - 45), (cx + 40, cy - 75), guide_color, 2, tipLength=0.3)
            cv2.putText(frame, "YOUR RIGHT", (cx - 60, cy + 50), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, guide_color, 2)

        elif challenge_key == 'CLOSE_LEFT':
            # User's left eye closed (appears on LEFT of mirrored screen)
            cv2.line(frame, (cx - 80, cy), (cx - 20, cy), guide_color, 3)  # Left closed
            cv2.ellipse(frame, (cx + 50, cy), (30, 15), 0, 0, 360, (100, 100, 100), 2)  # Right open
            cv2.putText(frame, "YOUR LEFT", (cx - 60, cy + 50), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, guide_color, 2)

        elif challenge_key == 'CLOSE_RIGHT':
            # User's right eye closed (appears on RIGHT of mirrored screen)
            cv2.ellipse(frame, (cx - 50, cy), (30, 15), 0, 0, 360, (100, 100, 100), 2)  # Left open
            cv2.line(frame, (cx + 20, cy), (cx + 80, cy), guide_color, 3)  # Right closed
            cv2.putText(frame, "YOUR RIGHT", (cx - 60, cy + 50), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, guide_color, 2)

    def draw_enrollment(self, frame):
        if not self._enrolling:
            return

        # Phase 1 (puzzle) is handled by draw_puzzle
        if self._enroll_phase == 1:
            return

        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 180), self.C['black'], -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Show phase 2 indicator
        cv2.putText(frame, f"ENROLLING: {self._enroll_name}", (20, 30), font, 0.7, self.C['green'], 2)
        cv2.putText(frame, "Phase 2: Face Capture", (w - 200, 30), font, 0.4, self.C['cyan'], 1)

        # Progress bar
        progress = self._enroll_step / 5
        cv2.rectangle(frame, (20, 45), (w-20, 65), self.C['white'], 2)
        cv2.rectangle(frame, (22, 47), (22 + int((w-44) * progress), 63), self.C['green'], -1)
        cv2.putText(frame, f"{self._enroll_step}/5", (w-70, 60), font, 0.45, self.C['white'], 1)

        if self._enroll_step < 5:
            pose_name, target_yaw, target_pitch, tol = self._enroll_poses[self._enroll_step]
            cv2.putText(frame, f"Look {pose_name}", (20, 95), font, 0.7, self.C['yellow'], 2)

            yaw_ok = abs(self._cur_yaw - target_yaw) < tol
            pitch_ok = abs(self._cur_pitch - target_pitch) < tol

            # Draw head placeholder visual
            self._draw_head_placeholder(frame, target_yaw, target_pitch)

            # Stability indicator
            stability_color = self.C['green'] if self._is_stable else self.C['red']
            cv2.putText(frame, f"Stability: {self._stability_score:.0f}%", (220, 95),
                       font, 0.5, stability_color, 1)

            # Stability bar
            cv2.rectangle(frame, (220, 100), (350, 115), self.C['white'], 1)
            bar_width = int(130 * self._stability_score / 100)
            cv2.rectangle(frame, (221, 101), (221 + bar_width, 114), stability_color, -1)

            if yaw_ok and pitch_ok and self._is_stable:
                hold = time.time() - self._hold_start
                pct = min(100, hold / 0.8 * 100)
                cv2.putText(frame, f"HOLD STILL! {pct:.0f}%", (20, 125), font, 0.6, self.C['green'], 2)
                cv2.rectangle(frame, (20, 140), (200, 160), self.C['white'], 2)
                cv2.rectangle(frame, (22, 142), (22 + int(176 * pct/100), 158), self.C['green'], -1)
            elif yaw_ok and pitch_ok and not self._is_stable:
                # Correct pose but moving
                cv2.putText(frame, "STOP MOVING!", (20, 125), font, 0.6, self.C['orange'], 2)
                cv2.putText(frame, "Keep your head still", (20, 150), font, 0.4, self.C['yellow'], 1)
            else:
                hints = []
                if self._cur_yaw < target_yaw - tol: hints.append("Turn RIGHT")
                elif self._cur_yaw > target_yaw + tol: hints.append("Turn LEFT")
                if self._cur_pitch < target_pitch - tol: hints.append("Tilt DOWN")
                elif self._cur_pitch > target_pitch + tol: hints.append("Tilt UP")
                cv2.putText(frame, " & ".join(hints) if hints else "Adjust", (20, 125), font, 0.5, self.C['orange'], 1)

            # Pose indicator (mini radar)
            ix, iy, ir = w-120, 110, 40
            cv2.circle(frame, (ix, iy), ir, self.C['white'], 2)
            dx = int(ix + (self._cur_yaw / 45) * ir)
            dy = int(iy + (self._cur_pitch / 35) * ir)
            color = self.C['green'] if (yaw_ok and pitch_ok and self._is_stable) else self.C['red']
            cv2.circle(frame, (dx, dy), 6, color, -1)
            tx = int(ix + (target_yaw / 45) * ir)
            ty = int(iy + (target_pitch / 35) * ir)
            cv2.drawMarker(frame, (tx, ty), self.C['cyan'], cv2.MARKER_CROSS, 15, 2)
        else:
            cv2.putText(frame, "COMPLETE!", (20, 110), font, 0.8, self.C['green'], 2)

        cv2.putText(frame, "ESC to cancel", (20, 170), font, 0.4, self.C['red'], 1)

    # =========================================================================
    # ENROLLMENT
    # =========================================================================

    def start_enrollment(self):
        self._enroll_name = f"Person_{len(self.face_db.faces) + 1}"
        self._enroll_embeddings = []
        self._enroll_step = 0
        self._hold_start = time.time()
        self._enrolling = True

        # Phase 1: Start with biometric puzzle (liveness check)
        self._enroll_phase = 1  # 1 = puzzle phase
        self.puzzle.start()  # Start random puzzle challenges

        # IMPORTANT: Switch to enroll mode so face detection runs
        self.mode = "enroll"
        self.mode_idx = self.MODES.index("enroll")

        logger.info(f"Enrollment started: {self._enroll_name} (Phase 1: Liveness Puzzle)")

    def start_puzzle_mode(self):
        """Start or restart standalone puzzle mode for liveness testing.

        Press L anytime to start a new puzzle. If already in puzzle mode,
        this restarts with new random challenges.
        """
        self.puzzle.start()  # This logs the challenges
        self.mode = "puzzle"
        self.mode_idx = self.MODES.index("puzzle")

    def cancel_enrollment(self):
        self._enrolling = False
        self._enroll_embeddings = []
        self._enroll_step = 0
        self._enroll_phase = 0
        self.puzzle.stop()
        logger.info("Enrollment cancelled")

    def _check_stability(self, faces) -> bool:
        """Check if face position is stable (not moving too much)."""
        if not faces:
            self._face_positions.clear()
            self._is_stable = False
            self._stability_score = 0.0
            return False

        # Get current face center
        largest = max(faces, key=lambda f: f.get('facial_area', {}).get('w', 0) * f.get('facial_area', {}).get('h', 0))
        a = largest.get('facial_area', {})
        cx = a.get('x', 0) + a.get('w', 0) // 2
        cy = a.get('y', 0) + a.get('h', 0) // 2

        self._face_positions.append((cx, cy))

        if len(self._face_positions) < 5:
            self._is_stable = False
            self._stability_score = 0.0
            return False

        # Calculate movement variance
        positions = list(self._face_positions)
        x_coords = [p[0] for p in positions]
        y_coords = [p[1] for p in positions]

        x_range = max(x_coords) - min(x_coords)
        y_range = max(y_coords) - min(y_coords)
        movement = max(x_range, y_range)

        # Calculate stability score (0-100)
        self._stability_score = max(0, min(100, 100 - (movement / self._stability_threshold) * 100))
        self._is_stable = movement < self._stability_threshold

        return self._is_stable

    def process_enrollment(self, frame, faces):
        if not self._enrolling or not faces:
            self._face_positions.clear()
            return

        if self._enroll_step >= 5:
            self._finalize_enrollment(frame, faces)
            return

        landmarks = self.detect_landmarks(frame)
        if landmarks:
            self._cur_yaw, self._cur_pitch = self.estimate_pose(landmarks[0], frame.shape[:2])
        else:
            return

        pose_name, target_yaw, target_pitch, tol = self._enroll_poses[self._enroll_step]
        yaw_ok = abs(self._cur_yaw - target_yaw) < tol
        pitch_ok = abs(self._cur_pitch - target_pitch) < tol

        # Check stability
        is_stable = self._check_stability(faces)

        if not (yaw_ok and pitch_ok):
            self._hold_start = time.time()
            return

        # Must be stable AND in correct pose
        if not is_stable:
            self._hold_start = time.time()
            return

        if time.time() - self._hold_start < 0.8:
            return

        # Capture!
        largest = max(faces, key=lambda f: f.get('facial_area', {}).get('w', 0) * f.get('facial_area', {}).get('h', 0))
        a = largest.get('facial_area', {})
        x, y, w, h = a.get('x', 0), a.get('y', 0), a.get('w', 100), a.get('h', 100)
        face_img = frame[max(0, y-20):y+h+20, max(0, x-20):x+w+20]

        # Quality check
        q = self.quality.assess(face_img)
        if q['score'] < 65:
            self._hold_start = time.time()
            return

        # Extract embedding
        if self.embedding_extractor is None:
            self.embedding_extractor = EmbeddingExtractor()

        emb = self.embedding_extractor.extract(face_img)
        if emb is not None:
            self._enroll_embeddings.append(emb)
            self._enroll_step += 1
            self._hold_start = time.time()
            self._face_positions.clear()  # Reset stability tracking for next pose
            logger.info(f"Captured angle {self._enroll_step}/5: {pose_name}")

    def _finalize_enrollment(self, frame, faces):
        if not self._enroll_embeddings:
            self._enrolling = False
            return

        # Get thumbnail
        if faces:
            a = max(faces, key=lambda f: f.get('facial_area', {}).get('w', 0) * f.get('facial_area', {}).get('h', 0)).get('facial_area', {})
            thumb = frame[max(0, a.get('y', 0)):a.get('y', 0)+a.get('h', 100),
                         max(0, a.get('x', 0)):a.get('x', 0)+a.get('w', 100)].copy()
        else:
            thumb = np.zeros((80, 80, 3), dtype=np.uint8)

        # Save first embedding
        self.face_db.enroll(self._enroll_name, self._enroll_embeddings[0], thumb)

        # Add rest
        for emb in self._enroll_embeddings[1:]:
            self.face_db.add_embedding(self._enroll_name, emb)

        self.stats['enrolled'] = len(self.face_db.faces)
        logger.info(f"Enrolled {self._enroll_name} with {len(self._enroll_embeddings)} angles")

        self._enrolling = False
        self._enroll_embeddings = []
        self._enroll_step = 0

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        frame_start = time.perf_counter()
        self.stats['frames'] += 1
        frame_num = self.stats['frames']

        # Card mode (skip if enrolling - need face detection)
        if self.mode == "card" and not self._enrolling:
            with self.profiler.time("card"):
                card = self.detect_card(frame)
            self.draw_card(frame, card)
            self.draw_status_bar(frame)
            self.draw_stats_panel(frame)
            self.draw_enrolled_faces(frame)  # Show enrolled faces in card mode too
            self.profiler.draw(frame)
            return frame

        # Face detection (FAST! - runs every frame)
        with self.profiler.time("detect"):
            detections = self.detector.detect(frame)

        tracked = self.tracker.update(detections)
        self.stats['faces'] += len(tracked)

        # Process puzzle challenges (standalone mode or enrollment phase 1)
        puzzle_result = None
        if self.puzzle.is_active:
            landmarks = self.detect_landmarks(frame)
            if landmarks and len(landmarks) > 0:
                yaw, pitch = self.estimate_pose(landmarks[0], frame.shape[:2])
                puzzle_result = self.puzzle.check_challenge(landmarks[0], yaw, pitch)

                # Check if puzzle completed
                if self.puzzle.is_complete:
                    if self._enrolling and self._enroll_phase == 1:
                        # Transition to phase 2 (face capture)
                        if self.puzzle.passed:
                            self._enroll_phase = 2
                            self._hold_start = time.time()
                            logger.info(f"Liveness verified! Moving to Phase 2: Face Capture")
                        else:
                            # Puzzle failed - cancel enrollment
                            self.cancel_enrollment()
                            logger.warning("Liveness check failed - enrollment cancelled")
                    elif self.mode == "puzzle":
                        # Standalone puzzle complete
                        if self.puzzle.passed:
                            logger.info("Standalone puzzle PASSED!")
                        else:
                            logger.info("Standalone puzzle ended")

        # Process enrollment (only phase 2)
        if self._enrolling and self._enroll_phase == 2:
            self.process_enrollment(frame, list(tracked.values()))

        # Process each face
        for fid, face in tracked.items():
            a = face.get('facial_area', {})
            region = {'x': a.get('x', 0), 'y': a.get('y', 0), 'w': a.get('w', 100), 'h': a.get('h', 100)}
            face_img = frame[max(0, region['y']):region['y']+region['h'],
                            max(0, region['x']):region['x']+region['w']]

            info = {}
            color = self.C['green']
            cache_key = str(fid)

            # Quality (every frame - very fast ~2ms)
            if self.mode in ["all", "quality", "enroll"]:
                with self.profiler.time("quality"):
                    q = self.quality.assess(face_img)
                info['Quality'] = f"{q['score']:.0f}%"
                if q['score'] < 50:
                    color = self.C['red']
                elif q['score'] < 70:
                    color = self.C['yellow']

            # Demographics (EXPENSIVE - only every N frames via cache)
            if self.mode in ["all", "demographics"]:
                with self.profiler.time("demo"):
                    demo = self.analyze_demographics(frame, region)
                if demo:
                    info['Age'] = demo.get('age', '?')
                    info['Gender'] = demo.get('gender', '?')
                    info['Mood'] = demo.get('emotion', '?')

            # Liveness (moderate - cached)
            if self.mode in ["all", "liveness"]:
                # Cache liveness per face
                now = time.time()
                if cache_key not in self._live_cache or now - self._live_cache[cache_key]['t'] > 1.0:
                    with self.profiler.time("live"):
                        live = self.liveness.check(face_img)
                    self._live_cache[cache_key] = {'d': live, 't': now}
                else:
                    live = self._live_cache[cache_key]['d']

                info['Live'] = f"{'Y' if live['is_live'] else 'N'} ({live['score']:.0f}%)"
                if not live['is_live']:
                    color = self.C['red']

            # Verification (EXPENSIVE - only every N frames via cache)
            if self.mode in ["all", "verify", "enroll"] and self.face_db.faces:
                with self.profiler.time("verify"):
                    match = self.verify_face(frame, region, fid)
                if match:
                    info['Match'] = f"{match[0]} ({match[1]*100:.0f}%)"
                    color = self.C['cyan']
                else:
                    info['Match'] = "---"

            self.draw_face(frame, face, fid, info, color)

        # Landmarks (every 3rd frame when in landmarks mode for smoothness)
        if self.mode in ["all", "landmarks"]:
            with self.profiler.time("landmarks"):
                landmarks = self.detect_landmarks(frame)
            self.draw_landmarks(frame, landmarks)

            # Show count
            if landmarks:
                total_pts = sum(len(pts) for pts in landmarks)
                cv2.putText(frame, f"Landmarks: {total_pts} pts ({len(landmarks)} faces)",
                           (10, frame.shape[0] - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.C['cyan'], 1)

        # UI elements
        self.draw_status_bar(frame)
        self.draw_stats_panel(frame)
        self.draw_enrolled_faces(frame)
        self.draw_help(frame)
        self.draw_enrollment(frame)
        self.draw_puzzle(frame, puzzle_result)
        self.profiler.draw(frame)

        # Recording
        if self.recording and self.video_writer:
            self.video_writer.write(frame)

        # FPS calculation
        self.frame_times.append(time.perf_counter() - frame_start)
        if len(self.frame_times) >= 10:
            avg = sum(self.frame_times) / len(self.frame_times)
            self.fps = 1.0 / avg if avg > 0 else 0

        return frame

    def run(self):
        print("\n" + "=" * 60)
        print("FAST BIOMETRIC DEMO - Target: 20-30+ FPS")
        print("=" * 60)

        # Initialize
        logger.info("Loading fast face detector (Haar Cascade)...")
        _ = self.detector  # Ensure loaded

        logger.info("Loading MediaPipe...")
        self._load_mediapipe()

        if self.card_detector.is_available():
            logger.info("Card detection available")
        else:
            logger.info("Card detection unavailable (model not found)")

        print("=" * 60)
        print("READY! Press 'h' for help, 'p' for profiler")
        print("=" * 60 + "\n")

        cap = cv2.VideoCapture(self.camera)
        if not cap.isOpened():
            print(f"ERROR: Cannot open camera {self.camera}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Camera: {w}x{h}")

        cv2.namedWindow("Fast Biometric Demo", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Fast Biometric Demo", 1280, 720)

        try:
            while True:
                if not self.paused:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    frame = cv2.flip(frame, 1)
                    frame = self.process_frame(frame)

                cv2.imshow("Fast Biometric Demo", frame)

                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break
                elif key == 27:  # ESC
                    if self._enrolling:
                        self.cancel_enrollment()
                    elif self.puzzle.is_active and self.mode == "puzzle":
                        # Cancel standalone puzzle mode
                        self.puzzle.stop()
                        self.mode = "all"
                        self.mode_idx = 0
                        logger.info("Puzzle mode cancelled")
                elif key == ord('m'):
                    if not self._enrolling:
                        self.mode_idx = (self.mode_idx + 1) % len(self.MODES)
                        self.mode = self.MODES[self.mode_idx]
                        logger.info(f"Mode: {self.mode}")
                elif key == ord('e'):
                    if not self._enrolling:
                        self.start_enrollment()
                elif key == ord('c'):
                    self.mode = "card" if self.mode != "card" else "all"
                    logger.info(f"Mode: {self.mode}")
                elif key == ord('r'):
                    if self.recording:
                        self.video_writer.release()
                        self.video_writer = None
                        self.recording = False
                        logger.info("Recording stopped")
                    else:
                        fname = f"rec_{datetime.now().strftime('%H%M%S')}.mp4"
                        self.video_writer = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*'mp4v'), 20, (w, h))
                        self.recording = True
                        logger.info(f"Recording: {fname}")
                elif key == ord('p'):
                    self.profiler.enabled = not self.profiler.enabled
                    logger.info(f"Profiler: {'ON' if self.profiler.enabled else 'OFF'}")
                elif key == ord('h'):
                    self.show_help = not self.show_help
                elif key == ord(' '):
                    self.paused = not self.paused
                    logger.info("Paused" if self.paused else "Resumed")
                elif key == ord('d'):
                    if self.face_db.faces:
                        n = len(self.face_db.faces)
                        self.face_db.faces.clear()
                        self.face_db.save()
                        self._verify_cache.clear()
                        self.stats['enrolled'] = 0
                        logger.info(f"Deleted {n} enrolled faces")
                elif key == ord('s'):
                    fname = f"snap_{datetime.now().strftime('%H%M%S')}.jpg"
                    cv2.imwrite(fname, frame)
                    logger.info(f"Screenshot: {fname}")
                elif key == ord('l'):
                    if not self._enrolling:
                        # L always (re)starts puzzle mode
                        self.start_puzzle_mode()

        except KeyboardInterrupt:
            pass
        finally:
            if self.recording and self.video_writer:
                self.video_writer.release()
            cap.release()
            cv2.destroyAllWindows()

            print("\n" + "=" * 60)
            print("PERFORMANCE SUMMARY")
            print("=" * 60)
            for name, vals in sorted(self.profiler.metrics.items()):
                if vals:
                    avg = sum(vals) / len(vals)
                    print(f"  {name}: {avg:.1f}ms")
            print(f"\nStats: {self.stats}")
            print(f"Average FPS: {self.fps:.1f}")
            print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Fast Biometric Demo")
    parser.add_argument('--camera', '-c', type=int, default=0)
    parser.add_argument('--mode', '-m', type=str, default='all', choices=FastBiometricDemo.MODES)
    parser.add_argument('--profile', '-p', action='store_true')
    args = parser.parse_args()

    FastBiometricDemo(camera=args.camera, mode=args.mode, profile=args.profile).run()


if __name__ == "__main__":
    main()
