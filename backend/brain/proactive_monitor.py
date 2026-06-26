"""
ProactiveMonitor — monitoraggio metriche di sistema con notifiche proattive.
Controlla periodicamente CPU, RAM, temperatura, disco.
Se una soglia critica viene superata per 2 controlli consecutivi,
invia una notifica WebSocket broadcast in stile Jarvis.
Anti-spam: non rinotifica lo stesso evento per 5 minuti.
"""
import asyncio
import logging
from datetime import datetime, timezone

from api.routes_common import _collect_metrics
from api.websocket_manager import manager

logger = logging.getLogger("jarvis.brain.proactive")

CHECK_INTERVAL = 30

# Soglie configurabili
THRESHOLDS = {
    "cpu": {"max": 90.0, "consecutive": 2},
    "ram": {"max": 90.0, "consecutive": 2},
    "temp": {"max": 80.0, "consecutive": 2},
    "disk": {"max": 95.0, "consecutive": 2},
}

COOLDOWN_SECONDS = 300  # 5 minuti

COOLDOWN_WARN = 60  # 1 minuto per warning meno critici

# Messaggi in stile Jarvis
ALERT_MESSAGES = {
    "cpu": (
        "Signore, ho rilevato un utilizzo della CPU anomalo, al {value}%. "
        "Vuole che verifichi i processi attivi?"
    ),
    "ram": (
        "Signore, la memoria RAM è al {value}%. "
        "Se il sistema rallenta, posso elencare i processi più pesanti."
    ),
    "temp": (
        "Signore, la temperatura del sistema ha raggiunto {value}°C. "
        "Potrebbe essere utile controllare la ventilazione."
    ),
    "disk": (
        "Signore, lo spazio su disco è al {value}%. "
        "Se vuole posso analizzare i file più grandi e suggerire una pulizia."
    ),
    "cpu_recovered": "Signore, l'utilizzo della CPU è tornato alla normalità ({value}%).",
    "temp_recovered": "Signore, la temperatura è scesa a {value}°C. Tutto nella norma.",
    "ram_recovered": "Signore, la RAM è tornata a livelli normali ({value}%).",
    "disk_recovered": "Signore, lo spazio su disco è migliorato ({value}%).",
}


class ProactiveMonitor:
    def __init__(self, thresholds: dict | None = None):
        self._thresholds = thresholds or THRESHOLDS
        self._running = False
        self._task: asyncio.Task | None = None
        self._consecutive: dict[str, int] = {}
        self._last_notified: dict[str, float] = {}
        self._last_alerted: dict[str, bool] = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ProactiveMonitor avviato (check ogni %ds)", CHECK_INTERVAL)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ProactiveMonitor fermato")

    async def _loop(self):
        while self._running:
            try:
                await self._check()
            except Exception as e:
                logger.warning("ProactiveMonitor check error: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check(self):
        metrics = _collect_metrics()

        checks = {
            "cpu": metrics.get("cpu", 0),
            "ram": metrics.get("ram", 0),
            "temp": metrics.get("temp") or 0,
            "disk": metrics.get("disk", 0),
        }

        now = datetime.now(timezone.utc).timestamp()

        for key, value in checks.items():
            threshold = self._thresholds.get(key)
            if threshold is None:
                continue
            max_val = threshold["max"]
            needed = threshold.get("consecutive", 2)

            is_high = value >= max_val
            was_high = self._last_alerted.get(key, False)

            if is_high:
                count = self._consecutive.get(key, 0) + 1
                self._consecutive[key] = count

                if count >= needed and not was_high:
                    cooldown = self._last_notified.get(key, 0)
                    if now - cooldown > COOLDOWN_SECONDS:
                        msg = ALERT_MESSAGES[key].format(value=value)
                        await self._notify(key, "alert", msg)
                        self._last_notified[key] = now
                        self._last_alerted[key] = True
                        logger.info("Notifica proattiva [%s]: %.1f", key, value)
            else:
                self._consecutive[key] = 0
                if was_high:
                    # Recupero
                    cooldown = self._last_notified.get(f"{key}_recovered", 0)
                    if now - cooldown > COOLDOWN_WARN:
                        recovery_key = f"{key}_recovered"
                        msg = ALERT_MESSAGES.get(recovery_key, "Signore, %s è tornato alla normalità (%s).").format(value=value)
                        await self._notify(recovery_key, "recovery", msg)
                        self._last_notified[recovery_key] = now
                        self._last_alerted[key] = False

    async def _notify(self, event_type: str, severity: str, message: str):
        payload = {
            "type": "proactive",
            "source": "monitor",
            "event": event_type,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await manager.broadcast(payload)


_monitor: ProactiveMonitor | None = None


def get_proactive_monitor(thresholds: dict | None = None) -> ProactiveMonitor:
    global _monitor
    if _monitor is None:
        _monitor = ProactiveMonitor(thresholds)
    return _monitor
