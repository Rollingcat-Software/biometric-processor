"""Unit tests for the face enrollment-existence probe (login triage F2/F7/F9).

``GET /face/{user_id}/exists`` is the cheap, authoritative probe that
identity-core-api's ``EnrollmentHealthService`` now calls to learn whether a
user REALLY has a face template — replacing the prior "trust if the biometric
service is reachable" fake that reported FACE/VOICE as always-enrolled.

These tests drive the route handler coroutine directly (rather than through a
full TestClient) to avoid the asyncio loop-poisoning that the
TestClient-in-test-body pattern suffers from (same approach as
``test_voice_routes.py``). The embedding repository is patched per-test, so no
DB / ML stack is required.
"""

import sys
import types
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _import_verification_routes():
    """Import app.api.routes.verification without leaking a container stub.

    In the Docker/CI image the real container imports cleanly, so the plain
    import succeeds. In a lean environment lacking the heavy ML stack, install a
    minimal container stub just long enough to satisfy verification.py's
    ``from app.core.container import``, then restore sys.modules so other test
    modules see the real container (mirrors the voice-route test helper).
    """
    try:
        from app.api.routes import verification as _verification
        return _verification
    except Exception:
        pass

    _had_container = "app.core.container" in sys.modules
    _saved_container = sys.modules.get("app.core.container")
    _stub_container = types.ModuleType("app.core.container")
    for _name in (
        "get_check_liveness_use_case",
        "get_client_embedding_observation_repository",
        "get_embedding_repository",
        "get_file_storage",
        "get_verify_face_use_case",
    ):
        setattr(_stub_container, _name, lambda *a, **k: None)
    sys.modules["app.core.container"] = _stub_container
    try:
        from app.api.routes import verification as _verification
        return _verification
    finally:
        if _had_container:
            sys.modules["app.core.container"] = _saved_container
        else:
            sys.modules.pop("app.core.container", None)


verification_routes = _import_verification_routes()


@pytest.mark.asyncio
async def test_face_exists_true_when_enrollment_present():
    """exists=True for an enrolled user; repo.exists is consulted with the user_id."""
    repo = Mock()
    repo.exists = AsyncMock(return_value=True)

    with patch.object(verification_routes, "get_embedding_repository", return_value=repo):
        res = await verification_routes.face_exists(
            "11111111-1111-1111-1111-111111111111", tenant_id=None
        )

    repo.exists.assert_awaited_once_with("11111111-1111-1111-1111-111111111111", None)
    assert res.exists is True
    assert res.user_id == "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_face_exists_false_when_not_enrolled():
    """A definitive exists=False is returned for an un-enrolled user (no masking)."""
    repo = Mock()
    repo.exists = AsyncMock(return_value=False)

    with patch.object(verification_routes, "get_embedding_repository", return_value=repo):
        res = await verification_routes.face_exists(
            "22222222-2222-2222-2222-222222222222", tenant_id=None
        )

    assert res.exists is False
    assert res.user_id == "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_face_exists_forwards_tenant_scope():
    """A supplied tenant_id is forwarded to repo.exists (verify-path parity)."""
    repo = Mock()
    repo.exists = AsyncMock(return_value=True)

    with patch.object(verification_routes, "get_embedding_repository", return_value=repo):
        await verification_routes.face_exists(
            "33333333-3333-3333-3333-333333333333", tenant_id="tenant-x"
        )

    repo.exists.assert_awaited_once_with(
        "33333333-3333-3333-3333-333333333333", "tenant-x"
    )


@pytest.mark.asyncio
async def test_face_exists_invalid_user_id_returns_400():
    """A malformed user_id is a clean 400, not a 500."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await verification_routes.face_exists("not a uuid !!", tenant_id=None)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_face_exists_never_runs_inference():
    """The probe is a pure store lookup — it must not invoke the verify use case."""
    repo = Mock()
    repo.exists = AsyncMock(return_value=True)
    verify_uc = Mock()
    verify_uc.match_embedding = AsyncMock(side_effect=AssertionError("must not match"))

    with patch.object(verification_routes, "get_embedding_repository", return_value=repo), \
         patch.object(verification_routes, "get_verify_face_use_case", return_value=verify_uc):
        await verification_routes.face_exists(
            "44444444-4444-4444-4444-444444444444", tenant_id=None
        )

    verify_uc.match_embedding.assert_not_awaited()
