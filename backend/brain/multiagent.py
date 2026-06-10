"""
MultiAgent — orchestratore delle risposte di J.A.R.V.I.S.  (versione potenziata)

Sostituisce integralmente backend/brain/multiagent.py

Miglioramenti rispetto alla versione originale:
  1. RAG sempre attivo con soglia di rilevanza (distance threshold) invece di
     pattern-matching fragile. Elimina il rischio di false negative.
  2. Context budget: tronca RAG e web results a un numero massimo di token
     stimato per non sforare il context_window di Qwen 2.5:14b (4096 token).
  3. Formato RAG migliorato: ogni chunk include nome sorgente e indice chunk
     così il modello può citare "[da: file.pdf §3]" con precisione.
  4. Web search condizionale più precisa: evita ricerche inutili per domande
     già coperte dal RAG o dalla memoria locale.
  5. Reflection abilitata di default (max_reflect_rounds=1) per intent
     "code" e "research" dove la qualità è prioritaria.
  6. Logging strutturato per diagnosticare facilmente cosa viene iniettato.
"""

import logging
import re
from duckduckgo_search import DDGS

logger = logging.getLogger("jarvis.brain.multiagent")

# ─── Mapping intent → categoria specialista ────────────────────────────────
INTENT_TO_SPECIALIST = {
    "system_control": "action",
    "web_search":     "research",
    "media_player":   "action",
    "productivity":   "action",
    "vision":         "action",
    "greeting":       "general",
    "chat":           "general",
    "code":           "code",
    "creative":       "creative",
    "research":       "research",
    "action":         "action",
    "general":        "general",
    "git":            "code",
    "terminal":       "action",
    "rpa":            "action",
}

# ─── Prompt specialisti (italiano) ─────────────────────────────────────────
SPECIALIST_PROMPTS_IT = {
    "code": """
Sei uno specialista di codice. Regole:
- Codice completo e funzionante, zero placeholder o commenti TODO.
- Type hints e docstring PEP 257 sempre presenti.
- Spiega le decisioni di design in 1-2 frasi dopo il blocco codice.
- Includi sempre un esempio d'uso.
- Language tag corretto in tutti i code block.
""",
    "creative": """
Sei uno scrittore creativo. Regole:
- Descrizioni vivide e coinvolgenti.
- Usa metafore e analogie quando appropriate.
- Stile narrativo naturale e fluido.
- Evita il gergo tecnico se non richiesto.
""",
    "research": """
Sei un analista di ricerca. Regole:
- Struttura le risposte in sezioni chiare quando necessario.
- Distingui tra fatti verificati e speculazioni informate.
- Includi dati o statistiche rilevanti quando disponibili.
- Se citi fonti dalla knowledge base, usa la notazione [da: nome_file].
""",
    "action": """
Sei un esecutore di azioni. Regole:
- Conferma l'azione eseguita in una sola frase.
- Fornisci il risultato o lo stato dell'azione.
- Se l'azione fallisce, spiega perché e offri alternative.
- Sii minimale: niente preamboli.
""",
    "general": """
Sei un assistente generale. Regole:
- Sii utile e informativo.
- Adotta il tono dell'utente, ma mantieni professionalità.
- Fai domande di chiarimento solo se strettamente necessario.
- Fornisci esempi concreti quando spieghi concetti astratti.
""",
}

# ─── Prompt specialisti (inglese) ──────────────────────────────────────────
SPECIALIST_PROMPTS_EN = {
    "code": """
You are a code specialist. Rules:
- Complete, working code. No placeholder comments or TODOs.
- Always include type hints and PEP 257 docstrings.
- Explain key design decisions in 1-2 sentences after the code block.
- Always include a usage example.
- Use the correct language tag in all code blocks.
""",
    "creative": """
You are a creative writer. Rules:
- Vivid and engaging descriptions.
- Use metaphors and analogies when appropriate.
- Natural, flowing narrative style.
- Avoid technical jargon unless requested.
""",
    "research": """
You are a research analyst. Rules:
- Structure answers with clear sections when appropriate.
- Distinguish between verified facts and informed speculation.
- Include relevant data points or statistics when available.
- When citing knowledge-base sources, use the [from: filename] notation.
""",
    "action": """
You are an action executor. Rules:
- Confirm the action taken in a single sentence.
- Provide the result or status of the action.
- If the action failed, explain why and offer alternatives.
- No preambles.
""",
    "general": """
You are a general assistant. Rules:
- Be helpful and informative.
- Match the user's tone while keeping professionalism.
- Ask clarifying questions only when strictly necessary.
- Provide concrete examples when explaining abstract concepts.
""",
}

