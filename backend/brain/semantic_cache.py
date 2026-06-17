"""
SemanticCache — LRU cache con TTL per query semantiche.

Previene memory leak da _SEMANTIC_CACHE globale non limitato.
Mantiene max 500 entry, scadono dopo 1 ora.
"""

import time
import logging
from collections import OrderedDict

logger = logging.getLogger("jarvis.brain.semantic_cache")


class SemanticCache:
    def __init__(self, max_entries: int = 500, ttl_seconds: int = 3600):
        """
        Initialize semantic cache with LRU eviction and TTL.

        Args:
            max_entries: Maximum number of cached queries
            ttl_seconds: Time to live for each entry (default 1 hour)
        """
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self.cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def get(self, query_hash: str) -> str | None:
        """
        Retrieve cached value if exists and not expired.
        Moves entry to end (LRU).
        """
        if query_hash not in self.cache:
            return None

        value, timestamp = self.cache[query_hash]
        if time.time() - timestamp > self.ttl:
            del self.cache[query_hash]
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(query_hash)
        return value

    def set(self, query_hash: str, value: str) -> None:
        """
        Store value in cache. Removes oldest entry if max reached.
        """
        if query_hash in self.cache:
            del self.cache[query_hash]

        self.cache[query_hash] = (value, time.time())

        # Evict oldest entry if at max
        if len(self.cache) > self.max_entries:
            oldest_key, _ = self.cache.popitem(last=False)
            logger.debug(f"SemanticCache evicted old entry: {oldest_key}")

    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.time()
        expired = [k for k, (_, ts) in self.cache.items() if now - ts > self.ttl]
        for k in expired:
            del self.cache[k]
        if expired:
            logger.debug(f"SemanticCache cleaned {len(expired)} expired entries")
        return len(expired)

    def clear(self) -> None:
        """Clear all entries."""
        self.cache.clear()
        logger.info("SemanticCache cleared")

    def stats(self) -> dict:
        """Return cache statistics."""
        now = time.time()
        valid_entries = sum(
            1 for _, (_, ts) in self.cache.items()
            if now - ts <= self.ttl
        )
        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "max_entries": self.max_entries,
            "ttl_seconds": self.ttl,
        }
