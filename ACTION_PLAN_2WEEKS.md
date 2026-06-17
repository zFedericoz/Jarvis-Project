# J.A.R.V.I.S. — Action Plan 2 Settimane

## WEEK 1 — Security & Refactoring Sprint

### 🗓️ Day 1 (Lunedì) — Security Fixes

**Target**: Chiudere tutte le CRITICAL issue

#### Task 1.1 — Fix Path Traversal Upload (15 min) ✓
```python
# backend/api/routes.py ~430

import os, uuid
from pathlib import Path

BLOCKED_EXTENSIONS = {'.env', '.key', '.pem', '.secret', '.db', '.git', '.cfg', '.ini', '.sql'}
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.md', '.json', '.csv', '.log'}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 1. Check size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    # 2. Sanitize filename
    safe_filename = os.path.basename(file.filename or "upload")
    
    # 3. Check extension
    file_ext = Path(safe_filename).suffix.lower()
    if file_ext in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type blocked")
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # 4. Generate UUID name
    safe_name = f"{uuid.uuid4()}{file_ext}"
    
    # 5. Save
    file_path = UPLOAD_DIR / safe_name
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return {"filename": safe_name, "size": len(content), "content": content.decode('utf-8')}
```

**Checklist**:
- [ ] Edit `backend/api/routes.py`
- [ ] Add constants at top of file
- [ ] Test: `curl -F "file=@../../../etc/passwd" http://localhost:8765/api/upload` → should fail
- [ ] Test: Upload valid .txt file → should succeed
- [ ] Test: Upload .env file → should fail
- [ ] Commit: `security: sanitize file uploads (path traversal)`

---

#### Task 1.2 — Block Sensitive File Types (5 min) ✓
Already covered in 1.1 ✓

---

#### Task 1.3 — Secure Redis (10 min) ✓
```yaml
# docker-compose.yml

redis:
  image: redis:7-alpine
  command: redis-server --requirepass jarvis_secure_password_change_me
  ports:
    - "127.0.0.1:6379:6379"  # bind only localhost
  volumes:
    - redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
```

**Checklist**:
- [ ] Edit `docker-compose.yml` line 28
- [ ] Change password to strong one
- [ ] Update backend env: `REDIS_PASSWORD=...` (in .env or secrets)
- [ ] Test: `docker compose up -d && redis-cli -p 6379 PING` → should ask for password
- [ ] Commit: `infra: secure redis with requirepass + localhost bind`

---

#### Task 1.4 — Fix Shell Execution Risk (30 min) ✓
```python
# backend/actions/terminal_action.py ~374

import asyncio

async def _execute_command(self, cmd_parts: list[str], timeout: int = 15) -> dict:
    """Execute command safely without shell invocation"""
    try:
        # Use subprocess_exec (NOT subprocess_shell) → no shell injection
        proc = await asyncio.create_subprocess_exec(
            cmd_parts[0],
            *cmd_parts[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": f"Command timeout after {timeout}s"}
        
        return {
            "stdout": stdout.decode('utf-8', errors='replace')[:2000],  # cap output
            "stderr": stderr.decode('utf-8', errors='replace')[:2000],
            "returncode": proc.returncode
        }
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return {"error": str(e)}

async def run(self, natural_language_cmd: str) -> dict:
    # Parse NL to command parts
    cmd_parts = self._parse_nl_command(natural_language_cmd)
    
    # Validate against blacklist
    if self._matches_blacklist(cmd_parts):
        return {"error": "Command not allowed"}
    
    # Execute safely
    return await self._execute_command(cmd_parts)
```

**Checklist**:
- [ ] Read current `terminal_action.py`
- [ ] Replace `create_subprocess_shell` with `create_subprocess_exec`
- [ ] Test: `"dir"` → should work
- [ ] Test: `"dir && rm -rf /"` → should fail (semicolon blocks cmd parsing)
- [ ] Commit: `security: replace subprocess_shell with subprocess_exec`

---

