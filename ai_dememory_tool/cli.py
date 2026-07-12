"""Unified command entry point for the local memory toolchain."""

from __future__ import annotations

import argparse
import importlib
from importlib import resources
import json
from pathlib import Path
import os
import shutil
import sys

from ai_dememory_tool import __version__
from ai_dememory_tool.mcp_profiles import MCP_PROFILE_NAMES, enabled_tools_for_profile


LOCAL_COMMANDS = {
    "init": "Create a new private memory vault.",
    "mcp-config": "Print MCP client configuration for a memory vault.",
    "vault-template": "Export the private vault GitHub template tree.",
}

COMMANDS = {
    "doctor": ("Run local readiness checks.", "doctor"),
    "verify-mcp": ("Statically validate MCP contract definitions.", "verify_mcp_contract"),
    "mcp-inventory": ("Report and validate documented MCP tool inventory.", "mcp_inventory"),
    "release-check": ("Run non-runtime v2 release readiness checks.", "release_check"),
    "install-smoke": ("Run fresh package and local Docker install smoke checks.", "install_smoke"),
    "package-build-smoke": ("Build package distributions in temp space and run twine check.", "package_build_smoke"),
    "publish-guard": ("Validate manual Trusted Publishing workflow safety.", "publish_guard"),
    "publish-plan": ("Plan manual TestPyPI/PyPI publishing without uploading packages.", "publish_plan"),
    "ci-guard": ("Validate CI workflow v2 gate coverage.", "ci_guard"),
    "artifact-guard": ("Validate no generated artifacts are staged.", "artifact_guard"),
    "vault-setup-guard": ("Validate private vault setup docs avoid generated artifacts.", "vault_setup_guard"),
    "pr-template-guard": ("Validate PR template v2 gate coverage.", "pr_template_guard"),
    "pr-draft-guard": ("Validate draft PR handoff freshness.", "pr_draft_guard"),
    "acceptance-guard": ("Validate manual acceptance checklist coverage.", "acceptance_guard"),
    "adr-guard": ("Validate ADR structure and required decision context.", "adr_guard"),
    "release-checklist-guard": ("Validate release checklist v2 gate coverage.", "release_checklist_guard"),
    "release-evidence": ("Summarize automated and manual v2 release readiness evidence.", "release_evidence"),
    "roadmap": ("Report v2 operational roadmap implementation status.", "roadmap_status"),
    "acceptance": ("Record and summarize reviewed manual release acceptance evidence.", "manual_acceptance"),
    "mcp-smoke": ("Run gated MCP stdio runtime smoke checks.", "mcp_runtime_smoke"),
    "mcp-client-smoke": ("Launch generated MCP client config and verify initialize/ping.", "mcp_client_smoke"),
    "api-smoke": ("Smoke test the local REST API.", "api_smoke"),
    "validate": ("Validate Markdown memory frontmatter.", "validate_memory"),
    "secret-scan": ("Scan repository text for suspected secrets.", "secret_scan"),
    "index": ("Rebuild the SQLite FTS memory index.", "index_memory"),
    "search": ("Search the generated memory index.", "search_memory"),
    "context": ("Assemble token-budgeted session context.", "context_memory"),
    "graph": ("Build a relationship graph from local memory.", "graph_memory"),
    "eval-recall": ("Evaluate search against recall quality fixtures.", "eval_recall"),
    "recall-fixtures": ("Inspect, promote, reject, or dismiss reviewed recall misses.", "recall_fixtures"),
    "vector": ("Evaluate whether vector search is justified.", "vector_gate"),
    "capture-miss": ("Capture a recall miss for human review.", "capture_miss"),
    "provenance": ("Audit durable memory review provenance.", "durable_provenance"),
    "export-context": ("Export generated LLM context bundles.", "export_context"),
    "consolidate": ("Generate a consolidation dry-run report.", "consolidate_memory"),
    "sleep": ("Plan safe sleep consolidation review packets.", "sleep_consolidation"),
    "mcp": ("Run or inspect the MCP server.", "memory_mcp"),
    "api": ("Run the local REST API server.", "http_api"),
    "maintenance": ("Run or inspect opt-in maintenance profiles.", "maintenance"),
    "providers": ("Detect and configure chat import providers.", "provider_import"),
    "import-chats": ("Import configured provider chats into review inbox.", "provider_import"),
    "capture": ("Capture explicit files or text into review inbox.", "provider_import"),
    "learn": ("Capture review-first lesson candidates from git history.", "git_lessons"),
    "schedule": ("Install, inspect, or remove opt-in maintenance schedules.", "schedule_memory"),
    "setup": ("Plan review-first local vault, MCP, provider, hook, and scheduler setup.", "setup_plan"),
    "onboard": ("Preview or apply minimum reviewed values, preferences, recommendations, and project profiles.", "onboarding"),
    "turn-context": ("Build bounded prompt- and project-aware memory context for one model turn.", "turn_context"),
    "hook-event": ("Capture provider hook event metadata into review inbox.", "hook_event"),
    "hooks": ("Print provider hook events and install config fragments.", "hook_event"),
    "working": ("Capture working memory snapshots and handoffs.", "working_memory"),
    "lifecycle": ("Inspect generated lifecycle scores and reports.", "lifecycle"),
    "mark-seen": ("Record that a memory was retrieved or used.", "lifecycle"),
    "outcome": ("Record good/bad memory usefulness feedback.", "lifecycle"),
    "review": ("Generate false-positive and conflict review reports.", "review_memory"),
    "false-positive": ("Manage secret-scan false-positive suppressions.", "review_memory"),
    "conflict": ("Manage memory conflict review decisions.", "review_memory"),
}

