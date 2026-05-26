import os
import re
import yaml
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jarvis")

def resolve_env(value):
    if isinstance(value, str):
        pattern = r'\$\{(\w+):-([^}]*)\}'
        def repl(m):
            return os.environ.get(m.group(1), m.group(2))
        return re.sub(pattern, repl, value)
    elif isinstance(value, dict):
        return {k: resolve_env(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env(v) for v in value]
    return value

app = FastAPI(title="J.A.R.V.I.S.", version="2.0.0")

with open("config/settings.yaml") as f:
    raw = yaml.safe_load(f)
    config = resolve_env(raw)

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
