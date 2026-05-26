# Architettura di J.A.R.V.I.S.

```
Jarvis-Project/
├── docker-compose.yml          Orchestra 4 servizi (ollama, redis, backend, frontend)
├── backend/                    FastAPI (Python 3.11)
│   ├── main.py                 Entrypoint: crea app FastAPI, carica config, avvia uvicorn
│   ├── requirements.txt        Dipendenze Python (fastapi, ollama, faster-whisper, …)
│   ├── Dockerfile              Multi-stage: builder + runtime leggero
│   ├── config/
│   │   ├── settings.yaml       Config: modelli, host, sensibilità, porte, …
│   │   └── persona.yaml        System prompt per il LLM (tono Jarvis)
│   ├── api/
│   │   ├── routes.py           4 endpoint: GET /status, WS /ws/wake, WS /ws/audio, POST /chat
│   │   ├── websocket_manager   ConnectionManager + handler wake word + handler audio stream
│   │   └── dependencies.py     Factory functions (get_config, get_brain, get_speech, …)
│   ├── brain/
│   │   ├── llm_client.py       Ollama Client: chat(), embed(), detect_language()
│   │   ├── intent_router.py    Classifica l'intento del testo
│   │   └── context_manager.py  Mantiene cronologia conversazione
│   ├── speech/
│   │   ├── stt.py              Speech-to-Text via faster-whisper
│   │   └── tts.py              Text-to-Speech: XTTS (clone vocale) → fallback Piper
│   ├── wake_word/
│   │   └── processor.py        Porcupine wrapper: process() restituisce true/false
│   ├── actions/
│   │   ├── base_action.py      Classe astratta per le azioni
│   │   ├── system_control.py   Spegni, riavvia, apri app, …
│   │   ├── web_search.py       Cerca su web via DuckDuckGo
│   │   ├── media_player.py     Controllo media (volume, play/pausa)
│   │   └── productivity.py     Timer, promemoria
│   ├── memory/
│   │   ├── ephemeral.py        Redis: memoria a breve termine
│   │   └── persistent.py       ChromaDB: memoria a lungo termine (vettoriale)
│   └── vision/
│       └── camera.py           Riconoscimento oggetti YOLOv8
├── frontend/                   React + TypeScript + Three.js
│   ├── Dockerfile              Build → Nginx statico con proxy_pass per /api/
│   ├── package.json            dipendenze: react, three, @react-three/fiber, framer-motion
│   ├── src/
│   │   ├── App.tsx             Orchestratore: Canvas 3D, hook wake/audio/ws, toggle
│   │   ├── main.tsx            Entrypoint React
│   │   ├── components/
│   │   │   ├── HolographicDisplay.tsx    Anelli 3D concentrici + orbite rotanti (Three.js)
│   │   │   ├── ParticleField.tsx         Campo particellare 3D
│   │   │   ├── VoiceVisualizer.tsx       Visualizzatore audio 3D
│   │   │   ├── ChatPanel.tsx             Input testo + cronologia messaggi
│   │   │   ├── Dashboard.tsx             Stato sistema, metriche, info
│   │   │   └── StatusIndicator.tsx       Pulsante microfono + stato (idle/listening/…)
│   │   ├── hooks/
│   │   │   ├── useWakeWord.ts            Cattura microfono PCM16 → WS → Porcupine
│   │   │   ├── useAudioStream.ts         Cattura audio per trascrizione → WS
│   │   │   ├── useWebSocket.ts           Gestisce messaggi JSON + audio binario
│   │   │   ├── useTTSPlayer.ts           Riproduce blob audio WAV
│   │   │   └── useStore.ts               Stato globale (zustand)
│   │   ├── utils/constants.ts            URL, colori, animazioni, particelle
│   │   ├── types/index.ts                Definizioni TypeScript
│   │   └── styles/globals.css            Stili scanline, vignetta, font
│   ├── index.html
│   ├── tsconfig.json
│   └── vite.config.ts
├── models/                    (montato come volume Docker)
│   ├── voice/jarvis_sample.wav   [fornito dall'utente] campione per XTTS
│   ├── piper/                    [automatico] modelli voce Piper
│   ├── porcupine/jarvis.ppn      [da scaricare] file Porcupine personalizzato
│   └── whisper/                  [automatico] modello faster-whisper (base)
├── data/                       (montato come volume Docker)
│   └── chroma_db/              Persistenza memoria a lungo termine
└── scripts/
    ├── run.ps1                 Avvio diretto (senza Docker)
    └── setup_models.ps1        Download modelli Ollama + setup
```

## Flusso di elaborazione

### Input testuale (`POST /api/chat`)

```
Browser (testo)  ──POST──>  Nginx  ──>  backend /api/chat
                                          │
                                          ├─ IntentRouter (classifica: greeting, web_search, …)
                                          │
                                          ├─ Actions.execute()  ──oppure──  LLM.chat()
                                          │
                                          ├─ TTS.synthesize() → bytes WAV
                                          │
                                          └─ JSON { response, intent, audio (base64) }
                                               │
                                               └─ Browser: mostra testo + riproduce audio
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
                                     ├─ ContextManager.add_turn("user", testo)
                                     │
                                     ├─ IntentRouter → Actions / LLM
                                     │
                                     ├─ ContextManager.add_turn("assistant", risposta)
                                     │
                                     └─ TTS → WAV bytes → WebSocket
                                          │
                                          └─ Browser: riproduce audio
```

## Comunicazione rete (Docker)

```
Browser ──:80──> Nginx (frontend container)
                    │
                    ├── /api/* ──proxy_pass──> backend:8765
                    │                             │
                    │                             ├── /api/status       GET
                    │                             ├── /api/ws/wake     WebSocket
                    │                             ├── /api/ws/audio    WebSocket
                    │                             └── /api/chat        POST
                    │
                    └── /* ──> index.html (SPA React)

backend ──> ollama:11434 (LLM + embeddings)
backend ──> redis:6379 (memoria breve termine)

Tutti i container sulla rete `jarvis-net`
```

## Dipendenze chiave

### Backend
- **FastAPI** — server API REST + WebSocket
- **ollama** (libreria Python v0.6.x) — client per Ollama LLM
- **faster-whisper** — trascrizione audio locale (~600 MB modello `base`)
- **pvporcupine** (v1.9.5) — wake word detection off-line (NO API key)
- **chromadb** — memoria vettoriale persistente
- **duckduckgo_search** — ricerca web integrata

### Frontend
- **React 18** con TypeScript
- **Three.js** + `@react-three/fiber` — rendering 3D olografico
- **framer-motion** — animazioni UI
- **zustand** — stato globale
- **Nginx** — serve statiche + proxy `/api/` al backend

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `OLLAMA_HOST` | `http://ollama:11434` | Host Ollama (Docker: nome servizio) |
| `REDIS_HOST` | `redis` | Host Redis (Docker: nome servizio) |

Il file `settings.yaml` supporta sintassi `${VAR:-default}` per env var.
