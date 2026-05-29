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
        self.embed_model = llm_cfg["embedding_model"]
        self.temperature = llm_cfg["temperature"]
        self.num_gpu = llm_cfg["num_gpu"]

        with open("config/persona.yaml") as f:
            persona = yaml.safe_load(f)
        self.system_prompt = persona["system_prompt"]

        host = llm_cfg["host"]
        self.client = ollama.Client(host=host)
        logger.info(f"LLM initialized: {self.model} @ {host} (GPU={self.num_gpu})")

    def warmup(self):
        self.client.chat(model=self.model, messages=[{"role": "user", "content": ""}], keep_alive=-1)
        logger.info("LLM model warmed up (keep_alive=-1)")

    def chat(self, message: str, context: list[dict] | None = None, language: str = "it",
             extra_system_prompt: str = "") -> str:
        messages = self._build_messages(message, context, language, extra_system_prompt)
        resp = self.client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": self.temperature, "num_gpu": self.num_gpu},
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
        prompt = (
            f"You are a quality evaluator. Rate the following assistant response from 1 to 10 based on:\n"
            f"1. Language: it MUST be in {self._lang_name(language)}. If it mixes languages or is in the wrong language, score 0.\n"
            f"2. Relevance: does it directly answer the user?\n"
            f"3. Conciseness: is it brief and to the point?\n"
            f"4. Tone: is it professional and calm?\n\n"
            f"User message: {user_message}\n\n"
            f"Assistant response: {response}\n\n"
            f"Reply ONLY with a number from 0 to 10."
        )
        try:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "system", "content": "You are a strict quality evaluator. Reply only with a number."},
                          {"role": "user", "content": prompt}],
                options={"temperature": 0, "num_gpu": self.num_gpu},
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
        prompt = (
            f"The previous response scored {score}/10. Improve it.\n\n"
            f"User: {user_message}\n"
            f"Previous response: {previous_response}\n\n"
            f"Issues to fix: be more concise, ensure it's in {self._lang_name(language)}, "
            f"and answer the user's question directly."
        )
        messages = self._build_messages(prompt, context, language)
        resp = self.client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": self.temperature * 0.5, "num_gpu": self.num_gpu},
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
