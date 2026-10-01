from redis import Redis
from redis.exceptions import RedisError

from app.core.errors import GatewayError


class RateLimiter:
    def __init__(self, cache: Redis, limit: int, window_seconds: int = 60) -> None:
        self.cache = cache
        self.limit = limit
        self.window_seconds = window_seconds

    def check(self, actor_id: int, tool_id: int) -> None:
        key = f"rate:{actor_id}:{tool_id}"
        try:
            with self.cache.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, self.window_seconds)
                count = int(pipe.execute()[0])
        except RedisError as exc:
            raise GatewayError(503, "rate_limit_unavailable", "Rate limiter unavailable") from exc
        if count > self.limit:
            raise GatewayError(429, "rate_limited", "Tool rate limit exceeded")

