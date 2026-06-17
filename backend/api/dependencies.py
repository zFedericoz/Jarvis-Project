import os
import re
import yaml
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


_config        = None
_brain         = None
_speech        = None
_actions       = None
_memory        = None
_chat_manager  = None


def get_config():
    global _config
    if _config is None:
        with open("config/settings.yaml") as f:
            raw = yaml.safe_load(f)
        _config = resolve_env(raw)
    return _config


def get_brain(config):
    global _brain
    if _brain is None:
        import skills
        skills.init()
        from brain.llm_client import LLMClient
        from brain.multiagent import MultiAgent
        from brain.intent_router import IntentRouter
        _, persistent_memory = get_memory(config)
        llm = LLMClient(config)
        _brain = (llm, IntentRouter(), MultiAgent(llm, persistent_memory, skills_registry=skills))
    return _brain


def new_context():
    from brain.context_manager import ContextManager
    config = get_config()
    _, persistent_memory = get_memory(config)
    return ContextManager(persistent_memory=persistent_memory)


def get_speech(config):
    global _speech
    if _speech is None:
        from speech.stt import SpeechToText
        from speech.tts import TextToSpeech
        _speech = {"stt": SpeechToText(config), "tts": TextToSpeech(config)}
    return _speech


def get_actions(config):
    global _actions
    if _actions is None:
        from actions.system_control import SystemControl
        from actions.web_search import WebSearch
        from actions.media_player import MediaPlayer
        from actions.productivity import Productivity
        from actions.vision import Vision
        from actions.git_action import GitAction            # Step 4
        from actions.terminal_action import TerminalAction  # Step 5
        from actions.rpa_action import RPAAction            # Step 7

        llm, _, _ = get_brain(config)
        speech = get_speech(config)
        _, persistent_memory = get_memory(config)

        _actions = {
            "system_control": SystemControl(config),
            "web_search":      WebSearch(config),
            "media_player":    MediaPlayer(config),
            "productivity":    Productivity(
                                   config,
                                   tts=speech["tts"],
                                   persistent_memory=persistent_memory,
                               ),
            "vision":          Vision(config),
            "git":             GitAction(config, llm),
            "terminal":        TerminalAction(config, llm),
            "rpa":             RPAAction(config, llm),      # Step 7
        }
    return _actions


def get_memory(config):
    global _memory
    if _memory is None:
        from memory.ephemeral import EphemeralMemory
        from memory.persistent import PersistentMemory
        _memory = (EphemeralMemory(config), PersistentMemory(config))
    return _memory


def get_chat_manager():
    global _chat_manager
    if _chat_manager is None:
        from chat.chat_manager import ChatManager
        _chat_manager = ChatManager()
    return _chat_manager
