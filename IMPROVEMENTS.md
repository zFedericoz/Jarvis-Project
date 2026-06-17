# J.A.R.V.I.S. — Lista di Miglioramenti & Fix

Data: 2026-06-17  
Statuto: **In Progress**  
Priorità globale: **CRITICAL → HIGH → MEDIUM → LOW**

---

## 🔴 CRITICAL — Sicurezza Urgente

### 1. **Path Traversal in File Upload** [CRITICAL]
- **File**: `backend/api/routes.py:414-446`
- **Problema**: Nome file preso direttamente da input utente. Attaccante: `../../etc/passwd`
- **Impatto**: Lettura file arbitrari dal filesystem
- **Fix**:
  ```python
  import os, uuid
  safe_filename = os.path.basename(file.filename)  # blocca ../
  if not safe_filename:
    safe_filename = str(uuid.uuid4())
  # Whitelist estensioni
  allowed_ext = {'.txt', '.pdf', '.md', '.json', '.csv'}
  if not any(safe_filename.endswith(ext) for ext in allowed_ext):
    raise ValueError("File type not allowed")
  ```
- **Effort**: 15 min
- **Status**: ⏳ TODO

---

### 2. **Session Ownership Not Validated** [CRITICAL]
- **File**: `backend/api/routes.py:269-272`
- **Problema**: Se conosco `session_id` di altro utente, accedo alla history chat. Nessun check.
- **Impatto**: Privacy leak, accesso non autorizzato a chat altrui
- **Fix**:
  - Aggiungere `user_id` a `chats` table SQLite
  - Prima di ogni query: `SELECT * FROM chats WHERE id=? AND user_id=?`
  - Implementare autenticazione (JWT o simple cookie-based)
- **Effort**: 1-2 ore (refactor schema + auth middleware)
- **Status**: ⏳ TODO

---

### 3. **Sensitive Files Upload Allowed** [CRITICAL]
- **File**: `backend/api/routes.py:438`
- **Problema**: Accetta `.env`, `.cfg`, `.ini`, `.sql`, `.key` files. Potrebbe esporre secrets.
- **Impatto**: Accesso a credenziali se file erroneamente caricato
- **Fix**:
  ```python
  BLOCKED_EXTENSIONS = {'.env', '.key', '.pem', '.secret', '.db', '.git', '.cfg', '.ini', '.sql'}
  if any(safe_filename.lower().endswith(ext) for ext in BLOCKED_EXTENSIONS):
    raise ValueError("File type blocked for security")
  ```
- **Effort**: 5 min
- **Status**: ⏳ TODO

---

### 4. **Redis Exposed Without Auth** [HIGH]
- **File**: `docker-compose.yml:28-29`
- **Problema**: Redis container su port 6379 senza password. Chiunque da host connette.
- **Impatto**: Redis hijacking, data theft, command injection
- **Fix**:
  ```yaml
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:-jarvis_dev_pass_change_me}
    ports:
      - "127.0.0.1:6379:6379"  # bind solo localhost
  ```
- **Effort**: 10 min
- **Status**: ⏳ TODO

---

### 5. **Shell Command Execution via subprocess_shell** [HIGH]
- **File**: `backend/actions/terminal_action.py:374-394`
- **Problema**: Usa `asyncio.create_subprocess_shell()` che invoca shell. Rischio anche con blacklist.
- **Impatto**: Shell injection se parser NL fallisce
- **Fix**:
  ```python
  # PRIMA: (rischioso)
  proc = await asyncio.create_subprocess_shell(cmd, ...)
  
  # DOPO: (safe)
  proc = await asyncio.create_subprocess_exec(
    parsed_cmd[0], *parsed_cmd[1:], 
    stdout=asyncio.subprocess.PIPE,
    ...
  )
  ```
- **Effort**: 30 min (test nuova parsing)
- **Status**: ⏳ TODO

---

## 🟠 HIGH — Stabilità & Performance

