"""Background active reaction evaluation for passive live capture sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class ReactionSignalFrame:
    """Minimal per-frame signal snapshot used for temporal reaction evaluation."""

    timestamp: float
    face_detected: bool
    active_score: float
    active_evidence: Optional[float]
    ear_current: Optional[float]
    mar_current: Optional[float]
    yaw_current: Optional[float]
    pitch_current: Optional[float] = None
    roll_current: Optional[float] = None
    face_quality: Optional[float] = None
    face_size_ratio: Optional[float] = None
    smile_score: Optional[float] = None
    blink_score: Optional[float] = None
    ear_baseline: Optional[float] = None
    mar_baseline: Optional[float] = None
    smile_baseline: Optional[float] = None
    yaw_baseline: Optional[float] = None
    pitch_baseline: Optional[float] = None
    roll_baseline: Optional[float] = None


@dataclass(frozen=True)
class BackgroundReactionSummary:
    """Per-reaction and combined active support metrics across recent frames."""

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
    supported_score: float
    passive_weight: float
    active_weight: float
    passive_window_score: float
    active_frame_score_mean: float
    active_frame_evidence_mean: float


class BackgroundActiveReactionEvaluator:
    """Evaluate supportive active reactions over a rolling live-capture window."""

    BLINK_DROP_RATIO = 0.16
    BLINK_RECOVERY_RATIO = 0.08
    BLINK_MIN_DROP_HOLD_SECONDS = 0.05
    SMILE_DELTA_THRESHOLD = 6.5
    SMILE_MIN_HOLD_SECONDS = 0.18
    MOUTH_OPEN_RATIO_THRESHOLD = 1.32
    MOUTH_OPEN_MIN_HOLD_SECONDS = 0.14
    HEAD_TURN_THRESHOLD_DEGREES = 9.0
    HEAD_TURN_MIN_HOLD_SECONDS = 0.12
    HEAD_TURN_RETURN_RATIO = 0.45
    MOUTH_OPEN_RETURN_RATIO = 0.60
    SUPPORTIVE_ACTIVE_BASE_BONUS = 4.0
    SUPPORTIVE_ACTIVE_MAX_BONUS = 12.0
    PRIMARY_EVENT_WEIGHT = 0.75
    SECONDARY_EVENT_WEIGHT = 0.25
    CURRENT_REACTION_BLEND_WEIGHT = 0.50
    PERSISTED_REACTION_BLEND_WEIGHT = 0.50
    TRUST_FLOOR = 0.65
    TRUST_RANGE = 0.35

    def __init__(
        self,
        *,
        decay_seconds: float = 1.25,
        min_face_size_ratio: float = 0.08,
    ) -> None:
        self._decay_seconds = decay_seconds
        self._min_face_size_ratio = min_face_size_ratio
        self._persisted_reaction_evidence: dict[str, float] = {
            "blink": 0.0,
            "head_turn_left": 0.0,
            "head_turn_right": 0.0,
            "mouth_open": 0.0,
            "smile": 0.0,
        }
        self._last_timestamp: Optional[float] = None

    def reset(self) -> None:
        self._persisted_reaction_evidence = {
            "blink": 0.0,
            "head_turn_left": 0.0,
            "head_turn_right": 0.0,
            "mouth_open": 0.0,
            "smile": 0.0,
        }
        self._last_timestamp = None

    def evaluate(
        self,
        frames: Sequence[ReactionSignalFrame],
        *,
        passive_window_score: float,
    ) -> BackgroundReactionSummary:
        latest_timestamp = frames[-1].timestamp if frames else self._last_timestamp
        self._decay_persisted_evidence(latest_timestamp)
        usable_frames = [frame for frame in frames if frame.face_detected]
        if not usable_frames:
            persisted_primary, persisted_secondary, persisted_reaction_evidence = self._strongest_two_evidence(
                self._persisted_reaction_evidence
            )
            return BackgroundReactionSummary(
                blink_evidence=None,
                smile_evidence=None,
                mouth_open_evidence=None,
                head_turn_left_evidence=None,
                head_turn_right_evidence=None,
                primary_event=0.0,
                secondary_event=0.0,
                raw_reaction_evidence=0.0,
                effective_trust=self._effective_trust(0.0),
                trusted_reaction_evidence=0.0,
                persisted_primary=persisted_primary,
                persisted_secondary=persisted_secondary,
                persisted_reaction_evidence=persisted_reaction_evidence,
                raw_active_evidence=0.0,
                combined_active_evidence=persisted_reaction_evidence,
                combined_active_score=self._active_score_from_evidence(persisted_reaction_evidence),
                supported_score=passive_window_score,
                passive_weight=0.88,
                active_weight=0.12,
                passive_window_score=passive_window_score,
                active_frame_score_mean=0.0,
                active_frame_evidence_mean=0.0,
            )

        ear_values = [frame.ear_current for frame in usable_frames if frame.ear_current is not None]
        mar_values = [frame.mar_current for frame in usable_frames if frame.mar_current is not None]
        yaw_values = [frame.yaw_current for frame in usable_frames if frame.yaw_current is not None]
        smile_scores = [frame.smile_score for frame in usable_frames if frame.smile_score is not None]
        frame_active_scores = [frame.active_score for frame in usable_frames]
        frame_active_evidence = [frame.active_evidence for frame in usable_frames if frame.active_evidence is not None]
        active_trust = self._compute_active_trust(usable_frames)

        ear_baseline = _first_available([frame.ear_baseline for frame in usable_frames])
        if ear_baseline is None and ear_values:
            ear_baseline = float(np.percentile(ear_values, 80))

        mar_baseline = _first_available([frame.mar_baseline for frame in usable_frames])
        if mar_baseline is None and mar_values:
            mar_baseline = float(np.percentile(mar_values, 25))

        smile_baseline = _first_available([frame.smile_baseline for frame in usable_frames])
        if smile_baseline is None and smile_scores:
            smile_baseline = float(np.percentile(smile_scores, 25))

        yaw_baseline = _first_available([frame.yaw_baseline for frame in usable_frames])
        if yaw_baseline is None and yaw_values:
            yaw_baseline = float(np.median(yaw_values))

        blink_evidence = self.compute_blink_evidence(usable_frames, ear_baseline)
        smile_evidence = self.compute_smile_evidence(usable_frames, mar_baseline, smile_baseline)
        mouth_open_evidence = self.compute_mouth_open_evidence(usable_frames, mar_baseline)
        head_turn_left_evidence = self.compute_head_turn_left_evidence(usable_frames, yaw_baseline)
        head_turn_right_evidence = self.compute_head_turn_right_evidence(usable_frames, yaw_baseline)
        event_evidences = {
            "blink": blink_evidence or 0.0,
            "head_turn_left": head_turn_left_evidence or 0.0,
            "head_turn_right": head_turn_right_evidence or 0.0,
            "mouth_open": mouth_open_evidence or 0.0,
            "smile": smile_evidence or 0.0,
        }
        primary_event, secondary_event, raw_reaction_evidence = self._strongest_two_evidence(event_evidences)
        frame_active_score_mean = float(np.mean(frame_active_scores)) if frame_active_scores else 0.0
        frame_active_evidence_mean = float(np.mean(frame_active_evidence)) if frame_active_evidence else 0.0
        effective_trust = self._effective_trust(active_trust)
        trusted_reaction_evidence = _clamp01(raw_reaction_evidence * effective_trust)

        self._persist_reaction_evidence(
            {
                key: value * effective_trust
                for key, value in event_evidences.items()
            }
        )
        persisted_primary, persisted_secondary, persisted_reaction_evidence = self._strongest_two_evidence(
            self._persisted_reaction_evidence
        )
        raw_active_evidence = trusted_reaction_evidence
        combined_active_evidence = _clamp01(
            self.CURRENT_REACTION_BLEND_WEIGHT * trusted_reaction_evidence
            + self.PERSISTED_REACTION_BLEND_WEIGHT * persisted_reaction_evidence
        )
        combined_active_score = self._active_score_from_evidence(combined_active_evidence)

        passive_foundation = max(0.0, min(100.0, passive_window_score))
        passive_strength = _clamp01((passive_foundation - 45.0) / 35.0)
        active_quality = combined_active_evidence
        active_bonus_budget = self.SUPPORTIVE_ACTIVE_BASE_BONUS + (
            self.SUPPORTIVE_ACTIVE_MAX_BONUS - self.SUPPORTIVE_ACTIVE_BASE_BONUS
        ) * passive_strength
        supportive_active_bonus = active_bonus_budget * combined_active_evidence * active_quality * effective_trust

        # Background active evidence is supportive only in passive live capture.
        # It may strengthen a good passive result, but it does not drag the
        # passive foundation downward when reactions are weak or absent.
        supported_score = min(100.0, passive_foundation + supportive_active_bonus)
        active_contribution = max(0.0, supported_score - passive_foundation)
        total_contribution = max(supported_score, 1e-6)
        active_weight = min(0.22, active_contribution / total_contribution)
        passive_weight = 1.0 - active_weight

        return BackgroundReactionSummary(
            blink_evidence=blink_evidence,
            smile_evidence=smile_evidence,
            mouth_open_evidence=mouth_open_evidence,
            head_turn_left_evidence=head_turn_left_evidence,
            head_turn_right_evidence=head_turn_right_evidence,
            primary_event=primary_event,
            secondary_event=secondary_event,
            raw_reaction_evidence=raw_reaction_evidence,
            effective_trust=effective_trust,
            trusted_reaction_evidence=trusted_reaction_evidence,
            persisted_primary=persisted_primary,
            persisted_secondary=persisted_secondary,
            persisted_reaction_evidence=persisted_reaction_evidence,
            raw_active_evidence=raw_active_evidence,
            combined_active_evidence=combined_active_evidence,
            combined_active_score=combined_active_score,
            supported_score=supported_score,
            passive_weight=passive_weight,
            active_weight=active_weight,
            passive_window_score=passive_window_score,
            active_frame_score_mean=frame_active_score_mean,
            active_frame_evidence_mean=frame_active_evidence_mean,
        )

    def _compute_active_trust(self, frames: Sequence[ReactionSignalFrame]) -> float:
        face_quality_mean = _mean([frame.face_quality for frame in frames if frame.face_quality is not None]) or 0.0
        face_size_values = [frame.face_size_ratio for frame in frames if frame.face_size_ratio is not None]
        if face_size_values:
            size_mean = float(np.mean(face_size_values))
            face_size_trust = _clamp01(size_mean / max(self._min_face_size_ratio, 1e-6))
        else:
            face_size_trust = 0.0
        return _clamp01(0.60 * face_size_trust + 0.40 * face_quality_mean)

    def _active_score_from_evidence(self, active_evidence: float) -> float:
        return min(100.0, max(0.0, 100.0 * float(np.sqrt(max(active_evidence, 0.0)))))

    def _decay_persisted_evidence(self, latest_timestamp: Optional[float]) -> None:
        if latest_timestamp is None:
            return
        if self._last_timestamp is None:
            self._last_timestamp = latest_timestamp
            return
        delta_seconds = max(0.0, latest_timestamp - self._last_timestamp)
        if delta_seconds <= 0.0:
            return
        decay_multiplier = float(np.exp(-delta_seconds / max(self._decay_seconds, 1e-6)))
        for key, value in self._persisted_reaction_evidence.items():
            self._persisted_reaction_evidence[key] = float(value) * decay_multiplier
        self._last_timestamp = latest_timestamp

    def _persist_reaction_evidence(self, current_values: dict[str, float]) -> None:
        for key, current_value in current_values.items():
            self._persisted_reaction_evidence[key] = max(
                self._persisted_reaction_evidence.get(key, 0.0),
                _clamp01(current_value) or 0.0,
            )

    def _effective_trust(self, active_trust: float) -> float:
        return _clamp01(self.TRUST_FLOOR + self.TRUST_RANGE * _clamp01(active_trust))

    def _strongest_two_evidence(self, values: dict[str, float]) -> tuple[float, float, float]:
        ranked = sorted((_clamp01(value) for value in values.values()), reverse=True)
        primary = ranked[0] if ranked else 0.0
        secondary = ranked[1] if len(ranked) > 1 else 0.0
        combined = _clamp01(
            self.PRIMARY_EVENT_WEIGHT * primary
            + self.SECONDARY_EVENT_WEIGHT * secondary
        )
        return primary, secondary, combined

    def compute_blink_evidence(
        self,
        frames: Sequence[ReactionSignalFrame],
        ear_baseline: Optional[float],
    ) -> Optional[float]:
        ear_points = [(frame.timestamp, frame.ear_current) for frame in frames if frame.ear_current is not None]
        if len(ear_points) < 3 or ear_baseline is None or ear_baseline <= 1e-6:
            return None

        ear_values = [value for _, value in ear_points]
        ear_min = min(ear_values)
        low_threshold = ear_baseline * (1.0 - self.BLINK_DROP_RATIO)
        recover_threshold = ear_baseline * (1.0 - self.BLINK_RECOVERY_RATIO)
        low_hold = _longest_run_duration(ear_points, lambda value: value <= low_threshold)
        recovery_seen = any(value >= recover_threshold for _, value in ear_points[-max(2, len(ear_points) // 3):])
        neutral_before_drop = any(value >= recover_threshold for _, value in ear_points[: max(2, len(ear_points) // 3)])
        drop_ratio = max(0.0, (ear_baseline - ear_min) / ear_baseline)
        drop_evidence = _normalize(drop_ratio, lower=0.14, upper=0.34)
        hold_evidence = _normalize(low_hold, lower=self.BLINK_MIN_DROP_HOLD_SECONDS, upper=0.18)
        recovery_evidence = 1.0 if recovery_seen and neutral_before_drop else (0.35 if neutral_before_drop else 0.0)
        return _clamp01(0.45 * drop_evidence + 0.20 * hold_evidence + 0.35 * recovery_evidence)

    def compute_smile_evidence(
        self,
        frames: Sequence[ReactionSignalFrame],
        mar_baseline: Optional[float],
        smile_baseline: Optional[float],
    ) -> Optional[float]:
        mar_values = [frame.mar_current for frame in frames if frame.mar_current is not None]
        smile_scores = [frame.smile_score for frame in frames if frame.smile_score is not None]
        if not mar_values:
            return None

        mar_peak = max(mar_values)
        mar_floor = min(mar_values)
        rise = mar_peak - mar_floor
        rise_ratio = None
        if mar_baseline is not None and mar_baseline > 1e-6:
            rise_ratio = rise / mar_baseline

        mar_evidence = _normalize(rise_ratio, lower=0.18, upper=0.52) if rise_ratio is not None else None
        smile_points = [(frame.timestamp, frame.smile_score) for frame in frames if frame.smile_score is not None]
        smile_frame_peak = max(smile_scores) if smile_scores else None
        smile_frame_delta = None
        if smile_frame_peak is not None and smile_baseline is not None:
            smile_frame_delta = smile_frame_peak - smile_baseline
        smile_frame_evidence = (
            _normalize(smile_frame_delta, lower=8.0, upper=28.0)
            if smile_frame_delta is not None
            else (
                _normalize(smile_frame_peak, lower=55.0, upper=90.0)
                if smile_frame_peak is not None
                else None
            )
        )
        hold_threshold = (
            smile_baseline + self.SMILE_DELTA_THRESHOLD
            if smile_baseline is not None
            else None
        )
        smile_hold = (
            _longest_run_duration(smile_points, lambda value: value >= hold_threshold)
            if hold_threshold is not None
            else 0.0
        )
        hold_evidence = _normalize(smile_hold, lower=self.SMILE_MIN_HOLD_SECONDS, upper=0.45)
        return _weighted_mean(
            [
                (mar_evidence, 0.35),
                (smile_frame_evidence, 0.40),
                (hold_evidence, 0.25),
            ]
        )

    def compute_head_turn_left_evidence(
        self,
        frames: Sequence[ReactionSignalFrame],
        yaw_baseline: Optional[float],
    ) -> Optional[float]:
        yaw_points = [(frame.timestamp, frame.yaw_current) for frame in frames if frame.yaw_current is not None]
        yaw_values = [value for _, value in yaw_points]
        if not yaw_values:
            return None
        baseline = yaw_baseline or 0.0
        left_deviations = [(timestamp, baseline - yaw) for timestamp, yaw in yaw_points if yaw < baseline]
        if not left_deviations:
            return None
        left_peak = max([deviation for _, deviation in left_deviations], default=None)
        hold_duration = _longest_run_duration(
            yaw_points,
            lambda value: (baseline - value) >= self.HEAD_TURN_THRESHOLD_DEGREES,
        )
        neutral_band = max(3.5, self.HEAD_TURN_THRESHOLD_DEGREES * self.HEAD_TURN_RETURN_RATIO)
        neutral_before_turn = any((baseline - value) <= neutral_band for _, value in yaw_points[: max(2, len(yaw_points) // 3)])
        return_seen = any((baseline - value) <= neutral_band for _, value in yaw_points[-max(2, len(yaw_points) // 3) :])
        peak_evidence = _normalize(left_peak, lower=8.0, upper=22.0)
        hold_evidence = _normalize(hold_duration, lower=self.HEAD_TURN_MIN_HOLD_SECONDS, upper=0.35)
        transition_evidence = 1.0 if neutral_before_turn and return_seen else (0.45 if neutral_before_turn else 0.0)
        return _weighted_mean([(peak_evidence, 0.55), (hold_evidence, 0.20), (transition_evidence, 0.25)])

    def compute_head_turn_right_evidence(
        self,
        frames: Sequence[ReactionSignalFrame],
        yaw_baseline: Optional[float],
    ) -> Optional[float]:
        yaw_points = [(frame.timestamp, frame.yaw_current) for frame in frames if frame.yaw_current is not None]
        yaw_values = [value for _, value in yaw_points]
        if not yaw_values:
            return None
        baseline = yaw_baseline or 0.0
        right_deviations = [(timestamp, yaw - baseline) for timestamp, yaw in yaw_points if yaw > baseline]
        if not right_deviations:
            return None
        right_peak = max([deviation for _, deviation in right_deviations], default=None)
        hold_duration = _longest_run_duration(
            yaw_points,
            lambda value: (value - baseline) >= self.HEAD_TURN_THRESHOLD_DEGREES,
        )
        neutral_band = max(3.5, self.HEAD_TURN_THRESHOLD_DEGREES * self.HEAD_TURN_RETURN_RATIO)
        neutral_before_turn = any((value - baseline) <= neutral_band for _, value in yaw_points[: max(2, len(yaw_points) // 3)])
        return_seen = any((value - baseline) <= neutral_band for _, value in yaw_points[-max(2, len(yaw_points) // 3) :])
        peak_evidence = _normalize(right_peak, lower=8.0, upper=22.0)
        hold_evidence = _normalize(hold_duration, lower=self.HEAD_TURN_MIN_HOLD_SECONDS, upper=0.35)
        transition_evidence = 1.0 if neutral_before_turn and return_seen else (0.45 if neutral_before_turn else 0.0)
        return _weighted_mean([(peak_evidence, 0.55), (hold_evidence, 0.20), (transition_evidence, 0.25)])

    def compute_mouth_open_evidence(
        self,
        frames: Sequence[ReactionSignalFrame],
        mar_baseline: Optional[float],
    ) -> Optional[float]:
        mar_points = [(frame.timestamp, frame.mar_current) for frame in frames if frame.mar_current is not None]
        mar_values = [value for _, value in mar_points]
        if not mar_values:
            return None

        mar_peak = max(mar_values)
        mar_mean = float(np.mean(mar_values))
        baseline = mar_baseline if mar_baseline is not None and mar_baseline > 1e-6 else mar_mean
        if baseline <= 1e-6:
            return None

        peak_ratio = mar_peak / baseline
        hold_duration = _longest_run_duration(
            mar_points,
            lambda value: value >= baseline * self.MOUTH_OPEN_RATIO_THRESHOLD,
        )
        open_threshold = baseline * self.MOUTH_OPEN_RATIO_THRESHOLD
        return_threshold = baseline * (1.0 + (self.MOUTH_OPEN_RATIO_THRESHOLD - 1.0) * self.MOUTH_OPEN_RETURN_RATIO)
        neutral_before_open = any(value <= return_threshold for _, value in mar_points[: max(2, len(mar_points) // 3)])
        return_seen = any(value <= return_threshold for _, value in mar_points[-max(2, len(mar_points) // 3) :])
        rise_ratio = (mar_peak - baseline) / baseline
        peak_evidence = _normalize(peak_ratio, lower=1.35, upper=1.95)
        hold_evidence = _normalize(hold_duration, lower=self.MOUTH_OPEN_MIN_HOLD_SECONDS, upper=0.40)
        rise_evidence = _normalize(rise_ratio, lower=0.28, upper=0.90)
        transition_evidence = 1.0 if neutral_before_open and return_seen else (0.45 if neutral_before_open else 0.0)
        if not any(value >= open_threshold for _, value in mar_points):
            transition_evidence = 0.0
        return _weighted_mean(
            [
                (peak_evidence, 0.35),
                (rise_evidence, 0.25),
                (hold_evidence, 0.20),
                (transition_evidence, 0.20),
            ]
        )


def _first_available(values: Sequence[Optional[float]]) -> Optional[float]:
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _normalize(value: Optional[float], *, lower: float, upper: float) -> Optional[float]:
    if value is None:
        return None
    if upper <= lower:
        return None
    return _clamp01((float(value) - lower) / (upper - lower))


def _weighted_mean(values: Sequence[tuple[Optional[float], float]]) -> float:
    numerator = 0.0
    denominator = 0.0
    for value, weight in values:
        if value is None or weight <= 0:
            continue
        numerator += float(value) * weight
        denominator += weight
    if denominator <= 1e-6:
        return 0.0
    return numerator / denominator


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    filtered = [float(value) for value in values if value is not None]
    if not filtered:
        return None
    return float(np.mean(filtered))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _longest_run_duration(
    points: Sequence[tuple[float, Optional[float]]],
    predicate,
) -> float:
    longest = 0.0
    run_start: Optional[float] = None
    previous_timestamp: Optional[float] = None

    for timestamp, value in points:
        if value is not None and predicate(value):
            if run_start is None:
                run_start = timestamp
            previous_timestamp = timestamp
            continue

        if run_start is not None and previous_timestamp is not None:
            longest = max(longest, previous_timestamp - run_start)
        run_start = None
        previous_timestamp = None

    if run_start is not None and previous_timestamp is not None:
        longest = max(longest, previous_timestamp - run_start)
    return max(0.0, longest)
