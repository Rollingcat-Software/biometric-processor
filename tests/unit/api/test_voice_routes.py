"""Unit tests for voice route handlers (F10 + F11).

These tests exercise the voice route handler coroutines directly (rather than
through a full TestClient) to avoid the asyncio loop-poisoning that the
integration TestClient-in-test-body pattern suffers from, while still covering
the two fixes:

    * F10 — ``/voice/search`` scopes the 1:N query by ``tenant_id`` so a voice
      sample can never match enrollments belonging to OTHER tenants. We assert
      the tenant_id supplied in the request is forwarded to the repository's
      ``find_similar`` call (which adds the SQL tenant predicate).

    * F11 — the voice replay-attack detector is actually invoked on the
      verify/search path (it previously existed but was never called). We assert
      ``check_and_record`` runs when the feature flag is enabled, and that the
      check is non-blocking / skipped when disabled.
"""

import sys
import types
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

# ``app.api.routes.voice`` imports a handful of getters from
# ``app.core.container`` at module load. The real container module eagerly
# wires the full DeepFace/TensorFlow/OpenCV ML stack at import time, which is
# not available in the lean unit-test environment (and is irrelevant to the
# route logic under test — every getter is patched per-test below).
#
# Earlier this file installed a lightweight ``app.core.container`` stub into
# ``sys.modules`` and never removed it. Because ``sys.modules`` is process-wide,
# the stub leaked into *every other* test module collected afterwards — e.g.
# ``tests/unit/infrastructure/test_liveness_runtime_wiring.py`` does
# ``from app.core.container import clear_cache, ...`` and hit the incomplete
# stub, raising ``ImportError`` and aborting the whole suite (exit 2).
#
# Fix: import ``voice`` exactly once here, falling back to a temporary stub
# ONLY for the duration of that import, then restoring the previous
# ``sys.modules`` state. Once ``voice`` is imported, the getter names are bound
# into the ``voice`` module's own namespace (and are patched per-test via
# ``patch.object(voice_routes, ...)``), so the real/stub container module is no
# longer referenced and must not be left lying around in ``sys.modules``.
def _import_voice_routes():
    """Import app.api.routes.voice without leaking a container stub.

    In the Docker/CI image the real container imports cleanly, so the plain
    import succeeds and no stub is ever installed. In a lean environment that
    lacks the heavy ML stack, we temporarily install a minimal container stub
    just long enough to satisfy voice.py's ``from app.core.container import``,
    then restore sys.modules so other test modules see the real container.
    """
    try:
        from app.api.routes import voice as _voice
        return _voice
    except Exception:
        pass

    _had_container = "app.core.container" in sys.modules
    _saved_container = sys.modules.get("app.core.container")
    _stub_container = types.ModuleType("app.core.container")
    for _name in (
        "get_speaker_embedder",
        "get_thread_pool",
        "get_voice_replay_detector",
        "get_voice_repository",
    ):
        setattr(_stub_container, _name, lambda *a, **k: None)
    sys.modules["app.core.container"] = _stub_container
    try:
        from app.api.routes import voice as _voice
        return _voice
    finally:
        if _had_container:
            sys.modules["app.core.container"] = _saved_container
        else:
            sys.modules.pop("app.core.container", None)


voice_routes = _import_voice_routes()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_embedding(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(256).astype(np.float32)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
# F10 — voice search is tenant-scoped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_voice_forwards_tenant_id_to_repository():
    """F10: a tenant_id in the request must be passed to repo.find_similar."""
    repo = Mock()
    repo.find_similar = AsyncMock(return_value=[("user-a", 0.2)])

    detector = Mock()
    detector.enabled = False  # keep replay path out of the way for this test

    with patch.object(voice_routes, "_extract_voice_embedding",
                      AsyncMock(return_value=_unit_embedding(1))), \
         patch.object(voice_routes, "get_voice_repository", return_value=repo), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):

        request = voice_routes.VoiceSearchRequest(
            voice_data="ZmFrZQ==", tenant_id="tenant-x"
        )
        result = await voice_routes.search_voice(request)

    # The repository must have been called WITH the tenant_id (the SQL layer
    # then scopes the query). This is the core of the cross-tenant fix.
    assert repo.find_similar.await_count == 1
    _, kwargs = repo.find_similar.await_args
    assert kwargs.get("tenant_id") == "tenant-x"
    assert result["total_matches"] == 1


