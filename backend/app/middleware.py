import os
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.redis_limiter import RedisRateLimiter

MAX_IMAGE_BYTES = 10 * 1024 * 1024


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self.use_redis = os.getenv("USE_REDIS_RATE_LIMIT", "false").lower() == "true"
        self.redis_limiter: Optional[RedisRateLimiter] = RedisRateLimiter() if self.use_redis else None
        self.memory_requests: defaultdict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=requests_per_minute)
        )
        # Backward-compatible alias used by health endpoint.
        self.requests = self.memory_requests

    async def initialize(self) -> None:
        if self.use_redis and self.redis_limiter is not None:
            await self.redis_limiter.initialize()

    async def close(self) -> None:
        if self.redis_limiter is not None:
            await self.redis_limiter.close()

    @property
    def mode(self) -> str:
        return "redis" if self.use_redis else "memory"

    async def check_limit(self, client_ip: str) -> bool:
        if self.use_redis and self.redis_limiter is not None:
            return await self.redis_limiter.check_limit(client_ip)

        return self._check_memory_limit(client_ip)

    def _check_memory_limit(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - 60

        timestamps = self.memory_requests[client_ip]
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

        if len(timestamps) >= self.requests_per_minute:
            return False

        timestamps.append(now)
        return True

    async def get_remaining(self, client_ip: str) -> int:
        if self.use_redis and self.redis_limiter is not None:
            return await self.redis_limiter.get_remaining(client_ip)

        return self._get_memory_remaining(client_ip)

    def _get_memory_remaining(self, client_ip: str) -> int:
        timestamps = self.memory_requests.get(client_ip, deque())
        now = time.time()
        cutoff = now - 60
        recent = sum(1 for stamp in timestamps if stamp > cutoff)
        return max(0, self.requests_per_minute - recent)


rate_limiter = RateLimiter(requests_per_minute=90)


async def validate_limits(request: Request):
    if request.url.path != "/api/generate-stl" or request.method != "POST":
        return None

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return JSONResponse(
            status_code=400,
            content={"error": "Request must be multipart/form-data"},
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_IMAGE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Image too large. Maximum request size is 10MB."},
                )
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid content-length header."})

    return None
