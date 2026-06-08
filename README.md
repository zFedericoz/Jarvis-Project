# J.A.R.V.I.S. — AI Assistant

Assistente AI personale ispirato a Iron Man, completamente locale.
Attivazione vocale ("Jarvis"), input testuale, HUD olografico 3D, risposta vocale.

> **7 step completati**: Core → Memoria → MultiAgent → Git → Terminale → Focus → RPA

## Architettura

```
┌─ Host Windows ──────────────────────────────────┐
│  Ollama (qwen2.5:14b) ←─── host.docker.internal │
│  ┌─ Docker ──────────────────────────────────┐   │
│  │  redis ← backend ← frontend (nginx)       │   │
│  └───────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

- **Ollama** gira nativamente su Windows (non in Docker)
- **Backend**, **Redis**, **Frontend** girano in container Docker
- Il backend si connette a Ollama via `host.docker.internal:11434`

## Requisiti

- **Windows 10/11** con Docker Desktop
- **~12 GB RAM** libera per il LLM (qwen2.5:14b ~9 GB + overhead)
- **~15 GB spazio su disco** (modelli inclusi)

## Primo avvio

### 1. Installa Ollama su Windows

Scarica da [ollama.com](https://ollama.com) e installa. Poi:

```powershell
ollama pull qwen2.5:14b
ollama pull mxbai-embed-large
```

### 2. Avvia J.A.R.V.I.S.

```powershell
mkdir data\chroma_db data\screenshots models
docker compose up -d --build
```

### 3. Apri il browser

http://localhost:80

## Funzionalità

### Chat intelligente
- RAG automatico su ChromaDB (memoria a lungo termine)
- Web search automatico (DuckDuckGo) per domande su notizie/meteo/attualità
- Routing a 5 specialisti (code, creative, research, action, general)
- Reflection engine per auto-valutazione qualità (disabilitabile su CPU)
- Feedback utente (▲/▼) salvato in `data/feedback.jsonl`

### Git integration
- `"committa tutto"` → auto `git add -A` + messaggio Conventional Commit generato dal LLM
- `"mostra lo status"`, `"ultimi 10 commit"`, `"fai il push"`, `"crea un branch"`, `"stash"`, `"diff"`

### Terminale sicuro
- 60+ pattern pericolosi bloccati (rm -rf, format, sudo, cmd.exe)
- Whitelist per categoria: info, filesystem, python, network, docker
- Linguaggio naturale: `"che versione di Python ho?"` → `python --version`
- Timeout (15s) e output cappato

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

### Sistema vocale completo
- Wake word "Jarvis" via Porcupine (offline, nessuna API key)
- STT: faster-whisper (modello base, CPU, int8)
- TTS: kokoro → XTTS (clone vocale) → edge-tts fallback

## API principali

| Endpoint | Descrizione |
|----------|-------------|
| `GET /api/status` | Stato sistema |
| `GET /api/system/metrics` | CPU/RAM/temp/disk + storico |
| `POST /api/chat` | Chat testuale |
| `WS /api/ws/audio` | Streaming audio → risposta vocale |
| `POST /api/git/command` | Comando Git |
| `POST /api/terminal/run` | Comando shell sicuro |
| `POST /api/focus/start` | Avvia Pomodoro |
| `POST /api/rpa/click` | Click mouse |
| `POST /api/rpa/screenshot` | Screenshot desktop |
| `POST /api/rpa/analyze` | Screenshot + analisi AI |

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

## Trasferimento su nuovo PC (con GPU NVIDIA)

Su PC con GPU NVIDIA (es. RTX 4060 Ti), i tempi di risposta passano da minuti a <1 secondo.

Segui le istruzioni in [ARCHITECTURE.md](ARCHITECTURE.md) per la configurazione.

## Note tecniche

- **LLM**: Ollama + qwen2.5:14b (o qualunque modello supportato), keep_alive=-1
- **Memoria**: Redis (breve termine, 1h) + ChromaDB (lungo termine, RAG)
- **Reflection**: auto-valutazione qualità (disabilitata su CPU)
- **Frontend**: React + Three.js (Arc Reactor 3D), metriche real-time, waveform audio
- **GPU**: `num_gpu: -1` in settings.yaml → auto-detect
- **Niente cloud**: tutto gira in locale
