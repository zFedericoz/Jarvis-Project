from duckduckgo_search import DDGS
from .base_action import BaseAction
import logging

logger = logging.getLogger("jarvis.actions.web")

class WebSearch(BaseAction):
    async def execute(self, command: str, **kwargs) -> str:
        query = self._extract_query(command)
        if not query:
            return "What would you like me to search for?"

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            if not results:
                return f"I couldn't find anything about '{query}'."
            summary = "\n".join(
                f"• {r['title']}: {r['body'][:150]}"
                for r in results
            )
            return f"Here's what I found about '{query}':\n{summary}"
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"I encountered an error searching for '{query}'."

    def _extract_query(self, command: str) -> str:
        for prefix in ["cerca ", "search for ", "search ", "trova ", "chi è ", "che cos'è "]:
            if command.lower().startswith(prefix):
                return command[len(prefix):]
        adverbs = ["chi", "che", "dove", "quando", "come", "perché", "cosa",
                   "who", "what", "where", "when", "why", "how"]
        words = command.split()
        if any(words[0].lower().startswith(a) for a in adverbs):
            return command
        return command

    def can_handle(self, intent: str) -> bool:
        return intent == "web_search"
