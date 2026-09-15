"""Local project identity shared by hooks, CLI and client-bound MCP.

No subprocess, transcript reader or background registry. Automatic IDs derive
from the local root; explicit aliases/exclusions live beside the vault selector.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .config import config_dir, harness_enabled
from .vault import _atomic_write, validate_scope


def _path(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
        raise ValueError("Choose an absolute local project directory")
    path = path.resolve()
    if not path.is_dir():
        raise ValueError("Project directory does not exist")
    return path


def _key(path):
    return os.path.normcase(str(path))


def bindings():
    path = config_dir() / "projects.json"
    if not path.exists():
        return {}
    if path.stat().st_size > 256_000:
        raise ValueError("Project configuration is too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or len(data) > 1000:
        raise ValueError("Invalid project configuration")
    for root, entry in data.items():
        if not isinstance(root, str) or not Path(root).is_absolute() or not isinstance(entry, dict):
            raise ValueError("Invalid project binding")
        if set(entry) - {"scope", "excluded_clients"}:
            raise ValueError("Unknown project binding field")
        if "scope" in entry:
            validate_scope(entry["scope"])
        excluded = entry.get("excluded_clients", [])
        if not isinstance(excluded, list) or any(c not in ("codex", "claude") for c in excluded):
            raise ValueError("Invalid project exclusion")
    return data


def _git_root(cwd):
    for folder in (cwd, *list(cwd.parents)[:32]):
        marker = folder / ".git"
        if marker.is_dir():
            return folder, marker.resolve()
        if marker.is_file():
            if marker.stat().st_size > 4096:
                raise ValueError("Invalid Git project marker")
            line = marker.read_text(encoding="utf-8").strip()
            if not line.startswith("gitdir: "):
                raise ValueError("Invalid Git project marker")
            git_dir = (folder / line[8:]).resolve()
            common = git_dir / "commondir"
            if common.is_file():
                if common.stat().st_size > 4096:
                    raise ValueError("Invalid Git common directory")
                git_dir = (git_dir / common.read_text(encoding="utf-8").strip()).resolve()
            if not git_dir.is_dir():
                raise ValueError("Git metadata directory is unavailable")
            return folder, git_dir
    return cwd, None


def resolve_project(cwd):
    cwd = _path(cwd)
    root, common = _git_root(cwd)
    configured = bindings()
    # Explicit ancestor mappings win; the common checkout maps its worktrees.
    candidates = [p for p in configured if cwd.is_relative_to(Path(p))]
    if not candidates and common is not None:
        candidates = [p for p in configured if (Path(p) / ".git").resolve() == common]
    chosen = max(candidates, key=len) if candidates else None
    entry = configured.get(chosen, {})
    if chosen:
        root = Path(chosen)
    if not chosen and (root == Path.home().resolve() or root.parent == root):
        raise ValueError("No project binding here; choose a project directory or an explicit scope")
    identity = common if common is not None and not chosen else root
    scope = entry.get("scope") or "project:" + uuid.uuid5(uuid.NAMESPACE_URL, _key(identity)).hex
    excluded = set(entry.get("excluded_clients", []))
    for alias in configured.values():
        if alias.get("scope") == scope:
            excluded.update(alias.get("excluded_clients", []))
    return {"scope": validate_scope(scope), "root": str(root), "name": root.name,
            "reason": "configured" if chosen else "git_common_directory" if common else "workspace_directory",
            "excluded_clients": sorted(excluded)}


def project_enabled(cwd, client):
    return harness_enabled(client) and client not in resolve_project(cwd)["excluded_clients"]


def configure_project(cwd, *, scope=None, client=None, enabled=None):
    root = _path(cwd)
    data = bindings()
    entry = dict(data.get(_key(root), {}))
    if scope is not None:
        entry["scope"] = validate_scope(scope)
    if client is not None:
        if client not in ("codex", "claude") or type(enabled) is not bool:
            raise ValueError("Choose a client and enabled state")
        excluded = set(entry.get("excluded_clients", []))
        excluded.discard(client) if enabled else excluded.add(client)
        entry["excluded_clients"] = sorted(excluded)
    # Preserve automatic identity when adding an exclusion for the first time.
    if "scope" not in entry:
        entry["scope"] = resolve_project(root)["scope"]
    data[_key(root)] = entry
    if client is not None:
        for alias in data.values():
            if alias.get("scope") == entry["scope"]:
                excluded = set(alias.get("excluded_clients", []))
                excluded.discard(client) if enabled else excluded.add(client)
                alias["excluded_clients"] = sorted(excluded)
    _atomic_write(config_dir() / "projects.json", json.dumps(data, indent=2) + "\n")
    return resolve_project(root)
