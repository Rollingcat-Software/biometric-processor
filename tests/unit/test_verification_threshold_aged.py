"""Regression tests for VERIFICATION_THRESHOLD_AGED semantics (bug 2026-05-12).

Background
----------
The comparator in ``app/application/use_cases/verify_face.py`` is
``verified = distance < threshold``. Under that semantic:

  - HIGHER threshold ⇒ MORE LENIENT (the allowed-distance ceiling rises,
    so more pairs pass).
  - LOWER threshold  ⇒ STRICTER (only near-zero distances match).

Before 2026-05-12 the defaults were:

  VERIFICATION_THRESHOLD       = 0.45
  VERIFICATION_THRESHOLD_AGED  = 0.38   # ← bug: stricter, not lenient

That made aged users get a HIGHER FRR — the opposite of the adaptive
feature's intent. This test pins:

  1. The new default for ``VERIFICATION_THRESHOLD_AGED`` is higher than
     the standard ``VERIFICATION_THRESHOLD``.
  2. Loading an inverted config (aged < standard) raises a
     ``ValidationError`` so the regression cannot silently come back via
     env-file edits.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _make(**overrides) -> Settings:
    """Build a Settings instance with no ambient .env interference."""
    return Settings(_env_file=None, **overrides)


def test_default_aged_threshold_is_more_lenient_than_standard():
    """Default config: aged threshold must allow GREATER distance, not less."""
    s = _make()
    assert s.VERIFICATION_THRESHOLD_AGED > s.VERIFICATION_THRESHOLD, (
        f"Aged threshold ({s.VERIFICATION_THRESHOLD_AGED}) must be > standard "
        f"({s.VERIFICATION_THRESHOLD}) under the 'distance < threshold' "
        "comparator. A lower aged threshold makes aged users stricter."
    )


def test_aged_threshold_below_standard_is_rejected():
    """Inversion regression guard: aged < standard must fail config load."""
    with pytest.raises((ValidationError, ValueError)) as exc_info:
        _make(
            VERIFICATION_THRESHOLD=0.45,
            VERIFICATION_THRESHOLD_AGED=0.38,  # the pre-2026-05-12 buggy value
        )
    msg = str(exc_info.value)
    assert "VERIFICATION_THRESHOLD_AGED" in msg
    assert "VERIFICATION_THRESHOLD" in msg


def test_aged_threshold_equal_to_standard_is_allowed():
    """Boundary case: equal thresholds are valid (no adaptive lenience, but
    not inverted)."""
    s = _make(VERIFICATION_THRESHOLD=0.45, VERIFICATION_THRESHOLD_AGED=0.45)
    assert s.VERIFICATION_THRESHOLD == s.VERIFICATION_THRESHOLD_AGED == 0.45


def test_aged_threshold_within_facenet_safe_band():
    """The new default must remain below the Facenet cosine-distance
    operating-point ceiling (~0.6) to avoid blowing FAR past the model."""
    s = _make()
    assert s.VERIFICATION_THRESHOLD_AGED <= 0.6, (
        "VERIFICATION_THRESHOLD_AGED above 0.6 risks FAR explosion under "
        "Facenet cosine-distance distributions."
    )