### 6. **Monolithic routes.py (1146 righe)** [HIGH]
- **File**: `backend/api/routes.py`
- **Problema**: Tutte le route in un file. Unmaintainable, hard to test.
- **Impatto**: Difficile aggiungere feature, debug complesso
- **Fix**: Splitta in:
  - `routes_chat.py` — `/api/chat`, `/api/chats`, `/api/feedback`
  - `routes_rpa.py` — `/api/rpa/*`
  - `routes_system.py` — `/api/status`, `/api/system/metrics`, `/api/system/logs`
  - `routes_git.py` — `/api/git/*`
  - `routes_memory.py` — `/api/memory/*`, `/api/rag/*`
  - `routes_focus.py` — `/api/focus/*`
  - `routes_briefing.py` — `/api/briefing/*`
  - Main `routes.py` include via router
- **Effort**: 2-3 ore
- **Status**: ⏳ TODO

---

### 7. **psutil.cpu_percent(interval=0.3) Blocks Async** [HIGH]
- **File**: `backend/api/routes.py:84-88`
- **Problema**: Ogni call `/api/system/metrics` blocca 300ms. Causa lag se LLM sta elaborando.
- **Impatto**: Response time lento, CPU waste
- **Fix**:
  ```python
  # PRIMA: (blocca)
  cpu = psutil.cpu_percent(interval=0.3)
  
  # DOPO: (non-blocking)
  # Primo call senza interval per cache
  if not hasattr(_metrics_cache, 'last_cpu_time'):
    _metrics_cache.last_cpu_time = psutil.cpu_times()
  cpu = psutil.cpu_percent(interval=None)  # istantaneo
  ```
- **Alternativa**: Background task aggiorna metriche ogni 2s, frontend legge cache
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

### 8. **Frontend Metrics Polling Every 2 Seconds** [HIGH]
- **File**: `frontend/src/App.tsx:78`
- **Problema**: `setInterval(fetchMetrics, 2000)` = 30 req/min. Troppe.
- **Impatto**: CPU waste, network congestion, LLM starved
- **Fix**:
  ```typescript
  // Aumenta a 5-10 secondi
  const METRICS_INTERVAL = 5000;  // configurable
  useEffect(() => {
    fetchMetrics();
    const id = setInterval(fetchMetrics, METRICS_INTERVAL);
    return () => clearInterval(id);
  }, [fetchMetrics]);
  ```
- **Alternativa**: WebSocket push-based (metriche inviate dal server quando cambiano)
- **Effort**: 20 min
- **Status**: ⏳ TODO

---

### 9. **Unbounded Semantic Cache (Memory Leak)** [HIGH]
- **File**: `backend/brain/multiagent.py:124`
- **Problema**: `_SEMANTIC_CACHE` dict cresce a infinite entries. No TTL, no LRU.
- **Impatto**: Memory leak, old queries mai ripuliti
- **Fix**:
  ```python
  from functools import lru_cache
  import time
  
  # PRIMA: global dict
  _SEMANTIC_CACHE: dict[str, tuple[str, str]] = {}
  
  # DOPO: con TTL
  class SemanticCache:
    def __init__(self, ttl=3600):
      self.cache = {}
      self.ttl = ttl
    
    def get(self, query_hash):
      if query_hash in self.cache:
        cached_val, timestamp = self.cache[query_hash]
        if time.time() - timestamp < self.ttl:
          return cached_val
        else:
          del self.cache[query_hash]
      return None
    
    def set(self, query_hash, val):
      self.cache[query_hash] = (val, time.time())
      # Mantenere max 500 entry
      if len(self.cache) > 500:
        oldest = min(self.cache.items(), key=lambda x: x[1][1])
        del self.cache[oldest[0]]
  ```
- **Effort**: 1 ora
- **Status**: ⏳ TODO

---

### 10. **SQLite Connection Per Method (No Pooling)** [MEDIUM]
- **File**: `backend/chat/chat_manager.py:19-22`
- **Problema**: `sqlite3.connect()` chiamato ogni volta. No pooling, handle leak risk.
- **Impatto**: Performance degrade, connection exhaustion
- **Fix**: Context manager singleton
  ```python
  class ChatDB:
    _conn = None
    _lock = threading.Lock()
    
    @classmethod
    def get_connection(cls):
      if cls._conn is None:
        with cls._lock:
          if cls._conn is None:
            cls._conn = sqlite3.connect(
              'data/chats.db',
              check_same_thread=False,
              timeout=10
            )
            cls._conn.execute("PRAGMA journal_mode=WAL")
      return cls._conn
    
    @classmethod
    def close(cls):
      if cls._conn:
        cls._conn.close()
  ```
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

