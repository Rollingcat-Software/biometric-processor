"""Puzzle-session contract v2 (PUZZLE_TRACE_V2_ENABLED): manager + route tests.

Covers the session-level rules layered on top of the trace verifier:
scalar-only rejection, issued order, attempt cap / burn, trace-span vs the
server-observed elapsed time, difficulty floor, split-capture binding at the
verdict, flag-OFF legacy behaviour, and a full HTTP round trip
(create → submit realistic traces → verdict with binding).
"""

from __future__ import annotations

from typing import Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.puzzle import get_puzzle_session_manager, router as puzzle_router
from app.api.schemas.active_liveness import ChallengeType as C
from app.application.services.puzzle_session_manager import PuzzleSessionManager
from app.application.services.puzzle_trace_verifier import FACE_TRACE_INDICES
from tests.unit.application.services import puzzle_trace_factory as F

USER, TENANT = "user-1", "tenant-1"


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


TRACES = {
    C.BLINK: F.blink_trace,
    C.TURN_LEFT: lambda: F.turn_trace(-25),
    C.OPEN_MOUTH: lambda: F.mouth_trace(1.0),
    C.WAVE: F.wave_trace,
    C.NOD: F.nod_trace,
}


def _mgr(clock: FakeClock, v2: bool = True) -> PuzzleSessionManager:
    return PuzzleSessionManager(trace_v2_enabled=v2, clock=clock)


def _session(mgr: PuzzleSessionManager, actions: List[C], difficulty: str = "standard"):
    s = mgr.create_session(
        user_id=USER, tenant_id=TENANT, allowed_challenge_types=actions,
        count=len(actions), difficulty=difficulty,
    )
    # Pin a deterministic issued order for the test.
    for c, a in zip(s.challenges, actions):
        c.action = a
        c.params = {}
    return s


def _submit(mgr, sid, action, trace=None, metrics=None):
    return mgr.submit_challenge(
        sid, action=action, metrics=metrics or {}, start_timestamp_ms=1.0,
        end_timestamp_ms=2.0, confidence=0.9, trace=trace,
    )


def test_flag_off_keeps_legacy_scalar_path() -> None:
    clock = FakeClock()
    mgr = _mgr(clock, v2=False)
    s = _session(mgr, [C.BLINK])
    assert s.trace_contract is None
    assert _submit(mgr, s.session_id, C.BLINK, metrics={"ear": 0.1}) == (True, None)


def test_v2_scalar_only_submission_rejected() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.OPEN_MOUTH])
    clock.advance(5)
    # A forged passing scalar is no longer accepted on its own.
    assert _submit(mgr, s.session_id, C.BLINK, metrics={"ear": 0.05}) == (False, "TRACE_REQUIRED")


def test_v2_forged_scalar_with_genuine_but_wrong_trace_rejected() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.OPEN_MOUTH])
    clock.advance(5)
    still = F.face_trace([(0, {}), (1200, {})])
    ok, code = _submit(mgr, s.session_id, C.BLINK, trace=still, metrics={"ear": 0.05})
    assert not ok and code == "EYE_NOT_CLOSED"


def test_v2_genuine_traces_in_order_then_verdict_passes() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.OPEN_MOUTH])
    clock.advance(3)
    assert _submit(mgr, s.session_id, C.BLINK, trace=TRACES[C.BLINK]()) == (True, None)
    clock.advance(3)
    assert _submit(mgr, s.session_id, C.OPEN_MOUTH, trace=TRACES[C.OPEN_MOUTH]()) == (True, None)
    assert mgr.verdict(s.session_id, user_id=USER, tenant_id=TENANT) == (True, None)


def test_v2_out_of_order_rejected() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.OPEN_MOUTH])
    clock.advance(3)
    ok, code = _submit(mgr, s.session_id, C.OPEN_MOUTH, trace=TRACES[C.OPEN_MOUTH]())
    assert (ok, code) == (False, "OUT_OF_ORDER")


def test_v2_action_not_issued_rejected() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.OPEN_MOUTH])
    clock.advance(3)
    assert _submit(mgr, s.session_id, C.NOD, trace=TRACES[C.NOD]()) == (False, "ACTION_NOT_ISSUED")


def test_v2_trace_longer_than_server_elapsed_rejected() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.TURN_LEFT, C.BLINK])
    clock.advance(0.1)  # a 1.9 s trace cannot have been performed in 0.1 s
    assert _submit(mgr, s.session_id, C.TURN_LEFT, trace=TRACES[C.TURN_LEFT]()) == (
        False,
        "TRACE_LONGER_THAN_ELAPSED",
    )


