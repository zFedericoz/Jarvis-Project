# Manutenzione

## Pulizia periodica

### Cache eliminabile in qualsiasi momento (rigenerabile)

| Cartella / Pattern | Dimensione tipica | Comando |
|---|---|---|
| `__pycache__` + `*.pyc` | ~1 MB | `Get-ChildItem -Recurse -Directory -Filter "__pycache__" \| Remove-Item -Recurse -Force` |
| `.pytest_cache` | ~10 KB | `Remove-Item -Recurse -Force .pytest_cache -ErrorAction SilentlyContinue` |
| `*.tsbuildinfo` | ~1 KB | `Remove-Item -Recurse -Force -Filter "*.tsbuildinfo"` |
| `frontend/node_modules/` | ~210 MB | `Remove-Item -Recurse -Force frontend/node_modules` (poi `npm install`) |
| `frontend/dist/` | ~8 MB | `Remove-Item -Recurse -Force frontend/dist` (poi `npm run build`) |
| `frontend/.vite/` | ~10 MB | `Remove-Item -Recurse -Force frontend/.vite -ErrorAction SilentlyContinue` |

### Cache dati rigenerabile

| Cartella | Dimensione | Ricostruzione | Nota |
|---|---|---|---|
| `data/hf_cache` | ~680 MB | Si riscarica automaticamente | Cache HuggingFace (modelli STT/TTS) |
| `data/chroma_cache` | ~170 MB | Si ricostruisce da `chroma_db` | Cache vettoriale — si rigenera al prossimo avvio |

### Dati persistenti — NON cancellare senza backup

| Cartella / File | Naturale | Cosa contiene |
|---|---|---|
| `data/chroma_db/` | Memoria a lungo termine | Preferenze utente, cronologia, vettori RAG |
| `data/chats.db*` | Database chat | Cronologia conversazioni |
| `data/backups/` | Backup automatici | Snapshot di `chats.db` |
| `models/voice/jarvis_sample.wav` | Voice sample | Campione vocale per clonazione XTTS |
| `data/uploads/` | File caricati | Documenti inviati dall'utente |
| `data/knowledge/` | Knowledge base | Documenti indicizzati per RAG |

### Pulizia completa in un comando

```powershell
# Libera ~1 GB di cache rigenerabile (non tocca dati persistenti)
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Remove-Item -Recurse -Force frontend/node_modules, frontend/dist, frontend/.vite -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force data/hf_cache, data/chroma_cache -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force -Filter "*.tsbuildinfo", "*.pyc" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .pytest_cache -ErrorAction SilentlyContinue
```

## Export leggero del progetto

Per condividere il repo (es. su GitHub, ZIP via email) senza file pesanti:

```powershell
# Crea uno zip pulito escludendo cache, dati runtime, dipendenze
$exclude = @(
    '__pycache__', '*.pyc', '.pytest_cache', '*.tsbuildinfo',
    'node_modules', 'dist', '.vite',
    'data', 'models',
    '.venv', 'venv',
    '.git', '.idea', '.vscode',
    '.env'
)
$excludeParam = ($exclude | ForEach-Object { "--exclude=$_" }) -join ' '
Compress-Archive -Path * -DestinationPath "jarvis-export.zip" $excludeParam.Split(' ')
```

Oppure usa lo script dedicato:

```powershell
.\scripts\export_clean.ps1
```

Questo produce `jarvis-export.zip` nella root del progetto (~5 MB invece di ~1.5 GB).
