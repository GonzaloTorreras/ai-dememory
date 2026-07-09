#!/usr/bin/env python3
"""Validate that the draft PR handoff runbook is reusable and current."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


DRAFT_PATH = Path("docs/pr-draft.md")

REQUIRED_HEADINGS = {
    "title": "# Draft PR Handoff",
    "required_fields": "## Required Fields",
    "body_template": "## Body Template",
    "validation": "## Validation Commands",
    "safety": "## Safety Notes",
    "after": "## After The Draft PR Exists",
}

REQUIRED_SNIPPETS = {
    "draft_pr": "Draft PR",
    "stacked_on": "Stacked on",
    "do_not_merge": "Do not merge",
    "summary": "## Summary",
    "tests": "## Tests",
    "notes": "## Notes",
    "pr_url_env": "AI_DEMEMORY_PR_URL",
    "pr_placeholder": "pull/<number>",
    "pr_draft_guard": "python3 scripts/ai_dememory.py pr-draft-guard",
    "pr_template_guard": "python3 scripts/ai_dememory.py pr-template-guard",
    "release_check_strict": "python3 scripts/ai_dememory.py release-check --strict",
    "mcp_smoke": "python3 scripts/ai_dememory.py mcp-smoke",
}

FORBIDDEN_SNIPPETS = {
    "old_pr_url": "pull/1",
    "old_title": "[codex] Build memory MVP toolchain",
    "published_pr": "Published PR",
    "ready_statement": "marked ready for review",
}


@dataclass(frozen=True)
class DraftGuardIssue:
    target: str
    message: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_pr_draft_text(text: str) -> list[DraftGuardIssue]:
    issues: list[DraftGuardIssue] = []
    normalized = normalize(text)
    for name, heading in REQUIRED_HEADINGS.items():
        if heading not in text:
            issues.append(DraftGuardIssue(f"pr_draft:{name}", f"missing heading: {heading}"))
    for name, snippet in REQUIRED_SNIPPETS.items():
        if normalize(snippet) not in normalized:
            issues.append(DraftGuardIssue(f"pr_draft:{name}", f"missing required snippet: {snippet}"))
    for name, snippet in FORBIDDEN_SNIPPETS.items():
        if snippet in text:
            issues.append(DraftGuardIssue(f"pr_draft:{name}", f"stale PR-specific text is not allowed: {snippet}"))
    return issues


def validate_pr_draft(root: Path) -> list[DraftGuardIssue]:
    path = root / DRAFT_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [DraftGuardIssue(str(DRAFT_PATH), "draft PR handoff runbook is missing")]
    return validate_pr_draft_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_pr_draft(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"PR draft guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("PR draft guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
