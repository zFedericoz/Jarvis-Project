# Architettura di J.A.R.V.I.S.

```
Jarvis-Project/
├── docker-compose.yml          Orchestra 3 servizi (redis, backend, frontend)
├── backend/                    FastAPI (Python 3.11)
│   ├── main.py                 Entrypoint: crea app FastAPI, carica config, avvia uvicorn
│   ├── requirements.txt        Dipendenze Python
│   ├── Dockerfile              Multi-stage: builder + runtime leggero
│   ├── config/
│   │   ├── settings.yaml       Config: LLM, speech, vision, memoria, azioni, git, terminal, focus, RPA
│   │   └── persona.yaml        System prompt bilingue (IT/EN) per il LLM
│   ├── api/
│   │   ├── routes.py           20+ endpoint REST + 2 WebSocket (893 righe)
│   │   ├── websocket_manager   ConnectionManager + handler wake word + handler audio stream
│   │   └── dependencies.py     Factory functions (get_config, get_brain, get_speech, get_actions, get_memory)
│   ├── brain/
│   │   ├── llm_client.py       Ollama Client: chat(), chat_with_reflection(), warmup(), detect_language()
│   │   ├── multiagent.py       MultiAgent: 5 specialisti + RAG + web search + contesto utente
│   │   ├── intent_router.py    Classifica l'intento (9 categorie + fallback chat)
│   │   └── context_manager.py  Mantiene cronologia conversazione con riepilogo automatico
│   ├── speech/
│   │   ├── stt.py              Speech-to-Text via faster-whisper
│   │   └── tts.py              Text-to-Speech: kokoro → XTTS (clone vocale) → edge-tts fallback
│   ├── wake_word/
│   │   └── processor.py        Porcupine wrapper: process() restituisce true/false
│   ├── actions/
│   │   ├── base_action.py      Classe astratta per le azioni
│   │   ├── system_control.py   Volume, shutdown, restart, lock screen
│   │   ├── web_search.py       Cerca su web via DuckDuckGo
│   │   ├── media_player.py     Controllo media (play/pausa/next/prev via scan code)
│   │   ├── productivity.py     Timer, reminders, delega a FocusMode
│   │   ├── focus_mode.py       Pomodoro: lavoro/pausa, site blocking (hosts file), Focus Assist Windows
│   │   ├── vision.py           Analisi webcam con YOLOv8
│   │   ├── git_action.py       Git: commit (LLM), status, log, push, pull, branch, stash, diff
│   │   ├── terminal_action.py  Terminale sicuro: blacklist + whitelist + timeout + NL parsing
│   │   └── rpa_action.py       UI Automation: click, type, hotkey, scroll, drag, screenshot, vision analysis
│   ├── memory/
│   │   ├── ephemeral.py        Redis: memoria a breve termine (TTL 1h)
│   │   └── persistent.py       ChromaDB: memoria a lungo termine (vettoriale) + preferenze utente
│   └── vision/
│       └── camera.py           Riconoscimento oggetti YOLOv8
├── frontend/                   React + TypeScript + Three.js
│   ├── Dockerfile              Build → Nginx statico con proxy_pass per /api/
│   ├── package.json            dipendenze: react, three, @react-three/fiber, framer-motion, zustand
│   ├── src/
│   │   ├── App.tsx             Orchestratore: Arc Reactor 3D, dashboard metriche, chat, log, feedback
│   │   ├── main.tsx            Entrypoint React
│   │   ├── components/
│   │   │   ├── HolographicDisplay.tsx    Anelli 3D concentrici + orbite rotanti (Three.js)
│   │   │   ├── ParticleField.tsx         Campo particellare 3D
│   │   │   ├── VoiceVisualizer.tsx       Visualizzatore audio 3D (instanced mesh)
│   │   │   ├── ChatPanel.tsx             Input testo + file attachment + feedback ▲/▼ + TTS playback
│   │   │   ├── Dashboard.tsx             HUD: ora, data, connessione
│   │   │   └── StatusIndicator.tsx       Pulsante microfono + stati (idle/listening/processing/speaking)
│   │   ├── hooks/
│   │   │   ├── useWakeWord.ts            Cattura microfono PCM16 → WS → Porcupine
│   │   │   ├── useAudioStream.ts         Cattura audio per trascrizione → WS
│   │   │   ├── useWebSocket.ts           Gestisce messaggi JSON + audio binario (auto-reconnect)
│   │   │   ├── useTTSPlayer.ts           Riproduce blob audio WAV (Web Audio API)
│   │   │   └── useStore.ts               Stato globale (zustand)
│   │   ├── utils/constants.ts            URL, colori, animazioni, particelle
│   │   ├── types/index.ts                Definizioni TypeScript
│   │   └── styles/globals.css            Stili scanline, vignetta, font, CRT overlay
│   ├── index.html
│   ├── tsconfig.json
│   └── vite.config.ts
├── models/                    (montato come volume Docker)
│   ├── voice/jarvis_sample.wav   [fornito dall'utente] campione per XTTS
│   ├── piper/                    [automatico] modelli voce Piper
│   ├── porcupine/jarvis.ppn      [da scaricare] file Porcupine personalizzato
│   └── whisper/                  [automatico] modello faster-whisper (base)
├── data/                       (montato come volume Docker)
│   ├── chroma_db/              Persistenza memoria a lungo termine
│   ├── screenshots/            Screenshot RPA
│   └── feedback.jsonl          Feedback utente (rating, messaggio, intento)
└── scripts/
    ├── run.ps1                 Avvio diretto (senza Docker)
    └── setup_models.ps1        Download modelli Ollama + setup
```

