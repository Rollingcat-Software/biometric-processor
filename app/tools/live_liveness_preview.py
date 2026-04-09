"""Developer-only webcam preview for live liveness calibration."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from statistics import pvariance
from typing import Any, Optional

import cv2
import numpy as np

from app.application.services.background_active_reaction_evaluator import (
    BackgroundActiveReactionEvaluator,
    ReactionSignalFrame,
)
from app.application.services.device_spoof_risk_evaluator import (
    DeviceSpoofRiskAssessment,
    DeviceSpoofRiskEvaluator,
)
from app.application.services.face_signal_metrics import extract_face_signal_metrics
from app.application.services.live_session_baseline_calibrator import (
    BaselineCalibrationFrame,
    LiveSessionBaselineCalibrator,
    SessionBaseline,
)
from app.core.config import Settings
from app.domain.entities.liveness_result import LivenessResult
from app.domain.exceptions.face_errors import FaceNotDetectedError
from app.domain.exceptions.liveness_errors import LivenessCheckError
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.landmark_detector import ILandmarkDetector
from app.domain.interfaces.liveness_detector import ILivenessDetector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameMetrics:
    """Per-frame metrics extracted from the current liveness pipeline."""

    timestamp: float
    face_detected: bool
    is_live: bool
    raw_score: float
    confidence: float
    passive_score: float
    active_score: float
    active_evidence: Optional[float]
    directional_agreement: Optional[float]
    face_quality: Optional[float]
    face_size_ratio: Optional[float]
    blur_score: Optional[float]
    brightness: float
    ear_current: Optional[float]
    mar_current: Optional[float]
    yaw_current: Optional[float]
    pitch_current: Optional[float]
    roll_current: Optional[float]
    landmark_model: Optional[str]
    background_active_mode: str
    background_active_detected: bool
    details: dict[str, Any]
    device_spoof: Optional[DeviceSpoofRiskAssessment] = None
    error: Optional[str] = None
    profiling: dict[str, float] = field(default_factory=dict)
    reused_face_detection: bool = False
    reused_landmarks: bool = False
    reused_liveness: bool = False
    held_from_previous: bool = False
    inference_scale: float = 1.0

    @property
    def frame_confidence(self) -> float:
        """Explicit alias for the detector's per-frame confidence."""
        return self.confidence


@dataclass(frozen=True)
class AggregatedMetrics:
    """Temporally smoothed metrics across the recent frame buffer."""

    sample_count: int
    window_seconds: float
    decision_state: str
    ema_score: float
    score_mean: float
    supported_score: float
    smoothed_score: float
    window_confidence: float
    score_variance: float
    min_score: float
    max_score: float
    stable_live_ratio: float
    face_present_ratio: float
    consecutive_no_face_frames: int
    warm_recovery: bool
    low_quality: bool
    sufficient_evidence: bool
    temporal_consistency: float
    frame_confidence_mean: float
    directional_agreement_mean: float
    face_quality_mean: float
    face_size_mean: float
    face_size_adequacy: float
    blur_adequacy: float
    brightness_adequacy: float
    ear_mean: Optional[float]
    ear_min: Optional[float]
    ear_max: Optional[float]
    ear_drop: Optional[float]
    ear_drop_ratio: Optional[float]
    mar_mean: Optional[float]
    mar_max: Optional[float]
    mar_rise: Optional[float]
    mar_rise_ratio: Optional[float]
    yaw_mean: Optional[float]
    yaw_left_peak: Optional[float]
    yaw_right_peak: Optional[float]
    pitch_mean: Optional[float]
    roll_mean: Optional[float]
    baseline_ready: bool
    baseline_sample_count: int
    baseline_duration_seconds: float
    ear_baseline: Optional[float]
    mar_baseline: Optional[float]
    smile_baseline: Optional[float]
    yaw_baseline: Optional[float]
    pitch_baseline: Optional[float]
    roll_baseline: Optional[float]
    blink_evidence: Optional[float]
    smile_evidence: Optional[float]
    mouth_open_evidence: Optional[float]
    head_turn_left_evidence: Optional[float]
    head_turn_right_evidence: Optional[float]
    primary_event: float
    secondary_event: float
    raw_reaction_evidence: float
    effective_trust: float
    trusted_reaction_evidence: float
    persisted_primary: float
    persisted_secondary: float
    persisted_reaction_evidence: float
    raw_active_evidence: float
    combined_active_evidence: float
    combined_active_score: float
    passive_window_score: float
    active_frame_score_mean: float
    active_frame_evidence_mean: float
    background_reaction_ms: float = 0.0
    temporal_aggregation_ms: float = 0.0
    @property
    def decision_confidence(self) -> float:
        """Backward-compatible alias for window-level decision confidence."""
        return self.window_confidence


