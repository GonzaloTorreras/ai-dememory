#!/usr/bin/env python3
"""Capture a recall miss for human review."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from memorylib import repo_relative_path, repo_root, slugify
from secret_scan import scan_text


MAX_FIELD_CHARS = 4000


def safe_recall_feedback_dir(root: Path) -> Path:
    root = root.resolve()
    inbox = root / "inbox"
    capture_dir = inbox / "recall-feedback"
    for component in (inbox, capture_dir):
        if component.is_symlink():
            raise ValueError("recall feedback path must not contain symlinks")
        if component.exists():
            try:
                component.resolve().relative_to(root)
            except ValueError as exc:
                raise ValueError("recall feedback path must stay inside the memory root") from exc

    capture_dir.mkdir(parents=True, exist_ok=True)
    for component in (inbox, capture_dir):
        if component.is_symlink():
            raise ValueError("recall feedback path must not contain symlinks")
        try:
            component.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("recall feedback path must stay inside the memory root") from exc
    return capture_dir


def frontmatter_scalar(value: str | None) -> str:
    if value is None or value == "":
        return "null"
    clean = " ".join(str(value).splitlines()).strip().replace('"', "'")
    return json.dumps(clean)


def validate_miss_fields(
    query: str,
    reason: str,
    expected_id: str | None = None,
    expected_path: str | None = None,
) -> tuple[str, str]:
    query = query.strip()
    reason = reason.strip()
    if not query:
        raise ValueError("query is required")
    if not reason:
        raise ValueError("reason is required")
    if bool(expected_id) == bool(expected_path):
        raise ValueError("provide exactly one of expected_id or expected_path")
    if len(query) > MAX_FIELD_CHARS or len(reason) > MAX_FIELD_CHARS:
        raise ValueError(f"query and reason must be at most {MAX_FIELD_CHARS} characters")

    scan_target = f"query: {query}\nreason: {reason}\nexpected_id: {expected_id or ''}\nexpected_path: {expected_path or ''}\n"
    if scan_text(scan_target, "<capture-miss>"):
        raise ValueError("recall miss rejected by secret scan")
    return query, reason


def render_miss_text(
    query: str,
    reason: str,
    expected_id: str | None = None,
    expected_path: str | None = None,
    source_ref: str | None = None,
    created_at: str | None = None,
) -> str:
    query, reason = validate_miss_fields(query, reason, expected_id, expected_path)
    created_at = created_at or datetime.now(timezone.utc).date().isoformat()
    expected_label = expected_id or expected_path or ""
    text = f"""---
type: recall-miss
status: proposed
created_at: {created_at}
query: {frontmatter_scalar(query)}
expected_id: {frontmatter_scalar(expected_id)}
expected_path: {frontmatter_scalar(expected_path)}
source_ref: {frontmatter_scalar(source_ref or "capture-miss")}
---

# Recall Miss: {query}

- expected: `{expected_label}`
- reason: {reason}

Review this miss before adding or changing `quality/recall-fixtures.json`.
"""
    if scan_text(text, "<capture-miss.rendered>"):
        raise ValueError("recall miss rejected by rendered secret scan")
    return text


def capture_miss(
    root: Path,
    query: str,
    reason: str,
    expected_id: str | None = None,
    expected_path: str | None = None,
    source_ref: str | None = None,
) -> Path:
    query, _ = validate_miss_fields(query, reason, expected_id, expected_path)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    slug = slugify(query, "recall-miss")
    capture_dir = safe_recall_feedback_dir(root)
    path = capture_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}_{slug}.md"
    if path.exists() or path.is_symlink():
        raise ValueError("recall miss path already exists")
    text = render_miss_text(query, reason, expected_id, expected_path, source_ref, now.date().isoformat())
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--query", required=True, help="Search query that missed expected memory.")
    parser.add_argument("--reason", required=True, help="Why the result was insufficient.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--expected-id", help="Memory id that should have been returned.")
    group.add_argument("--expected-path", help="Memory path that should have been returned.")
    parser.add_argument("--source-ref", default=None, help="Optional source reference.")
    parser.add_argument("--dry-run", action="store_true", help="Render the recall miss without writing a file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        if args.dry_run:
            text = render_miss_text(
                args.query,
                args.reason,
                expected_id=args.expected_id,
                expected_path=args.expected_path,
                source_ref=args.source_ref,
            )
            if args.json:
                print(json.dumps({"writes_files": False, "markdown": text}, indent=2))
            else:
                print(text, end="")
            return 0
        path = capture_miss(
            root,
            args.query,
            args.reason,
            expected_id=args.expected_id,
            expected_path=args.expected_path,
            source_ref=args.source_ref,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    relpath = repo_relative_path(path, root)
    if args.json:
        print(json.dumps({"writes_files": True, "path": relpath}, indent=2))
    else:
        print(f"Wrote {relpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
