# J.A.R.V.I.S. — Lista di Miglioramenti & Fix

Data: 2026-06-17  
Statuto: **In Progress** (CRITICAL+HIGH ✅, ENHANCEMENTS 12/15 ✅, TESTING 1/4, INFRA 3/5)  
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
- **Status**: ✅ **Done** (os.path.basename + UUID rename + ext whitelist in routes.py)

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
- **Status**: ✅ **Done** (`_validate_ownership` in chat_manager.py + user_id in sessions table)

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
- **Status**: ✅ **Done** (BLOCKED_EXTENSIONS + ALLOWED_EXTENSIONS in constants.py)

---

### 4. **Redis Exposed Without Auth** [HIGH]
- **File**: `docker-compose.yml:28-29`
- **Problema**: Redis container su port 6379 senza password. Chiunque da host connette.
- **Impatto**: Redis hijacking, data theft, command injection
- **Fix**:
  ```yaml
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    ports:
      - "127.0.0.1:6379:6379"
  ```
  La password va inserita nel file `.env` (gitignorato) per non spingerla su GitHub.
- **Effort**: 10 min
- **Status**: ✅ **Done** (--requirepass + .env per secrets + env var passato a Redis/backend per healthcheck e rate limiter)

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
- **Status**: ✅ **Done** (uses asyncio.create_subprocess_exec instead of shell)

---

## 🟠 HIGH — Stabilità & Performance

