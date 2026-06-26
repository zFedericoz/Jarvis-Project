import bcrypt
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

logger = logging.getLogger("jarvis.api.auth")

SECRET_KEY = os.getenv("JWT_SECRET", "jarvis-dev-secret-change-in-production")
if SECRET_KEY == "jarvis-dev-secret-change-in-production":
    logger.warning("JWT_SECRET non impostato in .env! Usare una chiave segreta forte in produzione.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

security = HTTPBearer(auto_error=False)

DB_PATH = Path("data/chats.db")


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_users_table():
    conn = _get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def register_user(username: str, password: str) -> dict:
    _init_users_table()
    conn = _get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already exists")
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                           (username, hash_password(password), now))
        conn.commit()
        user_id = cur.lastrowid
        token = create_access_token({"sub": username, "user_id": user_id})
        return {"access_token": token, "token_type": "bearer", "user_id": user_id, "username": username}
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> dict:
    _init_users_table()
    conn = _get_db()
    try:
        row = conn.execute("SELECT id, password_hash FROM users WHERE username=?", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = create_access_token({"sub": username, "user_id": row["id"]})
        return {"access_token": token, "token_type": "bearer", "user_id": row["id"], "username": username}
    finally:
        conn.close()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("user_id")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "user_id": user_id}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