DEV_COMMANDS = {
    "acceptance",
    "acceptance-guard",
    "adr-guard",
    "api-smoke",
    "artifact-guard",
    "capture-miss",
    "ci-guard",
    "conflict",
    "consolidate",
    "eval-recall",
    "export-context",
    "false-positive",
    "hook-event",
    "install-smoke",
    "lifecycle",
    "mark-seen",
    "mcp-client-smoke",
    "mcp-inventory",
    "mcp-smoke",
    "outcome",
    "package-build-smoke",
    "pr-draft-guard",
    "pr-template-guard",
    "provenance",
    "publish-guard",
    "publish-plan",
    "release-check",
    "release-checklist-guard",
    "release-evidence",
    "recall-fixtures",
    "roadmap",
    "sleep",
    "vault-setup-guard",
    "verify-mcp",
    "vector",
}


def is_tool_checkout(path: Path) -> bool:
    return (path / "docs" / "schema.md").exists() and (path / "scripts").exists()


def is_memory_vault(path: Path) -> bool:
    return (path / ".ai-dememory.toml").exists() or (path / "memories").exists()


def find_memory_root(start: Path | None = None) -> Path:
    env_root = os.environ.get("AI_DEMEMORY_ROOT")
    if env_root:
        return Path(env_root).resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if is_tool_checkout(candidate) or is_memory_vault(candidate):
            return candidate

    package_root = Path(__file__).resolve().parents[1]
    if is_tool_checkout(package_root):
        return package_root

    raise RuntimeError(
        "Could not locate a ai-dememory vault. "
        "Run from a vault, run `ai-dememory init <path>`, or set AI_DEMEMORY_ROOT."
    )


def configure_imports() -> None:
    """Load command modules from the installed package or trusted tool checkout only."""
    package_root = Path(__file__).resolve().parents[1]
    for package_name in ("ai_dememory_tool.admin", "ai_dememory_tool.mcp_server"):
        package = importlib.import_module(package_name)
        package_paths = getattr(package, "__path__", ())
        for entry in package_paths:
            package_path = Path(entry).resolve()
            try:
                package_path.relative_to(package_root)
            except ValueError as exc:
                raise RuntimeError(f"refusing untrusted command package: {package_name}") from exc


def has_root_arg(argv: list[str]) -> bool:
    return any(arg == "--root" or arg.startswith("--root=") for arg in argv)