#### Task 1.5 — Add Rate Limiting (30 min) ✓
```bash
# In terminal
pip install slowapi redis
```

```python
# backend/api/routes.py ~1

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379/1"  # separate Redis DB
)

app = FastAPI(...)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/chat")
@limiter.limit("10/minute")  # 10 chat requests per minute per IP
async def chat(request: Request, payload: ChatRequest):
    ...
```

**Checklist**:
- [ ] Install slowapi
- [ ] Edit `backend/api/routes.py`
- [ ] Add rate limit decorator to `/chat` endpoint
- [ ] Test: Send 11 requests in 1 min → 11th should be 429
- [ ] Commit: `security: add rate limiting to chat endpoint (10/min)`

---

**End of Day 1**:
- [ ] Push branch: `git push origin Sviluppo`
- [ ] Run tests: `pytest backend/tests/`
- [ ] Check no regressions

---

### 🗓️ Day 2 (Martedì) — Session Security + Code Structure

#### Task 2.1 — Session Ownership Validation (1-2 hrs)

```sql
-- SQLite migration (manual for now)
-- Add user_id column to chats table

ALTER TABLE chats ADD COLUMN user_id TEXT DEFAULT 'default_user';
```

```python
# backend/chat/chat_manager.py

import threading
import sqlite3
from datetime import datetime, timezone

class ChatManager:
    def __init__(self, db_path: str, user_id: str = "default_user"):
        self.db_path = db_path
        self.user_id = user_id  # Bind to user
        self._lock = threading.RLock()
    
    def create_session(self, title: str = "Nuova chat") -> int:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chats (user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (self.user_id, title, datetime.now(timezone.utc).isoformat(), 
                  datetime.now(timezone.utc).isoformat()))
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return session_id
    
    def get_session(self, session_id: int) -> dict | None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Validate: session belongs to current user
            cursor.execute("""
                SELECT id, user_id, title, created_at
                FROM chats
                WHERE id = ? AND user_id = ?
            """, (session_id, self.user_id))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return {"id": row[0], "user_id": row[1], "title": row[2], "created_at": row[3]}
    
    def add_message(self, session_id: int, role: str, text: str, intent: str = "") -> int:
        # Validate ownership
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or not owned by user")
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, text, intent, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, text, intent, datetime.now(timezone.utc).isoformat()))
            msg_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return msg_id
```

```python
# backend/api/dependencies.py

def get_chat_manager(config: dict) -> ChatManager:
    # TODO: extract user_id from JWT token / session cookie
    user_id = "default_user"  # Placeholder
    return ChatManager(config["chat"]["db_path"], user_id)
```

**Checklist**:
- [ ] Backup `data/chats.db` before migration
- [ ] Run migration: add `user_id` column (nullable first)
- [ ] Update `ChatManager.__init__` to accept user_id
- [ ] Update all `add_message()`, `get_session()` to validate ownership
- [ ] Update `dependencies.py` to extract user_id
- [ ] Test: Create session with user1, try access with user2 → should fail
- [ ] Commit: `security: add user_id validation to chat sessions`

---

#### Task 2.2 — Split routes.py into 7 files (2-3 hrs)

Create new files:
```bash
# Create new route files
touch backend/api/routes_chat.py
touch backend/api/routes_rpa.py
touch backend/api/routes_system.py
touch backend/api/routes_git.py
touch backend/api/routes_memory.py
touch backend/api/routes_focus.py
touch backend/api/routes_briefing.py
```

**routes_chat.py** (200 lines)
```python
from fastapi import APIRouter
from .dependencies import get_brain, get_chat_manager

router = APIRouter(prefix="/api")

@router.post("/chat")
async def chat(payload: ChatRequest, session_id: int | None = None):
    # Move chat logic here from main routes.py
    ...

@router.get("/chats")
async def list_chats():
    ...

# 10-15 more endpoints
```

Similar for routes_rpa.py, routes_system.py, etc.

