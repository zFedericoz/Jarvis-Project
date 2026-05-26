# J.A.R.V.I.S. — AI Assistant

Assistente AI personale ispirato a Iron Man, completamente locale.  
Attivazione vocale ("Jarvis"), input testuale, HUD olografico 3D, risposta vocale.

## Requisiti

- **Windows 10/11** con supporto Docker
- **GPU NVIDIA RTX 4060 Ti** (o equivalente, ma tutto funziona anche su CPU)
- **32 GB RAM**
- **~10 GB spazio su disco** (modelli inclusi)

## Primo avvio

```powershell
# 1. Clona/reperisci il progetto
cd Jarvis-Project

# 2. Avvia tutto (scarica automaticamente i modelli LLM ~4.9 GB)
docker compose up -d --build
```

Questo comando avvia 4 container:
- `ollama` — LLM + embedding
- `redis` — memoria a breve termine
- `backend` — API FastAPI (Python)
- `frontend` — interfaccia web (Nginx)

### Download modelli

Ollama scarica `llama3.1:8b` (4.9 GB) al primo `docker compose up`.  
Per monitorare o forzare il download:

```powershell
docker compose exec ollama ollama pull llama3.1:8b
```

## Accesso

| Cosa | URL |
|------|-----|
| Interfaccia | http://localhost |
| Backend API | http://localhost/api/status |

## Modalità d'uso

### Testo
Scrivi nella finestra "Scrivi un messaggio..." in basso a destra e premi **INVIA** o **Enter**.

### Voce (wake word)
1. Concedi il permesso microfono al browser
2. Il sistema ascolta la parola "Jarvis" in background
3. Dopo il risveglio, parla — l'audio viene trascritto, processato e ricevi risposta vocale
4. La connessione si chiude dopo la risposta; il wake word si riattiva

### Pulsante microfono
Clicca l'indicatore di stato per avviare/fermare la registrazione manualmente.

## Comandi speciali

Il sistema riconosce automaticamente l'intento:

| Intento | Esempio |
|---------|---------|
| `greeting` | "Ciao" / "Buongiorno" |
| `system_control` | "Spegni il computer" / "Apri calcolatrice" |
| `web_search` | "Cerca su Internet..." |
| `media_player` | "Metti musica" / "Alza volume" |
| `productivity` | "Imposta un timer" / "Ricordami di..." |

Se l'intento non viene riconosciuto, J.A.R.V.I.S. risponde usando il LLM.

## Personalizzazione

### Voce clone (XTTS)
Per attivare la voce clonata (idealmente Paul Bettany che parla italiano):

1. Prepara un file audio **WAV** (10-30 secondi) della voce da clonare
2. Mettilo in `models/voice/jarvis_sample.wav`
3. Riavvia il backend:
   ```powershell
   docker compose restart backend
   ```

Senza questo file, J.A.R.V.I.S. usa Piper TTS (voce sintetica italiana).

### Prompt di sistema
Modifica `backend/config/persona.yaml` per cambiare tono, tratti o capacità.

### Modello LLM
Cambia `backend/config/settings.yaml` → `llm.model`, poi:

```powershell
docker compose exec ollama ollama pull <nuovo-modello>
docker compose restart backend
```

## Comandi utili

```powershell
# Stato container
docker compose ps

# Log backend
docker compose logs -f backend

# Log frontend
docker compose logs -f frontend

# Riavvia tutto
docker compose restart

# Ricostruisci (dopo modifiche)
docker compose build backend frontend
docker compose up -d

# Ferma tutto
docker compose down
```

## Note tecniche

- **Microfono**: catturato dal browser (non dal backend) — compatibile con Docker
- **Wake word**: Porcupine v1.9.5 (ultima versione che non richiede API key Picovoice)
- **LLM**: Ollama + llama3.1:8b, accesso via libreria Python `ollama` v0.6.x
- **PCM audio**: stream grezzo PCM16 a 16kHz (non compresso) via WebSocket
- **TTS**: audio WAV restituito come base64 nella risposta JSON del REST endpoint
