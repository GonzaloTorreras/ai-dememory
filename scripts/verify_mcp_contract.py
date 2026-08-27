#!/usr/bin/env python3
"""Statically validate the local MCP server contract definitions."""

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
# the first package import; retrying after a failed import would leave that old
# package cached in sys.modules. Installed namespaced execution already has the
# authoritative package path and must not select a checkout this way.
if not __package__:
    source_root = Path(__file__).resolve().parents[1]
    if (source_root / "ai_dememory_tool").is_dir():
        # Insert unconditionally. A caller-controlled PYTHONPATH may already
        # contain this checkout after a stale or shadow package; membership is
        # not proof of import precedence.
        sys.path.insert(0, str(source_root))

from ai_dememory_tool.argument_safety import reject_duplicate_options


TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
REQUIRED_CAPABILITIES = {"tools", "resources", "prompts"}
TASK_SUPPORT_VALUES = {"forbidden", "optional", "required"}


@dataclass(frozen=True)
class ContractIssue:
    target: str
    message: str


def load_server(_legacy_root: Path | None = None) -> Any:
    """Load the contract from the active package, independent of a repository."""
    from ai_dememory_tool.mcp_server import memory_mcp

    return memory_mcp


def validate_object_schema(target: str, schema: Any) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if not isinstance(schema, dict):
        return [ContractIssue(target, "schema must be an object")]
    if schema.get("type") != "object":
        issues.append(ContractIssue(target, "schema.type must be object"))
    if not isinstance(schema.get("properties"), dict):
        issues.append(ContractIssue(target, "schema.properties must be an object"))
    if "additionalProperties" not in schema:
        issues.append(ContractIssue(target, "schema.additionalProperties must be explicit"))
    required = schema.get("required", [])
    if required is not None and not isinstance(required, list):
        issues.append(ContractIssue(target, "schema.required must be a list when present"))
    return issues


def validate_tools(tools: Any) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if not isinstance(tools, list) or not tools:
        return [ContractIssue("TOOLS", "must be a non-empty list")]

    seen: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict):
            issues.append(ContractIssue("TOOLS", "tool entries must be objects"))
            continue
        name = tool.get("name")
        target = f"tool:{name}"
        if not isinstance(name, str) or not TOOL_NAME_RE.fullmatch(name):
            issues.append(ContractIssue(target, "invalid MCP tool name"))
        elif name in seen:
            issues.append(ContractIssue(target, "duplicate tool name"))
        else:
            seen.add(name)
        if not isinstance(tool.get("description"), str) or not tool["description"].strip():
            issues.append(ContractIssue(target, "description is required"))
        issues.extend(validate_object_schema(f"{target}.inputSchema", tool.get("inputSchema")))
        if "outputSchema" in tool:
            issues.extend(validate_object_schema(f"{target}.outputSchema", tool.get("outputSchema")))
        annotations = tool.get("annotations")
        if not isinstance(annotations, dict):
            issues.append(ContractIssue(target, "annotations must be present"))
        else:
            for field in ("readOnlyHint", "destructiveHint", "openWorldHint"):
                if not isinstance(annotations.get(field), bool):
                    issues.append(ContractIssue(target, f"annotations.{field} must be boolean"))
        execution = tool.get("execution")
        if not isinstance(execution, dict) or execution.get("taskSupport") not in TASK_SUPPORT_VALUES:
            issues.append(ContractIssue(target, "execution.taskSupport must be valid"))
    return issues


def validate_prompts(prompts: Any) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if not isinstance(prompts, list) or not prompts:
        return [ContractIssue("PROMPTS", "must be a non-empty list")]
    seen: set[str] = set()
    for prompt in prompts:
        if not isinstance(prompt, dict):
            issues.append(ContractIssue("PROMPTS", "prompt entries must be objects"))
            continue
        name = prompt.get("name")
        target = f"prompt:{name}"
        if not isinstance(name, str) or not TOOL_NAME_RE.fullmatch(name):
            issues.append(ContractIssue(target, "invalid prompt name"))
        elif name in seen:
            issues.append(ContractIssue(target, "duplicate prompt name"))
        else:
            seen.add(name)
        if not isinstance(prompt.get("description"), str) or not prompt["description"].strip():
            issues.append(ContractIssue(target, "description is required"))
        arguments = prompt.get("arguments", [])
        if not isinstance(arguments, list):
            issues.append(ContractIssue(target, "arguments must be a list"))
    return issues


def validate_capabilities(capabilities: Any) -> list[ContractIssue]:
    if not isinstance(capabilities, dict):
        return [ContractIssue("SERVER_CAPABILITIES", "must be an object")]
    missing = sorted(REQUIRED_CAPABILITIES - set(capabilities))
    if missing:
        return [ContractIssue("SERVER_CAPABILITIES", "missing " + ", ".join(missing))]
    return []


def validate_contract(_legacy_root: Path | None = None) -> list[ContractIssue]:
    """Validate the active package; the optional root remains a compatibility no-op."""
    server = load_server()
    issues: list[ContractIssue] = []
    issues.extend(validate_capabilities(getattr(server, "SERVER_CAPABILITIES", None)))
    issues.extend(validate_tools(getattr(server, "TOOLS", None)))
    issues.extend(validate_prompts(getattr(server, "PROMPTS", None)))
    return issues


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--root",
        default=None,
        help="Legacy compatibility value; ignored because the contract comes from the active package.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    reject_duplicate_options(parser, arguments, ("--root",))
    args = parser.parse_args(arguments)

    if args.root is not None and not args.root.strip():
        parser.error("--root requires a non-empty compatibility value")
    issues = validate_contract()
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"MCP contract validation found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("MCP contract validation passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
