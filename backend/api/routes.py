import base64
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, UploadFile, File
from pydantic import BaseModel
from pathlib import Path

from .dependencies import get_config, get_brain, get_speech, get_actions, get_memory, new_context
from .websocket_manager import manager, handle_wake_word, handle_audio_stream

logger = logging.getLogger("jarvis.api.routes")
UPLOAD_DIR = Path("/app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_FILE = Path("/app/data/feedback.jsonl")

router = APIRouter(prefix="/api")

class ChatRequest(BaseModel):
    text: str = ""
    file_content: str = ""

class ChatResponse(BaseModel):
    response: str
    intent: str
    language: str
    audio: str | None = None

class StatusResponse(BaseModel):
    status: str
    version: str
    name: str
    llm: str

class UploadResponse(BaseModel):
    filename: str
    size: int
    content: str

class FeedbackRequest(BaseModel):
    message_id: str = ""
    user_message: str
    assistant_response: str
    rating: int  # 1 = thumbs down, 2 = thumbs up
    language: str = "it"
    intent: str = "chat"

@router.get("/status", response_model=StatusResponse)
async def get_status():
    config = get_config()
    return StatusResponse(
        status="online",
        version="2.0.0",
        name="J.A.R.V.I.S.",
        llm=config["llm"]["model"],
    )

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
    llm, intent_router, multiagent = get_brain(config)
    context = new_context()
    actions = get_actions(config)
    _, persistent_memory = get_memory(config)

    await handle_audio_stream(ws, stt, multiagent, intent_router, context, actions, tts, persistent_memory)
    manager.disconnect(ws)

@router.post("/chat", response_model=ChatResponse)
async def chat_text(payload: ChatRequest):
    config = get_config()
    text = payload.text.strip()
    file_content = payload.file_content

    if not text and not file_content:
        return ChatResponse(response="No input provided.", intent="none", language="it", audio=None)

    if file_content:
        text = f"{text}\n\n[File content]:\n{file_content}" if text else f"[File content]:\n{file_content}"

    llm, intent_router, multiagent = get_brain(config)
    context = new_context()
    actions = get_actions(config)
    _, tts = get_speech(config)
    _, persistent_memory = get_memory(config)

    lang = llm.detect_language(text)
    context.set_language(lang)

    memories = persistent_memory.search(text, n_results=3)
    if memories:
        memory_context = "\n".join(f"Related memory: {m}" for m in memories)
        text = f"{text}\n\n{memory_context}"

    intent = intent_router.route(text)
    if intent in actions:
        response = await actions[intent].execute(text)
    else:
        response = multiagent.chat(text, context.get_context(), language=lang, intent=intent)

    context.add_turn("user", text)
    context.add_turn("assistant", response)

    persistent_memory.store(text, metadata={"role": "user", "intent": intent})
    persistent_memory.store(response, metadata={"role": "assistant", "intent": intent})

    audio_bytes = await tts.synthesize_async(response, language=lang)

    return ChatResponse(
        response=response,
        intent=intent,
        language=lang,
        audio=base64.b64encode(audio_bytes).decode() if audio_bytes else None,
    )

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text_content = content.decode("utf-8", errors="replace")

    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(content)

    return UploadResponse(
        filename=file.filename,
        size=len(content),
        content=text_content,
    )

@router.post("/feedback")
async def submit_feedback(fb: FeedbackRequest):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_id": fb.message_id,
        "user_message": fb.user_message,
        "assistant_response": fb.assistant_response,
        "rating": fb.rating,
        "language": fb.language,
        "intent": fb.intent,
    }
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(f"Feedback saved: rating={fb.rating}, lang={fb.language}, intent={fb.intent}")
    return {"status": "saved", "rating": fb.rating}
