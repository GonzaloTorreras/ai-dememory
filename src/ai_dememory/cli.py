"""The small public command line interface for ai DeMemory V3."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .config import ConfigError, config_path, load_config, select_vault
from .core import CoreServices
from .modules import (
    ModuleError,
    create_module,
    disable_module,
    discover_modules,
    enable_module,
    load_enabled_module,
)
from .policy import UnsafeContentError
from .proposals import ProposalError, ProposalStore
from .search import SearchError, SearchIndex
from .vault import Vault, VaultError


class CliError(ValueError):
    pass


def _configure_text_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-dememory",
        description="Small, local-first memory. No daemon, model calls, or network by default.",
    )
    parser.add_argument("--version", action="version", version=f"ai-dememory {__version__}")
    parser.add_argument("--vault", metavar="PATH", help="Use this V3 vault instead of the saved default.")
    parser.add_argument("--json", action="store_true", help="Return machine-readable output.")
    commands = parser.add_subparsers(dest="command", required=True)

    setup = commands.add_parser("setup", help="Create or select one small local vault.")
    setup.add_argument("path", nargs="?", help="Vault path; defaults to ~/ai-dememory-vault.")
    setup.add_argument("--name", help="Human-readable vault name.")
    setup.add_argument("--yes", action="store_true", help="Apply without an interactive confirmation.")
    setup.add_argument("--no-select", action="store_true", help="Do not make this the default vault.")

    remember = commands.add_parser("remember", help="Write one human-approved Markdown memory.")
    remember.add_argument("content")
    remember.add_argument("--title")

    recall = commands.add_parser("recall", help="Search canonical memories with local SQLite FTS.")
    recall.add_argument("query")
    recall.add_argument("--limit", type=int, default=5)

    commands.add_parser("status", help="Show useful state and resource use.")

    review = commands.add_parser("review", help="Review proposals created by AI modules.")
    review_commands = review.add_subparsers(dest="review_command")
    review_list = review_commands.add_parser("list", help="List pending proposals.")
    review_list.add_argument("--limit", type=int, default=20)
    review_show = review_commands.add_parser("show", help="Show one proposal.")
    review_show.add_argument("proposal_id")
    review_accept = review_commands.add_parser("accept", help="Promote one proposal to canonical memory.")
    review_accept.add_argument("proposal_id")
    review_reject = review_commands.add_parser("reject", help="Reject one proposal.")
    review_reject.add_argument("proposal_id")

    module = commands.add_parser("module", help="List, enable, disable or create optional modules.")
    module_commands = module.add_subparsers(dest="module_command", required=True)
    module_commands.add_parser("list", help="List installed modules without importing disabled code.")
    module_enable = module_commands.add_parser("enable", help="Validate and enable an installed module.")
    module_enable.add_argument("module_id")
    module_disable = module_commands.add_parser("disable", help="Disable a module.")
    module_disable.add_argument("module_id")
    module_create = module_commands.add_parser("create", help="Scaffold a community module.")
    module_create.add_argument("module_id")
    module_create.add_argument("--path", type=Path)

    serve = commands.add_parser("serve", help="Run one enabled module in the foreground.")
    serve.add_argument("module_id", nargs="?", default="mcp")
    serve.add_argument("module_args", nargs=argparse.REMAINDER)
    return parser


def _extract_globals(argv: list[str]) -> tuple[list[str], str | None, bool]:
    """Allow --vault and --json before or after a subcommand."""
    remaining: list[str] = []
    vault: str | None = None
    json_output = False
    index = 0
    while index < len(argv):
        value = argv[index]
        if value == "--":
            remaining.extend(argv[index:])
            break
        if value == "--json":
            json_output = True
        elif value == "--vault":
            index += 1
            if index >= len(argv):
                raise CliError("--vault requires a path")
            vault = argv[index]
        elif value.startswith("--vault="):
            vault = value.partition("=")[2]
        else:
            remaining.append(value)
        index += 1
    return remaining, vault, json_output


def _resolve_vault(explicit: str | None) -> Vault:
    if explicit:
        return Vault.open(Path(explicit))
    selected = load_config().default_vault
    if not selected:
        raise CliError("No default vault is configured. Run `ai-dememory setup [path]` once.")
    return Vault.open(Path(selected))


def _emit(value: Any, json_output: bool) -> None:
    if json_output:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    if isinstance(value, str):
        print(value)
        return
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _setup(args: argparse.Namespace, json_output: bool) -> dict[str, Any]:
    try:
        existing = load_config().default_vault
    except ConfigError:
        existing = None
    target = Path(args.path or existing or (Path.home() / "ai-dememory-vault")).expanduser().resolve()
    plan = {
        "vault": str(target),
        "creates": ["Markdown memories", "review proposals", "a disposable SQLite search index"],
        "background_processes": 0,
        "model_calls": 0,
        "network": False,
        "select_as_default": not args.no_select,
    }
    if not args.yes:
        if json_output or not sys.stdin.isatty():
            raise CliError("Setup needs confirmation; rerun with --yes in non-interactive use")
        print("ai DeMemory will create a small local vault:")
        print(f"  Location: {target}")
        print("  Data: Markdown memories, review proposals, disposable SQLite index")
        print("  Background work, model calls and network: none")
        answer = input("Create/select this vault? [Y/n] ").strip().lower()
        if answer not in ("", "y", "yes"):
            raise CliError("Setup cancelled")
    vault = Vault.create(target, args.name)
    if not args.no_select:
        select_vault(vault.root)
    plan.update(
        {
            "name": vault.name,
            "config": str(config_path()),
            "next": [
                'ai-dememory remember "Something worth remembering"',
                'ai-dememory recall "something"',
                "ai-dememory module enable mcp  # optional AI connection",
            ],
        }
    )
    return plan


def _run(args: argparse.Namespace, explicit_vault: str | None, json_output: bool) -> int:
    if args.command == "setup":
        _emit(_setup(args, json_output), json_output)
        return 0
    if args.command == "module" and args.module_command == "list":
        modules = [descriptor.to_dict() for descriptor in discover_modules().values()]
        _emit({"modules": modules}, json_output)
        return 0
    if args.command == "module" and args.module_command == "enable":
        manifest = enable_module(args.module_id)
        _emit(
            {
                "enabled": manifest.module_id,
                "capabilities": list(manifest.capabilities),
                "resource_budget": manifest.resource_budget,
            },
            json_output,
        )
        return 0
    if args.command == "module" and args.module_command == "disable":
        disable_module(args.module_id)
        _emit({"disabled": args.module_id}, json_output)
        return 0
    if args.command == "module" and args.module_command == "create":
        path = create_module(args.module_id, args.path)
        _emit({"created": str(path), "next": [f"python -m pip install -e {path}"]}, json_output)
        return 0

    vault = _resolve_vault(explicit_vault)
    if args.command == "remember":
        memory = vault.remember(args.content, args.title)
        SearchIndex(vault).sync()
        _emit(memory.to_dict(), json_output)
        return 0
    if args.command == "recall":
        hits = SearchIndex(vault).search(args.query, args.limit)
        if json_output:
            _emit({"query": args.query, "results": [hit.to_dict() for hit in hits]}, True)
        elif not hits:
            print("No matching memories.")
        else:
            for hit in hits:
                print(f"{hit.title}  [{hit.memory_id[:8]}]")
                print(f"  {hit.snippet}")
                print(f"  {hit.path}")
        return 0
    if args.command == "status":
        _emit(CoreServices(vault).status(), json_output)
        return 0
    if args.command == "review":
        store = ProposalStore(vault)
        action = args.review_command or "list"
        if action == "list":
            limit = getattr(args, "limit", 20)
            _emit({"proposals": [item.to_dict() for item in store.list(limit=limit)]}, json_output)
        elif action == "show":
            proposal = store.get(args.proposal_id)
            if proposal is None:
                raise CliError(f"Proposal not found: {args.proposal_id}")
            _emit(proposal.to_dict(), json_output)
        else:
            proposal, memory = store.decide(args.proposal_id, accept=action == "accept")
            if memory:
                SearchIndex(vault).sync()
            _emit(
                {"proposal": proposal.to_dict(), "memory": memory.to_dict() if memory else None},
                json_output,
            )
        return 0
    if args.command == "serve":
        module = load_enabled_module(args.module_id)
        if not hasattr(module, "serve"):
            raise ModuleError(f"Module {args.module_id} does not expose serve()")
        return int(module.serve(CoreServices(vault), args.module_args) or 0)
    raise CliError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    _configure_text_output()
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        clean, explicit_vault, json_output = _extract_globals(raw)
        args = _parser().parse_args(clean)
        return _run(args, explicit_vault or args.vault, json_output or args.json)
    except (
        CliError,
        ConfigError,
        ModuleError,
        OSError,
        ProposalError,
        SearchError,
        sqlite3.Error,
        UnicodeError,
        UnsafeContentError,
        VaultError,
    ) as exc:
        print(f"ai-dememory: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
