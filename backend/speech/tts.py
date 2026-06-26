import os
import asyncio
import logging
import tempfile
import numpy as np
from pathlib import Path

logger = logging.getLogger("jarvis.speech.tts")

# Mapping lingua -> voce Kokoro (ONNX)
KOKORO_VOICE_MAP = {
    "it": "if_sara",       # voce italiana femminile (naturale)
    "en": "af_heart",      # voce inglese femminile
    "fr": "ff_siwis",      # voce francese femminile
    "de": "af_heart",      # fallback inglese (Kokoro non ha DE nativo)
    "es": "ef_dora",       # voce spagnola femminile
}

# Mapping lingua -> voce edge-tts (fallback cloud)
EDGE_VOICE_MAP = {
    "it": "it-IT-IsabellaNeural",
    "en": "en-US-AriaNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
}

# Istanza singleton del modello Kokoro (caricato una volta sola)
_kokoro_model = None


class TextToSpeech:
    def __init__(self, config: dict):
        self.config = config
        tts_cfg = config["speech"]["tts"]
        self.engine = tts_cfg.get("engine", "kokoro")
        self.voice_sample = Path(tts_cfg.get("voice_sample", "models/voice/jarvis_sample.wav"))
        self.device = tts_cfg.get("device", "cpu")
        self.kokoro_speed = tts_cfg.get("kokoro_speed", 1.0)

        self._kokoro_available = False
        self._edge_available = False
        self._xtts_available = False

        self._check_engines()

    # ──────────────────────────────────────────────
    # Availability checks
    # ──────────────────────────────────────────────

    def _check_engines(self):
        # Kokoro-ONNX (primario — locale, nessuna GPU richiesta)
        try:
            import kokoro_onnx  # noqa: F401
            self._kokoro_available = True
            logger.info("Kokoro-ONNX TTS disponibile (motore primario)")
        except ImportError:
            logger.warning("kokoro-onnx non installato — installa con: pip install kokoro-onnx")

        # edge-tts (fallback cloud)
        try:
            import edge_tts  # noqa: F401
            self._edge_available = True
            logger.info("edge-tts disponibile (fallback cloud)")
        except ImportError:
            logger.warning("edge-tts non installato")

        # XTTS v2 (opzionale, solo se voice sample presente)
        if self.voice_sample.exists():
            try:
                from TTS.api import TTS  # noqa: F401
                self._xtts_available = True
                logger.info(f"XTTS disponibile, voice sample: {self.voice_sample}")
            except ImportError:
                logger.warning("TTS package non installato, XTTS disabilitato")
        else:
            logger.info(f"Nessun voice sample in {self.voice_sample} — XTTS disabilitato")

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def synthesize(self, text: str, language: str = "it") -> bytes | None:
        """
        Ordine di priorità:
          1. Kokoro-ONNX  (locale, veloce, alta qualità)
          2. XTTS v2       (voice cloning, richiede GPU per essere usabile)
          3. edge-tts      (fallback cloud)
        """
        if not text or not text.strip():
            return None

        # 1. Kokoro (primario)
        if self._kokoro_available:
            result = self._synthesize_kokoro(text, language)
            if result:
                return result

        # 2. XTTS con voice cloning
        if self._xtts_available and self.voice_sample.exists():
            result = self._synthesize_xtts(text, language)
            if result:
                return result

        # 3. edge-tts (cloud fallback)
        if self._edge_available:
            return self._synthesize_edge(text, language)

        logger.error("Nessun motore TTS disponibile!")
        return None

    async def synthesize_async(self, text: str, language: str = "it") -> bytes | None:
        """
        Versione asincrona — stesso ordine di priorità di synthesize().
        Kokoro e XTTS sono eseguiti in executor per non bloccare l'event loop.
        """
        if not text or not text.strip():
            return None

        loop = asyncio.get_event_loop()

        if self._kokoro_available:
            result = await loop.run_in_executor(None, self._synthesize_kokoro, text, language)
            if result:
                return result

        if self._xtts_available and self.voice_sample.exists():
            result = await loop.run_in_executor(None, self._synthesize_xtts, text, language)
            if result:
                return result

        if self._edge_available:
            return await self._synthesize_edge_async(text, language)

        return None

    # ──────────────────────────────────────────────
    # Kokoro-ONNX
    # ──────────────────────────────────────────────

    def _get_kokoro_model(self):
        global _kokoro_model
        if _kokoro_model is None:
            from kokoro_onnx import Kokoro
            # Il modello viene scaricato automaticamente in ~/.cache/kokoro la prima volta
            _kokoro_model = Kokoro("kokoro-v1.0.onnx", "voices.bin")
            logger.info("Kokoro model caricato")
        return _kokoro_model

    def _synthesize_kokoro(self, text: str, language: str = "it") -> bytes | None:
        try:
            import soundfile as sf
            import io

            kokoro = self._get_kokoro_model()
            voice = KOKORO_VOICE_MAP.get(language, "if_sara")

            # Kokoro restituisce (samples: np.ndarray, sample_rate: int)
            samples, sample_rate = kokoro.create(
                text,
                voice=voice,
                speed=self.kokoro_speed,
                lang=language if language in ("it", "en", "fr", "es") else "en",
            )

            # Converti ndarray → bytes WAV in memoria
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV")
            buf.seek(0)
            data = buf.read()
            logger.debug(f"Kokoro TTS: {len(data)} bytes, voce={voice}, lang={language}")
            return data

        except Exception as e:
            logger.warning(f"Kokoro TTS fallito ({e}), provo fallback")
            return None

    # ──────────────────────────────────────────────
    # XTTS v2 (voice cloning)
    # ──────────────────────────────────────────────

    def _get_xtts_model(self):
        # Import qui per evitare import pesante a startup
        from TTS.api import TTS as CoquiTTS
        # Singleton — una volta caricato in GPU, resta lì per tutte le chiamate
        if not hasattr(self, "_xtts_instance") or self._xtts_instance is None:
            self._xtts_instance = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
            logger.info("XTTS model caricato su %s", self.device)
        return self._xtts_instance

    def warmup_xtts(self):
        """
        Carica XTTS in GPU all'avvio (in un executor), così la prima
        richiesta vocale dell'utente non subisce la latenza del loading.
        Da chiamare in background durante _warmup_all() in main.py.
        """
        try:
            self._get_xtts_model()
            try:
                import torch
                if torch.cuda.is_available():
                    logger.info(
                        "XTTS GPU memory allocata: %.1f GB",
                        torch.cuda.memory_allocated() / 1024 ** 3,
                    )
            except Exception:
                pass
            logger.info("XTTS warmup completato")
        except Exception as e:
            logger.warning("XTTS warmup fallito (verrà ricaricato on-demand): %s", e)

    def _synthesize_xtts(self, text: str, language: str = "it") -> bytes | None:
        try:
            model = self._get_xtts_model()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                model.tts_to_file(
                    text=text,
                    speaker_wav=str(self.voice_sample),
                    language=language if language in ("it", "en", "fr", "de", "es") else "en",
                    file_path=tmp.name,
                )
                with open(tmp.name, "rb") as f:
                    data = f.read()
            Path(tmp.name).unlink(missing_ok=True)
            return data
        except Exception as e:
            logger.warning(f"XTTS fallito ({e}), provo fallback")
            return None

    # ──────────────────────────────────────────────
    # edge-tts (fallback cloud)
    # ──────────────────────────────────────────────

    def _synthesize_edge(self, text: str, language: str = "it") -> bytes | None:
        try:
            import edge_tts
            voice = EDGE_VOICE_MAP.get(language, "it-IT-IsabellaNeural")
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
            asyncio.run(communicate.save(tmp_path))
            with open(tmp_path, "rb") as f:
                data = f.read()
            Path(tmp_path).unlink(missing_ok=True)
            logger.debug(f"edge-tts: {len(data)} bytes, voce={voice}")
            return data
        except Exception as e:
            logger.error(f"edge-tts fallito: {e}")
            return None

    async def _synthesize_edge_async(self, text: str, language: str = "it") -> bytes | None:
        try:
            import edge_tts
            voice = EDGE_VOICE_MAP.get(language, "it-IT-IsabellaNeural")
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
            await communicate.save(tmp_path)
            with open(tmp_path, "rb") as f:
                data = f.read()
            Path(tmp_path).unlink(missing_ok=True)
            return data
        except Exception as e:
            logger.error(f"edge-tts async fallito: {e}")
            return None
