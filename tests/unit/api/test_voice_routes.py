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


def _avg_centroid(*seeds: int) -> np.ndarray:
    """A centroid the way the default enroll path builds it: AVG of unit vectors.

    The mean of several unit-norm speaker embeddings has norm < 1 and shrinks as
    the samples diverge — exactly the non-normalized centroid the repository
    persists via ``AVG(embedding)::vector``. Used to reproduce the P1-10
    confidence-decay regression.
    """
    vecs = [_unit_embedding(s) for s in seeds]
    return np.mean(vecs, axis=0).astype(np.float32)


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


# ---------------------------------------------------------------------------
# P1-10 — voice verify confidence must be a true cosine similarity, invariant
# to the (non-normalized) stored centroid's norm.
# ---------------------------------------------------------------------------


def _direct_dot(a: np.ndarray, b: np.ndarray) -> float:
    """The OLD verify behavior: raw dot product, no centroid normalization."""
    return max(0.0, min(1.0, float(np.dot(a, b))))


async def _run_verify(probe: np.ndarray, centroid: np.ndarray) -> "voice_routes.BiometricResponse":
    """Drive verify_voice with a fixed probe + stored centroid (replay off)."""
    repo = Mock()
    repo.find_by_user_id = AsyncMock(return_value=centroid)
    detector = Mock()
    detector.enabled = False
    with patch.object(voice_routes, "_extract_voice_embedding",
                      AsyncMock(return_value=probe)), \
         patch.object(voice_routes, "get_voice_repository", return_value=repo), \
         patch.object(voice_routes, "get_voice_replay_detector", return_value=detector):
        req = voice_routes.VoiceRequest(user_id="u", voice_data="ZmFrZQ==")
        return await voice_routes.verify_voice(req)


@pytest.mark.asyncio
async def test_verify_confidence_is_true_cosine_not_raw_dot():
    """Confidence must be the cosine of probe·centroid_direction, not the raw dot.

    The default enroll path stores ``AVG(embedding)`` whose norm is < 1, so a
    raw ``np.dot(probe, centroid)`` under-reports by exactly ``||centroid||``.
    After the P1-10 fix the centroid is L2-normalized at verify time, so the
    reported confidence equals the genuine cosine similarity and is strictly
    HIGHER than the old raw-dot value whenever the centroid was not unit-norm.
    """
    probe = _unit_embedding(0)
    # AVG of unit vectors → norm < 1 (the exact shape the repository persists).
    centroid = _avg_centroid(0, 1, 2)
    centroid_norm = float(np.linalg.norm(centroid))
    assert centroid_norm < 1.0  # precondition: this is the decaying-norm case

    res = await _run_verify(probe, centroid)

    true_cosine = max(0.0, min(1.0, float(np.dot(probe, centroid / centroid_norm))))
    old_raw_dot = _direct_dot(probe, centroid)

    # Fixed path reports the true cosine ...
    assert res.confidence == pytest.approx(true_cosine, abs=1e-3)
    # ... which is strictly higher than the buggy raw-dot value.
    assert res.confidence > old_raw_dot
    # The raw dot equals cosine * norm, so the gap is the norm shortfall.
    assert old_raw_dot == pytest.approx(true_cosine * centroid_norm, abs=1e-3)


@pytest.mark.asyncio
async def test_verify_confidence_invariant_to_centroid_magnitude():
    """Confidence depends only on the centroid DIRECTION, not its magnitude.

    Models the decay driver directly: the SAME centroid direction stored at two
    different magnitudes (||c||=0.9 "2 enrollments" vs ||c||=0.45 "5 divergent
    enrollments"). Under the old raw dot the reported confidence halved with the
    norm; after the fix it is identical for both because the centroid is
    normalized before the cosine.
    """
    probe = _unit_embedding(0)
    direction = _avg_centroid(0, 1)  # an arbitrary, fixed, sub-unit direction
    direction = (direction / np.linalg.norm(direction)).astype(np.float32)

    centroid_big = (direction * 0.90).astype(np.float32)   # ~2 enrollments
    centroid_small = (direction * 0.45).astype(np.float32)  # ~5 enrollments

    conf_big = (await _run_verify(probe, centroid_big)).confidence
    conf_small = (await _run_verify(probe, centroid_small)).confidence

    true_cosine = max(0.0, min(1.0, float(np.dot(probe, direction))))

    # Fixed: both report the same true cosine regardless of stored magnitude.
    assert conf_big == pytest.approx(true_cosine, abs=1e-3)
    assert conf_small == pytest.approx(true_cosine, abs=1e-3)
    assert conf_big == pytest.approx(conf_small, abs=1e-3)

    # The OLD raw dot would have decayed in lockstep with the shrinking norm.
    assert _direct_dot(probe, centroid_small) < _direct_dot(probe, centroid_big)


@pytest.mark.asyncio
async def test_verify_genuine_user_not_false_rejected_for_subunit_centroid():
    """A perfect-direction match with a sub-0.65 norm must still verify.

    Construct the exact false-reject the bug produces: the centroid points in
    the SAME direction as the probe (true cosine = 1.0) but its stored norm is
    0.60 — so the old ``np.dot`` returns 0.60 < 0.65 and FALSE-REJECTS a genuine
    user. The fix normalizes the centroid first → confidence 1.0, verified.
    """
    probe = _unit_embedding(3)
    centroid = (probe * 0.60).astype(np.float32)  # same direction, norm 0.60

    # Precondition: the OLD path would false-reject (raw dot 0.60 < 0.65).
    assert _direct_dot(probe, centroid) == pytest.approx(0.60, abs=1e-3)
    assert _direct_dot(probe, centroid) < 0.65

    res = await _run_verify(probe, centroid)

    assert res.confidence == pytest.approx(1.0, abs=1e-3)
    assert res.confidence >= 0.65
    assert res.verified is True
