"""Server-authoritative, single-use, anti-replay puzzle SESSION manager.

CV-1 of the puzzle-as-login convergence
(docs/superpowers/plans/2026-06-12-puzzle-session-convergence.md).

Replaces the stateless ``/verify-challenge`` trust model for the auth path with a
server-issued session whose scoring state lives here (bio is the sole authority).

Trust properties enforced (all four):
  * Challenges are **server-randomized per attempt** — ``create_session`` picks
    ``count`` challenges at random from ``allowed_challenge_types``; the client
    cannot pre-record a known sequence.
  * ``session_id`` is **unguessable** (``secrets.token_urlsafe``) and short-lived
    (TTL ``DEFAULT_TTL_SECONDS`` = 300 s, matching the existing
    ``COMPLETED_SESSION_TTL_SECONDS`` for liveness sessions).
  * The session is **single-use** — ``verdict`` consumes it; a second verdict on
    the same id fails.
  * The session is **bound to ``user_id`` + ``tenant_id``** — a session issued for
    A cannot produce a verified verdict for B.

The store is an in-memory dict keyed by ``session_id`` (mirrors how
``ActiveGestureLivenessManager`` holds per-session scratch state in-process; the
auth puzzle session is intentionally process-local + ephemeral, like the other
liveness sessions). Scoring of a submitted challenge is delegated to the shared
:mod:`app.application.services.challenge_metric_scorer`, which covers BOTH the 14
face and 9 hand challenge types — so a single session spans both modalities.
"""

from __future__ import annotations

import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.api.schemas.active_liveness import ChallengeType
from app.application.services.challenge_metric_scorer import (
    metric_is_present,
    score_action_metrics,
)

logger = logging.getLogger(__name__)


@dataclass
class PuzzleChallengeState:
    """One issued challenge within a session."""

    action: ChallengeType
    params: Dict[str, Any] = field(default_factory=dict)
    completed: bool = False
    verified: bool = False


@dataclass
class PuzzleSession:
    """A server-issued puzzle session (in-memory)."""

    session_id: str
    user_id: str
    tenant_id: str
    challenges: List[PuzzleChallengeState]
    created_at: float
    expires_at: float
    consumed: bool = False

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def all_verified(self) -> bool:
        return bool(self.challenges) and all(
            c.completed and c.verified for c in self.challenges
        )

    def find_pending(self, action: ChallengeType) -> Optional[PuzzleChallengeState]:
        """First issued, not-yet-completed challenge matching ``action``."""
        for c in self.challenges:
            if c.action == action and not c.completed:
                return c
        return None


