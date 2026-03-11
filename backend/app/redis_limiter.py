import os
import time
import hashlib
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential


class RedisRateLimiter:
    def __init__(self, redis_url: Optional[str] = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379")
        self.requests_per_minute = int(os.getenv("RATE_LIMIT", "60"))
        self.fail_open = os.getenv("REDIS_FAIL_OPEN", "true").lower() == "true"
        self.max_failures = int(os.getenv("REDIS_MAX_FAILURES", "10"))
        self.redis_failures = 0
        self._initialized = False
        self.redis: Optional[object] = None
        self.key_prefix = "rl:"

        self.lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])

        redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
        local count = redis.call('ZCARD', key)

        if count >= limit then
            return 0
        end

        redis.call('ZADD', key, now, now)
        redis.call('EXPIRE', key, math.floor(window / 1000))
        return 1
        """
        self._script_sha: Optional[str] = None

    def _hash_key(self, client_ip: str) -> str:
        ip_hash = hashlib.md5(client_ip.encode("utf-8")).hexdigest()[:16]
        return f"{self.key_prefix}{ip_hash}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def initialize(self) -> None:
        if self._initialized:
            return

        import redis.asyncio as redis

        self.redis = redis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=10,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        await self.redis.ping()
        self._script_sha = await self.redis.script_load(self.lua_script)
        self._initialized = True
        self.redis_failures = 0

    def _on_failure(self) -> bool:
        self.redis_failures += 1
        if self.redis_failures >= self.max_failures:
            return False
        return self.fail_open

    async def check_limit(self, client_ip: str) -> bool:
        try:
            if not self._initialized:
                await self.initialize()

            if not self.redis or not self._script_sha:
                return self._on_failure()

            now = int(time.time() * 1000)
            window_ms = 60000
            key = self._hash_key(client_ip)
            allowed = await self.redis.evalsha(
                self._script_sha,
                1,
                key,
                now,
                window_ms,
                self.requests_per_minute,
            )
            self.redis_failures = 0
            return int(allowed) == 1
        except Exception:
            return self._on_failure()

    async def get_remaining(self, client_ip: str) -> int:
        try:
            if not self._initialized or self.redis is None:
                return self.requests_per_minute

            now = int(time.time() * 1000)
            window_ms = 60000
            key = self._hash_key(client_ip)
            await self.redis.zremrangebyscore(key, 0, now - window_ms)
            count = await self.redis.zcard(key)
            return max(0, self.requests_per_minute - int(count))
        except Exception:
            return self.requests_per_minute

    async def stats(self) -> dict[str, int | str | bool]:
        return {
            "mode": "redis",
            "initialized": self._initialized,
            "failures": self.redis_failures,
            "fail_open": self.fail_open,
            "max_failures": self.max_failures,
            "requests_per_minute": self.requests_per_minute,
        }

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None
            self._initialized = False
