import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from typing import Optional

logger = logging.getLogger("jarvis.api.ratelimiter")

_REDIS_KEY_PREFIX = "ratelimit:"
_WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self, redis_host: str = "redis", redis_port: int = 6379, redis_password: str | None = None):
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._password = redis_password or os.getenv("REDIS_PASSWORD")
        self._redis = None
        self._redis_available = False
        self._fallback: defaultdict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._connect_lock = asyncio.Lock()

    async def _ensure_redis(self):
        if self._redis_available and self._redis is not None:
            try:
                await self._redis.ping()
                return
            except Exception:
                self._redis_available = False
                self._redis = None
                logger.warning("Redis connessione persa, fallback a rate limiter locale")
        async with self._connect_lock:
            if self._redis is not None:
                return
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.Redis(
                    host=self._redis_host,
                    port=self._redis_port,
                    password=self._password,
                    decode_responses=True,
                    socket_timeout=2,
                )
                await self._redis.ping()
                self._redis_available = True
                logger.info("RateLimiter connesso a Redis")
            except Exception as e:
                self._redis = None
                self._redis_available = False
                logger.warning(f"Redis non disponibile per rate limiter ({e}), fallback locale")

    async def check(self, key: str, max_per_window: int, window: int = _WINDOW_SECONDS) -> bool:
        await self._ensure_redis()
        if self._redis_available and self._redis is not None:
            return await self._check_redis(key, max_per_window, window)
        return self._check_local(key, max_per_window, window)

    async def _check_redis(self, key: str, max_per_window: int, window: int) -> bool:
        redis_key = f"{_REDIS_KEY_PREFIX}{key}"
        now = time.time()
        min_score = now - window
        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.zremrangebyscore(redis_key, 0, min_score)
            pipe.zadd(redis_key, {f"{now}:{id(self)}:{key}": now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window + 10)
            _, _, count, _ = await pipe.execute()
            return count <= max_per_window
        except Exception as e:
            logger.debug(f"Redis rate limit fallito ({e}), fallback locale")
            return self._check_local(key, max_per_window, window)

    def _check_local(self, key: str, max_per_window: int, window: int) -> bool:
        now = time.time()
        times = self._fallback[key]
        times.append(now)
        while times and (now - times[0]) > window:
            times.popleft()
        return len(times) <= max_per_window


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
