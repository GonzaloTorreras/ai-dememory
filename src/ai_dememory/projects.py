"""Local project identity shared by hooks, CLI and client-bound MCP.

No subprocess or transcript reader. Automatic IDs derive from the local root;
explicit aliases/exclusions live beside the vault selector. Display names are
optional local metadata, never input to identity or access decisions.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
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


def resolve_project(cwd, *, allow_global=False):
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
    global_fallback = not chosen and (root == Path.home().resolve() or root.parent == root)
    if global_fallback and not allow_global:
        raise ValueError("No project binding here; choose a project directory or an explicit scope")
    identity = common if common is not None and not chosen else root
    scope = "global" if global_fallback else entry.get("scope") or "project:" + uuid.uuid5(uuid.NAMESPACE_URL, _key(identity)).hex
    excluded = set(entry.get("excluded_clients", []))
    for alias in configured.values():
        if alias.get("scope") == scope:
            excluded.update(alias.get("excluded_clients", []))
    # A linked worktree has a different folder name, but shares the main project.
    name_root = common.parent if not chosen and common is not None and common.name == ".git" else root
    return {"scope": validate_scope(scope), "root": str(root), "name": "" if global_fallback else name_root.name,
            "reason": "global" if global_fallback else "configured" if chosen else "git_common_directory" if common else "workspace_directory",
            "excluded_clients": sorted(excluded)}


def _display_name(value):
    from .policy import reject_high_confidence_secrets
    if not isinstance(value, str):
        return ""
    name = " ".join(value.split())[:120]
    try:
        reject_high_confidence_secrets(name)
    except ValueError:
        return ""
    return name


def remember_project_name(vault, project):
    """Best-effort display metadata from a resolved host project, not a transcript.

    Keep only a bounded basename, not its path or conversation contents. Failure
    must not interrupt learning/recall. This table never binds or merges scopes.
    """
    from .settings import local_file
    try:
        scope = validate_scope(project["scope"])
        name = _display_name(project["name"])
        if not name:
            return False
        path = local_file(vault, "runtime.sqlite")
        for suffix in ("-journal", "-wal", "-shm"):
            local_file(vault, "runtime.sqlite" + suffix)
        with closing(sqlite3.connect(path, timeout=0.05)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS project_names (scope TEXT PRIMARY KEY, name TEXT NOT NULL)")
            if db.execute("SELECT name FROM project_names WHERE scope=?", (scope,)).fetchone() == (name,):
                return True
            db.execute("""INSERT INTO project_names VALUES (?,?) ON CONFLICT(scope)
                DO UPDATE SET name=excluded.name WHERE name != excluded.name""", (scope, name))
            db.execute("DELETE FROM project_names WHERE rowid NOT IN (SELECT rowid FROM project_names ORDER BY rowid DESC LIMIT 1000)")
        return True
    except (ValueError, OSError, sqlite3.Error):
        return False


def scope_labels(vault, scopes):
    """Readable labels for UI only; callers must continue routing by raw scope."""
    from .settings import local_file
    names = {}
    try:
        path = local_file(vault, "runtime.sqlite")
        if path.exists():
            for suffix in ("-journal", "-wal", "-shm"):
                local_file(vault, "runtime.sqlite" + suffix)
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.05)) as db:
                names.update(db.execute("SELECT scope,name FROM project_names LIMIT 1000"))
    except (ValueError, OSError, sqlite3.Error):
        pass
    try:
        for root, entry in sorted(bindings().items(), reverse=True):
            if entry.get("scope"):
                names[entry["scope"]] = Path(root).name
    except (ValueError, OSError):
        pass
    labels = {}
    for scope in scopes:
        short = scope.removeprefix("project:")
        labels[scope] = ("Global · shared" if scope == "global" else _display_name(names.get(scope))
                         or ("Unnamed project" if re.fullmatch(r"[a-f0-9]{32}", short) else short))
    # Same-name folders remain separate. Only ambiguity adds a short identifier.
    groups = {}
    for scope, name in labels.items():
        groups.setdefault(name.casefold(), []).append(scope)
    for peers in groups.values():
        if len(peers) > 1:
            width = 8
            while len({key.removeprefix("project:")[:width] for key in peers}) < len(peers) and width < 128:
                width += 1
            for key in peers:
                labels[key] = f"{labels[key]} · {key[:width] if width == 128 else key.removeprefix('project:')[:width]}"
    return labels


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
