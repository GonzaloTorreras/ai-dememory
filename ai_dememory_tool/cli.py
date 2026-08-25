"""Unified command entry point for the local memory toolchain."""

from __future__ import annotations

import argparse
from functools import wraps
import importlib
from importlib import resources
import json
from pathlib import Path
import os
import shutil
import stat
import sys

from ai_dememory_tool import __version__
from ai_dememory_tool.argument_safety import (
    duplicate_options,
    reject_duplicate_options,
    validate_docker_image_argument,
)
from ai_dememory_tool.mcp_profiles import (
    DEFAULT_MCP_IDLE_TIMEOUT_SECONDS,
    MCP_PROFILE_NAMES,
    enabled_tools_for_profile,
    normalize_mcp_idle_timeout_seconds,
)
from ai_dememory_tool.vault_binding import (
    VaultBindingError,
    clear_default_vault,
    load_default_vault,
    resolve_runtime_vault,
    save_default_vault,
)


RUNTIME_VAULT_ROOT_HELP = (
    "Vault root. Resolution order: --root, AI_DEMEMORY_ROOT, then a saved local "
    "default selected with `ai-dememory vault use <absolute-vault-path>`; the command never "
    "uses the working directory to discover a vault."
)


LOCAL_COMMANDS = {
    "init": "Create a new private memory vault.",
    "vault": "Select, inspect, or clear the default private memory vault.",
    "mcp-config": "Print MCP client configuration for a memory vault.",
    "vault-template": "Export the private vault GitHub template tree.",
    "version-check": "Fail unless the installed package matches an exact release.",
}