### 11. **Timezone-Naive Datetimes (Inconsistent)** [MEDIUM]
- **File**: `backend/api/routes.py:104`, `backend/brain/multiagent.py:280` (+ multiple)
- **Problema**: Mix di `datetime.now()` (local) e `datetime.now(timezone.utc)` (UTC)
- **Impatto**: Bug nei timestamp, comparison fail
- **Fix**: Standardizzare **tutto a UTC**
  ```python
  # Globale util
  def now_utc():
    return datetime.now(timezone.utc)
  
  # Rimpiazzare tutti datetime.now() con now_utc()
  ```
- **Effort**: 1 ora (grep + replace)
- **Status**: ⏳ TODO

---

### 12. **No Rate Limiting on /api/chat** [MEDIUM]
- **File**: `backend/api/routes.py:251-391`
- **Problema**: Nessun limite. Potenziale DoS via abuse/bot loop.
- **Impatto**: LLM resource exhaustion
- **Fix**: Rate limit middleware
  ```python
  from slowapi import Limiter
  from slowapi.util import get_remote_address
  
  limiter = Limiter(key_func=get_remote_address)
  
  @router.post("/chat")
  @limiter.limit("10/minute")  # 10 chat per minuto
  async def chat(request: Request, payload: ChatRequest):
    ...
  ```
- **Effort**: 30 min (+ Redis setup se distribuito)
- **Status**: ⏳ TODO

---

### 13. **Chat Message Saved BEFORE Execution** [MEDIUM]
- **File**: `backend/api/routes.py:278-279`
- **Problema**: `add_message()` chiamato prima che azione completi. Se fallisce, user vede azione non eseguita.
- **Impatto**: Confusion, false state
- **Fix**:
  ```python
  # PRIMA:
  chat_mgr.add_message("user", text)
  response = await multiagent.chat(...)  # se fallisce qui...
  
  # DOPO:
  try:
    response = await multiagent.chat(...)
  except Exception as e:
    response = f"Errore: {str(e)}"
  finally:
    chat_mgr.add_message("user", text)
    chat_mgr.add_message("assistant", response, intent)
  ```
- **Effort**: 20 min
- **Status**: ⏳ TODO

---

## 🟡 MEDIUM — UX & Code Quality

### 14. **File Upload No Progress Indicator** [MEDIUM]
- **File**: `frontend/src/App.tsx:80-91`
- **Problema**: Upload blocca UI, user non sa se sta caricando.
- **Impatto**: Confusione, appear frozen
- **Fix**:
  ```typescript
  const [uploadProgress, setUploadProgress] = useState(0);
  
  const uploadFile = async (file: File) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener('progress', (e) => {
      setUploadProgress(Math.round((e.loaded / e.total) * 100));
    });
    // ... rest
  };
  
  return (
    <>
      <input onChange={handleFilePick} disabled={uploadProgress > 0} />
      {uploadProgress > 0 && <ProgressBar value={uploadProgress} />}
    </>
  );
  ```
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

### 15. **No Max Input Length Validation** [MEDIUM]
- **File**: `backend/api/routes.py:251-260`
- **Problema**: Utente potrebbe inviare 10MB text. Causa token overflow LLM, crash.
- **Impatto**: Backend crash, DoS
- **Fix**:
  ```python
  MAX_INPUT_LENGTH = 10000
  
  if len(payload.text) > MAX_INPUT_LENGTH:
    raise HTTPException(
      status_code=413,
      detail=f"Testo troppo lungo (max {MAX_INPUT_LENGTH} char)"
    )
  ```
- **Effort**: 10 min
- **Status**: ⏳ TODO

---

### 16. **Streaming State Race Condition** [MEDIUM]
- **File**: `backend/api/routes.py:355-372`
- **Problema**: Buffer reading e message state update non-atomic. Token persi se client disconnect mid-stream.
- **Impatto**: Message loss, data corruption
- **Fix**: Usa `anyio.CancelScope` + lock
  ```python
  from contextlib import asynccontextmanager
  
  @asynccontextmanager
  async def _stream_context():
    try:
      yield
    except asyncio.CancelledError:
      # Clean rollback su disconnect
      logger.info("Stream cancelled, rolling back")
      raise
  ```
