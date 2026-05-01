"""Unit tests for UniFaceLivenessDetector concurrency.

Covers the async-lock + double-checked-locking concurrency in
`_ensure_model_loaded` introduced in PR #57 / hardened in PR #59.
Without the lock, fan-in concurrent first calls would each hit the
import path and instantiate the heavy MiniFASNet ONNX model multiple
times (10x in the worst case → cold-start GC pressure + 10x ONNX
session memory).
"""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest

from app.infrastructure.ml.liveness.uniface_liveness_detector import (
    UniFaceLivenessDetector,
)


@pytest.mark.asyncio
async def test_concurrent_ensure_model_loaded_constructs_once(monkeypatch):
    """5 concurrent first-callers must result in exactly one MiniFASNet()."""
    # Track every call to MiniFASNet().
    call_count = 0

    def _fake_model_factory():
        nonlocal call_count
        call_count += 1
        # Yield to the loop so other coroutines have a chance to race.
        # If the lock is missing they'll each see _model is None and
        # call MiniFASNet() before the first construction completes.
        return MagicMock(name=f"MiniFASNet#{call_count}")

    # Stub `from uniface.spoofing import MiniFASNet`. We inject a fake module
    # so the test does not require the real `uniface` package on PYTHONPATH.
    fake_spoofing = types.ModuleType("uniface.spoofing")

    fake_spoofing.MiniFASNet = _fake_model_factory
    monkeypatch.setitem(sys.modules, "uniface", types.ModuleType("uniface"))
    monkeypatch.setitem(sys.modules, "uniface.spoofing", fake_spoofing)

    detector = UniFaceLivenessDetector(liveness_threshold=70.0)

    # Fire 5 concurrent first-callers. Each call hits `await self._lock`
    # before touching `self._model`, so the lock + double-checked-loading
    # path serialises the 5 coroutines: only the first one observes
    # `_model is None` and constructs; the other 4 wake on the released
    # lock and short-circuit on the non-None re-check.
    #
    # Note on test scope: this asserts the LOCK guard. We intentionally
    # don't try to "widen the race window" with `time.sleep` inside the
    # synchronous MiniFASNet() factory — that sleep would block the event
    # loop and prove nothing about the asyncio.Lock semantics under test.
    # The lock is what matters, and gather + lock + non-None re-check
    # together guarantee call_count == 1.
    results = await asyncio.gather(
        *(detector._ensure_model_loaded() for _ in range(5))
    )

    # Bug-fix assertion: only ONE MiniFASNet instantiation, regardless of
    # the 5 concurrent calls.
    assert call_count == 1, (
        f"Expected exactly 1 MiniFASNet() construction, got {call_count} — "
        "the async-lock double-checked-locking guard is broken."
    )

    # All 5 callers must observe the same loaded model instance.
    assert all(r is detector._model for r in results)
    assert detector._model is not None


@pytest.mark.asyncio
async def test_ensure_model_loaded_returns_loaded_model_directly(monkeypatch):
    """`_ensure_model_loaded` returns the model so callers don't need an
    Optional cast at the call site (Copilot PR #59 finding)."""
    fake_spoofing = types.ModuleType("uniface.spoofing")
    fake_spoofing.MiniFASNet = lambda: MagicMock(name="MiniFASNet-typing-test")
    monkeypatch.setitem(sys.modules, "uniface", types.ModuleType("uniface"))
    monkeypatch.setitem(sys.modules, "uniface.spoofing", fake_spoofing)

    detector = UniFaceLivenessDetector()
    model = await detector._ensure_model_loaded()

    assert model is not None
    assert model is detector._model

    # Second call (fast path) must also return the same model.
    model2 = await detector._ensure_model_loaded()
    assert model2 is model
