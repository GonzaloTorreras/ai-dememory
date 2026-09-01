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
        "prepares": [
            "canonical Markdown memory storage",
            "empty directories for optional proposals and generated search data",
        ],
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
        print("  Now: canonical Markdown memory storage")
        print("  Search index: setup does not build it; recall builds it only when needed")
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
            "search_index": {
                "state": "ready" if (vault.indexes_dir / "memory.sqlite").exists() else "not_built",
                "built_by": "recall",
            },
            "next": ['ai-dememory remember "Something worth remembering"'],
            "optional_later": [
                'ai-dememory recall "something"',
                "ai-dememory module enable mcp",
            ],
        }
    )
    return plan


def _run(args: argparse.Namespace, explicit_vault: str | None, json_output: bool) -> int:
    if args.command == "setup":
        _emit(_setup(args, json_output), json_output)
        return 0
    if args.command == "module" and args.module_command == "list":
        descriptors = list(discover_modules().values())
        if json_output:
            _emit(
                {"count": len(descriptors), "modules": [item.to_dict() for item in descriptors]},
                True,
            )
        elif not descriptors:
            print("No modules installed.")
        else:
            for descriptor in descriptors:
                state = "enabled" if descriptor.enabled else "disabled"
                print(f"{descriptor.module_id} [{state}]")
                print(f"  {descriptor.summary}")
                if descriptor.capabilities:
                    print(f"  capabilities: {', '.join(descriptor.capabilities)}")
        return 0
    if args.command == "module" and args.module_command == "enable":
        manifest = enable_module(args.module_id)
        result = {
            "enabled": manifest.module_id,
            "capabilities": list(manifest.capabilities),
            "resource_budget": manifest.resource_budget,
            "next": f"ai-dememory serve {manifest.module_id}",
        }
        if json_output:
            _emit(result, True)
        else:
            print(f"Enabled module: {manifest.module_id}")
            if manifest.capabilities:
                print(f"Capabilities: {', '.join(manifest.capabilities)}")
            print(f"Next: {result['next']}")
        return 0
    if args.command == "module" and args.module_command == "disable":
        disable_module(args.module_id)
        if json_output:
            _emit({"disabled": args.module_id}, True)
        else:
            print(f"Disabled module: {args.module_id}")
        return 0
    if args.command == "module" and args.module_command == "create":
        path = create_module(args.module_id, args.path)
        install = f'python -m pip install -e "{path}"'
        next_steps = (
            install,
            f"ai-dememory module enable {args.module_id}",
            f"ai-dememory serve {args.module_id}",
        )
        if json_output:
            _emit(
                {
                    "module_id": args.module_id,
                    "created": str(path),
                    "next": list(next_steps),
                },
                True,
            )
        else:
            print(f"Created module: {args.module_id}")
            print(f"Location: {path}")
            print("Next:")
            for step in next_steps:
                print(f"  {step}")
        return 0

    vault = _resolve_vault(explicit_vault)
    if args.command == "remember":
        memory = vault.remember(args.content, args.title)
        result = memory.to_dict()
        result.update({"saved": True, "verified": True})
        if json_output:
            _emit(result, True)
        else:
            print(f"Saved and verified: {memory.title} [{memory.memory_id[:8]}]")
            print(f"  {memory.path}")
        return 0
    if args.command == "recall":
        hits = SearchIndex(vault).search(args.query, args.limit)
        if json_output:
            _emit(
                {
                    "query": args.query,
                    "count": len(hits),
                    "results": [hit.to_dict() for hit in hits],
                },
                True,
            )
        elif not hits:
            print("No matching memories.")
        else:
            noun = "memory" if len(hits) == 1 else "memories"
            print(f"Found {len(hits)} matching {noun}.")
            for hit in hits:
                print(f"{hit.title}  [{hit.memory_id[:8]}]")
                print(f"  {hit.snippet}")
                print(f"  {hit.path}")
        return 0
    if args.command == "status":
        status = CoreServices(vault).status()
        if json_output:
            _emit(status, True)
        else:
            index = status["index"]
            index_state = str(index["state"]).replace("_", " ")
            modules = ", ".join(status["enabled_modules"]) or "none"
            print(f"Vault: {status['name']}")
            print(f"Location: {status['vault']}")
            print(f"Memories: {status['memories']}")
            print(f"Pending proposals: {status['pending_proposals']}")
            print(
                f"Search index: {index_state} "
                f"({index['rows']} rows, {index['bytes']} bytes)"
            )
            print(f"Enabled modules: {modules}")
            print(f"Background processes: {status['background_processes']}")
            print(f"Model calls: {status['model_calls']}")
        return 0
    if args.command == "review":
        store = ProposalStore(vault)
        action = args.review_command or "list"
        if action == "list":
            limit = getattr(args, "limit", 20)
            proposals = store.list(limit=limit)
            if json_output:
                _emit(
                    {"count": len(proposals), "proposals": [item.to_dict() for item in proposals]},
                    True,
                )
            elif not proposals:
                print("No pending proposals.")
            else:
                noun = "proposal" if len(proposals) == 1 else "proposals"
                print(f"{len(proposals)} pending {noun}.")
                for proposal in proposals:
                    print(f"{proposal.title}  [{proposal.proposal_id[:8]}]")
                    print(f"  created: {proposal.created_at}")
        elif action == "show":
            proposal = store.get(args.proposal_id)
            if proposal is None:
                raise CliError(f"Proposal not found: {args.proposal_id}")
            if json_output:
                _emit(proposal.to_dict(), True)
            else:
                print(f"Proposal: {proposal.title} [{proposal.proposal_id[:8]}]")
                print(f"Status: {proposal.status}")
                print(f"Created: {proposal.created_at}")
                print()
                print(proposal.content)
                print()
                print(proposal.path)
        else:
            proposal, memory = store.decide(args.proposal_id, accept=action == "accept")
            memory_result = None
            if memory:
                memory_result = memory.to_dict()
                memory_result.update({"saved": True, "verified": True})
            result = {
                "decision": proposal.status,
                "proposal": proposal.to_dict(),
                "memory": memory_result,
            }
            if json_output:
                _emit(result, True)
            elif memory:
                print(f"Accepted proposal: {proposal.title} [{proposal.proposal_id[:8]}]")
                print(f"Saved and verified: {memory.title} [{memory.memory_id[:8]}]")
                print(f"  {memory.path}")
            else:
                print(f"Rejected proposal: {proposal.title} [{proposal.proposal_id[:8]}]")
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
