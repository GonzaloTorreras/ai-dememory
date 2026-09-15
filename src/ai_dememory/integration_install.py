"""Owned, reversible global Codex configuration. No client trust edits."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tomllib
from dataclasses import replace

from .config import config_dir, config_path as selector_path, config_text, load_config
from .harness import SERVER_NAME, _shell_command, project_files
from .projects import bindings, _key, resolve_project
from .vault import _atomic_write, _exclusive_write_lock

BEGIN = "# BEGIN ai DeMemory V3 managed MCP\n"
END = "# END ai DeMemory V3 managed MCP\n"


def _read(path):
    if path.is_symlink() or path.resolve().parent != path.parent.absolute():
        raise ValueError("Integration configuration cannot be linked")
    if path.exists() and path.stat().st_size > 1_000_000:
        raise ValueError("Client configuration is too large")
    return path.read_text(encoding="utf-8") if path.exists() else None


def _toml_without_server(text):
    data = tomllib.loads(text)
    servers = data.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("Invalid MCP configuration")
    server = servers.pop(SERVER_NAME, None)
    if not servers:
        data.pop("mcp_servers", None)
    return data, server


def _replace_block(text, old, new):
    original, server = _toml_without_server(text)
    if old:
        if text.count(old) != 1 or server != _toml_without_server(old)[1]:
            raise ValueError("Managed MCP block was edited; review it before reinstalling")
        result = text.replace(old, new, 1)
    else:
        if server is not None or BEGIN in text or END in text:
            raise ValueError("An unowned DeMemory MCP definition already exists")
        result = text.rstrip() + ("\n\n" if text.strip() else "") + new
    if _toml_without_server(result)[0] != original:
        raise ValueError("Installing DeMemory would change unrelated TOML settings")
    return result


def _replace_hook(text, old, new):
    data = json.loads(text or "{}")
    if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
        raise ValueError("Invalid hooks.json")
    events = data.setdefault("hooks", {})
    groups = events.setdefault("UserPromptSubmit", [])
    if not isinstance(groups, list) or any(not isinstance(g, dict) or not isinstance(g.get("hooks", []), list) for g in groups):
        raise ValueError("Invalid UserPromptSubmit hooks")
    matches = sum(h == old for g in groups for h in g.get("hooks", [])) if old else 0
    if old and matches != 1:
        raise ValueError("Managed hook was edited or duplicated; review before reinstalling")
    if old:
        for group in groups:
            group["hooks"] = [h for h in group.get("hooks", []) if h != old]
        groups[:] = [g for g in groups if g.get("hooks") or set(g) != {"hooks"}]
    if new:
        if any(not isinstance(h, dict) or "ai_dememory.harness" in str(h.get("command", ""))
               for g in groups for h in g.get("hooks", [])):
            raise ValueError("Unowned DeMemory hook needs explicit cleanup before global install")
        if any(h == new for g in groups for h in g.get("hooks", [])):
            raise ValueError("Unowned duplicate DeMemory hook")
        groups.append({"hooks": [new]})
    return json.dumps(data, indent=2) + "\n"


def _transaction(changes):
    """Rollback only writes still identical to ours; never overwrite later edits."""
    completed = []
    try:
        for path, before, after in changes:
            if _read(path) != before:
                raise ValueError("Client settings changed during installation; retry after review")
            if before != after:
                _atomic_write(path, after)
                completed.append((path, before, after))
    except Exception:
        for path, before, after in reversed(completed):
            if _read(path) == after:
                if before is None:
                    path.unlink()
                else:
                    _atomic_write(path, before)
        raise


def install_user(vault, *, remove=False, projects=()):
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().absolute()
    if home.is_symlink() or home.resolve() != home:
        raise ValueError("Codex configuration home cannot be linked")
    receipt_path = config_dir() / "integrations" / "codex-global.json"
    config_dir().mkdir(parents=True, exist_ok=True)
    with _exclusive_write_lock(config_dir() / ".integration.lock"):
        receipt_raw = _read(receipt_path)
        receipt = json.loads(receipt_raw) if receipt_raw else {}
        if receipt and (receipt.get("schema_version") != 1 or receipt.get("home") != str(home)):
            raise ValueError("Global integration receipt belongs to another client home")
        if remove and not receipt:
            return {"installed": False, "changed": False}
        python, selector = str(Path(sys.executable).resolve()), str(config_dir())
        args = ["-m", "ai_dememory", "--vault", str(vault.root), "serve", "mcp", "--auto-scope"]
        block = (BEGIN + f"[mcp_servers.{SERVER_NAME}]\ncommand = {json.dumps(python)}\nargs = {json.dumps(args)}\n"
                 f"startup_timeout_sec = 10\ntool_timeout_sec = 8\n[mcp_servers.{SERVER_NAME}.env]\n"
                 f"AI_DEMEMORY_CONFIG_DIR = {json.dumps(selector)}\n" + END)
        hook = {"type": "command", "command": _shell_command([python, "-m", "ai_dememory.harness", "--vault", str(vault.root),
                 "--config-dir", selector, "--auto-scope", "--client", "codex"]), "timeout": 3,
                "additionalContextLimit": 1200, "statusMessage": "DeMemory V3: recall this project's memory"}
        config_path, hook_path = home / "config.toml", home / "hooks.json"
        old_toml, old_json = _read(config_path), _read(hook_path)
        # Inline TOML hook definitions are preserved, never guessed to be ours.
        inline = tomllib.loads(old_toml or "").get("hooks", {})
        if "ai_dememory.harness" in json.dumps(inline):
            raise ValueError("Inline DeMemory hooks need explicit cleanup before global install")
        new_toml = _replace_block(old_toml or "", receipt.get("block"), "" if remove else block)
        new_json = _replace_hook(old_json, receipt.get("hook"), None if remove else hook)
        changes = [(config_path, old_toml, new_toml), (hook_path, old_json, new_json)]
        retired = receipt.get("retired_project_files", [])
        if remove:
            for item in retired:
                path = Path(item["path"])
                current = _read(path)
                if current == item["after"]:
                    changes.append((path, current, item["before"]))
            # Keep an empty receipt file, not stale ownership after uninstall.
            changes.append((receipt_path, receipt_raw, "{}\n"))
        else:
            project_before = _read(config_dir() / "projects.json")
            project_data = bindings()
            for project in projects:
                project = Path(project).expanduser().resolve()
                path = project / ".codex" / "config.toml"
                current = _read(path)
                server = tomllib.loads(current or "").get("mcp_servers", {}).get(SERVER_NAME, {})
                old_args = server.get("args", [])
                if "--scope" not in old_args:
                    raise ValueError("Only exact generated project-local V3 connections can be retired")
                scope = old_args[old_args.index("--scope") + 1]
                expected = project_files(vault, project, "codex", scope)
                for path, before in expected.items():
                    if _read(path) != before:
                        raise ValueError("Project settings have other edits; retire owned entries manually")
                    after = "{}\n" if path.suffix == ".json" else ""
                    changes.append((path, before, after))
                    retired.append({"path": str(path), "before": before, "after": after})
                project_data[_key(project)] = {**project_data.get(_key(project), {}), "scope": scope}
            if projects:
                path = config_dir() / "projects.json"
                changes.append((path, project_before, json.dumps(project_data, indent=2) + "\n"))
            before = _read(selector_path())
            selected = load_config()
            enabled = tuple(sorted(set(selected.enabled_modules) | {"mcp"}))
            changes.append((selector_path(), before, config_text(replace(selected, enabled_modules=enabled))))
            new_receipt = {"schema_version": 1, "home": str(home), "block": block,
                           "hook": hook, "retired_project_files": retired}
            changes.append((receipt_path, receipt_raw, json.dumps(new_receipt, indent=2) + "\n"))
        # Everything, including restore targets, is parsed/preflighted before writes.
        _transaction(changes)
    return {"installed": not remove, "changed": any(before != after for _, before, after in changes),
            "client_home": str(home), "receipt": str(receipt_path), "trust_required": not remove}