COMMANDS = {
    "doctor": ("Run local readiness checks.", "doctor"),
    "verify-mcp": ("Statically validate MCP contract definitions.", "verify_mcp_contract"),
    "mcp-inventory": ("Report and validate documented MCP tool inventory.", "mcp_inventory"),
    "release-check": ("Run non-runtime v2 release readiness checks.", "release_check"),
    "install-smoke": ("Run fresh package and local Docker install smoke checks.", "install_smoke"),
    "package-build-smoke": ("Build package distributions in temp space and run twine check.", "package_build_smoke"),
    "publish-guard": ("Validate the canonical tag publisher and legacy read-only preflight.", "publish_guard"),
    "publish-plan": ("Plan TestPyPI/PyPI readiness without publishing packages.", "publish_plan"),
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


def _path_entry_status(path: Path) -> os.stat_result | None:
    """Inspect one local directory entry without following its final link."""
    try:
        return path.lstat()
    except (OSError, ValueError):
        return None


def _is_reparse_point(status: os.stat_result) -> bool:
    attributes = getattr(status, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _is_local_regular_file(path: Path) -> bool:
    status = _path_entry_status(path)
    return bool(
        status is not None
        and stat.S_ISREG(status.st_mode)
        and not _is_reparse_point(status)
    )


def _is_local_directory(path: Path) -> bool:
    status = _path_entry_status(path)
    return bool(
        status is not None
        and stat.S_ISDIR(status.st_mode)
        and not _is_reparse_point(status)
    )


def _has_vault_manifest(path: Path) -> bool:
    return _is_local_regular_file(path / ".ai-dememory.toml")


def _has_git_marker(path: Path) -> bool:
    # Presence is enough to make a nested ambient root ambiguous. Never open a
    # .git pointer, config, include, UNC path, symlink, reparse point, or device.
    return _path_entry_status(path / ".git") is not None


def _is_source_project_tree(path: Path) -> bool:
    """Recognize full or partial ai-dememory source trees without remote I/O."""
    if not _is_local_regular_file(path / "pyproject.toml"):
        return False
    package_dir = path / "ai_dememory_tool"
    scripts_dir = path / "scripts"
    return (
        _is_local_directory(package_dir)
        and _is_local_regular_file(package_dir / "cli.py")
    ) or (
        _is_local_directory(scripts_dir)
        and _is_local_regular_file(scripts_dir / "ai_dememory.py")
    )


def is_tool_checkout(path: Path) -> bool:
    """Return whether *path* has the local shape of an ai-dememory source tree."""
    try:
        resolved = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return _is_source_project_tree(resolved)


def is_within_tool_checkout(path: Path) -> bool:
    """Return whether ``path`` resolves to a tool checkout or one of its descendants."""
    try:
        resolved = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return any(is_tool_checkout(candidate) for candidate in (resolved, *resolved.parents))


def ambient_root_requires_explicit_binding(path: Path) -> bool:
    """Fail closed for unconfigured or nested roots used by persistent flows."""
    try:
        resolved = path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return True
    if not _has_vault_manifest(resolved) or is_within_tool_checkout(resolved):
        return True
    # A standalone Git-backed vault is valid. A vault nested inside any other
    # checkout is ambiguous and must be selected deliberately.
    return any(_has_git_marker(parent) for parent in resolved.parents)


def is_memory_vault(path: Path) -> bool:
    return (path / ".ai-dememory.toml").exists() or (path / "memories").exists()


def find_memory_root(start: Path | None = None) -> Path:
    env_root = root_binding_value(os.environ.get("AI_DEMEMORY_ROOT"))
    if env_root:
        return Path(env_root).expanduser().resolve()

    current = (start or Path.cwd()).expanduser().resolve()
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


def root_binding_value(value: str | None) -> str | None:
    """Return a root value only when it names more than whitespace.

    Keep nonblank values verbatim: spaces can be part of a valid path.  A
    whitespace-only argument/environment value would otherwise resolve to the
    current directory and turn an ambient checkout into an apparent binding.
    """
    return value if value is not None and value.strip() else None


def root_arg_value(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--root":
            if index + 1 >= len(argv):
                raise SystemExit("--root requires a path")
            return argv[index + 1]
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return None


def cli_argument_error(message: str) -> None:
    print(f"ai-dememory: error: {message}", file=sys.stderr)
    raise SystemExit(2)


def command_subcommand(argv: list[str]) -> str | None:
    """Return the first command token after an optional global root binding."""
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in {"--root", "--command"}:
            index += 2
            continue
        if argument.startswith(("--root=", "--command=")):
            index += 1
            continue
        if argument.startswith("-"):
            return None
        return argument
    return None


def command_mutates_vault(command: str, argv: list[str]) -> bool:
    """Identify persistent packaged flows before ambient root discovery."""
    if command in {"setup", "onboard", "capture"}:
        return True
    if command == "import-chats":
        return "--dry-run" not in argv
    subcommand = command_subcommand(argv)
    if command == "providers":
        return subcommand == "capture" or (
            subcommand in {"configure", "import"} and "--dry-run" not in argv
        )
    if command == "maintenance":
        return subcommand == "run" and "--dry-run" not in argv
    return False


def provider_command_requires_explicit_vault_binding(command: str, argv: list[str]) -> bool:
    """Identify provider flows that must never infer a vault from the CWD."""
    if command in {"import-chats", "capture"}:
        return True
    return command == "providers" and command_subcommand(argv) in {
        "plan",
        "configure",
        "import",
        "capture",
    }


def command_emits_bound_vault_command(command: str, argv: list[str]) -> bool:
    """Identify read-only command surfaces and stateful runs that need a bound vault."""
    subcommand = command_subcommand(argv)
    if command == "maintenance":
        return subcommand in {"run", "status"}
    if command == "providers":
        return subcommand == "plan" or (
            subcommand == "configure" and "--dry-run" in argv
        )
    return False


def command_requires_explicit_vault_binding(command: str, argv: list[str]) -> bool:
    """Require a binding before a command writes or prints a durable root."""
    return (
        provider_command_requires_explicit_vault_binding(command, argv)
        or command_mutates_vault(command, argv)
        or command_emits_bound_vault_command(command, argv)
    )


def run_packaged_command(
    command: str,
    argv: list[str],
    *,
    onboarding_mode: str | None = None,
) -> int:
    if onboarding_mode is not None and command != "onboard":
        raise ValueError("onboarding_mode is valid only for the internal onboarding command")
    if command in {
        "mcp",
        "api",
        "hook-event",
        "hooks",
        "setup",
        "onboard",
        "providers",
        "import-chats",
        "capture",
        "maintenance",
        "schedule",
    }:
        # Runtime, provider, maintenance, onboarding, and scheduler surfaces
        # own parsing and vault resolution (or an explicitly rootless path).
        # In particular, never discover a
        # CWD/package root, resolve a user path, or rewrite provider arguments
        # before the provider parser has accepted its exact grammar.  Resolving
        # a UNC path can perform I/O, and rewriting a trailing ``--root`` would
        # turn an invalid provider command into a valid one.
        configure_imports()
        _, module_name = COMMANDS[command]
        prefix = "ai_dememory_tool.mcp_server" if command == "mcp" else "ai_dememory_tool.admin"
        module = importlib.import_module(f"{prefix}.{module_name}")
        if command == "onboard":
            return int(module.main(argv, mode=onboarding_mode or "onboard"))
        return int(module.main(argv))
    raw_explicit_root = root_arg_value(argv)
    if raw_explicit_root is not None and not raw_explicit_root.strip():
        cli_argument_error("--root requires a non-empty vault path")
    explicit_root = root_binding_value(raw_explicit_root)
    configured_root = root_binding_value(os.environ.get("AI_DEMEMORY_ROOT"))
    if command == "hook-event" and "dispatch" in argv and not (explicit_root or configured_root):
        # Never discover a hook vault from an untrusted project working tree.
        print("{}")
        return 0
    used_default_binding = False
    try:
        if explicit_root:
            root = Path(explicit_root).expanduser().resolve()
        elif configured_root:
            root = Path(configured_root).expanduser().resolve()
        else:
            # An explicitly saved default is more intentional than an
            # arbitrary working directory. Existing CWD discovery remains
            # available only before a user chooses a default or after clear.
            default_binding = load_default_vault()
            if default_binding is not None:
                root = default_binding.root
                used_default_binding = True
            else:
                root = find_memory_root()
    except VaultBindingError as exc:
        # A malformed/stale selector is an explicit local configuration error;
        # do not quietly fall through to a checkout or a different CWD vault.
        cli_argument_error(str(exc))
    except RuntimeError:
        if command == "hook-event" and "dispatch" in argv:
            # Lifecycle hooks must remain protocol-valid even before a vault
            # root is configured. Set AI_DEMEMORY_ROOT or generate config with
            # --root to enable recall across unrelated project directories.
            print("{}")
            return 0
        raise
    if (
        command_requires_explicit_vault_binding(command, argv)
        and not (explicit_root or configured_root or used_default_binding)
        and ambient_root_requires_explicit_binding(root)
    ):
        cli_argument_error(
            f"{command} refuses an unconfigured or nested ambient root; "
            "pass --root <vault-path>, set AI_DEMEMORY_ROOT, or save a local "
            "default with `ai-dememory vault use <absolute-vault-path>`; the "
            "working directory is not a runtime binding"
        )
    # Some legacy command modules still inspect AI_DEMEMORY_ROOT. Keep their
    # invocation compatible without making a saved default sticky in a
    # long-running host process: selector changes must affect the next command.
    had_previous_root = "AI_DEMEMORY_ROOT" in os.environ
    previous_root = os.environ.get("AI_DEMEMORY_ROOT")
    os.environ["AI_DEMEMORY_ROOT"] = str(root)
    try:
        configure_imports()
        if not has_root_arg(argv):
            argv = ["--root", str(root), *argv]
        _, module_name = COMMANDS[command]
        prefix = "ai_dememory_tool.mcp_server" if command == "mcp" else "ai_dememory_tool.admin"
        module = importlib.import_module(f"{prefix}.{module_name}")
        if command == "onboard":
            return int(module.main(argv, mode=onboarding_mode or "onboard"))
        return int(module.main(argv))
    finally:
        if had_previous_root:
            os.environ["AI_DEMEMORY_ROOT"] = previous_root or ""
        else:
            os.environ.pop("AI_DEMEMORY_ROOT", None)


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
    parser = argparse.ArgumentParser(description=LOCAL_COMMANDS["init"], allow_abbrev=False)
    parser.add_argument("path", nargs="?", default=".", help="Vault directory to create.")
    parser.add_argument("--force", action="store_true", help="Add or overwrite template files in a non-empty directory.")
    wizard_group = parser.add_mutually_exclusive_group()
    wizard_group.add_argument("--wizard", action="store_true", help="Run the fingerprint-bound operational setup wizard after copying the vault.")
    wizard_group.add_argument("--no-wizard", action="store_true", help="Copy only; this is the default for non-interactive setup.")
    parser.add_argument(
        "--require-version",
        metavar="VERSION",
        help=argparse.SUPPRESS,
    )
    reject_duplicate_options(parser, argv, ("--require-version", "--wizard", "--no-wizard"))
    args = parser.parse_args(argv)

    if args.require_version is not None and not args.wizard:
        print("--require-version is valid only with --wizard", file=sys.stderr)
        return 2

    target = Path(args.path).expanduser().resolve()
    try:
        copied = copy_template_tree(target, force=args.force)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Initialized ai-dememory vault at {target}")
    print(f"Wrote {len(copied)} file(s).")
    if args.wizard:
        return run_packaged_command(
            "onboard",
            ["--root", str(target)],
            onboarding_mode="operational",
        )
    from ai_dememory_tool.admin.command_render import render_copy_command

    setup_command = render_copy_command(
        ["ai-dememory", "--root", str(target), "setup", "wizard"]
    )
    doctor_command = render_copy_command(
        ["ai-dememory", "--root", str(target), "doctor"]
    )
    health_command = render_copy_command(
        ["ai-dememory", "--root", str(target), "setup", "health", "--json"]
    )
    index_command = render_copy_command(
        ["ai-dememory", "--root", str(target), "index"]
    )
    print("Vault creation is complete; no further command is required.")
    print(
        "Optional configuration: run "
        f"`{setup_command}` to preview one config-only plan before any explicit apply."
    )
    print(
        "Optional diagnostics (not setup steps): "
        f"`{doctor_command}` or `{health_command}`."
    )
    print(
        "Optional search: after you add or review Markdown that you want searchable, "
        f"run `{index_command}`."
    )
    return 0


def vault_command(argv: list[str]) -> int:
    """Manage the one explicit host-local default vault selector."""
    parser = argparse.ArgumentParser(
        prog="ai-dememory vault",
        description=LOCAL_COMMANDS["vault"],
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    use = subparsers.add_parser(
        "use",
        help="Validate an absolute vault path and select it for future commands.",
        allow_abbrev=False,
    )
    use.add_argument("path", help="Absolute path of an initialized private vault.")
    use.add_argument("--json", action="store_true", help="Emit JSON output.")
    current = subparsers.add_parser(
        "current",
        help="Show the selected default vault without changing it.",
        allow_abbrev=False,
    )
    current.add_argument("--json", action="store_true", help="Emit JSON output.")
    clear = subparsers.add_parser(
        "clear",
        help="Clear the local default-vault selection.",
        allow_abbrev=False,
    )
    clear.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    try:
        if args.action == "use":
            binding = save_default_vault(args.path)
            payload = {
                "configured": True,
                "root": str(binding.root),
                "source": binding.source,
            }
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(f"Default vault selected: {binding.root}")
            return 0

        if args.action == "current":
            binding = load_default_vault()
            payload = {
                "configured": binding is not None,
                "root": str(binding.root) if binding is not None else None,
                "source": binding.source if binding is not None else None,
            }
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            elif binding is None:
                print("No default vault is selected.")
            else:
                print(f"Default vault: {binding.root}")
            return 0

        cleared = clear_default_vault()
        payload = {"cleared": cleared}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        elif cleared:
            print("Default vault selection cleared.")
        else:
            print("No default vault is selected.")
        return 0
    except VaultBindingError as exc:
        parser.error(str(exc))
    return 2  # Unreachable, but retains a total return contract for type checkers.


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
    parser = argparse.ArgumentParser(description=LOCAL_COMMANDS["mcp-config"], allow_abbrev=False)
    parser.add_argument("--client", choices=("generic", "codex", "claude"), default="generic")
    parser.add_argument("--mode", choices=("installed", "docker"), default="installed")
    parser.add_argument(
        "--root",
        default=None,
        help=RUNTIME_VAULT_ROOT_HELP,
    )
    parser.add_argument("--command", default="ai-dememory", help="Command clients should launch.")
    parser.add_argument("--command-arg", action="append", default=[], help="Extra argument before `mcp --stdio`; repeatable.")
    parser.add_argument("--image", default="ai-dememory:local", help="Docker image for --mode docker.")
    parser.add_argument(
        "--require-version",
        metavar="VERSION",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--profile",
        choices=MCP_PROFILE_NAMES,
        default=None,
        help="Server-enforced tool profile. Generated configs default to core for every client.",
    )
    parser.add_argument(
        "--idle-timeout-seconds",
        type=int,
        default=DEFAULT_MCP_IDLE_TIMEOUT_SECONDS,
        help=(
            "Stop an idle MCP process after this many seconds. "
            f"Default: {DEFAULT_MCP_IDLE_TIMEOUT_SECONDS}; use 0 only for an intentionally persistent server."
        ),
    )
    reject_duplicate_options(
        parser,
        argv,
        (
            "--client",
            "--mode",
            "--root",
            "--command",
            "--image",
            "--require-version",
            "--profile",
            "--idle-timeout-seconds",
        ),
    )
    args = parser.parse_args(argv)

    try:
        root = resolve_runtime_vault(args.root).root
    except VaultBindingError as exc:
        parser.error(str(exc))
    try:
        output = build_mcp_config(
            args.client,
            args.mode,
            root,
            command=args.command,
            command_args=args.command_arg,
            image=args.image,
            profile=args.profile,
            idle_timeout_seconds=args.idle_timeout_seconds,
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
    idle_timeout_seconds: int = DEFAULT_MCP_IDLE_TIMEOUT_SECONDS,
) -> dict[str, object] | str:
    command_args = list(command_args or [])
    if mode == "docker":
        image = validate_docker_image_argument(image)
    reserved_command_args = {
        "mcp",
        "--root",
        "--stdio",
        "--idle-timeout-seconds",
        "--require-version",
        "--profile",
        "--require-bound-root",
    }
    for argument in command_args:
        if argument in reserved_command_args or any(
            argument.startswith(f"{flag}=")
            for flag in reserved_command_args
            if flag.startswith("--")
        ):
            raise ValueError(
                f"--command-arg cannot override reserved MCP argument {argument!r}"
            )
    resolved_profile = profile or "core"
    idle_timeout_seconds = normalize_mcp_idle_timeout_seconds(idle_timeout_seconds)
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
                "mcp",
                "--stdio",
                "--idle-timeout-seconds",
                str(idle_timeout_seconds),
                "--profile",
                resolved_profile,
                "--require-bound-root",
            ],
            "env": {},
        }
    else:
        config = {
            "command": command,
            "args": [
                *command_args,
                "mcp",
                "--stdio",
                "--idle-timeout-seconds",
                str(idle_timeout_seconds),
                "--profile",
                resolved_profile,
                "--require-bound-root",
            ],
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
            "  ai-dememory init ~/code/my-memory --wizard",
            "  ai-dememory vault use ~/code/my-memory",
            "  ai-dememory vault current",
            "  ai-dememory --root ~/code/my-memory mcp-config --client codex",
            "  ai-dememory --root ~/code/my-memory index",
            "  ai-dememory --root ~/code/my-memory search ai-dememory --limit 3",
            "  ai-dememory --root ~/code/my-memory doctor",
            "  ai-dememory vault-template export ~/code/ai-dememory-vault-template",
            "",
            "Runtime vault selection: --root, AI_DEMEMORY_ROOT, then the saved local default ",
            "(`ai-dememory vault use <absolute-vault-path>`); it does not discover a vault from the working directory.",
            "",
            "Use `ai-dememory <command> --help` for a focused command reference.",
            "Use `ai-dememory dev --help` for CI, release, and maintainer tools.",
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


def _restore_root_environment(callback):
    """Keep CLI calls safe to reuse inside a long-running Python host."""
    @wraps(callback)
    def wrapped(*args, **kwargs):
        had_previous_root = "AI_DEMEMORY_ROOT" in os.environ
        previous_root = os.environ.get("AI_DEMEMORY_ROOT")
        try:
            return callback(*args, **kwargs)
        finally:
            if had_previous_root:
                os.environ["AI_DEMEMORY_ROOT"] = previous_root or ""
            else:
                os.environ.pop("AI_DEMEMORY_ROOT", None)

    return wrapped


@_restore_root_environment
def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if duplicate_options(argv, ("--root",)):
        print("--root may be specified at most once", file=sys.stderr)
        return 2
    raw_root_override = pop_global_root(argv)
    if raw_root_override is not None and not raw_root_override.strip():
        cli_argument_error("--root requires a non-empty vault path")
    root_override = root_binding_value(raw_root_override)
    if root_override:
        # Preserve the textual binding until the selected subcommand has
        # validated its arguments. Resolving a UNC path can perform I/O.
        os.environ["AI_DEMEMORY_ROOT"] = root_override
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(usage())
        return 0
    if argv[0] == "--version":
        print(f"ai-dememory {__version__}")
        return 0
    if argv[0] == "--require-version" or argv[0].startswith("--require-version="):
        print(
            "--require-version is a legacy subcommand option, not a top-level command. "
            "It is no longer needed for installation, the wizard, or generated MCP configuration. "
            "Use `ai-dememory --version` or `ai-dememory version-check <expected-version>` "
            "for an explicit diagnostic.",
            file=sys.stderr,
        )
        return 2

    command = argv.pop(0)
    onboarding_mode: str | None = None
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
    if command == "vault":
        return vault_command(argv)
    if command == "version-check":
        parser = argparse.ArgumentParser(prog="ai-dememory version-check")
        parser.add_argument("expected_version")
        args = parser.parse_args(argv)
        if args.expected_version != __version__:
            print(
                f"ai-dememory version mismatch: expected {args.expected_version}, found {__version__}",
                file=sys.stderr,
            )
            return 1
        print(f"ai-dememory {__version__}")
        return 0
    if command == "vault-template":
        return vault_template(argv)
    if command == "mcp-config":
        return mcp_config(argv)
    if command == "import-chats":
        argv = ["import", *argv]
    if command == "capture":
        argv = ["capture", *argv]
    if command == "setup":
        wizard_index = 0
        if argv and argv[0] == "--root":
            wizard_index = 2
        elif argv and argv[0].startswith("--root="):
            wizard_index = 1
        if len(argv) > wizard_index and argv[wizard_index] == "wizard":
            command = "onboard"
            onboarding_mode = "operational"
            del argv[wizard_index]
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

    if onboarding_mode is not None:
        return run_packaged_command(command, argv, onboarding_mode=onboarding_mode)
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
