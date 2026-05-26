import base64
import os
import logging
from fastapi import APIRouter, WebSocket, Body, UploadFile, File
from pathlib import Path

from .dependencies import get_config, get_brain, get_speech, get_actions
from .websocket_manager import manager, handle_wake_word, handle_audio_stream

logger = logging.getLogger("jarvis.api.routes")
UPLOAD_DIR = Path("/app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api")

@router.get("/status")
async def get_status():
    config = get_config()
    return {
        "status": "online",
        "version": "2.0.0",
        "name": "J.A.R.V.I.S.",
        "llm": config["llm"]["model"],
    }

@router.websocket("/ws/wake")
async def websocket_wake(ws: WebSocket):
    await manager.connect(ws)
    config = get_config()
    await handle_wake_word(ws, config)
    manager.disconnect(ws)

@router.websocket("/ws/audio")
async def websocket_audio(ws: WebSocket):
    await manager.connect(ws)
    config = get_config()
    stt, tts = get_speech(config)
    llm, intent_router, context = get_brain(config)
    actions = get_actions(config)

    await handle_audio_stream(ws, stt, llm, intent_router, context, actions, tts)
    manager.disconnect(ws)

@router.post("/chat")
async def chat_text(payload: dict = Body(...)):
    config = get_config()
    text = payload.get("text", "").strip()
    file_content = payload.get("file_content", "")

    if not text and not file_content:
        return {"response": "No input provided."}

    if file_content:
        text = f"{text}\n\n[File content]:\n{file_content}" if text else f"[File content]:\n{file_content}"

    llm, intent_router, context = get_brain(config)
    actions = get_actions(config)
    _, tts = get_speech(config)

    lang = llm.detect_language(text)
    context.set_language(lang)

    intent = intent_router.route(text)
    if intent in actions:
        response = await actions[intent].execute(text)
    else:
        response = llm.chat(text, context.get_context())

    context.add_turn("user", text)
    context.add_turn("assistant", response)

    audio_bytes = await tts.synthesize_async(response, language=lang)

    return {
        "response": response,
        "intent": intent,
        "language": lang,
        "audio": base64.b64encode(audio_bytes).decode() if audio_bytes else None,
    }

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text_content = content.decode("utf-8", errors="replace")

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(content)

    return {
        "filename": file.filename,
        "size": len(content),
        "content": text_content,
    }
