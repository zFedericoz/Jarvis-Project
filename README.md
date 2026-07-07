# J.A.R.V.I.S. — AI Assistant

Assistente AI personale ispirato a Iron Man, completamente locale.
Attivazione vocale ("Jarvis"), input testuale, HUD olografico 3D, risposta vocale.

> **GPU acceleration**: STT (faster-whisper CUDA), XTTS voice cloning su GPU, YOLO vision
> **Features**: Streaming TTS progressivo, VAD interrupt, vision monitoring, cache semantica, RAG aggressivo

## Architettura

```
┌─ Host Windows ───────────────────────────────────────┐
│  Ollama (qwen3:8b) ←─── host.docker.internal         │
│  host_metrics_server (:18765) ←─── host.docker.internal │
│  host_rpa_server     (:18766) ←─── host.docker.internal │
│  ┌─ Docker ───────────────────────────────────────┐   │
│  │  redis ← backend ← frontend (nginx)            │   │
│  │  backend ──> SQLite (chat)                     │   │
│  └────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────┘
```

- **Ollama** gira nativamente su Windows (non in Docker)
- **Backend**, **Redis**, **Frontend** girano in container Docker
- Il backend si connette a Ollama via `host.docker.internal:11434`
- **Chat persistenti**: SQLite (`data/chats.db`) con sessioni multiple, auto-titolo, cronologia
- **GPU NVIDIA**: supporto CUDA per STT (faster-whisper float16), XTTS voice cloning, YOLO vision
- **Streaming TTS**: sintesi vocale progressiva — frasi inviate appena pronte, non in blocco
- **Vision monitoring**: telecamera in background con YOLO, broadcast eventi in tempo reale via WebSocket

## Requisiti Hardware

I requisiti variano in base al modello LLM scelto. J.A.R.V.I.S. supporta qualsiasi modello Ollama; i due modelli di riferimento sono:

| Modello | Parametri | Attivi per token | Qualità | Download |
|---------|-----------|-----------------|---------|----------|
| **qwen3:8b** | 8.5B | 8.5B | Buona | ~4.7 GB |
| **qwen3:30b-a3b** | 30B (MoE) | 3B | Eccellente | ~18 GB |

> Il modello `qwen3:30b-a3b` usa architettura Mixture of Experts: ha 30B parametri totali ma ne attiva solo 3B a ogni token, offrendo qualità molto superiore con velocità paragonabile a un modello 3B.

### qwen3:8b — Requisiti minimi (CPU, risposta ~30-60 sec)

| Componente | Specifica |
|------------|----------|
| **CPU** | 4+ core, x86_64 con supporto AVX2 |
| **RAM** | 16 GB totali (di cui ~8 GB per LLM) |
| **GPU** | Nessuna (inferenza su CPU con int8) |
| **Disco** | 20 GB liberi (modello ~4.7 GB, whisper ~600 MB, chromaDB variabile) |
| **OS** | Windows 10/11 con Docker Desktop e WSL2 |
| **Rete** | Connessione Internet solo per primo download modelli |

### qwen3:8b — Requisiti consigliati (GPU, risposta <5 sec)

| Componente | Specifica |
|------------|----------|
| **CPU** | 6+ core moderno (es. Intel i5-12400 / AMD Ryzen 5 5600) |
| **RAM** | 16-32 GB DDR4/DDR5 |
| **GPU** | NVIDIA RTX 3060+ con **6+ GB VRAM** (o AMD con ROCm) |
| **Disco** | SSD NVMe con 30 GB liberi |
| **OS** | Windows 11 con Docker Desktop + WSL2 + CUDA Toolkit |
| **Rete** | Connessione Internet solo per primo download modelli |

### qwen3:30b-a3b — Requisiti minimi (CPU, risposta ~60-120 sec)

