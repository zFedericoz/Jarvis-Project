import logging
from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.vision")

class Vision(BaseAction):
    def __init__(self, config: dict):
        super().__init__(config)
        self._camera = None

    def _get_camera(self):
        if self._camera is None:
            try:
                from vision.camera import Camera
                vision_cfg = self.config.get("vision", {})
                self._camera = Camera(
                    model_path=vision_cfg.get("model", "yolov8n.pt"),
                    device=vision_cfg.get("device", "cpu"),
                    camera_id=vision_cfg.get("camera_id", 0),
                )
            except Exception as e:
                logger.error(f"Failed to initialize camera: {e}")
                return None
        return self._camera

    async def execute(self, command: str, **kwargs) -> str:
        camera = self._get_camera()
        if camera is None:
            return "Vision system is not available."
        try:
            result = camera.capture_and_analyze()
            return result
        except Exception as e:
            logger.error(f"Vision error: {e}")
            return "I encountered an error trying to use my vision."

    def can_handle(self, intent: str) -> bool:
        return intent == "vision"