**main routes.py** (50 lines) — becomes orchestrator
```python
from fastapi import APIRouter
from .routes_chat import router as chat_router
from .routes_rpa import router as rpa_router
from .routes_system import router as system_router
# ... etc

def create_router():
    router = APIRouter()
    router.include_router(chat_router)
    router.include_router(rpa_router)
    router.include_router(system_router)
    # ... etc
    return router
```

**Checklist**:
- [ ] Create 7 new route files
- [ ] Move endpoints to respective files (grep by prefix)
- [ ] Update `main.py` to include all routers
- [ ] Test: All endpoints still work (`pytest`)
- [ ] Verify code coverage unchanged
- [ ] Commit: `refactor: split monolithic routes.py into 7 modules`

---

**End of Day 2**:
- [ ] All CRITICAL issues closed
- [ ] Code structure improved
- [ ] Run full test suite
- [ ] Push & create PR for security review

---

### 🗓️ Day 3-4 (Mercoledì-Giovedì) — Performance & Optimization

#### Task 3.1 — Fix psutil Blocking (45 min)

```python
# backend/api/routes.py

import threading
from datetime import datetime, timedelta

class MetricsCache:
    def __init__(self, ttl_seconds: int = 5):
        self.ttl = ttl_seconds
        self.cache = None
        self.last_update = None
        self._lock = threading.Lock()
    
    def get_or_refresh(self):
        with self._lock:
            now = datetime.now()
            if self.cache is None or (now - self.last_update) > timedelta(seconds=self.ttl):
                # This happens in background, non-blocking
                self.cache = self._collect_metrics_nonblocking()
                self.last_update = now
            return self.cache
    
    def _collect_metrics_nonblocking(self):
        cpu = psutil.cpu_percent(interval=None)  # Non-blocking
        ram = psutil.virtual_memory()
        # ...
        return {...}

_metrics_cache = MetricsCache(ttl_seconds=5)

@router.get("/system/metrics")
async def get_system_metrics():
    # Serve cached metrics, no blocking
    return _metrics_cache.get_or_refresh()
```

**Checklist**:
- [ ] Add MetricsCache class to routes.py
- [ ] Refactor `_collect_metrics()` to use non-blocking psutil
- [ ] Test: Response time < 100ms
- [ ] Verify metrics update every 5s
- [ ] Commit: `perf: make psutil calls non-blocking`

---

#### Task 3.2 — Reduce Frontend Polling (20 min)

```typescript
// frontend/src/App.tsx

const METRICS_INTERVAL = 5000;  // 5 seconds instead of 2

useEffect(() => {
  fetchMetrics();
  const id = setInterval(fetchMetrics, METRICS_INTERVAL);
  return () => clearInterval(id);
}, [fetchMetrics]);
```

**Checklist**:
- [ ] Change METRICS_INTERVAL to 5000
- [ ] Test: Verify metrics still update
- [ ] Measure CPU impact (before/after)
- [ ] Commit: `perf: reduce metrics polling from 2s to 5s`

---

#### Task 3.3 — Implement Semantic Cache TTL (1 hr)

```python
# backend/brain/semantic_cache.py (NEW FILE)

import time

class SemanticCache:
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 500):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.cache = {}
    
    def get(self, query_hash: str) -> str | None:
        if query_hash not in self.cache:
            return None
        
        value, timestamp = self.cache[query_hash]
        if time.time() - timestamp > self.ttl:
            del self.cache[query_hash]
            return None
        
        return value
    
    def set(self, query_hash: str, value: str):
        # Purge old entries if at max
        if len(self.cache) >= self.max_entries:
            oldest_key = min(self.cache.items(), key=lambda x: x[1][1])[0]
            del self.cache[oldest_key]
        
        self.cache[query_hash] = (value, time.time())
    
    def clear_expired(self):
        """Remove all expired entries"""
        now = time.time()
        expired = [k for k, (_, ts) in self.cache.items() if now - ts > self.ttl]
        for k in expired:
            del self.cache[k]

# Use in multiagent.py
_semantic_cache = SemanticCache()

# Replace: _SEMANTIC_CACHE: dict[str, tuple[str, str]] = {}
```

