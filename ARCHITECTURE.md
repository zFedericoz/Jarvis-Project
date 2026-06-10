# Architettura di J.A.R.V.I.S.

```
Jarvis-Project/
├── docker-compose.yml          Orchestra 3 servizi (redis, backend, frontend)
├── ARCHITECTURE.md             Questo file
├── README.md                   Istruzioni di avvio e requisiti hardware
├── GUIDA.md                    Guida all'uso del dataset per fine-tuning
├── dataset_finetune.jsonl      Dataset per fine-tuning del LLM
│
├── backend/                    FastAPI (Python 3.11)
│   ├── main.py                 Entrypoint: crea app FastAPI, carica config, avvia uvicorn
│   ├── requirements.txt        Dipendenze Python
│   ├── Dockerfile              Multi-stage: builder + runtime leggero
│   ├── config/
│   │   ├── settings.yaml       Config: LLM, speech, vision, memoria, azioni, git, terminal, focus, RPA
│   │   └── persona.yaml        System prompt bilingue (IT/EN) per il LLM
│   ├── api/
│   │   ├── routes.py           30+ endpoint REST + 2 WebSocket (~960 righe)
│   │   ├── websocket_manager   ConnectionManager + handler wake word + handler audio stream
│   │   └── dependencies.py     Factory functions (config, brain, speech, actions, memory, chat)
│   ├── chat/
│   │   ├── chat_manager.py     SQLite: CRUD sessioni + messaggi, auto-title, thread-safe
│   │   └── __init__.py
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
│   │   ├── persistent.py       ChromaDB: memoria a lungo termine (vettoriale) + preferenze utente
│   │   └── rag_indexer.py      Indicizzatore documenti (PDF/TXT/MD) per RAG, watcher automatico
│   ├── services/
│   │   ├── briefing.py         Briefing quotidiano con notifica via WebSocket
│   │   └── __init__.py
│   ├── vision/
│   │   └── camera.py           Riconoscimento oggetti YOLOv8
│   ├── host_metrics_server.py  Server HTTP standalone per metriche host Windows (CPU/RAM/temp)
│   └── host_rpa_server.py      Server HTTP standalone per azioni RPA su host Windows
│
├── frontend/                   React + TypeScript + Three.js
│   ├── Dockerfile              Build → Nginx statico con proxy_pass per /api/
│   ├── package.json            dipendenze: react, three, @react-three/fiber, framer-motion, zustand
│   ├── src/
│   │   ├── App.tsx             Orchestratore: top bar metriche, sidebar chat, reattore 3D, chat persistente
│   │   ├── main.tsx            Entrypoint React
│   │   ├── components/
│   │   │   ├── Sidebar.tsx     Sidebar sessioni chat: crea, seleziona, rinomina (doppio click), elimina
│   │   │   ├── ChatPanel.tsx   Input testo + file attachment + feedback ▲/▼ + TTS playback
│   │   │   ├── HolographicDisplay.tsx    Anelli 3D concentrici + orbite rotanti (Three.js)
│   │   │   ├── ParticleField.tsx         Campo particellare 3D
│   │   │   ├── VoiceVisualizer.tsx       Visualizzatore audio 3D (instanced mesh)
│   │   │   ├── Dashboard.tsx             HUD: ora, data, connessione
│   │   │   └── StatusIndicator.tsx       Pulsante microfono + stati (idle/listening/processing/speaking)
│   │   ├── hooks/
│   │   │   ├── useStore.ts               Stato globale (zustand) — sessioni chat + messaggi WS + wake word
│   │   │   ├── useWakeWord.ts            Cattura microfono PCM16 → WS → Porcupine
│   │   │   ├── useAudioStream.ts         Cattura audio per trascrizione → WS
│   │   │   ├── useWebSocket.ts           Gestisce messaggi JSON + audio binario (auto-reconnect)
│   │   │   └── useTTSPlayer.ts           Riproduce blob audio WAV (Web Audio API)
│   │   ├── utils/constants.ts            URL, colori, animazioni, particelle
│   │   ├── types/index.ts                Definizioni TypeScript (WSMessage, AppStatus, ActionModule, SystemMetric)
│   │   └── styles/globals.css            Font Inter + JetBrains Mono, base 15px, scrollbar, CRT scanline
│   ├── index.html
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── models/                     (montato come volume Docker)
│   ├── voice/jarvis_sample.wav   [fornito dall'utente] campione per XTTS
│   ├── piper/                    [automatico] modelli voce Piper
│   ├── porcupine/jarvis.ppn      [da scaricare] file Porcupine personalizzato
│   └── whisper/                  [automatico] modello faster-whisper (base)
│
├── data/                        (montato come volume Docker)
│   ├── chroma_db/               Persistenza memoria a lungo termine
│   ├── chats.db                 Database SQLite sessioni chat persistenti
│   ├── screenshots/             Screenshot RPA
│   ├── knowledge/               Documenti PDF/TXT/MD per RAG (indicizzazione automatica)
│   └── feedback.jsonl           Feedback utente (rating, messaggio, intento)
│
└── scripts/
    ├── up.ps1                   Avvio Docker Compose con rebuild + avvio host_metrics + host_rpa
    ├── run.ps1                  Avvio diretto (senza Docker)
    └── setup_models.ps1         Download modelli Ollama + setup
```

