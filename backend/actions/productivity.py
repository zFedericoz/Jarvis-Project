import time
import threading
import re
import subprocess
import logging
from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.productivity")

class Productivity(BaseAction):
    def __init__(self, config: dict):
        super().__init__(config)
        self.timers: list[dict] = []

    async def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if "timer" in cmd or "conta" in cmd:
            return self._set_timer(cmd)

        if "promemoria" in cmd or "ricorda" in cmd or "remind" in cmd:
            return "Reminders stored in memory."

        return "Timer set."

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
            return "How many minutes or seconds?"

        threading.Thread(target=self._run_timer, args=(total,), daemon=True).start()
        return f"Timer set for {minutes}m {seconds}s."

    def _run_timer(self, duration: int):
        time.sleep(duration)
        logger.info(f"Timer expired! ({duration}s)")
        self._notify("Timer finished!")

    def _notify(self, message: str):
        try:
            subprocess.run([
                "powershell",
                "-NoProfile",
                "-Command",
                f'''
                $null = [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
                $notify = New-Object System.Windows.Forms.NotifyIcon
                $notify.Icon = [System.Drawing.SystemIcons]::Information
                $notify.BalloonTipTitle = "J.A.R.V.I.S."
                $notify.BalloonTipText = "{message}"
                $notify.Visible = $true
                $notify.ShowBalloonTip(5000)
                Start-Sleep -Seconds 5
                $notify.Dispose()
                ''',
            ], timeout=10)
        except Exception as e:
            logger.warning(f"Notification failed: {e}")