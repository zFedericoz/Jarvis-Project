"""
J.A.R.V.I.S. — Host RPA Server (Windows)

Run this OUTSIDE Docker to enable REAL UI automation on the Windows host.
When the Docker backend detects pyautogui is unavailable, it proxies
RPA requests here via host.docker.internal:18766.

Usage:  python host_rpa_server.py
Server: http://localhost:18766

Endpoints mirror those in routes.py (/api/rpa/*).
"""

import io
import os
import re
import json
import base64
import http.server
import subprocess
import platform
from pathlib import Path
from datetime import datetime, timezone

HOST = "0.0.0.0"
PORT = 18766

SCREENSHOTS_DIR = Path("data/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

MOVE_DURATION = 0.3
FAILSAFE = True

_APP_MAP = {
    "chrome":      "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox":     "firefox.exe",
    "edge":        "msedge.exe",
    "vscode":      "code",
    "vs code":     "code",
    "visual studio code": "code",
    "notepad":     "notepad.exe",
    "bloc note":   "notepad.exe",
    "explorer":    "explorer.exe",
    "terminale":   "wt.exe",
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

_gui = None


def _get_gui():
    global _gui
    if _gui is None:
        import pyautogui
        pyautogui.FAILSAFE = FAILSAFE
        pyautogui.PAUSE = 0.1
        _gui = pyautogui
    return _gui


# ── Handlers ────────────────────────────────────────────────────────────────────


def _do_screenshot():
    gui = _get_gui()
    img = gui.screenshot()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"screenshot_{ts}.png"
    img.save(str(path))
    return {"status": "ok", "result": f"Screenshot salvato: {path}"}


def _do_analyze():
    gui = _get_gui()
    img = gui.screenshot()
    max_w = 1280
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"status": "ok", "result": b64}


def _do_click(data: dict):
    gui = _get_gui()
    x = data["x"]
    y = data["y"]
    button = data.get("button", "left")
    clicks = data.get("clicks", 1)
    gui.click(x, y, button=button, clicks=clicks, duration=MOVE_DURATION)
    return {"status": "ok", "result": f"Click {button} su ({x},{y}) eseguito"}


def _do_type(data: dict):
    gui = _get_gui()
    text = data["text"]
    interval = data.get("interval", 0.03)
    gui.write(text, interval=interval)
    return {"status": "ok", "result": f"Digitato: {text}"}


def _do_hotkey(data: dict):
    gui = _get_gui()
    keys = data["keys"]
    gui.hotkey(*keys)
    combo = "+".join(k.upper() for k in keys)
    return {"status": "ok", "result": f"Premuto: {combo}"}


def _do_open_app(data: dict):
    app = data["app"].lower()
    exe = None
    for alias, binary in sorted(_APP_MAP.items(), key=lambda x: -len(x[0])):
        if alias in app:
            exe = binary
            break
    if not exe:
        exe = app
    subprocess.Popen(exe, shell=True)
    return {"status": "ok", "result": f"App aperta: {app}"}


def _do_open_file(data: dict):
    path = data["path"]
    app = data.get("app")
    if app:
        subprocess.Popen([app, path])
    else:
        subprocess.Popen(["start", "", path], shell=True)
    return {"status": "ok", "result": f"File aperto: {path}"}


def _do_scroll(data: dict):
    gui = _get_gui()
    direction = 1 if data.get("direction", "down") == "up" else -1
    clicks = data.get("clicks", 3)
    gui.scroll(direction * clicks)
    verso = "su" if direction > 0 else "giù"
    return {"status": "ok", "result": f"Scroll {verso} di {clicks} step eseguito"}


def _do_drag(data: dict):
    gui = _get_gui()
    gui.moveTo(data["x1"], data["y1"], duration=MOVE_DURATION)
    gui.dragTo(data["x2"], data["y2"], duration=MOVE_DURATION, button="left")
    return {"status": "ok", "result": f"Trascinato da ({data['x1']},{data['y1']}) a ({data['x2']},{data['y2']})"}


def _do_screen_info():
    gui = _get_gui()
    w, h = gui.size()
    mx, my = gui.position()
    return {
        "status": "ok",
        "result": {
            "width": w,
            "height": h,
            "mouse_x": mx,
            "mouse_y": my,
        }
    }


# ── Router ──────────────────────────────────────────────────────────────────────

_ROUTES = {
    "/api/rpa/screenshot":  ("POST", lambda _, __: _do_screenshot()),
    "/api/rpa/analyze":     ("POST", lambda _, __: _do_analyze()),
    "/api/rpa/click":       ("POST", lambda d, __: _do_click(d)),
    "/api/rpa/type":        ("POST", lambda d, __: _do_type(d)),
    "/api/rpa/hotkey":      ("POST", lambda d, __: _do_hotkey(d)),
    "/api/rpa/open_app":    ("POST", lambda d, __: _do_open_app(d)),
    "/api/rpa/open_file":   ("POST", lambda d, __: _do_open_file(d)),
    "/api/rpa/scroll":      ("POST", lambda d, __: _do_scroll(d)),
    "/api/rpa/drag":        ("POST", lambda d, __: _do_drag(d)),
    "/api/rpa/screen_info": ("GET",  lambda _, __: _do_screen_info()),
    "/api/rpa/command":     ("POST", lambda d, b: _route_nl(d.get("command", ""))),
}


def _route_nl(command: str):
    lower = command.lower()
    patterns = [
        ("screenshot",  [r"\b(screenshot|schermata)\b"]),
        ("analyze",     [r"\b(analizza|cosa c.è|descrivi)\s+(lo\s+)?schermo\b"]),
        ("click",       [r"\bclicca\s+(su|il|la|lo)\b"]),
        ("type",        [r"\b(scrivi|digita|inserisci)\b"]),
        ("hotkey",      [r"\bpremi\s+(ctrl|alt|shift|win|f\d+)\b"]),
        ("open_app",    [r"\b(apri|avvia|lancia)\s+\w"]),
        ("scroll",      [r"\b(scorri|scrolla)\s*(in\s+)?(su|giù|alto|basso)\b"]),
        ("drag",        [r"\btrascina\s+da\b"]),
        ("screen_info", [r"\b(risoluzione|schermo|mouse)\b"]),
    ]
    for sub, pats in patterns:
        for p in pats:
            if re.search(p, lower):
                return {"status": "ok", "result": f"Comando '{sub}' riconosciuto. Usa l'endpoint dedicato /api/rpa/{sub} con i parametri appropriati."}
    return {"status": "error", "result": "Comando non riconosciuto."}


# ── HTTP Server ─────────────────────────────────────────────────────────────────


class RPAHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json({})

    def do_GET(self):
        route = _ROUTES.get(self.path)
        if route and route[0] == "GET":
            try:
                result = route[1]({}, self.path)
                self._send_json(result)
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 500)
        else:
            self._send_json({"status": "error", "message": "Not found"}, 404)

    def do_POST(self):
        route = _ROUTES.get(self.path)
        if not route or route[0] != "POST":
            self._send_json({"status": "error", "message": "Not found"}, 404)
            return

        content_len = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_len) if content_len else b"{}"
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._send_json({"status": "error", "message": "Invalid JSON"}, 400)
            return

        try:
            result = route[1](data, self.path)
            self._send_json(result)
        except Exception as e:
            self._send_json({"status": "error", "message": str(e)}, 500)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print("J.A.R.V.I.S. Host RPA Server")
    print("----------------------------")
    print(f"Server in esecuzione su http://{HOST}:{PORT}")
    print(f"Espone 11 endpoint RPA su /api/rpa/*")
    print("Premi Ctrl+C per fermarlo.")
    print()

    server = http.server.HTTPServer((HOST, PORT), RPAHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer fermato.")
        server.server_close()
