#!/usr/bin/env python3
"""Validate that the pull request template includes current v2 gates."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


TEMPLATE_PATH = Path(".github/pull_request_template.md")

REQUIRED_SNIPPETS = {
    "doctor": "python3 scripts/ai_dememory.py doctor",
    "verify_mcp": "python3 scripts/ai_dememory.py verify-mcp",
    "mcp_inventory": "python3 scripts/ai_dememory.py mcp-inventory --check-docs",
    "ci_guard": "python3 scripts/ai_dememory.py ci-guard",
    "artifact_guard": "python3 scripts/ai_dememory.py artifact-guard",
    "vault_setup_guard": "python3 scripts/ai_dememory.py vault-setup-guard",
    "pr_template_guard": "python3 scripts/ai_dememory.py pr-template-guard",
    "pr_draft_guard": "python3 scripts/ai_dememory.py pr-draft-guard",
    "acceptance_guard": "python3 scripts/ai_dememory.py acceptance-guard",
    "adr_guard": "python3 scripts/ai_dememory.py adr-guard",
    "release_checklist_guard": "python3 scripts/ai_dememory.py release-checklist-guard",
    "release_check": "python3 scripts/ai_dememory.py release-check",
    "roadmap_status": "python3 scripts/ai_dememory.py roadmap status --json",
    "api_smoke": "python3 scripts/ai_dememory.py api-smoke",
    "validate": "python3 scripts/ai_dememory.py validate",
    "secret_scan": "python3 scripts/ai_dememory.py secret-scan",
    "eval_recall": "python3 scripts/ai_dememory.py eval-recall",
    "install_smoke": "python3 scripts/ai_dememory.py install-smoke",
    "package_build_smoke": "python3 scripts/ai_dememory.py package-build-smoke",
    "unit_tests": "python3 -m unittest discover -s tests",
    "compileall": "python3 -m compileall -q scripts mcp/server ai_dememory_tool",
    "pr_gate": "AI_DEMEMORY_PR_URL",
    "mcp_smoke": "python3 scripts/ai_dememory.py mcp-smoke",
    "mcp_client_smoke": "python3 scripts/ai_dememory.py mcp-client-smoke",
    "generated_artifacts": "No generated SQLite, reports, caches, or distilled context outputs are staged",
}

REQUIRED_HEADINGS = {
    "summary": "## Summary",
    "validation": "## Validation",
    "runtime": "## MCP Runtime",
    "safety": "## Safety",
}


@dataclass(frozen=True)
class TemplateGuardIssue:
    target: str
    message: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_template_text(text: str) -> list[TemplateGuardIssue]:
    issues: list[TemplateGuardIssue] = []
    normalized = normalize(text)
    for name, heading in REQUIRED_HEADINGS.items():
        if heading not in text:
            issues.append(TemplateGuardIssue(f"pull_request_template:{name}", f"missing heading: {heading}"))
    for name, snippet in REQUIRED_SNIPPETS.items():
        if normalize(snippet) not in normalized:
            issues.append(
                TemplateGuardIssue(
                    f"pull_request_template:{name}",
                    f"missing required validation snippet: {snippet}",
                )
            )
    return issues


def validate_pr_template(root: Path) -> list[TemplateGuardIssue]:
    path = root / TEMPLATE_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [TemplateGuardIssue(str(TEMPLATE_PATH), "pull request template is missing")]
    return validate_template_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_pr_template(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"PR template guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("PR template guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
