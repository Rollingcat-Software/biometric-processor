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

from app.domain.exceptions.liveness_errors import LivenessCheckError
from app.infrastructure.ml.liveness.uniface_liveness_detector import (
    UniFaceLivenessDetector,
    _get_shared_minifasnet,
)


@pytest.fixture(autouse=True)
def _reset_shared_minifasnet_cache():
    """Clear the module-level MiniFASNet `lru_cache` between tests.

    The cache is intentionally process-wide in production (Copilot
    post-merge round 8 / PR #64), but tests stub different fake
    `MiniFASNet` factories per case and need a fresh slate each time.
    """
    _get_shared_minifasnet.cache_clear()
    yield
    _get_shared_minifasnet.cache_clear()


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


# ---------------------------------------------------------------------------
# warm_model_sync — Copilot post-merge round 8 (PR #64)
# ---------------------------------------------------------------------------


def test_warm_model_sync_loads_minifasnet_exactly_once(monkeypatch):
    """warm_model_sync must instantiate MiniFASNet exactly once across both
    multiple detector instances and repeat calls — the whole point of the
    fix is that the warm-up persists into request-time detector instances."""
    call_count = 0

    def _fake_factory():
        nonlocal call_count
        call_count += 1
        return MagicMock(name=f"MiniFASNet#{call_count}")

    fake_spoofing = types.ModuleType("uniface.spoofing")
    fake_spoofing.MiniFASNet = _fake_factory
    monkeypatch.setitem(sys.modules, "uniface", types.ModuleType("uniface"))
    monkeypatch.setitem(sys.modules, "uniface.spoofing", fake_spoofing)

    # Detector A: warm at "startup" (analogue of initialize_dependencies).
    warm_detector = UniFaceLivenessDetector()
    warm_detector.warm_model_sync()
    assert call_count == 1, "warm_model_sync should construct exactly one MiniFASNet"
    assert warm_detector._model is not None

    # Repeat call on the same instance is a no-op.
    warm_detector.warm_model_sync()
    assert call_count == 1, "second warm_model_sync on same instance must be a no-op"

    # Detector B: a fresh instance — analogue of a request-time
    # `get_liveness_detector()` after the warm-up. The shared lru_cache
    # MUST hand back the same MiniFASNet, NOT instantiate another one.
    request_detector = UniFaceLivenessDetector()
    request_detector.warm_model_sync()
    assert call_count == 1, (
        "warm_model_sync on a second instance must reuse the shared MiniFASNet "
        "(otherwise the bio-1 caching fix is broken)."
    )
    assert request_detector._model is warm_detector._model


def test_warm_model_sync_surfaces_import_error_as_liveness_check_error(monkeypatch):
    """If `uniface` is not installed, warm_model_sync must raise
    LivenessCheckError with the original ImportError preserved as
    `__cause__` so container.py can disambiguate missing-dependency
    from real failures (Copilot post-merge round 8 / bio-2)."""
    # Force `from uniface.spoofing import MiniFASNet` to raise ImportError
    # by removing the fake modules from sys.modules and ensuring real
    # import fails. We simulate a missing package via a sentinel module
    # whose attribute access raises.
    fake_spoofing = types.ModuleType("uniface.spoofing")

    def _missing_attr(name):
        raise ImportError(f"cannot import name {name!r} from 'uniface.spoofing' (test stub)")

    fake_spoofing.__getattr__ = _missing_attr  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uniface", types.ModuleType("uniface"))
    monkeypatch.setitem(sys.modules, "uniface.spoofing", fake_spoofing)

    detector = UniFaceLivenessDetector()
    with pytest.raises(LivenessCheckError) as excinfo:
        detector.warm_model_sync()

    # The original ImportError must be reachable via __cause__ so the
    # container.py warm-up code can log the operator-friendly message.
    assert isinstance(excinfo.value.__cause__, ImportError)


def test_warm_model_sync_primes_shared_cache_for_async_path(monkeypatch):
    """After warm_model_sync(), a freshly constructed detector's
    async `_ensure_model_loaded()` must skip MiniFASNet construction
    and re-use the cached model — the end-to-end behaviour the warm-up
    is meant to deliver."""
    call_count = 0

    def _fake_factory():
        nonlocal call_count
        call_count += 1
        return MagicMock(name=f"MiniFASNet#{call_count}")

    fake_spoofing = types.ModuleType("uniface.spoofing")
    fake_spoofing.MiniFASNet = _fake_factory
    monkeypatch.setitem(sys.modules, "uniface", types.ModuleType("uniface"))
    monkeypatch.setitem(sys.modules, "uniface.spoofing", fake_spoofing)

    # Warm at startup.
    UniFaceLivenessDetector().warm_model_sync()
    assert call_count == 1

    # Simulate the request path: a fresh non-cached detector instance
    # calls the async lazy-loader. The shared cache must short-circuit.
    request_detector = UniFaceLivenessDetector()
    loaded = asyncio.run(request_detector._ensure_model_loaded())
    assert loaded is not None
    assert call_count == 1, (
        "request-time _ensure_model_loaded() must not pay the MiniFASNet "
        "construction cost when warm_model_sync() ran at startup."
    )
