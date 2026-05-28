import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.dependencies import resolve_env, get_config
from api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jarvis")

app = FastAPI(title="J.A.R.V.I.S.", version="2.0.0")

config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=config["server"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("  J.A.R.V.I.S. v2.0.0 - Starting up...")
    logger.info("=" * 50)
    logger.info(f"  LLM: {config['llm']['model']}")
    logger.info(f"  STT: {config['speech']['stt']['engine']}")
    logger.info(f"  TTS: {config['speech']['tts']['engine']}")
    logger.info(f"  Vision: {'enabled' if config['vision']['enabled'] else 'disabled'}")
    logger.info("=" * 50)

@app.on_event("shutdown")
async def shutdown():
    logger.info("J.A.R.V.I.S. shutting down.")

def main():
    host = config["server"]["host"]
    port = config["server"]["port"]
    logger.info(f"Server listening on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
