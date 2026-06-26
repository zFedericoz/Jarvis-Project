"""
Home Assistant Plugin — controlla luci, prese, termostato, tapparelle via API REST HA.
Config: impostare HA_URL e HA_TOKEN nelle preferenze utente o in settings.yaml
"""
import json
import logging
import os

import httpx

from plugins.loader import PluginBase

logger = logging.getLogger("jarvis.plugins.homeassistant")


class HomeAssistantPlugin(PluginBase):
    name = "homeassistant"
    description = "Controllo domotica via Home Assistant (luci, prese, termostato, tapparelle)"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self._base_url = os.getenv("HA_URL", "")
        self._token = os.getenv("HA_TOKEN", "")

    def on_load(self):
        if not self._base_url or not self._token:
            logger.warning("HA_URL o HA_TOKEN non impostati — plugin disabilitato")
        else:
            logger.info(f"HomeAssistant plugin pronto: {self._base_url}")

    async def execute(self, action: str, params: dict) -> dict:
        if not self._base_url or not self._token:
            return {"error": "HA non configurato (imposta HA_URL e HA_TOKEN)"}

        async with httpx.AsyncClient() as c:
            headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

            try:
                if action == "list_entities":
                    r = await c.get(f"{self._base_url}/api/states", headers=headers, timeout=10)
                    states = r.json() if r.status_code == 200 else []
                    return {"entities": [{"entity_id": s["entity_id"], "state": s["state"], "name": s["attributes"].get("friendly_name", "")} for s in states]}

                elif action == "get_state":
                    entity_id = params.get("entity_id", "")
                    r = await c.get(f"{self._base_url}/api/states/{entity_id}", headers=headers, timeout=10)
                    if r.status_code == 200:
                        s = r.json()
                        return {"entity_id": entity_id, "state": s["state"], "attributes": s["attributes"]}
                    return {"error": f"Entità {entity_id} non trovata"}

                elif action == "turn_on":
                    entity_id = params.get("entity_id", "")
                    r = await c.post(f"{self._base_url}/api/services/homeassistant/turn_on",
                                     headers=headers, json={"entity_id": entity_id}, timeout=10)
                    return {"status": "on" if r.status_code == 200 else "error", "entity_id": entity_id}

                elif action == "turn_off":
                    entity_id = params.get("entity_id", "")
                    r = await c.post(f"{self._base_url}/api/services/homeassistant/turn_off",
                                     headers=headers, json={"entity_id": entity_id}, timeout=10)
                    return {"status": "off" if r.status_code == 200 else "error", "entity_id": entity_id}

                elif action == "set_temperature":
                    entity_id = params.get("entity_id", "")
                    temp = params.get("temperature", 20)
                    r = await c.post(f"{self._base_url}/api/services/climate/set_temperature",
                                     headers=headers, json={"entity_id": entity_id, "temperature": temp}, timeout=10)
                    return {"status": "set" if r.status_code == 200 else "error", "temperature": temp}

                elif action == "set_light_brightness":
                    entity_id = params.get("entity_id", "")
                    brightness = params.get("brightness", 255)
                    r = await c.post(f"{self._base_url}/api/services/light/turn_on",
                                     headers=headers, json={"entity_id": entity_id, "brightness": brightness}, timeout=10)
                    return {"status": "set" if r.status_code == 200 else "error", "brightness": brightness}

                elif action == "cover":
                    entity_id = params.get("entity_id", "")
                    pos = params.get("position", 100)
                    r = await c.post(f"{self._base_url}/api/services/cover/set_cover_position",
                                     headers=headers, json={"entity_id": entity_id, "position": pos}, timeout=10)
                    return {"status": "set" if r.status_code == 200 else "error", "position": pos}

                return {"error": f"Azione '{action}' non supportata"}
            except Exception as e:
                return {"error": str(e)}