| Componente | Specifica |
|------------|----------|
| **CPU** | 8+ core moderno (es. Intel i7-12700 / AMD Ryzen 7 5700) |
| **RAM** | 32 GB totali (di cui ~18 GB per LLM) |
| **GPU** | Nessuna (inferenza su CPU con int8) |
| **Disco** | 40 GB liberi (modello ~18 GB, whisper ~600 MB, chromaDB variabile) |
| **OS** | Windows 10/11 con Docker Desktop e WSL2 |
| **Rete** | Connessione Internet solo per primo download modelli |

### qwen3:30b-a3b — Requisiti consigliati (GPU, risposta <10 sec)

| Componente | Specifica |
|------------|----------|
| **CPU** | 8+ core moderno |
| **RAM** | 32-64 GB DDR5 |
| **GPU** | NVIDIA RTX 4070+ / RTX 3090+ con **12+ GB VRAM** |
| **Disco** | SSD NVMe con 50 GB liberi |
| **OS** | Windows 11 con Docker Desktop + WSL2 + CUDA Toolkit |
| **Rete** | Connessione Internet solo per primo download modelli |

### Consumo risorse a regime

| Risorsa | qwen3:8b | qwen3:30b-a3b |
|---------|----------|---------------|
| RAM (LLM) | ~5-8 GB | ~16-20 GB |
| RAM (container + overhead) | ~1 GB | ~1 GB |
| RAM (chromaDB + redis) | ~500 MB | ~500 MB |
| CPU (idle, LLM in attesa) | ~2-5% | ~2-5% |
| CPU (durante generazione) | 100% su tutti i core | 100% su tutti i core |
| GPU VRAM (4-bit quantizzazione) | ~5 GB | ~10-12 GB |

> Nota: Con GPU NVIDIA, il LLM viene scaricato parzialmente sulla VRAM riducendo il carico sulla RAM di sistema. I tempi di risposta passano da minuti a <1-2 secondi (qwen3:8b) o ~5-10 secondi (qwen3:30b-a3b). Imposta `num_gpu: -1` in `settings.yaml` per abilitare auto-detect GPU.

## Primo avvio

### 1. Installa Ollama su Windows

