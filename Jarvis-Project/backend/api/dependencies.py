import os
import re
from functools import lru_cache
from pathlib import Path

def resolve_env(value):
    if isinstance(value, str):
        pattern = r'\$\{(\w+):-([^}]*)\}'
        def repl(m):
            return os.environ.get(m.group(1), m.group(2))
        return re.sub(pattern, repl, value)
    elif isinstance(value, dict):
        return {k: resolve_env(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env(v) for v in value]
    return value

@lru_cache
def get_config():
    import yaml
    with open("config/settings.yaml") as f:
        raw = yaml.safe_load(f)
    return resolve_env(raw)

def get_brain(config):
    from brain.llm_client import LLMClient
    from brain.intent_router import IntentRouter
    from brain.context_manager import ContextManager
    return LLMClient(config), IntentRouter(), ContextManager()

def get_speech(config):
    from speech.stt import SpeechToText
    from speech.tts import TextToSpeech
    return SpeechToText(), TextToSpeech(config)

def get_actions(config):
    from actions.system_control import SystemControl
    from actions.web_search import WebSearch
    from actions.media_player import MediaPlayer
    from actions.productivity import Productivity
    return {
        "system_control": SystemControl(config),
        "web_search": WebSearch(config),
        "media_player": MediaPlayer(config),
        "productivity": Productivity(config),
    }

def get_memory(config):
    from memory.ephemeral import EphemeralMemory
    from memory.persistent import PersistentMemory
    return EphemeralMemory(), PersistentMemory()
