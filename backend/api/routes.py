import base64
import json
import logging
import platform
import subprocess
import re
from datetime import datetime, timezone
from collections import deque
from fastapi import APIRouter, WebSocket, UploadFile, File, Request
from pydantic import BaseModel
from pathlib import Path

import psutil

from .dependencies import get_config, get_brain, get_speech, get_actions, get_memory, new_context
from .websocket_manager import manager, handle_wake_word, handle_audio_stream

logger = logging.getLogger("jarvis.api.routes")
UPLOAD_DIR = Path("/app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_FILE = Path("/app/data/feedback.jsonl")

# ── System Metrics Store ──────────────────────────────────────────────────────
_metric_history = {
    "cpu": deque(maxlen=60),
    "ram": deque(maxlen=60),
    "temp": deque(maxlen=60),
    "disk": deque(maxlen=60),
}

def _get_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    return round(entries[0].current, 1)
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "/namespace:\\\\root\\wmi", "path", "MSAcpi_ThermalZoneTemperature", "get", "CurrentTemperature"],
                capture_output=True, text=True, timeout=5
            )
            match = re.search(r"(\d+)", result.stdout)
            if match:
                kelvin = int(match.group(1))
                return round(kelvin / 10 - 273.15, 1)
    except Exception:
        pass
    return None

def _get_top_processes(limit=5):
    procs = []
    for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]), key=lambda p: p.info.get("cpu_percent", 0) or 0, reverse=True)[:limit]:
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "cpu": round(p.info["cpu_percent"] or 0, 1),
                "mem": round(p.info["memory_percent"] or 0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs

def _collect_metrics():
    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    temp = _get_temperature()
    procs = _get_top_processes()
    net = psutil.net_io_counters()
    return {
        "cpu": round(cpu, 1),
        "ram": round(ram.percent, 1),
        "ram_gb": round(ram.used / (1024**3), 1),
        "ram_total_gb": round(ram.total / (1024**3), 1),
        "temp": temp,
        "disk": round(disk.percent, 1),
        "disk_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "net_sent": round(net.bytes_sent / (1024**2), 2),
        "net_recv": round(net.bytes_recv / (1024**2), 2),
        "uptime": round(psutil.boot_time()),
        "processes": procs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# ── System Event Logger ───────────────────────────────────────────────────────
_system_logs = deque(maxlen=100)
_system_logs.append({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "level": "info",
    "message": f"Sistema avviato — {platform.system()} {platform.release()}",
})

def _push_log(level: str, message: str):
    _system_logs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
    })

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

@router.get("/system/metrics")
async def get_system_metrics():
    metrics = _collect_metrics()
    _metric_history["cpu"].append(metrics["cpu"])
    _metric_history["ram"].append(metrics["ram"])
    if metrics["temp"] is not None:
        _metric_history["temp"].append(metrics["temp"])
    _metric_history["disk"].append(metrics["disk"])
    return {
        **metrics,
        "history": {
            "cpu": list(_metric_history["cpu"]),
            "ram": list(_metric_history["ram"]),
            "temp": list(_metric_history["temp"]),
            "disk": list(_metric_history["disk"]),
        }
    }

@router.get("/system/logs")
async def get_system_logs():
    try:
        for p in psutil.process_iter(["name", "status"]):
            try:
                if p.info["status"] == "running":
                    continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass

    cpu = psutil.cpu_percent(interval=0)
    ram = psutil.virtual_memory()
    if cpu > 85:
        _push_log("warning", f"CPU criticamente alta: {cpu}%")
    if ram.percent > 85:
        _push_log("warning", f"RAM criticamente alta: {ram.percent}%")
    if cpu < 10:
        _push_log("info", f"Sistema in idle — CPU {cpu}%, RAM {ram.percent}%")

    return {"logs": list(_system_logs)}

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
async def chat_text(payload: ChatRequest, request: Request = None):
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

    if request and await request.is_disconnected():
        return ChatResponse(response="Richiesta interrotta.", intent="none", language="it", audio=None)

    lang = llm.detect_language(text)
    context.set_language(lang)

    original_query = text
    memories = persistent_memory.search(text, n_results=3)
    if memories:
        memory_context = "\n".join(f"Related memory: {m}" for m in memories)
        prompt = f"{text}\n\n{memory_context}"
    else:
        prompt = text

    if request and await request.is_disconnected():
        return ChatResponse(response="Richiesta interrotta.", intent="none", language="it", audio=None)

    intent = intent_router.route(original_query)
    if intent in actions:
        response = await actions[intent].execute(original_query)
    else:
        response = multiagent.chat(prompt, context.get_context(), language=lang, intent=intent, search_query=original_query)

    if request and await request.is_disconnected():
        return ChatResponse(response="Richiesta interrotta.", intent="none", language="it", audio=None)

    context.add_turn("user", original_query)
    context.add_turn("assistant", response)

    persistent_memory.store(original_query, metadata={"role": "user", "intent": intent})
    persistent_memory.store(response, metadata={"role": "assistant", "intent": intent})

    return ChatResponse(
        response=response,
        intent=intent,
        language=lang,
        audio=None,
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