Scarica da [ollama.com](https://ollama.com) e installa. Poi:

```powershell
:: Modello leggero (qwen3:8b) — consigliato per CPU / RAM ≤16 GB
ollama pull qwen3:8b

:: Modello pesante (qwen3:30b-a3b) — qualità superiore, serve GPU 12+ GB VRAM o 32+ GB RAM
:: ollama pull qwen3:30b-a3b

:: Modello per embedding (obbligatorio per RAG / memoria persistente)
ollama pull mxbai-embed-large
```

### 2. Avvia J.A.R.V.I.S.

**Metodo rapido (consigliato):**

```powershell
.\scripts\up.ps1
```

Lo script `up.ps1` si occupa di:
- Creare le directory necessarie (`data/`, `models/`)
- Avviare i container Docker con rebuild
- Avviare `host_metrics_server.py` (metriche CPU/RAM host Windows)
- Avviare `host_rpa_server.py` (azioni RPA su host Windows)
- All'uscita (Ctrl+C), fermare tutti i servizi

**Metodo manuale (solo Docker):**

```powershell
mkdir data\chroma_db data\screenshots models -Force
docker compose up -d --build
```

### 3. Apri il browser

http://localhost:80

### 4. (Opzionale) Wake word "Jarvis"

Scarica il file `jarvis.ppn` per Porcupine e mettilo in `models/porcupine/`.
https://github.com/Picovoice/porcupine/tree/master/resources/keyword_files/windows

## Funzionalità

### Chat persistente (multi-sessione)
- Sessioni multiple salvate su SQLite (`data/chats.db`)
- Sidebar con elenco chat, creazione, rinomina (doppio click sul titolo)
- Titolo generato automaticamente dal primo messaggio
- Cronologia completa caricata al click sulla sessione

### Chat intelligente
- RAG automatico su ChromaDB (memoria a lungo termine) — soglia 1.0, char_budget 6000
- **Cache semantica**: 2000 entry, TTL 4h, riduce chiamate LLM per domande simili
- Web search automatico (DuckDuckGo) per domande su notizie/meteo/attualità
- Routing a 5 specialisti (code, creative, research, action, general)
- Reflection engine per auto-valutazione qualità su TUTTE le risposte
- Feedback utente (▲/▼) salvato in `data/feedback.jsonl`

### Auto-miglioramento continuo (Self-Improvement)
- **Reflection universale**: ogni risposta viene auto-valutata (score 0-10) e se sufficiente (>7) salvata come esempio positivo nella knowledge base
- **Self-RAG**: prima di rispondere, cerca nella knowledge base esempi di alta qualità su domande simili e li inietta come few-shot
- **Bad feedback handling**: quando l'utente dà pollice giù, genera automaticamente una versione migliorata e la salva come correzione permanente
- **Auto-tuning**: ogni 50 risposte analizza la media rating e aggiusta automaticamente la soglia RAG
- **Benchmark giornaliero**: esegue un test su 5 domande campione, traccia accuracy e salva report in `data/self_improvement_benchmark.json`
- **Fine-tuning dataset**: esporta coppie Q&A da feedback.jsonl + knowledge base in `data/finetuning_dataset.jsonl`

### Git integration
- `"committa tutto"` → auto `git add -A` + messaggio Conventional Commit generato dal LLM
- `"mostra lo status"`, `"ultimi 10 commit"`, `"fai il push"`, `"crea un branch"`, `"stash"`, `"diff"`

### Terminale sicuro
- 60+ pattern pericolosi bloccati (rm -rf, format, sudo, cmd.exe)
- Whitelist per categoria: info, filesystem, python, network, docker
- Linguaggio naturale: `"che versione di Python ho?"` → `python --version`
- Timeout (15s) e output cappato

### Autenticazione JWT
- Registrazione e login con password hashata (bcrypt)
- Token JWT con scadenza configurabile
- Secret key da `.env` (`JWT_SECRET`), mai hardcoded
- Protezione endpoint API

### System control sicuro
- Comandi distruttivi (spegnimento, riavvio) con doppia conferma
- Matching a word boundary (`\b`) — "sicuramente" non attiva conferma per "si"
- Logica deny-before-confirm: negazione esplicita blocca prima della conferma
- Timeout (30s) su conferme pendenti

### Plugin system
- Plugin Python caricati dinamicamente da `plugins/`
- API hook: `on_startup`, `on_message`, `on_shutdown`
- Plugin inclusi: `weather_alert` (meteo via wttr.in), `smart_timer` (timer/promemoria in memoria)

### Focus mode (Pomodoro)
- Lavoro 25min → pausa breve 5min → pausa lunga 15min ogni 4 cicli
- Blocco siti distraenti via hosts file di Windows
- Windows Focus Assist (Non Disturbare) automatico
- Notifiche toast + annunci TTS a ogni cambio fase

### RPA / UI Automation
- Screenshot + analisi con LLM vision
- Click (singolo/doppio/destro), digitazione testo, hotkey
- Apertura app (Chrome, VSCode, Notepad, Discord, Spotify, ...)
- Scroll, drag & drop, info schermo
- Tutto via comando vocale in linguaggio naturale

### Vision (YOLO + telecamera)
- Rilevamento oggetti in tempo reale con YOLOv8 su GPU
- **Vision monitoring**: analisi continua della telecamera in background
- Broadcast eventi via WebSocket al frontend
- On-demand: "Cosa vedi?" via comando vocale

### Media player
- Spotify Web API (Client Credentials) per controllo riproduzione
- Fallback a tasti multimedia Windows se Spotify non configurato
- Supporto comandi vocali: riproduci, pausa, successivo, volume

### Sistema vocale completo
- Wake word "Jarvis" via Porcupine (offline, nessuna API key)
- STT: faster-whisper (modello small, GPU CUDA float16, fallback CPU int8)
- TTS a 3 livelli: kokoro-onnx (primario, veloce) → XTTS v2 (voice cloning su GPU) → edge-tts (fallback cloud)
- **Streaming TTS progressivo**: risposta divisa in frasi, sintetizzata e inviata singolarmente
- **VAD interrupt**: rilevamento vocale durante TTS, interruzione immediata se l'utente parla

## API principali

| Endpoint | Descrizione |
|----------|-------------|
| `GET /api/status` | Stato sistema |
| `GET /api/system/metrics` | CPU/RAM/temp/disk + storico |
| `POST /api/chat` | Chat testuale (con/senza sessione) |
| `GET /api/chats` | Elenco sessioni chat |
| `POST /api/chats` | Nuova sessione chat |
| `GET /api/chats/{id}/messages` | Messaggi di una sessione |
| `WS /api/ws/audio` | Streaming audio → risposta vocale (con streaming TTS progressivo) |
| `WS /api/ws` | WebSocket principale (vision monitoring, eventi in tempo reale) |
| `POST /api/auth/register` | Registrazione utente |
| `POST /api/auth/login` | Login, restituisce JWT |
| `POST /api/git/command` | Comando Git |
| `POST /api/terminal/run` | Comando shell sicuro |
| `POST /api/focus/start` | Avvia Pomodoro |
| `POST /api/rpa/click` | Click mouse |
| `POST /api/rpa/screenshot` | Screenshot desktop |
| `POST /api/rpa/analyze` | Screenshot + analisi AI |
| `GET /api/self-improvement/stats` | Statistiche auto-miglioramento |
| `GET /api/self-improvement/benchmark` | Report ultimo benchmark |
| `POST /api/self-improvement/benchmark` | Esegui benchmark manuale |
| `GET /api/self-improvement/knowledge-base` | Elenca knowledge base |

## Comandi vocali d'esempio

| Cosa dire | Cosa fa |
|-----------|---------|
| "Ehi Jarvis, ciao" | Saluto |
| "Committa tutto" | Git add + commit |
| "Che versione di Python ho?" | Terminale sicuro |
| "Avvia la modalità focus per 45 minuti" | Pomodoro |
| "Aggiungi reddit.com alla blacklist focus" | Blocca sito |
| "Fai uno screenshot" | Cattura schermo |
| "Clicca su 500, 300" | Click coordinata |
| "Apri Chrome" | Avvia browser |
| "Cerca su Internet le ultime notizie" | Web search |
| "Spegni il computer" | System control |

## Personalizzazione

Modifica `backend/config/settings.yaml` per: modello LLM, durata focus, comandi terminale consentiti, sensibilità RPA, ecc.

Modifica `backend/config/persona.yaml` per cambiare tono e comportamento.

Per il fine-tuning del LLM, consulta `GUIDA.md` e usa `dataset_finetune.jsonl`.

## Trasferimento su nuovo PC (con GPU NVIDIA)

Su PC con GPU NVIDIA (es. RTX 4060 Ti con 8 GB VRAM), i tempi di risposta passano da minuti a <1 secondo.
Imposta `num_gpu: -1` in `settings.yaml` per abilitare GPU.

Segui le istruzioni in [ARCHITECTURE.md](ARCHITECTURE.md) per la configurazione.

## Note tecniche

- **LLM**: Ollama + qwen3:8b (o qualunque modello supportato), keep_alive=-1
- **Memoria**: Redis (breve termine, 1h) + ChromaDB (lungo termine, RAG, 3 collezioni: jarvis_memories, jarvis_knowledge, jarvis_preferences)
- **Chat**: SQLite (sessioni multiple, auto-titolo, persistente su volume Docker)
- **Reflection**: auto-valutazione qualità (disabilitata su CPU)
- **Frontend**: React + Three.js (Arc Reactor 3D), metriche real-time, waveform audio, Inter/JetBrains Mono font
- **GPU**: `num_gpu: -1` in settings.yaml → auto-detect. STT: CUDA float16 (modello small). XTTS: singleton in GPU, warmup all'avvio. Vision: YOLOv8 su GPU
- **Docker**: 4 container (backend :8765, frontend nginx :80, redis con password, backup). GPU commentata in compose, sbloccare con Dockerfile.cuda
- **Auth**: JWT con secret da .env, prima registrazione via frontend o API `/api/auth/register`
- **Niente cloud**: tutto gira in locale
