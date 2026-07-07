import logging
from duckduckgo_search import DDGS

logger = logging.getLogger("jarvis.skills.web_search")

def execute(query: str, max_results: int = 4) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "Nessun risultato trovato."
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            url = r.get("href", "")
            lines.append(f"[{i}] {title}\n    {body[:200]}\n    {url}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning(f"web_search fallita: {e}")
        return f"Ricerca web non disponibile: {e}"
