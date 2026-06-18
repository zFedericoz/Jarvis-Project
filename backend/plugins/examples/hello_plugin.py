from plugins.loader import PluginBase


class HelloPlugin(PluginBase):
    name = "hello"
    description = "Hello World plugin — dice ciao in varie lingue"
    version = "1.0.0"

    async def execute(self, action: str, params: dict) -> dict:
        lang = params.get("language", "it")
        greetings = {"it": "Ciao!", "en": "Hello!", "fr": "Bonjour!", "de": "Hallo!", "es": "¡Hola!"}
        return {"response": greetings.get(lang, "Hello!"), "action": action}