- **Effort**: 1 ora
- **Status**: ⏳ TODO

---

### 17. **God Object MultiAgent** [MEDIUM]
- **File**: `backend/brain/multiagent.py:152-448`
- **Problema**: Fa 8 cose: cache, search, web search, RAG, ReAct loop, streaming, reflection, context mgmt.
- **Impatto**: Difficile testare, modificare, debug
- **Fix**: Refactor in moduli:
  - `cache_layer.py` — `SemanticCache` class
  - `rag_searcher.py` — `RAGSearcher` class
  - `web_searcher.py` — `WebSearcher` class
  - `react_orchestrator.py` — `ReactOrchestrator` class
  - `multiagent.py` — orchestration layer che usa i 4 sopra
- **Effort**: 3-4 ore
- **Status**: ⏳ TODO

---

### 18. **Duplicated Proxy Logic in RPA** [MEDIUM]
- **File**: `backend/actions/rpa_action.py:209-300`
- **Problema**: Same code pattern ripetuto 10 volte per screenshot, click, type, hotkey.
- **Impatto**: Hard to maintain, bug fix in un place ma non everywhere
- **Fix**:
  ```python
  async def _proxy_call(self, sub: str, params: dict) -> dict:
    """Generic proxy caller to host_rpa_server"""
    try:
      async with aiohttp.ClientSession() as session:
        async with session.post(
          f"{self.host_proxy_url}/rpa/{sub}",
          json=params,
          timeout=30
        ) as resp:
          return await resp.json()
    except Exception as e:
      logger.error(f"Proxy call {sub} failed: {e}")
      return {"error": str(e)}
  
  async def screenshot(self) -> dict:
    return await self._proxy_call("screenshot", {})
  
  async def click(self, x: int, y: int) -> dict:
    return await self._proxy_call("click", {"x": x, "y": y})
  ```
- **Effort**: 1-2 ore
- **Status**: ⏳ TODO

---

### 19. **Generic Error Message ("Errore di connessione")** [MEDIUM]
- **File**: `frontend/src/App.tsx:225`
- **Problema**: Non distingue 500 vs network timeout vs bad gateway.
- **Impatto**: User confusion, hard to debug
- **Fix**:
  ```typescript
  const handleChatError = (error: Error | Response) => {
    if (error instanceof Response) {
      if (error.status === 500) return "Errore server (500)";
      if (error.status === 503) return "Server unavailable";
      if (error.status === 0) return "Network unreachable";
    }
    if (error.message.includes("timeout")) return "Request timed out";
    return `Errore: ${error.message}`;
  };
  ```
- **Effort**: 30 min
- **Status**: ⏳ TODO

---

### 20. **Session Persistence Not Validated** [MEDIUM]
- **File**: `frontend/src/App.tsx:52, 212`
- **Problema**: `activeSessionId` da localStorage mai validato lato server.
- **Impatto**: Crash se session deleted, orphaned state
- **Fix**:
  ```typescript
  useEffect(() => {
    if (activeSessionId) {
      // Validate session exists
      fetch(`/api/chats/${activeSessionId}`)
        .catch(() => {
          setChatHistory([]);  // reset se non esiste
          localStorage.removeItem('activeSessionId');
        });
    }
  }, [activeSessionId]);
  ```
- **Effort**: 20 min
- **Status**: ⏳ TODO

---

### 21. **CORS Too Permissive** [MEDIUM]
- **File**: `backend/main.py:22-26`
- **Problema**: `allow_methods=["*"], allow_headers=["*"]` allow everything.
- **Impatto**: Security risk, CSRF potential
- **Fix**:
  ```python
  app.add_middleware(
    CORSMiddleware,
    allow_origins=config["server"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
  )
  ```
- **Effort**: 10 min
- **Status**: ⏳ TODO

---

### 22. **Threading Not Safe on SQLite** [MEDIUM]
- **File**: `backend/chat/chat_manager.py:45-54`
- **Problema**: Lock esiste ma `._conn()` crea new connection. Multi-thread race.
- **Impatto**: Data corruption, race condition
- **Fix**: Usare connection singleton (vedi item 10)
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

