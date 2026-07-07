import importlib
import inspect
import logging
import os
from pathlib import Path

logger = logging.getLogger("jarvis.plugins")


class PluginBase:
    name: str = ""
    description: str = ""
    version: str = "1.0.0"

    def on_load(self):
        pass

    def on_unload(self):
        pass

    async def execute(self, action: str, params: dict) -> dict:
        raise NotImplementedError


class PluginLoader:
    def __init__(self, plugin_dirs: list[Path] | None = None):
        self._plugins: dict[str, PluginBase] = {}
        self._dirs = plugin_dirs or [Path("plugins/examples")]
        self._loaded = False

    def discover_and_load(self):
        if self._loaded:
            return
        for d in self._dirs:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                continue
            for f in sorted(d.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                self._load_plugin(f)
        self._loaded = True
        logger.info(f"Plugin caricati: {list(self._plugins.keys())}")

    def _load_plugin(self, path: Path):
        try:
            mod_name = f"plugins.{path.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, str(path))
            if spec is None or spec.loader is None:
                return
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, PluginBase) and obj is not PluginBase:
                    inst = obj()
                    inst.on_load()
                    self._plugins[inst.name or path.stem] = inst
                    logger.info(f"Plugin caricato: {inst.name} v{inst.version}")
        except Exception as e:
            logger.warning(f"Plugin {path.name} non caricato: {e}")

    def get_plugin(self, name: str) -> PluginBase | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict]:
        return [{"name": p.name, "description": p.description, "version": p.version} for p in self._plugins.values()]

    def unload_plugin(self, name: str) -> bool:
        p = self._plugins.pop(name, None)
        if p:
            p.on_unload()
            return True
        return False


_loader: PluginLoader | None = None


def get_plugin_loader() -> PluginLoader:
    global _loader
    if _loader is None:
        _loader = PluginLoader()
        _loader.discover_and_load()
    return _loader