def root_arg_value(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--root":
            if index + 1 >= len(argv):
                raise SystemExit("--root requires a path")
            return argv[index + 1]
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return None


def run_packaged_command(command: str, argv: list[str]) -> int:
    explicit_root = root_arg_value(argv)
    configured_root = os.environ.get("AI_DEMEMORY_ROOT")
    if command == "hook-event" and "dispatch" in argv and not (explicit_root or configured_root):
        # Never discover a hook vault from an untrusted project working tree.
        print("{}")
        return 0
    try:
        root = Path(explicit_root).expanduser().resolve() if explicit_root else find_memory_root()
    except RuntimeError:
        if command == "hook-event" and "dispatch" in argv:
            # Lifecycle hooks must remain protocol-valid even before a vault
            # root is configured. Set AI_DEMEMORY_ROOT or generate config with
            # --root to enable recall across unrelated project directories.
            print("{}")
            return 0
        raise
    os.environ["AI_DEMEMORY_ROOT"] = str(root)
    configure_imports()
    if not has_root_arg(argv):
        argv = ["--root", str(root), *argv]
    _, module_name = COMMANDS[command]
    prefix = "ai_dememory_tool.mcp_server" if command == "mcp" else "ai_dememory_tool.admin"
    module = importlib.import_module(f"{prefix}.{module_name}")
    return int(module.main(argv))


def copy_template_tree(target: Path, force: bool = False) -> list[Path]:
    if target.exists() and any(target.iterdir()) and not force:
        raise RuntimeError(f"{target} is not empty. Use --force to add missing vault files.")
    target.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    template_root = resources.files("ai_dememory_tool").joinpath("templates", "vault")
    for source in template_root.rglob("*"):
        relpath = Path(str(source.relative_to(template_root)))
        destination = target / relpath
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not force:
            continue
        with resources.as_file(source) as source_path:
            shutil.copyfile(source_path, destination)
        copied.append(destination)
    return copied


def init_vault(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=LOCAL_COMMANDS["init"])
    parser.add_argument("path", nargs="?", default=".", help="Vault directory to create.")
    parser.add_argument("--force", action="store_true", help="Add or overwrite template files in a non-empty directory.")
    wizard_group = parser.add_mutually_exclusive_group()
    wizard_group.add_argument("--wizard", action="store_true", help="Run the reviewed onboarding wizard after copying the vault.")
    wizard_group.add_argument("--no-wizard", action="store_true", help="Copy only; this is the default for non-interactive setup.")
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser().resolve()
    try:
        copied = copy_template_tree(target, force=args.force)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Initialized ai-dememory vault at {target}")
    print(f"Wrote {len(copied)} file(s).")
    if args.wizard:
        exit_code = run_packaged_command("onboard", ["--root", str(target)])
        if exit_code:
            return exit_code
    else:
        print("Next: run `ai-dememory onboard`, review the preview, then apply it with its `plan_sha256`.")
    print("Then run `ai-dememory doctor` and `ai-dememory index`.")
    return 0


def export_vault_template(target: Path, force: bool = False) -> list[Path]:
    return copy_template_tree(target, force=force)


def vault_template(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=LOCAL_COMMANDS["vault-template"])
    subparsers = parser.add_subparsers(dest="action", required=True)
    export_parser = subparsers.add_parser(
        "export",
        help="Copy the packaged vault template into a GitHub template repo checkout.",
    )
    export_parser.add_argument("path", help="Directory that will contain the vault template files.")
    export_parser.add_argument("--force", action="store_true", help="Add or overwrite files in a non-empty directory.")
    export_parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser().resolve()
    try:
        copied = export_vault_template(target, force=args.force)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "target": str(target),
                    "copied": len(copied),
                    "next_steps": [
                        "Review the exported files.",
                        "Create a separate private GitHub repository.",
                        "Mark the repository as a GitHub template if it will be reused.",
                    ],
                },
                indent=2,
            )
        )
    else:
        print(f"Exported ai-dememory vault template to {target}")
        print(f"Wrote {len(copied)} file(s).")
        print("Next: review the files, create a separate private GitHub repo, and mark it as a template if needed.")
    return 0


