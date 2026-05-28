import pvporcupine
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.wakeword.processor")

_processor_instance = None
_processor_keyword = None
_processor_sensitivity = None

class WakeWordProcessor:
    def __init__(self, keyword: str = "jarvis", sensitivity: float = 0.5, model_path: str = ""):
        model_file = Path(model_path)
        if model_file.exists():
            self.porcupine = pvporcupine.create(
                keyword_paths=[str(model_file)],
                sensitivities=[sensitivity],
            )
            logger.info(f"WakeWordProcessor: custom model loaded from {model_file}")
        else:
            self.porcupine = pvporcupine.create(
                keywords=[keyword],
                sensitivities=[sensitivity],
            )
            logger.info(f"WakeWordProcessor: built-in keyword '{keyword}' (no custom model at {model_path})")
        self.frame_length = self.porcupine.frame_length
        self.sample_rate = self.porcupine.sample_rate

    def process(self, audio_chunk: np.ndarray) -> bool:
        if len(audio_chunk) != self.frame_length:
            return False
        result = self.porcupine.process(audio_chunk.astype(np.int16))
        return result >= 0

    def delete(self):
        self.porcupine.delete()

def get_wake_word_processor(keyword: str = "jarvis", sensitivity: float = 0.5, model_path: str = ""):
    global _processor_instance, _processor_keyword, _processor_sensitivity
    if _processor_instance is None or _processor_keyword != keyword or _processor_sensitivity != sensitivity:
        if _processor_instance is not None:
            _processor_instance.delete()
        _processor_instance = WakeWordProcessor(keyword=keyword, sensitivity=sensitivity, model_path=model_path)
        _processor_keyword = keyword
        _processor_sensitivity = sensitivity
    return _processor_instance