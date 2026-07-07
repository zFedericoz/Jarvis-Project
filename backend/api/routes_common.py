import json
import logging
import os
import platform
import re
import subprocess
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi.responses import StreamingResponse
import psutil

from .schemas import ChatResponse
from .constants import MAX_CHAT_REQUESTS_PER_MINUTE
from .ratelimiter import get_rate_limiter

logger = logging.getLogger("jarvis.api.routes")

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_FILE = Path("data/feedback.jsonl")

# ── Rate Limiting (Redis distribuito con fallback locale) ────────────────────
async def _check_rate_limit(client_ip: str, max_per_minute: int = MAX_CHAT_REQUESTS_PER_MINUTE) -> bool:
    """Check if client exceeded rate limit (Redis distribuito, fallback locale)"""
    limiter = get_rate_limiter()
    return await limiter.check(f"ip:{client_ip}", max_per_minute)

# ── Pending Actions Store (per azioni pericolose) ─────────────────────────────
_pending_actions: dict[str, dict] = {}
_PENDING_ACTION_TTL = 300  # 5 minutes

_DANGEROUS_ACTIONS = {"shutdown", "restart", "lock", "mute", "sleep", "hibernate"}

def _cleanup_expired_actions():
    """Remove pending actions that have timed out"""
    now = datetime.now(timezone.utc)
    expired = []
    for action_id, action_data in _pending_actions.items():
        created_at = datetime.fromisoformat(action_data.get("created_at", now.isoformat()))
        if (now - created_at).total_seconds() > _PENDING_ACTION_TTL:
            expired.append(action_id)
    for action_id in expired:
        del _pending_actions[action_id]
        logger.info(f"Pending action {action_id} expired")

def _is_dangerous(cmd: str) -> str | None:
    cmd_lower = cmd.lower()
    for kw in _DANGEROUS_ACTIONS:
        if kw in cmd_lower:
            return kw
    return None

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
    except Exception as e:
        logger.debug(f"Temperature read failed: {e}")
    return None

def _get_top_processes(limit=5):
    procs = []
    for p in sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
        key=lambda p: p.info.get("cpu_percent", 0) or 0,
        reverse=True,
    )[:limit]:
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
    # Use non-blocking cpu_percent (interval=None)
    # First call requires interval for cache initialization
    cpu = psutil.cpu_percent(interval=None)
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

# ── SSE helpers ───────────────────────────────────────────────────────────────
async def _sse_events(r: ChatResponse):
    d = {'type': 'done', 'response': r.response, 'intent': r.intent, 'language': r.language, 'session_id': r.session_id, 'sources': r.sources}
    if r.pending_action:
        d['pending_action'] = r.pending_action
    yield f"data: {json.dumps(d)}\n\n"

def _abort_response(session_id: int | None, stream: bool):
    r = ChatResponse(response="Richiesta interrotta.", intent="none", language="it", audio=None, session_id=session_id)
    if stream:
        return StreamingResponse(_sse_events(r), media_type="text/event-stream")
    return r
