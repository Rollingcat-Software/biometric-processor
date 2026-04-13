"""Replay/device spoof risk analysis for developer-facing live preview flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from app.application.services.device_boundary_detector import DeviceBoundaryDetector
from app.infrastructure.ml.liveness.moire_pattern_analysis import analyze_moire_pattern


@dataclass(frozen=True)
class DeviceSpoofRiskAssessment:
    """Normalized replay/device spoof indicators."""

    moire_risk: float
    reflection_risk: float
    flicker_risk: float
    screen_frame_risk: float
    device_replay_risk: float
    details: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, float]:
        """Serialize the primary risk values for UI/debug consumers."""
        return {
            "moire_risk": self.moire_risk,
            "reflection_risk": self.reflection_risk,
            "flicker_risk": self.flicker_risk,
            "screen_frame_risk": self.screen_frame_risk,
            "device_replay_risk": self.device_replay_risk,
        }


class DeviceSpoofRiskEvaluator:
    """Estimate device replay risk without modifying core liveness scoring."""

    DEVICE_REPLAY_MOIRE_WEIGHT = 0.35
    DEVICE_REPLAY_REFLECTION_WEIGHT = 0.25
    DEVICE_REPLAY_FLICKER_WEIGHT = 0.15
    DEVICE_REPLAY_SCREEN_FRAME_WEIGHT = 0.25

    def __init__(self, *, history_size: int = 12) -> None:
        self._max_history_samples = max(4, history_size)
        self._device_boundary_detector = DeviceBoundaryDetector(history_size=5)

    def evaluate(
        self,
        *,
        frame_bgr: np.ndarray,
        face_region_bgr: Optional[np.ndarray] = None,
        face_bounding_box: Optional[tuple[int, int, int, int]] = None,
    ) -> DeviceSpoofRiskAssessment:
        """Return normalized replay/device risk signals for the current frame."""
        analysis_region = face_region_bgr if face_region_bgr is not None and face_region_bgr.size else frame_bgr
        if analysis_region is None or analysis_region.size == 0:
            return DeviceSpoofRiskAssessment(
                moire_risk=0.0,
                reflection_risk=0.0,
                flicker_risk=0.0,
                screen_frame_risk=0.0,
                device_replay_risk=0.0,
                details={},
            )

        gray = cv2.cvtColor(analysis_region, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(analysis_region, cv2.COLOR_BGR2HSV)
        moire_risk, moire_details = self._compute_moire_risk(gray)
        reflection_risk, reflection_details = self._compute_reflection_risk(hsv)
        screen_frame_risk, screen_frame_details = self._compute_screen_frame_risk(
            frame_bgr=frame_bgr,
            face_bounding_box=face_bounding_box,
        )
        flicker_details = self._compute_flicker_signal_sample(gray)
        flicker_risk = 0.0
        device_replay_risk = self._combine_risks(
            moire_risk=moire_risk,
            reflection_risk=reflection_risk,
            flicker_risk=flicker_risk,
            screen_frame_risk=screen_frame_risk,
        )

        details = {
            **moire_details,
            **reflection_details,
            **screen_frame_details,
            **flicker_details,
            "device_replay_risk": device_replay_risk,
        }
        return DeviceSpoofRiskAssessment(
            moire_risk=moire_risk,
            reflection_risk=reflection_risk,
            flicker_risk=flicker_risk,
            screen_frame_risk=screen_frame_risk,
            device_replay_risk=device_replay_risk,
            details=details,
        )

    def update_with_temporal_history(
        self,
        assessment: DeviceSpoofRiskAssessment,
        temporal_signal_history: list[dict[str, float]],
    ) -> DeviceSpoofRiskAssessment:
        """Recompute flicker/device replay risk using the shared rolling preview history."""
        bounded_history = temporal_signal_history[-self._max_history_samples :]
        flicker_risk, flicker_details = self._compute_flicker_risk(bounded_history)
        device_replay_risk = self._combine_risks(
            moire_risk=assessment.moire_risk,
            reflection_risk=assessment.reflection_risk,
            flicker_risk=flicker_risk,
            screen_frame_risk=assessment.screen_frame_risk,
        )
        details = {
            **assessment.details,
            **flicker_details,
            "device_replay_risk": device_replay_risk,
        }
        return DeviceSpoofRiskAssessment(
            moire_risk=assessment.moire_risk,
            reflection_risk=assessment.reflection_risk,
            flicker_risk=flicker_risk,
            screen_frame_risk=assessment.screen_frame_risk,
            device_replay_risk=device_replay_risk,
            details=details,
        )

    @staticmethod
    def temporal_signal_sample_from_details(details: dict[str, float]) -> Optional[dict[str, float]]:
        """Extract replay-temporal signals previously stored on a frame."""
        mean_luma = _maybe_float(details.get("spoof_temporal_mean_luma"))
        line_profile_std = _maybe_float(details.get("spoof_temporal_line_profile_std"))
        row_profile_std = _maybe_float(details.get("spoof_temporal_row_profile_std"))
        col_profile_std = _maybe_float(details.get("spoof_temporal_col_profile_std"))
        if mean_luma is None or line_profile_std is None:
            return None
        return {
            "mean_luma": mean_luma,
            "line_profile_std": line_profile_std,
            "row_profile_std": row_profile_std or 0.0,
            "col_profile_std": col_profile_std or 0.0,
        }

    def _compute_moire_risk(self, gray: np.ndarray) -> tuple[float, dict[str, float]]:
        analysis = analyze_moire_pattern(gray)
        moire_risk = float(analysis["moire_risk"])
        return moire_risk, {
            "moire_score": float(analysis["moire_score"]),
            "moire_response_count": float(analysis["moire_response_count"]),
            "moire_response_fraction": float(analysis["moire_response_fraction"]),
            "moire_response_std_mean": float(analysis["moire_response_std_mean"]),
            "moire_response_std_max": float(analysis["moire_response_std_max"]),
            "moire_response_std_min": float(analysis["moire_response_std_min"]),
            "moire_response_std_range": float(analysis["moire_response_std_range"]),
            "moire_response_std_std": float(analysis["moire_response_std_std"]),
            "moire_gabor_strength": float(analysis["moire_gabor_strength"]),
            "moire_orientation_selectivity": float(analysis["moire_orientation_selectivity"]),
            "moire_periodic_gabor_risk": float(analysis["moire_periodic_gabor_risk"]),
            "moire_center_focus_ratio": float(analysis["moire_center_focus_ratio"]),
            "moire_fft_mid_low_ratio": float(analysis["moire_fft_mid_low_ratio"]),
            "moire_fft_peak_ratio": float(analysis["moire_fft_peak_ratio"]),
            "moire_fft_risk": float(analysis["moire_fft_risk"]),
        }

    def _compute_reflection_risk(self, hsv: np.ndarray) -> tuple[float, dict[str, float]]:
        saturation = hsv[:, :, 1].astype(np.float32)
        value = hsv[:, :, 2].astype(np.float32)
        low_sat_bright = (saturation < 36.0) & (value > 212.0)
        clipped_highlight = value > 245.0
        bright_ratio = float(np.mean(low_sat_bright))
        clipped_ratio = float(np.mean(clipped_highlight))
        p99_value = float(np.percentile(value, 99))
        cluster_metrics = self._analyze_highlight_clusters(low_sat_bright.astype(np.uint8))
        glossy_patch_ratio = float(cluster_metrics["glossy_patch_ratio"])
        compact_highlight_score = float(cluster_metrics["compact_highlight_score"])
        max_cluster_fill = float(cluster_metrics["max_cluster_fill"])
        max_cluster_area_ratio = float(cluster_metrics["max_cluster_area_ratio"])
        reflection_risk = _clamp01(
            0.30 * _normalize(bright_ratio, 0.015, 0.120)
            + 0.20 * _normalize(clipped_ratio, 0.003, 0.050)
            + 0.15 * _normalize(p99_value, 225.0, 252.0)
            + 0.20 * _normalize(glossy_patch_ratio, 0.003, 0.040)
            + 0.15 * compact_highlight_score
        )
        return reflection_risk, {
            "reflection_low_sat_bright_ratio": bright_ratio,
            "reflection_clipped_ratio": clipped_ratio,
            "reflection_p99_value": p99_value,
            "reflection_glossy_patch_ratio": glossy_patch_ratio,
            "reflection_compact_highlight_score": compact_highlight_score,
            "reflection_max_cluster_fill": max_cluster_fill,
            "reflection_max_cluster_area_ratio": max_cluster_area_ratio,
        }

    def _compute_screen_frame_risk(
        self,
        *,
        frame_bgr: np.ndarray,
        face_bounding_box: Optional[tuple[int, int, int, int]],
    ) -> tuple[float, dict[str, float]]:
        if frame_bgr is None or frame_bgr.size == 0 or face_bounding_box is None:
            return 0.0, {
                "screen_frame_area_ratio": 0.0,
                "screen_frame_rectangularity": 0.0,
                "screen_frame_border_darkness": 0.0,
                "screen_frame_inner_brightness": 0.0,
                "screen_frame_border_contrast": 0.0,
                "screen_frame_face_center_inside": 0.0,
                "screen_frame_source": 0.0,
            }
        detection = self._device_boundary_detector.analyze(
            frame_bgr=frame_bgr,
            face_bbox=face_bounding_box,
        )
        details = {
            "screen_frame_area_ratio": float(detection.details.get("boundary_candidate_area_ratio") or 0.0),
            "screen_frame_rectangularity": float(detection.details.get("boundary_rectangularity") or 0.0),
            "screen_frame_border_darkness": 0.0,
            "screen_frame_inner_brightness": 0.0,
            "screen_frame_border_contrast": 0.0,
            "screen_frame_face_center_inside": float(detection.details.get("boundary_face_coverage_score") or 0.0),
            "screen_frame_source": float(detection.is_spoof_confirmed),
            "screen_frame_line_score": float(detection.details.get("boundary_line_score") or 0.0),
            "screen_frame_parallel_score": float(detection.details.get("boundary_parallel_score") or 0.0),
            "screen_frame_orthogonal_score": float(detection.details.get("boundary_orthogonal_score") or 0.0),
            "screen_frame_aspect_score": float(detection.details.get("boundary_aspect_score") or 0.0),
            "screen_frame_temporal_sync_score": float(detection.details.get("boundary_temporal_sync_score") or 0.0),
            "screen_frame_motion_sync_ratio": float(detection.details.get("boundary_motion_sync_ratio") or 0.0),
            "screen_frame_candidate_score": detection.boundary_score,
        }
        return detection.boundary_score, details

    def _analyze_highlight_clusters(self, bright_mask: np.ndarray) -> dict[str, float]:
        if bright_mask.size == 0:
            return {
                "glossy_patch_ratio": 0.0,
                "compact_highlight_score": 0.0,
                "max_cluster_fill": 0.0,
                "max_cluster_area_ratio": 0.0,
            }

        roi_area = float(bright_mask.shape[0] * bright_mask.shape[1])
        kernel = np.ones((3, 3), dtype=np.uint8)
        cleaned = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
        component_count, _, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

        glossy_patch_area = 0.0
        compact_highlight_score = 0.0
        max_cluster_fill = 0.0
        max_cluster_area_ratio = 0.0
        min_component_area = max(4.0, roi_area * 0.0003)
        max_component_area = roi_area * 0.10

        for label in range(1, component_count):
            area = float(stats[label, cv2.CC_STAT_AREA])
            if area < min_component_area or area > max_component_area:
                continue

            width = float(stats[label, cv2.CC_STAT_WIDTH])
            height = float(stats[label, cv2.CC_STAT_HEIGHT])
            bbox_area = max(width * height, 1.0)
            fill_ratio = area / bbox_area
            area_ratio = area / max(roi_area, 1.0)

            glossy_patch_area += area
            max_cluster_fill = max(max_cluster_fill, fill_ratio)
            max_cluster_area_ratio = max(max_cluster_area_ratio, area_ratio)

            component_score = _clamp01(
                0.55 * _normalize(area_ratio, 0.0008, 0.020)
                + 0.45 * _normalize(fill_ratio, 0.30, 0.92)
            )
            compact_highlight_score = max(compact_highlight_score, component_score)

        return {
            "glossy_patch_ratio": glossy_patch_area / max(roi_area, 1.0),
            "compact_highlight_score": compact_highlight_score,
            "max_cluster_fill": max_cluster_fill,
            "max_cluster_area_ratio": max_cluster_area_ratio,
        }

    def _compute_flicker_signal_sample(self, gray: np.ndarray) -> dict[str, float]:
        row_profile = np.mean(gray, axis=1)
        col_profile = np.mean(gray, axis=0)
        row_profile_std = float(np.std(row_profile))
        col_profile_std = float(np.std(col_profile))
        return {
            "spoof_temporal_mean_luma": float(np.mean(gray)),
            "spoof_temporal_row_profile_std": row_profile_std,
            "spoof_temporal_col_profile_std": col_profile_std,
            "spoof_temporal_line_profile_std": max(row_profile_std, col_profile_std),
        }

    def _compute_flicker_risk(self, temporal_signal_history: list[dict[str, float]]) -> tuple[float, dict[str, float]]:
        if len(temporal_signal_history) < 4:
            return 0.0, {
                "flicker_luma_std": 0.0,
                "flicker_delta_std": 0.0,
                "flicker_zero_cross_ratio": 0.0,
                "flicker_line_profile_std": 0.0,
                "flicker_line_delta_std": 0.0,
            }

        values = np.asarray([sample["mean_luma"] for sample in temporal_signal_history], dtype=np.float32)
        line_values = np.asarray([sample["line_profile_std"] for sample in temporal_signal_history], dtype=np.float32)
        deltas = np.diff(values)
        line_deltas = np.diff(line_values)
        centered = values - np.mean(values)
        zero_crossings = np.sum(np.signbit(centered[:-1]) != np.signbit(centered[1:])) if len(centered) > 1 else 0
        zero_cross_ratio = float(zero_crossings / max(len(centered) - 1, 1))
        luma_std = float(np.std(values))
        delta_std = float(np.std(deltas)) if len(deltas) else 0.0
        line_profile_std = float(np.std(line_values))
        line_delta_std = float(np.std(line_deltas)) if len(line_deltas) else 0.0
        flicker_risk = _clamp01(
            0.35 * _normalize(luma_std, 1.5, 8.5)
            + 0.30 * _normalize(delta_std, 1.0, 6.5)
            + 0.20 * _normalize(zero_cross_ratio, 0.20, 0.75)
            + 0.10 * _normalize(line_profile_std, 0.8, 5.0)
            + 0.05 * _normalize(line_delta_std, 0.5, 4.0)
        )
        return flicker_risk, {
            "flicker_luma_std": luma_std,
            "flicker_delta_std": delta_std,
            "flicker_zero_cross_ratio": zero_cross_ratio,
            "flicker_line_profile_std": line_profile_std,
            "flicker_line_delta_std": line_delta_std,
        }

    @staticmethod
    def _combine_risks(
        *,
        moire_risk: float,
        reflection_risk: float,
        flicker_risk: float,
        screen_frame_risk: float,
    ) -> float:
        return _clamp01(
            DeviceSpoofRiskEvaluator.DEVICE_REPLAY_MOIRE_WEIGHT * moire_risk
            + DeviceSpoofRiskEvaluator.DEVICE_REPLAY_REFLECTION_WEIGHT * reflection_risk
            + DeviceSpoofRiskEvaluator.DEVICE_REPLAY_FLICKER_WEIGHT * flicker_risk
            + DeviceSpoofRiskEvaluator.DEVICE_REPLAY_SCREEN_FRAME_WEIGHT * screen_frame_risk
        )


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp01((float(value) - low) / (high - low))


def _maybe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
