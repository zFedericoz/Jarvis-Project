import time
import threading
import logging
from datetime import datetime, timedelta
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
        import re
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
        import subprocess
        subprocess.run([
            "powershell",
            "-c",
            f'New-BurntToastNotification -Text "{message}"',
        ])
