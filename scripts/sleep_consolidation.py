#!/usr/bin/env python3
"""Plan safe sleep consolidation review packets."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from consolidate_memory import report_summary
from lifecycle import lifecycle_scores
from memorylib import (
    extract_summary,
    parse_date,
    repo_relative_path,
    repo_root,
    slugify,
    today,
    validate_memories,
)
from review_memory import conflict_reviews, false_positive_reviews
from secret_scan import scan_paths, scan_text


DEFAULT_REPORT = Path("reports/sleep-plan.md")
DEFAULT_JSON = Path("reports/sleep-plan.json")
PACKET_DIR = Path("inbox/sleep-consolidation")


class SleepError(RuntimeError):
    """Raised when safe sleep consolidation cannot proceed."""


@dataclass(frozen=True)
class SleepCandidate:
    id: str
    kind: str
    title: str
    path: str
    reason: str
    priority: float
    safe_action: str
    summary: str


@dataclass(frozen=True)
class SleepPlan:
    generated_at: str
    candidates: list[SleepCandidate]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(kind: str, path: str, reason: str) -> str:
    digest = hashlib.sha256(f"{kind}|{path}|{reason}".encode("utf-8")).hexdigest()[:16]
    return f"sleep_{digest}"


def build_sleep_plan(root: Path) -> SleepPlan:
    documents, errors = validate_memories(root)
    if errors:
        raise SleepError("memory validation failed:\n" + "\n".join(errors))

    scan_targets = [repo_relative_path(document.path, root) for document in documents]
    if (root / "inbox").exists():
        scan_targets.extend(
            repo_relative_path(path, root)
            for path in sorted((root / "inbox").rglob("*.md"))
            if path.name != "README.md"
        )
    findings = scan_paths(root, scan_targets)
    if findings:
        formatted = "\n".join(
            f"{finding.path}:{finding.line}: {finding.kind}: {finding.redacted_line}"
            for finding in findings[:20]
        )
        raise SleepError(f"secret scan failed before sleep consolidation:\n{formatted}")

    candidates: list[SleepCandidate] = []
    now = today()
    for document in documents:
        data = document.frontmatter
        relpath = repo_relative_path(document.path, root)
        if data["status"] == "active" and parse_date(data["review_after"]) <= now:
            candidates.append(
                candidate(
                    "review_due",
                    str(data["title"]),
                    relpath,
                    "Memory review_after is due.",
                    0.80,
                    "Create a human review packet; do not auto-edit canonical memory.",
                    report_summary(document),
                )
            )
        if float(data["confidence"]) < 0.65 and data["status"] == "active":
            candidates.append(
                candidate(
                    "low_confidence",
                    str(data["title"]),
                    relpath,
                    "Memory confidence is below 0.65.",
                    0.70,
                    "Ask a human to reinforce, rewrite, or archive this memory.",
                    report_summary(document),
                )
            )

    for path in inbox_files(root):
        relpath = repo_relative_path(path, root)
        text = path.read_text(encoding="utf-8")
        candidates.append(
            candidate(
                "inbox_candidate",
                path.stem,
                relpath,
                "Inbox candidate awaits human review.",
                0.65,
                "Summarize for review; promote only after explicit approval.",
                extract_summary(text) or "_No summary available._",
            )
        )

    for conflict in conflict_reviews(root):
        if conflict.status != "active":
            continue
        candidates.append(
            candidate(
                "active_conflict",
                conflict.id,
                ",".join(conflict.paths),
                conflict.reason,
                0.90,
                "Write or review a conflict merge proposal; do not mutate canonical memory.",
                " ".join(conflict.summaries),
            )
        )

    for finding in false_positive_reviews(root):
        if finding.ignored:
            continue
        candidates.append(
            candidate(
                "secret_scan_finding",
                finding.id,
                f"{finding.path}:{finding.line}",
                f"Unreviewed secret-scan finding of kind {finding.kind}.",
                1.0,
                "Pause consolidation and review the redacted finding.",
                finding.redacted_line,
            )
        )

    try:
        lifecycle = lifecycle_scores(root)
    except FileNotFoundError:
        lifecycle = []
    for item in lifecycle:
        if item.recommendation not in {"needs_repair", "review_due"}:
            continue
        candidates.append(
            candidate(
                "lifecycle_recommendation",
                item.title,
                item.path,
                f"Lifecycle recommendation is {item.recommendation}.",
                0.75 if item.recommendation == "needs_repair" else 0.70,
                "Create a review packet with lifecycle evidence.",
                f"score={item.score}; outcomes=+{item.positive_outcomes}/-{item.negative_outcomes}",
            )
        )

    deduped = {item.id: item for item in candidates}
    return SleepPlan(
        generated_at=utc_now(),
        candidates=sorted(deduped.values(), key=lambda item: (-item.priority, item.kind, item.id)),
    )


def candidate(
    kind: str,
    title: str,
    path: str,
    reason: str,
    priority: float,
    safe_action: str,
    summary: str,
) -> SleepCandidate:
    return SleepCandidate(
        id=stable_id(kind, path, reason),
        kind=kind,
        title=title,
        path=path,
        reason=reason,
        priority=round(priority, 4),
        safe_action=safe_action,
        summary=summary,
    )


def inbox_files(root: Path) -> list[Path]:
    inbox = root / "inbox"
    if not inbox.exists():
        return []
    packets = root / PACKET_DIR
    files = []
    for path in sorted(inbox.rglob("*.md")):
        if path.name == "README.md":
            continue
        try:
            path.relative_to(packets)
            continue
        except ValueError:
            files.append(path)
    return files


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def resolve_report_path(root: Path, output: str | Path) -> Path:
    target = resolve_repo_path(root, output)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise SleepError("report path must stay inside the memory root") from exc
    return target


def write_sleep_report(root: Path, output: Path = DEFAULT_REPORT) -> tuple[Path, SleepPlan]:
    plan = build_sleep_plan(root)
    target = resolve_report_path(root, output)
    text = render_sleep_report(plan)
    if scan_text(text, "<sleep-plan-report>"):
        raise SleepError("sleep report rejected by secret scan")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target, plan


def write_sleep_json(root: Path, output: Path = DEFAULT_JSON) -> tuple[Path, SleepPlan]:
    plan = build_sleep_plan(root)
    target = resolve_report_path(root, output)
    text = json.dumps(asdict(plan), indent=2)
    if scan_text(text, "<sleep-plan-json>"):
        raise SleepError("sleep JSON report rejected by secret scan")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target, plan


def apply_review_packets(root: Path, ids: list[str] | None = None) -> list[Path]:
    plan = build_sleep_plan(root)
    selected_ids = set(ids or [])
    selected = [item for item in plan.candidates if not selected_ids or item.id in selected_ids]
    if selected_ids:
        known = {item.id for item in plan.candidates}
        missing = selected_ids - known
        if missing:
            raise SleepError("unknown sleep candidate id(s): " + ", ".join(sorted(missing)))
    output_dir = safe_packet_dir(root)
    written: list[Path] = []
    for item in selected:
        path = output_dir / f"{item.id}-{slugify(item.kind)}.md"
        text = render_review_packet(item)
        findings = scan_text(text, f"<sleep-packet:{item.id}>")
        if findings:
            raise SleepError(f"sleep packet rejected by secret scan: {item.id}")
        if path.exists() or path.is_symlink():
            raise SleepError("sleep packet path already exists")
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def safe_packet_dir(root: Path) -> Path:
    root = root.resolve()
    inbox = root / "inbox"
    packet_dir = root / PACKET_DIR
    for component in (inbox, packet_dir):
        if component.is_symlink():
            raise SleepError("sleep packet path must not contain symlinks")
        if component.exists():
            try:
                component.resolve().relative_to(root)
            except ValueError as exc:
                raise SleepError("sleep packet path must stay inside the memory root") from exc

    packet_dir.mkdir(parents=True, exist_ok=True)
    for component in (inbox, packet_dir):
        if component.is_symlink():
            raise SleepError("sleep packet path must not contain symlinks")
        try:
            component.resolve().relative_to(root)
        except ValueError as exc:
            raise SleepError("sleep packet path must stay inside the memory root") from exc
    return packet_dir


def render_sleep_report(plan: SleepPlan) -> str:
    lines = [
        "# Sleep Consolidation Plan",
        "",
        f"Generated at: {plan.generated_at}",
        "",
        "No canonical memory files were modified.",
        "",
        "## Summary",
        "",
        f"- candidates: {len(plan.candidates)}",
        "",
        "## Candidates",
        "",
    ]
    if not plan.candidates:
        lines.extend(["_No sleep consolidation candidates._", ""])
        return "\n".join(lines)
    for item in plan.candidates:
        lines.extend(render_candidate(item))
    return "\n".join(lines).rstrip() + "\n"


def render_candidate(item: SleepCandidate) -> list[str]:
    return [
        f"### {item.title}",
        "",
        f"- id: `{item.id}`",
        f"- kind: `{item.kind}`",
        f"- path: `{item.path}`",
        f"- priority: `{item.priority:.4f}`",
        f"- reason: {item.reason}",
        f"- safe_action: {item.safe_action}",
        "",
        item.summary,
        "",
    ]


def render_review_packet(item: SleepCandidate) -> str:
    lines = [
        f"# Sleep Review Packet: {item.title}",
        "",
        f"- sleep_id: `{item.id}`",
        f"- kind: `{item.kind}`",
        f"- source: `{item.path}`",
        f"- priority: `{item.priority:.4f}`",
        f"- reason: {item.reason}",
        f"- safe_action: {item.safe_action}",
        "",
        "## Evidence",
        "",
        item.summary,
        "",
        "## Human Review",
        "",
        "- [ ] Approve, reject, or rewrite this candidate.",
        "- [ ] Run validation and secret scan before promoting canonical memory.",
        "- [ ] Record durable review provenance if promoting durable memory.",
        "",
    ]
    return "\n".join(lines)


def display_path(path: Path, root: Path) -> str:
    try:
        return repo_relative_path(path, root)
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--dry-run", action="store_true", help="Preview sleep candidates without writing reports or packets.")
    parser.add_argument("--propose", action="store_true", help="Write sleep review packets for all candidates, or selected --id values.")
    parser.add_argument("--apply-reviewed", action="store_true", help="Compatibility alias for writing reviewed sleep packets.")
    parser.add_argument("--id", action="append", default=None, help="Candidate id for --propose or --apply-reviewed. Repeatable.")
    parser.add_argument("--all", action="store_true", help="Use with --apply-reviewed to write every sleep review packet.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output for top-level sleep aliases.")
    subparsers = parser.add_subparsers(dest="command")
    plan_cmd = subparsers.add_parser("plan", help="Write or print a sleep consolidation plan.")
    plan_cmd.add_argument("--output", default=str(DEFAULT_REPORT))
    plan_cmd.add_argument("--report-path", default=None, help="Markdown report path inside the memory root.")
    plan_cmd.add_argument("--json", action="store_true")
    plan_cmd.add_argument("--json-output", default=None)
    plan_cmd.add_argument("--json-report-path", default=None, help="JSON report path inside the memory root.")
    apply_cmd = subparsers.add_parser("apply-reviewed", help="Write review packets for selected candidates.")
    apply_cmd.add_argument("--id", action="append", default=None, help="Candidate id to write. Repeatable.")
    apply_cmd.add_argument("--all", action="store_true", help="Write packets for every candidate.")
    apply_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)

    try:
        if args.command is None:
            requested = [flag for flag, enabled in (("--dry-run", args.dry_run), ("--propose", args.propose), ("--apply-reviewed", args.apply_reviewed)) if enabled]
            if len(requested) > 1:
                raise SleepError("choose only one of --dry-run, --propose, or --apply-reviewed")
            if args.dry_run:
                if args.id or args.all:
                    raise SleepError("--dry-run cannot be combined with --id or --all")
                plan = build_sleep_plan(root)
                payload = {
                    "dry_run": True,
                    "writes_files": False,
                    "writes_canonical_memory": False,
                    "deletes_files": False,
                    "plan": asdict(plan),
                }
                if args.json:
                    print(json.dumps(payload, indent=2))
                else:
                    print(f"Sleep dry-run found {len(plan.candidates)} candidate(s).")
                    for item in plan.candidates:
                        print(f"{item.id}\t{item.kind}\t{item.path}")
                return 0
            if args.propose or args.apply_reviewed:
                if args.all and args.id:
                    raise SleepError("choose --all or --id, not both")
                if args.apply_reviewed and not args.all and not args.id:
                    raise SleepError("--apply-reviewed requires --all or at least one --id")
                written = apply_review_packets(root, None if args.all else args.id)
                paths = [repo_relative_path(path, root) for path in written]
                payload = {
                    "written": paths,
                    "writes_files": True,
                    "writes_canonical_memory": False,
                    "deletes_files": False,
                    "output_dir": repo_relative_path(root / PACKET_DIR, root),
                    "alias": "apply-reviewed" if args.apply_reviewed else "propose",
                }
                if args.json:
                    print(json.dumps(payload, indent=2))
                else:
                    print(f"Wrote {len(paths)} sleep review packet(s).")
                    for path in paths:
                        print(path)
                return 0
            parser.error("command required unless --dry-run, --propose, or --apply-reviewed is used")
        if args.dry_run or args.propose or args.apply_reviewed:
            parser.error("--dry-run, --propose, and --apply-reviewed cannot be combined with sleep subcommands")
        if args.command == "plan":
            if args.json:
                output = (
                    Path(args.json_report_path or args.json_output)
                    if args.json_report_path or args.json_output
                    else DEFAULT_JSON
                )
                path, plan = write_sleep_json(root, output)
                print(json.dumps({"path": display_path(path, root), "plan": asdict(plan)}, indent=2))
            else:
                path, plan = write_sleep_report(root, Path(args.report_path or args.output))
                print(f"Wrote {display_path(path, root)} ({len(plan.candidates)} candidate(s))")
            return 0
        if args.command == "apply-reviewed":
            if not args.all and not args.id:
                raise SleepError("apply-reviewed requires --all or at least one --id")
            written = apply_review_packets(root, None if args.all else args.id)
            paths = [repo_relative_path(path, root) for path in written]
            if args.json:
                print(json.dumps({"written": paths}, indent=2))
            else:
                print(f"Wrote {len(paths)} sleep review packet(s).")
                for path in paths:
                    print(path)
            return 0
    except (OSError, SleepError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error("unhandled command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
