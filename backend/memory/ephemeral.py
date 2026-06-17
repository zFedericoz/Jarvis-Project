import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("jarvis.memory.ephemeral")

class EphemeralMemory:
    def __init__(self, config: dict | None = None):
        self._redis = None
        self._local = {}
        self._ttl = 3600
        if config is not None:
            mem_cfg = config.get("memory", {}).get("short_term", {})
            self._ttl = mem_cfg.get("ttl", 3600)
            host = mem_cfg.get("host", "localhost")
            port = mem_cfg.get("port", 6379)
            password = os.getenv("REDIS_PASSWORD")  # Get from env for security
            try:
                import redis as redis_lib
                self._redis = redis_lib.Redis(
                    host=host,
                    port=port,
                    password=password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True
                )
                self._redis.ping()
                logger.info(f"EphemeralMemory connected to Redis at {host}:{port}")
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}), falling back to local dict")
                self._redis = None

    def set(self, key: str, value: object):
        if self._redis:
            try:
                data = json.dumps(value, default=str)
                self._redis.setex(key, self._ttl, data)
                return
            except Exception as e:
                logger.warning(f"Redis set failed ({e}), falling back to local")
        self._local[key] = value

    def get(self, key: str) -> object | None:
        if self._redis:
            try:
                data = self._redis.get(key)
                if data is not None:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get failed ({e}), falling back to local")
        return self._local.get(key)

    def delete(self, key: str):
        if self._redis:
            try:
                self._redis.delete(key)
                return
            except Exception:
                pass
        self._local.pop(key, None)

    def clear(self):
        if self._redis:
            try:
                self._redis.flushdb()
                return
            except Exception:
                pass
        self._local.clear()