class TemporalLivenessAggregator:
    """Rolling temporal aggregation for frame-level liveness output."""

    def __init__(
        self,
        *,
        window_seconds: float = 2.0,
        baseline_seconds: float = 0.75,
        max_entries: int = 45,
        ema_alpha: float = 0.25,
        no_face_consecutive_threshold: int = 6,
        face_return_grace_seconds: float = 1.0,
        face_loss_reset_seconds: float = 3.0,
        active_decay_seconds: float = 1.25,
        min_trusted_face_size_ratio: float = 0.08,
    ) -> None:
        self._window_seconds = window_seconds
        self._max_entries = max_entries
        self._buffer: deque[FrameMetrics] = deque()
        self._ema_alpha = ema_alpha
        self._no_face_consecutive_threshold = no_face_consecutive_threshold
        self._face_return_grace_seconds = face_return_grace_seconds
        self._face_loss_reset_seconds = face_loss_reset_seconds
        self._min_trusted_face_size_ratio = min_trusted_face_size_ratio
        self._background_reaction_evaluator = BackgroundActiveReactionEvaluator(
            decay_seconds=active_decay_seconds,
            min_face_size_ratio=min_trusted_face_size_ratio,
        )
        self._baseline_calibrator = LiveSessionBaselineCalibrator(baseline_seconds=baseline_seconds)
        self._ema_score: Optional[float] = None

    def add(self, metrics: FrameMetrics) -> AggregatedMetrics:
        """Add a frame result and return the updated temporal summary."""
        aggregation_started = time.perf_counter()
        self._buffer.append(metrics)
        self._evict_old_entries(reference_timestamp=metrics.timestamp)
        self._reset_long_face_loss_state(metrics.timestamp)
        session_baseline = self._baseline_calibrator.update(
            BaselineCalibrationFrame(
                timestamp=metrics.timestamp,
                face_detected=metrics.face_detected,
                face_quality=metrics.face_quality,
                blur_score=metrics.blur_score,
                brightness=metrics.brightness,
                ear_current=metrics.ear_current,
                mar_current=metrics.mar_current,
                yaw_current=metrics.yaw_current,
                pitch_current=metrics.pitch_current,
                roll_current=metrics.roll_current,
                smile_score=_maybe_float(metrics.details.get("smile")),
            )
        )

        if self._ema_score is None:
            self._ema_score = metrics.raw_score
        else:
            self._ema_score = self._ema_alpha * metrics.raw_score + (1.0 - self._ema_alpha) * self._ema_score

        recent_entries = list(self._buffer)
        effective_entries = _effective_entries_for_analysis(
            recent_entries,
            face_return_grace_seconds=self._face_return_grace_seconds,
        )
        scores = [item.raw_score for item in effective_entries]
        score_mean = float(np.mean(scores))
        # Keep score smoothing tied only to score history so it remains a temporal
        # stabilization of liveness, not a proxy for decision trustworthiness.
        smoothed_score = 0.65 * float(self._ema_score) + 0.35 * score_mean
        passive_window_score = _mean([entry.passive_score for entry in effective_entries]) or 0.0
        live_count = sum(1 for item in effective_entries if item.is_live)
        face_present_ratio = sum(1 for item in effective_entries if item.face_detected) / max(len(effective_entries), 1)
        consecutive_no_face_frames = _count_consecutive_no_face(recent_entries)
        warm_recovery = _is_warm_recovery_candidate(
            recent_entries=recent_entries,
            current_frame=metrics,
            face_return_grace_seconds=self._face_return_grace_seconds,
        )
        temporal_signal_summary = _compute_temporal_signal_summary(
            effective_entries,
            background_reaction_evaluator=self._background_reaction_evaluator,
            passive_window_score=passive_window_score,
            session_baseline=session_baseline,
        )
        low_quality = _is_low_quality(metrics)
        sufficient_evidence = _has_sufficient_evidence(
            recent_entries=effective_entries,
            temporal_signal_summary=temporal_signal_summary,
            current_frame=metrics,
            min_trusted_face_size_ratio=self._min_trusted_face_size_ratio,
            warm_recovery=warm_recovery,
        )
        score_variance = float(pvariance(scores)) if len(scores) > 1 else 0.0
        temporal_consistency = _calculate_temporal_consistency(score_variance)
        directional_agreement_mean = _mean(
            [entry.directional_agreement for entry in effective_entries if entry.directional_agreement is not None]
        ) or 0.0
        face_quality_mean = _mean(
            [entry.face_quality for entry in effective_entries if entry.face_quality is not None]
        ) or 0.0
        face_size_mean = _mean(
            [entry.face_size_ratio for entry in effective_entries if entry.face_size_ratio is not None]
        ) or 0.0
        face_size_adequacy = _mean(
            [_face_size_adequacy(entry.face_size_ratio) for entry in effective_entries if entry.face_size_ratio is not None]
        ) or 0.0
        blur_adequacy = _mean(
            [_blur_adequacy(entry.blur_score) for entry in effective_entries if entry.blur_score is not None]
        ) or 0.0
        brightness_adequacy = _mean(
            [_brightness_adequacy(entry.brightness) for entry in effective_entries]
        ) or 0.0
        frame_confidence_mean = _mean([entry.frame_confidence for entry in effective_entries]) or 0.0
        window_confidence = _calculate_window_confidence(
            recent_entries=effective_entries,
            face_present_ratio=face_present_ratio,
            temporal_signal_summary=temporal_signal_summary,
            sufficient_evidence=sufficient_evidence,
            temporal_consistency=temporal_consistency,
            frame_confidence_mean=frame_confidence_mean,
            directional_agreement_mean=directional_agreement_mean,
            face_quality_mean=face_quality_mean,
            face_size_adequacy=face_size_adequacy,
            blur_adequacy=blur_adequacy,
            brightness_adequacy=brightness_adequacy,
        )
        decision_state = _resolve_decision_state(
            recent_entries=effective_entries,
            current_frame=metrics,
            face_present_ratio=face_present_ratio,
            consecutive_no_face_frames=consecutive_no_face_frames,
            warm_recovery=warm_recovery,
            low_quality=low_quality,
            sufficient_evidence=sufficient_evidence,
            smoothed_score=smoothed_score,
            decision_confidence=window_confidence,
            no_face_consecutive_threshold=self._no_face_consecutive_threshold,
        )
        aggregation_elapsed_ms = (time.perf_counter() - aggregation_started) * 1000.0
        return AggregatedMetrics(
            sample_count=len(effective_entries),
            window_seconds=self._window_seconds,
            decision_state=decision_state,
            ema_score=float(self._ema_score),
            score_mean=score_mean,
            supported_score=float(temporal_signal_summary["supported_score"]),
            smoothed_score=smoothed_score,
            window_confidence=window_confidence,
            score_variance=score_variance,
            min_score=min(scores),
            max_score=max(scores),
            stable_live_ratio=live_count / max(len(effective_entries), 1),
            face_present_ratio=face_present_ratio,
            consecutive_no_face_frames=consecutive_no_face_frames,
            warm_recovery=warm_recovery,
            low_quality=low_quality,
            sufficient_evidence=sufficient_evidence,
            temporal_consistency=temporal_consistency,
            frame_confidence_mean=frame_confidence_mean,
            directional_agreement_mean=directional_agreement_mean,
            face_quality_mean=face_quality_mean,
            face_size_mean=face_size_mean,
            face_size_adequacy=face_size_adequacy,
            blur_adequacy=blur_adequacy,
            brightness_adequacy=brightness_adequacy,
            background_reaction_ms=float(temporal_signal_summary.get("background_reaction_ms") or 0.0),
            temporal_aggregation_ms=aggregation_elapsed_ms,
            **{
                key: value
                for key, value in temporal_signal_summary.items()
                if key not in {"supported_score", "background_reaction_ms"}
            },
        )

    @property
    def window_seconds(self) -> float:
        """Expose the configured rolling time window."""
        return self._window_seconds

    @property
    def max_entries(self) -> int:
        """Expose the maximum retained entries inside the time window."""
        return self._max_entries

    def get_recent_entries(self, now: Optional[float] = None) -> list[FrameMetrics]:
        """Return the current entries within the configured time window."""
        self._evict_old_entries(reference_timestamp=now or time.time())
        return list(self._buffer)

    def _evict_old_entries(self, reference_timestamp: float) -> None:
        min_timestamp = reference_timestamp - self._window_seconds
        while self._buffer and self._buffer[0].timestamp < min_timestamp:
            self._buffer.popleft()
        while len(self._buffer) > self._max_entries:
            self._buffer.popleft()

    def _reset_long_face_loss_state(self, reference_timestamp: float) -> None:
        no_face_run_duration = _tail_no_face_run_duration(list(self._buffer))
        if no_face_run_duration < self._face_loss_reset_seconds:
            return
        self._background_reaction_evaluator.reset()
        self._baseline_calibrator.reset()
        self._ema_score = None