## 🔵 LOW — Polish & Minor Fixes

### 23. **Auto-Scroll Disorienting** [LOW]
- **File**: `frontend/src/App.tsx:231`
- **Fix**: Solo scroll se user near bottom
  ```typescript
  useEffect(() => {
    const container = chatContainerRef.current;
    if (container) {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
      if (isNearBottom) chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);
  ```
- **Effort**: 15 min
- **Status**: ⏳ TODO

---

### 24. **Feedback Buttons No Visual Feedback** [LOW]
- **File**: `frontend/src/App.tsx:54-62`
- **Fix**: Disable + change color
  ```typescript
  <button 
    onClick={() => sendFeedback(...)}
    disabled={feedbackSent[msgId] !== undefined}
    style={{ 
      color: feedbackSent[msgId] ? 'green' : 'inherit',
      opacity: feedbackSent[msgId] ? 0.5 : 1
    }}
  >
    {feedbackSent[msgId] ? '✓' : '↑'}
  </button>
  ```
- **Effort**: 15 min
- **Status**: ⏳ TODO

---

### 25. **Dead Code: DOCKER_API Empty** [LOW]
- **File**: `frontend/src/App.tsx:18`
- **Fix**: Rimuovi `const DOCKER_API = ""`, usa solo `API_URL`
- **Effort**: 5 min
- **Status**: ⏳ TODO

---

### 26. **Magic Constants Hardcoded** [LOW]
- **File**: `backend/api/routes.py:26-36` (+ multiple)
- **Fix**: Sposta in `config.py`
  ```python
  UPLOAD_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB
  PENDING_ACTION_TTL = 300  # 5 min
  INPUT_MAX_LENGTH = 10000
  CHAT_RATE_LIMIT = "10/minute"
  METRICS_CACHE_TTL = 5
  ```
- **Effort**: 30 min
- **Status**: ⏳ TODO

---

### 27. **Silent Exception Catch-All** [LOW]
- **File**: `backend/api/routes.py:62-63`
- **Fix**: Almeno log
  ```python
  try:
    # ...
  except Exception as e:
    logger.exception("Feedback save failed")
  ```
- **Effort**: 10 min
- **Status**: ⏳ TODO

---

### 28. **Upload Directory Hardcoded** [LOW]
- **File**: `backend/api/routes.py:22-24`
- **Fix**: Leggi da config
  ```python
  UPLOAD_DIR = Path(config.get("storage", {}).get("upload_dir", "/app/data/uploads"))
  ```
- **Effort**: 5 min
- **Status**: ⏳ TODO

---

### 29. **JSON Parsing Silent Failure** [LOW]
- **File**: `backend/brain/multiagent.py:423-426`
- **Fix**: Log error
  ```python
  try:
    raw_args = json.loads(args_raw)
  except json.JSONDecodeError as e:
    logger.error(f"Failed to parse tool args: {args_raw[:100]}... - {e}")
    raw_args = {}
  ```
- **Effort**: 10 min
- **Status**: ⏳ TODO

---

### 30. **ReAct Loop Max Rounds No Hard Break** [LOW]
- **File**: `backend/brain/multiagent.py:383`
- **Problem**: Se LLM ignora "final answer", infinite loop?
- **Fix**:
  ```python
  for round in range(MAX_ROUNDS):  # MAX_ROUNDS = 5
    if round == MAX_ROUNDS - 1:
      # Force break
      return f"Max reasoning rounds reached. Last response: {last_response}"
  ```
- **Effort**: 15 min
- **Status**: ⏳ TODO

---

## 🚀 FEATURE ENHANCEMENTS & Potenziamenti

### 31. **Implementa Rate Limiting Distribuito** [HIGH]
- **Descrizione**: Attualmente no rate limit. Con Redis, implementare global rate limiting.
- **Beneficio**: Proteggere da DoS, abuse
- **Stack**: `slowapi` + Redis backend
- **Effort**: 1-2 ore
- **Status**: ⏳ TODO

---

### 32. **Add Authentication & Multi-User Support** [HIGH]
- **Descrizione**: Attualmente monouser. Aggiungere JWT + user accounts.
- **Beneficio**: Privacy, multi-user, enterprise-ready
- **Stack**: `python-jose` + SQLite users table
- **Effort**: 4-6 ore
- **Status**: ⏳ TODO

