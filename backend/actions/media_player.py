import subprocess
import logging
from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.media")

class MediaPlayer(BaseAction):
    def __init__(self, config: dict):
        super().__init__(config)
        self.player = None

    async def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if "play" in cmd or "riproduci" in cmd:
            return self._play(command)
        if "pause" in cmd or "pausa" in cmd:
            return self._pause()
        if "stop" in cmd:
            return self._stop()
        if "next" in cmd or "skippa" in cmd or "successiva" in cmd:
            return self._next()
        if "previous" in cmd or "precedente" in cmd:
            return self._previous()
        if "volume" in cmd:
            return self._set_volume(cmd)

        return "Media command not recognized."

    def _play(self, command: str) -> str:
        subprocess.run(["powershell", "-c", "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB3)"])
        return "Playing media."

    def _pause(self) -> str:
        subprocess.run(["powershell", "-c", "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB3)"])
        return "Media paused."

    def _stop(self) -> str:
        return "Stop not supported via keyboard shortcut."

    def _next(self) -> str:
        subprocess.run(["powershell", "-c", "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB0)"])
        return "Skipped to next track."

    def _previous(self) -> str:
        subprocess.run(["powershell", "-c", "(New-Object -ComObject WScript.Shell).SendKeys([char]0xB1)"])
        return "Previous track."

    def _set_volume(self, cmd: str) -> str:
        return "Use system control for volume adjustment."

    def can_handle(self, intent: str) -> bool:
        return intent == "media_player"