class PuzzleSessionManager:
    """In-memory, single-use, anti-replay puzzle session store + scorer."""

    # TTL for a freshly issued session, in seconds. Mirrors the existing
    # COMPLETED_SESSION_TTL_SECONDS (300) used by the liveness session repos.
    DEFAULT_TTL_SECONDS: int = 300

    # token_urlsafe byte length → ~43-char unguessable id.
    _TOKEN_BYTES: int = 32

    # Challenge actions that carry a server-issued numeric ``target`` param.
    _TARGETED_ACTIONS = (ChallengeType.FINGER_COUNT, ChallengeType.MATH)

    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self._ttl = int(ttl_seconds) if ttl_seconds is not None else self.DEFAULT_TTL_SECONDS
        self._sessions: Dict[str, PuzzleSession] = {}
        logger.info("PuzzleSessionManager initialised (ttl=%ss)", self._ttl)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create_session(
        self,
        *,
        user_id: str,
        tenant_id: str,
        allowed_challenge_types: List[ChallengeType],
        count: int,
        difficulty: Optional[str] = None,
        now: Optional[float] = None,
    ) -> PuzzleSession:
        """Create a session with ``count`` server-randomized challenges.

        Raises:
            ValueError: if ``allowed_challenge_types`` is empty or ``count`` < 1.
        """
        if not allowed_challenge_types:
            raise ValueError("allowed_challenge_types must be non-empty")
        if count < 1:
            raise ValueError("count must be >= 1")

        created_at = now if now is not None else time.time()

        # Server-randomized selection. Sample WITHOUT replacement when enough
        # distinct types are allowed; otherwise sample WITH replacement so a
        # caller can ask for more challenges than distinct allowed types.
        pool = list(allowed_challenge_types)
        if count <= len(pool):
            chosen = random.sample(pool, count)
        else:
            chosen = [random.choice(pool) for _ in range(count)]

        challenges: List[PuzzleChallengeState] = []
        for action in chosen:
            params: Dict[str, Any] = {}
            if action in self._TARGETED_ACTIONS:
                # Ask for 1..5 fingers (avoid 0=fist), mirroring the gesture manager.
                params["target"] = random.randint(1, 5)
            challenges.append(PuzzleChallengeState(action=action, params=params))

        session = PuzzleSession(
            session_id=self._new_session_id(),
            user_id=user_id,
            tenant_id=tenant_id,
            challenges=challenges,
            created_at=created_at,
            expires_at=created_at + self._ttl,
        )
        self._sessions[session.session_id] = session
        logger.info(
            "Created puzzle session %s for user=%s tenant=%s with %d challenges (%s)",
            session.session_id,
            user_id,
            tenant_id,
            len(challenges),
            ",".join(c.action.value for c in challenges),
        )
        return session

    def _new_session_id(self) -> str:
        # Collision-safe by construction (32 random bytes); loop is defensive.
        while True:
            sid = secrets.token_urlsafe(self._TOKEN_BYTES)
            if sid not in self._sessions:
                return sid

    # ------------------------------------------------------------------
    # SUBMIT (score one challenge)
    # ------------------------------------------------------------------

    def submit_challenge(
        self,
        session_id: str,
        *,
        action: ChallengeType,
        metrics: Dict[str, Any],
        start_timestamp_ms: float,
        end_timestamp_ms: float,
        confidence: float,
        now: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Score one submitted challenge against the issued session.

        Returns ``(verified, reason_code)``. ``verified`` is True only when the
        action is one of the issued + not-yet-completed challenges, a metric is
        PRESENT (metric-required on this path), and the metric + structural
        checks pass. On success the matching challenge is marked complete.

        A consumed / expired / unknown session yields ``(False, reason_code)``;
        the route maps ``SESSION_NOT_FOUND`` / ``SESSION_EXPIRED`` to HTTP 404.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return (False, "SESSION_NOT_FOUND")
        if session.consumed:
            return (False, "SESSION_CONSUMED")
        if session.is_expired(now):
            return (False, "SESSION_EXPIRED")

        challenge = session.find_pending(action)
        if challenge is None:
            # Either not issued, or already completed.
            issued = any(c.action == action for c in session.challenges)
            return (False, "ALREADY_COMPLETED" if issued else "ACTION_NOT_ISSUED")

        # Metric REQUIRED on the auth path — closes the structural-only hole.
        if not metric_is_present(action, metrics):
            return (False, "METRIC_REQUIRED")

        # Structural: timestamp monotonicity.
        if end_timestamp_ms < start_timestamp_ms:
            return (False, "TIMESTAMPS_OUT_OF_ORDER")

        # Structural: confidence floor (matches verify-challenge floor 0.5).
        if confidence < 0.5:
            return (False, "CONFIDENCE_BELOW_FLOOR")

        # Metric plausibility gate (shared scorer; consults params for target).
        rejection = score_action_metrics(action, metrics, challenge.params)
        if rejection is not None:
            reason_code, _msg = rejection
            return (False, reason_code)

        challenge.completed = True
        challenge.verified = True
        logger.info(
            "Puzzle session %s challenge %s verified (user=%s tenant=%s)",
            session_id,
            action.value,
            session.user_id,
            session.tenant_id,
        )
        return (True, None)

    # ------------------------------------------------------------------
    # VERDICT (consume, single-use)
    # ------------------------------------------------------------------

    def verdict(
        self,
        session_id: str,
        *,
        user_id: str,
        tenant_id: str,
        now: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Return the authoritative verdict and CONSUME the session (single-use).

        ``verified`` is True only when ALL of:
          * session exists and is not expired,
          * session has not already been consumed,
          * owner ``user_id`` + ``tenant_id`` match the requester,
          * every issued challenge was completed AND validated.

        The session is consumed (marked + removed) whenever it exists and is not
        expired — including on a False verdict — so a captured trace cannot be
        replayed against the same id. Unknown / expired sessions return
        ``(False, "SESSION_NOT_FOUND" | "SESSION_EXPIRED")`` (route → HTTP 404).
        """
        session = self._sessions.get(session_id)
        if session is None:
            return (False, "SESSION_NOT_FOUND")
        if session.consumed:
            # Already used once — anti-replay.
            return (False, "SESSION_CONSUMED")
        if session.is_expired(now):
            # Expire-and-evict; treat as not found by the route (404).
            self._sessions.pop(session_id, None)
            return (False, "SESSION_EXPIRED")

        # From here the session is live and unconsumed: consume it exactly once,
        # regardless of the boolean outcome (single-use is unconditional).
        session.consumed = True
        self._sessions.pop(session_id, None)

        if session.user_id != user_id or session.tenant_id != tenant_id:
            logger.warning(
                "Puzzle verdict owner mismatch session=%s issued_for=(%s,%s) requested_by=(%s,%s)",
                session_id,
                session.user_id,
                session.tenant_id,
                user_id,
                tenant_id,
            )
            return (False, "OWNER_MISMATCH")

        if not session.all_verified():
            return (False, "CHALLENGES_INCOMPLETE")

        logger.info(
            "Puzzle session %s verdict=PASS (user=%s tenant=%s, consumed)",
            session_id,
            user_id,
            tenant_id,
        )
        return (True, None)

    # ------------------------------------------------------------------
    # Introspection / maintenance
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[PuzzleSession]:
        return self._sessions.get(session_id)

    def purge_expired(self, now: Optional[float] = None) -> int:
        """Drop expired sessions; return the number removed."""
        ts = now if now is not None else time.time()
        stale = [sid for sid, s in self._sessions.items() if s.is_expired(ts)]
        for sid in stale:
            self._sessions.pop(sid, None)
        return len(stale)


__all__ = [
    "PuzzleSessionManager",
    "PuzzleSession",
    "PuzzleChallengeState",
]
