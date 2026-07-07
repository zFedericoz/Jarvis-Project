"""
Always-on wake word + voice loop with VAD interruptibility.
Ascolta il microfono in background, rileva il wake word, avvia STT,
chiama il brain, sintetizza TTS.
L'utente puo interrompere Jarvis parlando (VAD integrato).
"""
import asyncio
import logging
import threading
import time

import numpy as np

from wake_word.processor import get_wake_word_processor, WakeWordProcessor
from speech.stt import get_stt
from speech.tts import get_tts
from brain.intent_router import IntentRouter
from brain.context_manager import ContextManager

logger = logging.getLogger("jarvis.voice_loop")

SAMPLE_RATE = 16000
CHUNK = 1024
SILENCE_TIMEOUT = 2.0
MIN_AUDIO_LEN = 0.5


class VoiceLoop:
    def __init__(self, config: dict):
        self._config = config
        self._running = False
        self._thread: threading.Thread | None = None
        self._ww: WakeWordProcessor | None = None
        self._stt = None
        self._tts = None
        self._vad = None
        self._router = None
        self._ctx = None
        self._on_wake = None
        self._on_response_text = None
        self._on_response_audio = None

        # ── VAD interruzione ──────────────────────────────────────────
        self._processing = False
        self._interrupted = False
        self._interrupt_lock = threading.Lock()

    def set_callbacks(self, on_wake=None, on_response_text=None, on_response_audio=None):
        self._on_wake = on_wake
        self._on_response_text = on_response_text
        self._on_response_audio = on_response_audio

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="voice-loop")
        self._thread.start()
        logger.info("Voice loop avviato (wake word + STT + TTS + VAD)")

    def stop(self):
        self._running = False
        logger.info("Voice loop fermato")

    def _ensure_components(self):
        if self._ww is None:
            self._ww = get_wake_word_processor()
        if self._stt is None:
            self._stt = get_stt(self._config)
        if self._tts is None:
            self._tts = get_tts(self._config)
        if self._router is None:
            self._router = IntentRouter()
        if self._ctx is None:
            self._ctx = ContextManager()
        if self._vad is None:
            from services.vad import get_vad
            self._vad = get_vad()

    # ──────────────────────────────────────────────────────────────────
    # Loop principale — SEMPRE in ascolto
    # ──────────────────────────────────────────────────────────────────

    def _loop(self):
        self._ensure_components()
        try:
            import pyaudio
        except ImportError:
            logger.error("pyaudio non installato -- voice loop disabilitato")
            return

        p = pyaudio.PyAudio()
        try:
            stream = p.open(
                format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                input=True, frames_per_buffer=CHUNK,
            )
            logger.info("Microfono aperto, in ascolto wake word...")

            buffer = b""
            listening = False
            silence_start = 0.0

            while self._running:
                data = stream.read(CHUNK, exception_on_overflow=False)

                # Alimenta VAD durante la risposta di Jarvis
                if self._processing:
                    interrupted = self._vad.feed_audio(data, SAMPLE_RATE)
                    if interrupted:
                        with self._interrupt_lock:
                            self._interrupted = True
                        logger.info("Interruzione rilevata -- utente sta parlando")

                buffer += data

                if not listening:
                    # ── Wake word detection ─────────────
                    if len(buffer) >= CHUNK * 2:
                        chunk = buffer[:CHUNK * 2]
                        buffer = buffer[CHUNK * 2:]
                        if self._ww.process(chunk) is not None:
                            logger.info("Wake word rilevato!")
                            listening = True
                            buffer = b""
                            silence_start = time.time()
                            if self._on_wake:
                                self._on_wake()
                else:
                    # ── Speech collection ───────────────
                    audio_np = (
                        np.frombuffer(data, dtype=np.int16).astype(np.float32)
                        / 32768.0
                    )
                    volume = np.abs(audio_np).mean()

                    if volume < 0.01:
                        if (
                            time.time() - silence_start > SILENCE_TIMEOUT
                            and len(buffer) > int(SAMPLE_RATE * MIN_AUDIO_LEN)
                        ):
                            # Processa in thread separato (non blocca la lettura)
                            buf_copy = buffer
                            threading.Thread(
                                target=lambda: asyncio.run(
                                    self._process_audio(buf_copy)
                                ),
                                daemon=True,
                                name="voice-process",
                            ).start()
                            buffer = b""
                            listening = False
                    else:
                        silence_start = time.time()

            stream.stop_stream()
            stream.close()
        except Exception as e:
            logger.exception(f"Voice loop error: {e}")
        finally:
            p.terminate()

    # ──────────────────────────────────────────────────────────────────
    # STT -> LLM -> TTS (thread separato, async)
    # ──────────────────────────────────────────────────────────────────

    async def _process_audio(self, audio_bytes: bytes):
        with self._interrupt_lock:
            if self._interrupted:
                self._interrupted = False
                return

        try:
            audio_np = (
                np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                / 32768.0
            )
            text, lang = self._stt.transcribe(audio_np)
            if not text.strip():
                return
            logger.info(f"Trascritto: {text}")

            with self._interrupt_lock:
                if self._interrupted:
                    self._interrupted = False
                    return

            from brain.llm import get_brain
            from api.dependencies import get_config

            cfg = get_config()
            llm, _, _ = get_brain(cfg)

            resp, _ = llm.chat(text, context=self._ctx)
            logger.info(f"Risposta: {resp[:100]}")

            if self._on_response_text:
                self._on_response_text(resp)

            with self._interrupt_lock:
                if self._interrupted:
                    logger.info("Risposta saltata -- interrotto durante LLM")
                    self._interrupted = False
                    return

            # Jarvis inizia a parlare -> VAD in ascolto
            self._processing = True
            self._vad.mark_speaking(True)

            tts_audio = await self._tts.synthesize_async(resp, lang)

            with self._interrupt_lock:
                if self._interrupted:
                    logger.info("TTS saltato -- utente ha interrotto")
                    self._interrupted = False
                    self._processing = False
                    self._vad.mark_speaking(False)
                    return

            if self._on_response_audio:
                self._on_response_audio(tts_audio)

        except Exception as e:
            logger.exception(f"Process audio error: {e}")
        finally:
            self._processing = False
            self._vad.mark_speaking(False)


_voice_loop: VoiceLoop | None = None


def get_voice_loop(config: dict | None = None) -> VoiceLoop:
    global _voice_loop
    if _voice_loop is None:
        _voice_loop = VoiceLoop(config or {})
    return _voice_loop