### 6. **Monolithic routes.py (1234+ righe)** [HIGH]
- **File**: `backend/api/routes.py`
- **Problema**: Tutte le route in un file. Unmaintainable, hard to test.
- **Impatto**: Difficile aggiungere feature, debug complesso
- **Fix**: Splitta in moduli separati con `APIRouter.include_router()`
- **Effort**: 2-3 ore
- **Status**: ✅ **Done** (1259→386 righe. Nuovi file: schemas.py, routes_common.py, routes_chat.py, routes_system.py, routes_rpa.py)

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
  cpu = psutil.cpu_percent(interval=0)  # istantaneo
  ```
- **Effort**: 10 min
- **Status**: ✅ **Done** (uses interval=0 — non-blocking)

---

### 8. **Frontend Metrics Polling Every 2 Seconds** [HIGH]
- **File**: `frontend/src/App.tsx:78`
- **Problema**: `setInterval(fetchMetrics, 2000)` = 30 req/min. Troppe.
- **Impatto**: CPU waste, network congestion, LLM starved
- **Fix**:
  ```typescript
  const METRICS_INTERVAL = 5000;
  useEffect(() => {
    fetchMetrics();
    const id = setInterval(fetchMetrics, METRICS_INTERVAL);
    return () => clearInterval(id);
  }, [fetchMetrics]);
  ```
- **Effort**: 5 min
- **Status**: ✅ **Done** (5000ms interval from constants)

---

### 9. **Unbounded Semantic Cache (Memory Leak)** [HIGH]
- **File**: `backend/brain/multiagent.py:124`
- **Problema**: `_SEMANTIC_CACHE` dict cresce a infinite entries. No TTL, no LRU.
- **Impatto**: Memory leak, old queries mai ripuliti
- **Fix**: file `semantic_cache.py` dedicato
  ```python
  class SemanticCache:
    def __init__(self, ttl=3600, max_size=500):
      ...
  ```
- **Effort**: 1 ora
- **Status**: ✅ **Done** (dedicated semantic_cache.py with TTL + LRU + max_size)

---

### 10. **SQLite Connection Per Method (No Pooling)** [MEDIUM]
- **File**: `backend/chat/chat_manager.py:19-22`
- **Problema**: `sqlite3.connect()` chiamato ogni volta. No pooling, handle leak risk.
- **Impatto**: Performance degrade, connection exhaustion
- **Fix**: Singleton connection pool
  ```python
  class ChatDBConnection:
    _instance = None
    _lock = threading.Lock()
    ...
  ```
- **Effort**: 45 min
- **Status**: ✅ **Done** (ChatDBConnection singleton + db_connection.py)

---

### 11. **Timezone-Naive Datetimes (Inconsistent)** [MEDIUM]
- **File**: `backend/actions/focus_mode.py:155,178,296,466` (+ other)
- **Problema**: Mix di `datetime.now()` (local) e `datetime.now(timezone.utc)` (UTC)
- **Impatto**: Bug nei timestamp, comparison fail (TypeError: can't subtract naive-aware)
- **Fix**: Standardizzare **tutto a UTC**
  ```python
  def now_utc():
    return datetime.now(timezone.utc)
  
  # Rimpiazzare tutti datetime.now() con now_utc()
  ```
- **Effort**: 30 min (grep + replace)
- **Status**: ✅ **Done** (focus_mode.py fixed — all datetime.now() → datetime.now(timezone.utc))

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
- **Status**: ✅ **Done** (custom `_check_rate_limit` in routes.py)

---

### 13. **Chat Message Saved BEFORE Execution** [MEDIUM]
- **File**: `backend/api/routes.py:278-279`
- **Problema**: `add_message()` chiamato prima che azione completi. Se fallisce, user vede azione non eseguita.
- **Impatto**: Confusion, false state
- **Fix**:
  ```python
  try:
    response = await multiagent.chat(...)
  except Exception as e:
    response = f"Errore: {str(e)}"
  finally:
    chat_mgr.add_message("user", text)
    chat_mgr.add_message("assistant", response, intent)
  ```
- **Effort**: 20 min
- **Status**: ✅ **Done** (wrapped all execution paths in try/except with error fallback)

---

## 🟡 MEDIUM — UX & Code Quality

### 14. **File Upload No Progress Indicator** [MEDIUM]
- **File**: `frontend/src/App.tsx:80-91`
- **Problema**: Upload blocca UI, user non sa se sta caricando.
- **Impatto**: Confusione, appear frozen
- **Fix**:
  ```typescript
  const [uploading, setUploading] = useState(false);
  
  const uploadFile = async (file: File) => {
    setUploading(true);
    ...
    finally { setUploading(false); }
  };
  ```
- **Effort**: 30 min
- **Status**: ✅ **Done** (uploading state + spinning indicator in frontend)

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
- **Status**: ✅ **Done** (MAX_INPUT_LENGTH = 10000 in constants.py)

---

### 16. **Streaming State Race Condition** [MEDIUM]
- **File**: `backend/api/routes.py:355-372`
- **Problema**: Buffer reading e message state update non-atomic. Token persi se client disconnect mid-stream.
- **Impatto**: Message loss, data corruption
- **Fix**: Controllo `request.is_disconnected()` + `asyncio.CancelledError` handler
- **Effort**: 1 ora
- **Status**: ✅ **Done** (disconnect check nel loop, CancelledError catch, full_response salvato anche su cancellazione)

---

### 17. **God Object MultiAgent** [MEDIUM]
- **File**: `backend/brain/multiagent.py:152-448`
- **Problema**: Fa 8 cose: cache, search, web search, RAG, ReAct loop, streaming, reflection, context mgmt.
- **Impatto**: Difficile testare, modificare, debug
- **Fix**: Refactor in moduli:
  - `semantic_cache.py` — ✅ `SemanticCache` class
  - `rag_searcher.py` — ✅ `RAGSearcher` class
  - `web_searcher.py` — ✅ `WebSearcher` class
  - `multiagent.py` — orchestration layer ridotto
- **Effort**: 3-4 ore
- **Status**: ✅ **Done** (447→370 righe. Estratti RAGSearcher, WebSearcher, SemanticCache. ReAct loop + specialist prompts rimasti in multiagent.py)

---

### 18. **Duplicated Proxy Logic in RPA** [MEDIUM]
- **File**: `backend/actions/rpa_action.py:209-300`
- **Problema**: Same code pattern ripetuto 10 volte per screenshot, click, type, hotkey.
- **Impatto**: Hard to maintain, bug fix in un place ma non everywhere
- **Fix**: Metodo `_proxy_route()` centralizzato con dispatch per sub-comando
- **Effort**: 1-2 ore
- **Status**: ✅ **Done** (`_proxy_execute` da 90→30 righe, `_proxy_route()` centralizza endpoint + args + formatter)

---

### 19. **Generic Error Message ("Errore di connessione")** [MEDIUM]
- **File**: `frontend/src/App.tsx:225`
- **Problema**: Non distingue 500 vs network timeout vs bad gateway.
- **Impatto**: User confusion, hard to debug
- **Fix**:
  ```typescript
  const errorMessage = (err) => {
    if ((err as Error)?.name === "AbortError") return "Richiesta interrotta.";
    return `Errore di connessione al server. Verifica che il backend sia in esecuzione.`;
  };
  ```
- **Effort**: 30 min
- **Status**: ✅ **Done** (already specific: "Errore di connessione al server. Verifica che il backend sia in esecuzione." + AbortError distinction)

---

### 20. **Session Persistence Not Validated** [MEDIUM]
- **File**: `frontend/src/App.tsx:52, 212`
- **Problema**: `activeSessionId` da localStorage mai validato lato server.
- **Impatto**: Crash se session deleted, orphaned state
- **Fix**:
  ```typescript
  useEffect(() => {
    if (activeSessionId) {
      fetch(`/api/chats/${activeSessionId}`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      }).catch(() => {
        setChatHistory([]);
        localStorage.removeItem('activeSessionId');
        setMessages(p => [...p, {id:msgIdRef.current++,role:"system",text:"⚠️ Sessione scaduta..."}]);
      });
    }
  }, [activeSessionId]);
  ```
- **Effort**: 20 min
- **Status**: ✅ **Done** (validation + error message in session fetch)

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
- **Status**: ✅ **Done** (constants with ALLOWED_HTTP_METHODS + ALLOWED_HTTP_HEADERS, main.py uses config origins)

---

### 22. **Threading Not Safe on SQLite** [MEDIUM]
- **File**: `backend/chat/chat_manager.py:45-54`
- **Problema**: Lock esiste ma `._conn()` crea new connection. Multi-thread race.
- **Impatto**: Data corruption, race condition
- **Fix**: Usare connection singleton (vedi item 10)
- **Effort**: 45 min
- **Status**: ✅ **Done** (ChatDBConnection singleton + threading.Lock in db_connection.py)

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
- **Status**: ✅ **Done** (isNearBottom check at 100px threshold + smooth scroll)

---

### 24. **Feedback Buttons No Visual Feedback** [LOW]
- **File**: `frontend/src/App.tsx:54-62`
- **Fix**: Disable + change color
  ```typescript
  <span onClick={() => !feedbackSent[msg.id] && sendFeedback(...)}
    style={{
      color: feedbackSent[msg.id]===2 ? C.green : C.textFaint,
      opacity: feedbackSent[msg.id] ? 0.4 : 0.6,
    }}>
    {feedbackSent[msg.id]===2 ? "✓" : feedbackSent[msg.id] ? "" : "▲"}
  </span>
  ```
- **Effort**: 15 min
- **Status**: ✅ **Done** (color change, symbol change to ✓, opacity reduction on click)

---

### 25. **Dead Code: DOCKER_API Empty** [LOW]
- **File**: `frontend/src/App.tsx:18`
- **Fix**: Rimuovi `const DOCKER_API = ""`, usa solo `API_URL`
- **Effort**: 5 min
- **Status**: ✅ **Done** (removed, uses `API_URL` from constants + `HOST_METRICS_URL` for metrics proxy)

---

### 26. **Magic Constants Hardcoded** [LOW]
- **File**: `backend/api/routes.py:26-36` (+ multiple)
- **Fix**: Sposta in `constants.py`
  ```python
  UPLOAD_SIZE_LIMIT = 50 * 1024 * 1024
  PENDING_ACTION_TTL = 300
  INPUT_MAX_LENGTH = 10000
  ```
- **Effort**: 30 min
- **Status**: ✅ **Done** (all constants in backend/api/constants.py)

---

### 27. **Silent Exception Catch-All** [LOW]
- **File**: `backend/api/routes.py:62-63`
- **Fix**: Almeno log
  ```python
  except Exception as e:
    logger.debug("Temperature read failed: {e}")
  ```
- **Effort**: 10 min
- **Status**: ✅ **Done** (added logger.debug to temperature + logger.warning to web_search fallback)

---

### 28. **Upload Directory Hardcoded** [LOW]
- **File**: `backend/api/routes.py:22-24`
- **Fix**: Leggi da config
  ```python
  UPLOAD_DIR = Path(config.get("storage", {}).get("upload_dir", "/app/data/uploads"))
  ```
- **Effort**: 5 min
- **Status**: ✅ **Done** (uses `UPLOAD_DIR` from constants)

---

### 29. **JSON Parsing Silent Failure** [LOW]
- **File**: `backend/brain/multiagent.py:423-426`
- **Fix**: Log error
  ```python
  except json.JSONDecodeError:
    logger.error(f"JSON non valido negli argomenti di '{name}': {args_raw[:200]}")
    args_raw = {}
  ```
- **Effort**: 10 min
- **Status**: ✅ **Done** (logger.error with tool name + truncated args)

---

### 30. **ReAct Loop Max Rounds No Hard Break** [LOW]
- **File**: `backend/brain/multiagent.py:383`
- **Problem**: Se LLM ignora "final answer", infinite loop?
- **Fix**:
  ```python
  for round in range(MAX_ROUNDS):  # MAX_ROUNDS = 5
    if round == MAX_ROUNDS - 1:
      return f"Max reasoning rounds reached. Last response: {last_response}"
  ```
- **Effort**: 15 min
- **Status**: ✅ **Done** (`_max_react_rounds = 5` + loop guard)

---

## 🚀 FEATURE ENHANCEMENTS & Potenziamenti

### 31. **Implementa Rate Limiting Distribuito** [HIGH]
- **Descrizione**: Attualmente no rate limit. Con Redis, implementare global rate limiting.
- **Beneficio**: Proteggere da DoS, abuse
- **Stack**: `redis.asyncio` (ZSET sliding window) + fallback locale su deque
- **Effort**: 1-2 ore
- **Status**: ✅ **Done** (RateLimiter class in ratelimiter.py — Redis ZSET con fallback locale in-memory, _check_rate_limit aggiornato ad async)

---

### 32. **Add Authentication & Multi-User Support** [HIGH]
- **Descrizione**: Attualmente monouser. Aggiungere JWT + user accounts.
- **Beneficio**: Privacy, multi-user, enterprise-ready
- **Stack**: `python-jose` + `bcrypt` + SQLite users table
- **Effort**: 4-6 ore
- **Status**: ✅ **Done** (auth.py con register/login, JWT, bcrypt, users table, frontend login/register form)

---

### 33. **Implement Logging Centralized** [HIGH]
- **Descrizione**: Attualmente log su stdout. Aggiungere structured logging + ELK o file rotation.
- **Beneficio**: Debug più facile, audit trail
- **Stack**: `JSONFormatter` custom (timestamp ISO, level, logger, message, exception)
- **Effort**: 2 ore
- **Status**: ✅ **Done** (JSONFormatter in main.py — output strutturato con timestamp UTC, livello, logger e messaggio)

---

### 34. **Add Monitoring & Alerting Dashboard** [MEDIUM]
- **Descrizione**: Prometheus exporter + Grafana dashboard
- **Beneficio**: Visibility, proactive alerts
- **Stack**: `prometheus_client` + Grafana
- **Effort**: 3-4 ore
- **Status**: ✅ **Done** (MetricsMiddleware + /metrics endpoint con Counter/Histogram/Gauge per HTTP, LLM, cache, sistema. Resta da configurare Grafana per visualizzazione)

---

### 35. **Context Menu / Quick Actions** [MEDIUM]
- **Descrizione**: Tasto destro su messaggio → Copy, Share, Export, Regenerate
- **Beneficio**: UX improvement
- **Stack**: Menu contestuale custom inline React
- **Effort**: 1-2 ore
- **Status**: ✅ **Done** (right-click context menu su messaggi: Copia testo + Esporta messaggio come .txt)

---

### 36. **Voice Commands Customization UI** [MEDIUM]
- **Descrizione**: Panel per aggiungere/modificare voice commands senza riavviare backend
- **Beneficio**: Personalizzazione semplice
- **Effort**: 2-3 ore
- **Status**: ✅ **Done** (GET/PUT /api/voice/settings + sidebar panel con wake word toggle/sensibilità, STT model/language, TTS engine/speed)

---

### 37. **Export Chat to PDF with Formatting** [MEDIUM]
- **Descrizione**: Attualmente export solo text. Aggiungere PDF con styles, timestamps, images.
- **Beneficio**: Sharing, archiving
- **Stack**: `fpdf2` (leggero, no dipendenze extra)
- **Effort**: 1-2 ore
- **Status**: ✅ **Done** (POST /api/export/pdf + pulsante 📕 in toolbar, DejaVu fonts, encoding latin-1 safe)

---

### 38. **Web Search Source Citations** [MEDIUM]
- **Descrizione**: Aggiungi link clickable alle fonti di web search in response
- **Beneficio**: Transparency, fact-checking
- **Effort**: 45 min
- **Status**: ✅ **Done** (sources displayed as clickable links in frontend)

---

### 39. **Typing Indicator While Processing** [MEDIUM]
- **Descrizione**: Aggiungi "Jarvis sta scrivendo..." indicator
- **Beneficio**: UX improvement, meno confusion
- **Effort**: 30 min
- **Status**: ✅ **Done** (indicatore con blink animation mostrato quando isResponding e tutti i system msg hanno testo)

---

### 40. **Dark Mode Toggle UI** [LOW]
- **Descrizione**: Attualmente dark mode è default. Aggiungere button per toggle + save preference
- **Beneficio**: Accessibilità
- **Effort**: 30 min
- **Status**: ✅ **Done** (☀️/🌙 toggle in toolbar + applyTheme function)

---

### 41. **Keyboard Shortcuts Reference** [LOW]
- **Descrizione**: Modal con lista shortcuts (Cmd+Enter send, Cmd+K focus search, etc.)
- **Beneficio**: Productivity boost
- **Effort**: 30 min
- **Status**: ✅ **Done** (Ctrl+Enter=submit, Escape=stop streaming, placeholder aggiornato)

---

### 42. **Batch Process Commands** [MEDIUM]
- **Descrizione**: Es. "leggi questi 5 file e riassumili". Multi-step orchestration UI.
- **Beneficio**: Complex workflows
- **Effort**: 3-4 ore
- **Status**: ⏳ TODO

---

### 43. **RAG Similarity Threshold UI** [LOW]
- **Descrizione**: Slider per regolare quanto "stretto" il match RAG (0.1 - 3.0)
- **Beneficio**: Fine-tuning risposta
- **Effort**: 45 min
- **Status**: ✅ **Done** (slider in toolbar → PUT /api/rag/threshold, variabile condivisa rag_distance_threshold in rag_searcher.py)

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
  - `/api/health` + `/api/ready` (DB, Redis, ChromaDB, LLM)
- **Effort**: 30 min
- **Status**: ✅ **Done** (HEAD/GET /api/health + /api/ready con try/catch per degraded status)

---

### 51. **Add Prometheus Metrics Export** [MEDIUM]
- **Metrics**: request latency, error rate, cache hit rate, LLM tokens, memory usage
- **Effort**: 1-2 ore
- **Status**: ✅ **Done** (/metrics endpoint + MetricsMiddleware + Counter/Histogram/Gauge per HTTP, LLM, cache, sistema)

---

### 52. **Implement Database Migrations (Alembic)** [MEDIUM]
- **Scope**: Version SQLite schema, rollback support
- **Effort**: 1-2 ore
- **Status**: ✅ **Done** (ALTER TABLE sessions ADD COLUMN user_id per pre-existing database + schema versioning)

---

### 53. **Add Automated Backup of ChatDB** [LOW]
- **Scope**: Daily backup to S3 / local file, retention 30 days
- **Effort**: 1 ora
- **Status**: ✅ **Done** (backup_db.py con SQLite .backup + retention + container periodico in docker-compose)

---

### 54. **Docker Image Multi-Stage Optimization** [LOW]
- **Current**: ~600MB backend image
- **Target**: ~200MB (remove dev deps, slim base)
- **Effort**: 45 min
- **Status**: ⏳ TODO

---

## 📋 SUMMARY — Priority Matrix

| Priority | Count | ✅ Done | ❌ TODO | Effort |
|----------|-------|---------|---------|--------|
| CRITICAL | 3 | 3 | 0 | 2 ore |
| HIGH | 9 | 9 | 0 | 15 ore |
| MEDIUM | 18 | 18 | 0 | 25 ore |
| LOW | 7 | 7 | 0 | 5 ore |
| **ENHANCEMENTS** | 14 | 11 | 3 | 40 ore |
| **TESTING** | 4 | 0 | 4 | 10 ore |

**Total Done**: ~51 items of ~55

---

## 🎯 Roadmap — Prossimi Passi

### **Todo Rimasti** (prioritari)
1. ❌ Rate limiting distribuito via Redis (item 31) — 1-2 ore
2. ❌ Auth / multi-user JWT (item 32) — 4-6 ore
3. ❌ Monitoring dashboard Prometheus (item 34) — 2-3 ore
4. ❌ Testing suite (items 46-48) — 8-10 ore

### **Enhancement opzionali**
1. Context menu / quick actions (item 35)
2. RAG similarity threshold UI (item 43)
3. Plugin system (item 45)
4. Automated backup (item 53)
5. Docker image optimization (item 54)

---

## ✅ Tracking

- [x] CRITICAL security fixes (3/3)
- [x] Code refactoring (6, 17, 18)
- [x] Performance optimization (7, 8, 9, 10, 11)
- [ ] Testing suite (46, 47, 48)
- [ ] Enhancement features (31+)

---

**Last Updated**: 2026-06-17  
### 42. **Batch Process Commands** [MEDIUM]
- **Descrizione**: Eseguire comandi multipli in sequenza (chat, wait, shell) con un'unica API
- **Beneficio**: Automazione multi-step, orchestrazione rapida
- **Stack**: `POST /api/batch` + frontend Sidebar
- **Effort**: 2-3 ore
- **Status**: ✅ **Done**

### 43. **RAG Threshold Slider** [HIGH]
- **Descrizione**: Slider per regolare soglia di similarità RAG in tempo reale
- **File**: `PUT /api/rag/threshold` + toolbar frontend
- **Effort**: 1-2 ore
- **Status**: ✅ **Done**

### 44. **ChromaDB Vector Visualization** [MEDIUM]
- **Descrizione**: Visualizzare embedding vettori (memories, knowledge, preferences) su scatter plot 2D
- **Beneficio**: Debug, explorazione dati, qualità RAG
- **Stack**: `GET /api/vectors` + Canvas scatter plot
- **Effort**: 3-4 ore
- **Status**: ✅ **Done**

### 45. **Plugin System** [HIGH]
- **Descrizione**: Framework plugin caricabili da directory esterna
- **Beneficio**: Estendibilità senza toccare core
- **Stack**: `plugins/` directory, `PluginBase` class, `POST /api/plugins/{name}/exec`
- **Effort**: 4-6 ore
- **Status**: ✅ **Done** (hello + echo plugin example)

### 46. **Test Suite — Core Modules** [HIGH]
- **Descrizione**: pytest per health, CORS, plugins, auth
- **Beneficio**: Regression prevention
- **Status**: ✅ **Done** (test_routes.py, test_auth.py)

### 47-49. **Test Suite — E2E / Load / Security** [HIGH]
- **Descrizione**: pytest per flussi completi, carico, security scan
- **Effort**: 6-8 ore
- **Status**: ⏳ TODO

### 50. **Backup Automatico** [MEDIUM]
- **File**: `scripts/backup_db.py`
- **Status**: ✅ **Done**

### 51. **Prometheus Metrics** [MEDIUM]
- **File**: `api/monitoring/metrics.py`
- **Status**: ✅ **Done**

### 52. **PDF Export** [MEDIUM]
- **File**: `POST /api/export/pdf`
- **Status**: ✅ **Done**

### 53. **Voice Settings UI** [MEDIUM]
- **File**: `PUT /api/voice/settings`
- **Status**: ✅ **Done**

### 54. **Docker Ottimizzazione Slim** [LOW]
- **Descrizione**: Multi-stage build già presente (builder→final). Ottimizzazione pip cache, backup image lightweight (~50MB vs 1.9GB)
- **Status**: ✅ **Done**

**Next Review**: 2026-07-01
