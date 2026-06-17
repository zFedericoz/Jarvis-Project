"""
MultiAgent — orchestratore delle risposte di J.A.R.V.I.S.
Versione con agentic loop ReAct (Thought → Action → Observation → Repeat → Final).

Nuove feature:
  1. Tool calling via skill dinamiche (skills/ registry)
  2. ReAct loop multi-step (max_rounds=5)
  3. Cache semantica per query simili (con TTL + LRU eviction)
  4. Context summarization per chat lunghe (>4000 caratteri di cronologia)
  5. RAG + Web search + User context preserved
"""

import logging, re, json, hashlib
from duckduckgo_search import DDGS
from brain.semantic_cache import SemanticCache

logger = logging.getLogger("jarvis.brain.multiagent")

INTENT_TO_SPECIALIST = {
    "system_control": "action", "web_search": "research", "media_player": "action",
    "productivity": "action", "vision": "action", "greeting": "general",
    "chat": "general", "code": "code", "creative": "creative",
    "research": "research", "action": "action", "general": "general",
    "git": "code", "terminal": "action", "rpa": "action",
}

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

NEED_SEARCH_PATTERNS = [
    r"\b(notizie|ultime|news|breaking|aggiornament)\b",
    r"\b(meteo|tempo|che tempo|previsioni)\b",
    r"\b(classifica|risultato|punteggio|partita)\b",
    r"\b(prezzo|quanto costa|quanto costano)\b",
    r"\b(elezion|presidente|governo|ministro|politic)\b",
    r"\b(ultimo|ultima|recente|nuovo|nuova)\s+\w{3,}",
    r"\b(today|latest|current|now|breaking)\b",
]

_CHARS_PER_TOKEN = 4
_RAG_TOKEN_BUDGET = 1200
_WEB_TOKEN_BUDGET = 600
_RAG_CHAR_BUDGET = _RAG_TOKEN_BUDGET * _CHARS_PER_TOKEN
_WEB_CHAR_BUDGET = _WEB_TOKEN_BUDGET * _CHARS_PER_TOKEN
_RAG_DISTANCE_THRESHOLD = 1.2
_REFLECTION_INTENTS = {"code", "research", "creative"}

_SUMMARY_THRESHOLD = 4000

_semantic_cache = SemanticCache(max_entries=500, ttl_seconds=3600)


def _toolcall_to_dict(tc) -> dict:
    if isinstance(tc, dict):
        return tc
    if hasattr(tc, "function"):
        fn = tc.function
        if hasattr(fn, "name"):
            name = fn.name
        elif hasattr(fn, "get"):
            name = fn.get("name", "")
        else:
            name = str(fn)
        raw_args = getattr(fn, "arguments", {})
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse tool arguments: {raw_args[:100]}... - {e}")
                raw_args = {}
        elif hasattr(raw_args, "model_dump"):
            raw_args = raw_args.model_dump()
        elif hasattr(raw_args, "dict"):
            raw_args = raw_args.dict()
        return {"function": {"name": name, "arguments": raw_args}}
    return {"function": {"name": tc.get("function", {}).get("name", str(tc)), "arguments": {}}}


