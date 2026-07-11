#!/usr/bin/env python3
"""Small TOML subset helpers for .ai-dememory.toml."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_NAME = ".ai-dememory.toml"


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def load_config_path(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    config: dict[str, dict[str, Any]] = {}
    section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            config.setdefault(section, {})
            continue
        if section and "=" in line:
            key, value = line.split("=", 1)
            config.setdefault(section, {})[key.strip()] = parse_scalar(value)
    return config


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return parsed if isinstance(parsed, list) else value
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace("\\\\", "\\").replace('\\"', '"')
    if value in {"true", "false"}:
        return value == "true"
    try:
        return int(value)
    except ValueError:
        return value


def format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return '""'
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def load_config(root: Path) -> dict[str, dict[str, Any]]:
    return load_config_path(config_path(root))


def set_section(root: Path, section: str, values: dict[str, Any]) -> Path:
    return set_section_path(config_path(root), section, values, root=root)


def set_section_path(path: Path, section: str, values: dict[str, Any], root: Path | None = None) -> Path:
    ensure_safe_write_path(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_safe_write_path(path, root)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    output: list[str] = []
    index = 0
    replaced = False
    while index < len(existing):
        line = existing[index]
        if line.strip() == f"[{section}]":
            replaced = True
            output.extend(render_section(section, values))
            index += 1
            while index < len(existing):
                candidate = existing[index].strip()
                if candidate.startswith("[") and candidate.endswith("]"):
                    break
                index += 1
            if index < len(existing) and output and output[-1] != "":
                output.append("")
            continue
        output.append(line)
        index += 1

    if not replaced:
        if output and output[-1] != "":
            output.append("")
        output.extend(render_section(section, values))

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return path


def ensure_safe_write_path(path: Path, root: Path | None = None) -> None:
    if root is not None:
        root = root.resolve()
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise ValueError("config path must stay inside the memory root") from exc

    if path.is_symlink():
        raise ValueError("config path must not be a symlink")

    parent = path.parent
    stop_at = root if root is not None else None
    while True:
        if parent.exists() and parent.is_symlink():
            raise ValueError("config path parent must not be a symlink")
        if stop_at is not None and parent.resolve(strict=False) == stop_at:
            break
        next_parent = parent.parent
        if next_parent == parent:
            break
        parent = next_parent


def render_section(section: str, values: dict[str, Any]) -> list[str]:
    lines = [f"[{section}]"]
    for key, value in values.items():
        lines.append(f"{key} = {format_scalar(value)}")
    return lines
