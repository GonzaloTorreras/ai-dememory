#!/usr/bin/env python3
"""Validate that CI keeps required v2 verification gates."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


WORKFLOW_PATH = Path(".github/workflows/ci.yml")

REQUIRED_COMMANDS = {
    "compile": "python -m compileall -q scripts mcp/server ai_dememory_tool",
    "validate": "python scripts/ai_dememory.py validate",
    "secret_scan": "python scripts/ai_dememory.py secret-scan",
    "verify_mcp": "python scripts/ai_dememory.py verify-mcp",
    "artifact_guard": "python scripts/ai_dememory.py artifact-guard",
    "vault_setup_guard": "python scripts/ai_dememory.py vault-setup-guard",
    "pr_template_guard": "python scripts/ai_dememory.py pr-template-guard",
    "pr_draft_guard": "python scripts/ai_dememory.py pr-draft-guard",
    "acceptance_guard": "python scripts/ai_dememory.py acceptance-guard",
    "adr_guard": "python scripts/ai_dememory.py adr-guard",
    "release_checklist_guard": "python scripts/ai_dememory.py release-checklist-guard",
    "release_check": "python scripts/ai_dememory.py release-check",
    "roadmap_status": "python scripts/ai_dememory.py roadmap status --json",
    "strict_pr_release_check": "python scripts/ai_dememory.py release-check --strict",
    "mcp_smoke": "python scripts/ai_dememory.py mcp-smoke",
    "api_smoke": "python scripts/ai_dememory.py api-smoke",
    "unit_tests": "python -m unittest discover -s tests",
    "index": "python scripts/ai_dememory.py index",
    "search": "python scripts/ai_dememory.py search codex --limit 1",
    "eval_recall": "python scripts/ai_dememory.py eval-recall",
    "install_smoke": "python scripts/ai_dememory.py install-smoke",
    "package_build_smoke": "python scripts/ai_dememory.py package-build-smoke",
    "docker_smoke": "python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:ci",
    "post_smoke_package_build_artifact_guard": "python scripts/ai_dememory.py package-build-smoke --check-clean",
}

FINAL_ARTIFACT_GUARD_NAME = "Final package build artifact guard"
STRICT_PR_RELEASE_CHECK_NAME = "Strict PR release readiness check"
MCP_RUNTIME_SMOKE_NAME = "MCP runtime smoke"


@dataclass(frozen=True)
class CiGuardIssue:
    target: str
    message: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_step_block(text: str, step_name: str) -> str | None:
    marker = f"- name: {step_name}"
    start = text.find(marker)
    if start == -1:
        return None
    next_step = text.find("\n      - ", start + len(marker))
    if next_step == -1:
        return text[start:]
    return text[start:next_step]


def step_has_pr_gate_and_url(step: str) -> bool:
    has_pr_gate = "github.event_name == 'pull_request'" in step or 'github.event_name == "pull_request"' in step
    return has_pr_gate and "AI_DEMEMORY_PR_URL" in step and "github.event.pull_request.html_url" in step


def validate_ci_workflow(root: Path) -> list[CiGuardIssue]:
    path = root / WORKFLOW_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [CiGuardIssue(str(WORKFLOW_PATH), "CI workflow is missing")]
    return validate_ci_workflow_text(text)


def validate_ci_workflow_text(text: str) -> list[CiGuardIssue]:
    issues: list[CiGuardIssue] = []
    compact = normalize(text)
    if not re.search(r"(?m)^on:\s*$", text):
        issues.append(CiGuardIssue("ci.yml:on", "workflow must declare triggers"))
    if "pull_request:" not in text:
        issues.append(CiGuardIssue("ci.yml:on", "workflow must run on pull_request"))
    if "push:" not in text or "main" not in text:
        issues.append(CiGuardIssue("ci.yml:on", "workflow must run on pushes to main"))
    if "python-version: \"3.12\"" not in text and "python-version: '3.12'" not in text:
        issues.append(CiGuardIssue("ci.yml:python", "workflow must use Python 3.12"))
    for name, command in REQUIRED_COMMANDS.items():
        if normalize(command) not in compact:
            issues.append(CiGuardIssue(f"ci.yml:{name}", f"missing required command: {command}"))
    docker_index = compact.find(normalize(REQUIRED_COMMANDS["docker_smoke"]))
    final_name_index = compact.find(normalize(FINAL_ARTIFACT_GUARD_NAME))
    final_command_index = compact.find(normalize(REQUIRED_COMMANDS["post_smoke_package_build_artifact_guard"]))
    if final_name_index == -1:
        issues.append(
            CiGuardIssue(
                "ci.yml:final_artifact_guard",
                f"missing required post-smoke step name: {FINAL_ARTIFACT_GUARD_NAME}",
            )
        )
    elif docker_index == -1 or final_name_index < docker_index or final_command_index < docker_index:
        issues.append(
            CiGuardIssue(
                "ci.yml:final_artifact_guard",
                "final package build artifact guard must run after Docker local MCP smoke",
            )
        )
    mcp_name_index = compact.find(normalize(MCP_RUNTIME_SMOKE_NAME))
    mcp_command_index = compact.find(normalize(REQUIRED_COMMANDS["mcp_smoke"]))
    release_check_index = compact.find(normalize(REQUIRED_COMMANDS["release_check"]))
    strict_release_check_index = compact.find(normalize(REQUIRED_COMMANDS["strict_pr_release_check"]))
    api_smoke_index = compact.find(normalize(REQUIRED_COMMANDS["api_smoke"]))
    index_index = compact.find(normalize(REQUIRED_COMMANDS["index"]))
    search_index = compact.find(normalize(REQUIRED_COMMANDS["search"]))
    eval_recall_index = compact.find(normalize(REQUIRED_COMMANDS["eval_recall"]))
    install_smoke_index = compact.find(normalize(REQUIRED_COMMANDS["install_smoke"]))
    strict_release_name_index = compact.find(normalize(STRICT_PR_RELEASE_CHECK_NAME))
    strict_release_step = find_step_block(text, STRICT_PR_RELEASE_CHECK_NAME)
    mcp_step = find_step_block(text, MCP_RUNTIME_SMOKE_NAME)
    if strict_release_name_index == -1:
        issues.append(
            CiGuardIssue(
                "ci.yml:strict_pr_release_check",
                f"missing required PR-gated step name: {STRICT_PR_RELEASE_CHECK_NAME}",
            )
        )
    elif strict_release_step is None or not step_has_pr_gate_and_url(strict_release_step):
        issues.append(
            CiGuardIssue(
                "ci.yml:strict_pr_release_check",
                "Strict PR release readiness check must run only on pull_request events and set AI_DEMEMORY_PR_URL from the pull request URL",
            )
        )
    if mcp_name_index == -1:
        issues.append(CiGuardIssue("ci.yml:mcp_smoke", f"missing required PR-gated step name: {MCP_RUNTIME_SMOKE_NAME}"))
    elif mcp_step is None or not step_has_pr_gate_and_url(mcp_step):
        issues.append(
            CiGuardIssue(
                "ci.yml:mcp_smoke",
                "MCP runtime smoke must run only on pull_request events and set AI_DEMEMORY_PR_URL from the pull request URL",
            )
        )
    if (
        mcp_name_index != -1
        and mcp_command_index != -1
        and release_check_index != -1
        and strict_release_check_index != -1
        and api_smoke_index != -1
        and index_index != -1
        and search_index != -1
        and eval_recall_index != -1
        and install_smoke_index != -1
        and not (
            release_check_index
            < api_smoke_index
            < index_index
            < search_index
            < eval_recall_index
            < strict_release_check_index
            < mcp_name_index
            <= mcp_command_index
            < install_smoke_index
        )
    ):
        issues.append(
            CiGuardIssue(
                "ci.yml:mcp_smoke",
                "strict PR release-check and MCP runtime smoke must run after index/search/recall smoke and before install smoke",
            )
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_ci_workflow(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"CI workflow guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("CI workflow guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
