import time
from collections import defaultdict
import logging

logger = logging.getLogger("jarvis.memory.ephemeral")

class EphemeralMemory:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.store: dict[str, tuple[object, float]] = {}

    def set(self, key: str, value: object):
        self.store[key] = (value, time.time())

    def get(self, key: str) -> object | None:
        if key not in self.store:
            return None
        value, ts = self.store[key]
        if time.time() - ts > self.ttl:
            del self.store[key]
            return None
        return value

    def delete(self, key: str):
        self.store.pop(key, None)

    def clear(self):
        self.store.clear()
