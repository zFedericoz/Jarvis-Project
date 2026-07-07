"""
BriefingService — briefing vocale quotidiano di J.A.R.V.I.S.

Genera ogni mattina (ora configurabile) un riassunto vocale con:
  - Saluto personalizzato con nome utente
  - Meteo locale (via wttr.in, nessuna API key richiesta)
  - Fatti del giorno / citazione motivazionale (via LLM)
  - Riepilogo delle preferenze/note salvate rilevanti

Si avvia come background task al boot del server (vedi main.py).

Aggiunta in main.py:
    from services.briefing import BriefingService
    briefing = BriefingService(config, llm_client, tts, persistent_memory)
    briefing.start()
"""

import asyncio
import logging
import threading
from datetime import datetime, time as dt_time, timezone

import httpx

logger = logging.getLogger("jarvis.services.briefing")


class BriefingService:
    def __init__(self, config: dict, llm_client, tts, persistent_memory,
                 websocket_manager=None):
        """
        Args:
            config: configurazione YAML
            llm_client: istanza LLMClient
            tts: istanza TextToSpeech
            persistent_memory: istanza PersistentMemory
            websocket_manager: se fornito, invia il testo del briefing anche al frontend
        """
        self._config = config
        self._llm = llm_client
        self._tts = tts
        self._mem = persistent_memory
        self._ws = websocket_manager

        briefing_cfg = config.get("briefing", {})
        self._hour = briefing_cfg.get("hour", 8)        # ora del briefing (default 8:00)
        self._minute = briefing_cfg.get("minute", 0)
        self._city = briefing_cfg.get("city", "Bologna")  # città per il meteo
        self._enabled = briefing_cfg.get("enabled", True)
        self._language = briefing_cfg.get("language", "it")

        self._thread: threading.Thread | None = None

    # ──────────────────────────────────────────────
    # Avvio
    # ──────────────────────────────────────────────

    def start(self):
        """Avvia il servizio in un thread daemon."""
        if not self._enabled:
            logger.info("Briefing service disabilitato (briefing.enabled: false)")
            return

        self._thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="jarvis-briefing",
        )
        self._thread.start()
        logger.info(f"Briefing service avviato — ogni giorno alle {self._hour:02d}:{self._minute:02d}")

    # ──────────────────────────────────────────────
    # Scheduler
    # ──────────────────────────────────────────────

    def _scheduler_loop(self):
        """Loop che controlla ogni minuto se è ora del briefing."""
        import time
        last_run_date = None

        while True:
            now = datetime.now(timezone.utc)
            target = dt_time(self._hour, self._minute)
            current_t = now.time().replace(second=0, microsecond=0)

            # Esegui una volta al giorno all'ora configurata
            if (current_t.hour == target.hour and
                    current_t.minute == target.minute and
                    last_run_date != now.date()):
                last_run_date = now.date()
                try:
                    asyncio.run(self._deliver_briefing())
                except Exception as e:
                    logger.error(f"Errore durante il briefing: {e}")

            time.sleep(30)  # controlla ogni 30 secondi

    # ──────────────────────────────────────────────
    # Generazione e consegna briefing
    # ──────────────────────────────────────────────

    async def _deliver_briefing(self):
        logger.info("Generazione briefing quotidiano...")

        # 1. Recupera meteo
        weather = await self._get_weather()

        # 2. Recupera nome utente dalle preferenze
        nome = self._mem.get_preference("nome_utente") if self._mem else None
        saluto_nome = f", {nome.capitalize()}" if nome else ""

        # 3. Genera testo briefing via LLM
        now = datetime.now(timezone.utc)
        giorno = now.strftime("%A %d %B %Y")
        ora = now.strftime("%H:%M")

        prompt = self._build_briefing_prompt(saluto_nome, giorno, ora, weather)
        text = self._llm.chat(prompt, language=self._language)
        logger.info(f"Briefing generato ({len(text)} caratteri)")

        # 4. Invia al frontend via WebSocket (testo)
        if self._ws:
            try:
                await self._ws.broadcast({
                    "type": "briefing",
                    "text": text,
                    "timestamp": now.isoformat(),
                })
            except Exception as e:
                logger.warning(f"WebSocket broadcast fallito: {e}")

        # 5. Sintesi vocale
        audio = await self._tts.synthesize_async(text, language=self._language)
        if audio:
            # Salva il file audio per il frontend (il route /api/briefing/audio lo serve)
            audio_path = "data/briefing_latest.wav"
            try:
                with open(audio_path, "wb") as f:
                    f.write(audio)
                logger.info(f"Audio briefing salvato: {audio_path}")
            except Exception as e:
                logger.warning(f"Errore salvataggio audio: {e}")
        else:
            logger.warning("TTS non ha prodotto audio per il briefing")

    def _build_briefing_prompt(self, saluto_nome: str, giorno: str, ora: str, weather: str) -> str:
        weather_section = f"\n\nMeteo attuale: {weather}" if weather else ""
        notes = ""
        if self._mem:
            prefs = self._mem.get_all_preferences()
            relevant = {k: v for k, v in prefs.items()
                        if k not in ("nome_utente",) and not k.startswith("rag_hash_")}
            if relevant:
                note_lines = "\n".join(f"- {k}: {v}" for k, v in list(relevant.items())[:5])
                notes = f"\n\nNote salvate sull'utente:\n{note_lines}"

        return (
            f"Genera un briefing mattutino per J.A.R.V.I.S. da leggere ad alta voce.{weather_section}{notes}\n\n"
            f"Inizia con: 'Buongiorno{saluto_nome}. Oggi è {giorno}, sono le {ora}.'\n"
            f"Poi riporta il meteo in modo naturale (1-2 frasi).\n"
            f"Concludi con una frase motivazionale breve e pertinente.\n"
            f"Tono: professionale, conciso, JARVIS. Massimo 5 frasi totali."
        )

    # ──────────────────────────────────────────────
    # Meteo (wttr.in — nessuna API key)
    # ──────────────────────────────────────────────

    async def _get_weather(self) -> str:
        """
        Recupera il meteo da wttr.in in formato testo.
        Nessuna API key richiesta — funziona subito.
        """
        try:
            url = f"https://wttr.in/{self._city}?format=3&lang=it"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers={"User-Agent": "JARVIS/2.0"})
                if resp.status_code == 200:
                    weather = resp.text.strip()
                    logger.info(f"Meteo: {weather}")
                    return weather
        except Exception as e:
            logger.warning(f"Meteo non disponibile: {e}")
        return ""

    # ──────────────────────────────────────────────
    # Triggering manuale (via API)
    # ──────────────────────────────────────────────

    async def trigger_now(self) -> str:
        """Genera e consegna il briefing immediatamente (chiamato dall'API)."""
        await self._deliver_briefing()
        return "Briefing consegnato."
