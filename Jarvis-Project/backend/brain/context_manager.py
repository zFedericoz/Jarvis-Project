from collections import deque
import logging

logger = logging.getLogger("jarvis.brain.context")

class ContextManager:
    def __init__(self, max_turns: int = 20):
        self.history: deque[dict] = deque(maxlen=max_turns)
        self.current_language: str = "it"

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        logger.debug(f"Context added [{role}]: {content[:50]}...")

    def get_context(self) -> list[dict]:
        return list(self.history)

    def clear(self):
        self.history.clear()
        logger.info("Context cleared")

    def set_language(self, lang: str):
        self.current_language = lang