---

### 33. **Implement Logging Centralized** [HIGH]
- **Descrizione**: Attualmente log su stdout. Aggiungere structured logging + ELK o file rotation.
- **Beneficio**: Debug più facile, audit trail
- **Stack**: `python-json-logger` + `python-logstash`
- **Effort**: 2 ore
- **Status**: ⏳ TODO

---

### 34. **Add Monitoring & Alerting Dashboard** [MEDIUM]
- **Descrizione**: Prometheus exporter + Grafana dashboard
- **Beneficio**: Visibility, proactive alerts
- **Stack**: `prometheus_client` + Grafana
- **Effort**: 3-4 ore
- **Status**: ⏳ TODO

---

### 35. **Context Menu / Quick Actions** [MEDIUM]
- **Descrizione**: Tasto destro su messaggio → Copy, Share, Export, Regenerate
- **Beneficio**: UX improvement
- **Stack**: React context menu library
- **Effort**: 1-2 ore
- **Status**: ⏳ TODO

---

### 36. **Voice Commands Customization UI** [MEDIUM]
- **Descrizione**: Panel per aggiungere/modificare voice commands senza riavviare backend
- **Beneficio**: Personalizzazione semplice
- **Effort**: 2-3 ore
- **Status**: ⏳ TODO

---

### 37. **Export Chat to PDF with Formatting** [MEDIUM]
- **Descrizione**: Attualmente export solo text. Aggiungere PDF con styles, timestamps, images.
- **Beneficio**: Sharing, archiving
- **Stack**: `reportlab` o `weasyprint`
- **Effort**: 1-2 ore
- **Status**: ⏳ TODO

---

### 38. **Web Search Source Citations** [MEDIUM]
- **Descrizione**: Aggiungi link clickable alle fonti di web search in response
- **Beneficio**: Transparency, fact-checking
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

### 39. **Typing Indicator While Processing** [MEDIUM]
- **Descrizione**: Aggiungi "Jarvis sta scrivendo..." indicator
- **Beneficio**: UX improvement, meno confusion
- **Effort**: 30 min
- **Status**: ⏳ TODO

---

### 40. **Dark Mode Toggle UI** [LOW]
- **Descrizione**: Attualmente dark mode è default. Aggiungere button per toggle + save preference
- **Beneficio**: Accessibilità
- **Effort**: 30 min
- **Status**: ⏳ TODO

---

### 41. **Keyboard Shortcuts Reference** [LOW]
- **Descrizione**: Modal con lista shortcuts (Cmd+Enter send, Cmd+K focus search, etc.)
- **Beneficio**: Productivity boost
- **Effort**: 30 min
- **Status**: ⏳ TODO

---

### 42. **Batch Process Commands** [MEDIUM]
- **Descrizione**: Es. "leggi questi 5 file e riassumili". Multi-step orchestration UI.
- **Beneficio**: Complex workflows
- **Effort**: 3-4 ore
- **Status**: ⏳ TODO

---

### 43. **RAG Similarity Threshold UI** [LOW]
- **Descrizione**: Slider per regolare quanto "stretto" il match RAG (0.5 - 1.5)
- **Beneficio**: Fine-tuning risposta
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

### 44. **ChromaDB Vector Visualization** [MEDIUM]
- **Descrizione**: Visualizza embedding 3D nello spazio vettoriale (PCA/t-SNE)
- **Beneficio**: Debug RAG, capire similarities
- **Effort**: 2 ore
- **Status**: ⏳ TODO

---

### 45. **Implement Plugin System** [HIGH]
- **Descrizione**: Let users add custom actions/tools senza toccare backend code
- **Beneficio**: Extensibility, community contrib
- **Stack**: Python plugin loader + manifest.json
- **Effort**: 4-5 ore
- **Status**: ⏳ TODO

---

## 📊 TESTING & QA

### 46. **Add Unit Tests for Core Modules** [HIGH]
- **Coverage**: `brain/`, `memory/`, `chat/`
- **Framework**: `pytest` + `pytest-asyncio`
- **Target**: 70%+ coverage
- **Effort**: 4-6 ore
- **Status**: ⏳ TODO

