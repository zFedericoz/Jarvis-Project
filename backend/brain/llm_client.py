import yaml
import ollama
import logging

logger = logging.getLogger("jarvis.brain.llm")

class LLMClient:
    def __init__(self, config: dict | None = None):
        if config is None:
            with open("config/settings.yaml") as f:
                config = yaml.safe_load(f)
        llm_cfg = config["llm"]

        self.model = llm_cfg["model"]
        self.reflection_model = llm_cfg.get("reflection_model", self.model)
        self.embed_model = llm_cfg["embedding_model"]
        self.temperature = llm_cfg["temperature"]
        self.num_gpu = llm_cfg.get("num_gpu", -1)

        with open("config/persona.yaml") as f:
            persona = yaml.safe_load(f)
        self.system_prompt = persona["system_prompt"]

        host = llm_cfg["host"]
        self.client = ollama.Client(host=host)
        gpu_label = self.num_gpu if self.num_gpu > 0 else "auto"
        logger.info(f"LLM initialized: {self.model} @ {host} (GPU={gpu_label})")

    def warmup(self):
        self.client.chat(model=self.model, messages=[{"role": "user", "content": ""}], keep_alive=-1)
        logger.info("LLM model warmed up (keep_alive=-1)")

    def _options(self, **overrides) -> dict:
        opts = {"temperature": self.temperature}
        if self.num_gpu > 0:
            opts["num_gpu"] = self.num_gpu
        opts.update(overrides)
        return opts

    def chat(self, message: str, context: list[dict] | None = None, language: str = "it",
             extra_system_prompt: str = "") -> str:
        messages = self._build_messages(message, context, language, extra_system_prompt)
        resp = self.client.chat(
            model=self.model,
            messages=messages,
            options=self._options(),
            keep_alive=-1,
        )
        return resp["message"]["content"]

    def chat_with_reflection(self, message: str, context: list[dict] | None = None, language: str = "it",
                              extra_system_prompt: str = "",
                              min_score: int = 7, max_reflect_rounds: int = 1) -> str:
        response = self.chat(message, context, language, extra_system_prompt)

        for _ in range(max_reflect_rounds):
            score = self._rate_response(message, response, language)
            logger.info(f"Reflection score: {score}/10")
            if score >= min_score:
                break
            response = self._improve_response(message, response, context, language, score)

        return response

    def _build_messages(self, message: str, context: list[dict] | None = None,
                        language: str = "it", extra_system_prompt: str = "") -> list[dict]:
        lang_instruct = f"\n\nIMPORTANTE: Rispondi esclusivamente in {self._lang_name(language)}. Non mescolare lingue. Non tradurre la risposta in altre lingue."
        system_content = self.system_prompt + lang_instruct
        if extra_system_prompt:
            system_content += "\n\n" + extra_system_prompt
        messages = [{"role": "system", "content": system_content}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})
        return messages

    def _rate_response(self, user_message: str, response: str, language: str) -> int:
        lang_name = self._lang_name(language)
        prompt = (
            f"Valuta la seguente risposta da 1 a 10 in base a:\n"
            f"1. Lingua: deve essere ESCLUSIVAMENTE in {lang_name}. Se mescola lingue o è in altra lingua, assegna 0.\n"
            f"2. Pertinenza: risponde direttamente alla domanda dell'utente?\n"
            f"3. Concisione: è breve e va al punto?\n"
            f"4. Tono: è professionale e calmo?\n\n"
            f"Messaggio utente: {user_message}\n\n"
            f"Risposta assistente: {response}\n\n"
            f"Rispondi SOLO con un numero da 0 a 10."
        )
        try:
            resp = self.client.chat(
                model=self.reflection_model,
                messages=[{"role": "system", "content": "Sei un valutatore di qualità severo. Rispondi solo con un numero."},
                          {"role": "user", "content": prompt}],
                options=self._options(temperature=0),
                keep_alive=-1,
            )
            score_text = resp["message"]["content"].strip()
            score = int(''.join(c for c in score_text if c.isdigit()) or "5")
            return max(0, min(10, score))
        except Exception as e:
            logger.warning(f"Reflection scoring failed: {e}")
            return 10

    def _improve_response(self, user_message: str, previous_response: str,
                          context: list[dict] | None, language: str, score: int) -> str:
        lang_name = self._lang_name(language)
        prompt = (
            f"La risposta precedente ha ottenuto {score}/10. Migliorala.\n\n"
            f"Utente: {user_message}\n"
            f"Risposta precedente: {previous_response}\n\n"
            f"Problemi da correggere: sii più concisa, assicurati che sia in {lang_name}, "
            f"e rispondi direttamente alla domanda dell'utente."
        )
        messages = self._build_messages(prompt, context, language)
        resp = self.client.chat(
            model=self.reflection_model,
            messages=messages,
            options=self._options(temperature=self.temperature * 0.5),
            keep_alive=-1,
        )
        return resp["message"]["content"]

    @staticmethod
    def _lang_name(code: str) -> str:
        names = {"it": "italiano", "en": "inglese", "fr": "francese", "de": "tedesco", "es": "spagnolo"}
        return names.get(code, "italiano")

    def embed(self, text: str) -> list[float]:
        resp = self.client.embeddings(model=self.embed_model, prompt=text)
        return resp["embedding"]

    def detect_language(self, text: str) -> str:
        try:
            import langdetect
            lang = langdetect.detect(text)
            valid = {"it", "en", "fr", "de", "es"}
            return lang if lang in valid else "en"
        except Exception as e:
            logger.warning(f"Language detection failed ({e}), defaulting to en")
            return "en"
