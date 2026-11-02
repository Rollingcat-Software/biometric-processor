"""Attested puzzle binding: canonical trace digest + verdict `trace_digest`.

The golden vector below is shared with the Android client
(client-apps ``PuzzleTraceDigestTest``). Changing the encoding requires updating
both sides and identity-core-api ``docs/ATTESTED_PUZZLE_BINDING.md``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.puzzle import get_puzzle_session_manager
from app.api.routes.puzzle import router as puzzle_router
from app.api.schemas.active_liveness import ChallengeType as C
from app.application.services.puzzle_session_manager import PuzzleSessionManager
from app.application.services.puzzle_trace_digest import (
    challenge_trace_digest,
    session_trace_digest,
)
from tests.unit.application.services import puzzle_trace_factory as F

USER, TENANT = "user-1", "tenant-1"

GOLDEN_TRACE = {
    "version": 2,
    "frame_width": 640,
    "frame_height": 480,
    "frames": [
        {"t": 0, "f": list(range(96)), "h": None},
        {"t": 40, "f": None, "h": [-i for i in range(63)]},
        {"t": 2**53, "f": None, "h": None},
    ],
}
GOLDEN_BLINK = "6c30c5f05962a473576a2d514dea245bbc5954addaadf8d79231bfe4fdccb8b8"
GOLDEN_WAVE = "9d27d609842afc02754e30221d3b0441b6b17812ba71095bc67ce753b1f09a25"
GOLDEN_SESSION = "8843a760a10fd102f3cf6206ec69437632f5895072999f5cdba5c3230193364c"


def test_golden_vector() -> None:
    a = challenge_trace_digest("blink", GOLDEN_TRACE)
    b = challenge_trace_digest("wave", GOLDEN_TRACE)
    assert a.hex() == GOLDEN_BLINK
    assert b.hex() == GOLDEN_WAVE
    assert session_trace_digest([a, b]) == GOLDEN_SESSION


def test_missing_h_key_equals_explicit_none() -> None:
    no_h = {**GOLDEN_TRACE, "frames": [{"t": 0, "f": list(range(96))}]}
    explicit = {**GOLDEN_TRACE, "frames": [{"t": 0, "f": list(range(96)), "h": None}]}
    assert challenge_trace_digest("blink", no_h) == challenge_trace_digest("blink", explicit)


def test_any_change_changes_digest() -> None:
    base = challenge_trace_digest("blink", GOLDEN_TRACE)
    moved = {**GOLDEN_TRACE, "frames": [dict(GOLDEN_TRACE["frames"][0], t=1)] + GOLDEN_TRACE["frames"][1:]}
    assert challenge_trace_digest("blink", moved) != base
    assert challenge_trace_digest("smile", GOLDEN_TRACE) != base
    a = challenge_trace_digest("blink", GOLDEN_TRACE)
    b = challenge_trace_digest("wave", GOLDEN_TRACE)
    assert session_trace_digest([a, b]) != session_trace_digest([b, a])


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _two_challenge_session(mgr: PuzzleSessionManager):
    s = mgr.create_session(
        user_id=USER, tenant_id=TENANT, allowed_challenge_types=[C.BLINK, C.OPEN_MOUTH],
        count=2, difficulty="standard",
    )
    for c, a in zip(s.challenges, [C.BLINK, C.OPEN_MOUTH]):
        c.action = a
        c.params = {}
    return s


def _submit(mgr, clock, sid, action, trace):
    clock.now += 3
    return mgr.submit_challenge(
        sid, action=action, metrics={}, start_timestamp_ms=1.0, end_timestamp_ms=2.0,
        confidence=0.9, trace=trace,
    )


def test_verdict_returns_digest_of_accepted_traces_in_issued_order() -> None:
    clock = FakeClock()
    mgr = PuzzleSessionManager(trace_v2_enabled=True, clock=clock)
    s = _two_challenge_session(mgr)
    blink, mouth = F.blink_trace(), F.mouth_trace(1.0)
    # A rejected attempt (still face) must NOT enter the digest.
    still = F.face_trace([(0, {}), (1200, {})])
    assert _submit(mgr, clock, s.session_id, C.BLINK, still)[0] is False
    assert _submit(mgr, clock, s.session_id, C.BLINK, blink) == (True, None)
    assert _submit(mgr, clock, s.session_id, C.OPEN_MOUTH, mouth) == (True, None)
    res, digest = mgr.verdict_with_trace_digest(s.session_id, user_id=USER, tenant_id=TENANT)
    assert res.verified is True
    assert digest == session_trace_digest(
        [challenge_trace_digest("blink", blink), challenge_trace_digest("open_mouth", mouth)]
    )


def test_no_digest_on_failed_verdict_or_v1() -> None:
    clock = FakeClock()
    mgr = PuzzleSessionManager(trace_v2_enabled=True, clock=clock)
    s = _two_challenge_session(mgr)
    assert _submit(mgr, clock, s.session_id, C.BLINK, F.blink_trace())[0] is True
    res, digest = mgr.verdict_with_trace_digest(s.session_id, user_id=USER, tenant_id=TENANT)
    assert res.verified is False and digest is None

    mgr1 = PuzzleSessionManager(trace_v2_enabled=False, clock=clock)
    s1 = mgr1.create_session(
        user_id=USER, tenant_id=TENANT, allowed_challenge_types=[C.BLINK], count=1,
    )
    s1.challenges[0].action = C.BLINK
    s1.challenges[0].params = {}
    assert mgr1.submit_challenge(
        s1.session_id, action=C.BLINK, metrics={"ear": 0.1}, start_timestamp_ms=1.0,
        end_timestamp_ms=2.0, confidence=0.9,
    ) == (True, None)
    res1, digest1 = mgr1.verdict_with_trace_digest(s1.session_id, user_id=USER, tenant_id=TENANT)
    assert res1.verified is True and digest1 is None


@pytest.fixture()
def client_and_mgr():
    clock = FakeClock()
    mgr = PuzzleSessionManager(trace_v2_enabled=True, clock=clock)
    app = FastAPI()
    app.include_router(puzzle_router, prefix="/api/v1")
    app.dependency_overrides[get_puzzle_session_manager] = lambda: mgr
    with TestClient(app) as c:
        yield c, mgr, clock


def _http_pass(client, clock, include: bool | None):
    created = client.post(
        "/api/v1/liveness/puzzle-session",
        json={"tenant_id": TENANT, "user_id": USER, "allowed_challenge_types": ["blink"], "count": 1,
              "difficulty": "easy"},
    ).json()
    sid = created["session_id"]
    traces = []
    for ch in created["challenges"]:
        clock.now += 4
        trace = F.blink_trace()
        res = client.post(
            f"/api/v1/liveness/puzzle-session/{sid}/challenge",
            json={"action": ch["action"], "metrics": {}, "start_timestamp_ms": 1.0,
                  "end_timestamp_ms": 2.0, "confidence": 0.9, "trace": trace},
        )
        assert res.json()["verified"] is True, res.json()
        traces.append((ch["action"], trace))
    body = {"user_id": USER, "tenant_id": TENANT}
    if include is not None:
        body["include_trace_digest"] = include
    return client.post(f"/api/v1/liveness/puzzle-session/{sid}/verdict", json=body).json(), traces


def test_http_digest_only_when_requested(client_and_mgr) -> None:
    client, _mgr, clock = client_and_mgr
    body, _ = _http_pass(client, clock, None)
    assert body == {"verified": True}
    body, _ = _http_pass(client, clock, False)
    assert body == {"verified": True}
    body, traces = _http_pass(client, clock, True)
    # The route digests the pydantic-dumped trace; it must equal the digest of
    # the raw wire dict the client sent (f/h None vs missing are equivalent).
    expected = session_trace_digest([challenge_trace_digest(a, t) for a, t in traces])
    assert body == {"verified": True, "trace_digest": expected}
