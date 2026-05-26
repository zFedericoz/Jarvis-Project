import numpy as np
from faster_whisper import WhisperModel
import logging

logger = logging.getLogger("jarvis.speech.stt")

class SpeechToText:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        logger.info(f"Loading Whisper model: {model_size} ({device})")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_data: np.ndarray, language: str | None = None) -> str:
        segments, info = self.model.transcribe(audio_data, language=language)
        text = " ".join(seg.text for seg in segments)
        detected_lang = info.language if info.language else "en"
        logger.info(f"STT: [{detected_lang}] {text}")
        return text.strip(), detected_lang

    def transcribe_file(self, file_path: str) -> str:
        segments, info = self.model.transcribe(file_path)
        text = " ".join(seg.text for seg in segments)
        logger.info(f"STT (file): [{info.language}] {text}")
        return text.strip(), info.language
