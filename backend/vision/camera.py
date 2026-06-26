import cv2
import numpy as np
import logging
import threading
import time
from ultralytics import YOLO

logger = logging.getLogger("jarvis.vision")


class Camera:
    def __init__(self, model_path: str = "yolov8n.pt", device: str = "cuda", camera_id: int = 0):
        self.camera_id = camera_id
        self.device = device
        self.model = YOLO(model_path)
        self.cap = None
        # ── Continuous monitoring state ────────────────────────────────────
        self._monitor_thread: threading.Thread | None = None
        self._monitor_active = False
        self._last_objects: frozenset[str] = frozenset()
        # Lock per accesso concorrente a model e cap:
        # Il thread di monitoraggio continuo e una eventuale richiesta
        # on-demand (capture_and_analyze) potrebbero accedere a self.model
        # e self.cap contemporaneamente. YOLO inference (self.model(...))
        # e cv2.VideoCapture.read() non sono thread-safe.
        self._lock = threading.Lock()
        logger.info(f"Vision model loaded on {device}")

    def start(self):
        self.cap = cv2.VideoCapture(self.camera_id)

    # ──────────────────────────────────────────────────────────────────────
    # On-demand (invariato rispetto a prima, solo lock aggiunto)
    # ──────────────────────────────────────────────────────────────────────

    def capture_and_analyze(self) -> str:
        with self._lock:
            if self.cap is None:
                self.start()
            ret, frame = self.cap.read()
            if not ret:
                return "I cannot see anything."

            results = self.model(frame, device=self.device, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    label = self.model.names[cls_id]
                    conf = float(box.conf[0])
                    if conf > 0.5:
                        detections.append(f"{label} ({conf:.0%})")

            if not detections:
                return "I see nothing of significance."

            return f"I can see: {', '.join(set(detections))}."

    # ──────────────────────────────────────────────────────────────────────
    # Continuous monitoring (thread-safe, usa stesso lock di capture_and_analyze)
    # ──────────────────────────────────────────────────────────────────────

    def start_continuous_monitoring(self, callback, interval_seconds: int = 3):
        """Avvia un thread in background che analizza un frame ogni N secondi.

        Il callback viene invocato solo quando il set di oggetti rilevati
        cambia rispetto all'ultima rilevazione (apparizione/scomparsa).
        Firma attesa: callback(message: str)

        Thread-safe: usa self._lock per accesso a model e cap.
        """
        if self._monitor_active:
            logger.warning("Continuous monitoring already active")
            return

        self._monitor_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(callback, interval_seconds),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Continuous vision monitoring started")

    def stop_monitoring(self):
        """Arresta il monitoraggio continuo e rilascia la videocamera."""
        self._monitor_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        self._monitor_thread = None
        with self._lock:
            if self.cap:
                self.cap.release()
                self.cap = None
        logger.info("Continuous vision monitoring stopped")

    def _monitoring_loop(self, callback, interval: int):
        """Loop interno: cattura frame, analizza, rileva novità."""
        # Acquisisce la videocamera (thread-safe)
        with self._lock:
            if self.cap is None:
                try:
                    self.cap = cv2.VideoCapture(self.camera_id)
                except Exception as e:
                    logger.error("Camera init failed in monitoring: %s", e)
                    self._monitor_active = False
                    return

        while self._monitor_active:
            try:
                self._check_once(callback)
            except Exception as e:
                logger.warning("Monitoring check error: %s", e)

            for _ in range(interval * 10):
                if not self._monitor_active:
                    break
                time.sleep(0.1)

    def _check_once(self, callback):
        """Analizza un frame e chiama callback se cambia qualcosa."""
        with self._lock:
            if self.cap is None or not self.cap.isOpened():
                return
            ret, frame = self.cap.read()
            if not ret:
                return

            results = self.model(frame, device=self.device, verbose=False)

        # ── Estrai oggetti con confidenza > soglia ────────────────────────
        current_objects: set[str] = set()
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]
                conf = float(box.conf[0])
                if conf > 0.5:
                    current_objects.add(label)

        # ── Rileva novità rispetto all'ultimo ciclo ───────────────────────
        new_objs = current_objects - self._last_objects
        gone_objs = self._last_objects - current_objects

        if new_objs or gone_objs:
            self._last_objects = frozenset(current_objects)
            messages = []
            for obj in sorted(new_objs):
                messages.append(f"Ho notato un/una {obj} nel campo visivo.")
            for obj in sorted(gone_objs):
                messages.append(f"{obj.capitalize()} non è più nel mio campo visivo.")
            for msg in messages:
                try:
                    callback(msg)
                except Exception as e:
                    logger.warning("Monitor callback error: %s", e)

    # ──────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────

    def stop(self):
        self.stop_monitoring()
