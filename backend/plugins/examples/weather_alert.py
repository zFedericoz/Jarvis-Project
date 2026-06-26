import asyncio
import logging
import time

from plugins import PluginBase

logger = logging.getLogger("jarvis.plugins.weather")

try:
    import httpx
    _httpx = True
except ImportError:
    _httpx = False

CITY = "Bologna"
CHECK_INTERVAL = 1800


class WeatherAlert(PluginBase):
    name = "weather_alert"
    description = "Controlla meteo ogni 30 minuti e segnala cambiamenti significativi"
    version = "1.0.0"

    def __init__(self):
        self._last_weather = None
        self._task = None

    def on_load(self):
        logger.info("WeatherAlert plugin caricato — controllo ogni %s minuti", CHECK_INTERVAL // 60)

    async def execute(self, action: str, params: dict) -> dict:
        if action == "check":
            return await self._check()
        if action == "alert":
            return await self._alert_if_changed()
        if action == "set_city":
            global CITY
            CITY = params.get("city", CITY)
            return {"message": f"Città impostata a {CITY}"}
        return {"error": "Unknown action"}

    async def _check(self) -> dict:
        if not _httpx:
            return {"error": "httpx non installato"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"https://wttr.in/{CITY}?format=%C|%t|%h|%w")
                r.raise_for_status()
                parts = r.text.strip().split("|")
                return {
                    "condition": parts[0] if len(parts) > 0 else "unknown",
                    "temperature": parts[1] if len(parts) > 1 else "?",
                    "humidity": parts[2] if len(parts) > 2 else "?",
                    "wind": parts[3] if len(parts) > 3 else "?",
                }
        except Exception as e:
            logger.warning("Weather check fallito: %s", e)
            return {"error": str(e)}

    async def _alert_if_changed(self) -> dict:
        current = await self._check()
        if "error" in current:
            return current
        if self._last_weather and current.get("condition") != self._last_weather.get("condition"):
            old = self._last_weather.get("condition", "?")
            new = current.get("condition", "?")
            self._last_weather = current
            return {
                "alert": True,
                "message": f"Il meteo è cambiato: {old} -> {new} a {CITY}.",
                "data": current,
            }
        self._last_weather = current
        return {"alert": False, "data": current}