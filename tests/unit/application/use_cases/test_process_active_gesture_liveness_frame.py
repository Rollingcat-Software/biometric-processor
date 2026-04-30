"""Unit tests for ProcessActiveGestureLivenessFrameUseCase.

Covers P6.9 #5 (modality guard) — sending a face-modality session to the
gesture frame endpoint must raise InvalidModalityError, not the generic
SessionNotFound.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Awaitable, Callable, Optional
from unittest.mock import Mock

# Mock native ML deps that aren't installed in minimal CI images. Matches
# tests/integration/test_gesture_liveness_session.py.
sys.modules.setdefault("cv2", Mock())
sys.modules.setdefault("deepface", Mock())
sys.modules.setdefault("deepface.DeepFace", Mock())

import pytest

from app.api.schemas.active_liveness import (
    ActiveLivenessSession,
    ChallengeStatus,
    ChallengeType,
)
from app.api.schemas.active_liveness import Challenge
from app.api.schemas.gesture_liveness import GestureFramePayload, HandLandmark
from app.application.use_cases.process_active_gesture_liveness_frame import (
    ActiveLivenessSessionExpiredError,
    InvalidModalityError,
    ProcessActiveGestureLivenessFrameUseCase,
)


class _FakeRepo:
    """In-memory test double for IActiveLivenessSessionRepository."""

    def __init__(self, session: Optional[ActiveLivenessSession]) -> None:
        self._session = session
        self.deleted: list[str] = []

    async def mutate(
        self, session_id: str, fn: Callable[[ActiveLivenessSession], Awaitable[Any]]
    ) -> Any:
        if self._session is None or self._session.session_id != session_id:
            return None
        return await fn(self._session)

    async def delete(self, session_id: str) -> None:
        self.deleted.append(session_id)


class _FakeManager:
    """Minimal manager stub — only what the use case actually calls."""

    def is_expired(self, session: ActiveLivenessSession, now: float) -> bool:
        return now >= session.expires_at

    def build_response(self, session, detection=None, feedback=""):
        # Not exercised on the modality-guard path.
        return None

    async def process_frame(self, session, landmarks_payload):
        return None


def _make_session(modality: str = "gesture") -> ActiveLivenessSession:
    now = time.time()
    return ActiveLivenessSession(
        session_id="sess-1",
        modality=modality,
        challenges=[
            Challenge(
                type=ChallengeType.FINGER_COUNT,
                instruction="show 3 fingers",
                timeout_seconds=10.0,
            )
        ],
        current_challenge_index=0,
        started_at=now,
        expires_at=now + 60.0,
        last_activity_at=now,
        current_challenge_started_at=now,
    )


def _payload() -> GestureFramePayload:
    # 21 dummy hand landmarks (geometry doesn't matter — guard runs first).
    landmarks = [HandLandmark(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    return GestureFramePayload(
        frame_time_ms=0,
        landmarks_right=landmarks,
        landmarks_left=None,
        tremor_variance=0.01,
        brightness_std=0.5,
    )


@pytest.mark.asyncio
async def test_face_modality_session_raises_invalid_modality():
    """Face session sent to gesture endpoint -> InvalidModalityError, not 404."""

    session = _make_session(modality="face")
    repo = _FakeRepo(session)
    use_case = ProcessActiveGestureLivenessFrameUseCase(
        manager=_FakeManager(), session_repository=repo
    )

    with pytest.raises(InvalidModalityError) as exc_info:
        await use_case.execute(session_id="sess-1", payload=_payload())

    assert "face" in str(exc_info.value).lower()
    # Repo mustn't be deleted — the session is fine, the caller used the wrong endpoint.
    assert repo.deleted == []


@pytest.mark.asyncio
async def test_gesture_modality_session_passes_guard():
    """Gesture session must NOT raise InvalidModalityError."""

    session = _make_session(modality="gesture")
    repo = _FakeRepo(session)
    use_case = ProcessActiveGestureLivenessFrameUseCase(
        manager=_FakeManager(), session_repository=repo
    )

    # The fake manager returns None from process_frame; the use case treats
    # a None response as session-not-found. We only care that the guard did
    # not fire — InvalidModalityError must NOT be raised.
    try:
        await use_case.execute(session_id="sess-1", payload=_payload())
    except InvalidModalityError:
        pytest.fail("Gesture-modality session must not trigger InvalidModalityError")
    except Exception:
        pass  # any other exception is fine for this test


@pytest.mark.asyncio
async def test_expired_session_still_raises_expired_not_modality():
    """Expiry check fires BEFORE modality guard (preserves 410-Gone semantics)."""

    session = _make_session(modality="face")
    session.expires_at = time.time() - 5.0  # already expired
    repo = _FakeRepo(session)
    use_case = ProcessActiveGestureLivenessFrameUseCase(
        manager=_FakeManager(), session_repository=repo
    )

    with pytest.raises(ActiveLivenessSessionExpiredError):
        await use_case.execute(session_id="sess-1", payload=_payload())
    assert repo.deleted == ["sess-1"]
