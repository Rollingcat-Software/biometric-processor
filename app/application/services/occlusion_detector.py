"""Region-based occlusion detection for face quality assessment.

Replaces the hardcoded ``occlusion=0.0`` previously emitted by
``AnalyzeQualityUseCase`` (see INVESTIGATION_MASTER_2026-05-07.md P1).

Approach
--------
We do NOT need a deep occlusion classifier for the common cases we care
about (sunglasses, mask, hand over the mouth). Three classic image-signal
heuristics applied on relative-coordinate face crop regions are robust
enough at the quality-gate tier:

1. Eye-region pixel-variance: real iris/sclera contrast yields high local
   variance. Dark sunglasses / lowered eyelids collapse this variance
   close to zero.

2. Mouth-region pixel-variance: lips + teeth + shadow give a textured
   patch. A medical mask (mostly uniform white/blue/black fabric) or a
   palm flattens the variance.

3. Mouth-region skin-tone match: a hand over the mouth tends to keep
   skin-tone pixels (high a*/b* values in CIE-Lab) but suppresses
   lip-edge contrast. A mask, in contrast, deviates strongly from the
   cheek-baseline skin tone. We combine both signals so neither hand
   nor mask escapes detection.

Region indices follow ``cutout_anomaly_detector.REGION_SPECS`` (relative
to the bounding-box crop) so we reuse the same convention as the rest of
the bio pipeline without requiring MediaPipe landmarks to be already
computed (which the quality use case currently does not have access to
via the face detector interface).

Output schema (matches the public contract in INVESTIGATION P1):

    {
        "score": float in [0.0, 1.0],   # aggregate occlusion confidence
        "regions": list[str],            # which regions look occluded
        "reason": str | None,            # human-readable hint
        "details": {                     # opaque per-region metrics
            "eyes_variance": float,
            "mouth_variance": float,
            "mouth_skin_match": float,
            ...
        },
    }

The quality use case maps ``score`` onto the legacy 0-100 ``occlusion``
percentage and passes the full dict through as ``occlusion_details`` so
the API response can surface the occluded region(s) to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

# Region boxes are relative (x, y, w, h) inside the face bounding-box
# crop. We deliberately reuse the same layout as
# ``CutoutAnomalyDetector.REGION_SPECS`` to keep the bio pipeline
# coherent. ``cheek`` is added so we have a no-occlusion skin-tone
# baseline to compare mouth pixels against.
REGION_SPECS: dict[str, tuple[float, float, float, float]] = {
    "left_eye": (0.16, 0.21, 0.24, 0.18),
    "right_eye": (0.60, 0.21, 0.24, 0.18),
    "mouth": (0.28, 0.59, 0.44, 0.19),
    "left_cheek": (0.10, 0.42, 0.18, 0.14),
    "right_cheek": (0.72, 0.42, 0.18, 0.14),
}

# Thresholds tuned against synthetic fixtures + the bio-team's verify
# corpus. Variance is computed on the grayscale region scaled to 0-255;
# values below 120 indicate a near-uniform patch (sunglasses, mask,
# closed palm). The mask-vs-skin Lab delta-E threshold of 18 separates
# "fabric over face" from "natural skin".
EYE_VARIANCE_THRESHOLD: float = 120.0
MOUTH_VARIANCE_THRESHOLD: float = 130.0
MOUTH_SKIN_DELTA_THRESHOLD: float = 18.0

# The use case rejects when score > 0.5 OR a critical region is flagged.
# Eyes are critical (any sunglasses-style occlusion blocks enrollment);
# mouth is non-critical for enrollment but still surfaces a warning so
# the API can suggest "remove face covering".
CRITICAL_REGIONS: frozenset[str] = frozenset({"left_eye", "right_eye"})

# Minimum face-crop dimension (px) below which we abstain — too small to
# reason about local variance reliably. Returns score=0.0 so we never
# fail-closed on tiny crops; the face-size gate will catch those.
MIN_CROP_SIZE_PX: int = 48


@dataclass(frozen=True)
class OcclusionAssessment:
    """Structured occlusion result.

    Attributes:
        score: Aggregate occlusion confidence in [0.0, 1.0]. 0 = clear,
            1 = entire face covered.
        regions: Names of regions flagged as occluded.
        reason: Short human-readable hint, or None when clear.
        details: Raw per-region metrics for debugging / calibration.
    """

    score: float
    regions: list[str] = field(default_factory=list)
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe dict (drops numpy scalars)."""
        return {
            "score": float(self.score),
            "regions": list(self.regions),
            "reason": self.reason,
            "details": {k: float(v) for k, v in self.details.items()},
        }


def _relative_box(
    width: int,
    height: int,
    rx: float,
    ry: float,
    rw: float,
    rh: float,
) -> tuple[int, int, int, int]:
    """Convert relative (0..1) box coords to absolute pixel coords."""
    x = int(round(rx * width))
    y = int(round(ry * height))
    w = int(round(rw * width))
    h = int(round(rh * height))
    # Clamp so we never read past the crop edges.
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return x, y, w, h


def _region_variance(gray: np.ndarray, box: tuple[int, int, int, int]) -> float:
    """Pixel-variance of the gray region defined by ``box``."""
    x, y, w, h = box
    region = gray[y : y + h, x : x + w]
    if region.size == 0:
        return 0.0
    return float(np.var(region))


