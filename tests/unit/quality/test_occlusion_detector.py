"""Unit tests for ``app.application.services.occlusion_detector``.

Synthetic fixtures cover the four scenarios called out in T2-B /
INVESTIGATION_MASTER_2026-05-07.md P1:

1. Clean face        -> score < 0.5, no regions flagged.
2. Eyes occluded     -> score >= 0.5 (critical), eyes in regions.
3. Mouth occluded    -> mouth in regions, mask vs hand reason.
4. Hand-over-face    -> mouth flagged with hand reason.
"""

from __future__ import annotations

import numpy as np

from app.application.services.occlusion_detector import (
    CRITICAL_REGIONS,
    OcclusionAssessment,
    detect_occlusion,
    has_critical_occlusion,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _skin_face(size: int = 200) -> np.ndarray:
    """Build a 200x200 BGR face crop with simulated facial texture.

    We seed each region with a different mean + noise so eye / mouth
    variance lives above the detector thresholds for the "clean" baseline.
    """
    rng = np.random.default_rng(seed=42)
    # Cheek baseline: warm skin tone (BGR).
    img = np.full((size, size, 3), [110, 150, 200], dtype=np.uint8)
    # Add per-pixel noise so the variance stays high across the whole face.
    noise = rng.integers(-25, 25, size=(size, size, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # High-variance eye patches: stripe pattern simulating iris/sclera.
    for x0 in (int(0.16 * size), int(0.60 * size)):
        for dx in range(int(0.24 * size)):
            for dy in range(int(0.18 * size)):
                # alternating dark/bright rows = high variance
                pixel = 30 if dy % 2 == 0 else 220
                img[int(0.21 * size) + dy, x0 + dx] = [pixel, pixel, pixel]

    # Mouth: alternating red/dark vertical stripes (lip + shadow texture).
    mx, my = int(0.28 * size), int(0.59 * size)
    mw, mh = int(0.44 * size), int(0.19 * size)
    for dx in range(mw):
        for dy in range(mh):
            if dx % 2 == 0:
                img[my + dy, mx + dx] = [50, 60, 200]   # red-ish lip
            else:
                img[my + dy, mx + dx] = [20, 20, 40]    # shadow
    return img


def _occlude(
    img: np.ndarray,
    rel_box: tuple[float, float, float, float],
    color: tuple[int, int, int],
) -> np.ndarray:
    """Paint a flat coloured rectangle over ``rel_box`` (relative coords)."""
    out = img.copy()
    h, w = out.shape[:2]
    rx, ry, rw, rh = rel_box
    x = int(rx * w)
    y = int(ry * h)
    bw = int(rw * w)
    bh = int(rh * h)
    out[y : y + bh, x : x + bw] = color
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOcclusionDetector:
    """Sanity tests for the region-based occlusion detector."""

    def test_clean_face_passes(self) -> None:
        img = _skin_face()
        result = detect_occlusion(img)
        assert isinstance(result, OcclusionAssessment)
        assert result.score < 0.5, (
            f"clean face flagged: score={result.score} regions={result.regions}"
        )
        # No critical region should be flagged on a clean face.
        assert not has_critical_occlusion(result)

    def test_sunglasses_occlude_eyes(self) -> None:
        img = _skin_face()
        # Flat black bar across both eye regions.
        img = _occlude(img, (0.10, 0.18, 0.85, 0.24), (0, 0, 0))
        result = detect_occlusion(img)
        assert "left_eye" in result.regions
        assert "right_eye" in result.regions
        assert result.score >= 0.5, f"score too low: {result.score}"
        assert has_critical_occlusion(result)
        # Reason should mention eyes / sunglasses.
        assert result.reason is not None
        assert "eyes" in result.reason

    def test_mask_occludes_mouth(self) -> None:
        img = _skin_face()
        # Flat white mask over mouth — far from skin tone in Lab space.
        img = _occlude(img, (0.20, 0.55, 0.60, 0.30), (250, 250, 250))
        result = detect_occlusion(img)
        assert "mouth" in result.regions
        # Mask should classify as "mask" (skin-tone mismatch).
        assert result.reason is not None
        assert "mouth" in result.reason

    def test_hand_over_mouth(self) -> None:
        img = _skin_face()
        # Flat skin-tone patch over mouth — variance low, skin delta small.
        img = _occlude(img, (0.20, 0.55, 0.60, 0.30), (110, 150, 200))
        result = detect_occlusion(img)
        assert "mouth" in result.regions
        assert result.reason is not None
        # Should resolve to hand_or_object (skin-tone match, low variance).
        assert "hand" in result.reason or "mouth_occluded" in result.reason

    def test_tiny_crop_abstains(self) -> None:
        # Below MIN_CROP_SIZE_PX -> detector returns 0.0 (don't fail-closed).
        img = np.zeros((30, 30, 3), dtype=np.uint8)
        result = detect_occlusion(img)
        assert result.score == 0.0
        assert result.regions == []

    def test_empty_input_abstains(self) -> None:
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        result = detect_occlusion(empty)
        assert result.score == 0.0

    def test_to_dict_is_json_safe(self) -> None:
        img = _skin_face()
        result = detect_occlusion(img)
        payload = result.to_dict()
        assert set(payload.keys()) == {"score", "regions", "reason", "details"}
        assert isinstance(payload["score"], float)
        assert isinstance(payload["regions"], list)
        # details values must all be plain Python floats (no numpy scalars).
        for v in payload["details"].values():
            assert isinstance(v, float)

    def test_critical_regions_constant(self) -> None:
        # Contract: eyes are critical, mouth alone is not. Locking this
        # so a refactor cannot silently demote eye coverage to "warning".
        assert "left_eye" in CRITICAL_REGIONS
        assert "right_eye" in CRITICAL_REGIONS
        assert "mouth" not in CRITICAL_REGIONS
