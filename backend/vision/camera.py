import cv2
import numpy as np
import logging
from ultralytics import YOLO

logger = logging.getLogger("jarvis.vision")

class Camera:
    def __init__(self, model_path: str = "yolov8n.pt", device: str = "cuda", camera_id: int = 0):
        self.camera_id = camera_id
        self.device = device
        self.model = YOLO(model_path)
        self.cap = None
        logger.info(f"Vision model loaded on {device}")

    def start(self):
        self.cap = cv2.VideoCapture(self.camera_id)

    def capture_and_analyze(self) -> str:
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

    def stop(self):
        if self.cap:
            self.cap.release()