## Flusso di elaborazione

### Input testuale (`POST /api/chat`)

```
Browser (testo)  ──POST──>  Nginx  ──>  backend /api/chat
                                      │
                                      ├─ PersistentMemory.search() (RAG: 3 chunk)
                                      │
                                      ├─ IntentRouter (classifica: greeting, web_search, git, …)
                                      │
                                      ├─ git? ──> GitAction.execute() (LLM commit message)
                                      │
                                      ├─ intent in actions? ──> actions[intent].execute()
                                      │
                                      ├─ altrimenti ──> MultiAgent.chat() (5 specialisti)
                                      │     ├─ RAG injection se pertinente
                                      │     ├─ Web search automatico (notizie/meteo/prezzi)
                                      │     └─ Contesto utente da preferenze
                                      │
                                      ├─ ContextManager.add_turn() (user + assistant)
                                      │
                                      ├─ PersistentMemory.store() (entrambi i turni)
                                      │
                                      └─ JSON { response, intent, language }
```

### Input vocale (wake word + registrazione)

```
Browser (microfono)  ──PCM16──>  WebSocket /api/ws/wake
                                    │
                                    └─ Porcupine.process() → "wake"
                                         │
Browser (microfono)  ──PCM16──>  WebSocket /api/ws/audio
                                    │
                                    ├─ Whisper (STT) → testo + lingua
                                    │
                                    ├─ (stesso flusso del chat testuale)
                                    │
                                    └─ TTS → WAV bytes → WebSocket
                                         │
                                         └─ Browser: riproduce audio
```

## API Reference

### System
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/status` | Stato sistema, versione, modello LLM |
| GET | `/api/system/metrics` | CPU/RAM/temp/disk/processi + storico grafici |
| GET | `/api/system/logs` | Log eventi sistema (buffer 100) |

### Chat
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/chat` | Chat testuale con RAG + intent routing |
| POST | `/api/upload` | Upload file (UTF-8) per contesto |
| POST | `/api/feedback` | Salva rating ▲/▼ in feedback.jsonl |
| WS | `/api/ws/wake` | Streaming PCM per wake word |
| WS | `/api/ws/audio` | Streaming audio → STT → LLM → TTS |

### Git (Step 4)
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/git/command` | Comando Git generico (NL) |
| GET | `/api/git/status` | Git status shortcut |
| GET | `/api/git/log` | Git log (N commit) |
| POST | `/api/git/commit` | Git add -A + LLM commit |
| POST | `/api/git/push` | Git push |

### Terminal (Step 5)
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/terminal/run` | Esegui comando shell (sandboxed) |
| GET | `/api/terminal/history` | Storico comandi (ultimi 50) |
| GET | `/api/terminal/allowed` | Mappa comandi consentiti |

