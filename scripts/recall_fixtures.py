#!/usr/bin/env python3
"""Promote reviewed recall misses into curated recall fixtures."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from eval_recall import DEFAULT_FIXTURES, evaluate, load_fixtures
from memorylib import (
    FrontmatterError,
    discover_memory_files,
    load_memory,
    parse_frontmatter_text,
    repo_relative_path,
    repo_root,
    slugify,
)
from secret_scan import scan_text
from search_memory import result_to_dict, search


@dataclass(frozen=True)
class PromotedFixture:
    fixture: dict[str, Any]
    fixtures_path: str


@dataclass(frozen=True)
class RecallMissReviewResult:
    path: str
    status: str
    reviewed_by: str
    reviewed_at: str
    reason: str
    fixture_updated: bool
    canonical_memory_updated: bool


@dataclass(frozen=True)
class FixtureFreshness:
    fixtures_path: str
    total_fixtures: int
    reviewed_promotions: int
    seed_fixtures: int
    latest_reviewed_at: str | None
    latest_created_at: str | None
    max_age_days: int
    days_since_latest_review: int | None
    needs_reviewed_promotion: bool
    stale: bool
    status: str
    next_action: str


@dataclass(frozen=True)
class PendingRecallMiss:
    path: str
    created_at: str | None
    status: str | None
    query: str | None
    expected_id: str | None
    expected_path: str | None
    source_ref: str | None
    redacted_fields: bool


@dataclass(frozen=True)
class InvalidRecallMiss:
    path: str
    error: str


@dataclass(frozen=True)
class ResolvedRecallMiss:
    path: str
    status: str
    reviewed_by: str | None
    reviewed_at: str | None
    query: str | None
    expected_id: str | None
    expected_path: str | None
    review_reason: str | None
    promoted_fixture_id: str | None
    redacted_fields: bool


@dataclass(frozen=True)
class RecallReviewPlan:
    fixtures_path: str
    status: str
    stale: bool
    pending_count: int
    invalid_count: int
    resolved_count: int
    freshness: FixtureFreshness
    pending_misses: list[PendingRecallMiss]
    invalid_misses: list[InvalidRecallMiss]
    recent_resolved_misses: list[ResolvedRecallMiss]
    candidate_check_command: list[str]
    next_actions: list[str]
    limit: int | None = None
    pending_returned_count: int = 0
    pending_offset: int = 0
    pending_next_offset: int | None = None
    pending_has_more: bool = False
    invalid_returned_count: int = 0
    invalid_offset: int = 0
    invalid_next_offset: int | None = None
    invalid_has_more: bool = False
    reviewer: str | None = None
    pr_url: str | None = None


@dataclass(frozen=True)
class RecallMissCandidate:
    query: str
    expected_id: str
    expected_path: str | None
    expected_rank: int | None
    min_rank: int
    searched_limit: int
    candidate_miss: bool
    reason: str
    top_results: list[dict[str, Any]]
    capture_dry_run_command: list[str]
    capture_write_command: list[str]
    writes_files: bool


@dataclass(frozen=True)
class RecallReviewPacketArchiveEntry:
    path: str
    size_bytes: int
    modified_at: str
    generated_at: str | None


DEFAULT_REVIEW_REPORT = Path("reports/recall-review-plan.md")
DEFAULT_REVIEW_PACKET = Path("reports/recall-review-packet.md")
DEFAULT_REVIEW_PACKET_ARCHIVE_DIR = Path("reports/recall-review-packets")
RESOLVED_RECALL_MISS_STATUSES = {"promoted", "rejected", "dismissed"}
REVIEWABLE_RECALL_MISS_STATUSES = {"rejected", "dismissed"}


def reviewed_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def ensure_recall_miss_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    inbox_dir = root / "inbox"
    feedback_dir = inbox_dir / "recall-feedback"
    for component in (inbox_dir, feedback_dir):
        if component.is_symlink():
            raise ValueError("miss path must not contain symlinks")
    try:
        rel_parts = candidate.relative_to(feedback_dir).parts
    except ValueError:
        rel_parts = ()
    current = feedback_dir
    for part in rel_parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("miss path must not contain symlinks")
    if candidate.is_symlink():
        raise ValueError("miss path must not be a symlink")
    resolved = candidate.resolve()
    feedback_dir_resolved = feedback_dir.resolve()
    try:
        resolved.relative_to(feedback_dir_resolved)
    except ValueError as exc:
        raise ValueError("miss path must be under inbox/recall-feedback/") from exc
    if not resolved.exists() or resolved.suffix.lower() != ".md":
        raise ValueError("miss path must be an existing Markdown file")
    return resolved


def load_recall_miss(path: Path) -> dict[str, Any]:
    try:
        data, _ = parse_frontmatter_text(path.read_text(encoding="utf-8"), path)
    except (OSError, FrontmatterError) as exc:
        raise ValueError(f"could not read recall miss: {exc}") from exc
    if data.get("type") != "recall-miss":
        raise ValueError("miss file must have type: recall-miss")
    query = data.get("query")
    expected_id = data.get("expected_id")
    expected_path = data.get("expected_path")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("miss file must include query")
    if bool(expected_id) == bool(expected_path):
        raise ValueError("miss file must include exactly one of expected_id or expected_path")
    return data


def unsafe_recall_miss_entry_error(root: Path, feedback_dir: Path, path: Path) -> str | None:
    for component in (root / "inbox", feedback_dir):
        if component.is_symlink():
            return "recall feedback path must not contain symlinks"
    if path.is_symlink():
        return "recall miss path must not be a symlink"
    resolved = path.resolve()
    feedback_root = feedback_dir.resolve()
    try:
        resolved.relative_to(feedback_root)
    except ValueError:
        return "recall miss path must stay under inbox/recall-feedback/"
    return None


def recall_miss_display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def memory_id_exists(root: Path, memory_id: str) -> bool:
    for path in discover_memory_files(root):
        try:
            if load_memory(path).frontmatter.get("id") == memory_id:
                return True
        except (OSError, FrontmatterError):
            continue
    return False


def resolve_expected_id(root: Path, miss: dict[str, Any]) -> str:
    expected_id = miss.get("expected_id")
    if isinstance(expected_id, str) and expected_id.strip():
        expected_id = expected_id.strip()
        if not memory_id_exists(root, expected_id):
            raise ValueError(f"expected memory id does not exist: {expected_id}")
        return expected_id

    expected_path = miss.get("expected_path")
    if not isinstance(expected_path, str) or not expected_path.strip():
        raise ValueError("miss file must include expected_id or expected_path")
    path = resolve_repo_path(root, expected_path)
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("expected_path must stay inside the memory root") from exc
    data = load_memory(path).frontmatter
    memory_id = data.get("id")
    if not isinstance(memory_id, str) or not memory_id.strip():
        raise ValueError("expected_path memory must include an id")
    return memory_id


def resolve_expected_path_id(root: Path, expected_path: str | Path) -> str:
    path = resolve_repo_path(root, expected_path)
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("expected_path must stay inside the memory root") from exc
    data = load_memory(path).frontmatter
    memory_id = data.get("id")
    if not isinstance(memory_id, str) or not memory_id.strip():
        raise ValueError("expected_path memory must include an id")
    return memory_id


def recall_miss_candidate(
    root: Path,
    query: str,
    expected_id: str | None = None,
    expected_path: str | Path | None = None,
    min_rank: int = 5,
    limit: int = 10,
    include_sensitive: bool = False,
) -> RecallMissCandidate:
    query = " ".join(query.split()).strip()
    if not query:
        raise ValueError("query is required")
    if bool(expected_id) == bool(expected_path):
        raise ValueError("provide exactly one of expected_id or expected_path")
    if min_rank < 1:
        raise ValueError("min_rank must be >= 1")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    resolved_expected_path = str(expected_path).strip() if expected_path else None
    if expected_id:
        resolved_expected_id = str(expected_id).strip()
        if not resolved_expected_id:
            raise ValueError("expected_id is required")
        if not memory_id_exists(root, resolved_expected_id):
            raise ValueError(f"expected memory id does not exist: {resolved_expected_id}")
    else:
        resolved_expected_id = resolve_expected_path_id(root, str(expected_path))

    scan_target = json.dumps(
        {
            "query": query,
            "expected_id": resolved_expected_id,
            "expected_path": resolved_expected_path,
        },
        sort_keys=True,
    )
    if scan_text(scan_target, "<recall-miss-candidate>"):
        raise ValueError("recall miss candidate rejected by secret scan")

    searched_limit = max(limit, min_rank)
    results = search(query, root, limit=searched_limit, include_sensitive=include_sensitive)
    returned_ids = [result.id for result in results]
    expected_rank = returned_ids.index(resolved_expected_id) + 1 if resolved_expected_id in returned_ids else None
    candidate_miss = expected_rank is None or expected_rank > min_rank
    if expected_rank is None:
        reason = f"Expected memory was absent from the top {searched_limit} result(s)."
    elif expected_rank > min_rank:
        reason = f"Expected memory ranked {expected_rank}, outside the top {min_rank}."
    else:
        reason = f"Expected memory ranked {expected_rank}, within the top {min_rank}."

    base_capture_command = []
    if candidate_miss:
        base_capture_command = [
            "ai-dememory",
            "capture-miss",
            "--query",
            query,
            "--expected-id",
            resolved_expected_id,
            "--reason",
            reason,
        ]
    return RecallMissCandidate(
        query=query,
        expected_id=resolved_expected_id,
        expected_path=resolved_expected_path,
        expected_rank=expected_rank,
        min_rank=min_rank,
        searched_limit=searched_limit,
        candidate_miss=candidate_miss,
        reason=reason,
        top_results=[result_to_dict(result) for result in results],
        capture_dry_run_command=[*base_capture_command, "--dry-run"] if candidate_miss else [],
        capture_write_command=base_capture_command,
        writes_files=False,
    )


def default_fixture_id(query: str) -> str:
    return "recall_" + slugify(query, "miss").replace("-", "_")


def existing_fixtures(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_fixtures(path)


def reject_duplicate_fixture(fixtures: list[dict[str, Any]], fixture: dict[str, Any]) -> None:
    fixture_id = fixture["id"]
    query = fixture["query"]
    expected_ids = set(fixture["expected_ids"])
    for existing in fixtures:
        if existing.get("id") == fixture_id:
            raise ValueError(f"fixture id already exists: {fixture_id}")
        if existing.get("query") == query and expected_ids.intersection(set(existing.get("expected_ids") or [])):
            raise ValueError("fixture already covers this query and expected id")


def parse_fixture_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def recall_fixture_freshness(
    root: Path,
    fixtures_path: str | Path = DEFAULT_FIXTURES,
    max_age_days: int = 14,
    today: date | None = None,
) -> FixtureFreshness:
    if max_age_days < 1:
        raise ValueError("max_age_days must be >= 1")
    target = resolve_repo_path(root, fixtures_path)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("fixtures path must stay inside the memory root") from exc

    fixtures = load_fixtures(target)
    created_dates = [value for value in (parse_fixture_date(item.get("created_at")) for item in fixtures) if value]
    reviewed_dates = [value for value in (parse_fixture_date(item.get("reviewed_at")) for item in fixtures) if value]
    latest_created = max(created_dates) if created_dates else None
    latest_reviewed = max(reviewed_dates) if reviewed_dates else None
    today = today or datetime.now(timezone.utc).date()
    days_since_latest_review = (today - latest_reviewed).days if latest_reviewed else None
    needs_reviewed_promotion = not bool(reviewed_dates)
    stale = needs_reviewed_promotion or (
        days_since_latest_review is not None and days_since_latest_review > max_age_days
    )
    if needs_reviewed_promotion:
        status = "needs_reviewed_promotion"
        next_action = "Run `ai-dememory recall-fixtures check-miss` before capturing a real miss, then review and promote it."
    elif stale:
        status = "stale"
        next_action = "Run the weekly recall review and promote or reject reviewed misses."
    else:
        status = "fresh"
        next_action = "Continue weekly recall review and promote only validated misses."

    return FixtureFreshness(
        fixtures_path=repo_relative_path(target, root),
        total_fixtures=len(fixtures),
        reviewed_promotions=len(reviewed_dates),
        seed_fixtures=len(fixtures) - len(reviewed_dates),
        latest_reviewed_at=latest_reviewed.isoformat() if latest_reviewed else None,
        latest_created_at=latest_created.isoformat() if latest_created else None,
        max_age_days=max_age_days,
        days_since_latest_review=days_since_latest_review,
        needs_reviewed_promotion=needs_reviewed_promotion,
        stale=stale,
        status=status,
        next_action=next_action,
    )


def safe_frontmatter_text(value: Any, label: str, display_path: str) -> tuple[str | None, bool]:
    if not isinstance(value, str) or not value.strip():
        return None, False
    text = value.strip()
    if scan_text(f"{label}: {text}", display_path):
        return "<redacted:secret-like>", True
    return text, False


def recall_miss_review_state(
    root: Path,
) -> tuple[list[PendingRecallMiss], list[InvalidRecallMiss], list[ResolvedRecallMiss]]:
    feedback_dir = root / "inbox" / "recall-feedback"
    pending: list[PendingRecallMiss] = []
    invalid: list[InvalidRecallMiss] = []
    resolved: list[ResolvedRecallMiss] = []
    for component in (root / "inbox", feedback_dir):
        if component.is_symlink():
            invalid.append(
                InvalidRecallMiss(
                    path=recall_miss_display_path(component, root),
                    error="recall feedback path must not contain symlinks",
                )
            )
            return pending, invalid, resolved
    if not feedback_dir.exists():
        return pending, invalid, resolved
    for path in sorted(feedback_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        relpath = recall_miss_display_path(path, root)
        unsafe_error = unsafe_recall_miss_entry_error(root, feedback_dir, path)
        if unsafe_error:
            invalid.append(InvalidRecallMiss(path=relpath, error=unsafe_error))
            continue
        try:
            data = load_recall_miss(path)
        except ValueError as exc:
            invalid.append(InvalidRecallMiss(path=relpath, error=str(exc)))
            continue
        status = data.get("status")
        if isinstance(status, str) and status in RESOLVED_RECALL_MISS_STATUSES:
            secret_like = False
            fields: dict[str, str | None] = {}
            for label in (
                "query",
                "expected_id",
                "expected_path",
                "reviewed_by",
                "reviewed_at",
                "review_reason",
                "promoted_fixture_id",
            ):
                value, flagged = safe_frontmatter_text(data.get(label), label, relpath)
                fields[label] = value
                secret_like = secret_like or flagged
            resolved.append(
                ResolvedRecallMiss(
                    path=relpath,
                    status=status,
                    reviewed_by=fields["reviewed_by"],
                    reviewed_at=fields["reviewed_at"],
                    query=fields["query"],
                    expected_id=fields["expected_id"],
                    expected_path=fields["expected_path"],
                    review_reason=fields["review_reason"],
                    promoted_fixture_id=fields["promoted_fixture_id"],
                    redacted_fields=secret_like,
                )
            )
            continue
        secret_like = False
        fields: dict[str, str | None] = {}
        for label in ("query", "expected_id", "expected_path", "source_ref"):
            value, flagged = safe_frontmatter_text(data.get(label), label, relpath)
            fields[label] = value
            secret_like = secret_like or flagged
        created_at = data.get("created_at")
        pending.append(
            PendingRecallMiss(
                path=relpath,
                created_at=created_at if isinstance(created_at, str) else None,
                status=status if isinstance(status, str) else None,
                query=fields["query"],
                expected_id=fields["expected_id"],
                expected_path=fields["expected_path"],
                source_ref=fields["source_ref"],
                redacted_fields=secret_like,
            )
        )
    resolved.sort(key=lambda item: (item.reviewed_at or "", item.path), reverse=True)
    return pending, invalid, resolved


def pending_recall_misses(root: Path) -> tuple[list[PendingRecallMiss], list[InvalidRecallMiss]]:
    pending, invalid, _ = recall_miss_review_state(root)
    return pending, invalid


def recall_fixture_review_plan(
    root: Path,
    fixtures_path: str | Path = DEFAULT_FIXTURES,
    max_age_days: int = 14,
    resolved_limit: int = 5,
    today: date | None = None,
) -> RecallReviewPlan:
    if resolved_limit < 0:
        raise ValueError("resolved_limit must be >= 0")
    freshness = recall_fixture_freshness(root, fixtures_path, max_age_days, today=today)
    pending, invalid, resolved = recall_miss_review_state(root)
    recent_resolved = resolved[:resolved_limit]
    candidate_check_command = [
        "ai-dememory",
        "recall-fixtures",
        "check-miss",
        "--query",
        "<query>",
        "--expected-id",
        "<memory-id>",
        "--json",
    ]
    next_actions: list[str] = [freshness.next_action]
    if pending:
        next_actions.append(
            "Review pending misses, then promote validated ones with "
            "`ai-dememory recall-fixtures promote-miss --miss <path> --reviewed-by <name>`."
        )
    else:
        next_actions.append(
            "No pending recall miss files were found under `inbox/recall-feedback/`; "
            "run `ai-dememory recall-fixtures check-miss --query <query> --expected-id <memory-id> --json` "
            "before writing new recall feedback."
        )
    if invalid:
        next_actions.append("Fix or remove malformed recall miss files before weekly review sign-off.")
    next_actions.append("Run `ai-dememory eval-recall` after promoting reviewed misses.")
    status = "pending_review" if pending or invalid else freshness.status
    return RecallReviewPlan(
        fixtures_path=freshness.fixtures_path,
        status=status,
        stale=freshness.stale,
        pending_count=len(pending),
        invalid_count=len(invalid),
        resolved_count=len(resolved),
        freshness=freshness,
        pending_misses=pending,
        invalid_misses=invalid,
        recent_resolved_misses=recent_resolved,
        candidate_check_command=candidate_check_command,
        next_actions=next_actions,
        pending_returned_count=len(pending),
        invalid_returned_count=len(invalid),
    )


def paginate_recall_review_plan(
    plan: RecallReviewPlan,
    limit: int = 50,
    pending_offset: int = 0,
    invalid_offset: int = 0,
) -> RecallReviewPlan:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if pending_offset < 0:
        raise ValueError("pending_offset must be >= 0")
    if invalid_offset < 0:
        raise ValueError("invalid_offset must be >= 0")
    pending_page = plan.pending_misses[pending_offset : pending_offset + limit]
    pending_next_offset = pending_offset + len(pending_page)
    pending_has_more = pending_next_offset < plan.pending_count
    invalid_page = plan.invalid_misses[invalid_offset : invalid_offset + limit]
    invalid_next_offset = invalid_offset + len(invalid_page)
    invalid_has_more = invalid_next_offset < plan.invalid_count
    return replace(
        plan,
        limit=limit,
        pending_misses=pending_page,
        invalid_misses=invalid_page,
        pending_returned_count=len(pending_page),
        pending_offset=pending_offset,
        pending_next_offset=pending_next_offset if pending_has_more else None,
        pending_has_more=pending_has_more,
        invalid_returned_count=len(invalid_page),
        invalid_offset=invalid_offset,
        invalid_next_offset=invalid_next_offset if invalid_has_more else None,
        invalid_has_more=invalid_has_more,
    )


def annotate_recall_review_packet_plan(
    plan: RecallReviewPlan,
    reviewer: str | None = None,
    pr_url: str | None = None,
) -> RecallReviewPlan:
    clean_reviewer = reviewer.strip() if isinstance(reviewer, str) and reviewer.strip() else None
    clean_pr_url = pr_url.strip() if isinstance(pr_url, str) and pr_url.strip() else None
    return replace(plan, reviewer=clean_reviewer, pr_url=clean_pr_url)


def _markdown_code_span(value: str | None, default: str = "not provided") -> str:
    text = value if isinstance(value, str) and value else default
    text = re.sub(r"\s+", " ", text).strip() or default
    max_backtick_run = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    delimiter = "`" * (max_backtick_run + 1)
    if text.startswith("`") or text.endswith("`"):
        text = f" {text} "
    return f"{delimiter}{text}{delimiter}"


def render_recall_review_report(plan: RecallReviewPlan) -> str:
    lines = [
        "# Recall Review Plan",
        "",
        f"- status: `{plan.status}`",
        f"- stale: `{str(plan.stale).lower()}`",
        f"- fixtures: `{plan.fixtures_path}`",
        f"- total fixtures: `{plan.freshness.total_fixtures}`",
        f"- reviewed promotions: `{plan.freshness.reviewed_promotions}`",
        f"- seed fixtures: `{plan.freshness.seed_fixtures}`",
        f"- latest reviewed promotion: `{plan.freshness.latest_reviewed_at or 'none'}`",
        f"- limit: `{plan.limit if plan.limit is not None else 'all'}`",
        f"- pending misses: `{plan.pending_count}`",
        f"- pending returned: `{plan.pending_returned_count}`",
        f"- pending offset: `{plan.pending_offset}`",
        f"- pending next offset: `{plan.pending_next_offset}`",
        f"- pending has more: `{str(plan.pending_has_more).lower()}`",
        f"- invalid miss files: `{plan.invalid_count}`",
        f"- invalid returned: `{plan.invalid_returned_count}`",
        f"- invalid offset: `{plan.invalid_offset}`",
        f"- invalid next offset: `{plan.invalid_next_offset}`",
        f"- invalid has more: `{str(plan.invalid_has_more).lower()}`",
        f"- resolved misses: `{plan.resolved_count}`",
        "",
        "## Candidate Check",
        "",
        "Run this before writing new recall feedback:",
        "",
        "```bash",
        " ".join(plan.candidate_check_command),
        "```",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {action}" for action in plan.next_actions)
    lines.extend(["", "## Pending Misses", ""])
    if plan.pending_misses:
        for miss in plan.pending_misses:
            target = miss.expected_id or miss.expected_path or "unknown target"
            lines.append(f"- `{miss.path}`: {miss.query or 'no query'} -> `{target}`")
            if miss.redacted_fields:
                lines.append("  - redacted: `true`")
    else:
        lines.append("_No pending recall misses._")

    lines.extend(["", "## Invalid Miss Files", ""])
    if plan.invalid_misses:
        for miss in plan.invalid_misses:
            lines.append(f"- `{miss.path}`: {miss.error}")
    else:
        lines.append("_No invalid recall miss files._")

    lines.extend(["", "## Recent Resolved Misses", ""])
    if plan.recent_resolved_misses:
        for miss in plan.recent_resolved_misses:
            target = miss.expected_id or miss.expected_path or miss.promoted_fixture_id or "no target"
            lines.append(f"- `{miss.path}` ({miss.status}): {miss.query or 'no query'} -> `{target}`")
            if miss.reviewed_by or miss.reviewed_at:
                lines.append(f"  - reviewed: `{miss.reviewed_at or 'unknown'}` by `{miss.reviewed_by or 'unknown'}`")
            if miss.review_reason:
                lines.append(f"  - reason: {miss.review_reason}")
            if miss.redacted_fields:
                lines.append("  - redacted: `true`")
    else:
        lines.append("_No resolved recall misses._")

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- This report is generated review evidence.",
            "- It does not promote fixtures, reject misses, dismiss misses, or edit canonical memory.",
            "- Run `ai-dememory eval-recall` after promoting reviewed misses.",
            "",
        ]
    )
    return "\n".join(lines)


def write_recall_review_report(
    root: Path,
    plan: RecallReviewPlan,
    report_path: str | Path = DEFAULT_REVIEW_REPORT,
) -> Path:
    target = resolve_repo_path(root, report_path)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("report path must stay inside the memory root") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_recall_review_report(plan)
    if scan_text(text, "<recall-review-report>"):
        raise ValueError("recall review report rejected by secret scan")
    target.write_text(text, encoding="utf-8")
    return target


def render_recall_review_packet(plan: RecallReviewPlan) -> str:
    lines = [
        "# Recall Review Packet",
        "",
        "This generated packet helps a human reviewer decide which recall misses should become fixtures.",
        "It is not review evidence by itself and does not promote, reject, dismiss, or edit memories.",
        "",
        "## Summary",
        "",
        f"- status: `{plan.status}`",
        f"- stale: `{str(plan.stale).lower()}`",
        f"- fixtures: `{plan.fixtures_path}`",
        f"- total fixtures: `{plan.freshness.total_fixtures}`",
        f"- reviewed promotions: `{plan.freshness.reviewed_promotions}`",
        f"- seed fixtures: `{plan.freshness.seed_fixtures}`",
        f"- latest reviewed promotion: `{plan.freshness.latest_reviewed_at or 'none'}`",
        f"- limit: `{plan.limit if plan.limit is not None else 'all'}`",
        f"- pending misses: `{plan.pending_count}`",
        f"- pending returned: `{plan.pending_returned_count}`",
        f"- pending offset: `{plan.pending_offset}`",
        f"- pending next offset: `{plan.pending_next_offset}`",
        f"- pending has more: `{str(plan.pending_has_more).lower()}`",
        f"- invalid miss files: `{plan.invalid_count}`",
        f"- invalid returned: `{plan.invalid_returned_count}`",
        f"- invalid offset: `{plan.invalid_offset}`",
        f"- invalid next offset: `{plan.invalid_next_offset}`",
        f"- invalid has more: `{str(plan.invalid_has_more).lower()}`",
        f"- resolved misses: `{plan.resolved_count}`",
        f"- reviewer: {_markdown_code_span(plan.reviewer)}",
        f"- pr_url: {_markdown_code_span(plan.pr_url)}",
        "",
        "## Reviewer Workflow",
        "",
        "1. Reproduce each pending miss with the candidate check command.",
        "2. Promote only misses that still fail current FTS ranking and point to a valid memory.",
        "3. Reject stale, duplicate, unclear, or no-longer-reproducible misses.",
        "4. Run `ai-dememory eval-recall` after promotions.",
        "5. Run `ai-dememory release-evidence --strict` before release sign-off.",
        "",
        "## Candidate Check",
        "",
        "```bash",
        " ".join(plan.candidate_check_command),
        "```",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {action}" for action in plan.next_actions)
    lines.extend(["", "## Reviewer Fill-In", ""])
    if plan.pending_misses:
        for miss in plan.pending_misses:
            target = miss.expected_id or miss.expected_path or "unknown target"
            lines.extend(
                [
                    f"### `{miss.path}`",
                    "",
                    f"- query: `{miss.query or 'no query'}`",
                    f"- expected: `{target}`",
                    f"- created: `{miss.created_at or 'unknown'}`",
                    f"- source: `{miss.source_ref or 'unknown'}`",
                    f"- redacted fields: `{str(miss.redacted_fields).lower()}`",
                    "- reviewer:",
                    "- candidate check result:",
                    "- decision: promote | reject | dismiss",
                    "- reason:",
                    "",
                    "Promote command:",
                    "",
                    "```bash",
                    f"ai-dememory recall-fixtures promote-miss --miss {miss.path} --reviewed-by <name>",
                    "```",
                    "",
                    "Reject or dismiss command:",
                    "",
                    "```bash",
                    f"ai-dememory recall-fixtures review-miss --miss {miss.path} --status rejected --reviewed-by <name> --reason \"<reason>\"",
                    "```",
                    "",
                ]
            )
    else:
        lines.append("_No pending recall misses. Capture a real miss only after `recall-fixtures check-miss` confirms it._")

    lines.extend(["", "## Invalid Miss Files", ""])
    if plan.invalid_misses:
        for miss in plan.invalid_misses:
            lines.append(f"- `{miss.path}`: {miss.error}")
    else:
        lines.append("_No invalid recall miss files._")

    lines.extend(["", "## Recent Resolved Misses", ""])
    if plan.recent_resolved_misses:
        for miss in plan.recent_resolved_misses:
            target = miss.expected_id or miss.expected_path or miss.promoted_fixture_id or "no target"
            lines.append(f"- `{miss.path}` ({miss.status}): {miss.query or 'no query'} -> `{target}`")
            if miss.reviewed_by or miss.reviewed_at:
                lines.append(f"  - reviewed: `{miss.reviewed_at or 'unknown'}` by `{miss.reviewed_by or 'unknown'}`")
            if miss.review_reason:
                lines.append(f"  - reason: {miss.review_reason}")
            if miss.redacted_fields:
                lines.append("  - redacted: `true`")
    else:
        lines.append("_No resolved recall misses._")

    lines.extend(
        [
            "",
            "## Final Gates",
            "",
            "```bash",
            "ai-dememory eval-recall",
            "ai-dememory release-evidence --strict",
            "```",
            "",
            "## Boundaries",
            "",
            "- This packet is generated review guidance only.",
            "- It does not record reviewed fixture promotions.",
            "- It does not write `quality/recall-fixtures.json`.",
            "- It does not close recall miss files.",
            "- Do not paste raw chat logs, secrets, tokens, cookies, private keys, or `.env` content into recall misses.",
            "",
        ]
    )
    return "\n".join(lines)


def write_recall_review_packet(
    root: Path,
    plan: RecallReviewPlan,
    report_path: str | Path = DEFAULT_REVIEW_PACKET,
) -> Path:
    target = resolve_recall_review_packet_report_path(root, report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_recall_review_packet(plan)
    if scan_text(text, "<recall-review-packet>"):
        raise ValueError("recall review packet rejected by secret scan")
    target.write_text(text, encoding="utf-8")
    return target


def resolve_recall_review_packet_report_path(root: Path, report_path: str | Path = DEFAULT_REVIEW_PACKET) -> Path:
    root_abs = Path(os.path.abspath(root))
    candidate = Path(report_path)
    if not candidate.is_absolute():
        candidate = root_abs / candidate
    target = Path(os.path.abspath(candidate))
    reports_root = Path(os.path.abspath(root_abs / "reports"))
    try:
        target.relative_to(root_abs)
    except ValueError as exc:
        raise ValueError("report path must stay inside the memory root") from exc
    try:
        target.relative_to(reports_root)
    except ValueError as exc:
        raise ValueError("report path must stay under reports/") from exc
    reject_recall_review_packet_symlink_components(root_abs, target, "report path")
    return target


def reject_recall_review_packet_symlink_components(root_abs: Path, target: Path, label: str) -> None:
    current = root_abs
    for part in target.relative_to(root_abs).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} must not contain symlinks")


def resolve_recall_review_packet_archive_dir(
    root: Path,
    archive_dir: str | Path = DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
) -> Path:
    root_abs = Path(os.path.abspath(root))
    candidate = Path(archive_dir)
    if not candidate.is_absolute():
        candidate = root_abs / candidate
    target_dir = Path(os.path.abspath(candidate))
    allowed_dir = Path(os.path.abspath(root_abs / DEFAULT_REVIEW_PACKET_ARCHIVE_DIR))
    try:
        target_dir.relative_to(root_abs)
    except ValueError as exc:
        raise ValueError("archive dir must stay inside the memory root") from exc
    try:
        target_dir.relative_to(allowed_dir)
    except ValueError as exc:
        raise ValueError("archive dir must stay under reports/recall-review-packets") from exc
    reject_recall_review_packet_symlink_components(root_abs, target_dir, "archive dir")
    return target_dir


def recall_review_packet_archive_path(
    root: Path,
    archive_dir: str | Path = DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
    *,
    now: datetime | None = None,
) -> Path:
    target_dir = resolve_recall_review_packet_archive_dir(root, archive_dir)
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    candidate = target_dir / f"recall-review-packet-{timestamp}.md"
    suffix = 1
    while candidate.exists():
        candidate = target_dir / f"recall-review-packet-{timestamp}-{suffix}.md"
        suffix += 1
    return candidate


def write_recall_review_packet_archive(
    root: Path,
    plan: RecallReviewPlan,
    archive_dir: str | Path = DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
    *,
    now: datetime | None = None,
) -> Path:
    target = recall_review_packet_archive_path(root, archive_dir, now=now)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render_recall_review_packet(plan)
    if scan_text(text, "<recall-review-packet-archive>"):
        raise ValueError("recall review packet archive rejected by secret scan")
    target.write_text(text, encoding="utf-8")
    return target


def recall_review_packet_archive_generated_at(path: Path) -> str | None:
    match = re.fullmatch(r"recall-review-packet-(\d{8}T\d{6}Z)(?:-\d+)?\.md", path.name)
    if not match:
        return None
    try:
        generated = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return generated.isoformat().replace("+00:00", "Z")


def recall_review_packet_archive_sort_key(path: Path) -> tuple[bool, str, int, str]:
    match = re.fullmatch(r"recall-review-packet-(\d{8}T\d{6}Z)(?:-(\d+))?\.md", path.name)
    if not match:
        return (False, "", -1, path.name)
    suffix = int(match.group(2) or 0)
    return (True, match.group(1), suffix, path.name)


def recall_review_packet_archive_entries(
    root: Path,
    archive_dir: str | Path = DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
) -> tuple[Path, list[RecallReviewPacketArchiveEntry]]:
    target_dir = resolve_recall_review_packet_archive_dir(root, archive_dir)
    entries: list[RecallReviewPacketArchiveEntry] = []
    if target_dir.exists():
        for path in sorted(target_dir.glob("*.md"), key=recall_review_packet_archive_sort_key, reverse=True):
            stat = path.stat()
            entries.append(
                RecallReviewPacketArchiveEntry(
                    path=repo_relative_path(path, root),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                    generated_at=recall_review_packet_archive_generated_at(path),
                )
            )
    return target_dir, entries


def recall_review_packet_archive_status(
    root: Path,
    archive_dir: str | Path = DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    target_dir, entries = recall_review_packet_archive_entries(root, archive_dir)

    page = entries[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(entries)
    return {
        "archive_root": repo_relative_path(target_dir, root),
        "total_count": len(entries),
        "limit": limit,
        "offset": offset,
        "returned_count": len(page),
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "archives": [asdict(entry) for entry in page],
        "mutates_system": False,
        "records_fixture_promotions": False,
        "writes_fixture_file": False,
        "closes_miss_files": False,
        "writes_files": False,
    }


def recall_review_packet_archive_retention_plan(
    root: Path,
    archive_dir: str | Path = DEFAULT_REVIEW_PACKET_ARCHIVE_DIR,
    *,
    keep: int = 30,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if keep < 1:
        raise ValueError("keep must be >= 1")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    target_dir, entries = recall_review_packet_archive_entries(root, archive_dir)
    prune_candidates = entries[keep:]
    page = prune_candidates[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(prune_candidates)
    return {
        "archive_root": repo_relative_path(target_dir, root),
        "total_count": len(entries),
        "keep": keep,
        "retained_count": min(keep, len(entries)),
        "prunable_count": len(prune_candidates),
        "limit": limit,
        "offset": offset,
        "returned_count": len(page),
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "prune_candidates": [asdict(entry) for entry in page],
        "mutates_system": False,
        "records_fixture_promotions": False,
        "writes_fixture_file": False,
        "closes_miss_files": False,
        "writes_files": False,
        "deletes_files": False,
    }


def render_frontmatter_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(" ".join(str(value).splitlines()).strip())


def update_frontmatter_fields(path: Path, updates: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("miss file is missing opening frontmatter delimiter")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise ValueError("miss file is missing closing frontmatter delimiter")

    rendered_updates = {key: f"{key}: {render_frontmatter_scalar(value)}" for key, value in updates.items()}
    seen: set[str] = set()
    new_lines = list(lines)
    for index in range(1, closing_index):
        line = new_lines[index]
        if ":" not in line or line.startswith(" "):
            continue
        key = line.split(":", 1)[0].strip()
        if key in rendered_updates:
            new_lines[index] = rendered_updates[key]
            seen.add(key)
    insert_at = closing_index
    for key, line in rendered_updates.items():
        if key not in seen:
            new_lines.insert(insert_at, line)
            insert_at += 1
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def mark_recall_miss_promoted(path: Path, fixture_id: str, reviewed_by: str, reviewed_at: str) -> None:
    update_frontmatter_fields(
        path,
        {
            "status": "promoted",
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "promoted_fixture_id": fixture_id,
        },
    )


def review_recall_miss(
    root: Path,
    miss_path: str | Path,
    status: str,
    reviewed_by: str,
    reason: str,
) -> RecallMissReviewResult:
    status = status.strip().lower()
    if status not in REVIEWABLE_RECALL_MISS_STATUSES:
        raise ValueError("status must be rejected or dismissed")
    reviewed_by = reviewed_by.strip()
    if not reviewed_by:
        raise ValueError("reviewed_by is required")
    reason = " ".join(reason.split()).strip()
    if not reason:
        raise ValueError("reason is required")

    miss_file = ensure_recall_miss_path(root, miss_path)
    miss = load_recall_miss(miss_file)
    current_status = miss.get("status")
    if isinstance(current_status, str) and current_status in RESOLVED_RECALL_MISS_STATUSES:
        raise ValueError(f"recall miss is already resolved with status: {current_status}")

    scan_target = json.dumps(
        {
            "path": repo_relative_path(miss_file, root),
            "status": status,
            "reviewed_by": reviewed_by,
            "reason": reason,
        },
        sort_keys=True,
    )
    if scan_text(scan_target, "<recall-miss-review>"):
        raise ValueError("recall miss review rejected by secret scan")

    reviewed_at = reviewed_today()
    update_frontmatter_fields(
        miss_file,
        {
            "status": status,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "review_reason": reason,
        },
    )
    return RecallMissReviewResult(
        path=repo_relative_path(miss_file, root),
        status=status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        reason=reason,
        fixture_updated=False,
        canonical_memory_updated=False,
    )


def assert_promoted_fixture_passes(root: Path, fixtures_path: Path, fixture_id: str) -> None:
    results = evaluate(root, fixtures_path)
    for result in results:
        if result.id == fixture_id:
            if not result.passed:
                missing = ", ".join(result.missing_ids)
                raise ValueError(
                    f"promoted recall fixture {fixture_id} does not pass: missing {missing} "
                    f"within top {result.min_rank}"
                )
            return
    raise ValueError(f"promoted recall fixture {fixture_id} was not evaluated")


def promote_miss_to_fixture(
    root: Path,
    miss_path: str | Path,
    reviewed_by: str,
    fixture_id: str | None = None,
    notes: str | None = None,
    min_rank: int = 5,
    include_sensitive: bool = False,
    fixtures_path: str | Path = DEFAULT_FIXTURES,
) -> PromotedFixture:
    if min_rank < 1:
        raise ValueError("min_rank must be >= 1")
    reviewed_by = reviewed_by.strip()
    if not reviewed_by:
        raise ValueError("reviewed_by is required")

    miss_file = ensure_recall_miss_path(root, miss_path)
    miss = load_recall_miss(miss_file)
    status = miss.get("status")
    if isinstance(status, str) and status in RESOLVED_RECALL_MISS_STATUSES:
        raise ValueError(f"recall miss is already resolved with status: {status}")
    query = str(miss["query"]).strip()
    expected_id = resolve_expected_id(root, miss)
    source_ref = repo_relative_path(miss_file, root)
    review_date = reviewed_today()
    fixture = {
        "id": fixture_id or default_fixture_id(query),
        "query": query,
        "expected_ids": [expected_id],
        "min_rank": min_rank,
        "include_sensitive": include_sensitive,
        "notes": notes or "Promoted from reviewed recall miss.",
        "source_ref": source_ref,
        "created_at": review_date,
        "reviewed_by": reviewed_by,
        "reviewed_at": review_date,
    }

    scan_target = json.dumps(fixture, sort_keys=True)
    if scan_text(scan_target, "<recall-fixture>"):
        raise ValueError("recall fixture rejected by secret scan")

    target = resolve_repo_path(root, fixtures_path)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("fixtures path must stay inside the memory root") from exc
    fixtures = existing_fixtures(target)
    reject_duplicate_fixture(fixtures, fixture)
    previous_text = target.read_text(encoding="utf-8") if target.exists() else None
    fixtures.append(fixture)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fixtures, indent=2) + "\n", encoding="utf-8")
    try:
        load_fixtures(target)
        assert_promoted_fixture_passes(root, target, str(fixture["id"]))
    except Exception:
        if previous_text is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(previous_text, encoding="utf-8")
        raise
    mark_recall_miss_promoted(miss_file, str(fixture["id"]), reviewed_by, review_date)
    return PromotedFixture(fixture=fixture, fixtures_path=repo_relative_path(target, root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Report recall fixture provenance and freshness.")
    status.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Recall fixtures JSON path.")
    status.add_argument("--max-age-days", type=int, default=14, help="Freshness window for reviewed promotions.")
    status.add_argument("--strict", action="store_true", help="Exit nonzero when reviewed promotions are missing or stale.")
    status.add_argument("--json", action="store_true")

    review_plan = subparsers.add_parser(
        "review-plan",
        help="Plan weekly recall miss review; read-only unless --write-report is set.",
    )
    review_plan.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Recall fixtures JSON path.")
    review_plan.add_argument("--max-age-days", type=int, default=14, help="Freshness window for reviewed promotions.")
    review_plan.add_argument("--resolved-limit", type=int, default=5, help="Maximum recent resolved misses to include.")
    review_plan.add_argument("--write-report", action="store_true", help="Write reports/recall-review-plan.md.")
    review_plan.add_argument("--report-path", default=str(DEFAULT_REVIEW_REPORT), help="Generated recall review report path.")
    review_plan.add_argument("--json", action="store_true")

    packet = subparsers.add_parser("packet", help="Build a reviewer packet for weekly recall miss review.")
    packet.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Recall fixtures JSON path.")
    packet.add_argument("--max-age-days", type=int, default=14, help="Freshness window for reviewed promotions.")
    packet.add_argument("--resolved-limit", type=int, default=5, help="Maximum recent resolved misses to include.")
    packet.add_argument("--limit", type=int, default=50, help="Maximum pending and invalid miss records to include.")
    packet.add_argument("--pending-offset", type=int, default=0, help="Pending miss offset for packet pagination.")
    packet.add_argument("--invalid-offset", type=int, default=0, help="Invalid miss offset for packet pagination.")
    packet.add_argument("--reviewer", default=None, help="Optional reviewer name to pre-fill the packet header.")
    packet.add_argument("--pr-url", default=None, help="Optional PR URL to pre-fill the packet header.")
    packet.add_argument("--write-report", action="store_true", help="Write reports/recall-review-packet.md.")
    packet.add_argument("--report-path", default=str(DEFAULT_REVIEW_PACKET), help="Generated recall review packet path.")
    packet.add_argument("--archive", action="store_true", help="Write a timestamped packet copy under reports/recall-review-packets/.")
    packet.add_argument("--archive-dir", default=str(DEFAULT_REVIEW_PACKET_ARCHIVE_DIR), help="Archive directory under reports/recall-review-packets/.")
    packet.add_argument("--json", action="store_true")

    packet_archive_status = subparsers.add_parser(
        "packet-archive-status",
        help="List generated recall review packet archives without promoting fixtures.",
    )
    packet_archive_status.add_argument("--archive-dir", default=str(DEFAULT_REVIEW_PACKET_ARCHIVE_DIR))
    packet_archive_status.add_argument("--limit", type=int, default=50)
    packet_archive_status.add_argument("--offset", type=int, default=0)
    packet_archive_status.add_argument("--json", action="store_true")

    packet_archive_retention = subparsers.add_parser(
        "packet-archive-retention-plan",
        help="Plan generated recall review packet archive pruning without deleting files.",
    )
    packet_archive_retention.add_argument("--archive-dir", default=str(DEFAULT_REVIEW_PACKET_ARCHIVE_DIR))
    packet_archive_retention.add_argument("--keep", type=int, default=30, help="Newest archive files to retain.")
    packet_archive_retention.add_argument("--limit", type=int, default=50)
    packet_archive_retention.add_argument("--offset", type=int, default=0)
    packet_archive_retention.add_argument("--json", action="store_true")

    check_miss = subparsers.add_parser(
        "check-miss",
        help="Check whether a query and expected memory form a recall miss candidate without writing files.",
    )
    check_miss.add_argument("--query", required=True, help="Search query to evaluate.")
    expected_group = check_miss.add_mutually_exclusive_group(required=True)
    expected_group.add_argument("--expected-id", help="Expected memory id.")
    expected_group.add_argument("--expected-path", help="Expected memory path inside the vault.")
    check_miss.add_argument("--min-rank", type=int, default=5, help="Maximum acceptable rank.")
    check_miss.add_argument("--limit", type=int, default=10, help="Top results to inspect.")
    check_miss.add_argument("--include-sensitive", action="store_true")
    check_miss.add_argument("--json", action="store_true")

    promote = subparsers.add_parser("promote-miss", help="Promote a reviewed recall miss to a fixture.")
    promote.add_argument("--miss", required=True, help="Path under inbox/recall-feedback/.")
    promote.add_argument("--reviewed-by", required=True, help="Human reviewer name or handle.")
    promote.add_argument("--fixture-id", default=None, help="Override generated fixture id.")
    promote.add_argument("--notes", default=None, help="Reviewer notes for the fixture.")
    promote.add_argument("--min-rank", type=int, default=5)
    promote.add_argument("--include-sensitive", action="store_true")
    promote.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Recall fixtures JSON path.")
    promote.add_argument("--json", action="store_true")

    review = subparsers.add_parser("review-miss", help="Reject or dismiss a reviewed recall miss without writing fixtures.")
    review.add_argument("--miss", required=True, help="Path under inbox/recall-feedback/.")
    review.add_argument("--status", choices=sorted(REVIEWABLE_RECALL_MISS_STATUSES), required=True)
    review.add_argument("--reviewed-by", required=True, help="Human reviewer name or handle.")
    review.add_argument("--reason", required=True, help="Reviewed reason for the outcome.")
    review.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    root = repo_root(args.root)
    if args.command == "status":
        try:
            result = recall_fixture_freshness(root, args.fixtures, args.max_age_days)
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        data = asdict(result)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(
                "Recall fixture status: "
                f"{result.status}; {result.total_fixtures} fixture(s), "
                f"{result.reviewed_promotions} reviewed promotion(s)."
            )
            print(f"Latest reviewed promotion: {result.latest_reviewed_at or 'none'}")
            print(f"Next: {result.next_action}")
        return 1 if args.strict and result.stale else 0

    if args.command == "review-plan":
        try:
            result = recall_fixture_review_plan(root, args.fixtures, args.max_age_days, args.resolved_limit)
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        data = asdict(result)
        report_path: Path | None = None
        if args.write_report:
            try:
                report_path = write_recall_review_report(root, result, args.report_path)
            except (OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            data["report_path"] = repo_relative_path(report_path, root)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(
                "Recall fixture review plan: "
                f"{result.status}; {result.pending_count} pending miss(es), "
                f"{result.invalid_count} invalid miss file(s), "
                f"{result.resolved_count} resolved miss(es)."
            )
            for action in result.next_actions:
                print(f"- {action}")
            for miss in result.pending_misses:
                print(f"- pending: {miss.path} ({miss.query or 'no query'})")
            if report_path:
                print(f"Wrote {repo_relative_path(report_path, root)}")
        return 0

    if args.command == "packet":
        try:
            result = recall_fixture_review_plan(root, args.fixtures, args.max_age_days, args.resolved_limit)
            result = paginate_recall_review_plan(
                result,
                limit=args.limit,
                pending_offset=args.pending_offset,
                invalid_offset=args.invalid_offset,
            )
            result = annotate_recall_review_packet_plan(result, reviewer=args.reviewer, pr_url=args.pr_url)
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        data = asdict(result)
        data.update(
            {
                "mutates_system": False,
                "records_fixture_promotions": False,
                "writes_fixture_file": False,
                "closes_miss_files": False,
                "writes_files": False,
                "writes_archive": False,
                "report_path": None,
                "archive_path": None,
            }
        )
        report_path: Path | None = None
        archive_path: Path | None = None
        if args.archive:
            try:
                recall_review_packet_archive_path(root, args.archive_dir)
            except (OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
        if args.write_report:
            try:
                report_path = write_recall_review_packet(root, result, args.report_path)
            except (OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            data["report_path"] = repo_relative_path(report_path, root)
            data["writes_files"] = True
        if args.archive:
            try:
                archive_path = write_recall_review_packet_archive(root, result, args.archive_dir)
            except (OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
            data["archive_path"] = repo_relative_path(archive_path, root)
            data["writes_archive"] = True
            data["writes_files"] = True
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(
                "Recall review packet: "
                f"{result.status}; {result.pending_count} pending miss(es), "
                f"{result.invalid_count} invalid miss file(s)."
            )
            print("This packet is generated guidance only and does not promote fixtures.")
            for action in result.next_actions:
                print(f"- {action}")
            if report_path:
                print(f"Wrote {repo_relative_path(report_path, root)}")
            if archive_path:
                print(f"Archived {repo_relative_path(archive_path, root)}")
        return 0

    if args.command == "packet-archive-status":
        try:
            payload = recall_review_packet_archive_status(
                root,
                archive_dir=args.archive_dir,
                limit=args.limit,
                offset=args.offset,
            )
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Archive: {payload['archive_root']}")
            print(f"Archives: {payload['returned_count']}/{payload['total_count']}")
            for archive in payload["archives"]:
                generated_at = archive["generated_at"] or "unknown"
                print(f"- {archive['path']} ({archive['size_bytes']} bytes, generated_at={generated_at})")
            if payload["has_more"]:
                print(f"Next offset: {payload['next_offset']}")
        return 0

    if args.command == "packet-archive-retention-plan":
        try:
            payload = recall_review_packet_archive_retention_plan(
                root,
                archive_dir=args.archive_dir,
                keep=args.keep,
                limit=args.limit,
                offset=args.offset,
            )
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Archive: {payload['archive_root']}")
            print(f"Retention: keep newest {payload['keep']} of {payload['total_count']} archive(s)")
            print(f"Prune candidates: {payload['returned_count']}/{payload['prunable_count']}")
            for archive in payload["prune_candidates"]:
                generated_at = archive["generated_at"] or "unknown"
                print(f"- {archive['path']} ({archive['size_bytes']} bytes, generated_at={generated_at})")
            if payload["has_more"]:
                print(f"Next offset: {payload['next_offset']}")
        return 0

    if args.command == "check-miss":
        try:
            result = recall_miss_candidate(
                root,
                args.query,
                expected_id=args.expected_id,
                expected_path=args.expected_path,
                min_rank=args.min_rank,
                limit=args.limit,
                include_sensitive=args.include_sensitive,
            )
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        data = asdict(result)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            verdict = "yes" if result.candidate_miss else "no"
            rank = str(result.expected_rank) if result.expected_rank is not None else "not returned"
            print(f"Recall miss candidate: {verdict}")
            print(f"Expected id: {result.expected_id}")
            print(f"Expected rank: {rank}")
            print(f"Reason: {result.reason}")
            if result.candidate_miss:
                print("Next dry run: " + " ".join(result.capture_dry_run_command))
                print("Next write: " + " ".join(result.capture_write_command))
        return 0

    try:
        if args.command == "review-miss":
            reviewed = review_recall_miss(
                root,
                args.miss,
                args.status,
                args.reviewed_by,
                args.reason,
            )
            data = asdict(reviewed)
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                print(f"Marked {reviewed.path} as {reviewed.status}")
            return 0

        result = promote_miss_to_fixture(
            root,
            args.miss,
            args.reviewed_by,
            fixture_id=args.fixture_id,
            notes=args.notes,
            min_rank=args.min_rank,
            include_sensitive=args.include_sensitive,
            fixtures_path=args.fixtures,
        )
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    data = asdict(result)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"Added {result.fixture['id']} to {result.fixtures_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
