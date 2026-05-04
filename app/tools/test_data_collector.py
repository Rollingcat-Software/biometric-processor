"""Interactive tool to collect hybrid fusion test data.

Usage:
    python app/tools/test_data_collector.py

Workflow:
    1. Shows live camera feed
    2. Press SPACE to capture frame
    3. Select ground truth (1=LIVE, 2=SPOOF)
    4. Saves: frame image + metrics JSON
    5. Results in: data/test_frames/
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import cv2
import numpy as np

from app.application.services.device_spoof_risk_evaluator import DeviceSpoofRiskEvaluator
from app.application.services.hybrid_fusion_evaluator import HybridFusionEvaluator
from app.application.use_cases.live_camera_analysis import LiveCameraAnalysisUseCase
from app.api.schemas.live_analysis import AnalysisMode
from app.core.config import get_settings
from app.domain.exceptions.face_errors import FaceNotDetectedError
from app.infrastructure.ml.liveness.face_detector_factory import FaceDetectorFactory
from app.infrastructure.ml.liveness.liveness_detector_factory import LivenessDetectorFactory
from app.infrastructure.ml.liveness.quality_assessor_factory import QualityAssessorFactory
from app.infrastructure.ml.liveness.rppg_analyzer import RPPGAnalyzer

logger = logging.getLogger(__name__)

_CONFIDENCE_WINDOW_SIZE = 5
_MIN_CONFIDENCE_FOR_DETECTION = 0.50
_STATUS_MESSAGE_TTL_FRAMES = 45
_CAPTURE_KEYS = {32, 13, ord("c"), ord("C")}
_QUIT_KEYS = {ord("q"), ord("Q"), 27}


class TestDataCollector:
    """Collect labeled test frames for hybrid fusion validation."""

    OUTPUT_DIR = Path("data/test_frames")
    SUMMARY_FILE = OUTPUT_DIR / "summary.jsonl"

    def __init__(self) -> None:
        self.output_dir = self.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        settings = get_settings()
        self.detector = FaceDetectorFactory.create(
            backend=settings.FACE_DETECTION_BACKEND,
            device=settings.MODEL_DEVICE,
        )
        self.liveness_detector = LivenessDetectorFactory.create(
            backend=settings.get_liveness_backend(),
            device=settings.MODEL_DEVICE,
        )
        self.quality_assessor = QualityAssessorFactory.create(
            device=settings.MODEL_DEVICE,
        )
        self.device_spoof_evaluator = DeviceSpoofRiskEvaluator()
        self.rppg_analyzer = RPPGAnalyzer()
        self.hybrid_fusion_evaluator = HybridFusionEvaluator(
            threshold=settings.LIVENESS_FUSION_THRESHOLD
        )
        self.use_case = LiveCameraAnalysisUseCase(
            detector=self.detector,
            quality_assessor=self.quality_assessor,
            liveness_detector=self.liveness_detector,
            rppg_analyzer=self.rppg_analyzer,
            device_spoof_risk_evaluator=self.device_spoof_evaluator,
            settings=settings,
            hybrid_fusion_evaluator=self.hybrid_fusion_evaluator,
        )

        self.frame_count = {"live": 0, "spoof": 0}
        self.confidence_history = deque(maxlen=_CONFIDENCE_WINDOW_SIZE)

    def _detector_worker(self, frame_queue: Queue, result_queue: Queue) -> None:
        """Background thread: detect faces from frame queue."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            frame_data = frame_queue.get()
            if frame_data is None:
                break

            frame_number, frame = frame_data
            try:
                detection = loop.run_until_complete(self.detector.detect(frame))
                result_queue.put((frame_number, detection))
            except FaceNotDetectedError:
                result_queue.put((frame_number, None))
            except Exception as exc:
                logger.error("Detection error: %s", exc)
                result_queue.put((frame_number, None))

    def collect_from_camera(self) -> None:
        """Interactive camera capture loop (synchronous)."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Camera not available")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("\n" + "=" * 60)
        print("TEST DATA COLLECTOR - Hybrid Fusion Validation")
        print("=" * 60)
        print("\nInstructions:")
        print("  SPACE  -> Capture frame")
        print("  1      -> Label as LIVE")
        print("  2      -> Label as SPOOF")
        print("  Q      -> Quit")
        print("\nTroubleshooting:")
        print("  - If stuck on 'NO FACE', move closer/farther from camera")
        print("  - Ensure good lighting")
        print("  - Center your face in the frame")
        print("\n" + "=" * 60 + "\n")

        captured_frame = None
        frame_number = 0
        last_detection = None
        pending_results: dict[int, bool] = {}
        status_message = "SPACE: capture, 1: LIVE, 2: SPOOF, Q: quit"
        status_color = (200, 200, 200)
        status_ttl = _STATUS_MESSAGE_TTL_FRAMES
        last_key_code = -1

        cv2.namedWindow("Test Data Collector", cv2.WINDOW_NORMAL)

        frame_queue: Queue = Queue(maxsize=2)
        result_queue: Queue = Queue()
        detector_thread = threading.Thread(
            target=self._detector_worker,
            args=(frame_queue, result_queue),
            daemon=True,
        )
        detector_thread.start()

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1
            detection_ok = False

            try:
                frame_queue.put_nowait((frame_number, frame.copy()))
            except Exception:
                pass

            while True:
                try:
                    result_frame_num, detection = result_queue.get_nowait()
                except Empty:
                    break

                if detection:
                    self.confidence_history.append(float(detection.confidence))
                    last_detection = detection
                    pending_results[result_frame_num] = True
                else:
                    pending_results[result_frame_num] = False

            if pending_results:
                latest_result_frame = max(pending_results)
                detection_ok = bool(pending_results[latest_result_frame])
            elif last_detection is not None and self.confidence_history:
                detection_ok = (
                    float(np.mean(list(self.confidence_history)))
                    >= _MIN_CONFIDENCE_FOR_DETECTION
                )

            display_frame = frame.copy()
            if captured_frame is not None:
                cv2.rectangle(display_frame, (10, 10), (140, 50), (0, 255, 0), 3)
                cv2.putText(
                    display_frame,
                    "CAPTURED",
                    (15, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )

            face_status = "FACE DETECTED" if detection_ok else "NO FACE"
            face_color = (0, 255, 0) if detection_ok else (0, 0, 255)
            if self.confidence_history:
                avg_conf = float(np.mean(list(self.confidence_history)))
                conf_text = f"{face_status} ({avg_conf:.2f})"
            else:
                conf_text = face_status

            cv2.putText(
                display_frame,
                conf_text,
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                face_color,
                2,
            )

            status = (
                f"Frame: {frame_number} | Live: {self.frame_count['live']} | "
                f"Spoof: {self.frame_count['spoof']}"
            )
            cv2.putText(
                display_frame,
                status,
                (10, display_frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
            )
            if status_ttl > 0 and status_message:
                cv2.putText(
                    display_frame,
                    status_message,
                    (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    status_color,
                    2,
                )
                status_ttl -= 1

            cv2.imshow("Test Data Collector", display_frame)
            raw_key = cv2.waitKey(10)
            key = raw_key & 0xFF if raw_key != -1 else -1
            if key != -1:
                last_key_code = key

            if key in _CAPTURE_KEYS:
                captured_frame = frame.copy()
                if detection_ok:
                    print(f"\nFrame captured (#{frame_number})")
                    print("  Press 1 (LIVE) or 2 (SPOOF) to label")
                    status_message = (
                        f"Captured frame #{frame_number}. "
                        "Press 1=LIVE or 2=SPOOF."
                    )
                    status_color = (0, 255, 0)
                else:
                    print(f"\nFrame captured without confirmed face (#{frame_number})")
                    print("  Detector did not confirm a face yet.")
                    print("  Press 1/2 to save anyway, or SPACE again to recapture.")
                    status_message = (
                        f"Captured frame #{frame_number} without confirmed face. "
                        "Press 1/2 to save or SPACE to recapture."
                    )
                    status_color = (0, 215, 255)
                status_ttl = _STATUS_MESSAGE_TTL_FRAMES
            elif key in {ord("1"), 49} and captured_frame is not None:
                asyncio.run(self._save_frame(captured_frame, label="live"))
                captured_frame = None
                status_message = "Saved as LIVE. Press SPACE to capture next frame."
                status_color = (0, 255, 0)
                status_ttl = _STATUS_MESSAGE_TTL_FRAMES
            elif key in {ord("2"), 50} and captured_frame is not None:
                asyncio.run(self._save_frame(captured_frame, label="spoof"))
                captured_frame = None
                status_message = "Saved as SPOOF. Press SPACE to capture next frame."
                status_color = (0, 255, 0)
                status_ttl = _STATUS_MESSAGE_TTL_FRAMES
            elif key in _QUIT_KEYS:
                break

        frame_queue.put(None)
        detector_thread.join(timeout=2)
        cap.release()
        cv2.destroyAllWindows()
        self._print_summary()

    async def _save_frame(self, frame: np.ndarray, label: str) -> None:
        """Save frame and its metrics."""
        label = label.lower()
        self.frame_count[label] += 1
        timestamp = datetime.now().isoformat()
        filename = f"{label}_frame_{self.frame_count[label]:03d}"

        image_path = self.output_dir / f"{filename}.jpg"
        cv2.imwrite(str(image_path), frame)

        try:
            response = await self.use_case.analyze_frame(
                image=frame,
                mode=AnalysisMode.LIVENESS,
            )

            metrics = {
                "timestamp": timestamp,
                "label": label,
                "frame_number": self.frame_count[label],
                "image_path": str(image_path),
                "face_detected": response.face.detected if response.face else False,
                "liveness": (
                    {
                        "is_live": response.liveness.is_live,
                        "confidence": response.liveness.confidence,
                        "method": response.liveness.method,
                        "scores": response.liveness.scores,
                        "checks": response.liveness.checks,
                    }
                    if response.liveness
                    else None
                ),
                "quality": (
                    {
                        "score": response.quality.score,
                        "is_acceptable": response.quality.is_acceptable,
                    }
                    if response.quality
                    else None
                ),
            }

            json_path = self.output_dir / f"{filename}.json"
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(metrics, handle, indent=2)

            with open(self.SUMMARY_FILE, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(metrics) + "\n")

            is_live = response.liveness.is_live if response.liveness else False
            confidence = response.liveness.confidence if response.liveness else 0.0
            prediction = "LIVE" if is_live else "SPOOF"
            correct = (
                "OK"
                if (is_live and label == "live") or (not is_live and label == "spoof")
                else "MISS"
            )
            print(
                f"\n{correct} Saved {filename}: Prediction={prediction} "
                f"(conf={confidence:.2f})"
            )
        except FaceNotDetectedError:
            print(f"\nNo face detected in {filename}")
        except Exception as exc:
            print(f"\nError processing {filename}: {exc}")

    def _print_summary(self) -> None:
        """Print collection summary."""
        total = self.frame_count["live"] + self.frame_count["spoof"]
        print("\n" + "=" * 60)
        print("COLLECTION SUMMARY")
        print("=" * 60)
        print(f"Total frames: {total}")
        print(f"  LIVE:  {self.frame_count['live']}")
        print(f"  SPOOF: {self.frame_count['spoof']}")
        print(f"\nOutput directory: {self.output_dir.absolute()}")
        print(f"Summary JSONL: {self.SUMMARY_FILE.absolute()}")
        print("=" * 60 + "\n")


def main() -> None:
    """Run the collector."""
    collector = TestDataCollector()
    collector.collect_from_camera()


if __name__ == "__main__":
    main()