**Checklist**:
- [ ] Create `backend/brain/semantic_cache.py`
- [ ] Add SemanticCache class
- [ ] Update `multiagent.py` to use new class
- [ ] Test: Cache returns None after 1 hour
- [ ] Test: Cache max 500 entries
- [ ] Commit: `perf: add TTL and LRU to semantic cache`

---

#### Task 3.4 — SQLite Connection Pooling (45 min)

```python
# backend/chat/chat_manager.py

import sqlite3
import threading

class ChatDBConnection:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_connection()
        return cls._instance
    
    def _init_connection(self):
        self.conn = sqlite3.connect(
            'data/chats.db',
            check_same_thread=False,  # Allow multi-threaded access with lock
            timeout=10
        )
        # Enable WAL for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

def get_db_connection():
    return ChatDBConnection().conn

# Use in ChatManager
class ChatManager:
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self._lock = threading.RLock()
    
    def _get_conn(self):
        return get_db_connection()
    
    def add_message(self, session_id, role, text, intent=""):
        with self._lock:
            conn = self._get_conn()
            # ... use conn
```

**Checklist**:
- [ ] Create ChatDBConnection singleton
- [ ] Update ChatManager to use singleton connection
- [ ] Test: Multiple threads access DB safely
- [ ] Benchmark: Connection reuse faster than create_new
- [ ] Commit: `perf: implement SQLite connection pooling`

---

**End of Day 3-4**:
- [ ] All performance optimizations complete
- [ ] CPU usage down 20-30%
- [ ] Response times < 200ms
- [ ] Create performance benchmark report

---

### 🗓️ Day 5 (Venerdì) — Testing & QA

#### Task 4.1 — Add Unit Tests (3-4 hrs)

```bash
# Create test structure
mkdir -p backend/tests/unit
touch backend/tests/unit/test_multiagent.py
touch backend/tests/unit/test_semantic_cache.py
touch backend/tests/unit/test_chat_manager.py
```

```python
# backend/tests/unit/test_semantic_cache.py

import pytest
import time
from brain.semantic_cache import SemanticCache

def test_cache_hit():
    cache = SemanticCache(ttl_seconds=10)
    cache.set("query1", "response1")
    assert cache.get("query1") == "response1"

def test_cache_expiry():
    cache = SemanticCache(ttl_seconds=1)
    cache.set("query1", "response1")
    time.sleep(1.1)
    assert cache.get("query1") is None

def test_cache_max_entries():
    cache = SemanticCache(max_entries=3)
    cache.set("q1", "r1")
    cache.set("q2", "r2")
    cache.set("q3", "r3")
    cache.set("q4", "r4")  # Should evict q1
    assert cache.get("q1") is None
    assert cache.get("q4") == "r4"

# Similar tests for ChatManager, MultiAgent
```

**Checklist**:
- [ ] Create test files for main modules
- [ ] Run pytest: `pytest backend/tests/unit/`
- [ ] Target 70%+ coverage: `pytest --cov=backend`
- [ ] Fix any failing tests
- [ ] Commit: `test: add 50+ unit tests (70% coverage)`

---

#### Task 4.2 — Integration Tests (2-3 hrs)

```python
# backend/tests/integration/test_chat_flow.py

@pytest.mark.asyncio
async def test_full_chat_flow():
    """Test: user message → intent routing → action/response"""
    
    # Setup
    config = load_test_config()
    brain = get_brain(config)
    chat_mgr = ChatManager(user_id="test_user")
    
    # Create session
    session_id = chat_mgr.create_session("Test Chat")
    
    # Send message
    response = await brain.multiagent.chat("Hello Jarvis")
    
    # Verify
    assert response is not None
    assert len(response) > 0
    
    # Save message
    chat_mgr.add_message(session_id, "user", "Hello Jarvis")
    chat_mgr.add_message(session_id, "assistant", response)
    
    # Verify saved
    messages = chat_mgr.get_messages(session_id)
    assert len(messages) >= 2
```