---

### 47. **End-to-End Integration Tests** [HIGH]
- **Scope**: Full flow: user message → intent routing → action/chat → response
- **Framework**: `pytest` + local Redis/ChromaDB
- **Effort**: 3-4 ore
- **Status**: ⏳ TODO

---

### 48. **Load Testing (k6 / Locust)** [MEDIUM]
- **Scope**: 100 concurrent users, sustained 10 min
- **Target**: < 2s response time at p95
- **Effort**: 2 ore
- **Status**: ⏳ TODO

---

### 49. **Security Audit via OWASP ZAP** [MEDIUM]
- **Scope**: Auto-scan per XSS, CSRF, SQLi
- **Effort**: 1 ora + manual review
- **Status**: ⏳ TODO

---

## 🛠️ INFRASTRUCTURE & DEVOPS

### 50. **Add Health Check Endpoints** [MEDIUM]
- **Endpoints**: 
  - `/health` — basic alive
  - `/ready` — dependencies ready (Redis, Ollama, ChromaDB, SQLite)
- **Effort**: 30 min
- **Status**: ⏳ TODO

---

### 51. **Add Prometheus Metrics Export** [MEDIUM]
- **Metrics**: request latency, error rate, cache hit rate, LLM tokens, memory usage
- **Effort**: 1-2 ore
- **Status**: ⏳ TODO

---

### 52. **Implement Database Migrations (Alembic)** [MEDIUM]
- **Scope**: Version SQLite schema, rollback support
- **Effort**: 1-2 ore
- **Status**: ⏳ TODO

---

### 53. **Add Automated Backup of ChatDB** [LOW]
- **Scope**: Daily backup to S3 / local file, retention 30 days
- **Effort**: 1 ora
- **Status**: ⏳ TODO

---

### 54. **Docker Image Multi-Stage Optimization** [LOW]
- **Current**: ~600MB backend image
- **Target**: ~200MB (remove dev deps, slim base)
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

## 📋 SUMMARY — Priority Matrix

| Priority | Count | Effort | Focus |
|----------|-------|--------|-------|
| CRITICAL | 3 | 2 ore | Security first |
| HIGH | 9 | 15 ore | Stability + perf |
| MEDIUM | 18 | 25 ore | Features + UX |
| LOW | 7 | 5 ore | Polish |
| **ENHANCEMENTS** | 14 | 40 ore | Optional |
| **TESTING** | 4 | 10 ore | Recommended |

**Total Effort**: ~115 ore (2-3 sprints da 2 settimane)

---

## 🎯 Roadmap Consigliato

### **Sprint 1** (1 settimana) — Crítico & Stabilità
1. Fix path traversal + file upload security (items 1-5)
2. Split routes.py + multiagent refactor (items 6, 17)
3. Psutil blocking fix + metrics polling (items 7-8)
4. Rate limiting + auth (items 12, 32)

**Effort**: ~12 ore

---

### **Sprint 2** (1 settimana) — Performance & Quality
1. Semantic cache TTL (item 9)
2. SQLite connection pooling (item 10)
3. Timezone standardization (item 11)
4. Error handling + logging centralization (item 33)
5. Unit tests core modules (item 46)

**Effort**: ~15 ore

---

### **Sprint 3** (1 settimana) — UX & Polish
1. Upload progress indicator (item 14)
2. Input validation (item 15)
3. Error messages improvement (item 19)
4. Session validation (item 20)
5. Auto-scroll + feedback UX (items 23-24)

**Effort**: ~10 ore

---

### **Sprint 4+** (Optional) — Features & Enhancements
1. Monitoring + alerting (item 34)
2. Plugin system (item 45)
3. Export PDF (item 37)
4. Keyboard shortcuts + settings (items 41, 40)

**Effort**: ~20 ore

---

## ✅ Tracking

- [ ] CRITICAL security fixes (3)
- [ ] Code refactoring (6, 17, 18)
- [ ] Performance optimization (7, 8, 9, 10, 11)
- [ ] Testing suite (46, 47, 48)
- [ ] Enhancement features (31+)

---

**Last Updated**: 2026-06-17  
**Next Review**: 2026-07-01