## Flusso di elaborazione

### Input testuale (`POST /api/chat`)

```
Browser (testo)  ──POST──>  Nginx  ──>  backend /api/chat
                                      │
                                      ├─ session_id opzionale → ChatManager (SQLite)
                                      │   ├─ Crea/nuova sessione se non fornito
                                      │   ├─ Salva messaggio utente
                                      │   └─ Richiama auto_title se titolo ancora "Nuova chat"
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
                                      ├─ ChatManager.add_message() + auto_title()
                                      │
                                      └─ JSON { response, intent, language, session_id }
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
| POST | `/api/chat` | Chat testuale con RAG + intent routing + sessione persistente |
| POST | `/api/upload` | Upload file (UTF-8) per contesto |
| POST | `/api/feedback` | Salva rating ▲/▼ in feedback.jsonl |
| WS | `/api/ws/wake` | Streaming PCM per wake word |
| WS | `/api/ws/audio` | Streaming audio → STT → LLM → TTS |

### Chat Sessions (Step 8)
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/chats` | Elenco sessioni (con conteggio messaggi e ultimo messaggio) |
| POST | `/api/chats` | Crea nuova sessione |
| DELETE | `/api/chats/{id}` | Elimina sessione e relativi messaggi |
| PATCH | `/api/chats/{id}` | Rinomina sessione |
| GET | `/api/chats/{id}/messages` | Recupera messaggi di una sessione |

### Memoria & RAG
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/memory/preferences` | Elenca preferenze utente |
| POST | `/api/memory/preferences` | Salva preferenza |
| DELETE | `/api/memory/preferences/{key}` | Elimina preferenza |
| GET | `/api/rag/sources` | Elenca documenti indicizzati |
| POST | `/api/rag/index` | (Re)indicizza cartella knowledge |
| DELETE | `/api/rag/sources/{source}` | Rimuovi sorgente RAG |

### Briefing
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/briefing/trigger` | Lancia briefing quotidiano manualmente |
| GET | `/api/briefing/audio` | Recupera audio ultimo briefing |

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
backend ──> SQLite (data/chats.db, persistente su volume)

Browser ──:80──> Nginx (frontend container)
                  │
                  ├── /api/* ──proxy_pass──> backend:8765
                  │
                  └── /* ──> index.html (SPA React)

host_metrics_server (Windows, :18765) ← host.docker.internal
host_rpa_server     (Windows, :18766) ← host.docker.internal

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

### Chat session flow

```
POST /api/chat (con o senza session_id)
    │
    ├─ session_id = None → ChatManager.create_session()
    │                      → nuovo ID restituito in response.session_id
    │
    ├─ session_id fornito → ChatManager.get_session()
    │                        → se non esiste, ne crea una nuova
    │
    ├─ ChatManager.add_message("user", testo, intent="")
    │
    ├─ (elaborazione LLM...)
    │
    ├─ ChatManager.add_message("assistant", risposta, intent)
    │
    └─ ChatManager.auto_title(session_id)
       (solo se titolo ancora "Nuova chat")
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
- **sqlite3** — database chat persistenti (built-in, nessuna dipendenza aggiuntiva)

### Frontend
- **React 18** con TypeScript
- **Three.js** + `@react-three/fiber` — rendering 3D olografico
- **framer-motion** — animazioni UI
- **zustand** — stato globale
- **Inter** + **JetBrains Mono** — font (sostituito Share Tech Mono per leggibilità)
- **Nginx** — serve statiche + proxy `/api/` al backend

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `OLLAMA_HOST` | `http://ollama:11434` | Host Ollama |
| `REDIS_HOST` | `redis` | Host Redis |

Il file `settings.yaml` supporta sintassi `${VAR:-default}` per env var.
