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

from memorylib import repo_root


TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
REQUIRED_CAPABILITIES = {"tools", "resources", "prompts"}
TASK_SUPPORT_VALUES = {"forbidden", "optional", "required"}


@dataclass(frozen=True)
class ContractIssue:
    target: str
    message: str


def load_server(root: Path) -> Any:
    server_dir = root / "mcp" / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
    import memory_mcp  # type: ignore

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


def validate_contract(root: Path) -> list[ContractIssue]:
    server = load_server(root)
    issues: list[ContractIssue] = []
    issues.extend(validate_capabilities(getattr(server, "SERVER_CAPABILITIES", None)))
    issues.extend(validate_tools(getattr(server, "TOOLS", None)))
    issues.extend(validate_prompts(getattr(server, "PROMPTS", None)))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_contract(root)
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
