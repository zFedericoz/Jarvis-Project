"""
Productivity — action che gestisce timer, promemoria e modalità focus.

Step 6: integra FocusMode (Pomodoro + blocco siti + DND).
"""

import re
import time
import threading
import subprocess
import logging
from .base_action import BaseAction
from .focus_mode import FocusMode

logger = logging.getLogger("jarvis.actions.productivity")

# Pattern per rilevare il sottocomando
_FOCUS_PATTERNS = [
    (r"\b(attiva|inizia|avvia|start)\s+(la\s+)?modalità\s+focus\b", "focus_start"),
    (r"\b(inizia|avvia|start|fai)\s+(un\s+)?pomodoro\b",             "focus_start"),
    (r"\bpomodoro\s+(da\s+)?(\d+)\b",                                "focus_start_custom"),
    (r"\b(pausa|metti in pausa)\s+(il\s+)?(focus|pomodoro)\b",       "focus_pause"),
    (r"\b(riprendi|continua)\s+(il\s+)?(focus|pomodoro)\b",          "focus_resume"),
    (r"\b(disattiva|ferma|stop|termina)\s+(la\s+)?(modalità\s+)?focus\b", "focus_stop"),
    (r"\bquanto\s+(manca|resta|rimane)\b",                           "focus_status"),
    (r"\b(stato|status)\s+(del\s+)?(focus|pomodoro)\b",              "focus_status"),
    (r"\baggiungi\s+(.+?)\s+(alla\s+)?blacklist\s+focus\b",          "focus_add_site"),
    (r"\brimuovi\s+(.+?)\s+(dalla\s+)?blacklist\s+focus\b",          "focus_remove_site"),
    (r"\b(lista|elenco)\s+(dei\s+)?siti\s+(bloccati|focus)\b",       "focus_list_sites"),
]


class Productivity(BaseAction):
    def __init__(self, config: dict, tts=None, persistent_memory=None):
        super().__init__(config)
        self.timers: list[dict] = []
        self._focus = FocusMode(config, tts=tts, persistent_memory=persistent_memory)

    async def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower().strip()

        # ── Focus mode routing ────────────────────────────────────────────────
        for pattern, action in _FOCUS_PATTERNS:
            m = re.search(pattern, cmd)
            if m:
                return self._handle_focus(action, cmd, m)

        # ── Timer ─────────────────────────────────────────────────────────────
        if "timer" in cmd or "conta" in cmd or "conto alla rovescia" in cmd:
            return self._set_timer(cmd)

        # ── Promemoria ────────────────────────────────────────────────────────
        if "promemoria" in cmd or "ricorda" in cmd or "remind" in cmd:
            return "Promemoria salvato in memoria. Ti avviserò al momento opportuno."

        return "Non ho capito. Puoi chiedermi di impostare un timer, un promemoria o attivare la modalità focus."

    # ──────────────────────────────────────────────
    # Focus dispatch
    # ──────────────────────────────────────────────

    def _handle_focus(self, action: str, cmd: str, match) -> str:
        if action == "focus_start":
            return self._focus.start()

        if action == "focus_start_custom":
            # "pomodoro da 45 minuti" → estrae 45
            m = re.search(r"(\d+)", cmd)
            minutes = int(m.group(1)) if m else None
            return self._focus.start(work_minutes=minutes)

        if action == "focus_pause":
            return self._focus.pause()

        if action == "focus_resume":
            return self._focus.resume()

        if action == "focus_stop":
            return self._focus.stop()

        if action == "focus_status":
            return self._focus.status_text()

        if action == "focus_add_site":
            # Estrae il sito dal match o dal comando
            site = self._extract_site(cmd)
            if not site:
                return "Non ho capito quale sito aggiungere. Prova: 'aggiungi reddit.com alla blacklist focus'."
            return self._focus.add_site(site)

        if action == "focus_remove_site":
            site = self._extract_site(cmd)
            if not site:
                return "Non ho capito quale sito rimuovere."
            return self._focus.remove_site(site)

        if action == "focus_list_sites":
            return self._focus.list_sites()

        return "Comando focus non riconosciuto."

    def _extract_site(self, cmd: str) -> str | None:
        """Estrae un dominio dalla frase (es. 'aggiungi reddit.com...' → 'reddit.com')."""
        m = re.search(
            r"(?:aggiungi|rimuovi)\s+([\w\.\-]+(?:\.\w{2,}))",
            cmd
        )
        return m.group(1) if m else None

    # ──────────────────────────────────────────────
    # Timer (invariato dall'originale, solo refactored)
    # ──────────────────────────────────────────────

    def _set_timer(self, cmd: str) -> str:
        minutes = 0
        seconds = 0

        m = re.search(r"(\d+)\s*minut[oie]?", cmd)
        if m:
            minutes = int(m.group(1))
        s = re.search(r"(\d+)\s*second[oie]?", cmd)
        if s:
            seconds = int(s.group(1))

        total = minutes * 60 + seconds
        if total == 0:
            return "Quanti minuti o secondi per il timer?"

        threading.Thread(
            target=self._run_timer, args=(total,),
            daemon=True, name=f"jarvis-timer-{total}s"
        ).start()

        if minutes and seconds:
            return f"Timer impostato: {minutes} minuti e {seconds} secondi."
        elif minutes:
            return f"Timer impostato: {minutes} minuti."
        else:
            return f"Timer impostato: {seconds} secondi."

    def _run_timer(self, duration: int):
        time.sleep(duration)
        logger.info(f"Timer scaduto ({duration}s)")
        self._notify("Timer scaduto!")

    def _notify(self, message: str):
        try:
            ps_script = f"""
$null = [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = "J.A.R.V.I.S."
$notify.BalloonTipText = "{message}"
$notify.Visible = $true
$notify.ShowBalloonTip(5000)
Start-Sleep -Seconds 5
$notify.Dispose()
"""
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                timeout=10, capture_output=True,
            )
        except Exception as e:
            logger.warning(f"Notifica fallita: {e}")

    def can_handle(self, intent: str) -> bool:
        return intent == "productivity"

    # ── Espone il FocusMode per le API REST ───────────────────────────────────
    @property
    def focus(self) -> FocusMode:
        return self._focus