class MultiAgent:
    def __init__(self, llm_client, persistent_memory=None, skills_registry=None):
        self.llm = llm_client
        self._mem = persistent_memory
        self._skills = skills_registry
        self._last_sources: list[dict] = []
        self._max_react_rounds = 5

    def _map_intent(self, intent: str) -> str:
        return INTENT_TO_SPECIALIST.get(intent, "general")

    def _specialist_prompt(self, category: str, language: str = "it") -> str:
        prompts = SPECIALIST_PROMPTS_IT if language == "it" else SPECIALIST_PROMPTS_EN
        return prompts.get(category, prompts["general"])

    def _react_system_prompt(self, language: str = "it") -> str:
        if language == "it":
            return (
                "Hai a disposizione degli strumenti (tools) che puoi chiamare per ottenere informazioni o eseguire azioni.\n\n"
                "REGOLA FONDAMENTALE: Chiama un tool SOLO SE strettamente necessario. "
                "Per domande semplici (saluti, opinione, definizioni, spiegazioni), rispondi direttamente senza usare tools.\n\n"
                "Quando usi un tool:\n"
                "1. Thought: ragiona brevemente su cosa serve fare\n"
                "2. Action: chiama il tool con i parametri corretti\n"
                "3. Observation: arriverà il risultato del tool\n"
                "4. Ripeti se necessario, poi dai la risposta finale\n\n"
                "Non chiamare mai lo stesso tool due volte con la stessa richiesta.\n"
                "Se un tool restituisce un errore, prova un approccio alternativo o informa l'utente.\n"
                "Non inventare risultati di tool mai chiamati."
            )
        return (
            "You have access to tools you can call to get information or perform actions.\n\n"
            "RULE: Only call a tool when strictly necessary. "
            "For simple questions (greetings, opinions, definitions, explanations), answer directly without tools.\n\n"
            "When using a tool:\n"
            "1. Thought: reason briefly about what is needed\n"
            "2. Action: call the tool with correct parameters\n"
            "3. Observation: the tool result will arrive\n"
            "4. Repeat if needed, then give the final answer\n\n"
            "Never call the same tool twice with the same request.\n"
            "If a tool returns an error, try an alternative or inform the user.\n"
            "Do not invent tool results for tools you never called."
        )

    def _semantic_cache_key(self, query: str, language: str, intent: str) -> str:
        return hashlib.md5(f"{query}|{language}|{intent}".encode()).hexdigest()

    def _check_cache(self, query: str, language: str, intent: str) -> str | None:
        key = self._semantic_cache_key(query, language, intent)
        hit = _semantic_cache.get(key)
        if hit:
            logger.info(f"Cache HIT per: {query[:60]}")
            return hit
        return None

    def _store_cache(self, query: str, language: str, intent: str, response: str):
        key = self._semantic_cache_key(query, language, intent)
        _semantic_cache.set(key, response)

    def _maybe_summarize_context(self, context: list[dict] | None) -> list[dict] | str | None:
        if not context:
            return context
        total_chars = sum(len(m.get("content", "")) for m in context)
        if total_chars <= _SUMMARY_THRESHOLD:
            return context
        texts = [f"{m['role']}: {m['content'][:500]}" for m in context[-10:]]
        return "\n".join(texts)

    def _search_rag(self, query: str) -> str:
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
        relevant = [(d, m, dist) for d, m, dist in zip(docs, metas, distances) if dist <= _RAG_DISTANCE_THRESHOLD]
        if not relevant:
            return ""
        lines = ["# Documenti rilevanti dalla knowledge base"]
        total_chars = len(lines[0])
        for doc, meta, dist in relevant:
            source = meta.get("source", "sconosciuto")
            ci = meta.get("chunk_index", "?")
            h = f"\n[da: {source} §{ci}] (rilevanza: {1 - dist / 2:.0%})"
            entry = f"{h}\n{doc}"
            if total_chars + len(entry) > _RAG_CHAR_BUDGET:
                break
            lines.append(entry)
            total_chars += len(entry)
        return "\n".join(lines)

    def _needs_web_search(self, message: str) -> bool:
        return any(re.search(p, message.lower()) for p in NEED_SEARCH_PATTERNS)

    def _search_web(self, query: str, max_results: int = 4):
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

    def _user_context(self) -> str:
        if not self._mem:
            return ""
        return self._mem.build_user_context_string()

    @property
    def last_sources(self) -> list[dict]:
        return self._last_sources

    def chat(self, message: str, context: list[dict] | None = None,
             language: str = "it", intent: str = "general",
             search_query: str | None = None) -> str:
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
        cache_hit = self._check_cache(message, language, intent)
        if cache_hit:
            yield cache_hit
            return

        category = self._map_intent(intent)
        specialist = self._specialist_prompt(category, language)
        query = search_query or message
        extra_parts = []

        user_ctx = self._user_context()
        if user_ctx:
            extra_parts.append(user_ctx)

        rag_ctx = self._search_rag(query)
        if rag_ctx:
            extra_parts.append(rag_ctx)

        rag_already_covers = bool(rag_ctx)
        if self._needs_web_search(query) and not rag_already_covers:
            logger.info(f"Web search attivata per: {query[:80]}")
            web_results = self._search_web(query)
            if web_results[0]:
                extra_parts.append("Risultati web (usa solo se pertinenti, ignora altrimenti):\n" + web_results[0])
                self._last_sources = web_results[1]
            else:
                self._last_sources = []

        tools = None
        if self._skills:
            react_sys = self._react_system_prompt(language)
            tools = self._skills.get_ollama_tools()

        full_specialist = specialist
        if extra_parts:
            full_specialist = specialist + "\n\n" + "\n\n".join(extra_parts)

        if tools:
            full_specialist = react_sys + "\n\n" + full_specialist

        context_for_llm = self._maybe_summarize_context(context)
        if isinstance(context_for_llm, str):
            full_specialist += "\n\n# Riassunto cronologia chat\n" + context_for_llm
            context_for_llm = None

        if tools:
            yield from self._react_loop(message, context_for_llm, language, full_specialist, tools)
            return

        if use_reflection:
            result = self.llm.chat_with_reflection(message, context_for_llm, language, extra_system_prompt=full_specialist, min_score=7, max_reflect_rounds=1)
            self._store_cache(message, language, intent, result)
            yield result
        else:
            result_chars = []
            for kind, data in self.llm.chat_stream(message, context_for_llm, language, extra_system_prompt=full_specialist):
                if kind == "token":
                    result_chars.append(data)
                    yield data
            final = "".join(result_chars)
            self._store_cache(message, language, intent, final)

    def _react_loop(self, message: str, context: list[dict] | None,
                    language: str, system_prompt: str, tools: list[dict]):
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})

        all_tool_calls_ever = set()

        for round_idx in range(self._max_react_rounds):
            stream = self.llm.client.chat(
                model=self.llm.model,
                messages=messages,
                tools=tools,
                options=self.llm._options(),
                keep_alive=-1,
                stream=True,
            )

            text_buffer = []
            tool_calls_batch = []

            for chunk in stream:
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                tc = msg.get("tool_calls", None)
                if content:
                    text_buffer.append(content)
                if tc:
                    for call in tc:
                        call_dict = _toolcall_to_dict(call)
                        tc_key = json.dumps(call_dict, sort_keys=True)
                        if tc_key not in all_tool_calls_ever:
                            all_tool_calls_ever.add(tc_key)
                            tool_calls_batch.append(call)

            assistant_text = "".join(text_buffer)

            if tool_calls_batch:
                tool_calls_dicts = [_toolcall_to_dict(tc) for tc in tool_calls_batch]
                assistant_msg = {"role": "assistant", "content": assistant_text, "tool_calls": tool_calls_dicts}
                messages.append(assistant_msg)

                for tc in tool_calls_batch:
                    tc_dict = _toolcall_to_dict(tc)
                    fn = tc_dict.get("function", tc_dict) if isinstance(tc_dict, dict) else {}
                    name = fn.get("name", "")
                    args_raw = fn.get("arguments", {})
                    if isinstance(args_raw, str):
                        try:
                            args_raw = json.loads(args_raw)
                        except json.JSONDecodeError:
                            args_raw = {}
                    logger.info(f"ReAct round {round_idx + 1}: chiamata tool '{name}' con {args_raw}")
                    if assistant_text:
                        yield assistant_text
                        assistant_text = ""
                    result = self._skills.execute(name, **args_raw) if self._skills else f"Skills non disponibili"
                    logger.info(f"ReAct round {round_idx + 1}: tool '{name}' -> {result[:100]}...")
                    messages.append({"role": "tool", "content": result})
            else:
                if assistant_text:
                    yield assistant_text
                return

        messages.append({"role": "user", "content": "Fornisci la risposta finale basata sulle osservazioni raccolte. Sii conciso."})
        stream = self.llm.client.chat(
            model=self.llm.model, messages=messages,
            options=self.llm._options(), keep_alive=-1, stream=True,
        )
        for chunk in stream:
            c = chunk.get("message", {}).get("content", "")
            if c:
                yield c