@pytest.mark.asyncio
async def test_search_voice_without_tenant_passes_none():
    """Backward-compat: a request without tenant_id forwards tenant_id=None."""
    repo = Mock()
    repo.find_similar = AsyncMock(return_value=[])

    detector = Mock()
    detector.enabled = False

    with patch.object(voice_routes, "_extract_voice_embedding",
                      AsyncMock(return_value=_unit_embedding(2))), \
         patch.object(voice_routes, "get_voice_repository", return_value=repo), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):

        request = voice_routes.VoiceSearchRequest(voice_data="ZmFrZQ==")
        await voice_routes.search_voice(request)

    _, kwargs = repo.find_similar.await_args
    assert kwargs.get("tenant_id") is None


# ---------------------------------------------------------------------------
# F11 — replay detector is wired into the voice paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_voice_invokes_replay_detector_when_enabled():
    """F11: enabled detector's check_and_record must run on /voice/verify."""
    repo = Mock()
    repo.find_by_user_id = AsyncMock(return_value=_unit_embedding(3))

    detector = Mock()
    detector.enabled = True
    detector.check_and_record = AsyncMock(return_value=False)

    probe = _unit_embedding(3)

    with patch.object(voice_routes, "_extract_voice_embedding",
                      AsyncMock(return_value=probe)), \
         patch.object(voice_routes, "_compute_replay_fingerprint",
                      AsyncMock(return_value=np.ones(128, dtype=np.float32))), \
         patch.object(voice_routes, "get_voice_repository", return_value=repo), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):

        request = voice_routes.VoiceRequest(user_id="user-1", voice_data="ZmFrZQ==")
        result = await voice_routes.verify_voice(request)

    # The replay detector must have been consulted on the verify path.
    detector.check_and_record.assert_awaited_once()
    _, kwargs = detector.check_and_record.await_args
    assert kwargs.get("user_id") == "user-1"
    # Replay detection is advisory/log-only — it must NOT block verification.
    assert result.verified is True


@pytest.mark.asyncio
async def test_verify_voice_skips_replay_detector_when_disabled():
    """When the flag is off, check_and_record is never called (no-op)."""
    repo = Mock()
    repo.find_by_user_id = AsyncMock(return_value=_unit_embedding(4))

    detector = Mock()
    detector.enabled = False
    detector.check_and_record = AsyncMock(return_value=False)

    probe = _unit_embedding(4)

    with patch.object(voice_routes, "_extract_voice_embedding",
                      AsyncMock(return_value=probe)), \
         patch.object(voice_routes, "get_voice_repository", return_value=repo), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):

        request = voice_routes.VoiceRequest(user_id="user-2", voice_data="ZmFrZQ==")
        await voice_routes.verify_voice(request)

    detector.check_and_record.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_check_is_non_blocking_on_error():
    """A detector error must be swallowed and treated as 'not a replay'."""
    detector = Mock()
    detector.enabled = True
    detector.check_and_record = AsyncMock(side_effect=RuntimeError("redis down"))

    with patch.object(voice_routes, "_compute_replay_fingerprint",
                      AsyncMock(return_value=np.ones(128, dtype=np.float32))), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):

        suspect = await voice_routes._run_replay_check(
            "ZmFrZQ==", user_id="user-9", tenant_id="tenant-y"
        )

    assert suspect is False


@pytest.mark.asyncio
async def test_search_voice_invokes_replay_detector_when_enabled():
    """F11: the replay detector also runs on the 1:N /voice/search path."""
    repo = Mock()
    repo.find_similar = AsyncMock(return_value=[])

    detector = Mock()
    detector.enabled = True
    detector.check_and_record = AsyncMock(return_value=False)

    with patch.object(voice_routes, "_extract_voice_embedding",
                      AsyncMock(return_value=_unit_embedding(5))), \
         patch.object(voice_routes, "_compute_replay_fingerprint",
                      AsyncMock(return_value=np.ones(128, dtype=np.float32))), \
         patch.object(voice_routes, "get_voice_repository", return_value=repo), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):

        request = voice_routes.VoiceSearchRequest(
            voice_data="ZmFrZQ==", tenant_id="tenant-z"
        )
        await voice_routes.search_voice(request)

    detector.check_and_record.assert_awaited_once()
    _, kwargs = detector.check_and_record.await_args
    assert kwargs.get("tenant_id") == "tenant-z"