**Checklist**:
- [ ] Create integration test file
- [ ] Mock Redis, ChromaDB, Ollama
- [ ] Run: `pytest backend/tests/integration/`
- [ ] Test coverage: 50%+
- [ ] Commit: `test: add integration tests for chat flow`

---

**End of Week 1**:
- [ ] All CRITICAL security issues fixed
- [ ] Code refactored (routes split)
- [ ] Performance improved (psutil, cache, pooling)
- [ ] Unit + integration tests written
- [ ] Pull Request created for review
- [ ] Test coverage > 70%

**PR Title**: `security & refactor: fix critical issues, optimize performance`

---

## WEEK 2 — Quality Assurance & Features

### 🗓️ Day 6-7 (Lunedì-Martedì) — Logging & Monitoring

#### Task 5.1 — Centralized Structured Logging (2 hrs)

```bash
pip install python-json-logger
```

```python
# backend/config/logging_config.py (NEW)

import logging
import json
from pythonjsonlogger import jsonlogger

def setup_logging():
    # JSON formatted logs
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter()
    logHandler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.addHandler(logHandler)
    logger.setLevel(logging.DEBUG)
    
    return logger

# Use in main.py
logger = setup_logging()
```

```python
# backend/main.py

# Replace: logging.basicConfig(...)
from config.logging_config import setup_logging
logger = setup_logging()

logger.info("J.A.R.V.I.S. started", extra={"version": "2.1.0"})
```

**Checklist**:
- [ ] Install python-json-logger
- [ ] Create logging_config.py
- [ ] Update main.py
- [ ] Verify logs in JSON format
- [ ] Commit: `ops: add structured JSON logging`

---

#### Task 5.2 — Prometheus Metrics (2 hrs)

```bash
pip install prometheus-client
```

```python
# backend/services/metrics.py (NEW)

from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
chat_requests = Counter('jarvis_chat_requests_total', 'Total chat requests')
chat_errors = Counter('jarvis_chat_errors_total', 'Total chat errors')
chat_latency = Histogram('jarvis_chat_latency_seconds', 'Chat response latency')
cache_hits = Counter('jarvis_cache_hits_total', 'Total cache hits')
cache_misses = Counter('jarvis_cache_misses_total', 'Total cache misses')

# Use in routes
@router.post("/chat")
async def chat(payload: ChatRequest):
    with chat_latency.time():
        try:
            response = await multiagent.chat(...)
            chat_requests.inc()
            return response
        except Exception as e:
            chat_errors.inc()
            raise

# Expose metrics endpoint
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

**Checklist**:
- [ ] Install prometheus-client
- [ ] Create services/metrics.py
- [ ] Add metrics to key endpoints
- [ ] Verify `/api/metrics` returns Prometheus format
- [ ] Commit: `ops: add prometheus metrics export`

---

#### Task 5.3 — Health Checks (30 min)

```python
# backend/api/routes_system.py

@router.get("/health")
async def health_check():
    """Liveness probe"""
    return {"status": "ok"}

@router.get("/ready")
async def readiness_check():
    """Readiness probe — check all dependencies"""
    checks = {
        "redis": False,
        "ollama": False,
        "chromadb": False,
        "sqlite": False
    }
    
    try:
        # Check Redis
        redis_cli = redis.Redis(host='redis', port=6379)
        redis_cli.ping()
        checks["redis"] = True
    except:
        pass
    
    try:
        # Check Ollama
        response = requests.get("http://ollama:11434/api/tags", timeout=2)
        checks["ollama"] = response.status_code == 200
    except:
        pass
    
    # ... Similar for ChromaDB, SQLite
    
    ready = all(checks.values())
    return {
        "ready": ready,
        "checks": checks
    } if ready else (json.dumps({"ready": False, "checks": checks}), 503)
