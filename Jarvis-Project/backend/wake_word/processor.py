import pvporcupine
import numpy as np
import logging

logger = logging.getLogger("jarvis.wakeword.processor")

class WakeWordProcessor:
    def __init__(self, keyword: str = "jarvis", sensitivity: float = 0.5):
        self.porcupine = pvporcupine.create(
            keywords=[keyword],
            sensitivities=[sensitivity],
        )
        self.frame_length = self.porcupine.frame_length
        self.sample_rate = self.porcupine.sample_rate
        logger.info(f"WakeWordProcessor initialized: '{keyword}' @ {self.sample_rate}Hz")

    def process(self, audio_chunk: np.ndarray) -> bool:
        if len(audio_chunk) != self.frame_length:
            return False
        result = self.porcupine.process(audio_chunk.astype(np.int16))
        return result >= 0

    def delete(self):
        self.porcupine.delete()
