#!/usr/bin/env python3
"""Small TOML subset helpers for .ai-dememory.toml."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any

from memorylib import path_is_link_like, safe_write_text


CONFIG_NAME = ".ai-dememory.toml"
MAX_CONFIG_BYTES = 64 * 1024


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def root_bound_config_path(path: Path, root: Path) -> Path:
    """Anchor one config path below a vault while preserving a root alias."""

    logical_root = Path(os.path.abspath(Path(root).expanduser()))
    resolved_root = logical_root.resolve(strict=False)
    candidate = Path(os.path.abspath(Path(path).expanduser()))
    try:
        relative = candidate.relative_to(logical_root)
    except ValueError:
        try:
            relative = candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("config path must stay inside the memory root") from exc

    target = resolved_root / relative
    current = resolved_root
    for part in relative.parts:
        current = current / part
        if path_is_link_like(current):
            raise ValueError("config path must not contain symlinks or junctions")
    return target


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _has_stable_file_identity(value: os.stat_result) -> bool:
    """Require an inode value that can distinguish a raced file handle."""

    return value.st_ino != 0


def _has_single_hard_link(value: os.stat_result) -> bool:
    """Reject ambiguous or shared file metadata at the vault boundary."""

    return value.st_nlink == 1


def _validated_config_stat(path: Path, root: Path, expected: os.stat_result | None = None) -> os.stat_result | None:
    target = root_bound_config_path(path, root)
    try:
        observed = target.lstat()
    except FileNotFoundError:
        if expected is not None:
            raise ValueError("config path changed while reading") from None
        return None
    except OSError as exc:
        raise ValueError("config path could not be inspected safely") from exc
    if not stat.S_ISREG(observed.st_mode):
        raise ValueError("config path must be a regular file")
    if not _has_stable_file_identity(observed):
        raise ValueError("config path has no stable file identity")
    if observed.st_nlink > 1:
        raise ValueError("config path must not have multiple hard links")
    if not _has_single_hard_link(observed):
        raise ValueError("config path has no stable hard-link count")
    if expected is not None and not _same_file_identity(observed, expected):
        raise ValueError("config path changed while reading")
    return observed


def read_config_bytes(path: Path, *, root: Path) -> bytes | None:
    """Read a regular in-vault config without following links or stale paths."""

    target = root_bound_config_path(path, root)
    before = _validated_config_stat(target, root)
    if before is None:
        return None

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_CLOEXEC", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    flags |= int(getattr(os, "O_NONBLOCK", 0))
    fd = -1
    try:
        try:
            fd = os.open(target, flags)
        except FileNotFoundError:
            raise ValueError("config path changed while reading") from None
        except OSError as exc:
            raise ValueError("config path could not be opened safely") from exc
        try:
            opened = os.fstat(fd)
        except OSError as exc:
            raise ValueError("config path could not be read safely") from exc
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("config path must be a regular file")
        if not _has_stable_file_identity(opened):
            raise ValueError("config path has no stable file identity")
        if not _has_single_hard_link(opened):
            raise ValueError("config path has no stable hard-link count")
        if not _same_file_identity(before, opened):
            raise ValueError("config path changed while reading")
        _validated_config_stat(target, root, expected=opened)
        chunks: list[bytes] = []
        total_bytes = 0
        while True:
            try:
                chunk = os.read(fd, min(64 * 1024, MAX_CONFIG_BYTES + 1 - total_bytes))
            except OSError as exc:
                raise ValueError("config path could not be read safely") from exc
            if not chunk:
                break
            chunks.append(chunk)
            total_bytes += len(chunk)
            if total_bytes > MAX_CONFIG_BYTES:
                raise ValueError(f"config file exceeds {MAX_CONFIG_BYTES} byte limit")
        _validated_config_stat(target, root, expected=opened)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)


def read_config_path(path: Path, *, root: Path) -> str | None:
    content = read_config_bytes(path, root=root)
    if content is None:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("config file must be valid UTF-8") from exc


def parse_config_text(text: str) -> dict[str, dict[str, Any]]:
    """Parse the small supported TOML subset from already-validated text."""

    config: dict[str, dict[str, Any]] = {}
    section: str | None = None
    for raw_line in text.splitlines():
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


def load_config_path(path: Path, *, root: Path) -> dict[str, dict[str, Any]]:
    text = read_config_path(path, root=root)
    return parse_config_text(text) if text is not None else {}


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
    return load_config_path(config_path(root), root=root)


def set_section(root: Path, section: str, values: dict[str, Any]) -> Path:
    return set_section_path(config_path(root), section, values, root=root)


def set_section_path(path: Path, section: str, values: dict[str, Any], *, root: Path) -> Path:
    path = root_bound_config_path(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = root_bound_config_path(path, root)
    existing_text = read_config_path(path, root=root)
    existing = existing_text.splitlines() if existing_text is not None else []

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

    safe_write_text(
        path,
        "\n".join(output).rstrip() + "\n",
        root=root,
        overwrite=True,
    )
    return path


def ensure_safe_write_path(path: Path, root: Path | None = None) -> None:
    if root is not None:
        root = root.resolve()
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise ValueError("config path must stay inside the memory root") from exc

    if path_is_link_like(path):
        raise ValueError("config path must not be a symlink")

    parent = path.parent
    stop_at = root if root is not None else None
    while True:
        if parent.exists() and path_is_link_like(parent):
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
