"""Per-session rate limiter for proctoring."""

import logging
import time
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)


# Prometheus metrics
RATE_LIMIT_CHECKS = Counter(
    "biometric_proctor_rate_limit_checks_total",
    "Rate limit check count",
    ["result"],
)

RATE_LIMIT_VIOLATIONS = Counter(
    "biometric_proctor_rate_limit_violations_total",
    "Rate limit violations",
    ["session_status"],
)

FRAMES_PER_SESSION = Histogram(
    "biometric_proctor_frames_per_session",
    "Frames submitted per session per minute",
    buckets=(10, 20, 30, 40, 50, 60, 80, 100, 150),
)


@dataclass
class SessionRateLimitConfig:
    """Per-session rate limiting configuration."""

    max_frames_per_second: float = 2.0
    max_frames_per_minute: int = 60
    burst_allowance: int = 5
    cooldown_seconds: int = 10


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    remaining: int
    retry_after: Optional[float] = None
    is_suspicious: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "allowed": self.allowed,
            "remaining": self.remaining,
            "retry_after": self.retry_after,
            "is_suspicious": self.is_suspicious,
        }


class SessionRateLimiter:
    """Per-session rate limiter using sliding window algorithm."""

    def __init__(
        self,
        redis_client,
        config: Optional[SessionRateLimitConfig] = None,
    ):
        self.redis = redis_client
        self.config = config or SessionRateLimitConfig()

    async def check(self, session_id: UUID) -> RateLimitResult:
        """Check if frame submission is allowed for session."""
        now = time.time()
        key_second = f"proctor:rate:{session_id}:second"
        key_minute = f"proctor:rate:{session_id}:minute"
        key_violations = f"proctor:rate:{session_id}:violations"

        # Check cooldown from previous violations
        violations = await self.redis.get(key_violations)
        violations = int(violations) if violations else 0

        if violations > 0:
            ttl = await self.redis.ttl(key_violations)
            if ttl > 0:
                RATE_LIMIT_CHECKS.labels(result="denied").inc()
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=ttl,
                    is_suspicious=True,
                )

        # Sliding window check for per-second limit
        second_count = await self._sliding_window_count(key_second, now, 1.0)
        max_per_second = self.config.max_frames_per_second + self.config.burst_allowance

        if second_count >= max_per_second:
            await self._record_violation(session_id)
            is_suspicious = second_count > self.config.max_frames_per_second * 2
            RATE_LIMIT_CHECKS.labels(result="denied").inc()
            RATE_LIMIT_VIOLATIONS.labels(
                session_status="suspicious" if is_suspicious else "normal"
            ).inc()
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=1.0,
                is_suspicious=is_suspicious,
            )

        # Sliding window check for per-minute limit
        minute_count = await self._sliding_window_count(key_minute, now, 60.0)
        max_per_minute = self.config.max_frames_per_minute + self.config.burst_allowance

        if minute_count >= max_per_minute:
            await self._record_violation(session_id)
            is_suspicious = minute_count > self.config.max_frames_per_minute * 1.5
            RATE_LIMIT_CHECKS.labels(result="denied").inc()
            RATE_LIMIT_VIOLATIONS.labels(
                session_status="suspicious" if is_suspicious else "normal"
            ).inc()
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=60.0 - (now % 60),
                is_suspicious=is_suspicious,
            )

        # Record this request
        pipe = self.redis.pipeline()
        pipe.zadd(key_second, {str(now): now})
        pipe.expire(key_second, 2)
        pipe.zadd(key_minute, {str(now): now})
        pipe.expire(key_minute, 120)
        await pipe.execute()

        remaining = self.config.max_frames_per_minute - minute_count - 1
        RATE_LIMIT_CHECKS.labels(result="allowed").inc()
        FRAMES_PER_SESSION.observe(minute_count + 1)

        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            is_suspicious=False,
        )

    async def _sliding_window_count(
        self,
        key: str,
        now: float,
        window_seconds: float,
    ) -> int:
        """Count requests in sliding window."""
        window_start = now - window_seconds

        # Remove old entries and count current
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        results = await pipe.execute()

        return results[1] if len(results) > 1 else 0

    async def _record_violation(self, session_id: UUID) -> None:
        """Record rate limit violation."""
        key = f"proctor:rate:{session_id}:violations"
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.config.cooldown_seconds)
        await pipe.execute()

        logger.warning(f"Rate limit violation for session {session_id}")

    async def get_session_stats(self, session_id: UUID) -> dict:
        """Get rate limiting stats for session."""
        now = time.time()
        key_minute = f"proctor:rate:{session_id}:minute"
        key_violations = f"proctor:rate:{session_id}:violations"

        minute_count = await self._sliding_window_count(key_minute, now, 60.0)
        violations = await self.redis.get(key_violations)
        violations = int(violations) if violations else 0

        return {
            "frames_last_minute": minute_count,
            "remaining_this_minute": max(
                0, self.config.max_frames_per_minute - minute_count
            ),
            "violation_count": violations,
            "is_throttled": violations > 0,
        }

    async def reset_session(self, session_id: UUID) -> None:
        """Reset rate limiting for a session."""
        keys = [
            f"proctor:rate:{session_id}:second",
            f"proctor:rate:{session_id}:minute",
            f"proctor:rate:{session_id}:violations",
        ]
        for key in keys:
            await self.redis.delete(key)


