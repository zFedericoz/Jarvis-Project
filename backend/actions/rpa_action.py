"""
RPAAction — automazione UI/RPA per J.A.R.V.I.S.

Capacità:
  1. Apertura app e finestre  (subprocess / pyautogui.hotkey)
  2. Click, doppio click, click destro su coordinate o elementi trovati per immagine
  3. Digitazione testo e compilazione form
  4. Screenshot + analisi LLM vision (describe/find/click what's on screen)
  5. Scroll, drag & drop, hotkey globali

Comandi vocali:
  "JARVIS, apri Chrome"
  "JARVIS, apri il file C:/Dev/main.py in VSCode"
  "JARVIS, fai uno screenshot"
  "JARVIS, cosa c'è sullo schermo?"
  "JARVIS, clicca sul pulsante OK"
  "JARVIS, scrivi 'ciao mondo' nel campo di testo"
  "JARVIS, premi Ctrl+S"
  "JARVIS, premi Alt+Tab"
  "JARVIS, scorri in basso"
  "JARVIS, trascina da (100,200) a (400,300)"

API REST:
  POST /api/rpa/screenshot          → screenshot + path del file
  POST /api/rpa/analyze             → screenshot + analisi LLM
  POST /api/rpa/click               { "x": 100, "y": 200, "button": "left" }
  POST /api/rpa/type                { "text": "ciao" }
  POST /api/rpa/hotkey              { "keys": ["ctrl", "s"] }
  POST /api/rpa/open_app            { "app": "chrome" }
  POST /api/rpa/open_file           { "path": "C:/Dev/main.py", "app": "code" }
  POST /api/rpa/scroll              { "direction": "down", "clicks": 3 }
  GET  /api/rpa/screen_info         → risoluzione + posizione mouse

Dipendenze (aggiunte a requirements.txt):
  pyautogui>=0.9.54
  pillow>=10.0.0         (già usata da pyautogui)
  pygetwindow>=0.0.9     (gestione finestre Windows)
"""

import re
import io
import json
import base64
import asyncio
import logging
import platform
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.rpa")

# ── App aliases ────────────────────────────────────────────────────────────────
# Mapping nome parlato → comando/path eseguibile
_APP_MAP_WINDOWS = {
    "chrome":      "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox":     "firefox.exe",
    "edge":        "msedge.exe",
    "vscode":      "code",
    "vs code":     "code",
    "visual studio code": "code",
    "notepad":     "notepad.exe",
    "bloc note":   "notepad.exe",
    "esplora file": "explorer.exe",
    "explorer":    "explorer.exe",
    "terminale":   "wt.exe",           # Windows Terminal
    "powershell":  "powershell.exe",
    "cmd":         "cmd.exe",
    "discord":     "discord.exe",
    "spotify":     "spotify.exe",
    "word":        "winword.exe",
    "excel":       "excel.exe",
    "outlook":     "outlook.exe",
    "task manager": "taskmgr.exe",
    "calcolatrice": "calc.exe",
}

_APP_MAP_LINUX = {
    "chrome":      "google-chrome",
    "google chrome": "google-chrome",
    "firefox":     "firefox",
    "vscode":      "code",
    "vs code":     "code",
    "visual studio code": "code",
    "terminale":   "gnome-terminal",
    "terminal":    "gnome-terminal",
    "nautilus":    "nautilus",
    "discord":     "discord",
    "spotify":     "spotify",
}

# ── Pattern NL → sottocomando ──────────────────────────────────────────────────
_CMD_PATTERNS = [
    ("screenshot",   [r"\b(screenshot|schermata|cattura\s+(lo\s+)?schermo)\b"]),
    ("analyze",      [r"\b(analizza|cosa c.è|descrivi|guarda)\s+(lo\s+)?schermo\b",
                      r"\bcosa\s+(vedi|c.è)\s+(sullo|nello)\s+schermo\b"]),
    ("click",        [r"\bclicca\s+(su|il|la|lo|nel|nella|sul)\b",
                      r"\bfai\s+click\b", r"\bpremi\s+il\s+tasto\b"]),
    ("double_click", [r"\bdoppio\s+click\b", r"\bdoppio\s+clic\b"]),
    ("right_click",  [r"\bclick\s+destro\b", r"\btasto\s+destro\b"]),
    ("type",         [r"\b(scrivi|digita|inserisci|typed?)\b"]),
    ("hotkey",       [r"\bpremi\s+(ctrl|alt|shift|win|tab|esc|f\d+|invio|enter|canc|delete)\b",
                      r"\b(ctrl|alt|shift)\s*\+\s*\w"]),
    ("open_app",     [r"\b(apri|avvia|lancia|apri l.app)\s+\w",
                      r"\b(open|launch|start)\s+\w"]),
    ("open_file",    [r"\b(apri|apri il file|apri con)\s+.+\.(py|js|ts|txt|md|json|yaml|csv|pdf|docx|xlsx)\b"]),
    ("scroll",       [r"\b(scorri|scrolla|scroll)\s*(in\s+)?(su|giù|alto|basso|up|down)\b"]),
    ("drag",         [r"\b(trascina|drag)\b"]),
    ("screen_info",  [r"\b(risoluzione|dimensioni|schermo|mouse)\b"]),
]


