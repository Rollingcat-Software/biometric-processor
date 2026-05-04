"""Interactive tool to collect hybrid fusion test data.

Usage:
    python app/tools/test_data_collector.py

Workflow:
    1. Shows live camera feed
    2. Press SPACE to capture frame
    3. Select ground truth (1=LIVE, 2=SPOOF)
    4. Saves: frame image + metrics JSON
    5. Results in: data/test_frames/

Output format:
    data/test_frames/
    ├── live_frame_001.jpg
    ├── live_frame_001.json
    ├── spoof_frame_001.jpg
    ├── spoof_frame_001.json
    └── summary.jsonl (all frames + metrics)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

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


class TestDataCollector:
    """Collect labeled test frames for hybrid fusion validation."""

    OUTPUT_DIR = Path("data/test_frames")
    SUMMARY_FILE = OUTPUT_DIR / "summary.jsonl"

    def __init__(self):
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

    async def collect_from_camera(self):
        """Interactive camera capture loop."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Camera not available")
            return

        print("\n" + "=" * 60)
        print("TEST DATA COLLECTOR - Hybrid Fusion Validation")
        print("=" * 60)
        print("\nInstructions:")
        print("  SPACE  → Capture frame")
        print("  1      → Label as LIVE")
        print("  2      → Label as SPOOF")
        print("  Q      → Quit")
        print("\n" + "=" * 60 + "\n")

        captured_frame = None
        frame_number = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_number += 1

            # Show captured frame highlight
            display_frame = frame.copy()
            if captured_frame is not None:
                cv2.rectangle(display_frame, (10, 10), (100, 50), (0, 255, 0), 3)
                cv2.putText(
                    display_frame,
                    "CAPTURED",
                    (15, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )

            # Status text
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

            cv2.imshow("Test Data Collector", display_frame)

            key = cv2.waitKey(1) & 0xFF

            # SPACE - Capture frame
            if key == ord(" "):
                captured_frame = frame.copy()
                print(f"\n✓ Frame captured (#{frame_number})")
                print("  Press 1 (LIVE) or 2 (SPOOF) to label")

            # 1 - Label as LIVE
            elif key == ord("1") and captured_frame is not None:
                await self._save_frame(captured_frame, label="live")
                captured_frame = None

            # 2 - Label as SPOOF
            elif key == ord("2") and captured_frame is not None:
                await self._save_frame(captured_frame, label="spoof")
                captured_frame = None

            # Q - Quit
            elif key == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()
        self._print_summary()

    async def _save_frame(self, frame: np.ndarray, label: str):
        """Save frame and its metrics."""
        label = label.lower()
        self.frame_count[label] += 1
        timestamp = datetime.now().isoformat()
        filename = f"{label}_frame_{self.frame_count[label]:03d}"

        # Save image
        image_path = self.output_dir / f"{filename}.jpg"
        cv2.imwrite(str(image_path), frame)

        # Run analysis
        try:
            response = await self.use_case.analyze_frame(
                image=frame, mode=AnalysisMode.LIVENESS
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

            # Save metrics JSON
            json_path = self.output_dir / f"{filename}.json"
            with open(json_path, "w") as f:
                json.dump(metrics, f, indent=2)

            # Append to summary JSONL
            with open(self.SUMMARY_FILE, "a") as f:
                f.write(json.dumps(metrics) + "\n")

            # Print summary
            is_live = (
                response.liveness.is_live if response.liveness else False
            )
            confidence = (
                response.liveness.confidence if response.liveness else 0.0
            )
            prediction = "LIVE" if is_live else "SPOOF"

            correct = "✓" if (is_live and label == "live") or (not is_live and label == "spoof") else "✗"
            print(
                f"\n{correct} Saved {filename}: Prediction={prediction} "
                f"(conf={confidence:.2f})"
            )

        except FaceNotDetectedError:
            print(f"\n⚠️  No face detected in {filename}")
        except Exception as e:
            print(f"\n❌ Error processing {filename}: {e}")

    def _print_summary(self):
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


async def main():
    """Run the collector."""
    collector = TestDataCollector()
    await collector.collect_from_camera()


if __name__ == "__main__":
    asyncio.run(main())
