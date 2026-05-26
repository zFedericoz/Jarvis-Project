import re
import logging

logger = logging.getLogger("jarvis.brain.intent")

INTENTS = [
    ("greeting", [
        r"\bciao\b", r"\bhey\b", r"\bsalve\b", r"\bhello\b", r"\bhi\b",
        r"\bbuongiorno\b", r"\bbuonasera\b", r"\bgood morning\b",
    ]),
    ("productivity", [
        r"\btimer\b", r"\bpromemoria\b", r"\bricorda\b", r"\ballarme\b",
        r"\btimer\b", r"\bremind\b", r"\breminder\b", r"\balarm\b",
    ]),
    ("system_control", [
        r"\b(volume|spegn[i]|riavvia|blocca|schermo|processo|task|wifi|bluetooth)\b",
        r"\b(shutdown|restart|lock|screen|process|task|wifi|bluetooth|volume)\b",
    ]),
    ("media_player", [
        r"\b(musica|canzone|play|pausa|stop|skippa|volume|riproduci|spotify)\b",
        r"\b(music|song|play|pause|stop|skip|volume|spotify)\b",
    ]),
    ("vision", [
        r"\b(guarda|vedi|riconosce|cosa vedi)\b",
        r"\b(look|see|recognize|what do you see|camera)\b",
    ]),
    ("web_search", [
        r"\bcerca\b", r"\bsearch\b", r"\btrova\b", r"\bfind\b",
        r"\b(chi|che cos|dove|quando|come|perché)\s",
        r"\b(who|what|where|when|why|how)\s",
    ]),
]

class IntentRouter:
    def route(self, text: str) -> str:
        text_lower = text.lower()
        for intent, patterns in INTENTS:
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    logger.debug(f"Routing '{text}' -> {intent}")
                    return intent
        logger.debug(f"Routing '{text}' -> chat")
        return "chat"
