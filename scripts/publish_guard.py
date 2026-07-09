#!/usr/bin/env python3
"""Validate that package publishing stays manual and uses Trusted Publishing."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


WORKFLOW_PATH = Path(".github/workflows/publish.yml")
REQUIRED_PREFLIGHT_COMMANDS = (
    "python -m compileall -q scripts mcp/server ai_dememory_tool",
    "python scripts/ai_dememory.py publish-guard",
    "python scripts/ai_dememory.py artifact-guard",
    "python scripts/ai_dememory.py validate",
    "python scripts/ai_dememory.py secret-scan",
    "python scripts/ai_dememory.py verify-mcp",
    "python scripts/ai_dememory.py release-check",
    "python scripts/ai_dememory.py install-smoke",
    "python scripts/ai_dememory.py package-build-smoke --check-clean",
    "python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:publish",
    'python scripts/ai_dememory.py publish-plan --repository "$PUBLISH_REPOSITORY" --pr-url "$AI_DEMEMORY_PR_URL" --strict',
)


@dataclass(frozen=True)
class PublishGuardIssue:
    target: str
    message: str


def leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def workflow_dispatch_input_block(text: str, input_name: str) -> str | None:
    lines = text.splitlines()
    workflow_indent: int | None = None
    inputs_indent: int | None = None
    input_indent: int | None = None
    block: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if input_indent is not None:
                block.append(line)
            continue
        indent = leading_spaces(line)
        if stripped == "workflow_dispatch:":
            workflow_indent = indent
            inputs_indent = None
            input_indent = None
            block = []
            continue
        if workflow_indent is None:
            continue
        if indent <= workflow_indent:
            break
        if inputs_indent is None:
            if stripped == "inputs:" and indent > workflow_indent:
                inputs_indent = indent
            continue
        if indent <= inputs_indent:
            break
        if input_indent is None:
            if stripped == f"{input_name}:":
                input_indent = indent
                block = [line]
            continue
        if indent <= input_indent:
            break
        block.append(line)
    return "\n".join(block) if input_indent is not None else None


def workflow_dispatch_input_required(text: str, input_name: str) -> bool:
    block = workflow_dispatch_input_block(text, input_name)
    return block is not None and bool(re.search(r"(?m)^\s+required:\s*true\s*$", block))


def yaml_mapping_block(text: str, key: str) -> str | None:
    lines = text.splitlines()
    block_indent: int | None = None
    block: list[str] = []
    for line in lines:
        stripped = line.strip()
        if block_indent is None:
            if stripped == f"{key}:":
                block_indent = leading_spaces(line)
                block = [line]
            continue
        if stripped and leading_spaces(line) <= block_indent:
            break
        block.append(line)
    return "\n".join(block) if block_indent is not None else None


def validate_publish_workflow(root: Path) -> list[PublishGuardIssue]:
    path = root / WORKFLOW_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [PublishGuardIssue(str(WORKFLOW_PATH), "publish workflow is missing")]
    return validate_publish_workflow_text(text)


def validate_publish_workflow_text(text: str) -> list[PublishGuardIssue]:
    issues: list[PublishGuardIssue] = []
    if not re.search(r"(?m)^on:\s*$", text):
        issues.append(PublishGuardIssue("publish.yml:on", "workflow must declare triggers"))
    if "workflow_dispatch:" not in text:
        issues.append(PublishGuardIssue("publish.yml:on", "workflow must be manually dispatched"))
    if re.search(r"(?m)^\s+(push|pull_request|schedule):\s*$", text):
        issues.append(PublishGuardIssue("publish.yml:on", "publish workflow must not run on push, PR, or schedule"))
    if "confirm:" not in text or "inputs.confirm != 'publish'" not in text:
        issues.append(PublishGuardIssue("publish.yml:confirm", "publish workflow must require confirm=publish"))
    if not workflow_dispatch_input_required(text, "pr_url"):
        issues.append(
            PublishGuardIssue(
                "publish.yml:pr_url",
                "publish workflow must define workflow_dispatch.inputs.pr_url with required=true",
            )
        )
    preflight_block = yaml_mapping_block(text, "preflight")
    if preflight_block is None or "AI_DEMEMORY_PR_URL: ${{ inputs.pr_url }}" not in preflight_block:
        issues.append(PublishGuardIssue("publish.yml:pr_url", "publish preflight must set AI_DEMEMORY_PR_URL from the PR URL input"))
    if preflight_block is None or "PUBLISH_REPOSITORY: ${{ inputs.repository }}" not in preflight_block:
        issues.append(PublishGuardIssue("publish.yml:repository", "publish preflight must expose repository input to strict publish planning"))
    if "repository:" not in text or "testpypi" not in text or "pypi" not in text:
        issues.append(PublishGuardIssue("publish.yml:repository", "workflow must choose testpypi or pypi"))
    if "environment: testpypi" not in text:
        issues.append(PublishGuardIssue("publish.yml:testpypi", "TestPyPI publish job must use environment testpypi"))
    if "environment: pypi" not in text:
        issues.append(PublishGuardIssue("publish.yml:pypi", "PyPI publish job must use environment pypi"))
    if text.count("id-token: write") < 2:
        issues.append(PublishGuardIssue("publish.yml:trusted-publishing", "publish jobs must request id-token: write"))
    if "pypa/gh-action-pypi-publish" not in text:
        issues.append(PublishGuardIssue("publish.yml:publisher", "workflow must use pypa/gh-action-pypi-publish"))
    if "repository-url: https://test.pypi.org/legacy/" not in text:
        issues.append(PublishGuardIssue("publish.yml:testpypi", "TestPyPI job must publish to TestPyPI legacy URL"))
    if re.search(r"(?im)^\s*(password|api[_-]?token|pypi[_-]?token)\s*:", text):
        issues.append(PublishGuardIssue("publish.yml:secrets", "workflow must not configure stored PyPI tokens"))
    if "python -m build" not in text or "python -m twine check dist/*" not in text:
        issues.append(PublishGuardIssue("publish.yml:build", "workflow must build and twine-check distributions"))
    if "preflight:" not in text or "needs: preflight" not in text:
        issues.append(PublishGuardIssue("publish.yml:preflight", "build job must depend on preflight verification"))
    for command in REQUIRED_PREFLIGHT_COMMANDS:
        if command not in text:
            issues.append(
                PublishGuardIssue(
                    "publish.yml:preflight",
                    f"missing required pre-publish command: {command}",
                )
            )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_publish_workflow(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"Publish workflow guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("Publish workflow guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
