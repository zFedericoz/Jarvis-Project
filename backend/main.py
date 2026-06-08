import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

from api.dependencies import resolve_env, get_config, get_brain, get_speech, get_actions, get_memory
from api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jarvis")

app = FastAPI(title="J.A.R.V.I.S.", version="2.1.0")
config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=config["server"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# ──────────────────────────────────────────────
# Route aggiuntive (Step 1-3)
# ──────────────────────────────────────────────

@app.get("/api/memory/preferences")
async def get_preferences():
    """Ritorna tutte le preferenze utente salvate."""
    _, _, _ = get_brain(config)
    mem, _ = get_memory(config)
    return {"preferences": mem.get_all_preferences()}


@app.post("/api/memory/preferences")
async def set_preference(key: str, value: str):
    """Salva una preferenza utente."""
    mem, _ = get_memory(config)
    mem.set_preference(key, value)
    return {"status": "ok", "key": key, "value": value}


@app.delete("/api/memory/preferences/{key}")
async def delete_preference(key: str):
    mem, _ = get_memory(config)
    mem.delete_preference(key)
    return {"status": "deleted", "key": key}


@app.get("/api/rag/sources")
async def list_rag_sources():
    """Elenca i documenti indicizzati nella knowledge base."""
    mem, _ = get_memory(config)
    return {"sources": mem.list_knowledge_sources()}


@app.post("/api/rag/index")
async def index_rag_folder(folder: str = "data/knowledge"):
    """Indicizza (o re-indicizza) tutti i file in una cartella."""
    from memory.rag_indexer import RAGIndexer
    mem, _ = get_memory(config)
    indexer = RAGIndexer(mem)
    result = indexer.index_folder(folder)
    return {"indexed": result, "total_chunks": sum(result.values())}


@app.delete("/api/rag/sources/{source}")
async def delete_rag_source(source: str):
    from memory.rag_indexer import RAGIndexer
    mem, _ = get_memory(config)
    indexer = RAGIndexer(mem)
    indexer.delete_source(source)
    return {"status": "deleted", "source": source}


@app.post("/api/briefing/trigger")
async def trigger_briefing():
    """Lancia manualmente il briefing quotidiano."""
    briefing = app.state.briefing
    if briefing:
        result = await briefing.trigger_now()
        return {"status": "ok", "message": result}
    return {"status": "error", "message": "Briefing service non attivo"}


@app.get("/api/briefing/audio")
async def get_briefing_audio():
    """Ritorna l'ultimo audio del briefing generato."""
    import os
    path = "data/briefing_latest.wav"
    if os.path.exists(path):
        return FileResponse(path, media_type="audio/wav")
    return {"status": "error", "message": "Nessun briefing disponibile"}


# ──────────────────────────────────────────────
# Startup / Shutdown
# ──────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("  J.A.R.V.I.S. v2.1.0 - Starting up...")
    logger.info("=" * 50)
    logger.info(f"  LLM    : {config['llm']['model']}")
    logger.info(f"  STT    : {config['speech']['stt']['engine']} ({config['speech']['stt']['model']})")
    logger.info(f"  TTS    : {config['speech']['tts']['engine']}")
    logger.info(f"  Vision : {'enabled' if config['vision']['enabled'] else 'disabled'}")
    logger.info("=" * 50)

    asyncio.create_task(_warmup_all(config))


async def _warmup_all(config):
    try:
        logger.info("  Inizializzazione componenti...")
        llm, _, _ = get_brain(config)
        speech = get_speech(config)
        get_actions(config)
        mem, _ = get_memory(config)

        # ── Step 1: Memoria persistente ──────────────
        user_name = mem.get_preference("nome_utente")
        if user_name:
            logger.info(f"  Utente riconosciuto: {user_name}")
        prefs_count = len(mem.get_all_preferences())
        logger.info(f"  Preferenze caricate: {prefs_count}")

        # ── Step 2: RAG watcher ───────────────────────
        import os
        from memory.rag_indexer import RAGIndexer
        knowledge_folder = "data/knowledge"
        os.makedirs(knowledge_folder, exist_ok=True)
        indexer = RAGIndexer(mem)
        # Indicizza i file esistenti all'avvio
        existing = indexer.index_folder(knowledge_folder)
        if existing:
            logger.info(f"  RAG: indicizzati {len(existing)} file all'avvio")
        # Avvia il watcher (controlla modifiche ogni 5 minuti)
        indexer.watch_folder(knowledge_folder, interval_seconds=300)
        logger.info(f"  RAG watcher attivo su '{knowledge_folder}'")

        # ── Step 3: Briefing service ──────────────────
        from services.briefing import BriefingService
        from api.websocket_manager import manager as ws_manager
        briefing = BriefingService(config, llm, speech["tts"], mem, ws_manager)
        briefing.start()
        app.state.briefing = briefing

        # ── LLM warmup ────────────────────────────────
        logger.info("  LLM warmup (caricamento modello in RAM)...")
        llm.warmup()
        logger.info("  Tutti i componenti pronti")

    except Exception as e:
        logger.warning(f"  Warmup fallito (non critico): {e}")
        app.state.briefing = None


@app.on_event("shutdown")
async def shutdown():
    logger.info("J.A.R.V.I.S. in spegnimento.")


def main():
    host = config["server"]["host"]
    port = config["server"]["port"]
    logger.info(f"Server in ascolto su {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
