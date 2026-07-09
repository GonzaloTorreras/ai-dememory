#!/usr/bin/env python3
"""Generate a dry-run consolidation report for memory review."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys

from memorylib import (
    MemoryDocument,
    extract_summary,
    parse_date,
    repo_relative_path,
    repo_root,
    today,
    validate_memories,
)
from review_memory import ReviewError, conflict_reviews, review_policy_config
from secret_scan import scan_paths, scan_text


DEFAULT_REPORT = Path("reports/consolidation-dry-run.md")


def build_report(root: Path) -> str:
    documents, errors = validate_memories(root)
    if errors:
        raise RuntimeError("memory validation failed:\n" + "\n".join(errors))

    targets = [repo_relative_path(document.path, root) for document in documents]
    findings = scan_paths(root, targets)
    if findings:
        formatted = "\n".join(
            f"{finding.path}:{finding.line}: {finding.kind}: {finding.redacted_line}"
            for finding in findings
        )
        raise RuntimeError(f"secret scan failed before consolidation:\n{formatted}")

    now = today()
    by_title: dict[str, list[MemoryDocument]] = defaultdict(list)
    by_alias: dict[str, list[MemoryDocument]] = defaultdict(list)
    for document in documents:
        by_title[document.frontmatter["title"].strip().lower()].append(document)
        for alias in document.frontmatter.get("aliases", []):
            by_alias[alias.strip().lower()].append(document)

    duplicate_titles = {title: docs for title, docs in by_title.items() if len(docs) > 1}
    duplicate_aliases = {alias: docs for alias, docs in by_alias.items() if alias and len(docs) > 1}
    review_due = [
        document
        for document in documents
        if parse_date(document.frontmatter["review_after"]) <= now
        and document.frontmatter["status"] == "active"
    ]
    low_confidence = [
        document for document in documents if float(document.frontmatter["confidence"]) < 0.65
    ]
    missing_review_provenance = [
        document
        for document in documents
        if document.frontmatter["type"] == "durable"
        and (
            document.frontmatter.get("reviewed") is not True
            or not document.frontmatter.get("reviewed_by")
            or not document.frontmatter.get("reviewed_at")
        )
    ]
    disputed = [document for document in documents if document.frontmatter["status"] == "disputed"]
    stale = [document for document in documents if document.frontmatter["status"] == "stale"]
    conflict_scan = consolidation_conflict_scan(root)
    inbox_files = sorted((root / "inbox").rglob("*.md")) if (root / "inbox").exists() else []
    inbox_files = [path for path in inbox_files if path.name != "README.md"]

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# Consolidation Dry Run",
        "",
        f"Generated at: {generated_at}",
        "",
        "No memory files were modified.",
        "",
        "## Summary",
        "",
        f"- memory files: {len(documents)}",
        f"- inbox proposals: {len(inbox_files)}",
        f"- duplicate titles: {len(duplicate_titles)}",
        f"- duplicate aliases: {len(duplicate_aliases)}",
        f"- review due: {len(review_due)}",
        f"- low confidence: {len(low_confidence)}",
        f"- missing review provenance: {len(missing_review_provenance)}",
        f"- disputed: {len(disputed)}",
        f"- stale: {len(stale)}",
        f"- conflict scan: `{conflict_scan['status']}`",
        f"- conflicts: {conflict_scan['conflicts']}",
        f"- active conflicts: {conflict_scan['active_conflicts']}",
        "",
    ]

    add_group(lines, "Inbox Proposals", [repo_relative_path(path, root) for path in inbox_files])
    add_conflict_scan_group(lines, conflict_scan)
    add_duplicate_group(lines, "Duplicate Titles", duplicate_titles, root)
    add_duplicate_group(lines, "Duplicate Aliases", duplicate_aliases, root)
    add_document_group(lines, "Review Due", review_due, root)
    add_document_group(lines, "Low Confidence", low_confidence, root)
    add_document_group(lines, "Missing Review Provenance", missing_review_provenance, root)
    add_document_group(lines, "Disputed", disputed, root)
    add_document_group(lines, "Stale", stale, root)
    return "\n".join(lines)


def consolidation_conflict_scan(root: Path) -> dict[str, object]:
    try:
        policy = review_policy_config(root)["conflicts"]
        if not policy["enabled"]:
            return {
                "status": "disabled",
                "conflicts": 0,
                "active_conflicts": 0,
                "active_ids": [],
                "message": "Conflict review scan disabled by policy.",
            }
        if not policy["scan_on_consolidate"]:
            return {
                "status": "skipped",
                "conflicts": 0,
                "active_conflicts": 0,
                "active_ids": [],
                "message": "Conflict review scan skipped by policy.",
            }
        conflicts = conflict_reviews(root)
    except ReviewError as exc:
        raise RuntimeError(f"conflict review scan failed before consolidation:\n{exc}") from exc
    active = [item for item in conflicts if item.status == "active"]
    return {
        "status": "scanned",
        "conflicts": len(conflicts),
        "active_conflicts": len(active),
        "active_ids": [item.id for item in active[:20]],
        "message": "Conflict review scan completed without mutating memory.",
    }


def add_conflict_scan_group(lines: list[str], scan: dict[str, object]) -> None:
    lines.extend(["## Conflict Review Scan", ""])
    lines.extend(
        [
            f"- status: `{scan['status']}`",
            f"- conflicts: {scan['conflicts']}",
            f"- active_conflicts: {scan['active_conflicts']}",
            f"- message: {scan['message']}",
        ]
    )
    active_ids = scan.get("active_ids", [])
    if active_ids:
        lines.append("- active_ids:")
        lines.extend(f"  - `{item}`" for item in active_ids)
    lines.append("")


def add_group(lines: list[str], title: str, items: list[object]) -> None:
    lines.extend([f"## {title}", ""])
    if not items:
        lines.extend(["_None._", ""])
        return
    for item in items:
        lines.append(f"- `{item}`")
    lines.append("")


def add_duplicate_group(
    lines: list[str], title: str, groups: dict[str, list[MemoryDocument]], root: Path
) -> None:
    lines.extend([f"## {title}", ""])
    if not groups:
        lines.extend(["_None._", ""])
        return
    for key, documents in sorted(groups.items()):
        paths = ", ".join(f"`{repo_relative_path(document.path, root)}`" for document in documents)
        lines.append(f"- `{key}`: {paths}")
    lines.append("")


def add_document_group(
    lines: list[str], title: str, documents: list[MemoryDocument], root: Path
) -> None:
    lines.extend([f"## {title}", ""])
    if not documents:
        lines.extend(["_None._", ""])
        return
    for document in sorted(documents, key=lambda item: item.frontmatter["updated_at"]):
        data = document.frontmatter
        relpath = repo_relative_path(document.path, root)
        lines.extend(
            [
                f"### {data['title']}",
                "",
                f"- id: `{data['id']}`",
                f"- path: `{relpath}`",
                f"- status: `{data['status']}`",
                f"- confidence: `{float(data['confidence']):.2f}`",
                f"- review_after: `{data['review_after']}`",
                "",
                report_summary(document),
                "",
            ]
        )


def report_summary(document: MemoryDocument) -> str:
    if document.frontmatter["sensitivity"] in {"private", "sensitive", "secret-prohibited"}:
        return "_Content omitted because sensitivity is not public/internal._"
    return extract_summary(document.content) or "_No summary available._"


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def write_report(root: Path, output: Path) -> Path:
    target = resolve_repo_path(root, output)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("report path must stay inside the memory root") from exc
    report = build_report(root)
    if scan_text(report, "<consolidation-report>"):
        raise RuntimeError("consolidation report rejected by secret scan")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report path.")
    parser.add_argument("--report-path", default=None, help="Report path inside the memory root.")
    parser.add_argument("--dry-run", action="store_true", help="Document that no mutations are made.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    output = Path(args.report_path or args.output)

    try:
        path = write_report(root, output)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Wrote {repo_relative_path(path, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
