#!/usr/bin/env python3
"""Validate that manual acceptance docs match the canonical item registry."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from manual_acceptance import ACCEPTANCE_ITEMS
from memorylib import repo_root


CHECKLIST_PATH = Path("docs/release-v2-checklist.md")


@dataclass(frozen=True)
class AcceptanceGuardIssue:
    target: str
    message: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def manual_acceptance_section(text: str) -> str:
    marker = "## Manual Acceptance"
    start = text.find(marker)
    if start == -1:
        return ""
    next_heading = text.find("\n## ", start + len(marker))
    return text[start:] if next_heading == -1 else text[start:next_heading]


def validate_acceptance_checklist_text(text: str) -> list[AcceptanceGuardIssue]:
    issues: list[AcceptanceGuardIssue] = []
    section = manual_acceptance_section(text)
    if not section:
        return [AcceptanceGuardIssue(str(CHECKLIST_PATH), "missing Manual Acceptance section")]
    normalized = normalize(section)
    for item_id, description in ACCEPTANCE_ITEMS.items():
        if f"`{item_id}`" not in section:
            issues.append(AcceptanceGuardIssue(f"manual_acceptance:{item_id}", f"missing item id `{item_id}`"))
        if normalize(description) not in normalized:
            issues.append(
                AcceptanceGuardIssue(
                    f"manual_acceptance:{item_id}",
                    f"missing canonical description: {description}",
                )
            )
    if "ai-dememory acceptance record --item <item-id>" not in normalized:
        issues.append(
            AcceptanceGuardIssue(
                "manual_acceptance:record_command",
                "missing acceptance record command with --item <item-id>",
            )
        )
    return issues


def validate_acceptance_checklist(root: Path) -> list[AcceptanceGuardIssue]:
    path = root / CHECKLIST_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [AcceptanceGuardIssue(str(CHECKLIST_PATH), "release checklist is missing")]
    return validate_acceptance_checklist_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_acceptance_checklist(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"Acceptance guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("Acceptance guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
