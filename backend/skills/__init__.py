import logging, importlib, inspect, pkgutil, yaml, os
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.skills")

SKILLS_DIR = Path(__file__).parent
_registry: dict[str, dict] = {}
_last_mtime: dict[str, float] = {}

def _load_skill_yaml(skill_dir: Path) -> dict | None:
    yml_path = skill_dir / "skill.yaml"
    if not yml_path.exists():
        return None
    with open(yml_path) as f:
        return yaml.safe_load(f)

def _discover():
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        meta = _load_skill_yaml(entry)
        if not meta:
            continue
        name = meta.get("name", entry.name)
        if name in _registry and not meta.get("reload", False):
            continue
        try:
            mod = importlib.import_module(f"skills.{entry.name}.execute")
            handler = getattr(mod, "execute", None)
            if not handler:
                logger.warning(f"Skill '{name}': nessuna funzione execute() in execute.py")
                continue
            _registry[name] = {"meta": meta, "handler": handler, "dir": str(entry)}
            logger.info(f"Skill caricata: {name} — {meta.get('description','')[:60]}")
        except Exception as e:
            logger.warning(f"Skill '{name}': errore import — {e}")

def init():
    _discover()
    logger.info(f"Skills registrate: {list(_registry.keys())}")

def reload():
    _registry.clear()
    _discover()

def get_ollama_tools() -> list[dict]:
    tools = []
    for name, skill in _registry.items():
        meta = skill["meta"]
        params = meta.get("parameters", {"type": "object", "properties": {}, "required": []})
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": meta.get("description", ""),
                "parameters": params,
            },
        })
    return tools

def execute(name: str, **kwargs) -> str:
    skill = _registry.get(name)
    if not skill:
        return f"Skill '{name}' non trovata"
    try:
        return skill["handler"](**kwargs)
    except Exception as e:
        logger.exception(f"Skill '{name}' fallita: {e}")
        return f"Errore skill '{name}': {e}"

def get_skill(name: str) -> dict | None:
    return _registry.get(name)