# ─── Pattern per web search ─────────────────────────────────────────────────
NEED_SEARCH_PATTERNS = [
    r"\b(notizie|ultime|news|breaking|aggiornament)\b",
    r"\b(meteo|tempo|che tempo|previsioni)\b",
    r"\b(classifica|risultato|punteggio|partita)\b",
    r"\b(prezzo|quanto costa|quanto costano)\b",
    r"\b(elezion|presidente|governo|ministro|politic)\b",
    r"\b(ultimo|ultima|recente|nuovo|nuova)\s+\w{3,}",
    r"\b(today|latest|current|now|breaking)\b",
]

# ─── Costanti per il budget del contesto ───────────────────────────────────
# Stima conservativa: 1 token ≈ 4 caratteri.
# Context window Qwen 2.5:14b = 4096 token → ~16 384 caratteri.
# Riserviamo ~2500 token per system prompt + risposta → budget extra ~1500 token.
_CHARS_PER_TOKEN = 4
_RAG_TOKEN_BUDGET = 1200     # token massimi da dedicare al RAG
_WEB_TOKEN_BUDGET = 600      # token massimi per i risultati web
_RAG_CHAR_BUDGET  = _RAG_TOKEN_BUDGET * _CHARS_PER_TOKEN
_WEB_CHAR_BUDGET  = _WEB_TOKEN_BUDGET * _CHARS_PER_TOKEN

# Soglia di distanza ChromaDB sotto la quale un chunk è considerato rilevante.
# ChromaDB usa distanza coseno: 0.0 = identico, 2.0 = opposto.
# Valori < 1.2 sono generalmente buoni; abbassa a 0.9 per maggiore precisione.
_RAG_DISTANCE_THRESHOLD = 1.2

# Intent che beneficiano della reflection (qualità > velocità)
_REFLECTION_INTENTS = {"code", "research", "creative"}