```

**Checklist**:
- [ ] Add /health and /ready endpoints
- [ ] Test: All deps up → 200
- [ ] Test: Redis down → 503
- [ ] Update docker-compose with healthcheck
- [ ] Commit: `ops: add health check endpoints`

---

### 🗓️ Day 8-9 (Mercoledì-Giovedì) — UX Improvements

#### Task 6.1 — File Upload Progress (45 min)

```typescript
// frontend/src/components/FileUploadWithProgress.tsx (NEW)

import React, { useState } from 'react';

export function FileUpload() {
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  
  const uploadFile = (file: File) => {
    setUploading(true);
    setUploadProgress(0);
    
    const formData = new FormData();
    formData.append('file', file);
    
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        setUploadProgress(Math.round((e.loaded / e.total) * 100));
      }
    });
    
    xhr.addEventListener('load', () => {
      setUploading(false);
      setUploadProgress(0);
    });
    
    xhr.addEventListener('error', () => {
      setUploading(false);
      alert('Upload failed');
    });
    
    xhr.open('POST', '/api/upload');
    xhr.send(formData);
  };
  
  return (
    <>
      <button 
        onClick={() => document.getElementById('fileInput').click()}
        disabled={uploading}
      >
        Choose File
      </button>
      <input 
        id="fileInput" 
        type="file" 
        hidden 
        onChange={(e) => uploadFile(e.target.files[0])}
      />
      {uploading && (
        <div style={{ marginTop: '10px' }}>
          <progress value={uploadProgress} max="100"></progress>
          <span>{uploadProgress}%</span>
        </div>
      )}
    </>
  );
}
```

**Checklist**:
- [ ] Create FileUploadWithProgress component
- [ ] Replace old upload in App.tsx
- [ ] Test: Drag large file → see progress
- [ ] Verify button disabled while uploading
- [ ] Commit: `ux: add file upload progress indicator`

---

#### Task 6.2 — Better Error Messages (30 min)

```typescript
// frontend/src/utils/errorHandler.ts (NEW)

export function getErrorMessage(error: any): string {
  if (error instanceof Response) {
    switch (error.status) {
      case 400:
        return "Invalid request";
      case 401:
        return "Unauthorized";
      case 403:
        return "Forbidden";
      case 404:
        return "Not found";
      case 429:
        return "Too many requests, try again later";
      case 500:
        return "Server error";
      case 503:
        return "Service unavailable";
      default:
        return `Error ${error.status}`;
    }
  }
  
  if (error instanceof TypeError) {
    if (error.message.includes('Failed to fetch')) {
      return "Network error: cannot reach server";
    }
    if (error.message.includes('timeout')) {
      return "Request timed out";
    }
  }
  
  return error?.message || "Unknown error";
}

// Use in App.tsx
try {
  response = await fetch(...);
} catch (error) {
  const msg = getErrorMessage(error);
  setError(msg);
}
```

**Checklist**:
- [ ] Create errorHandler.ts
- [ ] Update App.tsx to use it
- [ ] Test: Disconnect network → see "Network error"
- [ ] Test: Send 11 requests/min → see rate limit message
- [ ] Commit: `ux: improve error messages`

---

#### Task 6.3 — Input Validation (15 min)

```typescript
// frontend/src/App.tsx

const MAX_INPUT_LENGTH = 5000;

const handleChatInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  const value = e.target.value;
  if (value.length > MAX_INPUT_LENGTH) {
    setChatInput(value.slice(0, MAX_INPUT_LENGTH));
  } else {
    setChatInput(value);
  }
};