def _region_mean_lab(
    lab: np.ndarray, box: tuple[int, int, int, int]
) -> tuple[float, float, float]:
    """Mean Lab colour for a region. Useful for skin-tone matching."""
    x, y, w, h = box
    region = lab[y : y + h, x : x + w]
    if region.size == 0:
        return 0.0, 0.0, 0.0
    mean = region.reshape(-1, 3).mean(axis=0)
    return float(mean[0]), float(mean[1]), float(mean[2])


def _delta_e(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> float:
    """CIE76 delta-E between two Lab triples. Lower = more similar."""
    return float(
        np.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
    )


def detect_occlusion(face_crop_bgr: np.ndarray) -> OcclusionAssessment:
    """Detect region-based occlusion in a face crop.

    Args:
        face_crop_bgr: Face region in BGR colour order (OpenCV native).
            Callers using RGB must convert first.

    Returns:
        ``OcclusionAssessment`` with score in [0,1] and a list of flagged
        regions. Returns ``score=0.0`` for crops smaller than
        ``MIN_CROP_SIZE_PX`` (too small to reason about reliably).
    """
    if face_crop_bgr is None or face_crop_bgr.size == 0:
        return OcclusionAssessment(
            score=0.0,
            regions=[],
            reason=None,
            details={"abstain": 1.0, "reason_code": 1.0},
        )

    height, width = face_crop_bgr.shape[:2]
    if min(height, width) < MIN_CROP_SIZE_PX:
        return OcclusionAssessment(
            score=0.0,
            regions=[],
            reason=None,
            details={"abstain": 1.0, "min_size_blocked": 1.0},
        )

    gray = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2LAB)

    boxes = {
        name: _relative_box(width, height, *spec)
        for name, spec in REGION_SPECS.items()
    }

    # Per-region variance.
    left_eye_var = _region_variance(gray, boxes["left_eye"])
    right_eye_var = _region_variance(gray, boxes["right_eye"])
    mouth_var = _region_variance(gray, boxes["mouth"])

    # Skin-tone baseline: mean of left + right cheek in Lab space.
    cheek_l = _region_mean_lab(lab, boxes["left_cheek"])
    cheek_r = _region_mean_lab(lab, boxes["right_cheek"])
    cheek_mean = (
        (cheek_l[0] + cheek_r[0]) / 2.0,
        (cheek_l[1] + cheek_r[1]) / 2.0,
        (cheek_l[2] + cheek_r[2]) / 2.0,
    )
    mouth_lab = _region_mean_lab(lab, boxes["mouth"])
    mouth_skin_delta = _delta_e(mouth_lab, cheek_mean)

    flagged: list[str] = []
    eye_occluded = False
    if left_eye_var < EYE_VARIANCE_THRESHOLD:
        flagged.append("left_eye")
        eye_occluded = True
    if right_eye_var < EYE_VARIANCE_THRESHOLD:
        flagged.append("right_eye")
        eye_occluded = True

    # Mouth: flag if low variance AND either (a) the area is uniform and
    # differs strongly from skin (= mask / object) or (b) the area is
    # uniform and matches skin (= flat palm / hand). Either way we want
    # to surface "mouth covered".
    mouth_occluded = mouth_var < MOUTH_VARIANCE_THRESHOLD
    mouth_reason: str | None = None
    if mouth_occluded:
        flagged.append("mouth")
        if mouth_skin_delta >= MOUTH_SKIN_DELTA_THRESHOLD:
            mouth_reason = "mask"
        else:
            mouth_reason = "hand_or_object"

    # Score: 0.6 weight on eyes, 0.4 on mouth, since the use case treats
    # eyes as the critical region. Either fully-occluded eyes pair pushes
    # us above 0.5 even when the mouth is clear.
    eye_contribution = 0.0
    if eye_occluded:
        # Both eyes -> 0.6, single eye -> 0.3.
        eye_contribution = 0.6 if (
            "left_eye" in flagged and "right_eye" in flagged
        ) else 0.3
    mouth_contribution = 0.4 if mouth_occluded else 0.0
    score = min(1.0, eye_contribution + mouth_contribution)

    reason: str | None = None
    if eye_occluded and mouth_occluded:
        reason = "eyes_and_mouth_occluded"
    elif eye_occluded:
        reason = "eyes_occluded_possible_sunglasses"
    elif mouth_occluded:
        reason = f"mouth_occluded_{mouth_reason}" if mouth_reason else "mouth_occluded"

    details: dict[str, Any] = {
        "left_eye_variance": left_eye_var,
        "right_eye_variance": right_eye_var,
        "mouth_variance": mouth_var,
        "mouth_skin_delta_e": mouth_skin_delta,
        "eye_variance_threshold": EYE_VARIANCE_THRESHOLD,
        "mouth_variance_threshold": MOUTH_VARIANCE_THRESHOLD,
        "mouth_skin_delta_threshold": MOUTH_SKIN_DELTA_THRESHOLD,
    }

    return OcclusionAssessment(
        score=score,
        regions=flagged,
        reason=reason,
        details=details,
    )


def has_critical_occlusion(assessment: OcclusionAssessment) -> bool:
    """Return True when the use case must fail the quality gate.

    The contract from INVESTIGATION_MASTER_2026-05-07.md P1 is:
    "Quality fails if occlusion.score > 0.5 OR any critical region listed."
    """
    if assessment.score > 0.5:
        return True
    return any(region in CRITICAL_REGIONS for region in assessment.regions)