class RPAAction(BaseAction):
    def __init__(self, config: dict, llm_client=None):
        super().__init__(config)
        self._llm = llm_client
        self._pyautogui = None
        self._screenshots_dir = Path("data/screenshots")
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._system = platform.system()

        rpa_cfg = config.get("rpa", {})
        self._move_duration = rpa_cfg.get("move_duration", 0.3)   # secondi per movimento mouse
        self._screenshot_quality = rpa_cfg.get("screenshot_quality", 85)
        self._failsafe = rpa_cfg.get("failsafe", True)             # muovi mouse in angolo per stop
        self._proxy_url = rpa_cfg.get("host_proxy_url", "")         # proxy per host Windows

    # ──────────────────────────────────────────────
    # pyautogui lazy init
    # ──────────────────────────────────────────────

    def _gui(self):
        if self._pyautogui is None:
            try:
                import pyautogui
                pyautogui.FAILSAFE = self._failsafe
                pyautogui.PAUSE = 0.1   # pausa minima tra azioni (sicurezza)
                self._pyautogui = pyautogui
                logger.info("pyautogui inizializzato")
            except ImportError:
                logger.error("pyautogui non installato — pip install pyautogui")
                return None
        return self._pyautogui

    # ──────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────

    async def execute(self, command: str, **kwargs) -> str:
        sub = self._route(command.lower())
        logger.info(f"RPAAction: sub={sub}, cmd={command[:60]}")

        # Se pyautogui non disponibile, proxa le chiamate all'host Windows
        if self._pyautogui is None and self._proxy_url:
            return await self._proxy_execute(sub, command)

        loop = asyncio.get_event_loop()

        if sub == "screenshot":
            return await loop.run_in_executor(None, self._do_screenshot, command)

        if sub == "analyze":
            return await self._do_analyze(command)

        if sub == "click":
            return await loop.run_in_executor(None, self._do_click, command, "left", 1)

        if sub == "double_click":
            return await loop.run_in_executor(None, self._do_click, command, "left", 2)

        if sub == "right_click":
            return await loop.run_in_executor(None, self._do_click, command, "right", 1)

        if sub == "type":
            return await loop.run_in_executor(None, self._do_type, command)

        if sub == "hotkey":
            return await loop.run_in_executor(None, self._do_hotkey, command)

        if sub == "open_app":
            return await loop.run_in_executor(None, self._do_open_app, command)

        if sub == "open_file":
            return await loop.run_in_executor(None, self._do_open_file, command)

        if sub == "scroll":
            return await loop.run_in_executor(None, self._do_scroll, command)

        if sub == "drag":
            return await loop.run_in_executor(None, self._do_drag, command)

        if sub == "screen_info":
            return self._do_screen_info()

        return (
            "Non ho capito quale azione UI eseguire. Prova: "
            "'apri Chrome', 'fai uno screenshot', 'clicca su OK', 'premi Ctrl+S'."
        )

    # ──────────────────────────────────────────────
    # Proxy verso host_rpa_server.py (host Windows)
    # ──────────────────────────────────────────────

    async def _proxy_execute(self, sub: str, command: str) -> str:
        """
        Esegue il comando RPA via HTTP sul proxy Windows host
        quando pyautogui non è disponibile (es. dentro Docker).
        """
        base = self._proxy_url.rstrip("/")

        if sub == "screenshot":
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/screenshot")
            return data.get("result", str(data))

        if sub == "analyze":
            # Proxy prende lo screenshot, poi noi lo analizziamo con LLM locale
            b64_data = await self._proxy_call_async("POST", f"{base}/api/rpa/analyze")
            if b64_data.get("result"):
                return await self._analyze_with_vision(b64_data["result"])
            return "Analisi schermo non disponibile via proxy."

        if sub == "click":
            coords = self._extract_coords(command) or (500, 300)
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/click", {
                "x": coords[0], "y": coords[1], "button": "left", "clicks": 1,
            })
            return data.get("result", str(data))

        if sub == "double_click":
            coords = self._extract_coords(command) or (500, 300)
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/click", {
                "x": coords[0], "y": coords[1], "button": "left", "clicks": 2,
            })
            return data.get("result", str(data))

        if sub == "right_click":
            coords = self._extract_coords(command) or (500, 300)
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/click", {
                "x": coords[0], "y": coords[1], "button": "right", "clicks": 1,
            })
            return data.get("result", str(data))

        if sub == "type":
            text = self._extract_text_to_type(command) or "testo"
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/type", {"text": text})
            return data.get("result", str(data))

        if sub == "hotkey":
            keys = self._extract_keys(command) or ["ctrl", "s"]
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/hotkey", {"keys": keys})
            return data.get("result", str(data))

        if sub == "open_app":
            m = re.search(r"(?:apri|avvia|lancia|open|launch|start)\s+(.+)", command.lower())
            app = m.group(1).strip() if m else command
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/open_app", {"app": app})
            return data.get("result", str(data))

        if sub == "open_file":
            path_m = re.search(r"([A-Za-z]:\\[\w\\\.\-_ ]+|/[\w/\.\-_ ]+)", command)
            path = path_m.group(1) if path_m else command
            app = "code" if "code" in command.lower() else None
            payload = {"path": path}
            if app:
                payload["app"] = app
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/open_file", payload)
            return data.get("result", str(data))

        if sub == "scroll":
            direction = "up" if any(w in command.lower() for w in ("su", "alto", "up")) else "down"
            m = re.search(r"(\d+)", command)
            clicks = int(m.group(1)) if m else 3
            data = self._proxy_call_sync("POST", f"{base}/api/rpa/scroll", {
                "direction": direction, "clicks": clicks,
            })
            return data.get("result", str(data))

        if sub == "drag":
            coords_all = re.findall(r"\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", command)
            if len(coords_all) >= 2:
                data = self._proxy_call_sync("POST", f"{base}/api/rpa/drag", {
                    "x1": int(coords_all[0][0]), "y1": int(coords_all[0][1]),
                    "x2": int(coords_all[1][0]), "y2": int(coords_all[1][1]),
                })
                return data.get("result", str(data))
            return "Specifica origine e destinazione per il drag."

        if sub == "screen_info":
            data = self._proxy_call_sync("GET", f"{base}/api/rpa/screen_info")
            result = data.get("result", {})
            if isinstance(result, dict):
                return f"Risoluzione: {result.get('width')}x{result.get('height')}, Mouse: ({result.get('mouse_x')},{result.get('mouse_y')})"
            return str(data)

        return "Comando RPA non supportato via proxy."

    def _proxy_call_sync(self, method: str, url: str, json_data: dict | None = None) -> dict:
        """Chiamata HTTP sincrona al proxy RPA (usata dentro executor)."""
        try:
            body = json.dumps(json_data).encode("utf-8") if json_data else None
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            logger.error(f"RPA proxy call fallita: {e}")
            return {"status": "error", "message": f"Proxy non raggiungibile: {e.reason}"}
        except Exception as e:
            logger.error(f"RPA proxy error: {e}")
            return {"status": "error", "message": str(e)}

    async def _proxy_call_async(self, method: str, url: str, json_data: dict | None = None) -> dict:
        """Chiamata HTTP asincrona al proxy RPA."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                if method == "GET":
                    resp = await client.get(url)
                else:
                    resp = await client.post(url, json=json_data or {})
                return resp.json()
        except Exception as e:
            logger.error(f"RPA proxy async call fallita: {e}")
            return {"status": "error", "message": str(e)}

    async def _analyze_with_vision(self, b64_image: str) -> str:
        """Analizza uno screenshot base64 con il LLM vision locale."""
        if not self._llm:
            return "LLM non disponibile per l'analisi."

        prompt = (
            "Analizza questo screenshot del desktop. "
            "Descrivi cosa vedi (app aperte, contenuto principale, pulsanti visibili). "
            "Sii conciso e preciso."
        )
        try:
            import ollama
            host = self._config.get("llm", {}).get("host", "http://localhost:11434")
            client = ollama.Client(host=host)
            resp = client.chat(
                model="llava",
                messages=[{"role": "user", "content": prompt, "images": [b64_image]}],
            )
            return resp["message"]["content"]
        except Exception as e:
            logger.warning(f"Vision LLM via proxy fallito: {e}")
            return "Analisi schermo non disponibile."

    # ──────────────────────────────────────────────
    # Screenshot
    # ──────────────────────────────────────────────

    def _do_screenshot(self, command: str = "") -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile — non posso fare screenshot."
        try:
            img = gui.screenshot()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._screenshots_dir / f"screenshot_{ts}.png"
            img.save(str(path), quality=self._screenshot_quality)
            logger.info(f"Screenshot salvato: {path}")
            return f"Screenshot salvato: {path}"
        except Exception as e:
            logger.error(f"Screenshot fallito: {e}")
            return f"Errore screenshot: {e}"

    def _screenshot_as_base64(self) -> str | None:
        """Cattura lo schermo e restituisce base64 per il LLM."""
        gui = self._gui()
        if not gui:
            return None
        try:
            img = gui.screenshot()
            # Ridimensiona a max 1280px di larghezza per non saturare il contesto LLM
            max_w = 1280
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            logger.error(f"Screenshot base64 fallito: {e}")
            return None

    # ──────────────────────────────────────────────
    # Analisi schermo via LLM vision
    # ──────────────────────────────────────────────

    async def _do_analyze(self, command: str) -> str:
        """Cattura lo schermo e chiede al LLM di descriverlo / trovare elementi."""
        if not self._llm:
            return "LLM non disponibile per l'analisi dello schermo."

        loop = asyncio.get_event_loop()
        b64 = await loop.run_in_executor(None, self._screenshot_as_base64)
        if not b64:
            return "Non sono riuscito a catturare lo schermo."

        # Estrai l'intenzione dell'utente per guidare il LLM
        intent_hint = self._extract_vision_intent(command)

        prompt = (
            f"Analizza questo screenshot del desktop e {intent_hint}. "
            "Sii conciso e preciso. Se vedi pulsanti, campi testo o elementi interattivi rilevanti, "
            "descrivi la loro posizione (es. 'in alto a sinistra', 'centro schermo')."
        )

        try:
            import ollama
            client = ollama.Client(host=self._llm.client._client.base_url if hasattr(self._llm, 'client') else "http://localhost:11434")
            resp = client.chat(
                model="llava" if self._llm_has_vision() else self._llm.model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }],
            )
            return resp["message"]["content"]
        except Exception as e:
            logger.warning(f"Vision LLM fallito ({e}) — uso descrizione base")
            return await loop.run_in_executor(None, self._basic_screen_description)

    def _llm_has_vision(self) -> bool:
        """Controlla se il modello corrente supporta vision (es. llava, qwen2-vl)."""
        if not self._llm:
            return False
        model = self._llm.model.lower()
        return any(v in model for v in ("llava", "vision", "vl", "bakllava", "moondream"))

    def _extract_vision_intent(self, command: str) -> str:
        lower = command.lower()
        if "trova" in lower or "cerca" in lower:
            return "trova e descrivi l'elemento richiesto"
        if "clicca" in lower:
            return "indica la posizione esatta dell'elemento su cui cliccare"
        return "descrivi cosa vedi (app aperte, contenuto principale, pulsanti visibili)"

    def _basic_screen_description(self) -> str:
        """Fallback senza vision LLM: info base sullo schermo."""
        try:
            gui = self._gui()
            if not gui:
                return "Non disponibile."
            w, h = gui.size()
            mx, my = gui.position()
            return f"Risoluzione schermo: {w}×{h}px. Posizione mouse: ({mx}, {my})."
        except Exception:
            return "Informazioni schermo non disponibili."

    # ──────────────────────────────────────────────
    # Click
    # ──────────────────────────────────────────────

    def _do_click(self, command: str, button: str = "left", clicks: int = 1) -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile."

        # Estrai coordinate esplicite (es. "clicca su (500, 300)")
        coords = self._extract_coords(command)
        if coords:
            x, y = coords
            gui.click(x, y, button=button, clicks=clicks, duration=self._move_duration)
            action = {1: "Click", 2: "Doppio click"}.get(clicks, "Click")
            return f"{action} {button} su ({x}, {y}) eseguito."

        # Nessuna coordinata → cerca testo nel comando e simula click al centro schermo
        target = self._extract_click_target(command)
        if target:
            return (
                f"Non ho trovato '{target}' sullo schermo tramite coordinate. "
                f"Usa 'JARVIS, analizza lo schermo' per trovare la posizione esatta, "
                f"poi 'clicca su (X, Y)'."
            )

        return "Specifica le coordinate o il nome dell'elemento su cui cliccare."

    def _extract_coords(self, text: str) -> tuple[int, int] | None:
        m = re.search(r"\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    def _extract_click_target(self, text: str) -> str | None:
        m = re.search(r"clicca\s+(?:su|il|la|lo|nel|nella|sul)\s+(?:pulsante\s+|tasto\s+|bottone\s+)?[\"']?([^\"'\n]{2,30})[\"']?", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # ──────────────────────────────────────────────
    # Digitazione
    # ──────────────────────────────────────────────

    def _do_type(self, command: str) -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile."

        # Estrai il testo tra virgolette o dopo "scrivi"/"digita"
        text = self._extract_text_to_type(command)
        if not text:
            return "Non ho capito cosa scrivere. Prova: \"JARVIS, scrivi 'ciao mondo'\"."

        try:
            gui.write(text, interval=0.03)   # interval = pausa tra tasti (simula umano)
            logger.info(f"Digitato: {text[:50]}")
            return f"Digitato: \"{text}\""
        except Exception as e:
            return f"Errore digitazione: {e}"

    def _extract_text_to_type(self, command: str) -> str | None:
        # Tra virgolette singole o doppie
        m = re.search(r"[\"'](.+?)[\"']", command)
        if m:
            return m.group(1)
        # Dopo le keyword
        m = re.search(r"(?:scrivi|digita|inserisci|typed?)\s+(.+)", command, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    # ──────────────────────────────────────────────
    # Hotkey
    # ──────────────────────────────────────────────

    _KEY_ALIASES = {
        "invio": "enter", "spazio": "space", "canc": "delete",
        "backspace": "backspace", "tab": "tab", "esc": "escape",
        "su": "up", "giù": "down", "sinistra": "left", "destra": "right",
        "home": "home", "fine": "end", "pag su": "pageup", "pag giù": "pagedown",
        "stampa": "printscreen", "pausa": "pause",
    }

    def _do_hotkey(self, command: str) -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile."

        keys = self._extract_keys(command)
        if not keys:
            return "Non ho capito la combinazione di tasti. Prova: 'premi Ctrl+S' o 'premi Alt+Tab'."

        try:
            gui.hotkey(*keys)
            logger.info(f"Hotkey: {'+'.join(keys)}")
            return f"Premuto: {'+'.join(k.upper() for k in keys)}"
        except Exception as e:
            return f"Errore hotkey: {e}"

    def _extract_keys(self, command: str) -> list[str]:
        lower = command.lower()
        # Formato "ctrl+s", "alt+tab", "ctrl+shift+z"
        m = re.search(r"((?:ctrl|alt|shift|win|cmd)\s*\+\s*(?:\w+)(?:\s*\+\s*\w+)*)", lower)
        if m:
            raw = re.split(r"\s*\+\s*", m.group(1).strip())
            return [self._KEY_ALIASES.get(k.strip(), k.strip()) for k in raw]

        # Formato parlato: "premi Ctrl S"
        m = re.search(r"premi\s+(.+)", lower)
        if m:
            parts = re.split(r"[\s+]+", m.group(1).strip())
            return [self._KEY_ALIASES.get(p, p) for p in parts if p]

        return []

    # ──────────────────────────────────────────────
    # Apertura app
    # ──────────────────────────────────────────────

    def _do_open_app(self, command: str) -> str:
        app_map = _APP_MAP_WINDOWS if self._system == "Windows" else _APP_MAP_LINUX
        lower = command.lower()

        # Cerca alias nella mappa
        exe = None
        app_name = None
        for alias, binary in sorted(app_map.items(), key=lambda x: -len(x[0])):
            if alias in lower:
                exe = binary
                app_name = alias
                break

        # Estrai nome app direttamente se non trovato nella mappa
        if not exe:
            m = re.search(r"(?:apri|avvia|lancia|open|launch|start)\s+(.+)", lower)
            if m:
                app_name = m.group(1).strip()
                exe = app_name

        if not exe:
            return "Non ho capito quale app aprire."

        try:
            if self._system == "Windows":
                subprocess.Popen(["start", "", exe], shell=True)
            else:
                subprocess.Popen([exe], start_new_session=True)
            logger.info(f"App aperta: {exe}")
            return f"Ho aperto {app_name or exe}."
        except Exception as e:
            logger.error(f"Apertura app fallita ({exe}): {e}")
            return f"Non sono riuscito ad aprire '{app_name or exe}'. Verifica che sia installato."

    # ──────────────────────────────────────────────
    # Apertura file con app specifica
    # ──────────────────────────────────────────────

    def _do_open_file(self, command: str) -> str:
        # Estrai percorso file
        path_match = re.search(
            r"([A-Za-z]:\\[\w\\\.\-_]+|/[\w/\.\-_]+|\.[\w/\.\-_]+)",
            command
        )
        if not path_match:
            # Prova a prendere qualsiasi cosa con un'estensione
            path_match = re.search(r"(\S+\.\w{2,5})", command)

        if not path_match:
            return "Non ho trovato un percorso file valido nel comando."

        file_path = Path(path_match.group(1))

        # App da usare
        app = None
        if "vscode" in command.lower() or "vs code" in command.lower() or "code" in command.lower():
            app = "code"
        elif "notepad" in command.lower() or "bloc note" in command.lower():
            app = "notepad.exe"

        try:
            if app:
                subprocess.Popen([app, str(file_path)])
                return f"Aperto '{file_path.name}' con {app}."
            else:
                if self._system == "Windows":
                    subprocess.Popen(["start", "", str(file_path)], shell=True)
                else:
                    subprocess.Popen(["xdg-open", str(file_path)])
                return f"Aperto '{file_path.name}' con l'applicazione predefinita."
        except Exception as e:
            return f"Errore apertura file: {e}"

    # ──────────────────────────────────────────────
    # Scroll
    # ──────────────────────────────────────────────

    def _do_scroll(self, command: str) -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile."

        lower = command.lower()
        direction = 1   # positivo = su, negativo = giù in pyautogui
        if any(w in lower for w in ("giù", "basso", "down")):
            direction = -1

        # Quanti click di scroll?
        m = re.search(r"(\d+)\s*(?:click|volte|passi)", lower)
        clicks = int(m.group(1)) if m else 3

        try:
            gui.scroll(direction * clicks)
            verso = "in su" if direction > 0 else "in giù"
            return f"Scroll {verso} di {clicks} step eseguito."
        except Exception as e:
            return f"Errore scroll: {e}"

    # ──────────────────────────────────────────────
    # Drag & drop
    # ──────────────────────────────────────────────

    def _do_drag(self, command: str) -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile."

        # "trascina da (100,200) a (400,300)"
        coords = re.findall(r"\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", command)
        if len(coords) < 2:
            return (
                "Specifica origine e destinazione: "
                "\"JARVIS, trascina da (100,200) a (400,300)\"."
            )

        x1, y1 = int(coords[0][0]), int(coords[0][1])
        x2, y2 = int(coords[1][0]), int(coords[1][1])

        try:
            gui.moveTo(x1, y1, duration=self._move_duration)
            gui.dragTo(x2, y2, duration=self._move_duration, button="left")
            return f"Trascinato da ({x1},{y1}) a ({x2},{y2})."
        except Exception as e:
            return f"Errore drag: {e}"

    # ──────────────────────────────────────────────
    # Info schermo
    # ──────────────────────────────────────────────

    def _do_screen_info(self) -> str:
        gui = self._gui()
        if not gui:
            return "pyautogui non disponibile."
        try:
            w, h = gui.size()
            mx, my = gui.position()
            return (
                f"Risoluzione schermo: {w}×{h}px.\n"
                f"Posizione corrente del mouse: ({mx}, {my})."
            )
        except Exception as e:
            return f"Errore info schermo: {e}"

    # ──────────────────────────────────────────────
    # Routing interno
    # ──────────────────────────────────────────────

    def _route(self, cmd: str) -> str:
        for sub, patterns in _CMD_PATTERNS:
            for p in patterns:
                if re.search(p, cmd):
                    return sub
        return "unknown"

    def can_handle(self, intent: str) -> bool:
        return intent in ("rpa", "vision", "ui_automation")