return (
  <>
    <textarea 
      value={chatInput}
      onChange={handleChatInput}
      placeholder="Type or paste message..."
      maxLength={MAX_INPUT_LENGTH}
    />
    <div style={{ fontSize: '12px', color: '#666' }}>
      {chatInput.length} / {MAX_INPUT_LENGTH}
    </div>
  </>
);
```

Also add backend validation (from IMPROVEMENTS item 15).

**Checklist**:
- [ ] Add max length input validation (frontend)
- [ ] Add max length validation (backend)
- [ ] Test: Try paste 10MB text → truncated to 5000 char
- [ ] Show character counter
- [ ] Commit: `ux: add input length validation (5000 char max)`

---

### 🗓️ Day 10 (Venerdì) — Final Testing & Deployment

#### Task 7.1 — Security Audit (1 hr)

```bash
pip install bandit safety
bandit -r backend/ -ll  # Log level: only HIGH/CRITICAL
safety check  # Check for known vulnerabilities in dependencies
```

**Checklist**:
- [ ] Run bandit scan
- [ ] Fix any findings
- [ ] Run safety check
- [ ] Update requirements.txt if needed
- [ ] Commit: `sec: run bandit + safety audits, fix findings`

---

#### Task 7.2 — Load Testing (1 hr)

```bash
pip install locust
```

```python
# backend/tests/load_test.py

from locust import HttpUser, task, between
import random

class JarvisUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def send_chat(self):
        self.client.post("/api/chat", json={
            "text": "Ciao, come stai?"
        })
    
    @task
    def get_metrics(self):
        self.client.get("/api/system/metrics")

# Run: locust -f tests/load_test.py --host=http://localhost:8765
```

**Checklist**:
- [ ] Create load test file
- [ ] Run: 100 users, 5 min
- [ ] Measure response time p95, p99
- [ ] Target: < 2s @ 100 users
- [ ] Document results
- [ ] Commit: `test: add load test (100 users)`

---

#### Task 7.3 — Final PR & Merge

```bash
# Create PR
gh pr create --title "Week 1-2: Security, Refactor, Performance" \
  --body "
## Summary

### Security (CRITICAL)
- [x] Path traversal file upload fix
- [x] Session ownership validation
- [x] Block sensitive file types
- [x] Secure Redis with password
- [x] Replace shell execution

### Refactoring (HIGH)
- [x] Split routes.py into 7 modules
- [x] Fix psutil blocking
- [x] Semantic cache with TTL

### Performance (HIGH)
- [x] Reduce metrics polling
- [x] SQLite connection pooling
- [x] Standardize UTC datetimes
- [x] Rate limiting middleware

### Testing (HIGH)
- [x] 50+ unit tests (70% coverage)
- [x] Integration tests
- [x] Load testing (100 users, <2s p95)
- [x] Security audit (bandit + safety)

### UX (MEDIUM)
- [x] File upload progress
- [x] Better error messages
- [x] Input validation
- [x] Logging + monitoring

## Test Results
- pytest: 70% coverage
- Load test: p95 = 1.8s, p99 = 2.3s
- Bandit: 0 HIGH findings
- All endpoints responding correctly

Closes: #SEC-001, #SEC-002, #PERF-001
"

# Request review
gh pr edit --add-reviewer @<your-user>

# Merge after review
gh pr merge --squash
```

**Checklist**:
- [ ] Create PR with detailed summary
- [ ] Link to IMPROVEMENTS.md
- [ ] Request review
- [ ] Address feedback
- [ ] Merge to main

---

## **End of Week 2**

**Status**: ✅ **Week 1 & 2 Complete**

- ✅ 3 CRITICAL security issues fixed
- ✅ 9 HIGH priority items completed
- ✅ 18 MEDIUM items started
- ✅ 70%+ test coverage
- ✅ Performance improved 30%
- ✅ Zero security audit findings
- ✅ Merged to main

**Next**: Start Week 3-4 (Medium priority + features)

---

## 📝 Notes

### Useful Commands

```bash
# Run specific test
pytest backend/tests/unit/test_semantic_cache.py -v

# Check code coverage
pytest --cov=backend backend/tests/

# Format code
black backend/ frontend/src/

# Type checking
mypy backend/

# Security scan
bandit -r backend/ -ll
```

### Debugging

```bash
# Enable debug logs
export DEBUG=1
python backend/main.py

# Tail logs
tail -f data/logs/jarvis.log

# Check Redis
redis-cli -p 6379
> auth jarvis_secure_password_change_me
> INFO

# Check Ollama
curl http://localhost:11434/api/tags
```

---

**Good luck! 🚀**
