import asyncio
import io
import base64
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("jarvis.speech.tts")

LANG_MAP = {
    "it": "it-IT-IsabellaNeural",
    "en": "en-US-AriaNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
}

class TextToSpeech:
    def __init__(self, config: dict):
        self.config = config
        self.engine = config["speech"]["tts"]["engine"]
        self.voice_sample = Path(config["speech"]["tts"]["voice_sample"])
        self.device = config["speech"]["tts"]["device"]
        self._edge_available = False
        self._xtts_available = False
        self._check_engines()

    def _check_engines(self):
        try:
            import edge_tts
            self._edge_available = True
            logger.info("edge-tts available")
        except ImportError:
            logger.warning("edge-tts not installed")

        if self.voice_sample.exists():
            try:
                from TTS.api import TTS
                self._xtts_available = True
                logger.info(f"XTTS available, voice sample found: {self.voice_sample}")
            except ImportError:
                logger.warning("TTS package not installed, XTTS unavailable")
        else:
            logger.info(f"No voice sample at {self.voice_sample}, XTTS disabled")

    def synthesize(self, text: str, language: str = "it") -> bytes | None:
        if self._xtts_available and self.voice_sample.exists():
            result = self._synthesize_xtts(text, language)
            if result:
                return result
        if self._edge_available:
            return self._synthesize_edge(text, language)
        return None

    def _synthesize_xtts(self, text: str, language: str = "it") -> bytes | None:
        try:
            import builtins
            original_input = builtins.input
            def auto_accept(prompt=""):
                return "y"
            builtins.input = auto_accept

            from TTS.api import TTS
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
            builtins.input = original_input
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tts.tts_to_file(
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
            logger.warning(f"XTTS failed ({e}), falling back")
            return None

    def _synthesize_edge(self, text: str, language: str = "it") -> bytes | None:
        try:
            import edge_tts
            voice = LANG_MAP.get(language, "it-IT-IsabellaNeural")
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            asyncio.run(communicate.save(tmp_path))
            with open(tmp_path, "rb") as f:
                data = f.read()
            Path(tmp_path).unlink(missing_ok=True)
            return data
        except Exception as e:
            logger.error(f"edge-tts failed: {e}")
            return None

    async def synthesize_async(self, text: str, language: str = "it") -> bytes | None:
        if self._xtts_available and self.voice_sample.exists():
            result = self._synthesize_xtts(text, language)
            if result:
                return result
        if self._edge_available:
            try:
                import edge_tts
                voice = LANG_MAP.get(language, "it-IT-IsabellaNeural")
                communicate = edge_tts.Communicate(text, voice)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                await communicate.save(tmp_path)
                with open(tmp_path, "rb") as f:
                    data = f.read()
                Path(tmp_path).unlink(missing_ok=True)
                return data
            except Exception as e:
                logger.error(f"edge-tts async failed: {e}")
                return None
        return None
