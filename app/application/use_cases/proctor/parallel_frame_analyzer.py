"""Parallel frame analyzer for proctoring.

This module provides parallel execution of independent frame analyses
using asyncio.gather for concurrent processing.

Following:
- Single Responsibility: Only handles parallel analysis orchestration
- Open/Closed: Can be extended with new analyzers without modification
- DRY: Centralized error handling and result merging
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from app.domain.entities.proctor_analysis import (
    FrameAnalysisResult,
)
from app.domain.interfaces.audio_analyzer import IAudioAnalyzer
from app.domain.interfaces.deepfake_detector import IDeepfakeDetector
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.gaze_tracker import IGazeTracker
from app.domain.interfaces.liveness_detector import ILivenessDetector
from app.domain.interfaces.object_detector import IObjectDetector
from app.domain.interfaces.similarity_calculator import ISimilarityCalculator
from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreakerOpenError,
    DEEPFAKE_DETECTOR_BREAKER,
    FACE_VERIFIER_BREAKER,
    GAZE_TRACKER_BREAKER,
    OBJECT_DETECTOR_BREAKER,
    AUDIO_ANALYZER_BREAKER,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisTask:
    """Configuration for a single analysis task.

    Attributes:
        name: Task name for logging
        enabled: Whether this task should run
        func: Async function to execute
        circuit_breaker: Optional circuit breaker to wrap the call
        fallback_result: Result to use if task fails or is skipped
    """

    name: str
    enabled: bool
    func: Callable[[], Any]
    circuit_breaker: Any = None
    fallback_result: Any = None


@dataclass
class FaceVerificationResult:
    """Result of face verification."""

    detected: bool = False
    matched: bool = False
    confidence: float = 0.0
    face_count: int = 0


@dataclass
class LivenessResult:
    """Result of liveness detection."""

    passed: bool = False
    score: float = 0.0


class ParallelFrameAnalyzer:
    """Parallel frame analysis using asyncio.gather.

    This analyzer executes all independent analyses concurrently,
    significantly reducing frame processing time compared to
    sequential execution.

    Architecture:
        Instead of running analyses one after another:
        [Face] -> [Gaze] -> [Object] -> [Deepfake] -> [Audio]
        Total: sum of all times

        We run independent analyses in parallel:
        [Face] ---|
        [Gaze] ---|--> [Merge Results]
        [Object] -|
        [Deepfake]|
        [Audio] --|
        Total: max of all times

    Performance:
        Sequential: ~500ms (100+100+100+100+100)
        Parallel: ~150ms (max of individual times + overhead)

    Thread Safety:
        Safe for concurrent use. Each analyze() call creates
        independent tasks that don't share mutable state.

    Usage:
        analyzer = ParallelFrameAnalyzer(
            embedding_extractor=extractor,
            similarity_calculator=calculator,
            gaze_tracker=gaze_tracker,
            object_detector=object_detector,
        )

        result = await analyzer.analyze(
            frame=frame,
            session=session,
            frame_number=1,
        )
    """

    def __init__(
        self,
        embedding_extractor: Optional[IEmbeddingExtractor] = None,
        similarity_calculator: Optional[ISimilarityCalculator] = None,
        liveness_detector: Optional[ILivenessDetector] = None,
        gaze_tracker: Optional[IGazeTracker] = None,
        object_detector: Optional[IObjectDetector] = None,
        audio_analyzer: Optional[IAudioAnalyzer] = None,
        deepfake_detector: Optional[IDeepfakeDetector] = None,
    ) -> None:
        """Initialize parallel frame analyzer.

        Args:
            embedding_extractor: For face embedding extraction
            similarity_calculator: For comparing embeddings
            liveness_detector: For liveness detection
            gaze_tracker: For gaze tracking analysis
            object_detector: For prohibited object detection
            audio_analyzer: For audio analysis
            deepfake_detector: For deepfake detection
        """
        self._embedding_extractor = embedding_extractor
        self._similarity_calculator = similarity_calculator
        self._liveness_detector = liveness_detector
        self._gaze_tracker = gaze_tracker
        self._object_detector = object_detector
        self._audio_analyzer = audio_analyzer
        self._deepfake_detector = deepfake_detector

        logger.info(
            f"ParallelFrameAnalyzer initialized: "
            f"face={embedding_extractor is not None}, "
            f"liveness={liveness_detector is not None}, "
            f"gaze={gaze_tracker is not None}, "
            f"object={object_detector is not None}, "
            f"audio={audio_analyzer is not None}, "
            f"deepfake={deepfake_detector is not None}"
        )

    async def analyze(
        self,
        frame: np.ndarray,
        session,
        frame_number: int,
        audio_data: Optional[bytes] = None,
        audio_sample_rate: int = 16000,
    ) -> FrameAnalysisResult:
        """Analyze frame with parallel execution of independent tasks.

        All independent analyses (gaze, object, deepfake, audio) run
        concurrently. Face verification and liveness have a dependency
        (liveness requires face detection) but are still parallelized
        with other independent tasks.

        Args:
            frame: Video frame as numpy array (BGR format)
            session: Proctoring session with configuration
            frame_number: Frame sequence number
            audio_data: Optional audio data bytes
            audio_sample_rate: Audio sample rate in Hz

        Returns:
            FrameAnalysisResult with all analysis results merged
        """
        timestamp = datetime.utcnow()

        # Build list of analysis tasks
        tasks = self._build_analysis_tasks(
            frame=frame,
            session=session,
            audio_data=audio_data,
            audio_sample_rate=audio_sample_rate,
        )

        # Execute all tasks in parallel
        results = await self._execute_parallel(tasks)

        # Extract results by name
        face_result = results.get("face", FaceVerificationResult())
        liveness_result_data = results.get("liveness", LivenessResult())
        gaze_result = results.get("gaze")
        object_result = results.get("object")
        audio_result = results.get("audio")
        deepfake_result = results.get("deepfake")

        return FrameAnalysisResult(
            session_id=session.id,
            timestamp=timestamp,
            frame_number=frame_number,
            face_detected=face_result.detected,
            face_matched=face_result.matched,
            face_confidence=face_result.confidence,
            face_count=face_result.face_count,
            liveness_passed=liveness_result_data.passed,
            liveness_score=liveness_result_data.score,
            gaze_result=gaze_result,
            object_result=object_result,
            audio_result=audio_result,
            deepfake_result=deepfake_result,
        )

    def _build_analysis_tasks(
        self,
        frame: np.ndarray,
        session,
        audio_data: Optional[bytes],
        audio_sample_rate: int,
    ) -> List[AnalysisTask]:
        """Build list of analysis tasks based on configuration.

        Args:
            frame: Video frame
            session: Proctoring session
            audio_data: Optional audio data
            audio_sample_rate: Audio sample rate

        Returns:
            List of AnalysisTask objects to execute
        """
        tasks = []

        # Face verification task
        if self._embedding_extractor and self._similarity_calculator:
            tasks.append(
                AnalysisTask(
                    name="face",
                    enabled=True,
                    func=lambda: self._verify_face(frame, session),
                    circuit_breaker=FACE_VERIFIER_BREAKER,
                    fallback_result=FaceVerificationResult(),
                )
            )

        # Liveness detection task (depends on face, but can start concurrently)
        if self._liveness_detector:
            tasks.append(
                AnalysisTask(
                    name="liveness",
                    enabled=True,
                    func=lambda: self._detect_liveness(frame),
                    circuit_breaker=None,  # No circuit breaker for liveness
                    fallback_result=LivenessResult(),
                )
            )

        # Gaze tracking task
        if self._gaze_tracker and session.config.gaze_sensitivity > 0:
            tasks.append(
                AnalysisTask(
                    name="gaze",
                    enabled=True,
                    func=lambda: self._gaze_tracker.analyze(frame, session.id),
                    circuit_breaker=GAZE_TRACKER_BREAKER,
                    fallback_result=None,
                )
            )

        # Object detection task
        if self._object_detector and session.config.enable_object_detection:
            tasks.append(
                AnalysisTask(
                    name="object",
                    enabled=True,
                    func=lambda: self._object_detector.detect(frame, session.id),
                    circuit_breaker=OBJECT_DETECTOR_BREAKER,
                    fallback_result=None,
                )
            )

        # Audio analysis task
        if (
            self._audio_analyzer
            and session.config.enable_audio_monitoring
            and audio_data
        ):
            tasks.append(
                AnalysisTask(
                    name="audio",
                    enabled=True,
                    func=lambda: self._audio_analyzer.analyze(
                        audio_data, audio_sample_rate, session.id
                    ),
                    circuit_breaker=AUDIO_ANALYZER_BREAKER,
                    fallback_result=None,
                )
            )

        # Deepfake detection task
        if self._deepfake_detector and session.config.enable_deepfake_detection:
            tasks.append(
                AnalysisTask(
                    name="deepfake",
                    enabled=True,
                    func=lambda: self._deepfake_detector.detect(frame, session.id),
                    circuit_breaker=DEEPFAKE_DETECTOR_BREAKER,
                    fallback_result=None,
                )
            )

        return tasks

    async def _execute_parallel(
        self, tasks: List[AnalysisTask]
    ) -> Dict[str, Any]:
        """Execute analysis tasks in parallel using asyncio.gather.

        Args:
            tasks: List of analysis tasks to execute

        Returns:
            Dictionary mapping task names to results
        """
        if not tasks:
            return {}

        # Create async wrappers for each task
        async def execute_task(task: AnalysisTask) -> Tuple[str, Any]:
            """Execute a single task with error handling."""
            try:
                if not task.enabled:
                    return task.name, task.fallback_result

                if task.circuit_breaker:
                    try:
                        result = await task.circuit_breaker.call_async(
                            task.func,
                            fallback=lambda: task.fallback_result,
                        )
                        return task.name, result
                    except CircuitBreakerOpenError:
                        logger.warning(f"{task.name} circuit breaker is open")
                        return task.name, task.fallback_result
                else:
                    # No circuit breaker, call directly
                    result = task.func()
                    # Handle both sync and async results
                    if asyncio.iscoroutine(result):
                        result = await result
                    return task.name, result

            except Exception as e:
                logger.error(f"Error in {task.name} analysis: {e}")
                return task.name, task.fallback_result

        # Execute all tasks in parallel
        task_results = await asyncio.gather(
            *[execute_task(task) for task in tasks],
            return_exceptions=True,
        )

        # Convert to dictionary, handling any exceptions
        results = {}
        for i, result in enumerate(task_results):
            if isinstance(result, Exception):
                logger.error(f"Task {tasks[i].name} raised exception: {result}")
                results[tasks[i].name] = tasks[i].fallback_result
            else:
                name, value = result
                results[name] = value

        return results

    async def _verify_face(
        self, frame: np.ndarray, session
    ) -> FaceVerificationResult:
        """Verify face against baseline embedding.

        Args:
            frame: Video frame
            session: Proctoring session with baseline embedding

        Returns:
            FaceVerificationResult
        """
        try:
            if session.baseline_embedding is None:
                logger.warning(f"Session {session.id} has no baseline embedding")
                return FaceVerificationResult()

            # Extract embedding from current frame
            try:
                current_embedding = await self._embedding_extractor.extract(frame)
            except Exception as e:
                logger.warning(f"Failed to extract embedding: {e}")
                return FaceVerificationResult()

            # Compare with baseline
            distance = self._similarity_calculator.calculate(
                current_embedding,
                session.baseline_embedding,
            )

            threshold = self._similarity_calculator.get_threshold()
            is_matched = distance < threshold
            confidence = 1.0 - distance

            return FaceVerificationResult(
                detected=True,
                matched=is_matched,
                confidence=confidence,
                face_count=1,
            )

        except Exception as e:
            logger.error(f"Face verification failed: {e}")
            return FaceVerificationResult()

    async def _detect_liveness(self, frame: np.ndarray) -> LivenessResult:
        """Run liveness detection on frame.

        Args:
            frame: Video frame

        Returns:
            LivenessResult
        """
        try:
            result = await self._liveness_detector.detect(frame)
            return LivenessResult(
                passed=result.is_live,
                score=result.liveness_score,
            )
        except Exception as e:
            logger.error(f"Liveness detection failed: {e}")
            return LivenessResult()

    def __repr__(self) -> str:
        components = []
        if self._embedding_extractor:
            components.append("face")
        if self._liveness_detector:
            components.append("liveness")
        if self._gaze_tracker:
            components.append("gaze")
        if self._object_detector:
            components.append("object")
        if self._audio_analyzer:
            components.append("audio")
        if self._deepfake_detector:
            components.append("deepfake")

        return f"ParallelFrameAnalyzer(components=[{', '.join(components)}])"
