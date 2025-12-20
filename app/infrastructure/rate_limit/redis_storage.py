"""Redis-backed rate limit storage implementation."""

import logging
import time
from typing import Optional

from app.domain.interfaces.rate_limit_storage import IRateLimitStorage, RateLimitInfo

logger = logging.getLogger(__name__)


class RedisRateLimitStorage:
    """Redis-backed rate limit storage.

    Uses sliding window algorithm with Redis for distributed deployments.
    Thread-safe and supports multiple instances behind a load balancer.
    """

    def __init__(self, redis_url: str, key_prefix: str = "rate_limit:") -> None:
        """Initialize Redis rate limit storage.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            key_prefix: Prefix for all rate limit keys
        """
        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError(
                "redis package required for Redis rate limiting. "
                "Install with: pip install redis>=5.0.0"
            )

        self._redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._key_prefix = key_prefix
        self._tier_prefix = "tier:"
        logger.info(f"RedisRateLimitStorage initialized with prefix: {key_prefix}")

    def _make_key(self, key: str) -> str:
        """Create a Redis key with prefix.

        Args:
            key: The base key

        Returns:
            Prefixed key for Redis
        """
        return f"{self._key_prefix}{key}"

    def _make_tier_key(self, key: str) -> str:
        """Create a Redis key for tier storage.

        Args:
            key: The base key

        Returns:
            Prefixed tier key for Redis
        """
        return f"{self._key_prefix}{self._tier_prefix}{key}"

    async def increment(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitInfo:
        """Increment request count using Redis.

        Uses a Lua script for atomic increment with window management.

        Args:
            key: Unique key (tenant_id or API key)
            limit: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            Current rate limit information
        """
        redis_key = self._make_key(key)
        current_time = int(time.time())

        # Lua script for atomic sliding window rate limiting
        lua_script = """
        local key = KEYS[1]
        local window_seconds = tonumber(ARGV[1])
        local current_time = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])

        -- Get current data
        local data = redis.call('HGETALL', key)
        local count = 0
        local window_start = 0

        -- Parse existing data
        for i = 1, #data, 2 do
            if data[i] == 'count' then
                count = tonumber(data[i + 1]) or 0
            elseif data[i] == 'window_start' then
                window_start = tonumber(data[i + 1]) or 0
            end
        end

        -- Check if window has expired
        if current_time >= window_start + window_seconds then
            count = 0
            window_start = current_time
        end

        -- Increment count
        count = count + 1

        -- Save updated data
        redis.call('HSET', key, 'count', count, 'window_start', window_start)

        -- Set TTL to auto-cleanup expired keys
        redis.call('EXPIRE', key, window_seconds + 60)

        return {count, window_start}
        """

        # Execute Lua script atomically
        result = await self._redis.eval(
            lua_script,
            1,
            redis_key,
            window_seconds,
            current_time,
            limit,
        )

        count = int(result[0])
        window_start = int(result[1])

        # Get tier
        tier = await self._get_tier(key)

        # Calculate remaining
        remaining = max(0, limit - count)
        reset_at = window_start + window_seconds

        return RateLimitInfo(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            tier=tier,
        )

    async def get(self, key: str) -> Optional[RateLimitInfo]:
        """Get current rate limit info without incrementing.

        Args:
            key: Unique key

        Returns:
            Rate limit info or None if not found
        """
        redis_key = self._make_key(key)

        data = await self._redis.hgetall(redis_key)

        if not data:
            return None

        count = int(data.get("count", 0))
        window_start = int(data.get("window_start", 0))
        tier = await self._get_tier(key)

        # Default window
        window_seconds = 60
        limit = 60

        current_time = int(time.time())
        reset_at = window_start + window_seconds

        # Check if window has expired
        if current_time >= reset_at:
            return RateLimitInfo(
                limit=limit,
                remaining=limit,
                reset_at=current_time + window_seconds,
                tier=tier,
            )

        remaining = max(0, limit - count)

        return RateLimitInfo(
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            tier=tier,
        )

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Unique key to reset
        """
        redis_key = self._make_key(key)
        await self._redis.delete(redis_key)
        logger.debug(f"Rate limit reset for key: {key}")

    async def get_all_keys(self) -> list:
        """Get all tracked keys.

        Returns:
            List of all keys being tracked (without prefix)
        """
        pattern = f"{self._key_prefix}*"
        keys = []

        async for key in self._redis.scan_iter(pattern):
            # Skip tier keys
            if self._tier_prefix not in key:
                # Remove prefix
                clean_key = key[len(self._key_prefix) :]
                keys.append(clean_key)

        return keys

    async def _get_tier(self, key: str) -> str:
        """Get tier for a key.

        Args:
            key: Unique key

        Returns:
            Tier name or 'standard' if not set
        """
        tier_key = self._make_tier_key(key)
        tier = await self._redis.get(tier_key)
        return tier or "standard"

    async def set_tier(self, key: str, tier: str) -> None:
        """Set rate limit tier for a key.

        Args:
            key: Unique key
            tier: Tier name (free, standard, premium, unlimited)
        """
        tier_key = self._make_tier_key(key)
        await self._redis.set(tier_key, tier)
        logger.debug(f"Set tier for {key}: {tier}")

    async def close(self) -> None:
        """Close Redis connection."""
        await self._redis.close()
        logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if connection is healthy
        """
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
