import pvporcupine
import pyaudio
import numpy as np
import struct
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.wakeword")

class WakeWordDetector:
    def __init__(self, keyword: str = "jarvis", sensitivity: float = 0.5):
        self.keyword = keyword
        self.sensitivity = sensitivity
        self.porcupine = None
        self.audio = None
        self.stream = None
        self.callback = None

    def start(self, on_wake: callable):
        self.callback = on_wake
        model_path = Path(f"models/porcupine/{self.keyword}.ppn")
        lib_path = Path("models/porcupine/libpv_porcupine.dll")

        if model_path.exists():
            self.porcupine = pvporcupine.create(
                keyword_paths=[str(model_path)],
                sensitivities=[self.sensitivity],
            )
        else:
            self.porcupine = pvporcupine.create(
                keywords=[self.keyword],
                sensitivities=[self.sensitivity],
            )

        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length,
            stream_callback=self._audio_callback,
        )
        logger.info(f"Wake word active: '{self.keyword}'")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        pcm = struct.unpack_from("h" * self.porcupine.frame_length, in_data)
        result = self.porcupine.process(pcm)
        if result >= 0 and self.callback:
            logger.info(f"Wake word detected: '{self.keyword}'")
            self.callback()
        return (in_data, pyaudio.paContinue)

    def stop(self):
        if self.stream:
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.porcupine:
            self.porcupine.delete()