def test_v2_attempt_cap_burns_session() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.OPEN_MOUTH])
    clock.advance(5)
    still = F.face_trace([(0, {}), (1200, {})])
    for _ in range(PuzzleSessionManager.MAX_ATTEMPTS_PER_CHALLENGE):
        assert _submit(mgr, s.session_id, C.BLINK, trace=still)[0] is False
    # Even a genuine trace is refused now, and the verdict fails.
    assert _submit(mgr, s.session_id, C.BLINK, trace=TRACES[C.BLINK]()) == (False, "SESSION_FAILED")
    assert mgr.verdict(s.session_id, user_id=USER, tenant_id=TENANT) == (False, "SESSION_FAILED")


def test_v2_difficulty_sets_minimum_challenge_count() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    hard = mgr.create_session(
        user_id=USER, tenant_id=TENANT, allowed_challenge_types=[C.BLINK, C.NOD, C.WAVE, C.SMILE],
        count=1, difficulty="hard",
    )
    assert len(hard.challenges) == 3
    unknown = mgr.create_session(
        user_id=USER, tenant_id=TENANT, allowed_challenge_types=[C.BLINK, C.NOD],
        count=1, difficulty="bogus",
    )
    assert len(unknown.challenges) == 2  # unknown → standard floor
    legacy = _mgr(clock, v2=False).create_session(
        user_id=USER, tenant_id=TENANT, allowed_challenge_types=[C.BLINK, C.NOD],
        count=1, difficulty="hard",
    )
    assert len(legacy.challenges) == 1  # v1 unchanged


def _binding_from(trace: Dict, k: int = 4) -> Dict:
    fr = trace["frames"][k]
    return {"t": fr["t"], "f": list(fr["f"])}


def test_v2_verdict_binding_inside_window_passes() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.WAVE])
    blink = TRACES[C.BLINK]()
    clock.advance(3)
    assert _submit(mgr, s.session_id, C.BLINK, trace=blink) == (True, None)
    clock.advance(3)
    assert _submit(mgr, s.session_id, C.WAVE, trace=TRACES[C.WAVE]()) == (True, None)
    assert mgr.verdict(
        s.session_id, user_id=USER, tenant_id=TENANT,
        require_identity_binding=True, binding_frame=_binding_from(blink),
    ) == (True, None)


@pytest.mark.parametrize(
    "binding,code",
    [
        (None, "BINDING_FRAME_REQUIRED"),
        ("outside", "BINDING_OUTSIDE_WINDOW"),
        ("other_face", "BINDING_GEOMETRY_MISMATCH"),
    ],
)
def test_v2_verdict_binding_rejections(binding, code) -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.BLINK, C.WAVE])
    blink = TRACES[C.BLINK]()
    clock.advance(3)
    _submit(mgr, s.session_id, C.BLINK, trace=blink)
    clock.advance(3)
    wave = TRACES[C.WAVE]()
    _submit(mgr, s.session_id, C.WAVE, trace=wave)
    if binding == "outside":
        binding = _binding_from(blink)
        binding["t"] = blink["frames"][-1]["t"] + 5_000
    elif binding == "other_face":
        binding = _binding_from(blink)
        binding["f"] = F.encode(F.face_points(cx=250, cy=200, px_per_cm=18.0, yaw=5))
    ok, reason = mgr.verdict(
        s.session_id, user_id=USER, tenant_id=TENANT,
        require_identity_binding=True, binding_frame=binding,
    )
    assert (ok, reason) == (False, code)
    # Single-use still holds after a binding failure.
    assert mgr.verdict(s.session_id, user_id=USER, tenant_id=TENANT)[0] is False


def test_v2_binding_ignored_when_not_requested() -> None:
    clock = FakeClock()
    mgr = _mgr(clock)
    s = _session(mgr, [C.WAVE, C.OPEN_MOUTH])
    clock.advance(3)
    _submit(mgr, s.session_id, C.WAVE, trace=TRACES[C.WAVE]())
    clock.advance(3)
    _submit(mgr, s.session_id, C.OPEN_MOUTH, trace=TRACES[C.OPEN_MOUTH]())
    assert mgr.verdict(s.session_id, user_id=USER, tenant_id=TENANT) == (True, None)


