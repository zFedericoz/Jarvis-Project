import logging

logger = logging.getLogger("jarvis.brain.rag_searcher")

_CHARS_PER_TOKEN = 4

# Shared RAG distance threshold (adjustable at runtime)
rag_distance_threshold: float = 1.0  # Più selettivo (distanza minore = più pertinente)


class RAGSearcher:
    def __init__(self, memory, distance_threshold=None, char_budget=6000):
        self._mem = memory
        self._distance_threshold = distance_threshold
        self._char_budget = char_budget

    def _effective_threshold(self) -> float:
        if self._distance_threshold is not None:
            return self._distance_threshold
        return rag_distance_threshold

    def search(self, query: str) -> str:
        """Search RAG knowledge base and return formatted context string"""
        if not self._mem:
            return ""
        count = self._mem.knowledge.count()
        if count == 0:
            return ""
        n_results = min(6, count)
        try:
            raw = self._mem.knowledge.query(
                query_texts=[query], n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"RAG query fallita: {e}")
            return ""
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        if not docs:
            return ""
        threshold = self._effective_threshold()
        relevant = [(d, m, dist) for d, m, dist in zip(docs, metas, distances) if dist <= threshold]
        if not relevant:
            return ""
        lines = ["# Documenti rilevanti dalla knowledge base"]
        total_chars = len(lines[0])
        for doc, meta, dist in relevant:
            source = meta.get("source", "sconosciuto")
            ci = meta.get("chunk_index", "?")
            h = f"\n[da: {source} \u00a7{ci}] (rilevanza: {1 - dist / 2:.0%})"
            entry = f"{h}\n{doc}"
            if total_chars + len(entry) > self._char_budget:
                break
            lines.append(entry)
            total_chars += len(entry)
        return "\n".join(lines)
