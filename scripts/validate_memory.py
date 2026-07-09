#!/usr/bin/env python3
"""Validate Markdown memory frontmatter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from memorylib import repo_root, validate_memories
from review_memory import ReviewError, conflict_reviews, review_policy_config


def validate_repo_result(root: Path) -> dict[str, object]:
    documents, errors = validate_memories(root)
    if errors:
        return {
            "ok": False,
            "exit_code": 1,
            "memory_count": 0,
            "messages": [],
            "errors": errors,
            "conflict_review": {"available": False, "status": "not_run"},
        }

    messages = [f"Validated {len(documents)} memory file(s)."]
    conflict_review: dict[str, object]
    try:
        policy = review_policy_config(root)
        conflict_policy = policy["conflicts"]
        if conflict_policy["enabled"] and conflict_policy["scan_on_validate"]:
            conflicts = conflict_reviews(root)
            active = [item for item in conflicts if item.status == "active"]
            conflict_review = {
                "available": True,
                "status": "scanned",
                "conflicts": len(conflicts),
                "active_conflicts": len(active),
                "blocking": False,
            }
            messages.append(
                "Conflict review scan: "
                f"{len(conflicts)} conflict(s), {len(active)} active "
                "(non-blocking)."
            )
        elif not conflict_policy["enabled"]:
            conflict_review = {
                "available": True,
                "status": "disabled",
                "conflicts": None,
                "active_conflicts": None,
                "blocking": False,
            }
            messages.append("Conflict review scan: disabled by policy.")
        else:
            conflict_review = {
                "available": True,
                "status": "skipped",
                "conflicts": None,
                "active_conflicts": None,
                "blocking": False,
            }
            messages.append("Conflict review scan: skipped by policy.")
    except ReviewError as exc:
        return {
            "ok": False,
            "exit_code": 1,
            "memory_count": len(documents),
            "messages": messages,
            "errors": [f"Conflict review scan failed: {exc}"],
            "conflict_review": {
                "available": False,
                "status": "failed",
                "errors": str(exc).splitlines(),
                "blocking": True,
            },
        }
    return {
        "ok": True,
        "exit_code": 0,
        "memory_count": len(documents),
        "messages": messages,
        "errors": [],
        "conflict_review": conflict_review,
    }


def validate_repo(root: Path) -> tuple[int, list[str]]:
    result = validate_repo_result(root)
    messages = list(result["errors"] if result["errors"] else result["messages"])
    return int(result["exit_code"]), [str(message) for message in messages]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit structured validation output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    result = validate_repo_result(root)
    exit_code = int(result["exit_code"])
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        messages = result["errors"] if result["errors"] else result["messages"]
        stream = sys.stderr if exit_code else sys.stdout
        for message in messages:
            print(message, file=stream)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
