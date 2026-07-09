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


def configure_imports(root: Path) -> None:
    for path in (root / "scripts", root / "mcp" / "server"):
        if path.exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
    for package_name in ("scripts", "mcp.server"):
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            continue
        package_file = getattr(package, "__file__", None)
        if package_file:
            package_path = Path(package_file).resolve().parent
            if str(package_path) not in sys.path:
                sys.path.insert(0, str(package_path))


def has_root_arg(argv: list[str]) -> bool:
    return any(arg == "--root" or arg.startswith("--root=") for arg in argv)


def run_packaged_command(command: str, argv: list[str]) -> int:
    root = find_memory_root()
    os.environ.setdefault("AI_DEMEMORY_ROOT", str(root))
    configure_imports(root)
    if not has_root_arg(argv):
        argv = ["--root", str(root), *argv]
    _, module_name = COMMANDS[command]
    module = __import__(module_name)
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
    args = parser.parse_args(argv)

    target = Path(args.path).expanduser().resolve()
    try:
        copied = copy_template_tree(target, force=args.force)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Initialized ai-dememory vault at {target}")
    print(f"Wrote {len(copied)} file(s).")
    print("Next: cd into the vault, then run `ai-dememory doctor` and `ai-dememory index`.")
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
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else find_memory_root()
    output = build_mcp_config(
        args.client,
        args.mode,
        root,
        command=args.command,
        command_args=args.command_arg,
        image=args.image,
    )
    print(json.dumps(output, indent=2))
    return 0


def build_mcp_config(
    client: str,
    mode: str,
    root: Path,
    command: str = "ai-dememory",
    command_args: list[str] | None = None,
    image: str = "ai-dememory:local",
) -> dict[str, object]:
    command_args = command_args or []
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
    if client == "codex":
        output = {"mcpServers": {"ai-dememory": config}}
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
        lines.append(f"  {name:<14} {description}")
    lines.extend(
        [
            "",
            "Examples:",
            "  ai-dememory init ~/code/my-memory",
            "  ai-dememory vault-template export ~/code/ai-dememory-vault-template",
            "  ai-dememory mcp-config --client codex",
            "  ai-dememory setup plan --json",
            "  ai-dememory setup health --json",
            "  ai-dememory mcp-client-smoke",
            "  ai-dememory doctor",
            "  ai-dememory mcp-inventory --check-docs",
            "  ai-dememory install-smoke --skip-package --docker",
            "  ai-dememory package-build-smoke",
            "  ai-dememory publish-guard",
            "  ai-dememory ci-guard",
            "  ai-dememory artifact-guard",
            "  ai-dememory vault-setup-guard",
            "  ai-dememory pr-template-guard",
            "  ai-dememory pr-draft-guard",
            "  ai-dememory acceptance-guard",
            "  ai-dememory adr-guard",
            "  ai-dememory release-checklist-guard",
            "  ai-dememory release-evidence --write-report",
            "  ai-dememory roadmap status --json",
            "  ai-dememory acceptance status",
            "  ai-dememory acceptance verify",
            "  ai-dememory api-smoke",
            "  ai-dememory validate",
            "  ai-dememory validate --json",
            "  ai-dememory secret-scan",
            "  ai-dememory index",
            "  ai-dememory graph --json",
            "  ai-dememory eval-recall",
            "  ai-dememory recall-fixtures status --json",
            "  ai-dememory recall-fixtures check-miss --query \"missed query\" --expected-id mem_example --json",
            "  ai-dememory recall-fixtures promote-miss --miss inbox/recall-feedback/example.md --reviewed-by you",
            "  ai-dememory recall-fixtures review-miss --miss inbox/recall-feedback/example.md --status rejected --reviewed-by you --reason \"obsolete\"",
            "  ai-dememory vector status --json",
            "  ai-dememory provenance --json",
            "  ai-dememory search ai-dememory --limit 3",
            "  ai-dememory search ai-dememory --why",
            "  ai-dememory context ai-dememory --budget 2000",
            "  ai-dememory working snapshot --title \"Current task\" --notes \"...\"",
            "  ai-dememory working status --json",
            "  ai-dememory working handoff --title \"Session handoff\" --notes \"...\"",
            "  ai-dememory mark-seen --id mem_example --query codex",
            "  ai-dememory outcome --last --good",
            "  ai-dememory lifecycle scores --json",
            "  ai-dememory lifecycle report",
            "  ai-dememory sleep plan",
            "  ai-dememory sleep apply-reviewed --all",
            "  ai-dememory review false-positives",
            "  ai-dememory review false-positives --due-only",
            "  ai-dememory review stale-false-positives",
            "  ai-dememory review conflicts",
            "  ai-dememory review modes",
            "  ai-dememory review configure-mode --mode balanced --reviewer you",
            "  ai-dememory review plan --kind conflict",
            "  ai-dememory review configure-mode --mode assisted --reviewer you",
            "  ai-dememory review configure-mode --mode autonomous_proposals --reviewer you",
            "  ai-dememory conflict resolve --id conf_... --merge-proposal --reviewer you",
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