def mcp_config(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=LOCAL_COMMANDS["mcp-config"])
    parser.add_argument("--client", choices=("generic", "codex", "claude"), default="generic")
    parser.add_argument("--mode", choices=("installed", "docker"), default="installed")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to the current vault.")
    parser.add_argument("--command", default="ai-dememory", help="Command clients should launch.")
    parser.add_argument("--command-arg", action="append", default=[], help="Extra argument before `mcp --stdio`; repeatable.")
    parser.add_argument("--image", default="ai-dememory:local", help="Docker image for --mode docker.")
    parser.add_argument(
        "--profile",
        choices=MCP_PROFILE_NAMES,
        default=None,
        help="Codex tool profile. Defaults to core for Codex and admin for clients without allowlist support.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else find_memory_root()
    try:
        output = build_mcp_config(
            args.client,
            args.mode,
            root,
            command=args.command,
            command_args=args.command_arg,
            image=args.image,
            profile=args.profile,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(output if isinstance(output, str) else json.dumps(output, indent=2))
    return 0


def build_mcp_config(
    client: str,
    mode: str,
    root: Path,
    command: str = "ai-dememory",
    command_args: list[str] | None = None,
    image: str = "ai-dememory:local",
    profile: str | None = None,
) -> dict[str, object] | str:
    command_args = command_args or []
    resolved_profile = profile or ("core" if client == "codex" else "admin")
    if client != "codex" and resolved_profile != "admin":
        raise ValueError(
            f"MCP profile {resolved_profile!r} is not enforceable for {client}; "
            "use --profile admin or a client-specific tool allowlist"
        )
    if mode == "docker":
        config = {
            "command": "docker",
            "args": [
                "run",
                "--rm",
                "-i",
                "-e",
                "AI_DEMEMORY_ROOT=/memory",
                "-v",
                f"{root}:/memory",
                image,
            ],
            "env": {},
        }
    else:
        config = {
            "command": command,
            "args": [*command_args, "mcp", "--stdio"],
            "env": {"AI_DEMEMORY_ROOT": str(root)},
        }
    enabled_tools = enabled_tools_for_profile(resolved_profile)
    if client == "codex":
        lines = [
            "[mcp_servers.ai-dememory]",
            f"command = {json.dumps(config['command'], ensure_ascii=False)}",
            f"args = {json.dumps(config['args'], ensure_ascii=False)}",
        ]
        if enabled_tools is not None:
            lines.append(f"enabled_tools = {json.dumps(list(enabled_tools), ensure_ascii=False)}")
        env = config.get("env") or {}
        if env:
            lines.append("")
            lines.append("[mcp_servers.ai-dememory.env]")
            for key, value in env.items():
                lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
        output = "\n".join(lines)
    elif client == "claude":
        output = {"mcpServers": {"ai-dememory": config}}
    else:
        output = config
    return output


def usage() -> str:
    lines = [
        "Usage: ai-dememory [--root <vault>] <command> [args...]",
        "",
        "Commands:",
    ]
    for name, description in LOCAL_COMMANDS.items():
        lines.append(f"  {name:<14} {description}")
    for name, (description, _) in COMMANDS.items():
        if name in DEV_COMMANDS:
            continue
        lines.append(f"  {name:<14} {description}")
    lines.append(f"  {'dev':<14} Advanced, CI, release, publishing, and distribution tools.")
    lines.extend(
        [
            "",
            "Examples:",
            "  ai-dememory init ~/code/my-memory",
            "  ai-dememory vault-template export ~/code/ai-dememory-vault-template",
            "  ai-dememory mcp-config --client codex",
            "  ai-dememory setup plan --json",
            "  ai-dememory setup wizard --json",
            "  ai-dememory onboard --input-file onboarding.json --apply --expect-plan-sha256 <preview-sha256> --json",
            "  ai-dememory turn-context \"fix portfolio tracker staging smoke\" --cwd D:/Github/portfolio-tracker --json",
            "  ai-dememory setup health --json",
            "  ai-dememory doctor",
            "  ai-dememory validate",
            "  ai-dememory validate --json",
            "  ai-dememory secret-scan",
            "  ai-dememory index",
            "  ai-dememory graph --json",
            "  ai-dememory search ai-dememory --limit 3",
            "  ai-dememory search ai-dememory --why",
            "  ai-dememory context ai-dememory --budget 2000",
            "  ai-dememory working snapshot --title \"Current task\" --notes \"...\"",
            "  ai-dememory working status --json",
            "  ai-dememory working handoff --title \"Session handoff\" --notes \"...\"",
            "  ai-dememory review false-positives",
            "  ai-dememory review false-positives --due-only",
            "  ai-dememory review stale-false-positives",
            "  ai-dememory review conflicts",
            "  ai-dememory review modes",
            "  ai-dememory review configure-mode --mode balanced --reviewer you",
            "  ai-dememory review plan --kind conflict",
            "  ai-dememory review configure-mode --mode assisted --reviewer you",
            "  ai-dememory review configure-mode --mode autonomous_proposals --reviewer you",
            "  ai-dememory api --host 127.0.0.1 --port 8765",
            "  ai-dememory providers detect",
            "  ai-dememory providers plan --json",
            "  ai-dememory providers configure codex --path ~/.codex",
            "  ai-dememory import-chats codex",
            "  ai-dememory capture markdown --path notes.md",
            "  ai-dememory capture text --stdin --title \"Session note\"",
            "  ai-dememory learn --git --days 7 --repo .",
            "  ai-dememory learn --git --days 7 --repo . --write",
            "  ai-dememory maintenance run --profile daily",
            "  ai-dememory schedule doctor --json",
            "  ai-dememory schedule plan --json",
            "  ai-dememory schedule setup --dry-run",
            "  ai-dememory schedule setup --dry-run --mode docker --image ai-dememory:local",
            "  ai-dememory schedule cron --mode docker --image ai-dememory:local",
            "  ai-dememory hooks config --client codex",
            "  ai-dememory hooks config --client claude",
            "  ai-dememory hooks list",
            "  ai-dememory hooks install --client all --dry-run",
            "  ai-dememory mcp --stdio",
            "  ai-dememory dev --help",
        ]
    )
    return "\n".join(lines)


def dev_usage() -> str:
    lines = [
        "Usage: ai-dememory [--root <vault>] dev <command> [args...]",
        "",
        "Advanced and maintainer commands:",
    ]
    for name in sorted(DEV_COMMANDS):
        lines.append(f"  {name:<24} {COMMANDS[name][0]}")
    lines.extend(
        [
            "",
            "Compatibility: direct forms such as `ai-dememory release-check` remain supported.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    root_override = pop_global_root(argv)
    if root_override:
        os.environ["AI_DEMEMORY_ROOT"] = str(Path(root_override).expanduser().resolve())
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(usage())
        return 0
    if argv[0] == "--version":
        print(f"ai-dememory {__version__}")
        return 0

    command = argv.pop(0)
    if command == "dev":
        if not argv or argv[0] in {"-h", "--help", "help"}:
            print(dev_usage())
            return 0
        command = argv.pop(0)
        if command not in DEV_COMMANDS:
            print(f"Unknown maintainer command: {command}", file=sys.stderr)
            print(dev_usage(), file=sys.stderr)
            return 2
    if command == "init":
        return init_vault(argv)
    if command == "vault-template":
        return vault_template(argv)
    if command == "mcp-config":
        return mcp_config(argv)
    if command == "import-chats":
        argv = ["import", *argv]
    if command == "capture":
        argv = ["capture", *argv]
    if command == "setup" and argv and argv[0] == "wizard":
        command = "onboard"
        argv = argv[1:]
    if command == "mark-seen":
        argv = ["mark-seen", *argv]
    if command == "outcome":
        argv = ["outcome", *argv]
    if command == "lifecycle":
        argv = list(argv)
    if command == "review":
        argv = ["review", *argv]
    if command == "false-positive":
        argv = ["false-positive", *argv]
    if command == "conflict":
        argv = ["conflict", *argv]
    if command not in COMMANDS:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 2

    return run_packaged_command(command, argv)


def pop_global_root(argv: list[str]) -> str | None:
    if not argv:
        return None
    if argv[0] == "--root":
        if len(argv) < 2:
            raise SystemExit("--root requires a path")
        _, value = argv.pop(0), argv.pop(0)
        return value
    if argv[0].startswith("--root="):
        return argv.pop(0).split("=", 1)[1]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
