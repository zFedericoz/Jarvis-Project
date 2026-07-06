import asyncio
import json
import logging

from fastapi import APIRouter, Depends

from .auth import get_current_user

import skills
from .dependencies import get_config, get_actions, get_memory
from .routes_common import _push_log
from .routes_chat import router as chat_router
from .routes_system import router as system_router
from .routes_rpa import router as rpa_router
# Re-export all schemas for backwards compatibility
from .schemas import (
    ChatRequest, ChatResponse, PendingActionInfo, ConfirmRequest,
    StatusResponse, UploadResponse, FeedbackRequest,
    GitRequest, TerminalRequest,
    FocusStartRequest, FocusSiteRequest, RenameSessionRequest,
    RPAClickRequest, RPATypeRequest, RPAHotkeyRequest,
    RPAOpenAppRequest, RPAOpenFileRequest, RPAScrollRequest,
    RPADragRequest, RPACommandRequest,
)

logger = logging.getLogger("jarvis.api.routes")

router = APIRouter(prefix="/api")
router.include_router(chat_router)
router.include_router(system_router)
router.include_router(rpa_router)


# ══════════════════════════════════════════════════════════════════════════════
# Git API routes
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/git/command")
async def git_command(payload: GitRequest, user: dict = Depends(get_current_user)):
    """
    Esegue un comando Git via API REST.

    Esempi:
      POST /api/git/command
      { "command": "committa tutto", "repo_path": "C:/Dev/JARVIS" }

      POST /api/git/command
      { "command": "status" }

      POST /api/git/command
      { "command": "ultimi 10 commit" }
    """
    config = get_config()
    actions = get_actions(config)
    git = actions.get("git")
    if not git:
        return {"status": "error", "message": "GitAction non disponibile"}

    # Se il repo_path non è specificato, prova dalle preferenze utente
    repo = payload.repo_path
    if not repo:
        _, persistent_memory = get_memory(config)
        repo = persistent_memory.get_preference("cartella_progetti")

    result = await git.execute(payload.command, repo_path=repo)
    _push_log("info", f"Git API: {payload.command[:60]}")
    return {"status": "ok", "result": result, "repo": str(repo or "default")}


@router.get("/git/status")
async def git_status(repo_path: str | None = None, user: dict = Depends(get_current_user)):
    """Shortcut per git status."""
    config = get_config()
    actions = get_actions(config)
    git = actions.get("git")
    if not git:
        return {"status": "error", "message": "GitAction non disponibile"}

    if not repo_path:
        _, mem = get_memory(config)
        repo_path = mem.get_preference("cartella_progetti")

    result = await git.execute("status", repo_path=repo_path)
    return {"status": "ok", "result": result}


@router.get("/git/log")
async def git_log(repo_path: str | None = None, n: int = 10, user: dict = Depends(get_current_user)):
    """Shortcut per git log con N commit."""
    config = get_config()
    actions = get_actions(config)
    git = actions.get("git")
    if not git:
        return {"status": "error", "message": "GitAction non disponibile"}

    if not repo_path:
        _, mem = get_memory(config)
        repo_path = mem.get_preference("cartella_progetti")

    result = await git.execute(f"mostrami gli ultimi {n} commit", repo_path=repo_path)
    return {"status": "ok", "result": result, "n": n}


@router.post("/git/commit")
async def git_commit(repo_path: str | None = None, user: dict = Depends(get_current_user)):
    """
    Esegue git add -A + commit con messaggio generato dall'LLM.
    Shortcut per il frontend (pulsante "Commit" nella dashboard).
    """
    config = get_config()
    actions = get_actions(config)
    git = actions.get("git")
    if not git:
        return {"status": "error", "message": "GitAction non disponibile"}

    if not repo_path:
        _, mem = get_memory(config)
        repo_path = mem.get_preference("cartella_progetti")

    result = await git.execute("committa tutto", repo_path=repo_path)
    return {"status": "ok", "result": result}


@router.post("/git/push")
async def git_push(repo_path: str | None = None, user: dict = Depends(get_current_user)):
    """Esegue git push."""
    config = get_config()
    actions = get_actions(config)
    git = actions.get("git")
    if not git:
        return {"status": "error", "message": "GitAction non disponibile"}

    if not repo_path:
        _, mem = get_memory(config)
        repo_path = mem.get_preference("cartella_progetti")

    result = await git.execute("push", repo_path=repo_path)
    return {"status": "ok", "result": result}


# ══════════════════════════════════════════════════════════════════════════════
# Terminal API routes
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/terminal/run")
async def terminal_run(payload: TerminalRequest, user: dict = Depends(get_current_user)):
    """
    Esegue un comando nel terminale sicuro.

    Esempi:
      { "command": "ls -la" }
      { "command": "che versione di Python ho?" }
      { "command": "esegui python analisi.py", "cwd": "/app/scripts" }
      { "command": "docker ps" }
    """
    config = get_config()
    actions = get_actions(config)
    terminal = actions.get("terminal")
    if not terminal:
        return {"status": "error", "message": "TerminalAction non disponibile"}

    result = await terminal.execute(payload.command, cwd=payload.cwd)
    _push_log("info", f"Terminal: {payload.command[:60]}")
    return {
        "status": "ok",
        "command": payload.command,
        "result": result,
    }