class InMemorySessionRateLimiter:
    """In-memory rate limiter for testing or single-instance deployments."""

    def __init__(self, config: Optional[SessionRateLimitConfig] = None):
        self.config = config or SessionRateLimitConfig()
        self._requests: dict = {}  # session_id -> list of timestamps
        self._violations: dict = {}  # session_id -> (count, expiry_time)

    async def check(self, session_id: UUID) -> RateLimitResult:
        """Check if frame submission is allowed."""
        now = time.time()
        session_key = str(session_id)

        # Check cooldown
        if session_key in self._violations:
            count, expiry = self._violations[session_key]
            if now < expiry:
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=expiry - now,
                    is_suspicious=True,
                )
            else:
                del self._violations[session_key]

        # Get or create request list
        if session_key not in self._requests:
            self._requests[session_key] = []

        requests = self._requests[session_key]

        # Clean old requests
        requests[:] = [t for t in requests if now - t < 60]

        # Check per-second limit
        second_count = sum(1 for t in requests if now - t < 1)
        if second_count >= self.config.max_frames_per_second + self.config.burst_allowance:
            self._record_violation(session_key, now)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=1.0,
                is_suspicious=second_count > self.config.max_frames_per_second * 2,
            )

        # Check per-minute limit
        if len(requests) >= self.config.max_frames_per_minute + self.config.burst_allowance:
            self._record_violation(session_key, now)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=60.0 - (now % 60),
                is_suspicious=len(requests) > self.config.max_frames_per_minute * 1.5,
            )

        # Record request
        requests.append(now)

        return RateLimitResult(
            allowed=True,
            remaining=self.config.max_frames_per_minute - len(requests),
            is_suspicious=False,
        )

    def _record_violation(self, session_key: str, now: float) -> None:
        """Record a violation."""
        if session_key in self._violations:
            count, _ = self._violations[session_key]
            count += 1
        else:
            count = 1

        expiry = now + self.config.cooldown_seconds
        self._violations[session_key] = (count, expiry)

    async def get_session_stats(self, session_id: UUID) -> dict:
        """Get stats for session."""
        session_key = str(session_id)
        now = time.time()

        requests = self._requests.get(session_key, [])
        requests = [t for t in requests if now - t < 60]

        violations = self._violations.get(session_key, (0, 0))

        return {
            "frames_last_minute": len(requests),
            "remaining_this_minute": max(
                0, self.config.max_frames_per_minute - len(requests)
            ),
            "violation_count": violations[0],
            "is_throttled": now < violations[1] if violations[1] else False,
        }

    async def reset_session(self, session_id: UUID) -> None:
        """Reset session rate limits."""
        session_key = str(session_id)
        self._requests.pop(session_key, None)
        self._violations.pop(session_key, None)
