#!/usr/bin/env python3
"""
Biometric Demo - Full Feature Local Demo
==========================================
Complete biometric analysis with all features, no server required.

Features:
    - Face Detection (multi-face)
    - Quality Assessment (blur, brightness, size)
    - Demographics (age, gender, emotion)
    - 468 Facial Landmarks
    - Liveness Detection (texture + eye analysis)
    - Face Enrollment & Verification
    - Face Comparison (similarity between faces)
    - Recording Mode (save annotated video)
    - Export Analysis (JSON reports)

Usage:
    python demo_local.py                    # All features
    python demo_local.py --mode face        # Face detection only
    python demo_local.py --mode enroll      # Enrollment mode

Controls:
    q - Quit
    m - Cycle modes
    e - Enroll current face
    d - Delete all enrolled faces
    c - Compare faces in frame
    r - Toggle recording
    x - Export analysis to JSON
    s - Screenshot
    f - Toggle FPS
    h - Help overlay
    Space - Pause/Resume
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from collections import deque
import pickle

# Suppress warnings BEFORE imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import cv2
import numpy as np


# =============================================================================
# SIMPLE ML COMPONENTS (No async, pure OpenCV/NumPy)
# =============================================================================

class SimpleQualityAssessor:
    """Quality assessment using OpenCV."""

    def __init__(self, blur_threshold: float = 100.0, min_face_size: int = 80):
        self.blur_threshold = blur_threshold
        self.min_face_size = min_face_size

    def assess(self, face_image: np.ndarray) -> Dict[str, Any]:
        if face_image is None or face_image.size == 0:
            return {'score': 0, 'issues': ['No image']}

        h, w = face_image.shape[:2]
        issues, scores = [], []

        # Size check
        size_score = min(100, (min(h, w) / self.min_face_size) * 50)
        scores.append(size_score)
        if min(h, w) < self.min_face_size:
            issues.append('Small')

        # Blur detection
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY) if len(face_image.shape) == 3 else face_image
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_score = min(100, (laplacian_var / self.blur_threshold) * 100)
        scores.append(blur_score)
        if laplacian_var < self.blur_threshold:
            issues.append('Blurry')

        # Brightness
        mean_brightness = np.mean(gray)
        if mean_brightness < 50:
            issues.append('Dark')
            scores.append(50)
        elif mean_brightness > 200:
            issues.append('Bright')
            scores.append(50)
        else:
            scores.append(100)

        # Contrast
        contrast = gray.std()
        if contrast < 30:
            issues.append('Low contrast')
            scores.append(60)
        else:
            scores.append(100)

        return {
            'score': sum(scores) / len(scores),
            'blur': blur_score,
            'size': size_score,
            'brightness': mean_brightness,
            'contrast': contrast,
            'issues': issues
        }


class SimpleLivenessDetector:
    """Liveness detection using texture analysis."""

    def __init__(self):
        opencv_data_dir = os.path.join(cv2.__path__[0], "data")
        self._eye_cascade = cv2.CascadeClassifier(
            os.path.join(opencv_data_dir, "haarcascade_eye.xml")
        )

    def check(self, face_image: np.ndarray) -> Dict[str, Any]:
        if face_image is None or face_image.size == 0:
            return {'is_live': False, 'score': 0}

        try:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY) if len(face_image.shape) == 3 else face_image

            # Texture analysis (Laplacian variance)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            texture_score = min(100, laplacian.var() / 2)

            # Eye detection
            eyes = self._eye_cascade.detectMultiScale(gray, 1.1, 3)
            eye_score = 100 if len(eyes) >= 2 else 50 if len(eyes) == 1 else 20

            # Color histogram analysis (real faces have more color variation)
            if len(face_image.shape) == 3:
                hsv = cv2.cvtColor(face_image, cv2.COLOR_BGR2HSV)
                h_std = hsv[:, :, 0].std()
                s_std = hsv[:, :, 1].std()
                color_score = min(100, (h_std + s_std) * 2)
            else:
                color_score = 50

            # Combined score
            liveness_score = texture_score * 0.4 + eye_score * 0.4 + color_score * 0.2
            is_live = liveness_score >= 45

            return {
                'is_live': is_live,
                'score': liveness_score,
                'texture': texture_score,
                'eyes': eye_score,
                'color': color_score,
                'eye_count': len(eyes)
            }
        except Exception:
            return {'is_live': False, 'score': 0}


class FaceDatabase:
    """Simple local face database for enrollment/verification."""

    def __init__(self, db_path: str = "face_db.pkl"):
        self.db_path = db_path
        self.faces: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'rb') as f:
                    self.faces = pickle.load(f)
                print(f"Loaded {len(self.faces)} enrolled faces")
            except Exception:
                self.faces = {}

    def save(self):
        with open(self.db_path, 'wb') as f:
            pickle.dump(self.faces, f)

    def enroll(self, name: str, embedding: np.ndarray, thumbnail: np.ndarray) -> bool:
        self.faces[name] = {
            'embedding': embedding,
            'thumbnail': thumbnail,
            'enrolled_at': datetime.now().isoformat()
        }
        self.save()
        return True

    def search(self, embedding: np.ndarray, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """Search for matching face. Returns (name, similarity) or None."""
        if not self.faces:
            return None

        best_match = None
        best_sim = 0

        for name, data in self.faces.items():
            sim = self._cosine_similarity(embedding, data['embedding'])
            if sim > best_sim and sim >= threshold:
                best_sim = sim
                best_match = name

        return (best_match, best_sim) if best_match else None

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        a = np.array(a).flatten()
        b = np.array(b).flatten()
        if len(a) != len(b):
            return 0
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def list_enrolled(self) -> List[str]:
        return list(self.faces.keys())

    def delete(self, name: str) -> bool:
        if name in self.faces:
            del self.faces[name]
            self.save()
            return True
        return False


class FaceTracker:
    """Simple face tracking to maintain consistent IDs across frames."""

    def __init__(self, max_disappeared: int = 10):
        self.next_id = 0
        self.faces: Dict[int, Dict] = {}  # {id: {'centroid': (x,y), 'disappeared': count}}
        self.max_disappeared = max_disappeared

    def update(self, detections: List[Dict]) -> Dict[int, Dict]:
        """Update tracker with new detections. Returns {id: detection}."""
        if not detections:
            # Mark all as disappeared
            for fid in list(self.faces.keys()):
                self.faces[fid]['disappeared'] += 1
                if self.faces[fid]['disappeared'] > self.max_disappeared:
                    del self.faces[fid]
            return {}

        # Get centroids of new detections
        new_centroids = []
        for det in detections:
            area = det.get('facial_area', {})
            cx = area.get('x', 0) + area.get('w', 0) // 2
            cy = area.get('y', 0) + area.get('h', 0) // 2
            new_centroids.append((cx, cy))

        # If no existing faces, register all as new
        if not self.faces:
            result = {}
            for i, det in enumerate(detections):
                self.faces[self.next_id] = {
                    'centroid': new_centroids[i],
                    'disappeared': 0
                }
                result[self.next_id] = det
                self.next_id += 1
            return result

        # Match existing faces to new detections
        face_ids = list(self.faces.keys())
        face_centroids = [self.faces[fid]['centroid'] for fid in face_ids]

        # Simple nearest neighbor matching
        used_detections = set()
        result = {}

        for i, fid in enumerate(face_ids):
            fc = face_centroids[i]
            best_dist = float('inf')
            best_j = -1

            for j, nc in enumerate(new_centroids):
                if j in used_detections:
                    continue
                dist = np.sqrt((fc[0] - nc[0])**2 + (fc[1] - nc[1])**2)
                if dist < best_dist and dist < 150:  # Max 150px movement
                    best_dist = dist
                    best_j = j

            if best_j >= 0:
                self.faces[fid]['centroid'] = new_centroids[best_j]
                self.faces[fid]['disappeared'] = 0
                result[fid] = detections[best_j]
                used_detections.add(best_j)
            else:
                self.faces[fid]['disappeared'] += 1
                if self.faces[fid]['disappeared'] > self.max_disappeared:
                    del self.faces[fid]

        # Register new faces
        for j, det in enumerate(detections):
            if j not in used_detections:
                self.faces[self.next_id] = {
                    'centroid': new_centroids[j],
                    'disappeared': 0
                }
                result[self.next_id] = det
                self.next_id += 1

        return result


# =============================================================================
# MAIN DEMO CLASS
# =============================================================================

class BiometricDemo:
    """Full-feature biometric demo."""

    MODES = ["all", "face", "quality", "demographics", "landmarks", "liveness", "enroll", "verify"]

    def __init__(self, camera_id: int = 0, mode: str = "all"):
        self.camera_id = camera_id
        self.mode = mode
        self.mode_index = self.MODES.index(mode) if mode in self.MODES else 0

        # State
        self.paused = False
        self.recording = False
        self.video_writer = None

        # Performance
        self.fps = 0.0
        self.frame_times = deque(maxlen=30)
        self.last_fps_update = time.time()

        # Display
        self.show_fps = True
        self.show_help = False
        self.show_stats = True
        self.window_name = "Biometric Demo"

        # ML Components
        self._deepface = None
        self._mp_face_mesh = None  # Legacy Solutions API
        self._mp_face_landmarker = None  # New Tasks API
        self._mp_use_tasks_api = False
        self._mediapipe_loaded = False
        self._quality_assessor = SimpleQualityAssessor()
        self._liveness_detector = SimpleLivenessDetector()
        self._face_db = FaceDatabase()
        self._face_tracker = FaceTracker()

        # Caching
        self._demographics_cache = {}
        self._demographics_interval = 2.0  # Slower refresh for stability
        self._last_demographics_time = 0
        self._embeddings_cache = {}
        self._last_embedding_time = 0

        # Verification cache (to prevent flickering)
        self._verification_cache = {}  # {face_id: {'match': (name, sim), 'time': timestamp}}
        self._verification_interval = 2.0  # Keep match visible for 2 seconds

        # Quality and liveness cache
        self._quality_cache = {}
        self._liveness_cache = {}
        self._cache_interval = 0.5  # Update every 0.5 seconds

        # Analysis history for export
        self._analysis_history = deque(maxlen=1000)

        # Colors
        self.COLORS = {
            'green': (0, 255, 0),
            'red': (0, 0, 255),
            'blue': (255, 150, 0),
            'yellow': (0, 255, 255),
            'cyan': (255, 255, 0),
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'orange': (0, 165, 255),
            'purple': (255, 0, 255),
        }

        # Stats
        self.stats = {
            'frames_processed': 0,
            'faces_detected': 0,
            'enrollments': len(self._face_db.faces),
            'verifications': 0,
            'live_checks': 0
        }

    def _init_ml(self):
        """Initialize ML components."""
        print("\n" + "=" * 60)
        print("BIOMETRIC DEMO - INITIALIZING")
        print("=" * 60)

        print("[1/3] Loading DeepFace (face detection + embeddings)...")
        from deepface import DeepFace
        self._deepface = DeepFace
        print("      DeepFace ready!")

        print("[2/3] Loading MediaPipe (468 landmarks)...")
        self._mediapipe_loaded = False
        self._mp_face_mesh = None
        self._mp_use_tasks_api = False

        try:
            import mediapipe as mp

            # Try new Tasks API first (MediaPipe 0.10.14+)
            if hasattr(mp, 'tasks'):
                try:
                    from mediapipe.tasks import python as mp_tasks
                    from mediapipe.tasks.python import vision

                    # Download model if needed
                    import urllib.request
                    import os
                    model_path = "face_landmarker.task"
                    if not os.path.exists(model_path):
                        print("      Downloading face landmark model...")
                        url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
                        urllib.request.urlretrieve(url, model_path)

                    base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
                    options = vision.FaceLandmarkerOptions(
                        base_options=base_options,
                        output_face_blendshapes=False,
                        output_facial_transformation_matrixes=False,
                        num_faces=5
                    )
                    self._mp_face_landmarker = vision.FaceLandmarker.create_from_options(options)
                    self._mp_use_tasks_api = True
                    self._mediapipe_loaded = True
                    print("      MediaPipe Tasks API ready!")
                except Exception as e:
                    print(f"      Tasks API failed: {e}")

            # Fall back to legacy solutions API
            if not self._mediapipe_loaded and hasattr(mp, 'solutions'):
                self._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=5,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                self._mediapipe_loaded = True
                print("      MediaPipe Solutions API ready!")

            if not self._mediapipe_loaded:
                print("      MediaPipe: No compatible API found")

        except Exception as e:
            print(f"      MediaPipe unavailable: {e}")

        print("[3/3] Loading local components...")
        print(f"      Quality Assessor: ready")
        print(f"      Liveness Detector: ready")
        print(f"      Face Database: {len(self._face_db.faces)} enrolled")
        print(f"      Face Tracker: ready")

        print("=" * 60)
        print("ALL SYSTEMS READY!")
        print("=" * 60 + "\n")

    # =========================================================================
    # DETECTION METHODS
    # =========================================================================

    def detect_faces(self, frame: np.ndarray) -> List[Dict]:
        """Detect faces and track them."""
        try:
            face_objs = self._deepface.extract_faces(
                img_path=frame,
                detector_backend="opencv",
                enforce_detection=False,
                align=False,
            )
            faces = [f for f in face_objs if f.get('confidence', 0) > 0.5]
            return faces
        except Exception:
            return []

    def extract_embedding(self, frame: np.ndarray, face_region: Dict) -> Optional[np.ndarray]:
        """Extract face embedding for verification."""
        current_time = time.time()
        if current_time - self._last_embedding_time < 0.5:
            return None

        try:
            x, y, w, h = face_region['x'], face_region['y'], face_region['w'], face_region['h']
            pad = 30
            x, y = max(0, x - pad), max(0, y - pad)
            w = min(w + 2*pad, frame.shape[1] - x)
            h = min(h + 2*pad, frame.shape[0] - y)

            face_img = frame[y:y+h, x:x+w]
            if face_img.size == 0 or min(face_img.shape[:2]) < 48:
                return None

            embeddings = self._deepface.represent(
                img_path=face_img,
                model_name="VGG-Face",
                enforce_detection=False,
                detector_backend="skip"
            )

            self._last_embedding_time = current_time
            if embeddings and len(embeddings) > 0:
                return np.array(embeddings[0]['embedding'])
            return None
        except Exception:
            return None

    def analyze_demographics(self, frame: np.ndarray, face_region: Dict) -> Dict:
        """Analyze demographics with caching."""
        current_time = time.time()
        face_id = f"{face_region['x']//50}_{face_region['y']//50}"

        # Check cache
        if face_id in self._demographics_cache:
            cached = self._demographics_cache[face_id]
            if current_time - cached['time'] < self._demographics_interval:
                return cached['data']

        # Throttle analysis
        if current_time - self._last_demographics_time < 0.3:
            return self._demographics_cache.get(face_id, {}).get('data', {})

        self._last_demographics_time = current_time

        try:
            x, y, w, h = face_region['x'], face_region['y'], face_region['w'], face_region['h']
            pad = 20
            x, y = max(0, x - pad), max(0, y - pad)
            w = min(w + 2*pad, frame.shape[1] - x)
            h = min(h + 2*pad, frame.shape[0] - y)

            face_img = frame[y:y+h, x:x+w]
            if face_img.size == 0 or face_img.shape[0] < 48:
                return {}

            results = self._deepface.analyze(
                img_path=face_img,
                actions=['age', 'gender', 'emotion'],
                enforce_detection=False,
                detector_backend='skip',
                silent=True
            )

            if results:
                result = results[0] if isinstance(results, list) else results
                data = {
                    'age': int(result.get('age', 0)),
                    'gender': 'M' if result.get('dominant_gender') == 'Man' else 'F',
                    'emotion': result.get('dominant_emotion', '?')
                }
                self._demographics_cache[face_id] = {'data': data, 'time': current_time}
                return data
            return {}
        except Exception:
            return self._demographics_cache.get(face_id, {}).get('data', {})

    def detect_landmarks(self, frame: np.ndarray) -> List[List[Tuple[int, int]]]:
        """Detect 468 facial landmarks using MediaPipe (Tasks or Solutions API)."""
        if not self._mediapipe_loaded:
            return []

        h, w = frame.shape[:2]

        try:
            # Use Tasks API (MediaPipe 0.10.14+)
            if self._mp_use_tasks_api and hasattr(self, '_mp_face_landmarker'):
                import mediapipe as mp
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = self._mp_face_landmarker.detect(mp_image)

                if not results.face_landmarks:
                    return []

                all_landmarks = []
                for face in results.face_landmarks:
                    points = [(int(lm.x * w), int(lm.y * h)) for lm in face]
                    all_landmarks.append(points)
                return all_landmarks

            # Use legacy Solutions API
            elif self._mp_face_mesh is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self._mp_face_mesh.process(rgb)
                if not results.multi_face_landmarks:
                    return []

                return [[(int(lm.x * w), int(lm.y * h)) for lm in face.landmark]
                        for face in results.multi_face_landmarks]

        except Exception as e:
            # Only log once per session to avoid spam
            if not hasattr(self, '_landmark_error_logged'):
                print(f"Landmark detection error: {e}")
                self._landmark_error_logged = True
            return []

        return []

    # =========================================================================
    # DRAWING METHODS
    # =========================================================================

    def draw_face(self, frame: np.ndarray, face: Dict, face_id: int, info: Dict, color: Tuple):
        """Draw face box with info panel."""
        area = face.get('facial_area', {})
        x, y, w, h = area.get('x', 0), area.get('y', 0), area.get('w', 100), area.get('h', 100)

        # Face box with corners
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
        corner = min(w, h) // 4
        for px, py, dx, dy in [(x, y, 1, 1), (x+w, y, -1, 1), (x, y+h, 1, -1), (x+w, y+h, -1, -1)]:
            cv2.line(frame, (px, py), (px + corner*dx, py), color, 3)
            cv2.line(frame, (px, py), (px, py + corner*dy), color, 3)

        # Face ID badge
        cv2.rectangle(frame, (x, y-25), (x+40, y), color, -1)
        cv2.putText(frame, f"#{face_id}", (x+5, y-7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS['white'], 1)

        # Info panel
        if info:
            self._draw_info_panel(frame, info, x + w + 10, y)

    def _draw_info_panel(self, frame: np.ndarray, info: Dict, x: int, y: int):
        """Draw info panel with background."""
        lines = [f"{k}: {v}" for k, v in info.items()]
        if not lines:
            return

        font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
        padding = 6

        widths = [cv2.getTextSize(l, font, scale, thick)[0][0] for l in lines]
        max_w = max(widths) if widths else 100
        line_h = 18
        total_h = len(lines) * line_h + padding * 2

        # Clamp position
        if x + max_w + padding * 2 > frame.shape[1]:
            x = max(0, frame.shape[1] - max_w - padding * 2)

        # Background
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + max_w + padding*2, y + total_h), self.COLORS['black'], -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Text
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (x + padding, y + padding + (i+1)*line_h - 4),
                       font, scale, self.COLORS['white'], thick)

    def draw_landmarks(self, frame: np.ndarray, landmarks: List[List[Tuple[int, int]]]):
        """Draw facial landmarks with better visibility."""
        if not landmarks:
            return

        for points in landmarks:
            # Draw mesh connections for better visibility
            # Face contour
            contour_indices = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10]

            # Draw contour
            for i in range(len(contour_indices) - 1):
                if contour_indices[i] < len(points) and contour_indices[i+1] < len(points):
                    pt1 = points[contour_indices[i]]
                    pt2 = points[contour_indices[i+1]]
                    cv2.line(frame, pt1, pt2, self.COLORS['cyan'], 1)

            # Draw key points (eyes, nose, mouth)
            key_points = [
                # Left eye
                (33, self.COLORS['green']), (133, self.COLORS['green']),
                (160, self.COLORS['green']), (144, self.COLORS['green']),
                # Right eye
                (362, self.COLORS['green']), (263, self.COLORS['green']),
                (387, self.COLORS['green']), (373, self.COLORS['green']),
                # Nose
                (1, self.COLORS['yellow']), (4, self.COLORS['yellow']),
                # Mouth
                (61, self.COLORS['red']), (291, self.COLORS['red']),
                (0, self.COLORS['red']), (17, self.COLORS['red']),
            ]

            for idx, color in key_points:
                if idx < len(points):
                    cv2.circle(frame, points[idx], 3, color, -1)

            # Draw all points smaller
            for i, (x, y) in enumerate(points):
                cv2.circle(frame, (x, y), 1, (150, 200, 200), -1)

    def draw_status_bar(self, frame: np.ndarray):
        """Draw top status bar."""
        h, w = frame.shape[:2]

        # Background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 40), self.COLORS['black'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Mode
        mode_color = self.COLORS['cyan'] if self.mode != 'enroll' else self.COLORS['orange']
        cv2.putText(frame, f"Mode: {self.mode.upper()}", (10, 28), font, 0.6, mode_color, 2)

        # Recording indicator
        if self.recording:
            cv2.circle(frame, (200, 20), 8, self.COLORS['red'], -1)
            cv2.putText(frame, "REC", (215, 28), font, 0.5, self.COLORS['red'], 2)

        # Paused indicator
        if self.paused:
            cv2.putText(frame, "PAUSED", (280, 28), font, 0.5, self.COLORS['yellow'], 2)

        # FPS
        if self.show_fps:
            fps_color = self.COLORS['green'] if self.fps >= 10 else self.COLORS['yellow'] if self.fps >= 5 else self.COLORS['red']
            cv2.putText(frame, f"FPS: {self.fps:.1f}", (w - 100, 28), font, 0.5, fps_color, 1)

        # Enrolled count
        enrolled = len(self._face_db.faces)
        if enrolled > 0:
            cv2.putText(frame, f"Enrolled: {enrolled}", (w - 220, 28), font, 0.5, self.COLORS['green'], 1)

        # Help hint
        cv2.putText(frame, "'h' help | 'e' enroll | 'd' delete | 'r' record", (w//2 - 150, 28), font, 0.4, self.COLORS['white'], 1)

    def draw_stats_panel(self, frame: np.ndarray):
        """Draw statistics panel."""
        if not self.show_stats:
            return

        h, w = frame.shape[:2]
        stats_lines = [
            f"Frames: {self.stats['frames_processed']}",
            f"Faces: {self.stats['faces_detected']}",
            f"Enrolled: {self.stats['enrollments']}",
            f"Verified: {self.stats['verifications']}",
        ]

        # Background
        panel_w, panel_h = 130, len(stats_lines) * 20 + 15
        overlay = frame.copy()
        cv2.rectangle(overlay, (w - panel_w - 10, h - panel_h - 10), (w - 10, h - 10), self.COLORS['black'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Text
        for i, line in enumerate(stats_lines):
            cv2.putText(frame, line, (w - panel_w, h - panel_h + 20 + i*20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLORS['white'], 1)

    def draw_help(self, frame: np.ndarray):
        """Draw help overlay with two columns."""
        if not self.show_help:
            return

        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (30, 30), (w-30, h-30), self.COLORS['black'], -1)
        cv2.addWeighted(overlay, 0.92, frame, 0.08, 0, frame)

        font = cv2.FONT_HERSHEY_SIMPLEX

        # Title
        cv2.putText(frame, "BIOMETRIC DEMO - FULL FEATURES", (50, 70), font, 0.9, self.COLORS['cyan'], 2)
        cv2.line(frame, (50, 85), (w-50, 85), self.COLORS['cyan'], 1)

        # Left column - Controls
        left_x = 60
        left_lines = [
            ("CONTROLS", 0.6, self.COLORS['yellow']),
            ("", 0.4, self.COLORS['white']),
            ("q    Quit application", 0.45, self.COLORS['white']),
            ("m    Cycle through modes", 0.45, self.COLORS['white']),
            ("e    Enroll current face", 0.45, self.COLORS['green']),
            ("d    Delete all enrolled", 0.45, self.COLORS['red']),
            ("c    Compare faces in frame", 0.45, self.COLORS['white']),
            ("r    Toggle video recording", 0.45, self.COLORS['red']),
            ("x    Export analysis to JSON", 0.45, self.COLORS['white']),
            ("s    Save screenshot", 0.45, self.COLORS['white']),
            ("f    Toggle FPS display", 0.45, self.COLORS['white']),
            ("Space  Pause/Resume", 0.45, self.COLORS['white']),
            ("h    Toggle this help", 0.45, self.COLORS['white']),
        ]

        y = 115
        for text, scale, color in left_lines:
            thick = 2 if scale > 0.5 else 1
            cv2.putText(frame, text, (left_x, y), font, scale, color, thick)
            y += 24

        # Right column - Features
        right_x = w // 2 + 20
        right_lines = [
            ("FEATURES", 0.6, self.COLORS['yellow']),
            ("", 0.4, self.COLORS['white']),
            ("Face Detection - Multi-face with tracking IDs", 0.4, self.COLORS['white']),
            ("Quality - Blur, brightness, size analysis", 0.4, self.COLORS['white']),
            ("Demographics - Age, gender, emotion", 0.4, self.COLORS['white']),
            ("Landmarks - 468 facial points (MediaPipe)", 0.4, self.COLORS['white']),
            ("Liveness - Anti-spoofing detection", 0.4, self.COLORS['white']),
            ("Enrollment - Save faces to local database", 0.4, self.COLORS['green']),
            ("Verification - Match against enrolled faces", 0.4, self.COLORS['cyan']),
            ("Comparison - Similarity between faces", 0.4, self.COLORS['white']),
            ("Recording - Save annotated video (MP4)", 0.4, self.COLORS['red']),
            ("Export - Analysis history to JSON", 0.4, self.COLORS['white']),
        ]

        y = 115
        for text, scale, color in right_lines:
            thick = 2 if scale > 0.5 else 1
            cv2.putText(frame, text, (right_x, y), font, scale, color, thick)
            y += 24

        # Bottom - Modes and status
        cv2.line(frame, (50, h-120), (w-50, h-120), self.COLORS['cyan'], 1)

        modes_text = "MODES: all | face | quality | demographics | landmarks | liveness | enroll | verify"
        cv2.putText(frame, modes_text, (60, h-95), font, 0.45, self.COLORS['yellow'], 1)

        # Status row
        status_y = h - 60
        cv2.putText(frame, f"Current Mode: {self.mode.upper()}", (60, status_y), font, 0.55, self.COLORS['green'], 2)
        cv2.putText(frame, f"Enrolled: {len(self._face_db.faces)}", (350, status_y), font, 0.55, self.COLORS['cyan'], 1)
        cv2.putText(frame, f"Frames: {self.stats['frames_processed']}", (520, status_y), font, 0.55, self.COLORS['white'], 1)
        cv2.putText(frame, f"FPS: {self.fps:.1f}", (700, status_y), font, 0.55, self.COLORS['green'] if self.fps >= 10 else self.COLORS['yellow'], 1)

        # Tip
        tip = "TIP: Press 'e' to enroll your face, then see 'Match' appear when recognized!"
        cv2.putText(frame, tip, (60, h-35), font, 0.4, self.COLORS['orange'], 1)

    def draw_enrolled_faces(self, frame: np.ndarray):
        """Draw thumbnails of enrolled faces."""
        if not self._face_db.faces:
            return

        h, w = frame.shape[:2]
        thumb_size = 50
        margin = 5
        start_x = 10
        start_y = h - thumb_size - 10

        for i, (name, data) in enumerate(list(self._face_db.faces.items())[:5]):
            thumb = data.get('thumbnail')
            if thumb is not None:
                try:
                    thumb_resized = cv2.resize(thumb, (thumb_size, thumb_size))
                    x = start_x + i * (thumb_size + margin)
                    frame[start_y:start_y+thumb_size, x:x+thumb_size] = thumb_resized
                    cv2.rectangle(frame, (x, start_y), (x+thumb_size, start_y+thumb_size), self.COLORS['green'], 1)
                    cv2.putText(frame, name[:6], (x, start_y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, self.COLORS['white'], 1)
                except Exception:
                    pass

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def enroll_face(self, frame: np.ndarray, faces: List[Dict]):
        """Enroll the largest face in frame (prevents duplicates)."""
        if not faces:
            print("No face detected for enrollment")
            return

        # Get largest face
        largest = max(faces, key=lambda f: f.get('facial_area', {}).get('w', 0) * f.get('facial_area', {}).get('h', 0))
        area = largest.get('facial_area', {})
        face_region = {'x': area.get('x', 0), 'y': area.get('y', 0), 'w': area.get('w', 100), 'h': area.get('h', 100)}

        # Force extract embedding (bypass throttling for enrollment)
        self._last_embedding_time = 0
        embedding = self.extract_embedding(frame, face_region)
        if embedding is None:
            print("Could not extract embedding - try again with better lighting")
            return

        # Check if face already enrolled (duplicate prevention)
        existing_match = self._face_db.search(embedding, threshold=0.55)
        if existing_match:
            name, similarity = existing_match
            print(f"Already enrolled as '{name}' ({similarity*100:.0f}% match) - skipping")
            return

        # Create thumbnail
        x, y, w, h = face_region['x'], face_region['y'], face_region['w'], face_region['h']
        thumbnail = frame[max(0,y):y+h, max(0,x):x+w].copy()

        # Generate name
        name = f"Person_{len(self._face_db.faces) + 1}"

        if self._face_db.enroll(name, embedding, thumbnail):
            self.stats['enrollments'] = len(self._face_db.faces)
            print(f"Enrolled: {name}")

    def verify_face(self, frame: np.ndarray, face_region: Dict, face_id: int) -> Optional[Tuple[str, float]]:
        """Verify face against enrolled faces with caching."""
        current_time = time.time()
        face_key = str(face_id)

        # Check cache first - return cached result if still valid
        if face_key in self._verification_cache:
            cached = self._verification_cache[face_key]
            if current_time - cached['time'] < self._verification_interval:
                return cached['match']

        # Throttle embedding extraction (expensive operation)
        if current_time - self._last_embedding_time < 1.0:
            # Return cached result if available
            if face_key in self._verification_cache:
                return self._verification_cache[face_key]['match']
            return None

        # Extract embedding
        embedding = self.extract_embedding(frame, face_region)
        if embedding is None:
            # Keep showing old match if we couldn't get new embedding
            if face_key in self._verification_cache:
                return self._verification_cache[face_key]['match']
            return None

        # Search for match
        match = self._face_db.search(embedding, threshold=0.5)

        # Cache the result
        self._verification_cache[face_key] = {
            'match': match,
            'time': current_time
        }

        if match:
            self.stats['verifications'] += 1

        return match

    def compare_faces(self, frame: np.ndarray, faces: List[Dict]) -> List[Tuple[int, int, float]]:
        """Compare all faces in frame. Returns [(i, j, similarity), ...]."""
        if len(faces) < 2:
            return []

        embeddings = []
        for face in faces:
            area = face.get('facial_area', {})
            region = {'x': area.get('x', 0), 'y': area.get('y', 0), 'w': area.get('w', 100), 'h': area.get('h', 100)}

            # Direct embedding extraction for comparison
            try:
                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                face_img = frame[max(0,y-20):y+h+20, max(0,x-20):x+w+20]
                if face_img.size > 0:
                    emb = self._deepface.represent(face_img, model_name="VGG-Face",
                                                   enforce_detection=False, detector_backend="skip")
                    if emb:
                        embeddings.append(np.array(emb[0]['embedding']))
                    else:
                        embeddings.append(None)
                else:
                    embeddings.append(None)
            except Exception:
                embeddings.append(None)

        # Compare all pairs
        comparisons = []
        for i in range(len(embeddings)):
            for j in range(i+1, len(embeddings)):
                if embeddings[i] is not None and embeddings[j] is not None:
                    sim = FaceDatabase._cosine_similarity(embeddings[i], embeddings[j])
                    comparisons.append((i, j, sim))

        return comparisons

    def toggle_recording(self, frame_size: Tuple[int, int]):
        """Toggle video recording."""
        if self.recording:
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.recording = False
            print("Recording stopped")
        else:
            filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(filename, fourcc, 20.0, frame_size)
            self.recording = True
            print(f"Recording started: {filename}")

    def export_analysis(self):
        """Export analysis history to JSON."""
        filename = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            'exported_at': datetime.now().isoformat(),
            'stats': self.stats,
            'enrolled_faces': list(self._face_db.faces.keys()),
            'history': list(self._analysis_history)
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Exported: {filename}")

    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process a single frame."""
        start_time = time.time()
        self.stats['frames_processed'] += 1

        # Detect and track faces
        detections = self.detect_faces(frame)
        tracked = self._face_tracker.update(detections)
        self.stats['faces_detected'] += len(tracked)

        # Store faces for actions
        self._current_faces = list(tracked.values())

        # Process each tracked face
        for face_id, face in tracked.items():
            area = face.get('facial_area', {})
            region = {'x': area.get('x', 0), 'y': area.get('y', 0), 'w': area.get('w', 100), 'h': area.get('h', 100)}

            info = {}
            color = self.COLORS['green']

            # Confidence
            conf = face.get('confidence', 0)
            info['Conf'] = f"{conf*100:.0f}%"

            # Quality (with caching)
            if self.mode in ["all", "quality", "enroll"]:
                current_time = time.time()
                cache_key = str(face_id)

                if cache_key not in self._quality_cache or \
                   current_time - self._quality_cache[cache_key]['time'] > self._cache_interval:
                    face_img = frame[max(0,region['y']):region['y']+region['h'],
                                    max(0,region['x']):region['x']+region['w']]
                    if face_img.size > 0:
                        q = self._quality_assessor.assess(face_img)
                        self._quality_cache[cache_key] = {'data': q, 'time': current_time}

                q = self._quality_cache.get(cache_key, {}).get('data', {})
                score = q.get('score', 0)
                info['Quality'] = f"{score:.0f}%"
                if score < 50:
                    color = self.COLORS['red']
                elif score < 70:
                    color = self.COLORS['yellow']

            # Demographics
            if self.mode in ["all", "demographics"]:
                demo = self.analyze_demographics(frame, region)
                if demo:
                    info['Age'] = demo.get('age', '?')
                    info['Gender'] = demo.get('gender', '?')
                    info['Mood'] = str(demo.get('emotion', '?'))[:7]

            # Liveness (with caching)
            if self.mode in ["all", "liveness"]:
                current_time = time.time()
                cache_key = str(face_id)

                if cache_key not in self._liveness_cache or \
                   current_time - self._liveness_cache[cache_key]['time'] > self._cache_interval:
                    face_img = frame[max(0,region['y']):region['y']+region['h'],
                                    max(0,region['x']):region['x']+region['w']]
                    if face_img.size > 0:
                        live = self._liveness_detector.check(face_img)
                        self._liveness_cache[cache_key] = {'data': live, 'time': current_time}
                        self.stats['live_checks'] += 1

                live = self._liveness_cache.get(cache_key, {}).get('data', {})
                info['Live'] = f"{'Y' if live.get('is_live') else 'N'} ({live.get('score', 0):.0f}%)"
                if not live.get('is_live'):
                    color = self.COLORS['red']

            # Verification
            if self.mode in ["all", "verify", "enroll"] and self._face_db.faces:
                match = self.verify_face(frame, region, face_id)
                if match:
                    info['Match'] = f"{match[0]} ({match[1]*100:.0f}%)"
                    color = self.COLORS['cyan']
                else:
                    info['Match'] = "---"  # Show placeholder when no match

            # Draw face
            self.draw_face(frame, face, face_id, info, color)

            # Store for history
            self._analysis_history.append({
                'time': datetime.now().isoformat(),
                'face_id': face_id,
                'info': info
            })

        # Landmarks
        if self.mode in ["all", "landmarks"]:
            landmarks = self.detect_landmarks(frame)
            self.draw_landmarks(frame, landmarks)

            # Show landmarks count
            if landmarks:
                total_points = sum(len(pts) for pts in landmarks)
                cv2.putText(frame, f"Landmarks: {total_points} pts ({len(landmarks)} faces)",
                           (10, frame.shape[0] - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS['cyan'], 1)

        # UI
        self.draw_status_bar(frame)
        self.draw_stats_panel(frame)
        self.draw_enrolled_faces(frame)
        self.draw_help(frame)

        # Recording
        if self.recording and self.video_writer:
            self.video_writer.write(frame)

        # FPS
        self.frame_times.append(time.time() - start_time)
        if time.time() - self.last_fps_update >= 0.5:
            self.fps = 1.0 / (sum(self.frame_times) / len(self.frame_times)) if self.frame_times else 0
            self.last_fps_update = time.time()

        return frame

    def run(self):
        """Main loop."""
        print("\n" + "=" * 60)
        print("BIOMETRIC DEMO - FULL FEATURES")
        print("=" * 60)
        print(f"Camera: {self.camera_id} | Mode: {self.mode}")
        print("=" * 60)

        self._init_ml()

        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print(f"ERROR: Could not open camera {self.camera_id}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Camera: {frame_w}x{frame_h}")

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1280, 720)

        print("\n" + "=" * 60)
        print("RUNNING! Press 'h' for help, 'q' to quit")
        print("=" * 60 + "\n")

        self._current_faces = []

        try:
            while True:
                if not self.paused:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    frame = cv2.flip(frame, 1)
                    processed = self.process_frame(frame)
                else:
                    processed = frame  # Show last frame when paused

                cv2.imshow(self.window_name, processed)

                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break
                elif key == ord('m'):
                    self.mode_index = (self.mode_index + 1) % len(self.MODES)
                    self.mode = self.MODES[self.mode_index]
                    print(f"Mode: {self.mode.upper()}")
                elif key == ord('e'):
                    self.enroll_face(frame, self._current_faces)
                elif key == ord('c'):
                    comps = self.compare_faces(frame, self._current_faces)
                    for i, j, sim in comps:
                        print(f"Face {i} vs Face {j}: {sim*100:.1f}% similar")
                elif key == ord('r'):
                    self.toggle_recording((frame_w, frame_h))
                elif key == ord('x'):
                    self.export_analysis()
                elif key == ord('s'):
                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, processed)
                    print(f"Saved: {filename}")
                elif key == ord('f'):
                    self.show_fps = not self.show_fps
                elif key == ord('h'):
                    self.show_help = not self.show_help
                elif key == ord(' '):
                    self.paused = not self.paused
                    print("Paused" if self.paused else "Resumed")
                elif key == ord('d'):
                    # Delete all enrolled faces
                    count = len(self._face_db.faces)
                    if count > 0:
                        self._face_db.faces.clear()
                        self._face_db.save()
                        self._verification_cache.clear()
                        self.stats['enrollments'] = 0
                        print(f"Deleted all {count} enrolled faces")
                    else:
                        print("No enrolled faces to delete")

        except KeyboardInterrupt:
            pass
        finally:
            if self.recording and self.video_writer:
                self.video_writer.release()
            cap.release()
            cv2.destroyAllWindows()
            print("\nDemo ended.")
            print(f"Stats: {self.stats}")


def main():
    parser = argparse.ArgumentParser(description="Biometric Demo - Full Features")
    parser.add_argument('--camera', '-c', type=int, default=0)
    parser.add_argument('--mode', '-m', type=str, default='all', choices=BiometricDemo.MODES)
    args = parser.parse_args()

    BiometricDemo(camera_id=args.camera, mode=args.mode).run()


if __name__ == "__main__":
    main()
