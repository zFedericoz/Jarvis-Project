import logging
import re
from duckduckgo_search import DDGS

logger = logging.getLogger("jarvis.brain.multiagent")

INTENT_TO_SPECIALIST = {
    "system_control": "action",
    "web_search": "research",
    "media_player": "action",
    "productivity": "action",
    "vision": "action",
    "greeting": "general",
    "chat": "general",
    "code": "code",
    "creative": "creative",
    "research": "research",
    "action": "action",
    "general": "general",
}

SPECIALIST_PROMPTS = {
    "code": """
You are a code specialist. Follow these rules:
- Provide complete, working code with no placeholder comments
- Include type hints and docstrings (PEP 257)
- Explain the key design decisions in 1-2 sentences
- Always include a usage example
- Format code blocks with the correct language tag
""",
    "creative": """
You are a creative writer. Follow these rules:
- Be vivid and engaging in your descriptions
- Use metaphors and analogies when appropriate
- Keep a natural, flowing narrative style
- Avoid technical jargon unless requested
""",
    "research": """
You are a research analyst. Follow these rules:
- Structure answers with clear sections when appropriate
- Cite sources or explain reasoning
- Distinguish between facts and informed speculation
- Include relevant data points or statistics
- Suggest follow-up questions for deeper exploration
""",
    "action": """
You are an action executor. Follow these rules:
- Confirm the action taken in one brief sentence
- Provide the result or status of the action
- If the action failed, explain why and offer alternatives
- Keep it minimal
""",
    "general": """
You are a general assistant. Follow these rules:
- Be helpful and informative
- Match the user's tone
- If unsure, ask clarifying questions
- Provide examples when explaining concepts
""",
}

SPECIALIST_PROMPTS_IT = {
    "code": """
Sei uno specialista di codice. Segui queste regole:
- Fornisci codice completo e funzionante, senza commenti placeholder
- Includi type hints e docstring (PEP 257)
- Spiega le decisioni di design in 1-2 frasi
- Includi sempre un esempio d'uso
- Formatta i blocchi di codice con il language tag corretto
""",
    "creative": """
Sei uno scrittore creativo. Segui queste regole:
- Sii vivido e coinvolgente nelle descrizioni
- Usa metafore e analogie quando appropriate
- Mantieni uno stile narrativo naturale e fluido
- Evita il gergo tecnico se non richiesto
""",
    "research": """
Sei un analista di ricerca. Segui queste regole:
- Struttura le risposte in sezioni chiare quando necessario
- Cita le fonti o spiega il ragionamento
- Distingui tra fatti e speculazioni informate
- Includi dati o statistiche rilevanti
- Suggerisci domande di approfondimento
""",
    "action": """
Sei un esecutore di azioni. Segui queste regole:
- Conferma l'azione eseguita in una frase breve
- Fornisci il risultato o lo stato dell'azione
- Se l'azione fallisce, spiega perché e offri alternative
- Sii minimale
""",
    "general": """
Sei un assistente generale. Segui queste regole:
- Sii utile e informativo
- Adotta il tono dell'utente
- Se non sei sicuro, fai domande di chiarimento
- Fornisci esempi quando spieghi concetti
""",
}

NEED_SEARCH_PATTERNS = [
    r"\b(notizie|ultime|news|breaking|aggiornament)\b",
    r"\b(meteo|tempo|che tempo|previsioni)\b",
    r"\b(classifica|risultato|punteggio|partita)\b",
    r"\b(cos.è|chi è|che cos.è|che cosa.sono)\b",
    r"\b(prezzo|quanto costa|quanto costano)\b",
    r"\b(elezion|presidente|governo|ministro|politic)\b",
    r"\b(ultimo|ultima|recente|nuovo|nuova)\s+\w{2,}",
]

class MultiAgent:
    def __init__(self, llm_client):
        self.llm = llm_client

    def _map_intent(self, intent: str) -> str:
        return INTENT_TO_SPECIALIST.get(intent, "general")

    def _specialist_prompt(self, category: str, language: str = "it") -> str:
        prompts = SPECIALIST_PROMPTS_IT if language == "it" else SPECIALIST_PROMPTS
        return prompts.get(category, prompts["general"])

    def _needs_web_search(self, message: str) -> bool:
        return any(re.search(p, message.lower()) for p in NEED_SEARCH_PATTERNS)

    def _search_web(self, query: str, max_results: int = 3) -> str:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return ""
            lines = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                lines.append(f"- {title}: {body[:200]}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return ""

    def chat(self, message: str, context: list[dict] | None = None,
             language: str = "it", intent: str = "general", search_query: str | None = None) -> str:
        category = self._map_intent(intent)
        specialist = self._specialist_prompt(category, language)

        extra_context = ""
        query = search_query or message
        if self._needs_web_search(query):
            logger.info(f"Auto web search triggered for: {query[:80]}")
            results = self._search_web(query)
            if results:
                extra_context = f"\n\nWeb search results:\n{results}\n\nUse these results to answer accurately. If they are not relevant, ignore them."
                logger.info(f"Web search returned {len(results)} chars of results")

        full_specialist = specialist + extra_context if extra_context else specialist

        return self.llm.chat_with_reflection(
            message, context, language,
            extra_system_prompt=full_specialist,
            min_score=7, max_reflect_rounds=0,
        )
