"""
Intelligenza proattiva — analizza contesto e invia notifiche/azioni predittive.
- Rileva ora del giorno, giorno della settimana, pattern d'uso
- Suggerisce azioni basate su contesto (riunioni, meteo, orario)
- Invia notifiche push al frontend
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("jarvis.proactive")

CHECK_INTERVAL = 60  # secondi tra ogni check


class ProactiveEngine:
    def __init__(self, config: dict):
        self._config = config
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_notification: dict[str, float] = {}  # cooldown per tipo

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ProactiveEngine avviato")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            try:
                await self._check_context()
            except Exception as e:
                logger.warning(f"Proactive check error: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_context(self):
        now = datetime.now(timezone.utc)
        local_hour = now.hour  # sarà ora locale quando configurato
        weekday = now.weekday()  # 0=lunedì

        triggers = []

        # Mattina presto (7:00-9:00, giorni feriali) — suggerisci briefing
        if 7 <= local_hour < 9 and weekday < 5:
            triggers.append(("briefing", "Buongiorno! Vuole il briefing mattutino?"))

        # Metà mattina (10:00-11:00) — pausa
        if local_hour == 10 and weekday < 5:
            triggers.append(("break", "È ora di una pausa caffè?"))

        # Mezzogiorno (12:00-13:00) — pranzo
        if local_hour == 12:
            triggers.append(("lunch", "È ora di pranzo. Vuole che cerchi un ristorante?"))

        # Pomeriggio (15:00-16:00) — controllo energia
        if local_hour == 15 and weekday < 5:
            triggers.append(("checkin", "Come sta procedendo la giornata?"))

        # Sera (19:00-20:00) — riepilogo
        if local_hour == 19 and weekday < 5:
            triggers.append(("summary", "Vuole un riepilogo della giornata?"))

        # Weekend — suggerimenti diversi
        if weekday >= 5 and local_hour == 10:
            triggers.append(("weekend", "Buon weekend! Ha dei piani?"))

        for trigger_type, message in triggers:
            # Cooldown: non notificare più di una volta ogni 4 ore per tipo
            last = self._last_notification.get(trigger_type, 0)
            if now.timestamp() - last > 14400:
                self._last_notification[trigger_type] = now.timestamp()
                await self._notify(trigger_type, message)

    async def _notify(self, trigger_type: str, message: str):
        try:
            # Invia al frontend via WebSocket broadcast
            async with httpx.AsyncClient() as c:
                await c.post("http://localhost:8765/api/broadcast",
                             json={"type": "proactive", "subtype": trigger_type, "message": message},
                             timeout=5)
            logger.info(f"Notifica proattiva: [{trigger_type}] {message}")
        except Exception as e:
            logger.warning(f"Notifica fallita: {e}")


_proactive: ProactiveEngine | None = None


def get_proactive_engine(config: dict | None = None) -> ProactiveEngine:
    global _proactive
    if _proactive is None:
        _proactive = ProactiveEngine(config or {})
    return _proactive
