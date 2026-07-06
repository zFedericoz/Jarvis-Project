import numpy as np
from faster_whisper import WhisperModel
import logging

logger = logging.getLogger("jarvis.speech.stt")


class SpeechToText:
    """
    Speech-to-text con faster-whisper su GPU.

    Trade-off modelli per GPU consumer (8-12 GB VRAM, realtime):

      tiny   (~75 MB)  — troppo impreciso, specialmente in italiano.
                          Sconsigliato anche su GPU.
      base   (~150 MB) — buon equilibrio, trascrizione sub-50ms su GPU.
                          Accettabile, ma "small" offre molto più per pochi MB.
      small  (~500 MB) — scelta consigliata. Eccellente per italiano,
                          trascrizione ~50-100ms su GPU float16.
                          Lascia VRAM libera per XTTS e vision.
      medium (~1.5 GB) — qualità massima, trascrizione ~100-200ms su GPU.
                          Consumano ~1 GB di VRAM in più; consigliato solo
                          se la precisione è critica e XTTS/vision non servono
                          contemporaneamente.

    Conclusione: "small" è il default perché offre il miglior rapporto
    qualità/velocità/VRAM in un sistema che carica anche XTTS e YOLO.
    Con GPU + float16 è ~5x più veloce di CPU + int8.
    """

    def __init__(self, config: dict | None = None):
        if config is None:
            import yaml
            with open("config/settings.yaml") as f:
                config = yaml.safe_load(f)

        stt_cfg = config["speech"]["stt"]
        model_size = stt_cfg.get("model", "small")
        device = stt_cfg.get("device", "cuda")
        compute_type = stt_cfg.get("compute_type", "float16")

        # Lingua fissa o auto-detection
        self.default_language = stt_cfg.get("language", None)
        if self.default_language == "auto":
            self.default_language = None  # faster-whisper usa None per auto-detect

        logger.info(f"Caricamento Whisper: {model_size} ({device}, {compute_type})")
        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )
        except Exception:
            logger.warning(f"Whisper con {device}/{compute_type} fallito, fallback a cpu/int8")
            self.model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )
        logger.info("Whisper pronto")

    def transcribe(self, audio_data: np.ndarray, language: str | None = None) -> tuple[str, str]:
        """
        Trascrive un array numpy (float32, mono, 16kHz).
        Restituisce (testo, lingua_rilevata).
        """
        lang = language or self.default_language  # None = auto-detect

        segments, info = self.model.transcribe(
            audio_data,
            language=lang,
            vad_filter=True,           # filtra silenzio con Voice Activity Detection
            vad_parameters={
                "min_silence_duration_ms": 500,   # pausa minima per separare segmenti
                "speech_pad_ms": 200,              # padding attorno alla voce
            },
            beam_size=5,               # migliore accuratezza (era default 5, esplicitato)
            best_of=5,
            temperature=0.0,           # deterministico → più accurato per comandi vocali
        )

        text = " ".join(seg.text.strip() for seg in segments)
        detected_lang = info.language if info.language else "it"

        logger.info(f"STT [{detected_lang}, prob={info.language_probability:.2f}]: {text!r}")
        return text.strip(), detected_lang

    def transcribe_file(self, file_path: str, language: str | None = None) -> tuple[str, str]:
        """Trascrive un file audio da disco."""
        lang = language or self.default_language

        segments, info = self.model.transcribe(
            file_path,
            language=lang,
            vad_filter=True,
            beam_size=5,
            temperature=0.0,
        )

        text = " ".join(seg.text.strip() for seg in segments)
        logger.info(f"STT file [{info.language}]: {text!r}")
        return text.strip(), info.language
