"""
WebSearcher — ricerca web tramite DuckDuckGo.
"""

import logging
import re
from duckduckgo_search import DDGS

logger = logging.getLogger("jarvis.brain.web_searcher")


class WebSearcher:
    NEED_SEARCH_PATTERNS = [
        r"\b(notizie|ultime|news|breaking|aggiornament)\b",
        r"\b(meteo|tempo|che tempo|previsioni)\b",
        r"\b(classifica|risultato|punteggio|partita)\b",
        r"\b(prezzo|quanto costa|quanto costano)\b",
        r"\b(elezion|presidente|governo|ministro|politic)\b",
        r"\b(ultimo|ultima|recente|nuovo|nuova)\s+\w{3,}",
        r"\b(today|latest|current|now|breaking)\b",
    ]

    def __init__(self, max_results=4, char_budget=2400, patterns=None):
        self._max_results = max_results
        self._char_budget = char_budget
        self._patterns = patterns or self.NEED_SEARCH_PATTERNS

    def needs_search(self, message: str) -> bool:
        """Check if message likely needs web search"""
        return any(re.search(p, message.lower()) for p in self._patterns)

    def search(self, query: str) -> tuple[str, list[dict]]:
        """Search the web and return (text_results, sources)"""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self._max_results))
            if not results:
                return ("", [])
            lines = []
            sources = []
            total = 0
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                url = r.get("href", "")
                body = r.get("body", "")
                snippet = f"- [{i}] {title}: {body[:300]}"
                if total + len(snippet) > self._char_budget:
                    break
                lines.append(snippet)
                total += len(snippet)
                if url:
                    sources.append({"title": title or url, "url": url})
            return ("\n".join(lines), sources)
        except Exception as e:
            logger.warning(f"Web search fallita: {e}")
            return ("", [])