@router.get("/terminal/history")
async def terminal_history(user: dict = Depends(get_current_user)):
    """Ritorna lo storico dei comandi eseguiti (ultimi 50, più recenti prima)."""
    config = get_config()
    actions = get_actions(config)
    terminal = actions.get("terminal")
    if not terminal:
        return {"status": "error", "message": "TerminalAction non disponibile"}

    return {
        "status": "ok",
        "history": terminal.get_history(),
    }


@router.get("/terminal/allowed")
async def terminal_allowed(user: dict = Depends(get_current_user)):
    """
    Ritorna la mappa dei comandi consentiti nelle categorie abilitate.
    Utile per il frontend (mostrare all'utente cosa può fare).
    """
    config = get_config()
    actions = get_actions(config)
    terminal = actions.get("terminal")
    if not terminal:
        return {"status": "error", "message": "TerminalAction non disponibile"}

    return {
        "status": "ok",
        "allowed": terminal.get_allowed_commands(),
        "working_dir": str(terminal._working_dir),
        "timeout": terminal._timeout,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Focus Mode API routes
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/focus/start")
async def focus_start(payload: FocusStartRequest = FocusStartRequest(), user: dict = Depends(get_current_user)):
    """
    Avvia una sessione Pomodoro.
    Blocca i siti distraenti e attiva Focus Assist (Windows).

    Esempio:
      POST /api/focus/start
      POST /api/focus/start  { "duration_minutes": 45 }
    """
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    result = productivity.focus.start(work_minutes=payload.duration_minutes)
    _push_log("info", f"Focus avviato: {payload.duration_minutes or 'default'} min")
    return {"status": "ok", "result": result, "focus_status": productivity.focus.status()}


@router.post("/focus/stop")
async def focus_stop(user: dict = Depends(get_current_user)):
    """Ferma la sessione focus e sblocca i siti."""
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    result = productivity.focus.stop()
    _push_log("info", "Focus disattivato")
    return {"status": "ok", "result": result}


@router.post("/focus/pause")
async def focus_pause(user: dict = Depends(get_current_user)):
    """Mette in pausa il timer focus (sblocca i siti temporaneamente)."""
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    result = productivity.focus.pause()
    return {"status": "ok", "result": result}


@router.post("/focus/resume")
async def focus_resume(user: dict = Depends(get_current_user)):
    """Riprende una sessione focus in pausa."""
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    result = productivity.focus.resume()
    return {"status": "ok", "result": result}


@router.get("/focus/status")
async def focus_status(user: dict = Depends(get_current_user)):
    """
    Ritorna lo stato corrente della sessione focus.

    Response:
      {
        "state": "working" | "break" | "paused" | "idle",
        "pomodoro_count": 3,
        "remaining_seconds": 847,
        "remaining_formatted": "14 min 7 sec",
        "blocked_sites": ["reddit.com", ...],
        "notifications_muted": true
      }
    """
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    return {"status": "ok", **productivity.focus.status()}


@router.post("/focus/sites/add")
async def focus_add_site(payload: FocusSiteRequest, user: dict = Depends(get_current_user)):
    """
    Aggiunge un sito alla blacklist focus (persistente tra sessioni).

    Esempio:
      POST /api/focus/sites/add  { "site": "reddit.com" }
    """
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    result = productivity.focus.add_site(payload.site)
    return {"status": "ok", "result": result, "blocked_sites": productivity.focus._blocked_sites}


@router.post("/focus/sites/remove")
async def focus_remove_site(payload: FocusSiteRequest, user: dict = Depends(get_current_user)):
    """
    Rimuove un sito dalla blacklist focus.

    Esempio:
      POST /api/focus/sites/remove  { "site": "youtube.com" }
    """
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    result = productivity.focus.remove_site(payload.site)
    return {"status": "ok", "result": result, "blocked_sites": productivity.focus._blocked_sites}


@router.get("/focus/sites")
async def focus_list_sites(user: dict = Depends(get_current_user)):
    """Ritorna la lista dei siti bloccati durante il focus."""
    config = get_config()
    actions = get_actions(config)
    productivity = actions.get("productivity")
    if not productivity:
        return {"status": "error", "message": "Productivity action non disponibile"}

    return {
        "status": "ok",
        "blocked_sites": productivity.focus._blocked_sites,
        "count": len(productivity.focus._blocked_sites),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Market Data API routes
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/market/quote")
async def market_quote(symbol: str = "AAPL", user: dict = Depends(get_current_user)):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: skills.execute("market_data", action="quote", symbol=symbol))
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"error": result}


@router.get("/market/history")
async def market_history(symbol: str = "AAPL", period: str = "1mo", interval: str = "1d", user: dict = Depends(get_current_user)):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: skills.execute("market_data", action="history", symbol=symbol, period=period, interval=interval))
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"error": result, "data": []}


@router.get("/market/search")
async def market_search(q: str = "Tesla", user: dict = Depends(get_current_user)):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: skills.execute("market_data", action="search", query=q))
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"error": result, "results": []}


@router.get("/market/news")
async def market_news(symbol: str = "AAPL", user: dict = Depends(get_current_user)):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: skills.execute("market_data", action="news", symbol=symbol))
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"error": result}
