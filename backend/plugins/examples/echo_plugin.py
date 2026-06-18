import datetime


from plugins.loader import PluginBase


class EchoPlugin(PluginBase):
    name = "echo"
    description = "Echo plugin — rispecchia il messaggio con timestamp"
    version = "1.0.1"

    async def execute(self, action: str, params: dict) -> dict:
        msg = params.get("message", "")
        ts = datetime.datetime.now().isoformat()
        return {"response": f"[{ts}] Echo: {msg}", "action": action}
