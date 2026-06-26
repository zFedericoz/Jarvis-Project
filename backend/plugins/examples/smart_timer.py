import asyncio
import logging
import time

from plugins import PluginBase

logger = logging.getLogger("jarvis.plugins.timer")


class SmartTimer(PluginBase):
    name = "smart_timer"
    description = "Timer e promemoria in memoria"
    version = "1.0.0"

    def __init__(self):
        self._timers: list[dict] = []
        self._task = None

    def on_load(self):
        logger.info("SmartTimer plugin caricato")

    async def execute(self, action: str, params: dict) -> dict:
        if action == "set":
            return await self._set(
                seconds=params.get("seconds", 0),
                label=params.get("label", "Promemoria"),
            )
        if action == "list":
            return {"timers": self._list_active()}
        if action == "cancel":
            return self._cancel(params.get("id"))
        return {"error": f"Unknown action: {action}"}

    async def _set(self, seconds: int, label: str) -> dict:
        if seconds <= 0:
            return {"error": "Il tempo deve essere > 0"}
        tid = f"t{int(time.time())}_{len(self._timers)}"
        expires = time.time() + seconds
        self._timers.append({"id": tid, "label": label, "expires": expires, "remaining": seconds})
        self._timers.sort(key=lambda t: t["expires"])
        logger.info("Timer %s impostato: %s tra %ds", tid, label, seconds)
        return {"timer_id": tid, "label": label, "seconds": seconds}

    def _list_active(self) -> list[dict]:
        now = time.time()
        active = [t for t in self._timers if t["expires"] > now]
        for t in active:
            t["remaining"] = int(t["expires"] - now)
        return active

    def _cancel(self, tid: str) -> dict:
        for t in self._timers:
            if t["id"] == tid:
                self._timers.remove(t)
                return {"cancelled": tid, "label": t["label"]}
        return {"error": f"Timer {tid} non trovato"}