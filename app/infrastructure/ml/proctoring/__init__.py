"""Proctoring ML implementations.

Real ML implementations for proctoring analysis:
- Gaze tracking using MediaPipe Face Mesh
- Object detection using YOLO
- Deepfake detection using texture/frequency analysis
- Audio analysis for voice activity and speaker detection
"""

from app.infrastructure.ml.proctoring.basic_audio_analyzer import BasicAudioAnalyzer
from app.infrastructure.ml.proctoring.mediapipe_gaze_tracker import MediaPipeGazeTracker
from app.infrastructure.ml.proctoring.texture_deepfake_detector import TextureDeepfakeDetector
from app.infrastructure.ml.proctoring.yolo_object_detector import YOLOObjectDetector

__all__ = [
    "MediaPipeGazeTracker",
    "YOLOObjectDetector",
    "TextureDeepfakeDetector",
    "BasicAudioAnalyzer",
]
