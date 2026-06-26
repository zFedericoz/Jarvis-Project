"""
Voice Activity Detection — rileva quando l'utente parla mentre Jarvis sta rispondendo.
Usa webrtcvad per segmentazione audio in tempo reale.
Permette interruzione naturale: se l'utente parla, Jarvis smette di parlare.
"""
import logging
import threading

logger = logging.getLogger("jarvis.vad")


class VADInterrupt:
    def __init__(self, aggressiveness: int = 2):
        self._aggressiveness = aggressiveness
        self._vad = None
        self._speaking = False  # Jarvis sta parlando
        self._interrupted = False  # utente ha interrotto
        self._lock = threading.Lock()

    def _ensure_vad(self):
        if self._vad is not None:
            return
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(self._aggressiveness)
            logger.info(f"VAD inizializzato (aggressiveness={self._aggressiveness})")
        except ImportError:
            logger.warning("webrtcvad non installato — interrompibilità disabilitata. `pip install webrtcvad`")

    def mark_speaking(self, is_speaking: bool):
        """Jarvis inizia/finisce di parlare."""
        with self._lock:
            self._speaking = is_speaking
            if not is_speaking:
                self._interrupted = False

    def is_speaking(self) -> bool:
        with self._lock:
            return self._speaking

    def feed_audio(self, frame: bytes, sample_rate: int = 16000) -> bool:
        """
        Analizza un frame audio (16-bit PCM, 16kHz, mono, 30ms).
        Se Jarvis sta parlando e viene rilevata voce utente → interruzione.
        Restituisce True se interrotto.
        """
        self._ensure_vad()
        if self._vad is None or not self._speaking:
            return False

        is_speech = self._vad.is_speech(frame, sample_rate)
        if is_speech:
            with self._lock:
                self._interrupted = True
                self._speaking = False
            logger.info("Interruzione rilevata!")
            return True
        return False

    def was_interrupted(self) -> bool:
        with self._lock:
            return self._interrupted

    def clear_interrupt(self):
        with self._lock:
            self._interrupted = False


_vad: VADInterrupt | None = None


def get_vad() -> VADInterrupt:
    global _vad
    if _vad is None:
        _vad = VADInterrupt()
    return _vad
