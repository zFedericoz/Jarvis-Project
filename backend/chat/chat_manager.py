import sqlite3
import logging
import threading
import os
from datetime import datetime, timezone
from pathlib import Path

from .db_connection import ChatDBConnection

logger = logging.getLogger("jarvis.chat")

DB_PATH = Path("data/chats.db")


class ChatManager:
    def __init__(self, db_path: str | Path = DB_PATH, user_id: str | None = None):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._user_id = user_id or os.getenv("USER", "default_user")
        self._init_db()

    def _conn(self):
        """Get singleton connection from pool."""
        return ChatDBConnection().get_connection()

    def _init_db(self):
        with self._lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default_user',
                    title TEXT NOT NULL DEFAULT 'Nuova chat',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    intent TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
            """)
            conn.commit()

    def _validate_ownership(self, session_id: int) -> bool:
        """Verify session belongs to current user"""
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            if not row:
                return False
            return row[0] == self._user_id

    def create_session(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (self._user_id, "Nuova chat", now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def list_sessions(self) -> list[dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT s.*,
                       (SELECT COUNT(*) FROM messages WHERE session_id = s.id) AS message_count,
                       (SELECT content FROM messages WHERE session_id = s.id ORDER BY id DESC LIMIT 1) AS last_message_preview
                FROM sessions s
                WHERE s.user_id = ?
                ORDER BY s.updated_at DESC
            """, (self._user_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_session(self, session_id: int) -> dict | None:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, self._user_id)
            ).fetchone()
            return dict(row) if row else None

    def rename_session(self, session_id: int, title: str) -> bool:
        if not self._validate_ownership(session_id):
            logger.warning(f"Ownership validation failed for session {session_id} and user {self._user_id}")
            return False

        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (title, now, session_id, self._user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_session(self, session_id: int) -> bool:
        if not self._validate_ownership(session_id):
            logger.warning(f"Ownership validation failed for delete session {session_id}")
            return False

        with self._lock, self._conn() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, self._user_id))
            conn.commit()
            return cur.rowcount > 0

    def add_message(self, session_id: int, role: str, content: str, intent: str = "") -> dict:
        if not self._validate_ownership(session_id):
            raise ValueError(f"Session {session_id} not owned by user {self._user_id}")

        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, intent, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, intent, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def get_messages(self, session_id: int) -> list[dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def auto_title(self, session_id: int) -> str:
        session = self.get_session(session_id)
        if session and session["title"] != "Nuova chat":
            return session["title"]
        msgs = self.get_messages(session_id)
        for msg in msgs:
            if msg["role"] == "user" and msg["content"]:
                raw = msg["content"].strip()
                title = raw[:60]
                if len(raw) > 60:
                    title += "..."
                self.rename_session(session_id, title)
                return title
        return "Nuova chat"
