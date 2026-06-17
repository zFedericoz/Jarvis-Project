"""
ChatDBConnection — Singleton connection pool for SQLite with WAL mode.

Fixes:
- No more connection-per-call (thread-safe singleton)
- WAL mode for better concurrency
- Proper lock management
"""

import sqlite3
import threading
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.chat")


class ChatDBConnection:
    """Singleton thread-safe SQLite connection with connection pooling."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._db_path = Path("data/chats.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create connection with WAL mode for better concurrency
        self.conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,  # Allow multi-threaded access with lock
            timeout=10.0,  # 10 second timeout on lock waits
            cached_statements=100,  # Cache prepared statements
        )
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode (Write-Ahead Logging) for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA foreign_keys=ON")

        self._initialized = True
        logger.info(f"ChatDB singleton initialized with WAL mode: {self._db_path}")

    def get_connection(self):
        """Get the singleton connection."""
        return self.conn

    @classmethod
    def close(cls):
        """Close the connection (for cleanup/testing)."""
        if cls._instance and hasattr(cls._instance, 'conn'):
            cls._instance.conn.close()
            cls._instance._initialized = False
            logger.info("ChatDB connection closed")
