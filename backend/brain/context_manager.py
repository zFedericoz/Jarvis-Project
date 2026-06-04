"""
ContextManager — gestisce il contesto della conversazione.

Novità rispetto alla versione originale:
  - Inietta automaticamente le preferenze utente nel system prompt
  - Estrae e salva fatti sull'utente dai messaggi ("mi chiamo X", "la mia cartella è Y")
  - Integra risultati RAG come contesto aggiuntivo quando rilevante
"""

import re
import logging
from collections import deque

logger = logging.getLogger("jarvis.brain.context")

# Pattern per estrarre fatti espliciti dall'utente
_FACT_PATTERNS = [
    (r"mi chiamo\s+([A-Za-zÀ-ÿ\s]+)", "nome_utente"),
    (r"il mio nome[èe]\s+([A-Za-zÀ-ÿ\s]+)", "nome_utente"),
    (r"chiamami\s+([A-Za-zÀ-ÿ\s]+)", "nome_utente"),
    (r"lavoro (?:in|a|per)\s+(.+?)(?:\.|$)", "luogo_lavoro"),
    (r"la (?:mia )?cartella (?:principale|progetti?|lavoro)[eè è]+[\"']?([^\"\n']+)[\"']?", "cartella_progetti"),
    (r"uso (?:sempre )?([A-Za-z\s]+) come editor", "editor_preferito"),
    (r"il mio linguaggio preferito[eè è]+\s*([A-Za-z\+#]+)", "linguaggio_preferito"),
    (r"ricordati? (?:che )?(.+)", "nota_utente"),
]


class ContextManager:
    def __init__(self, max_turns: int = 20, persistent_memory=None):
        """
        Args:
            max_turns: numero massimo di turni nel contesto della sessione corrente
            persistent_memory: istanza di PersistentMemory (opzionale)
                               Se fornita, inietta preferenze nel prompt e salva fatti
        """
        self.history: deque[dict] = deque(maxlen=max_turns)
        self.current_language: str = "it"
        self._memory = persistent_memory

    # ──────────────────────────────────────────────
    # API base
    # ──────────────────────────────────────────────

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

        # Se è un messaggio utente, cerca fatti da salvare
        if role == "user" and self._memory:
            self._extract_and_save_facts(content)

        logger.debug(f"Context [{role}]: {content[:60]}")

    def get_context(self) -> list[dict]:
        return list(self.history)

    def clear(self):
        self.history.clear()
        logger.info("Contesto sessione azzerato")

    def set_language(self, lang: str):
        self.current_language = lang

    # ──────────────────────────────────────────────
    # Contesto arricchito con memoria persistente
    # ──────────────────────────────────────────────

    def get_user_context_injection(self) -> str:
        """
        Ritorna il blocco di testo da aggiungere al system prompt
        con le preferenze note sull'utente.
        """
        if not self._memory:
            return ""
        return self._memory.build_user_context_string()

    def get_rag_context(self, query: str, n_results: int = 3) -> str:
        """
        Cerca nella knowledge base RAG e ritorna i chunk rilevanti
        formattati come stringa da iniettare nel prompt.
        """
        if not self._memory:
            return ""

        results = self._memory.search_knowledge(query, n_results=n_results)
        if not results:
            return ""

        lines = ["# Documenti rilevanti dalla knowledge base"]
        for r in results:
            source = r["metadata"].get("source", "sconosciuto")
            lines.append(f"\n[Fonte: {source}]\n{r['text']}")

        logger.info(f"RAG: trovati {len(results)} chunk rilevanti per '{query[:50]}'")
        return "\n".join(lines)

    def save_preference(self, key: str, value):
        """Salva una preferenza utente nella memoria persistente."""
        if self._memory:
            self._memory.set_preference(key, value)

    def get_preference(self, key: str, default=None):
        if self._memory:
            return self._memory.get_preference(key, default)
        return default

    # ──────────────────────────────────────────────
    # Estrazione automatica di fatti dai messaggi
    # ──────────────────────────────────────────────

    def _extract_and_save_facts(self, text: str):
        """
        Analizza il messaggio utente e salva automaticamente
        fatti espliciti (nome, cartelle, preferenze, ecc.).
        """
        text_lower = text.lower()
        for pattern, key in _FACT_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip().rstrip(".,!?")
                if len(value) > 1:  # evita match vuoti o singola lettera
                    self._memory.set_preference(key, value)
                    logger.info(f"Fatto estratto automaticamente: {key} = '{value}'")
