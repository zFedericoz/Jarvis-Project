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

    def chat(self, message: str, context: list[dict] | None = None) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})

        resp = self.client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": self.temperature, "num_gpu": self.num_gpu},
        )
        return resp["message"]["content"]

    def embed(self, text: str) -> list[float]:
        resp = self.client.embeddings(model=self.embed_model, prompt=text)
        return resp["embedding"]

    def detect_language(self, text: str) -> str:
        prompt = (
            "Identify the language of the following text. "
            "Reply with ONLY the language code: it, en, fr, de, es. "
            f"Text: '{text[:200]}'"
        )
        try:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0, "num_gpu": self.num_gpu},
            )
            lang = resp["message"]["content"].strip().lower()
            valid = {"it", "en", "fr", "de", "es"}
            return lang if lang in valid else "en"
        except Exception as e:
            logger.warning(f"Language detection failed ({e}), defaulting to en")
            return "en"
