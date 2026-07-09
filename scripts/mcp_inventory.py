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

from memorylib import repo_root


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


def load_server(root: Path) -> Any:
    server_dir = root / "mcp" / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
    import memory_mcp  # type: ignore

    return memory_mcp


def build_inventory(root: Path) -> dict[str, Any]:
    server = load_server(root)
    tools = sorted(tool["name"] for tool in server.TOOLS)
    prompts = sorted(prompt["name"] for prompt in server.PROMPTS)
    resource_templates = [
        template["uriTemplate"]
        for template in server.list_resource_templates()["resourceTemplates"]
    ]
    return {
        "protocol_versions": list(server.SUPPORTED_PROTOCOL_VERSIONS),
        "capabilities": sorted(server.SERVER_CAPABILITIES.keys()),
        "tool_count": len(tools),
        "tools": tools,
        "prompt_count": len(prompts),
        "prompts": prompts,
        "resource_templates": sorted(resource_templates),
    }


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--check-docs", action="store_true", help="Validate docs against the server inventory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    if args.check_docs:
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

    inventory = build_inventory(root)
    if args.json:
        print(json.dumps(inventory, indent=2))
    else:
        print(f"MCP inventory: {inventory['tool_count']} MCP tools")
        for tool_name in inventory["tools"]:
            print(f"- {tool_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