class MultiAgent:
    def __init__(self, llm_client, persistent_memory=None):
        """
        Args:
            llm_client:        istanza LLMClient
            persistent_memory: istanza PersistentMemory (opzionale)
        """
        self.llm  = llm_client
        self._mem = persistent_memory
        self._last_sources: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Mapping e selezione specialista
    # ──────────────────────────────────────────────────────────────────────────

    def _map_intent(self, intent: str) -> str:
        return INTENT_TO_SPECIALIST.get(intent, "general")

    def _specialist_prompt(self, category: str, language: str = "it") -> str:
        prompts = SPECIALIST_PROMPTS_IT if language == "it" else SPECIALIST_PROMPTS_EN
        return prompts.get(category, prompts["general"])

    # ──────────────────────────────────────────────────────────────────────────
    # RAG: ricerca nella knowledge base con soglia di rilevanza
    # ──────────────────────────────────────────────────────────────────────────

    def _search_rag(self, query: str) -> str:
        """
        Cerca nella knowledge base.
        Filtra i chunk con distanza coseno > _RAG_DISTANCE_THRESHOLD per
        evitare di iniettare contenuto non pertinente nel prompt.
        Tronca il risultato al budget di caratteri configurato.
        """
        if not self._mem:
            return ""

        count = self._mem.knowledge.count()
        if count == 0:
            return ""

        n_results = min(6, count)  # recupera più chunk, poi filtra
        try:
            raw = self._mem.knowledge.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"RAG query fallita: {e}")
            return ""

        docs      = raw.get("documents",  [[]])[0]
        metas     = raw.get("metadatas",  [[]])[0]
        distances = raw.get("distances",  [[]])[0]

        if not docs:
            return ""

        # Filtra per rilevanza
        relevant = [
            (doc, meta, dist)
            for doc, meta, dist in zip(docs, metas, distances)
            if dist <= _RAG_DISTANCE_THRESHOLD
        ]

        if not relevant:
            logger.info(f"RAG: nessun chunk rilevante (threshold={_RAG_DISTANCE_THRESHOLD}) per '{query[:60]}'")
            return ""

        logger.info(f"RAG: {len(relevant)}/{n_results} chunk rilevanti per '{query[:60]}'")

        # Formatta con fonte e indice chunk per facilitare la citazione
        lines = ["# Documenti rilevanti dalla knowledge base"]
        total_chars = len(lines[0])

        for doc, meta, dist in relevant:
            source      = meta.get("source", "sconosciuto")
            chunk_index = meta.get("chunk_index", "?")
            header      = f"\n[da: {source} §{chunk_index}] (rilevanza: {1 - dist / 2:.0%})"
            entry       = f"{header}\n{doc}"

            if total_chars + len(entry) > _RAG_CHAR_BUDGET:
                logger.info("RAG: budget caratteri raggiunto, chunk successivi scartati")
                break

            lines.append(entry)
            total_chars += len(entry)

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────────────────
    # Web search
    # ──────────────────────────────────────────────────────────────────────────

    def _needs_web_search(self, message: str) -> bool:
        return any(re.search(p, message.lower()) for p in NEED_SEARCH_PATTERNS)

    def _search_web(self, query: str, max_results: int = 4):
        """Esegue una ricerca DuckDuckGo.
        Returns:
            (text_for_llm, sources_list) — sources_list è una lista di dict con 'title' e 'url'.
        """
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
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
                if total + len(snippet) > _WEB_CHAR_BUDGET:
                    break
                lines.append(snippet)
                total += len(snippet)
                if url:
                    sources.append({"title": title or url, "url": url})

            return ("\n".join(lines), sources)
        except Exception as e:
            logger.warning(f"Web search fallita: {e}")
            return ("", [])

    # ──────────────────────────────────────────────────────────────────────────
    # Contesto utente da memoria persistente
    # ──────────────────────────────────────────────────────────────────────────

    def _user_context(self) -> str:
        if not self._mem:
            return ""
        ctx = self._mem.build_user_context_string()
        return ctx

    # ──────────────────────────────────────────────────────────────────────────
    # Entry point principale
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def last_sources(self) -> list[dict]:
        return self._last_sources

    def chat(
        self,
        message: str,
        context: list[dict] | None = None,
        language: str = "it",
        intent: str = "general",
        search_query: str | None = None,
    ) -> str:
        self._last_sources = []
        return "".join(self._chat_stream_impl(message, context, language, intent, search_query, use_reflection=intent in _REFLECTION_INTENTS))

    def chat_stream(self, message: str, context: list[dict] | None = None,
                    language: str = "it", intent: str = "general",
                    search_query: str | None = None):
        self._last_sources = []
        yield from self._chat_stream_impl(message, context, language, intent, search_query, use_reflection=False)

    def _chat_stream_impl(self, message: str, context: list[dict] | None = None,
                          language: str = "it", intent: str = "general",
                          search_query: str | None = None,
                          use_reflection: bool = False):
        category   = self._map_intent(intent)
        specialist = self._specialist_prompt(category, language)
        query      = search_query or message
        extra_parts: list[str] = []

        # 1. Contesto utente (preferenze persistenti)
        user_ctx = self._user_context()
        if user_ctx:
            extra_parts.append(user_ctx)

        # 2. RAG — sempre attivo, filtrato per rilevanza
        rag_ctx = self._search_rag(query)
        if rag_ctx:
            extra_parts.append(rag_ctx)

        # 3. Web search
        rag_already_covers = bool(rag_ctx)
        if self._needs_web_search(query) and not rag_already_covers:
            logger.info(f"Web search attivata per: {query[:80]}")
            web_results = self._search_web(query)
            if web_results[0]:
                extra_parts.append(
                    "Risultati web (usa solo se pertinenti, ignora altrimenti):\n"
                    + web_results[0]
                )
                self._last_sources = web_results[1]
            else:
                self._last_sources = []

        full_specialist = specialist
        if extra_parts:
            full_specialist = specialist + "\n\n" + "\n\n".join(extra_parts)

        if use_reflection:
            yield self.llm.chat_with_reflection(
                message, context, language,
                extra_system_prompt=full_specialist,
                min_score=7, max_reflect_rounds=1,
            )
        else:
            yield from self.llm.chat_stream(
                message, context, language,
                extra_system_prompt=full_specialist,
            )
