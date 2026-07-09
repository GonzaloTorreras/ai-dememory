#!/usr/bin/env python3
"""Audit durable memory review provenance."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from memorylib import discover_memory_files, is_date_string, load_memory, repo_relative_path, repo_root
from secret_scan import scan_text


DEFAULT_PROVENANCE_REPORT = Path("reports/durable-provenance.md")


@dataclass(frozen=True)
class ProvenanceIssue:
    path: str
    memory_id: str
    field: str
    message: str


@dataclass(frozen=True)
class ProvenanceAudit:
    generated_at: str
    durable_count: int
    issue_count: int
    issues: list[ProvenanceIssue]


def audit_durable_provenance(root: Path) -> ProvenanceAudit:
    issues: list[ProvenanceIssue] = []
    durable_count = 0
    for path in discover_memory_files(root):
        document = load_memory(path)
        data = document.frontmatter
        if data.get("type") != "durable":
            continue
        durable_count += 1
        relpath = repo_relative_path(path, root)
        memory_id = str(data.get("id") or "")
        if data.get("reviewed") is not True:
            issues.append(
                ProvenanceIssue(relpath, memory_id, "reviewed", "durable memory must include reviewed: true")
            )
        if not isinstance(data.get("reviewed_by"), str) or not str(data.get("reviewed_by") or "").strip():
            issues.append(
                ProvenanceIssue(relpath, memory_id, "reviewed_by", "durable memory must include reviewed_by")
            )
        if not is_date_string(data.get("reviewed_at")):
            issues.append(
                ProvenanceIssue(relpath, memory_id, "reviewed_at", "durable memory must include reviewed_at YYYY-MM-DD")
            )
    return ProvenanceAudit(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        durable_count=durable_count,
        issue_count=len(issues),
        issues=issues,
    )


def render_markdown(audit: ProvenanceAudit) -> str:
    if audit.issues:
        issues = "\n".join(
            f"- `{issue.path}` `{issue.memory_id}` `{issue.field}`: {issue.message}"
            for issue in audit.issues
        )
    else:
        issues = "No durable provenance issues found."
    return f"""# Durable Provenance Audit

Generated: `{audit.generated_at}`

Durable memories: `{audit.durable_count}`

Issues: `{audit.issue_count}`

## Issues

{issues}
"""


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def resolve_report_path(root: Path, report_path: str | Path) -> Path:
    root_abs = root.resolve()
    target = resolve_repo_path(root_abs, report_path)
    try:
        target.relative_to(root_abs / "reports")
    except ValueError as exc:
        raise ValueError("report path must stay under reports/") from exc
    current = root_abs
    for part in target.relative_to(root_abs).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("report path must not contain symlinks")
    if target.is_symlink():
        raise ValueError("report path must not be a symlink")
    return target


def write_report(
    root: Path,
    audit: ProvenanceAudit,
    report_path: str | Path = DEFAULT_PROVENANCE_REPORT,
) -> Path:
    target = resolve_report_path(root, report_path)

    text = render_markdown(audit)
    if scan_text(text, "<durable-provenance-report>"):
        raise ValueError("durable provenance report rejected by secret scan")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def audit_to_dict(audit: ProvenanceAudit) -> dict[str, Any]:
    data = asdict(audit)
    data["issues"] = [asdict(issue) for issue in audit.issues]
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--write-report", action="store_true", help="Write reports/durable-provenance.md.")
    parser.add_argument("--report-path", default=str(DEFAULT_PROVENANCE_REPORT), help="Report path inside the memory root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        audit = audit_durable_provenance(root)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        report_path = write_report(root, audit, args.report_path) if args.write_report else None
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    output = audit_to_dict(audit)
    if report_path:
        output["report_path"] = repo_relative_path(report_path, root)

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(render_markdown(audit))
        if report_path:
            print(f"Wrote {repo_relative_path(report_path, root)}")
    return 1 if audit.issue_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
