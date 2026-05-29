# J.A.R.V.I.S. — AI Assistant

Assistente AI personale ispirato a Iron Man, completamente locale.  
Attivazione vocale ("Jarvis"), input testuale, HUD olografico 3D, risposta vocale.

## Architettura

```
┌─ Host Windows ──────────────────────────────────┐
│  Ollama (qwen2.5:7b) ←──── host.docker.internal  │
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
- **~8 GB RAM** libera per il LLM
- **~8 GB spazio su disco** (modelli inclusi)

## Primo avvio

### 1. Installa Ollama su Windows

Scarica da [ollama.com](https://ollama.com) e installa. Poi:

```powershell
ollama pull qwen2.5:7b
```

### 2. Avvia J.A.R.V.I.S.

```powershell
# Dalla cartella del progetto
docker compose up -d --build
```

Questo avvia 3 container:
- `redis` — memoria a breve termine
- `backend` — API FastAPI (Python) su `:8765`
- `frontend` — interfaccia web (Nginx) su `:80`

### 3. Apri il browser

http://localhost:80

La prima richiesta richiede ~12s (warmup del LLM), tutte le successive sono **<100ms** (modello tenuto caldo in RAM con `keep_alive=-1`).

## Accesso

| Cosa | URL |
|------|-----|
| Interfaccia | http://localhost |
| Backend API | http://localhost:8765/api/status |

## Uso

### Chat testuale
Scrivi in basso a destra e premi **INVIA** o **Enter**.

### Comandi speciali
Il sistema riconosce automaticamente l'intento:

| Intento | Esempio |
|---------|---------|
| `greeting` | "Ciao" / "Buongiorno" |
| `system_control` | "Spegni il computer" / "Apri calcolatrice" |
| `web_search` | "Cerca su Internet notizie" |
| `media_player` | "Metti musica" / "Alza volume" |
| `productivity` | "Imposta un timer" / "Ricordami di..." |

Se l'intento non viene riconosciuto, J.A.R.V.I.S. risponde via LLM.

## Personalizzazione

### Prompt di sistema
Modifica `backend/config/persona.yaml` per cambiare tono e comportamento.

### Modello LLM
Cambia `backend/config/settings.yaml` → `llm.model`, poi:

```powershell
ollama pull <nuovo-modello>
docker compose restart backend
```

Consigliati: `llama3.1:8b`, `qwen2.5:14b`, `mistral:7b`.

### Voce
J.A.R.V.I.S. usa **edge-tts** (voci naturali Windows, nessun download).
Per usare una voce clone XTTS, metti `models/voice/jarvis_sample.wav` (WAV 10-30s).

## Comandi utili

```powershell
# Stato container
docker compose ps

# Log
docker compose logs -f backend
docker compose logs -f frontend

# Riavvia
docker compose restart

# Ricostruisci dopo modifiche
docker compose build backend frontend
docker compose up -d

# Ferma tutto
docker compose down
```

## Note tecniche

- **LLM**: Ollama + qwen2.5:7b, keep_alive=-1 (sempre in RAM)
- **Risposte**: ~70ms dopo warmup iniziale (~12s all'avvio)
- **STT**: faster-whisper (tiny, CPU, int8)
- **TTS**: edge-tts (voci naturali, nessun modello da scaricare)
- **Wake word**: Porcupine v1.9.5
- **Memoria**: Redis (breve termine) + ChromaDB (lungo termine, RAG)
- **Dashboard**: Three.js (React), grafici real-time CPU/RAM/temperatura/disk
- **Niente cloud**: tutto gira in locale
