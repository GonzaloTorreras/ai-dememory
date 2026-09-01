"""Machine-local configuration for selecting a default vault and modules."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    default_vault: str | None = None
    enabled_modules: tuple[str, ...] = ()


def config_dir() -> Path:
    override = os.environ.get("AI_DEMEMORY_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Roaming") / "ai-dememory"
    if os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ai-dememory"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "ai-dememory"


def config_path() -> Path:
    return config_dir() / "config.toml"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Cannot read local config {path}: {exc}") from exc

    unknown = set(data) - {"schema_version", "default_vault", "modules"}
    if unknown:
        raise ConfigError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    if data.get("schema_version") != 1:
        raise ConfigError("Unsupported local config schema; run `ai-dememory setup` again")
    default = data.get("default_vault")
    if default is not None and not isinstance(default, str):
        raise ConfigError("default_vault must be a path string")
    if default is not None and not Path(default).is_absolute():
        raise ConfigError("default_vault must be an absolute path; run `ai-dememory setup` again")
    modules = data.get("modules", {})
    if not isinstance(modules, dict) or set(modules) - {"enabled"}:
        raise ConfigError("modules may contain only an enabled list")
    enabled = modules.get("enabled", [])
    if not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
        raise ConfigError("modules.enabled must be a list of module ids")
    return AppConfig(default_vault=default, enabled_modules=tuple(sorted(set(enabled))))


def save_config(config: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["schema_version = 1"]
    if config.default_vault:
        lines.append(f"default_vault = {json.dumps(config.default_vault)}")
    lines.extend(("", "[modules]", f"enabled = {json.dumps(list(config.enabled_modules))}", ""))
    payload = "\n".join(lines)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def select_vault(path: Path) -> AppConfig:
    try:
        current = load_config()
    except ConfigError:
        current = AppConfig()
    config = replace(current, default_vault=str(path.resolve()))
    save_config(config)
    return config


def set_module_enabled(module_id: str, enabled: bool) -> AppConfig:
    config = load_config()
    modules = set(config.enabled_modules)
    if enabled:
        modules.add(module_id)
    else:
        modules.discard(module_id)
    updated = replace(config, enabled_modules=tuple(sorted(modules)))
    save_config(updated)
    return updated
