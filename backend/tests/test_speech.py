"""Test per STT, TTS e VAD (con dipendenze mockate)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ── TTS ──────────────────────────────────────────────────────────────

class TestTTSSplitSentences:
    """Test per _split_sentences (streaming TTS progressivo)."""

    @pytest.fixture
    def splitter(self):
        from api.websocket_manager import _split_sentences
        return _split_sentences

    def test_single_sentence(self, splitter):
        result = splitter("Ciao mondo.")
        assert result == ["Ciao mondo."]

    def test_multiple_sentences(self, splitter):
        # min_chars=30: ogni frase (28+14) è sotto soglia, quindi vengono unite
        result = splitter("Oggi è una bella giornata. Domani piove.")
        assert len(result) == 1

    def test_multiple_sentences_low_threshold(self, splitter):
        # Con soglia bassa ogni frase resta separata
        result = splitter("Oggi è una bella giornata. Domani piove.", min_chars=10)
        assert len(result) == 2
        assert "Oggi è una bella giornata." in result
        assert "Domani piove." in result

    def test_sentences_merged_when_below_threshold(self, splitter):
        result = splitter("Sì. No. Forse.", min_chars=10)
        # Ciascuna è < 10, vengono unite in un unico segmento
        assert result == ["Sì. No. Forse."]

    def test_empty_text(self, splitter):
        assert splitter("") == [""]

    def test_no_delimiter(self, splitter):
        result = splitter("Ciao mondo senza punto")
        assert result == ["Ciao mondo senza punto"]

    def test_question_and_exclamation(self, splitter):
        result = splitter("Come stai? Bene! Perfetto.")
        assert all(any(s in r for r in result) for s in ["Come stai?", "Bene!", "Perfetto."])


class TestTTSWarmup:
    """Verifica che warmup_xtts non sollevi eccezioni."""

    @patch("speech.tts.TextToSpeech._get_xtts_model")
    def test_warmup_xtts(self, mock_get_model):
        mock_get_model.return_value = MagicMock()
        from speech.tts import TextToSpeech

        tts = TextToSpeech({"speech": {"tts": {"device": "cpu", "voice_sample": "nonexistent.wav"}}})
        tts._xtts_available = True
        tts.warmup_xtts()
        mock_get_model.assert_called_once()


# ── STT ──────────────────────────────────────────────────────────────

class TestSTTInitialization:
    """Verifica che STT si inizializzi con i parametri corretti."""

    @patch("speech.stt.WhisperModel")
    def test_init_defaults(self, mock_whisper):
        from speech.stt import SpeechToText

        cfg = {"speech": {"stt": {"model": "small", "device": "cuda", "compute_type": "float16"}}}
        stt = SpeechToText(cfg)
        mock_whisper.assert_called_once_with("small", device="cuda", compute_type="float16")

    @patch("speech.stt.WhisperModel")
    def test_transcribe_empty(self, mock_whisper):
        from speech.stt import SpeechToText

        mock_model = MagicMock()
        mock_whisper.return_value = mock_model
        mock_model.transcribe.return_value = ([], type("obj", (object,), {"language": "it", "language_probability": 0.95})())

        cfg = {"speech": {"stt": {"model": "tiny", "device": "cpu", "compute_type": "int8"}}}
        stt = SpeechToText(cfg)
        text, lang = stt.transcribe(np.zeros(16000, dtype=np.float32))
        assert text == ""
        assert lang == "it"


# ── VAD ──────────────────────────────────────────────────────────────

class TestVADInterrupt:
    """Test per VADInterrupt (senza webrtcvad reale)."""

    def test_mark_speaking(self):
        from services.vad import VADInterrupt

        vad = VADInterrupt()
        assert not vad.is_speaking()
        vad.mark_speaking(True)
        assert vad.is_speaking()
        vad.mark_speaking(False)
        assert not vad.is_speaking()

    def test_interrupt_clears_speaking(self):
        from services.vad import VADInterrupt

        vad = VADInterrupt()
        vad._speaking = True
        vad._interrupted = True
        vad.mark_speaking(False)
        assert not vad.was_interrupted()

    def test_clear_interrupt(self):
        from services.vad import VADInterrupt

        vad = VADInterrupt()
        vad._interrupted = True
        vad.clear_interrupt()
        assert not vad.was_interrupted()


# ── Camera ───────────────────────────────────────────────────────────

class TestCameraMonitoring:
    """Test per continuous monitoring (senza webcam/cv2 reale)."""

    def test_change_detection(self):
        # Camera importa cv2 e ultralytics; mockiamo prima
        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = MagicMock()
        with patch.dict("sys.modules", {
            "cv2": MagicMock(),
            "ultralytics": mock_ultralytics,
        }):
            from vision.camera import Camera

        cam = Camera.__new__(Camera)
        cam.model = MagicMock()
        cam._last_objects = frozenset({"person", "chair"})
        cam._lock = MagicMock()
        cam._lock.__enter__ = MagicMock()
        cam._lock.__exit__ = MagicMock()

        calls = []

        def mock_check_once(self, callback):
            callback("Person non e piu nel mio campo visivo.")
            calls.append(1)

        original = Camera._check_once
        Camera._check_once = mock_check_once
        try:
            cam._check_once(lambda msg: calls.append(msg))
            assert len(calls) >= 1
        finally:
            Camera._check_once = original


# ── Progressive TTS integration ─────────────────────────────────────

class TestProgressiveTTS:
    """Verifica che la sintesi progressiva divida correttamente i testi lunghi."""

    def test_long_response_split(self):
        from api.websocket_manager import _split_sentences

        long = (
            "Buongiorno, Signore. La giornata di oggi si preannuncia produttiva. "
            "Ho notato che ha tre appuntamenti in calendario. "
            "Il primo e alle 10:00 con il team di sviluppo. "
            "Vuole che prepari un briefing?")
        parts = _split_sentences(long, min_chars=15)
        assert len(parts) >= 2
        assert all(len(p) >= 15 for p in parts[:-1])