### Focus (Step 6)
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/focus/start` | Avvia Pomodoro (durata opzionale) |
| POST | `/api/focus/stop` | Ferma focus + sblocca siti |
| POST | `/api/focus/pause` | Pausa timer + sblocca siti |
| POST | `/api/focus/resume` | Riprende timer + blocca siti |
| GET | `/api/focus/status` | Stato: working/break/paused/idle |
| POST | `/api/focus/sites/add` | Aggiungi sito a blacklist |
| POST | `/api/focus/sites/remove` | Rimuovi sito da blacklist |
| GET | `/api/focus/sites` | Lista siti bloccati |

### RPA (Step 7)
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/rpa/screenshot` | Screenshot desktop → PNG |
| POST | `/api/rpa/analyze` | Screenshot + analisi LLM vision |
| POST | `/api/rpa/click` | Click mouse (x, y, button, clicks) |
| POST | `/api/rpa/type` | Digita testo nella finestra attiva |
| POST | `/api/rpa/hotkey` | Combinazione tasti (ctrl+s, alt+tab) |
| POST | `/api/rpa/open_app` | Apri applicazione per nome |
| POST | `/api/rpa/open_file` | Apri file con app specificata |
| POST | `/api/rpa/scroll` | Scroll direzione + click |
| POST | `/api/rpa/drag` | Drag & drop coordinate |
| GET | `/api/rpa/screen_info` | Risoluzione + posizione mouse |
| POST | `/api/rpa/command` | Comando RPA in linguaggio naturale |

## Comunicazione rete (Docker)

```
Ollama (host Windows, :11434)
  ↑ host.docker.internal
backend ──> redis:6379 (memoria breve)
backend ──> ChromaDB (locale, persistente su volume)

Browser ──:80──> Nginx (frontend container)
                  │
                  ├── /api/* ──proxy_pass──> backend:8765
                  │
                  └── /* ──> index.html (SPA React)

Tutti i container sulla rete `jarvis-net`
```

## Architettura interna del backend

### Pipeline di risposta (MultiAgent)

```
POST /api/chat  ──>  IntentRouter.route(text)
                        │
              ┌─────────┼──────────┐
              │         │          │
          "git"    in actions  fallback
              │         │          │
        GitAction  actions[X]  MultiAgent.chat()
                                   │
                          ┌────────┼────────┐
                          │        │        │
                    code/    research/    action/
                    creative  general     general
                          │        │        │
                    Specialist prompt injected
                          │
                    ┌─────┴─────┐
                    │           │
              RAG search   Web search
              (ChromaDB)   (DuckDuckGo)
                    │           │
                    └─────┬─────┘
                          │
                    Contesto utente
                    (preferenze)
                          │
                    LLM.chat_with_reflection()
                    (reflection disabilitato di default)
```

### Sistema di sicurezza terminale (3 livelli)

```
Comando utente (NL)
    │
    ├─ Blacklist (60+ pattern pericolosi: rm -rf, format, sudo, cmd.exe, ...)
    │   Se matcha → bloccato con messaggio "Comando non consentito"
    │
    ├─ Natural Language → parsing estrae verbo + oggetto
    │   "che versione di Python ho?" → python --version
    │
    ├─ Whitelist per categoria
    │   info/filesystem/python/network/docker/git
    │
    ├─ Timeout (default 15s) + output cappato
    │
    └─ Esecuzione subprocess in path ristretto
```

## Dipendenze chiave

### Backend
- **FastAPI** — server API REST + WebSocket
- **ollama** (libreria Python v0.6.x) — client per Ollama LLM
- **faster-whisper** — trascrizione audio locale (~600 MB modello `base`)
- **pvporcupine** (v1.9.5) — wake word detection off-line (NO API key)
- **chromadb** — memoria vettoriale persistente
- **duckduckgo_search** — ricerca web integrata
- **pyautogui** — automazione interfaccia (RPA)
- **pywin32** — API Windows (Focus Assist, scan code media, hosts file)
- **psutil** — metriche di sistema (CPU, RAM, disk, processi)
- **Pillow** — screenshot processing
- **redis** — client per Redis
- **ultralytics** — YOLOv8 per vision
- **edge-tts** — sintesi vocale naturale Windows
- **sounddevice** — cattura microfono

### Frontend
- **React 18** con TypeScript
- **Three.js** + `@react-three/fiber` — rendering 3D olografico
- **framer-motion** — animazioni UI
- **zustand** — stato globale
- **Nginx** — serve statiche + proxy `/api/` al backend

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `OLLAMA_HOST` | `http://ollama:11434` | Host Ollama |
| `REDIS_HOST` | `redis` | Host Redis |

Il file `settings.yaml` supporta sintassi `${VAR:-default}` per env var.
