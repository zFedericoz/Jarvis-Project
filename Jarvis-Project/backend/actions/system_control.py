import subprocess
import psutil
import logging
from pathlib import Path
from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.system")

class SystemControl(BaseAction):
    async def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if "volume up" in cmd or "alza volume" in cmd:
            self._change_volume(10)
            return "Volume increased."

        if "volume down" in cmd or "abbassa volume" in cmd:
            self._change_volume(-10)
            return "Volume decreased."

        if "mute" in cmd or "silenzia" in cmd:
            self._change_volume(-100)
            return "System muted."

        if "shutdown" in cmd or "spegnimento" in cmd:
            subprocess.run(["shutdown", "/s", "/t", "10"])
            return "Shutting down in 10 seconds."

        if "restart" in cmd or "riavvia" in cmd:
            subprocess.run(["shutdown", "/r", "/t", "10"])
            return "Restarting in 10 seconds."

        if "lock" in cmd or "blocca" in cmd:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Workstation locked."

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        return f"System status: CPU at {cpu}%, RAM at {ram.percent}% ({ram.used // 1024**3}GB/{ram.total // 1024**3}GB used)"

    def _change_volume(self, delta: int):
        import pycaw.pycaw
        from pycaw.api.endpoint import AudioEndpoint
        subprocess.run(["nircmd", "changesysvolume", str(delta * 655)])

    def can_handle(self, intent: str) -> bool:
        return intent == "system_control"
