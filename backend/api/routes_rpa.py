import asyncio
import logging

from fastapi import APIRouter

from .dependencies import get_config, get_actions
from .routes_common import _push_log
from .schemas import (
    RPAClickRequest, RPATypeRequest, RPAHotkeyRequest,
    RPAOpenAppRequest, RPAOpenFileRequest, RPAScrollRequest,
    RPADragRequest, RPACommandRequest,
)

logger = logging.getLogger("jarvis.api.routes")

router = APIRouter()


@router.post("/rpa/screenshot")
async def rpa_screenshot():
    """
    Cattura uno screenshot del desktop e lo salva in data/screenshots/.

    Response:
      { "status": "ok", "result": "Screenshot salvato: data/screenshots/screenshot_20260101_120000.png" }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, rpa._do_screenshot)
    _push_log("info", "Screenshot catturato")
    return {"status": "ok", "result": result}


@router.post("/rpa/analyze")
async def rpa_analyze():
    """
    Cattura lo schermo e lo analizza con il LLM vision.
    Richiede un modello con supporto immagini (llava, qwen2-vl, ecc.).
    Se il modello non supporta vision, ritorna una descrizione base.
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    result = await rpa._do_analyze("analizza lo schermo")
    _push_log("info", "Analisi schermo completata")
    return {"status": "ok", "result": result}


@router.post("/rpa/click")
async def rpa_click(payload: RPAClickRequest):
    """
    Esegue un click del mouse alle coordinate specificate.

    Esempio:
      POST /api/rpa/click  { "x": 500, "y": 300, "button": "left", "clicks": 1 }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    gui = rpa._gui()
    if not gui:
        return {"status": "error", "message": "pyautogui non disponibile"}

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: gui.click(payload.x, payload.y, button=payload.button,
                          clicks=payload.clicks, duration=rpa._move_duration)
    )
    _push_log("info", f"Click {payload.button} su ({payload.x},{payload.y})")
    return {"status": "ok", "result": f"Click su ({payload.x},{payload.y}) eseguito"}


@router.post("/rpa/type")
async def rpa_type(payload: RPATypeRequest):
    """
    Digita testo nella finestra attiva.

    Esempio:
      POST /api/rpa/type  { "text": "ciao mondo", "interval": 0.05 }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    gui = rpa._gui()
    if not gui:
        return {"status": "error", "message": "pyautogui non disponibile"}

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: gui.write(payload.text, interval=payload.interval))
    _push_log("info", f"Digitato: {payload.text[:40]}")
    return {"status": "ok", "result": f"Digitato: \"{payload.text}\""}


@router.post("/rpa/hotkey")
async def rpa_hotkey(payload: RPAHotkeyRequest):
    """
    Preme una combinazione di tasti.

    Esempi:
      { "keys": ["ctrl", "s"] }        → Salva
      { "keys": ["alt", "tab"] }       → Cambia finestra
      { "keys": ["ctrl", "shift", "t"]} → Riapri tab chiusa
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    gui = rpa._gui()
    if not gui:
        return {"status": "error", "message": "pyautogui non disponibile"}

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: gui.hotkey(*payload.keys))
    combo = "+".join(k.upper() for k in payload.keys)
    _push_log("info", f"Hotkey: {combo}")
    return {"status": "ok", "result": f"Premuto: {combo}"}


@router.post("/rpa/open_app")
async def rpa_open_app(payload: RPAOpenAppRequest):
    """
    Apre un'applicazione per nome.

    Esempi:
      { "app": "chrome" }
      { "app": "vscode" }
      { "app": "notepad" }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, rpa._do_open_app, f"apri {payload.app}")
    _push_log("info", f"App aperta: {payload.app}")
    return {"status": "ok", "result": result}


@router.post("/rpa/open_file")
async def rpa_open_file(payload: RPAOpenFileRequest):
    """
    Apre un file con l'app specificata o quella predefinita.

    Esempi:
      { "path": "C:/Dev/main.py", "app": "code" }
      { "path": "/home/user/report.pdf" }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    app_hint = f" con {payload.app}" if payload.app else ""
    cmd = f"apri il file {payload.path}{app_hint}"
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, rpa._do_open_file, cmd)
    return {"status": "ok", "result": result}


@router.post("/rpa/scroll")
async def rpa_scroll(payload: RPAScrollRequest):
    """
    Esegue lo scroll nella finestra attiva.

    Esempio:
      { "direction": "down", "clicks": 5 }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    cmd = f"scorri in {payload.direction} di {payload.clicks} click"
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, rpa._do_scroll, cmd)
    return {"status": "ok", "result": result}


@router.post("/rpa/drag")
async def rpa_drag(payload: RPADragRequest):
    """
    Esegue un drag & drop tra due coordinate.

    Esempio:
      { "x1": 100, "y1": 200, "x2": 400, "y2": 300 }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    cmd = f"trascina da ({payload.x1},{payload.y1}) a ({payload.x2},{payload.y2})"
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, rpa._do_drag, cmd)
    return {"status": "ok", "result": result}


@router.get("/rpa/screen_info")
async def rpa_screen_info():
    """Ritorna risoluzione schermo e posizione corrente del mouse."""
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    result = rpa._do_screen_info()
    return {"status": "ok", "result": result}


@router.post("/rpa/command")
async def rpa_command(payload: RPACommandRequest):
    """
    Esegue un comando RPA in linguaggio naturale.
    Equivalente a parlare direttamente a JARVIS.

    Esempi:
      { "command": "apri Chrome" }
      { "command": "premi Ctrl+S" }
      { "command": "cosa c'è sullo schermo?" }
      { "command": "clicca su (500, 300)" }
    """
    config = get_config()
    actions = get_actions(config)
    rpa = actions.get("rpa")
    if not rpa:
        return {"status": "error", "message": "RPAAction non disponibile"}

    result = await rpa.execute(payload.command)
    _push_log("info", f"RPA command: {payload.command[:60]}")
    return {"status": "ok", "result": result}