# ---------------------------------------------------------------------------
# HTTP round trip (routes + schemas)
# ---------------------------------------------------------------------------


@pytest.fixture()
def v2_client():
    clock = FakeClock()
    mgr = PuzzleSessionManager(trace_v2_enabled=True, clock=clock)
    app = FastAPI()
    app.include_router(puzzle_router, prefix="/api/v1")
    app.dependency_overrides[get_puzzle_session_manager] = lambda: mgr
    with TestClient(app) as c:
        yield c, clock


def test_http_round_trip_v2_with_binding(v2_client) -> None:
    client, clock = v2_client
    created = client.post(
        "/api/v1/liveness/puzzle-session",
        json={"tenant_id": TENANT, "user_id": USER,
              "allowed_challenge_types": ["blink", "turn_left", "wave"], "count": 3},
    ).json()
    assert created["trace_contract"] == "v2"
    assert created["trace_face_indices"] == list(FACE_TRACE_INDICES)
    sid = created["session_id"]
    traces = {"blink": F.blink_trace(), "turn_left": F.turn_trace(-25), "wave": F.wave_trace()}
    for ch in created["challenges"]:
        action = ch["action"]
        clock.advance(4)
        body = {
            "action": action, "metrics": {}, "start_timestamp_ms": 1.0,
            "end_timestamp_ms": 2.0, "confidence": 0.9, "trace": traces[action],
        }
        res = client.post(f"/api/v1/liveness/puzzle-session/{sid}/challenge", json=body)
        assert res.status_code == 200, res.text
        assert res.json()["verified"] is True, res.json()
    verdict = client.post(
        f"/api/v1/liveness/puzzle-session/{sid}/verdict",
        json={"user_id": USER, "tenant_id": TENANT, "require_identity_binding": True,
              "binding_frame": _binding_from(traces["blink"])},
    )
    assert verdict.status_code == 200
    assert verdict.json() == {"verified": True}


def test_http_v2_scalar_submit_rejected(v2_client) -> None:
    client, clock = v2_client
    created = client.post(
        "/api/v1/liveness/puzzle-session",
        json={"tenant_id": TENANT, "user_id": USER, "allowed_challenge_types": ["blink"], "count": 1,
              "difficulty": "easy"},
    ).json()
    clock.advance(2)
    res = client.post(
        f"/api/v1/liveness/puzzle-session/{created['session_id']}/challenge",
        json={"action": "blink", "metrics": {"ear": 0.05}, "start_timestamp_ms": 1.0,
              "end_timestamp_ms": 900.0, "confidence": 0.9},
    )
    assert res.json() == {"verified": False, "action": "blink", "reason_code": "TRACE_REQUIRED"}


def test_http_v2_schema_rejects_oversized_or_malformed_trace(v2_client) -> None:
    client, clock = v2_client
    created = client.post(
        "/api/v1/liveness/puzzle-session",
        json={"tenant_id": TENANT, "user_id": USER, "allowed_challenge_types": ["blink"], "count": 1},
    ).json()
    sid = created["session_id"]
    bad = F.blink_trace()
    bad["frames"][0]["f"] = bad["frames"][0]["f"][:30]
    res = client.post(
        f"/api/v1/liveness/puzzle-session/{sid}/challenge",
        json={"action": "blink", "metrics": {}, "start_timestamp_ms": 1.0, "end_timestamp_ms": 2.0,
              "confidence": 0.9, "trace": bad},
    )
    assert res.status_code == 422
    huge = F.face_trace([(0, {}), (8500, {})])
    res = client.post(
        f"/api/v1/liveness/puzzle-session/{sid}/challenge",
        json={"action": "blink", "metrics": {}, "start_timestamp_ms": 1.0, "end_timestamp_ms": 2.0,
              "confidence": 0.9, "trace": huge},
    )
    assert res.status_code == 422


def test_http_flag_off_create_has_no_trace_contract() -> None:
    mgr = PuzzleSessionManager(trace_v2_enabled=False)
    app = FastAPI()
    app.include_router(puzzle_router, prefix="/api/v1")
    app.dependency_overrides[get_puzzle_session_manager] = lambda: mgr
    with TestClient(app) as c:
        body = c.post(
            "/api/v1/liveness/puzzle-session",
            json={"tenant_id": TENANT, "user_id": USER, "allowed_challenge_types": ["blink"], "count": 1},
        ).json()
    assert body["trace_contract"] is None
    assert body["trace_face_indices"] is None
