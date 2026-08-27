#!/usr/bin/env python3
"""Report and validate the documented MCP server inventory."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any

# A direct source-script invocation starts with ``scripts/`` on sys.path. Put
# this script's own checkout ahead of an older installed ai_dememory_tool before
# the first package import. Installed namespaced execution already has the
# authoritative package path and must not select a checkout this way.
if not __package__:
    source_root = Path(__file__).resolve().parents[1]
    if (source_root / "ai_dememory_tool").is_dir():
        sys.path.insert(0, str(source_root))

from ai_dememory_tool.argument_safety import reject_duplicate_options
from ai_dememory_tool.mcp_profiles import MCP_PROFILE_NAMES, enabled_tools_for_profile


INVENTORY_DOCS = (
    "README.md",
    "docs/adr/0010-mcp-inventory-drift-check.md",
    "docs/adr/0088-mcp-client-tools-list-pagination-smoke.md",
    "docs/mcp-v2-gap-analysis.md",
    "mcp/README.md",
    "mcp/server/README.md",
)

TOOL_LIST_DOCS = (
    "README.md",
    "mcp/README.md",
)

MCP_TOOL_TOKEN_RE = re.compile(r"`(memory\.[A-Za-z0-9_]+)`")


@dataclass(frozen=True)
class InventoryIssue:
    target: str
    message: str


def load_server(_legacy_root: Path | None = None) -> Any:
    """Load the canonical server definitions from the active package."""
    from ai_dememory_tool.mcp_server import memory_mcp

    return memory_mcp


def build_inventory(_legacy_root: Path | None = None) -> dict[str, Any]:
    """Build package metadata without consulting a vault or source checkout."""
    server = load_server()
    tools = sorted(tool["name"] for tool in server.TOOLS)
    tool_definitions = {tool["name"]: tool for tool in server.TOOLS}
    prompts = sorted(prompt["name"] for prompt in server.PROMPTS)
    resource_templates = [
        template["uriTemplate"]
        for template in server.list_resource_templates()["resourceTemplates"]
    ]
    profiles: dict[str, dict[str, Any]] = {}
    for profile_name in MCP_PROFILE_NAMES:
        profile_tools = enabled_tools_for_profile(profile_name, tools) or ()
        missing = sorted(set(profile_tools) - set(tools))
        selected = [tool_definitions[name] for name in profile_tools if name in tool_definitions]
        schema_bytes = len(json.dumps(selected, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        profiles[profile_name] = {
            "tool_count": len(profile_tools),
            "schema_bytes": schema_bytes,
            "estimated_schema_tokens": (schema_bytes + 3) // 4,
            "tools": list(profile_tools),
            "missing_tools": missing,
        }
    return {
        "protocol_versions": list(server.SUPPORTED_PROTOCOL_VERSIONS),
        "capabilities": sorted(server.SERVER_CAPABILITIES.keys()),
        "tool_count": len(tools),
        "tools": tools,
        "profiles": profiles,
        "prompt_count": len(prompts),
        "prompts": prompts,
        "resource_templates": sorted(resource_templates),
    }


def resolve_inventory_docs_root(value: str | Path | None = None) -> Path:
    """Resolve only the source tree used by the explicit documentation check.

    The default is the checkout containing this module. An explicit path must
    be absolute after ``~`` expansion. Deliberately ignore ``AI_DEMEMORY_ROOT``,
    the saved vault selector, and CWD: none is source-code authority.
    """
    if value is None:
        return Path(__file__).resolve().parents[1]
    text = str(value)
    if not text.strip():
        raise ValueError("--root requires a non-empty source path")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        raise ValueError("--root requires an absolute source path for --check-docs")
    return candidate.resolve(strict=False)


def validate_inventory_docs(root: Path) -> list[InventoryIssue]:
    inventory = build_inventory(root)
    issues: list[InventoryIssue] = []
    documents: dict[str, str] = {}
    for relpath in INVENTORY_DOCS:
        path = root / relpath
        try:
            documents[relpath] = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            issues.append(InventoryIssue(relpath, "missing MCP inventory documentation"))
    issues.extend(validate_inventory_texts(inventory, documents))
    return issues


def validate_inventory_texts(inventory: dict[str, Any], documents: dict[str, str]) -> list[InventoryIssue]:
    issues: list[InventoryIssue] = []
    expected_count = f"{inventory['tool_count']} MCP tools"
    for relpath in INVENTORY_DOCS:
        text = documents.get(relpath)
        if text is None:
            continue
        if expected_count not in text:
            issues.append(InventoryIssue(relpath, f"must mention `{expected_count}`"))
    for relpath in TOOL_LIST_DOCS:
        text = documents.get(relpath, "")
        documented_tools = set(MCP_TOOL_TOKEN_RE.findall(text))
        for tool_name in inventory["tools"]:
            if tool_name not in documented_tools:
                issues.append(InventoryIssue(relpath, f"missing tool `{tool_name}`"))
    return issues


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--root",
        default=None,
        help=(
            "Absolute source-checkout root for --check-docs. Ignored by "
            "package-derived inventory output for compatibility."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-docs",
        action="store_true",
        help="Validate source documentation against the packaged server inventory.",
    )
    mode.add_argument("--profile", choices=MCP_PROFILE_NAMES, help="Report one client tool profile.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    reject_duplicate_options(parser, arguments, ("--root", "--check-docs", "--profile", "--json"))
    args = parser.parse_args(arguments)

    if args.root is not None and not args.root.strip():
        parser.error("--root requires a non-empty compatibility value")

    if args.check_docs:
        try:
            root = resolve_inventory_docs_root(args.root)
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        issues = validate_inventory_docs(root)
        if args.json:
            print(json.dumps([asdict(issue) for issue in issues], indent=2))
        elif issues:
            print(f"MCP inventory docs have {len(issues)} issue(s):", file=sys.stderr)
            for issue in issues:
                print(f"{issue.target}: {issue.message}", file=sys.stderr)
        else:
            print("MCP inventory docs are current.")
        return 1 if issues else 0

    inventory = build_inventory()
    if args.profile:
        inventory = {"profile": args.profile, **inventory["profiles"][args.profile]}
    if args.json:
        print(json.dumps(inventory, indent=2))
    else:
        if args.profile:
            print(
                f"MCP profile {args.profile}: {inventory['tool_count']} tools, "
                f"{inventory['schema_bytes']} schema bytes, "
                f"~{inventory['estimated_schema_tokens']} schema tokens"
            )
            for tool_name in inventory["tools"]:
                print(f"- {tool_name}")
        else:
            print(f"MCP inventory: {inventory['tool_count']} MCP tools")
            for profile_name, profile in inventory["profiles"].items():
                print(
                    f"- {profile_name}: {profile['tool_count']} tools, "
                    f"{profile['schema_bytes']} schema bytes, "
                    f"~{profile['estimated_schema_tokens']} schema tokens"
                )
            for tool_name in inventory["tools"]:
                print(f"- {tool_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
