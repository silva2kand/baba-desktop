"""config/settings.py — Loads and validates all Baba Desktop settings"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any


CONFIG_PATH = Path(__file__).parent / "config.json"


def _resolve_from(base: Path, value: str) -> str:
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base / p).resolve())


@dataclass
class Settings:
    providers: Dict[str, Any] = field(default_factory=dict)
    routing:   Dict[str, Any] = field(default_factory=dict)
    brain_db_path: str = "data/brain_index/brain.db"
    memory_dir: str = "data/brain_memory"
    watch_folders: list = field(default_factory=list)
    pc_bridge_port: int = 8765
    claws_dir: str = "src/claws/installed"
    tools_experimental_dir: str = "src/tools_experimental"
    tools_active_dir: str = "src/tools"
    exports_dir: str = "data/exports"
    logs_dir: str = "logs"
    ui_port: int = 8080
    theme: str = "Midnight"
    voice_enabled: bool = False
    safety: Dict[str, Any] = field(default_factory=dict)
    vision: Dict[str, Any] = field(default_factory=dict)
    integrations: Dict[str, Any] = field(default_factory=dict)
    oauth_redirect_uri: str = "http://localhost:8080/oauth/callback"
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)
    _path: Path = field(default=CONFIG_PATH, repr=False)

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Settings":
        with open(path) as f:
            raw = json.load(f)

        app_root = path.parent.parent.resolve()

        s = cls()
        s._raw            = raw
        s._path           = path
        s.providers       = raw.get("providers", {})
        s.routing         = raw.get("routing", {})
        s.brain_db_path   = _resolve_from(app_root, raw.get("brain", {}).get("db_path", s.brain_db_path))
        s.memory_dir      = _resolve_from(app_root, raw.get("memory", {}).get("dir", s.memory_dir))
        s.watch_folders   = [
            _resolve_from(app_root, p)
            for p in raw.get("brain", {}).get("watch_folders", [])
        ]
        s.pc_bridge_port  = raw.get("pc_bridge", {}).get("port", 8765)
        s.claws_dir       = _resolve_from(app_root, raw.get("claws_dir", s.claws_dir))
        s.tools_experimental_dir = _resolve_from(app_root, raw.get("tools_experimental_dir", s.tools_experimental_dir))
        s.tools_active_dir       = _resolve_from(app_root, raw.get("tools_active_dir", s.tools_active_dir))
        s.exports_dir     = _resolve_from(app_root, raw.get("exports_dir", s.exports_dir))
        s.logs_dir        = _resolve_from(app_root, raw.get("logs_dir", s.logs_dir))
        s.ui_port         = raw.get("ui", {}).get("port", s.ui_port)
        s.theme           = raw.get("ui", {}).get("theme", s.theme)
        s.voice_enabled   = bool(raw.get("ui", {}).get("auto_tts", s.voice_enabled))
        s.safety          = raw.get("safety", {})
        s.vision          = raw.get("vision", {})
        s.integrations    = raw.get("integrations", {})
        s.oauth_redirect_uri = (
            s.integrations.get("oauth", {}).get("redirect_uri")
            or f"http://localhost:{s.ui_port}/oauth/callback"
        )

        # Inject API keys from environment
        for pname, pcfg in s.providers.items():
            env_var = pcfg.get("api_key_env")
            if env_var:
                key = os.environ.get(env_var, "")
                s.providers[pname]["api_key"] = key

        # Ensure required directories exist.
        for d in [
            Path(s.brain_db_path).parent,
            Path(s.memory_dir),
            Path(s.exports_dir),
            Path(s.logs_dir),
            Path(s.claws_dir),
            Path(_resolve_from(app_root, "data/claws")),
        ]:
            d.mkdir(parents=True, exist_ok=True)

        return s

    def get_provider_url(self, provider: str) -> str:
        return self.providers.get(provider, {}).get("url", "")

    def get_api_key(self, provider: str) -> str:
        return self.providers.get(provider, {}).get("api_key", "")

    def get_model(self, provider: str, role: str = "default") -> str:
        return self.providers.get(provider, {}).get("models", {}).get(role, "")

    def get_route(self, task: str) -> Dict[str, str]:
        return self.routing.get(task, self.routing.get("fallback", {}))

    def is_provider_enabled(self, provider: str) -> bool:
        return self.providers.get(provider, {}).get("enabled", False)

    def get_localhost_redirect_uri(self) -> str:
        return self.oauth_redirect_uri or f"http://localhost:{self.ui_port}/oauth/callback"

    def save(self, path: Path | None = None) -> None:
        out_path = path or self._path or CONFIG_PATH
        raw = dict(self._raw) if self._raw else {}

        # Never persist runtime-injected API keys into config.json.
        sanitized_providers: Dict[str, Any] = {}
        for name, cfg in self.providers.items():
            cfg_copy = dict(cfg)
            cfg_copy.pop("api_key", None)
            sanitized_providers[name] = cfg_copy

        raw["providers"] = sanitized_providers
        raw["routing"] = self.routing
        raw.setdefault("brain", {})
        raw["brain"]["db_path"] = self.brain_db_path
        raw["brain"]["watch_folders"] = self.watch_folders
        raw.setdefault("memory", {})
        raw["memory"]["dir"] = self.memory_dir
        raw.setdefault("pc_bridge", {})
        raw["pc_bridge"]["port"] = self.pc_bridge_port
        raw["claws_dir"] = self.claws_dir
        raw["tools_experimental_dir"] = self.tools_experimental_dir
        raw["tools_active_dir"] = self.tools_active_dir
        raw["exports_dir"] = self.exports_dir
        raw["logs_dir"] = self.logs_dir
        raw.setdefault("ui", {})
        raw["ui"]["port"] = self.ui_port
        raw["ui"]["theme"] = self.theme
        raw["ui"]["auto_tts"] = self.voice_enabled
        raw["safety"] = self.safety
        raw["vision"] = self.vision
        raw.setdefault("integrations", {})
        existing_oauth = raw.get("integrations", {}).get("oauth", {})
        if not isinstance(existing_oauth, dict):
            existing_oauth = {}
        existing_oauth["redirect_uri"] = self.get_localhost_redirect_uri()
        raw["integrations"]["oauth"] = existing_oauth

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)

        self._raw = raw
        self._path = out_path
