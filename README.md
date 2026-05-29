# J.A.R.V.I.S. — AI Assistant

Assistente AI personale ispirato a Iron Man, completamente locale.  
Attivazione vocale ("Jarvis"), input testuale, HUD olografico 3D, risposta vocale.

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
# Crea le directory dati (ignorate da .gitignore)
mkdir data\chroma_db data\hf_cache models

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

## Trasferimento su nuovo PC (con GPU NVIDIA)

Il progetto è già pronto per GPU. Su un PC con scheda NVIDIA (es. RTX 4060 Ti), i tempi di risposta passano da ~4 minuti a **<1 secondo**.

```powershell
# 1. Clona la repo sul nuovo PC
git clone <url-repo>
cd jarvis-project

# 2. Installa Docker Desktop con supporto WSL2 + GPU NVIDIA
#    (https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

# 3. Installa Ollama su Windows nativo
#    Scarica da https://ollama.com

# 4. Scarica i modelli
ollama pull qwen2.5:14b
ollama pull mxbai-embed-large

# 5. Ferma il vecchio modello 7b (libera ~5 GB RAM)
ollama stop qwen2.5:7b

# 6. Crea le directory dati (ignorate da .gitignore)
mkdir data\chroma_db data\hf_cache models

# 7. (Opzionale) Riattiva la reflection per auto-valutazione qualità
#    Apri backend/brain/multiagent.py, riga ~161:
#    Cambia max_reflect_rounds=0 → max_reflect_rounds=1

# 8. Avvia
docker compose up -d --build
```

Verifica che Ollama usi la GPU:

```powershell
ollama ps
# Deve mostrare: PROCESSOR   100% GPU
```

Se vedi `100% CPU`, controlla che `num_gpu` in `backend/config/settings.yaml` sia `-1` (auto-detect).

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

- **LLM**: Ollama + qwen2.5:14b, keep_alive=-1 (sempre in RAM)
- **Reflection**: auto-valutazione qualità (disabilitata su CPU, riattivabile su GPU)
- **Web search**: DuckDuckGo automatico per domande su news/meteo/attualità
- **Feedback utente**: pulsanti ▲/▼ su ogni risposta, salvato in `data/feedback.jsonl`
- **STT**: faster-whisper (tiny, CPU, int8)
- **TTS**: edge-tts (voci naturali, nessun modello da scaricare)
- **Wake word**: Porcupine v1.9.5
- **Memoria**: Redis (breve termine) + ChromaDB (lungo termine, RAG)
- **Dashboard**: Three.js (React), grafici real-time CPU/RAM/temperatura/disk
- **GPU**: `num_gpu: -1` in settings.yaml → auto-detect GPU NVIDIA
- **Niente cloud**: tutto gira in locale
