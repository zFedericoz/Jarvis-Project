from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("jarvis.actions")

class BaseAction(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.name = self.__class__.__name__.lower()

    @abstractmethod
    async def execute(self, command: str, **kwargs) -> str:
        pass

    def can_handle(self, intent: str) -> bool:
        return intent == self.name