class LivenessPreviewFrameProcessor:
    """Thin adapter around the existing detector stack for ndarray frames."""

    def __init__(
        self,
        face_detector: IFaceDetector,
        liveness_detector: ILivenessDetector,
        settings: Settings,
        landmark_detector: Optional[ILandmarkDetector] = None,
    ) -> None:
        self._face_detector = face_detector
        self._liveness_detector = liveness_detector
        self._settings = settings
        self._landmark_detector = landmark_detector
        self._frame_index = 0
        self._cached_bounding_box: Optional[tuple[int, int, int, int]] = None
        self._cached_face_signal_metrics: Any = None
        self._cached_liveness_result: Optional[LivenessResult] = None
        self._last_successful_metrics: Optional[FrameMetrics] = None
        self._last_successful_frame_index = 0
        self._device_spoof_risk_evaluator = DeviceSpoofRiskEvaluator()

    def process_frame(self, frame: np.ndarray) -> FrameMetrics:
        """Synchronously process one frame via the async detector APIs."""
        self._frame_index += 1
        profiling: dict[str, float] = {}
        reused_face_detection = False
        reused_landmarks = False
        reused_liveness = False
        brightness = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
        inference_frame, inference_scale = self._resize_for_inference(frame)

        detection_started = time.perf_counter()
        bounding_box: Optional[tuple[int, int, int, int]]
        should_detect = (
            self._cached_bounding_box is None
            or self._frame_index == 1
            or (self._frame_index - 1) % self._settings.DEV_LIVENESS_PREVIEW_DETECT_EVERY_N_FRAMES == 0
        )
        try:
            if should_detect:
                detection = asyncio.run(self._face_detector.detect(inference_frame))
                if not detection.found or detection.bounding_box is None:
                    self._cached_bounding_box = None
                    self._cached_face_signal_metrics = None
                    self._cached_liveness_result = None
                    profiling["face_detection_ms"] = (time.perf_counter() - detection_started) * 1000.0
                    return self._error_metrics(
                        brightness=brightness,
                        blur_score=None,
                        face_detected=False,
                        error="No face detected",
                        profiling=profiling,
                        inference_scale=inference_scale,
                    )

                bounding_box = self._scale_bounding_box(detection.bounding_box, inference_scale, frame.shape)
                self._cached_bounding_box = bounding_box
            else:
                reused_face_detection = True
                bounding_box = self._cached_bounding_box
        except Exception as exc:
            self._cached_bounding_box = None
            self._cached_face_signal_metrics = None
            self._cached_liveness_result = None
            profiling["face_detection_ms"] = (time.perf_counter() - detection_started) * 1000.0
            return self._error_metrics(
                brightness=brightness,
                blur_score=None,
                face_detected=False,
                error=f"Face detection error: {exc}",
                profiling=profiling,
                inference_scale=inference_scale,
            )
        profiling["face_detection_ms"] = (time.perf_counter() - detection_started) * 1000.0

        if bounding_box is None:
            self._cached_face_signal_metrics = None
            self._cached_liveness_result = None
            return self._error_metrics(
                brightness=brightness,
                blur_score=None,
                face_detected=False,
                error="No face detected",
                profiling=profiling,
                inference_scale=inference_scale,
            )

        face_region = self._crop_face_region(frame, bounding_box)
        if face_region.size == 0:
            self._cached_bounding_box = None
            self._cached_face_signal_metrics = None
            self._cached_liveness_result = None
            return self._error_metrics(
                brightness=brightness,
                blur_score=None,
                face_detected=False,
                error="No face detected",
                profiling=profiling,
                inference_scale=inference_scale,
            )

        blur_started = time.perf_counter()
        blur_score = self._compute_blur(face_region)
        profiling["blur_ms"] = (time.perf_counter() - blur_started) * 1000.0
        face_region_brightness = float(np.mean(cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)))
        _, _, face_width, face_height = bounding_box
        frame_height, frame_width = frame.shape[:2]
        face_size_ratio = (face_width * face_height) / max(frame_width * frame_height, 1)
        landmark_started = time.perf_counter()
        should_extract_landmarks = (
            self._cached_face_signal_metrics is None
            or self._frame_index == 1
            or (self._frame_index - 1) % self._settings.DEV_LIVENESS_PREVIEW_LANDMARK_EVERY_N_FRAMES == 0
        )
        if should_extract_landmarks:
            face_signal_metrics = extract_face_signal_metrics(
                face_region_bgr=face_region,
                landmark_detector=self._landmark_detector,
                face_quality=None,
                blur_score=blur_score,
                brightness=face_region_brightness,
            )
            self._cached_face_signal_metrics = face_signal_metrics
        else:
            reused_landmarks = True
            face_signal_metrics = self._cached_face_signal_metrics
        profiling["landmark_ms"] = (time.perf_counter() - landmark_started) * 1000.0

        liveness_started = time.perf_counter()
        should_run_liveness = (
            self._cached_liveness_result is None
            or self._frame_index == 1
            or (self._frame_index - 1) % self._settings.DEV_LIVENESS_PREVIEW_LIVENESS_EVERY_N_FRAMES == 0
        )
        try:
            if should_run_liveness:
                liveness_result = asyncio.run(self._liveness_detector.check_liveness(face_region))
                self._cached_liveness_result = liveness_result
            else:
                reused_liveness = True
                liveness_result = self._cached_liveness_result
        except FaceNotDetectedError:
            self._cached_bounding_box = None
            self._cached_face_signal_metrics = None
            self._cached_liveness_result = None
            profiling["liveness_ms"] = (time.perf_counter() - liveness_started) * 1000.0
            return self._error_metrics(
                brightness=face_region_brightness,
                blur_score=blur_score,
                face_detected=False,
                error="No face detected in cropped region",
                profiling=profiling,
                inference_scale=inference_scale,
            )
        except LivenessCheckError as exc:
            self._cached_liveness_result = None
            profiling["liveness_ms"] = (time.perf_counter() - liveness_started) * 1000.0
            return self._error_metrics(
                brightness=face_region_brightness,
                blur_score=blur_score,
                face_detected=True,
                error=str(exc),
                profiling=profiling,
                inference_scale=inference_scale,
            )
        except Exception as exc:
            self._cached_liveness_result = None
            profiling["liveness_ms"] = (time.perf_counter() - liveness_started) * 1000.0
            return self._error_metrics(
                brightness=face_region_brightness,
                blur_score=blur_score,
                face_detected=True,
                error=f"Liveness error: {exc}",
                profiling=profiling,
                inference_scale=inference_scale,
            )
        profiling["liveness_ms"] = (time.perf_counter() - liveness_started) * 1000.0

        metrics = self._build_metrics(
            frame=frame,
            face_region=face_region,
            result=liveness_result,
            brightness=face_region_brightness,
            blur_score=blur_score,
            face_signal_metrics=face_signal_metrics,
            face_size_ratio=face_size_ratio,
            profiling=profiling,
            reused_face_detection=reused_face_detection,
            reused_landmarks=reused_landmarks,
            reused_liveness=reused_liveness,
            inference_scale=inference_scale,
        )
        self._last_successful_metrics = metrics
        self._last_successful_frame_index = self._frame_index
        return metrics

    def enrich_device_spoof_with_history(
        self,
        metrics: FrameMetrics,
        recent_entries: list[FrameMetrics],
    ) -> FrameMetrics:
        """Update temporal spoof metrics using the existing preview frame window."""
        if metrics.device_spoof is None:
            return metrics

        temporal_signal_history: list[dict[str, float]] = []
        for entry in [*recent_entries, metrics]:
            sample = self._device_spoof_risk_evaluator.temporal_signal_sample_from_details(entry.details)
            if sample is not None:
                temporal_signal_history.append(sample)

        updated_device_spoof = self._device_spoof_risk_evaluator.update_with_temporal_history(
            metrics.device_spoof,
            temporal_signal_history,
        )
        updated_details = dict(metrics.details)
        updated_details.update(updated_device_spoof.details)
        updated_details.update(updated_device_spoof.to_dict())
        return replace(
            metrics,
            details=updated_details,
            device_spoof=updated_device_spoof,
        )

    def _resize_for_inference(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        max_side = self._settings.DEV_LIVENESS_PREVIEW_INFERENCE_MAX_SIDE
        if max_side <= 0:
            return frame, 1.0
        height, width = frame.shape[:2]
        current_max_side = max(height, width)
        if current_max_side <= max_side:
            return frame, 1.0
        scale = max_side / float(current_max_side)
        resized = cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        return resized, scale

    @staticmethod
    def _scale_bounding_box(
        bounding_box: tuple[int, int, int, int],
        inference_scale: float,
        frame_shape: tuple[int, ...],
    ) -> tuple[int, int, int, int]:
        if abs(inference_scale - 1.0) <= 1e-6:
            return LivenessPreviewFrameProcessor._clamp_bounding_box(bounding_box, frame_shape)
        x, y, width, height = bounding_box
        scaled = (
            int(round(x / inference_scale)),
            int(round(y / inference_scale)),
            int(round(width / inference_scale)),
            int(round(height / inference_scale)),
        )
        return LivenessPreviewFrameProcessor._clamp_bounding_box(scaled, frame_shape)

    @staticmethod
    def _clamp_bounding_box(
        bounding_box: tuple[int, int, int, int],
        frame_shape: tuple[int, ...],
    ) -> tuple[int, int, int, int]:
        frame_height, frame_width = frame_shape[:2]
        x, y, width, height = bounding_box
        x = max(0, min(x, frame_width - 1))
        y = max(0, min(y, frame_height - 1))
        width = max(1, min(width, frame_width - x))
        height = max(1, min(height, frame_height - y))
        return (x, y, width, height)

    @staticmethod
    def _crop_face_region(frame: np.ndarray, bounding_box: tuple[int, int, int, int]) -> np.ndarray:
        x, y, width, height = bounding_box
        return frame[y : y + height, x : x + width]

    @staticmethod
    def _compute_blur(face_region: np.ndarray) -> float:
        gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _error_metrics(
        self,
        *,
        brightness: float,
        blur_score: Optional[float],
        face_detected: bool,
        error: str,
        profiling: Optional[dict[str, float]] = None,
        inference_scale: float = 1.0,
    ) -> FrameMetrics:
        if self._should_hold_last_success(error):
            return self._hold_last_success(
                error=error,
                profiling=profiling,
                inference_scale=inference_scale,
            )
        return FrameMetrics(
            timestamp=time.time(),
            face_detected=face_detected,
            is_live=False,
            raw_score=0.0,
            confidence=0.0,
            passive_score=0.0,
            active_score=0.0,
            active_evidence=None,
            directional_agreement=None,
            face_quality=None,
            face_size_ratio=None,
            blur_score=blur_score,
            brightness=brightness,
            ear_current=None,
            mar_current=None,
            yaw_current=None,
            pitch_current=None,
            roll_current=None,
            landmark_model=None,
            background_active_mode="error" if face_detected else "no_face",
            background_active_detected=False,
            device_spoof=None,
            details={},
            error=error,
            profiling=profiling or {},
            inference_scale=inference_scale,
        )

    def _should_hold_last_success(self, error: str) -> bool:
        if self._last_successful_metrics is None:
            return False
        hold_frames = self._settings.DEV_LIVENESS_PREVIEW_HOLD_LAST_SUCCESS_FRAMES
        if hold_frames <= 0:
            return False
        frames_since_success = self._frame_index - self._last_successful_frame_index
        if frames_since_success > hold_frames:
            return False
        lowered_error = error.lower()
        return "no face detected" in lowered_error or "circuit breaker" in lowered_error

    def _hold_last_success(
        self,
        *,
        error: str,
        profiling: Optional[dict[str, float]],
        inference_scale: float,
    ) -> FrameMetrics:
        assert self._last_successful_metrics is not None
        previous = self._last_successful_metrics
        details = dict(previous.details)
        details["preview_hold_last_success"] = True
        details["preview_hold_error"] = error
        return FrameMetrics(
            timestamp=time.time(),
            face_detected=True,
            is_live=previous.is_live,
            raw_score=previous.raw_score,
            confidence=previous.confidence,
            passive_score=previous.passive_score,
            active_score=previous.active_score,
            active_evidence=previous.active_evidence,
            directional_agreement=previous.directional_agreement,
            face_quality=previous.face_quality,
            face_size_ratio=previous.face_size_ratio,
            blur_score=previous.blur_score,
            brightness=previous.brightness,
            ear_current=previous.ear_current,
            mar_current=previous.mar_current,
            yaw_current=previous.yaw_current,
            pitch_current=previous.pitch_current,
            roll_current=previous.roll_current,
            landmark_model=previous.landmark_model,
            background_active_mode=previous.background_active_mode,
            background_active_detected=previous.background_active_detected,
            device_spoof=previous.device_spoof,
            details=details,
            error=f"{error} (holding last success)",
            profiling=profiling or {},
            reused_face_detection=True,
            reused_landmarks=True,
            reused_liveness=True,
            held_from_previous=True,
            inference_scale=inference_scale,
        )

    def _build_metrics(
        self,
        *,
        frame: np.ndarray,
        face_region: np.ndarray,
        result: LivenessResult,
        brightness: float,
        blur_score: float,
        face_signal_metrics,
        face_size_ratio: Optional[float],
        profiling: Optional[dict[str, float]] = None,
        reused_face_detection: bool = False,
        reused_landmarks: bool = False,
        reused_liveness: bool = False,
        inference_scale: float = 1.0,
    ) -> FrameMetrics:
        details = dict(result.details)
        face_quality = _coalesce_float(_maybe_float(details.get("face_quality")), face_signal_metrics.face_quality)
        ear_current = _coalesce_float(_maybe_float(details.get("ear_current")), face_signal_metrics.ear_current)
        mar_current = _coalesce_float(_maybe_float(details.get("mar_current")), face_signal_metrics.mar_current)
        yaw_current = _coalesce_float(_maybe_float(details.get("yaw_current")), face_signal_metrics.yaw_current)
        pitch_current = _coalesce_float(_maybe_float(details.get("pitch_current")), face_signal_metrics.pitch_current)
        roll_current = _coalesce_float(_maybe_float(details.get("roll_current")), face_signal_metrics.roll_current)
        detector_active_score = float(details.get("active_score") or 0.0)
        detector_active_evidence = _maybe_float(details.get("active_evidence"))
        frame_active_evidence = self._compute_preview_frame_active_evidence(
            details=details,
            face_quality=face_quality,
            face_size_ratio=face_size_ratio,
            ear_current=ear_current,
            mar_current=mar_current,
            yaw_current=yaw_current,
        )
        frame_active_score = min(100.0, max(0.0, 100.0 * float(np.sqrt(max(frame_active_evidence, 0.0)))))
        details["detector_active_score"] = detector_active_score
        details["detector_active_evidence"] = detector_active_evidence
        details["preview_frame_active_score"] = frame_active_score
        details["preview_frame_active_evidence"] = frame_active_evidence
        device_spoof = self._device_spoof_risk_evaluator.evaluate(
            frame_bgr=frame,
            face_region_bgr=face_region,
        )
        details.update(device_spoof.to_dict())
        return FrameMetrics(
            timestamp=time.time(),
            face_detected=True,
            is_live=result.is_live,
            raw_score=result.score,
            confidence=result.confidence,
            passive_score=float(details.get("passive_score") or 0.0),
            active_score=frame_active_score,
            active_evidence=frame_active_evidence,
            directional_agreement=_maybe_float(details.get("directional_agreement")),
            face_quality=face_quality,
            face_size_ratio=face_size_ratio,
            blur_score=blur_score,
            brightness=brightness,
            ear_current=ear_current,
            mar_current=mar_current,
            yaw_current=yaw_current,
            pitch_current=pitch_current,
            roll_current=roll_current,
            landmark_model=details.get("landmark_model") or face_signal_metrics.landmark_model,
            background_active_mode=details.get("background_active_mode") or result.challenge,
            background_active_detected=bool(
                details.get("background_active_reaction_detected")
                if details.get("background_active_reaction_detected") is not None
                else result.challenge_completed
            ),
            device_spoof=device_spoof,
            details=details,
            error=None,
            profiling=profiling or {},
            reused_face_detection=reused_face_detection,
            reused_landmarks=reused_landmarks,
            reused_liveness=reused_liveness,
            held_from_previous=False,
            inference_scale=inference_scale,
        )

    def _compute_preview_frame_active_evidence(
        self,
        *,
        details: dict[str, Any],
        face_quality: Optional[float],
        face_size_ratio: Optional[float],
        ear_current: Optional[float],
        mar_current: Optional[float],
        yaw_current: Optional[float],
    ) -> float:
        blink_score = _maybe_float(details.get("blink"))
        smile_score = _maybe_float(details.get("smile"))
        mar_baseline = _maybe_float(details.get("mar_baseline"))
        yaw_baseline = _maybe_float(details.get("yaw_baseline"))

        blink_support = _clamp01((blink_score - 70.0) / 22.0) if blink_score is not None else 0.0
        smile_support = _clamp01((smile_score - 58.0) / 26.0) if smile_score is not None else 0.0

        mouth_support = 0.0
        if mar_current is not None:
            if mar_baseline is not None and mar_baseline > 1e-6:
                mouth_support = _clamp01((mar_current / mar_baseline - 1.18) / 0.50)
            else:
                mouth_support = _clamp01((mar_current - 0.36) / 0.22)

        head_support = 0.0
        if yaw_current is not None:
            yaw_delta = abs(yaw_current - (yaw_baseline or 0.0))
            head_support = _clamp01((yaw_delta - 7.0) / 11.0)

        ranked = sorted(
            [blink_support, smile_support, mouth_support, head_support],
            reverse=True,
        )
        primary = ranked[0] if ranked else 0.0
        secondary = ranked[1] if len(ranked) > 1 else 0.0
        raw_frame_evidence = _clamp01(0.70 * primary + 0.30 * secondary)

        size_trust = _clamp01((face_size_ratio or 0.0) / max(self._settings.DEV_LIVENESS_PREVIEW_MIN_TRUSTED_FACE_SIZE_RATIO, 1e-6))
        quality_trust = _clamp01(face_quality or 0.0)
        effective_trust = _clamp01(0.70 + 0.20 * size_trust + 0.10 * quality_trust)
        return _clamp01(raw_frame_evidence * effective_trust)


class LiveLivenessPreview:
    """Webcam preview window for observing frame and temporal liveness metrics."""

    WINDOW_NAME = "Dev Liveness Preview"
    OVERLAY_FONT_SCALE = 0.43
    OVERLAY_LINE_HEIGHT = 18
    OVERLAY_TEXT_THICKNESS = 1
    def __init__(
        self,
        *,
        settings: Settings,
        frame_processor: LivenessPreviewFrameProcessor,
        temporal_aggregator: TemporalLivenessAggregator,
    ) -> None:
        self._settings = settings
        self._frame_processor = frame_processor
        self._temporal_aggregator = temporal_aggregator
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Launch the preview loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.debug("Dev liveness preview already running")
            return

        self._thread = threading.Thread(
            target=self.run,
            name="dev-liveness-preview",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the preview thread to stop."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def run(self) -> None:
        """Open the webcam and continuously render preview overlays."""
        logger.info(
            "Starting dev liveness preview: camera_index=%s window_seconds=%.2f max_entries=%s ema_alpha=%.2f infer_max_side=%s detect_every=%s landmark_every=%s liveness_every=%s",
            self._settings.DEV_LIVENESS_PREVIEW_CAMERA_INDEX,
            self._temporal_aggregator.window_seconds,
            self._temporal_aggregator.max_entries,
            self._settings.DEV_LIVENESS_PREVIEW_EMA_ALPHA,
            self._settings.DEV_LIVENESS_PREVIEW_INFERENCE_MAX_SIDE,
            self._settings.DEV_LIVENESS_PREVIEW_DETECT_EVERY_N_FRAMES,
            self._settings.DEV_LIVENESS_PREVIEW_LANDMARK_EVERY_N_FRAMES,
            self._settings.DEV_LIVENESS_PREVIEW_LIVENESS_EVERY_N_FRAMES,
        )
        capture = cv2.VideoCapture(self._settings.DEV_LIVENESS_PREVIEW_CAMERA_INDEX)
        if not capture.isOpened():
            logger.warning("Dev liveness preview could not open webcam %s", self._settings.DEV_LIVENESS_PREVIEW_CAMERA_INDEX)
            return

        cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_NORMAL)

        frame_count = 0
        last_frame_started = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                capture_started = time.perf_counter()
                ok, frame = capture.read()
                capture_ms = (time.perf_counter() - capture_started) * 1000.0
                if not ok or frame is None:
                    logger.warning("Dev liveness preview failed to read webcam frame")
                    break

                frame_started = time.perf_counter()
                display_fps = 1.0 / max(frame_started - last_frame_started, 1e-6)
                last_frame_started = frame_started

                inference_started = time.perf_counter()
                frame_metrics = self._frame_processor.process_frame(frame)
                recent_entries = self._temporal_aggregator.get_recent_entries(now=frame_metrics.timestamp)
                frame_metrics = self._frame_processor.enrich_device_spoof_with_history(frame_metrics, recent_entries)
                aggregate = self._temporal_aggregator.add(frame_metrics)
                inference_elapsed = time.perf_counter() - inference_started
                inference_fps = 1.0 / max(inference_elapsed, 1e-6)
                overlay_started = time.perf_counter()
                overlay = self._render_overlay(frame, frame_metrics, aggregate, display_fps, inference_fps)
                overlay_ms = (time.perf_counter() - overlay_started) * 1000.0
                cv2.imshow(self.WINDOW_NAME, overlay)

                if self._window_closed():
                    break

                frame_count += 1
                self._maybe_log_frame(
                    frame_count,
                    frame_metrics,
                    aggregate,
                    display_fps=display_fps,
                    inference_fps=inference_fps,
                    capture_ms=capture_ms,
                    overlay_ms=overlay_ms,
                )

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27) or self._window_closed():
                    break
        finally:
            capture.release()
            try:
                cv2.destroyWindow(self.WINDOW_NAME)
            except cv2.error:
                pass
            logger.info("Dev liveness preview stopped")

    def _maybe_log_frame(
        self,
        frame_count: int,
        frame_metrics: FrameMetrics,
        aggregate: AggregatedMetrics,
        *,
        display_fps: float,
        inference_fps: float,
        capture_ms: float,
        overlay_ms: float,
    ) -> None:
        cadence = self._settings.DEV_LIVENESS_PREVIEW_LOG_EVERY_N_FRAMES
        if cadence <= 0 or frame_count % cadence != 0:
            return

        logger.info(
            "dev_liveness_preview frame=%s raw=%.1f smooth=%.1f active_support=%.2f active_score=%.1f conf=%.2f stable_live=%.2f display_fps=%.1f inference_fps=%.1f capture_ms=%.1f detect_ms=%.1f landmark_ms=%.1f liveness_ms=%.1f bg_ms=%.1f agg_ms=%.1f overlay_ms=%.1f reuse=det:%s lm:%s liv:%s scale=%.2f face=%s error=%s",
            frame_count,
            frame_metrics.raw_score,
            aggregate.smoothed_score,
            aggregate.combined_active_evidence,
            aggregate.combined_active_score,
            aggregate.window_confidence,
            aggregate.stable_live_ratio,
            display_fps,
            inference_fps,
            capture_ms,
            frame_metrics.profiling.get("face_detection_ms", 0.0),
            frame_metrics.profiling.get("landmark_ms", 0.0),
            frame_metrics.profiling.get("liveness_ms", 0.0),
            aggregate.background_reaction_ms,
            aggregate.temporal_aggregation_ms,
            overlay_ms,
            frame_metrics.reused_face_detection,
            frame_metrics.reused_landmarks,
            frame_metrics.reused_liveness,
            frame_metrics.inference_scale,
            frame_metrics.face_detected,
            frame_metrics.error,
        )
        logger.info(
            "dev_liveness_preview metrics %s",
            " | ".join(
                [
                    f"status={aggregate.decision_state}",
                    f"frame_score={frame_metrics.raw_score:.1f}",
                    f"smoothed={aggregate.smoothed_score:.1f}",
                    f"frame_conf={frame_metrics.frame_confidence:.2f}",
                    f"window_conf={aggregate.window_confidence:.2f}",
                    f"passive={frame_metrics.passive_score:.1f}",
                    f"passive_win={aggregate.passive_window_score:.1f}",
                    f"frame_active={frame_metrics.active_score:.1f}",
                    f"frame_active_ev={_format_optional(frame_metrics.active_evidence)}",
                    f"detector_active={_format_optional(_maybe_float(frame_metrics.details.get('detector_active_score')))}",
                    f"detector_active_ev={_format_optional(_maybe_float(frame_metrics.details.get('detector_active_evidence')))}",
                    f"bg_active_raw={_format_optional(aggregate.raw_active_evidence)}",
                    f"bg_active_temp={_format_optional(aggregate.combined_active_evidence)}",
                    f"moire={_format_optional(_device_spoof_value(frame_metrics, 'moire_risk'))}",
                    f"reflection={_format_optional(_device_spoof_value(frame_metrics, 'reflection_risk'))}",
                    f"flicker={_format_optional(_device_spoof_value(frame_metrics, 'flicker_risk'))}",
                    f"device_replay={_format_optional(_device_spoof_value(frame_metrics, 'device_replay_risk'))}",
                    f"face={int(frame_metrics.face_detected)}",
                    f"face_quality={_format_optional(frame_metrics.face_quality)}",
                    f"face_size={_format_optional(frame_metrics.face_size_ratio)}",
                    f"brightness={frame_metrics.brightness:.1f}",
                    f"blur={_format_optional(frame_metrics.blur_score)}",
                    f"ear={_format_optional(frame_metrics.ear_current)}",
                    f"mar={_format_optional(frame_metrics.mar_current)}",
                    f"yaw={_format_optional(frame_metrics.yaw_current)}",
                    f"pitch={_format_optional(frame_metrics.pitch_current)}",
                    f"roll={_format_optional(frame_metrics.roll_current)}",
                    f"baseline={'ready' if aggregate.baseline_ready else 'calibrating'}",
                    f"baseline_n={aggregate.baseline_sample_count}",
                    f"ear_base={_format_optional(aggregate.ear_baseline)}",
                    f"mar_base={_format_optional(aggregate.mar_baseline)}",
                    f"smile_base={_format_optional(aggregate.smile_baseline)}",
                    f"yaw_base={_format_optional(aggregate.yaw_baseline)}",
                    f"ear_drop={_format_optional(aggregate.ear_drop_ratio)}",
                    f"mar_rise={_format_optional(aggregate.mar_rise_ratio)}",
                    f"blink_ev={_format_optional(aggregate.blink_evidence)}",
                    f"smile_ev={_format_optional(aggregate.smile_evidence)}",
                    f"mouth_ev={_format_optional(aggregate.mouth_open_evidence)}",
                    f"turn_left_ev={_format_optional(aggregate.head_turn_left_evidence)}",
                    f"turn_right_ev={_format_optional(aggregate.head_turn_right_evidence)}",
                    f"primary={aggregate.primary_event:.2f}",
                    f"secondary={aggregate.secondary_event:.2f}",
                    f"raw_react={aggregate.raw_reaction_evidence:.2f}",
                    f"trust={aggregate.effective_trust:.2f}",
                    f"trusted_react={aggregate.trusted_reaction_evidence:.2f}",
                    f"persist1={aggregate.persisted_primary:.2f}",
                    f"persist2={aggregate.persisted_secondary:.2f}",
                    f"persist_react={aggregate.persisted_reaction_evidence:.2f}",
                    f"variance={aggregate.score_variance:.2f}",
                    f"score_mean={aggregate.score_mean:.1f}",
                    f"ema={aggregate.ema_score:.1f}",
                    f"temp_consistency={aggregate.temporal_consistency:.2f}",
                    f"dir_agreement={_format_optional(frame_metrics.directional_agreement)}",
                    f"dir_agreement_mean={aggregate.directional_agreement_mean:.2f}",
                    f"face_quality_mean={aggregate.face_quality_mean:.2f}",
                    f"face_size_mean={aggregate.face_size_mean:.3f}",
                    f"face_size_adequacy={aggregate.face_size_adequacy:.2f}",
                    f"blur_adequacy={aggregate.blur_adequacy:.2f}",
                    f"brightness_adequacy={aggregate.brightness_adequacy:.2f}",
                    f"stable_live={aggregate.stable_live_ratio:.2f}",
                    f"face_ratio={aggregate.face_present_ratio:.2f}",
                    f"no_face={aggregate.consecutive_no_face_frames}",
                    f"recovery={'warm' if aggregate.warm_recovery else 'normal'}",
                    f"evidence={'sufficient' if aggregate.sufficient_evidence else 'pending'}",
                    f"quality_state={'low' if aggregate.low_quality else 'ok'}",
                    f"bg_mode={frame_metrics.background_active_mode}",
                    f"bg_detect={int(frame_metrics.background_active_detected)}",
                    f"error={frame_metrics.error or '-'}",
                ]
            ),
        )

    def _window_closed(self) -> bool:
        """Return True when the preview window has been closed by the user."""
        try:
            visible = cv2.getWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_VISIBLE)
            autosize = cv2.getWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_AUTOSIZE)
            aspect_ratio = cv2.getWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_ASPECT_RATIO)
            return visible < 1 or autosize < 0 or aspect_ratio < 0
        except cv2.error:
            return True

    def _render_overlay(
        self,
        frame: np.ndarray,
        frame_metrics: FrameMetrics,
        aggregate: AggregatedMetrics,
        display_fps: float,
        inference_fps: float,
    ) -> np.ndarray:
        overlay = frame.copy()
        status_color = _status_color(frame_metrics, aggregate)
        status_text = _status_text(frame_metrics, aggregate)
        lines = [
            ("STATUS", status_text),
            ("Frame score", f"{frame_metrics.raw_score:5.1f}"),
            ("Smoothed", f"{aggregate.smoothed_score:5.1f}"),
            ("Frame conf.", f"{frame_metrics.frame_confidence:0.2f}"),
            ("Window conf.", f"{aggregate.window_confidence:0.2f}"),
            ("Decision", aggregate.decision_state),
            ("Passive", f"{frame_metrics.passive_score:5.1f} / win {aggregate.passive_window_score:5.1f}"),
            ("Frame active", f"{frame_metrics.active_score:5.1f}"),
            ("BG active temp", f"{aggregate.combined_active_score:5.1f}"),
            ("Device replay", _format_optional(_device_spoof_value(frame_metrics, "device_replay_risk"))),
            ("Face", "YES" if frame_metrics.face_detected else "NO"),
            ("Window", f"{aggregate.window_seconds:0.1f}s / {aggregate.sample_count} samples"),
            ("FPS", f"{display_fps:0.1f} / inf {inference_fps:0.1f}"),
        ]

        if self._settings.DEV_LIVENESS_PREVIEW_SHOW_DEBUG:
            lines.extend(
                [
                    ("Moire risk", _format_optional(_device_spoof_value(frame_metrics, "moire_risk"))),
                    ("Reflection risk", _format_optional(_device_spoof_value(frame_metrics, "reflection_risk"))),
                    ("Flicker risk", _format_optional(_device_spoof_value(frame_metrics, "flicker_risk"))),
                    ("Device replay", _format_optional(_device_spoof_value(frame_metrics, "device_replay_risk"))),
                    ("--- Liveness Debug ---", ""),
                    ("Frame active ev.", _format_optional(frame_metrics.active_evidence)),
                    ("Detector active", _format_optional(_maybe_float(frame_metrics.details.get("detector_active_score")))),
                    ("Detector act ev.", _format_optional(_maybe_float(frame_metrics.details.get("detector_active_evidence")))),
                    ("BG active raw", _format_optional(aggregate.raw_active_evidence)),
                    ("BG active temp", _format_optional(aggregate.combined_active_evidence)),
                    ("Frame conf. mean", f"{aggregate.frame_confidence_mean:0.2f}"),
                    ("Directional agr.", _format_optional(frame_metrics.directional_agreement)),
                    ("Face quality", _format_optional(frame_metrics.face_quality)),
                    ("Face size", _format_optional(frame_metrics.face_size_ratio)),
                    ("Blur", _format_optional(frame_metrics.blur_score)),
                    ("Brightness", f"{frame_metrics.brightness:0.1f}"),
                    ("EAR", _format_optional(frame_metrics.ear_current)),
                    ("MAR", _format_optional(frame_metrics.mar_current)),
                    ("Yaw", _format_optional(frame_metrics.yaw_current)),
                    ("Pitch", _format_optional(frame_metrics.pitch_current)),
                    ("Roll", _format_optional(frame_metrics.roll_current)),
                    ("Baseline", f"{'READY' if aggregate.baseline_ready else 'CALIBRATING'} ({aggregate.baseline_sample_count})"),
                    ("EAR base", _format_optional(aggregate.ear_baseline)),
                    ("MAR base", _format_optional(aggregate.mar_baseline)),
                    ("Smile base", _format_optional(aggregate.smile_baseline)),
                    ("Yaw base", _format_optional(aggregate.yaw_baseline)),
                    ("EAR drop", _format_optional(aggregate.ear_drop_ratio)),
                    ("MAR rise", _format_optional(aggregate.mar_rise_ratio)),
                    ("EMA raw", f"{aggregate.ema_score:0.1f}"),
                    ("Blink ev.", _format_optional(aggregate.blink_evidence)),
                    ("Smile ev.", _format_optional(aggregate.smile_evidence)),
                    ("Mouth ev.", _format_optional(aggregate.mouth_open_evidence)),
                    ("Turn L/R ev.", f"{_format_optional(aggregate.head_turn_left_evidence)} / {_format_optional(aggregate.head_turn_right_evidence)}"),
                    ("Primary/2nd", f"{aggregate.primary_event:0.2f} / {aggregate.secondary_event:0.2f}"),
                    ("Raw react", f"{aggregate.raw_reaction_evidence:0.2f}"),
                    ("Eff trust", f"{aggregate.effective_trust:0.2f}"),
                    ("Trusted react", f"{aggregate.trusted_reaction_evidence:0.2f}"),
                    ("Persist 1/2", f"{aggregate.persisted_primary:0.2f} / {aggregate.persisted_secondary:0.2f}"),
                    ("Persist react", f"{aggregate.persisted_reaction_evidence:0.2f}"),
                    ("Variance", f"{aggregate.score_variance:0.2f}"),
                    ("Score mean", f"{aggregate.score_mean:0.1f}"),
                    ("Score EMA", f"{aggregate.ema_score:0.1f}"),
                    ("Temp consist.", f"{aggregate.temporal_consistency:0.2f}"),
                    ("Dir. agr mean", f"{aggregate.directional_agreement_mean:0.2f}"),
                    ("Face qual mean", f"{aggregate.face_quality_mean:0.2f}"),
                    ("Face size mean", f"{aggregate.face_size_mean:0.3f}"),
                    ("Face size adq.", f"{aggregate.face_size_adequacy:0.2f}"),
                    ("Blur adequacy", f"{aggregate.blur_adequacy:0.2f}"),
                    ("Bright adequacy", f"{aggregate.brightness_adequacy:0.2f}"),
                    ("Detect ms", f"{frame_metrics.profiling.get('face_detection_ms', 0.0):0.1f}"),
                    ("Landmark ms", f"{frame_metrics.profiling.get('landmark_ms', 0.0):0.1f}"),
                    ("Liveness ms", f"{frame_metrics.profiling.get('liveness_ms', 0.0):0.1f}"),
                    ("BG react ms", f"{aggregate.background_reaction_ms:0.1f}"),
                    ("Agg ms", f"{aggregate.temporal_aggregation_ms:0.1f}"),
                    ("Infer scale", f"{frame_metrics.inference_scale:0.2f}"),
                    ("Reuse", f"D{int(frame_metrics.reused_face_detection)} L{int(frame_metrics.reused_landmarks)} V{int(frame_metrics.reused_liveness)} H{int(frame_metrics.held_from_previous)}"),
                    ("Stable live", f"{aggregate.stable_live_ratio:0.2f}"),
                    ("Face ratio", f"{aggregate.face_present_ratio:0.2f} / no-face {aggregate.consecutive_no_face_frames}"),
                    ("Recovery", "WARM" if aggregate.warm_recovery else "NORMAL"),
                    ("Evidence", "SUFFICIENT" if aggregate.sufficient_evidence else "PENDING"),
                    ("Quality", "LOW" if aggregate.low_quality else "OK"),
                    ("BG mode", frame_metrics.background_active_mode),
                    ("BG detect", "YES" if frame_metrics.background_active_detected else "NO"),
                ]
            )

        panel_bottom = min(
            overlay.shape[0] - 6,
            10 + len(lines) * self.OVERLAY_LINE_HEIGHT + (30 if frame_metrics.error else 0),
        )
        cv2.rectangle(overlay, (6, 4), (540, panel_bottom), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.42, frame, 0.58, 0, overlay)

        y = 18
        for index, (label, value) in enumerate(lines):
            color = status_color if index == 0 else (0, 0, 0)
            if label.startswith("--- "):
                color = (40, 40, 40)
            cv2.putText(
                overlay,
                label if label.startswith("--- ") else f"{label}: {value}",
                (14, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.OVERLAY_FONT_SCALE,
                color,
                self.OVERLAY_TEXT_THICKNESS,
                cv2.LINE_AA,
            )
            y += self.OVERLAY_LINE_HEIGHT

        if frame_metrics.error:
            cv2.putText(
                overlay,
                frame_metrics.error.upper(),
                (14, y + 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        border_color = status_color
        cv2.rectangle(overlay, (0, 0), (overlay.shape[1] - 1, overlay.shape[0] - 1), border_color, 4)
        return overlay


def create_dev_liveness_preview(
    *,
    settings: Settings,
    face_detector: IFaceDetector,
    liveness_detector: ILivenessDetector,
    landmark_detector: Optional[ILandmarkDetector] = None,
) -> LiveLivenessPreview:
    """Construct a preview instance from existing detector components."""
    return LiveLivenessPreview(
        settings=settings,
        frame_processor=LivenessPreviewFrameProcessor(
            face_detector=face_detector,
            liveness_detector=liveness_detector,
            settings=settings,
            landmark_detector=landmark_detector,
        ),
        temporal_aggregator=TemporalLivenessAggregator(
            window_seconds=settings.DEV_LIVENESS_PREVIEW_WINDOW_SECONDS,
            baseline_seconds=settings.DEV_LIVENESS_PREVIEW_BASELINE_SECONDS,
            max_entries=settings.DEV_LIVENESS_PREVIEW_BUFFER_SIZE,
            ema_alpha=settings.DEV_LIVENESS_PREVIEW_EMA_ALPHA,
            no_face_consecutive_threshold=settings.DEV_LIVENESS_PREVIEW_NO_FACE_CONSECUTIVE_THRESHOLD,
            face_return_grace_seconds=settings.DEV_LIVENESS_PREVIEW_FACE_RETURN_GRACE_SECONDS,
            face_loss_reset_seconds=settings.DEV_LIVENESS_PREVIEW_FACE_LOSS_RESET_SECONDS,
            active_decay_seconds=settings.DEV_LIVENESS_PREVIEW_ACTIVE_DECAY_SECONDS,
            min_trusted_face_size_ratio=settings.DEV_LIVENESS_PREVIEW_MIN_TRUSTED_FACE_SIZE_RATIO,
        ),
    )


def _status_color(frame_metrics: FrameMetrics, aggregate: AggregatedMetrics) -> tuple[int, int, int]:
    state = aggregate.decision_state
    if state == "NO_FACE":
        return (0, 165, 255)
    if state == "LOW_QUALITY":
        return (0, 215, 255)
    if state == "INSUFFICIENT_EVIDENCE":
        return (0, 215, 255)
    if state == "LIKELY_LIVE":
        return (0, 200, 0)
    return (0, 0, 220)


def _status_text(frame_metrics: FrameMetrics, aggregate: AggregatedMetrics) -> str:
    return aggregate.decision_state


def _format_optional(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:0.2f}"


def _device_spoof_value(frame_metrics: FrameMetrics, field_name: str) -> Optional[float]:
    if frame_metrics.device_spoof is None:
        return None
    value = getattr(frame_metrics.device_spoof, field_name, None)
    return float(value) if value is not None else None


def _is_device_replay_spoof_detected(frame_metrics: FrameMetrics) -> bool:
    device_replay_risk = _device_spoof_value(frame_metrics, "device_replay_risk")
    reflection_risk = _device_spoof_value(frame_metrics, "reflection_risk") or 0.0
    flicker_risk = _device_spoof_value(frame_metrics, "flicker_risk") or 0.0

    if device_replay_risk is None:
        return False

    reflective_screen_replay = (
        device_replay_risk >= 0.78 and reflection_risk >= 0.55 and flicker_risk >= 0.60
    )
    flickering_screen_replay = (
        device_replay_risk >= 0.78 and reflection_risk >= 0.30 and flicker_risk >= 0.90
    )
    glossy_static_screen_replay = (
        device_replay_risk >= 0.80 and reflection_risk >= 0.94
    )
    return reflective_screen_replay or flickering_screen_replay or glossy_static_screen_replay


def _maybe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coalesce_float(primary: Optional[float], fallback: Optional[float]) -> Optional[float]:
    return primary if primary is not None else fallback


def _compute_temporal_signal_summary(
    entries: list[FrameMetrics],
    *,
    background_reaction_evaluator: Optional[BackgroundActiveReactionEvaluator] = None,
    passive_window_score: Optional[float] = None,
    session_baseline: Optional[SessionBaseline] = None,
) -> dict[str, Optional[float]]:
    ear_values = [entry.ear_current for entry in entries if entry.ear_current is not None]
    mar_values = [entry.mar_current for entry in entries if entry.mar_current is not None]
    yaw_values = [entry.yaw_current for entry in entries if entry.yaw_current is not None]
    pitch_values = [entry.pitch_current for entry in entries if entry.pitch_current is not None]
    roll_values = [entry.roll_current for entry in entries if entry.roll_current is not None]

    ear_baseline = session_baseline.ear_baseline if session_baseline else _first_available(entries, "ear_baseline")
    mar_baseline = session_baseline.mar_baseline if session_baseline else _first_available(entries, "mar_baseline")
    smile_baseline = session_baseline.smile_baseline if session_baseline else _first_available(entries, "smile_baseline")
    yaw_baseline = session_baseline.yaw_baseline if session_baseline else _first_available(entries, "yaw_baseline")
    pitch_baseline = session_baseline.pitch_baseline if session_baseline else _first_available(entries, "pitch_baseline")
    roll_baseline = session_baseline.roll_baseline if session_baseline else _first_available(entries, "roll_baseline")

    ear_mean = _mean(ear_values)
    ear_min = min(ear_values) if ear_values else None
    ear_max = max(ear_values) if ear_values else None
    ear_drop = (ear_max - ear_min) if ear_min is not None and ear_max is not None else None
    ear_drop_ratio = _ratio(ear_drop, ear_baseline or ear_max)

    mar_mean = _mean(mar_values)
    mar_min = min(mar_values) if mar_values else None
    mar_max = max(mar_values) if mar_values else None
    mar_rise = (mar_max - mar_min) if mar_min is not None and mar_max is not None else None
    mar_rise_ratio = _ratio(mar_rise, mar_baseline or mar_mean)

    yaw_mean = _mean(yaw_values)
    yaw_left_peak = max([-value for value in yaw_values if value < 0], default=None)
    yaw_right_peak = max([value for value in yaw_values if value > 0], default=None)
    pitch_mean = _mean(pitch_values)
    roll_mean = _mean(roll_values)

    reaction_summary = None
    background_reaction_ms = 0.0
    if background_reaction_evaluator is not None:
        reaction_started = time.perf_counter()
        reaction_summary = background_reaction_evaluator.evaluate(
            [
                ReactionSignalFrame(
                    timestamp=entry.timestamp,
                    face_detected=entry.face_detected,
                    active_score=entry.active_score,
                    active_evidence=entry.active_evidence,
                    ear_current=entry.ear_current,
                    mar_current=entry.mar_current,
                    yaw_current=entry.yaw_current,
                    pitch_current=entry.pitch_current,
                    roll_current=entry.roll_current,
                    face_quality=entry.face_quality,
                    face_size_ratio=entry.face_size_ratio,
                    smile_score=_maybe_float(entry.details.get("smile")),
                    blink_score=_maybe_float(entry.details.get("blink")),
                    ear_baseline=ear_baseline if ear_baseline is not None else _maybe_float(entry.details.get("ear_baseline")),
                    mar_baseline=mar_baseline if mar_baseline is not None else _maybe_float(entry.details.get("mar_baseline")),
                    smile_baseline=smile_baseline if smile_baseline is not None else _maybe_float(entry.details.get("smile_baseline")),
                    yaw_baseline=yaw_baseline if yaw_baseline is not None else _maybe_float(entry.details.get("yaw_baseline")),
                    pitch_baseline=pitch_baseline if pitch_baseline is not None else _maybe_float(entry.details.get("pitch_baseline")),
                    roll_baseline=roll_baseline if roll_baseline is not None else _maybe_float(entry.details.get("roll_baseline")),
                )
                for entry in entries
            ],
            passive_window_score=passive_window_score or 0.0,
        )
        background_reaction_ms = (time.perf_counter() - reaction_started) * 1000.0

    blink_evidence = reaction_summary.blink_evidence if reaction_summary else _clamp01(_ratio(ear_drop, (ear_baseline or ear_max or 0.0) * 0.35 if (ear_baseline or ear_max) else None))
    smile_evidence = reaction_summary.smile_evidence if reaction_summary else _clamp01(_ratio(mar_rise, (mar_baseline or mar_max or 0.0) * 0.45 if (mar_baseline or mar_max) else None))
    mouth_open_evidence = reaction_summary.mouth_open_evidence if reaction_summary else _clamp01(_ratio(mar_max, (mar_baseline or mar_mean or 0.0) * 1.7 if (mar_baseline or mar_mean) else None))
    head_turn_left_evidence = reaction_summary.head_turn_left_evidence if reaction_summary else _clamp01(_ratio(yaw_left_peak, 15.0))
    head_turn_right_evidence = reaction_summary.head_turn_right_evidence if reaction_summary else _clamp01(_ratio(yaw_right_peak, 15.0))
    primary_event = reaction_summary.primary_event if reaction_summary else 0.0
    secondary_event = reaction_summary.secondary_event if reaction_summary else 0.0
    raw_reaction_evidence = reaction_summary.raw_reaction_evidence if reaction_summary else 0.0
    effective_trust = reaction_summary.effective_trust if reaction_summary else 0.65
    trusted_reaction_evidence = reaction_summary.trusted_reaction_evidence if reaction_summary else 0.0
    persisted_primary = reaction_summary.persisted_primary if reaction_summary else 0.0
    persisted_secondary = reaction_summary.persisted_secondary if reaction_summary else 0.0
    persisted_reaction_evidence = reaction_summary.persisted_reaction_evidence if reaction_summary else 0.0
    combined_active_evidence = reaction_summary.combined_active_evidence if reaction_summary else 0.0
    combined_active_score = reaction_summary.combined_active_score if reaction_summary else 0.0
    raw_active_evidence = reaction_summary.raw_active_evidence if reaction_summary else 0.0
    passive_weight = reaction_summary.passive_weight if reaction_summary else 0.88
    active_weight = reaction_summary.active_weight if reaction_summary else 0.12
    passive_window_score = reaction_summary.passive_window_score if reaction_summary else (passive_window_score or 0.0)
    active_frame_score_mean = reaction_summary.active_frame_score_mean if reaction_summary else 0.0
    active_frame_evidence_mean = reaction_summary.active_frame_evidence_mean if reaction_summary else 0.0
    supported_score = (
        reaction_summary.supported_score
        if reaction_summary is not None
        else min(100.0, max(0.0, passive_window_score * passive_weight + combined_active_score * active_weight))
    )

    return {
        "supported_score": supported_score,
        "ear_mean": ear_mean,
        "ear_min": ear_min,
        "ear_max": ear_max,
        "ear_drop": ear_drop,
        "ear_drop_ratio": ear_drop_ratio,
        "mar_mean": mar_mean,
        "mar_max": mar_max,
        "mar_rise": mar_rise,
        "mar_rise_ratio": mar_rise_ratio,
        "yaw_mean": yaw_mean,
        "yaw_left_peak": yaw_left_peak,
        "yaw_right_peak": yaw_right_peak,
        "pitch_mean": pitch_mean,
        "roll_mean": roll_mean,
        "baseline_ready": session_baseline.calibrated if session_baseline else False,
        "baseline_sample_count": session_baseline.sample_count if session_baseline else 0,
        "baseline_duration_seconds": session_baseline.duration_seconds if session_baseline else 0.0,
        "ear_baseline": ear_baseline,
        "mar_baseline": mar_baseline,
        "smile_baseline": smile_baseline,
        "yaw_baseline": yaw_baseline,
        "pitch_baseline": pitch_baseline,
        "roll_baseline": roll_baseline,
        "blink_evidence": blink_evidence,
        "smile_evidence": smile_evidence,
        "mouth_open_evidence": mouth_open_evidence,
        "head_turn_left_evidence": head_turn_left_evidence,
        "head_turn_right_evidence": head_turn_right_evidence,
        "primary_event": primary_event,
        "secondary_event": secondary_event,
        "raw_reaction_evidence": raw_reaction_evidence,
        "effective_trust": effective_trust,
        "trusted_reaction_evidence": trusted_reaction_evidence,
        "persisted_primary": persisted_primary,
        "persisted_secondary": persisted_secondary,
        "persisted_reaction_evidence": persisted_reaction_evidence,
        "raw_active_evidence": raw_active_evidence,
        "combined_active_evidence": combined_active_evidence,
        "combined_active_score": combined_active_score,
        "passive_window_score": passive_window_score,
        "active_frame_score_mean": active_frame_score_mean,
        "active_frame_evidence_mean": active_frame_evidence_mean,
        "background_reaction_ms": background_reaction_ms,
    }


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return float(np.mean(values))


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or abs(denominator) <= 1e-6:
        return None
    return float(numerator / denominator)


def _clamp01(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _count_consecutive_no_face(entries: list[FrameMetrics]) -> int:
    count = 0
    for entry in reversed(entries):
        if entry.face_detected or entry.held_from_previous:
            break
        count += 1
    return count


def _tail_no_face_run_duration(entries: list[FrameMetrics]) -> float:
    no_face_tail: list[FrameMetrics] = []
    for entry in reversed(entries):
        if entry.face_detected or entry.held_from_previous:
            break
        no_face_tail.append(entry)
    if len(no_face_tail) < 2:
        return 0.0
    return max(0.0, no_face_tail[0].timestamp - no_face_tail[-1].timestamp)


def _effective_entries_for_analysis(
    entries: list[FrameMetrics],
    *,
    face_return_grace_seconds: float,
) -> list[FrameMetrics]:
    if not entries or not entries[-1].face_detected:
        return entries

    tail_count = 0
    for entry in reversed(entries[:-1]):
        if entry.face_detected or entry.held_from_previous:
            break
        tail_count += 1
    if tail_count <= 0:
        return entries

    no_face_start = len(entries) - 1 - tail_count
    no_face_run = entries[no_face_start:-1]
    if len(no_face_run) < 1:
        return entries

    no_face_duration = max(0.0, entries[-1].timestamp - no_face_run[0].timestamp)
    if no_face_duration > face_return_grace_seconds:
        return entries

    return entries[:no_face_start] + [entries[-1]]


def _is_low_quality(frame_metrics: FrameMetrics) -> bool:
    if not frame_metrics.face_detected:
        return False
    if frame_metrics.face_size_ratio is not None and frame_metrics.face_size_ratio < 0.08:
        return True
    if frame_metrics.face_quality is not None and frame_metrics.face_quality < 0.45:
        return True
    if frame_metrics.blur_score is not None and frame_metrics.blur_score < 25.0:
        return True
    if not 45.0 <= frame_metrics.brightness <= 215.0:
        return True
    return False


def _is_warm_recovery_candidate(
    *,
    recent_entries: list[FrameMetrics],
    current_frame: FrameMetrics,
    face_return_grace_seconds: float,
) -> bool:
    if not current_frame.face_detected or len(recent_entries) < 2:
        return False

    tail_no_face: list[FrameMetrics] = []
    for entry in reversed(recent_entries[:-1]):
        if entry.face_detected or entry.held_from_previous:
            break
        tail_no_face.append(entry)

    if not tail_no_face:
        return False

    no_face_duration = max(0.0, current_frame.timestamp - tail_no_face[-1].timestamp)
    if no_face_duration > face_return_grace_seconds:
        return False

    prior_valid_faces = sum(
        1 for entry in recent_entries[: len(recent_entries) - 1 - len(tail_no_face)]
        if entry.face_detected
    )
    return prior_valid_faces >= 2


def _has_sufficient_evidence(
    *,
    recent_entries: list[FrameMetrics],
    temporal_signal_summary: dict[str, Optional[float]],
    current_frame: FrameMetrics,
    min_trusted_face_size_ratio: float,
    warm_recovery: bool,
) -> bool:
    minimum_samples = 2 if warm_recovery else 6
    if len(recent_entries) < minimum_samples:
        return False
    if not current_frame.face_detected:
        return False
    if current_frame.face_size_ratio is not None and current_frame.face_size_ratio < min_trusted_face_size_ratio:
        return False
    baseline_ready = bool(temporal_signal_summary.get("baseline_ready"))
    baseline_sample_count = int(temporal_signal_summary.get("baseline_sample_count") or 0)
    if not baseline_ready and not (warm_recovery and baseline_sample_count >= 1):
        return False

    combined_active_evidence = temporal_signal_summary.get("combined_active_evidence") or 0.0
    face_present_ratio = sum(1 for entry in recent_entries if entry.face_detected) / max(len(recent_entries), 1)
    min_face_ratio = 0.35 if warm_recovery else 0.6
    min_confidence = 0.45 if warm_recovery else 0.60
    return face_present_ratio >= min_face_ratio and (
        combined_active_evidence >= 0.12 or current_frame.confidence >= min_confidence
    )


def _resolve_decision_state(
    *,
    recent_entries: list[FrameMetrics],
    current_frame: FrameMetrics,
    face_present_ratio: float,
    consecutive_no_face_frames: int,
    warm_recovery: bool,
    low_quality: bool,
    sufficient_evidence: bool,
    smoothed_score: float,
    decision_confidence: float,
    no_face_consecutive_threshold: int,
) -> str:
    if consecutive_no_face_frames >= no_face_consecutive_threshold or face_present_ratio <= 0.15:
        return "NO_FACE"
    if _is_device_replay_spoof_detected(current_frame):
        return "LIKELY_SPOOF"
    if low_quality:
        return "LOW_QUALITY"
    if not sufficient_evidence:
        return "INSUFFICIENT_EVIDENCE"

    live_score_threshold = 68.0 if warm_recovery else 80.0
    live_conf_threshold = 0.50 if warm_recovery else 0.65
    if smoothed_score >= live_score_threshold and decision_confidence >= live_conf_threshold:
        return "LIKELY_LIVE"
    if smoothed_score < 55.0 and decision_confidence >= 0.55:
        return "LIKELY_SPOOF"
    return "INSUFFICIENT_EVIDENCE"


def _calculate_temporal_consistency(score_variance: float) -> float:
    return max(0.0, min(1.0, 1.0 - (score_variance / 400.0)))


def _face_size_adequacy(face_size_ratio: Optional[float]) -> float:
    if face_size_ratio is None:
        return 0.0
    return max(0.0, min(1.0, face_size_ratio / 0.18))


def _blur_adequacy(blur_score: Optional[float]) -> float:
    if blur_score is None:
        return 0.0
    return max(0.0, min(1.0, blur_score / 120.0))


def _brightness_adequacy(brightness: float) -> float:
    return max(0.0, min(1.0, 1.0 - abs(brightness - 130.0) / 110.0))


def _calculate_window_confidence(
    *,
    recent_entries: list[FrameMetrics],
    face_present_ratio: float,
    temporal_signal_summary: dict[str, Optional[float]],
    sufficient_evidence: bool,
    temporal_consistency: float,
    frame_confidence_mean: float,
    directional_agreement_mean: float,
    face_quality_mean: float,
    face_size_adequacy: float,
    blur_adequacy: float,
    brightness_adequacy: float,
) -> float:
    if not recent_entries:
        return 0.0

    # Confidence is a reliability metric. It intentionally excludes the smoothed
    # liveness score and is driven only by input quality, agreement, presence,
    # temporal stability, and evidence sufficiency.
    valid_face_ratio = sum(1 for entry in recent_entries if entry.face_detected) / max(len(recent_entries), 1)
    evidence_strength = max(
        0.0,
        min(
            1.0,
            0.55 * float(temporal_signal_summary.get("combined_active_evidence") or 0.0)
            + 0.45 * (1.0 if sufficient_evidence else 0.0),
        ),
    )
    confidence = (
        0.18 * max(0.0, min(1.0, face_quality_mean))
        + 0.16 * max(0.0, min(1.0, valid_face_ratio))
        + 0.14 * face_size_adequacy
        + 0.12 * blur_adequacy
        + 0.10 * brightness_adequacy
        + 0.10 * max(0.0, min(1.0, face_present_ratio))
        + 0.08 * max(0.0, min(1.0, frame_confidence_mean))
        + 0.12 * max(0.0, min(1.0, directional_agreement_mean))
        + 0.10 * temporal_consistency
        + 0.10 * evidence_strength
    )
    if len(recent_entries) < 4:
        confidence *= 0.75
    return max(0.0, min(1.0, confidence))


def _first_available(entries: list[FrameMetrics], field_name: str) -> Optional[float]:
    for entry in reversed(entries):
        value = _maybe_float(entry.details.get(field_name))
        if value is not None:
            return value
    return None
