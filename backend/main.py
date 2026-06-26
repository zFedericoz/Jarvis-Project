import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.dependencies import resolve_env, get_config, get_brain, get_speech, get_actions, get_memory, get_chat_manager
from api.routes import router


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("jarvis")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="J.A.R.V.I.S.", version="2.1.0")
app.state.limiter = limiter

config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=config["server"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(router)

# ── Prometheus metrics ────────────────────────────────────────────────────────
from api.monitoring.metrics import MetricsMiddleware, metrics_response
app.add_middleware(MetricsMiddleware)

@app.get("/metrics")
async def prometheus_metrics():
    return metrics_response()

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
@app.get("/api/rag/index")
async def index_rag_folder(folder: str = "data/knowledge"):
    """Indicizza (o re-indicizza) tutti i file in una cartella."""
    from memory.rag_indexer import RAGIndexer
    _, persistent_mem = get_memory(config)
    indexer = RAGIndexer(persistent_mem)
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


# ── Face Auth endpoints ─────────────────────────────────────────────
@app.get("/api/face/list")
async def face_list():
    from services.face_auth.face_auth import get_face_auth
    return {"faces": get_face_auth().list_faces()}


@app.post("/api/face/register")
async def face_register(name: str):
    from services.face_auth.face_auth import get_face_auth
    return {"status": "not_implemented", "note": "Usa POST /api/face/register con form-data (file image)"}


@app.delete("/api/face/{name}")
async def face_delete(name: str):
    from services.face_auth.face_auth import get_face_auth
    ok = get_face_auth().delete_face(name)
    return {"status": "deleted" if ok else "not_found"}


@app.get("/api/face/recognize")
async def face_recognize():
    """Riconoscimento facciale via webcam (richiede face_recognition + webcam accessibile)."""
    return {"info": "Usa WebSocket per streaming video"}


# ── Home Assistant endpoints ────────────────────────────────────────
@app.get("/api/ha/entities")
async def ha_list_entities():
    from plugins.homeassistant.ha_plugin import HomeAssistantPlugin
    p = HomeAssistantPlugin()
    return await p.execute("list_entities", {})


@app.post("/api/ha/{entity_id}/{action}")
async def ha_action(entity_id: str, action: str):
    from plugins.homeassistant.ha_plugin import HomeAssistantPlugin
    p = HomeAssistantPlugin()
    return await p.execute(action, {"entity_id": entity_id})


# ── Broadcast (proactive notifications) ─────────────────────────────
@app.post("/api/broadcast")
async def broadcast_message(body: dict):
    from api.websocket_manager import manager as ws_manager
    await ws_manager.broadcast(json.dumps(body))
    return {"status": "broadcasted"}


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

    # ── Chat DB init ───────────────────────────
    try:
        get_chat_manager()
        logger.info("  Chat database pronto")
    except Exception as e:
        logger.warning(f"  Chat DB init fallito: {e}")

    # ── Plugin loader ──────────────────────────
    try:
        from plugins.loader import PluginLoader
        _pl = PluginLoader()
        _pl.discover_and_load()
    except Exception as e:
        logger.warning(f"  Plugin init fallito: {e}")

    asyncio.create_task(_warmup_all(config))


async def _warmup_all(config):
    try:
        logger.info("  Inizializzazione componenti...")
        llm, _, _ = get_brain(config)
        speech = get_speech(config)
        get_actions(config)
        _, persistent_mem = get_memory(config)

        # ── Step 1: Memoria persistente ──────────────
        user_name = persistent_mem.get_preference("nome_utente")
        if user_name:
            logger.info(f"  Utente riconosciuto: {user_name}")
        prefs_count = len(persistent_mem.get_all_preferences())
        logger.info(f"  Preferenze caricate: {prefs_count}")

        # ── Step 2: RAG watcher ───────────────────────
        import os
        from memory.rag_indexer import RAGIndexer
        knowledge_folder = "data/knowledge"
        os.makedirs(knowledge_folder, exist_ok=True)
        indexer = RAGIndexer(persistent_mem)
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
        briefing = BriefingService(config, llm, speech["tts"], persistent_mem, ws_manager)
        briefing.start()
        app.state.briefing = briefing

        # ── Step 4: Voice loop (wake word sempre attivo) ──
        try:
            from services.voice_loop.voice_loop import VoiceLoop
            voice = VoiceLoop(config, llm, speech["stt"], speech["tts"], persistent_mem, ws_manager)
            voice.start()
            app.state.voice_loop = voice
            logger.info("  Voice loop avviato (wake word sempre attivo)")
        except Exception as e:
            logger.warning(f"  Voice loop init fallito: {e}")

        # ── Step 5: Proactive intelligence ────────────────
        try:
            from services.proactive.proactive import get_proactive_engine
            pro = get_proactive_engine(config)
            pro.start()
            app.state.proactive = pro
            logger.info("  Proactive engine avviato")
        except Exception as e:
            logger.warning(f"  Proactive engine init fallito: {e}")

        # ── Step 6: Proactive system monitor ──────────────
        try:
            from brain.proactive_monitor import get_proactive_monitor
            monitor = get_proactive_monitor()
            monitor.start()
            app.state.proactive_monitor = monitor
            logger.info("  ProactiveMonitor avviato (metriche ogni 30s)")
        except Exception as e:
            logger.warning(f"  ProactiveMonitor init fallito: {e}")

        # ── LLM warmup ────────────────────────────────
        logger.info("  LLM warmup (caricamento modello in RAM)...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, llm.warmup)
        logger.info("  LLM modello pronto")

        # ── Step 7: Vision monitoring continuo ───────────
        try:
            from vision.camera import Camera
            from api.websocket_manager import manager as ws_manager
            import json
            vision_cfg = config.get("vision", {})
            if vision_cfg.get("enabled", True):
                cam = Camera(
                    model_path=vision_cfg.get("model", "yolov8n.pt"),
                    device=vision_cfg.get("device", "cuda"),
                    camera_id=vision_cfg.get("camera_id", 0),
                )
                cam.start_continuous_monitoring(
                    callback=lambda msg: asyncio.ensure_future(
                        ws_manager.broadcast(json.dumps({
                            "type": "proactive_vision",
                            "message": msg,
                        }))
                    ),
                    interval_seconds=3,
                )
                app.state.vision_camera = cam
                # Condividi la camera con l'action Vision
                try:
                    actions_list = get_actions(config)
                    if "vision" in actions_list:
                        actions_list["vision"].set_camera(cam)
                except Exception:
                    pass
                logger.info("  Vision monitoring continuo avviato")
        except Exception as e:
            logger.warning(f"  Vision monitoring init fallito: {e}")

        # ── XTTS warmup (voice cloning su GPU) ───────
        if speech["tts"]._xtts_available:
            logger.info("  XTTS warmup (caricamento modello su GPU)...")
            await loop.run_in_executor(None, speech["tts"].warmup_xtts)
        else:
            logger.info("  XTTS non disponibile (skip warmup)")

        logger.info("  Tutti i componenti pronti")

    except Exception as e:
        logger.warning(f"  Warmup fallito (non critico): {e}")
        app.state.briefing = None


@app.on_event("shutdown")
async def shutdown():
    logger.info("J.A.R.V.I.S. in spegnimento.")
    if hasattr(app.state, "voice_loop"):
        try:
            app.state.voice_loop.stop()
        except Exception:
            pass
    if hasattr(app.state, "proactive"):
        try:
            await app.state.proactive.stop()
        except Exception:
            pass
    if hasattr(app.state, "proactive_monitor"):
        try:
            await app.state.proactive_monitor.stop()
        except Exception:
            pass
    if hasattr(app.state, "briefing"):
        try:
            app.state.briefing.stop()
        except Exception:
            pass
    if hasattr(app.state, "vision_camera"):
        try:
            app.state.vision_camera.stop_monitoring()
        except Exception:
            pass


def main():
    host = config["server"]["host"]
    port = config["server"]["port"]
    logger.info(f"Server in ascolto su {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
