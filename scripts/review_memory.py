#!/usr/bin/env python3
"""Review false positives and memory conflicts without mutating canonical memory."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from config_file import ensure_safe_write_path, load_config, load_config_path, set_section, set_section_path
from memorylib import (
    FrontmatterError,
    MemoryDocument,
    extract_summary,
    parse_value,
    repo_relative_path,
    repo_root,
    slugify,
    today,
    validate_memories,
)
from secret_scan import Finding, redact_line, scan_paths, scan_text


IGNORE_NAME = ".ai-dememory-ignore.toml"
FALSE_POSITIVE_REPORT = Path("reports/false-positives.md")
CONFLICT_REPORT = Path("reports/conflicts.md")
REVIEW_RECOMMENDATION_OUTCOME_REPORT = Path("reports/review-recommendation-outcomes.md")
CONFLICT_PROPOSAL_DIR = Path("inbox/conflict-resolution")
REVIEW_RECOMMENDATION_DIR = Path("inbox/review-recommendations")
REVIEW_RECOMMENDATION_ARCHIVE_DIR = Path("archive/review-recommendations")
SAFE_SUMMARY_SENSITIVITIES = {"public", "internal"}
REVIEW_PLAN_KINDS = {"inbox", "false-positive", "conflict", "promotion", "maintenance"}
FALSE_POSITIVE_ID_RE = re.compile(r"^fp_[0-9a-f]{16}$")
CONFLICT_ID_RE = re.compile(r"^conf_[0-9a-f]{16}$")
REVIEW_RECOMMENDATION_ACTIONS = {
    "collect_evidence",
    "dismiss_candidate",
    "dismiss_conflict",
    "draft_promotion",
    "escalate",
    "ignore_false_positive",
    "keep_finding_active",
    "keep_memory",
    "maintenance_follow_up",
    "mark_superseded",
    "merge_proposal",
    "no_action",
    "organize_inbox",
    "reject_candidate",
}
REVIEW_RECOMMENDATION_OUTCOMES = {"accepted", "rejected"}


def markdown_code_span(value: Any, default: str = "none") -> str:
    text = str(value) if value not in {None, ""} else default
    text = re.sub(r"\s+", " ", text).strip() or default
    max_backtick_run = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    delimiter = "`" * (max_backtick_run + 1)
    if text.startswith("`") or text.endswith("`"):
        text = f" {text} "
    return f"{delimiter}{text}{delimiter}"


DEFAULT_FALSE_POSITIVE_REVIEW_AFTER_DAYS = 90
FALSE_POSITIVE_TRIAGE_POLICIES = {"human_only", "llm_suggests", "llm_auto_for_low_risk"}
CONFLICT_RESOLUTION_POLICIES = {"human_only", "llm_suggests", "llm_preselects", "llm_auto_for_low_risk"}
DEFAULT_HUMAN_REQUIRED_SEVERITIES = ["high", "critical"]
DEFAULT_LLM_AUTO_DENY_CATEGORIES = ["restricted", "durable", "policy"]


class ReviewError(RuntimeError):
    """Raised when review workflow input is unsafe or invalid."""


@dataclass(frozen=True)
class FalsePositiveReview:
    id: str
    path: str
    line: int
    kind: str
    redacted_line: str
    ignored: bool
    reason: str | None
    reviewer: str | None
    reviewed_at: str | None
    review_after: str | None
    review_due: bool
    review_after_status: str
    recommendation_id: str | None
    recommendation_path: str | None
    recommendation_action: str | None
    recommendation_policy_violation: bool | None


@dataclass(frozen=True)
class StaleFalsePositiveSuppression:
    id: str
    ignored: bool
    reason: str | None
    reviewer: str | None
    reviewed_at: str | None
    review_after: str | None
    review_due: bool
    review_after_status: str
    status: str


@dataclass(frozen=True)
class ConflictReview:
    id: str
    category: str
    memory_ids: list[str]
    paths: list[str]
    titles: list[str]
    overlap: list[str]
    status: str
    confidence: float
    reason: str
    suggested_action: str
    decision: str | None
    proposal_path: str | None
    reviewer: str | None
    reviewed_at: str | None
    recommendation_id: str | None
    recommendation_path: str | None
    recommendation_action: str | None
    recommendation_policy_violation: bool | None
    summaries: list[str]


@dataclass(frozen=True)
class ReviewMode:
    name: str
    summary: str
    require_human_for_durable: bool
    allow_llm_false_positive_triage: bool
    allow_llm_conflict_recommendations: bool
    allow_llm_merge_proposals: bool
    allow_autonomous_inbox_proposals: bool
    allow_apply_reviewed: bool
    require_secret_scan_before_promotion: bool
    checklist: list[str]
    forbidden_actions: list[str]


REVIEW_MODES: dict[str, ReviewMode] = {
    "strict": ReviewMode(
        name="strict",
        summary="Human-led review. LLMs may gather evidence but should not classify or recommend outcomes.",
        require_human_for_durable=True,
        allow_llm_false_positive_triage=False,
        allow_llm_conflict_recommendations=False,
        allow_llm_merge_proposals=False,
        allow_autonomous_inbox_proposals=False,
        allow_apply_reviewed=True,
        require_secret_scan_before_promotion=True,
        checklist=[
            "Run validation and secret scan before promotion.",
            "Read source captures manually.",
            "Record reviewer and reviewed_at on durable memories.",
            "Keep rejected or uncertain items in inbox.",
        ],
        forbidden_actions=[
            "Do not let an LLM decide that a secret finding is safe.",
            "Do not let an LLM choose the canonical winner for a conflict.",
            "Do not auto-promote durable memory.",
        ],
    ),
    "balanced": ReviewMode(
        name="balanced",
        summary="LLMs may group low-risk findings and recommend conflict outcomes, while humans make final decisions.",
        require_human_for_durable=True,
        allow_llm_false_positive_triage=True,
        allow_llm_conflict_recommendations=True,
        allow_llm_merge_proposals=False,
        allow_autonomous_inbox_proposals=False,
        allow_apply_reviewed=True,
        require_secret_scan_before_promotion=True,
        checklist=[
            "Use LLM grouping only for public/internal review candidates.",
            "Require a human to accept suppressions or conflict decisions.",
            "Keep merge proposal drafting as an explicit assisted-mode action.",
            "Run validation and secret scan before promotion.",
        ],
        forbidden_actions=[
            "Do not auto-promote durable memory.",
            "Do not let an LLM apply false-positive suppressions.",
            "Do not expose private/sensitive captures to LLM summaries.",
        ],
    ),
    "assisted": ReviewMode(
        name="assisted",
        summary="LLMs may draft review notes and merge proposals, while humans approve durable changes.",
        require_human_for_durable=True,
        allow_llm_false_positive_triage=True,
        allow_llm_conflict_recommendations=True,
        allow_llm_merge_proposals=True,
        allow_autonomous_inbox_proposals=False,
        allow_apply_reviewed=True,
        require_secret_scan_before_promotion=True,
        checklist=[
            "Ask the LLM for evidence-backed recommendations only.",
            "Require a human to accept false-positive suppressions.",
            "Use conflict merge proposals as drafts, not canonical memory.",
            "Run validation and secret scan before promotion.",
        ],
        forbidden_actions=[
            "Do not auto-promote durable memory.",
            "Do not include restricted summaries in LLM-readable reports.",
            "Do not suppress secret findings without human approval.",
        ],
    ),
    "autonomous_proposals": ReviewMode(
        name="autonomous_proposals",
        summary="LLMs may organize low-risk inbox proposals, but canonical and durable memory still require human approval.",
        require_human_for_durable=True,
        allow_llm_false_positive_triage=True,
        allow_llm_conflict_recommendations=True,
        allow_llm_merge_proposals=True,
        allow_autonomous_inbox_proposals=True,
        allow_apply_reviewed=False,
        require_secret_scan_before_promotion=True,
        checklist=[
            "Group related inbox candidates before review.",
            "Use LLM summaries only for public/internal content.",
            "Allow autonomous proposal cleanup only inside inbox candidate folders.",
            "Promote canonical memory only after human approval and passing checks.",
            "Leave durable, restricted, and sensitive items for explicit follow-up.",
        ],
        forbidden_actions=[
            "Do not auto-apply reviewed changes to canonical memory.",
            "Do not auto-promote durable memory.",
            "Do not expose private/sensitive captures to LLM summaries.",
        ],
    ),
}

REVIEW_MODE_ALIASES = {
    "batch": "autonomous_proposals",
}


@dataclass(frozen=True)
class ReviewPlan:
    kind: str
    mode: str
    summary: str
    policy: dict[str, Any]
    allowed_llm_actions: list[str]
    required_human_actions: list[str]
    required_checks: list[str]
    forbidden_actions: list[str]


@dataclass(frozen=True)
class ReviewRecommendationResult:
    id: str
    path: str
    kind: str
    target_id: str
    recommendation: str
    confidence: float | None
    recommended_by: str
    mode: str
    allowed_by_mode: bool
    policy_violation: bool
    requires_human_approval: bool
    writes_files: bool
    applies_review_decision: bool
    writes_canonical_memory: bool
    created_at: str


@dataclass(frozen=True)
class ReviewRecommendationRecord:
    path: str
    id: str | None
    kind: str | None
    target_id: str | None
    recommendation: str | None
    confidence: float | None
    recommended_by: str | None
    mode: str | None
    allowed_by_mode: bool | None
    policy_violation: bool
    requires_human_approval: bool
    applies_review_decision: bool
    writes_canonical_memory: bool
    created_at: str | None
    evidence: list[str]
    redacted_fields: bool
    outcome_status: str
    outcome_reviewed_by: str | None
    outcome_reviewed_at: str | None
    outcome_reason: str | None
    outcome_applies_review_decision: bool
    outcome_writes_canonical_memory: bool


@dataclass(frozen=True)
class InvalidReviewRecommendation:
    path: str
    error: str
    redacted: bool = False


def safe_invalid_review_recommendation(path: str, error: str) -> InvalidReviewRecommendation:
    findings = scan_text(error, "<review-error>")
    if not findings:
        return InvalidReviewRecommendation(path=path, error=error, redacted=False)
    redacted_error = redact_line(error, [finding.kind for finding in findings])
    return InvalidReviewRecommendation(path=path, error=redacted_error, redacted=True)


@dataclass(frozen=True)
class ReviewRecommendationArchiveResult:
    dry_run: bool
    archive_root: str
    filters: dict[str, str]
    min_outcome_days: int
    unfiltered_total_count: int
    eligible_count: int
    archived_count: int
    skipped_count: int
    candidates: list[dict[str, str]]
    archived: list[dict[str, str]]
    skipped: list[dict[str, str]]
    malformed_count: int
    malformed: list[dict[str, str]]
    writes_files: bool
    applies_review_decisions: bool
    writes_canonical_memory: bool
    canonical_memory_updated: bool


@dataclass(frozen=True)
class ReviewRecommendationArchiveRestoreResult:
    dry_run: bool
    archive_root: str
    inbox_root: str
    requested_id: str
    recursive: bool
    restored_count: int
    skipped_count: int
    candidates: list[dict[str, str]]
    restored: list[dict[str, str]]
    skipped: list[dict[str, str]]
    malformed_count: int
    malformed: list[dict[str, str]]
    writes_files: bool
    applies_review_decisions: bool
    writes_canonical_memory: bool
    canonical_memory_updated: bool


def ignore_path(root: Path) -> Path:
    return review_state_path(root)


def review_state_path(root: Path) -> Path:
    config = load_config(root)
    false_positive_config = config.get("false_positives", {})
    configured = false_positive_config.get("ignore_file")
    if configured in {None, ""}:
        selected: str | Path = IGNORE_NAME
    else:
        if false_positive_config.get("allow_ignore_file") is False:
            raise ReviewError("configured false-positive ignore file is disabled")
        selected = str(configured)

    target = unresolved_repo_path(root, selected)
    try:
        target.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewError("review state path must stay inside the memory root") from exc
    try:
        ensure_safe_write_path(target, root=root)
    except ValueError as exc:
        raise ReviewError(str(exc)) from exc
    memories_root = (root / "memories").resolve(strict=False)
    try:
        target.resolve(strict=False).relative_to(memories_root)
    except ValueError:
        pass
    else:
        raise ReviewError("review state path must not be under memories/")
    return target


def stable_id(prefix: str, parts: Iterable[object]) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def finding_id(finding: Finding) -> str:
    return stable_id(
        "fp",
        (finding.path, finding.line, finding.kind, finding.redacted_line),
    )


def conflict_id(category: str, memory_ids: Iterable[str]) -> str:
    return stable_id("conf", (category, *sorted(memory_ids)))


def load_review_config(root: Path) -> dict[str, dict[str, Any]]:
    return load_config_path(ignore_path(root))


def active_review_mode(root: Path) -> ReviewMode:
    config = load_config(root)
    configured = str(config.get("review", {}).get("mode") or "strict")
    mode = REVIEW_MODES.get(canonical_review_mode(configured))
    if mode:
        return mode
    raise ReviewError(f"unknown review mode in .ai-dememory.toml: {configured}")


def canonical_review_mode(mode_name: str) -> str:
    return REVIEW_MODE_ALIASES.get(mode_name, mode_name)


def review_modes(root: Path) -> dict[str, Any]:
    active = active_review_mode(root).name
    return {
        "active": active,
        "aliases": dict(REVIEW_MODE_ALIASES),
        "policy": review_policy_config(root),
        "modes": [review_mode_dict(mode, active == mode.name) for mode in REVIEW_MODES.values()],
    }


def review_mode_dict(mode: ReviewMode, active: bool = False) -> dict[str, Any]:
    data = asdict(mode)
    data["active"] = active
    return data


def configure_review_mode(root: Path, mode_name: str, reviewer: str | None = None) -> Path:
    mode = REVIEW_MODES.get(canonical_review_mode(mode_name))
    if not mode:
        raise ReviewError(f"unknown review mode: {mode_name}")
    config = load_config(root)
    current = dict(config.get("review", {}))
    if reviewer is not None:
        current["reviewer"] = safe_review_text(reviewer, "reviewer")
    current.update(
        {
            "mode": mode.name,
            "require_human_for_durable": mode.require_human_for_durable,
            "allow_llm_conflict_recommendations": mode.allow_llm_conflict_recommendations,
            "allow_llm_false_positive_triage": mode.allow_llm_false_positive_triage,
            "allow_llm_merge_proposals": mode.allow_llm_merge_proposals,
            "allow_autonomous_inbox_proposals": mode.allow_autonomous_inbox_proposals,
            "allow_apply_reviewed": mode.allow_apply_reviewed,
            "require_secret_scan_before_promotion": mode.require_secret_scan_before_promotion,
            "updated_at": today().isoformat(),
        }
    )
    return set_section(root, "review", current)


def review_plan(root: Path, kind: str) -> ReviewPlan:
    if kind not in REVIEW_PLAN_KINDS:
        raise ReviewError(f"unknown review plan kind: {kind}")
    mode = active_review_mode(root)
    policy = review_policy_config(root)
    allowed_llm_actions = llm_actions_for_kind(mode, kind)
    required_human_actions = human_actions_for_kind(mode, kind)
    required_checks = checks_for_kind(mode, kind)
    return ReviewPlan(
        kind=kind,
        mode=mode.name,
        summary=mode.summary,
        policy=policy,
        allowed_llm_actions=allowed_llm_actions,
        required_human_actions=required_human_actions,
        required_checks=required_checks,
        forbidden_actions=mode.forbidden_actions,
    )


def capture_review_recommendation(
    root: Path,
    kind: str,
    target_id: str,
    recommendation: str,
    rationale: str,
    recommended_by: str,
    confidence: float | None = None,
    evidence: list[str] | None = None,
) -> ReviewRecommendationResult:
    if kind not in REVIEW_PLAN_KINDS:
        raise ReviewError(f"unknown review recommendation kind: {kind}")
    if recommendation not in REVIEW_RECOMMENDATION_ACTIONS:
        allowed = ", ".join(sorted(REVIEW_RECOMMENDATION_ACTIONS))
        raise ReviewError(f"unknown review recommendation action: {recommendation}; expected one of {allowed}")
    if confidence is not None and (confidence < 0 or confidence > 1):
        raise ReviewError("confidence must be between 0 and 1")

    target_id = safe_review_text(target_id, "target_id")
    rationale = safe_review_text(rationale, "rationale")
    recommended_by = safe_review_text(recommended_by, "recommended_by")
    evidence_items = safe_review_list(evidence or [], "evidence")
    mode = active_review_mode(root)
    allowed_by_mode = recommendation_allowed_by_mode(mode, kind, recommendation)
    created_at = utc_now()
    recommendation_id = stable_id(
        "rec",
        (kind, target_id, recommendation, recommended_by, rationale, created_at),
    )
    target_dir = resolve_review_recommendation_inbox_root(root)
    filename = (
        f"{utc_file_stamp()}_{slugify(kind, 'review')}_"
        f"{slugify(target_id, 'target')}_{slugify(recommendation, 'recommendation')}_"
        f"{recommendation_id.removeprefix('rec_')[:8]}.md"
    )
    path = Path(os.path.abspath(target_dir / filename))
    try:
        path.relative_to(target_dir)
    except ValueError as exc:
        raise ReviewError("review recommendation file must stay inside review recommendation inbox") from exc
    reject_review_recommendation_symlink_components(
        Path(os.path.abspath(root)),
        path,
        "review recommendation file",
    )

    text = render_review_recommendation(
        recommendation_id=recommendation_id,
        kind=kind,
        target_id=target_id,
        recommendation=recommendation,
        rationale=rationale,
        recommended_by=recommended_by,
        confidence=confidence,
        evidence=evidence_items,
        mode=mode.name,
        allowed_by_mode=allowed_by_mode,
        policy=review_policy_config(root),
        created_at=created_at,
    )
    if scan_text(text, "<review-recommendation>"):
        raise ReviewError("review recommendation rejected by secret scan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return ReviewRecommendationResult(
        id=recommendation_id,
        path=repo_relative_path(path, root),
        kind=kind,
        target_id=target_id,
        recommendation=recommendation,
        confidence=confidence,
        recommended_by=recommended_by,
        mode=mode.name,
        allowed_by_mode=allowed_by_mode,
        policy_violation=not allowed_by_mode,
        requires_human_approval=True,
        writes_files=True,
        applies_review_decision=False,
        writes_canonical_memory=False,
        created_at=created_at,
    )


def review_recommendations(
    root: Path,
    kind: str | None = None,
    policy_violations_only: bool = False,
    outcome_status: str | None = None,
) -> dict[str, Any]:
    if kind is not None and kind not in REVIEW_PLAN_KINDS:
        raise ReviewError(f"unknown review recommendation kind: {kind}")
    if outcome_status is not None and outcome_status not in {"pending"} | REVIEW_RECOMMENDATION_OUTCOMES:
        raise ReviewError(f"unknown review recommendation outcome status: {outcome_status}")
    records, invalid = review_recommendation_state(root)
    if kind is not None:
        records = [record for record in records if record.kind == kind]
    if policy_violations_only:
        records = [record for record in records if record.policy_violation]
    if outcome_status is not None:
        records = [record for record in records if record.outcome_status == outcome_status]
    records.sort(key=lambda item: (item.created_at or "", item.path), reverse=True)
    latest_created = next((record.created_at for record in records if record.created_at), None)
    policy_violations = sum(1 for record in records if record.policy_violation)
    allowed = sum(1 for record in records if record.allowed_by_mode is True)
    needs_human = sum(1 for record in records if record.requires_human_approval)
    pending = sum(1 for record in records if record.outcome_status == "pending")
    accepted = sum(1 for record in records if record.outcome_status == "accepted")
    rejected = sum(1 for record in records if record.outcome_status == "rejected")
    return {
        "enabled": True,
        "mutates_system": False,
        "writes_files": False,
        "applies_review_decisions": False,
        "writes_canonical_memory": False,
        "recommendation_dir": REVIEW_RECOMMENDATION_DIR.as_posix(),
        "filters": {
            "kind": kind,
            "policy_violations_only": policy_violations_only,
            "outcome_status": outcome_status,
        },
        "total_count": len(records),
        "invalid_count": len(invalid),
        "policy_violation_count": policy_violations,
        "allowed_count": allowed,
        "requires_human_approval_count": needs_human,
        "pending_count": pending,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "latest_created_at": latest_created,
        "recommendations": [asdict(record) for record in records],
        "invalid": [asdict(item) for item in invalid],
        "next_actions": review_recommendation_next_actions(records, invalid),
    }


def archived_review_recommendations(
    root: Path,
    archive_root: str | Path = REVIEW_RECOMMENDATION_ARCHIVE_DIR,
    kind: str | None = None,
    outcome_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    invalid_offset: int = 0,
    recursive: bool = False,
) -> dict[str, Any]:
    if kind is not None and kind not in REVIEW_PLAN_KINDS:
        raise ReviewError(f"unknown review recommendation kind: {kind}")
    if outcome_status is not None and outcome_status not in REVIEW_RECOMMENDATION_OUTCOMES:
        raise ReviewError(f"unknown review recommendation outcome status: {outcome_status}")
    if limit < 1:
        raise ReviewError("limit must be at least 1")
    if offset < 0:
        raise ReviewError("offset must be zero or greater")
    if invalid_offset < 0:
        raise ReviewError("invalid_offset must be zero or greater")

    archive_target = resolve_review_recommendation_archive_root(root, archive_root)
    records: list[ReviewRecommendationRecord] = []
    invalid: list[InvalidReviewRecommendation] = []
    if archive_target.exists():
        for path in iter_review_recommendation_archive_files(archive_target, recursive):
            relpath = path.absolute().relative_to(root.resolve()).as_posix()
            if path.is_symlink():
                invalid.append(InvalidReviewRecommendation(path=relpath, error="archive entry must not be a symlink"))
                continue
            source = path.resolve()
            try:
                source.relative_to(archive_target)
            except ValueError:
                invalid.append(InvalidReviewRecommendation(path=relpath, error="archive entry must stay under archive root"))
                continue
            try:
                data = parse_review_recommendation_frontmatter_text(path.read_text(encoding="utf-8"), path)
                records.append(parse_review_recommendation_record(relpath, data))
            except (OSError, FrontmatterError, ReviewError) as exc:
                invalid.append(safe_invalid_review_recommendation(relpath, str(exc)))

    if kind is not None:
        records = [record for record in records if record.kind == kind]
    if outcome_status is not None:
        records = [record for record in records if record.outcome_status == outcome_status]
    records.sort(key=lambda item: (item.outcome_reviewed_at or "", item.created_at or "", item.path), reverse=True)
    invalid.sort(key=lambda item: item.path)
    accepted = sum(1 for record in records if record.outcome_status == "accepted")
    rejected = sum(1 for record in records if record.outcome_status == "rejected")
    kind_counts: dict[str, int] = {}
    for record in records:
        key = str(record.kind or "unknown")
        kind_counts[key] = kind_counts.get(key, 0) + 1
    page = records[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(records)
    invalid_page = invalid[invalid_offset : invalid_offset + limit]
    invalid_next_offset = invalid_offset + len(invalid_page)
    invalid_has_more = invalid_next_offset < len(invalid)
    return {
        "enabled": True,
        "mutates_system": False,
        "writes_files": False,
        "applies_review_decisions": False,
        "writes_canonical_memory": False,
        "archive_root": repo_relative_path(archive_target, root),
        "filters": {
            "kind": kind,
            "outcome_status": outcome_status,
            "limit": limit,
            "offset": offset,
            "invalid_offset": invalid_offset,
            "recursive": recursive,
        },
        "total_count": len(records),
        "returned_count": len(page),
        "offset": offset,
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "invalid_count": len(invalid),
        "invalid_returned_count": len(invalid_page),
        "invalid_offset": invalid_offset,
        "invalid_next_offset": invalid_next_offset if invalid_has_more else None,
        "invalid_has_more": invalid_has_more,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "status_counts": {"accepted": accepted, "rejected": rejected},
        "kind_counts": dict(sorted(kind_counts.items())),
        "recommendations": [asdict(record) for record in page],
        "invalid": [asdict(item) for item in invalid_page],
        "next_actions": archived_review_recommendation_next_actions(records, invalid),
    }


def archived_review_recommendation_next_actions(
    records: list[ReviewRecommendationRecord],
    invalid: list[InvalidReviewRecommendation],
) -> list[str]:
    actions: list[str] = []
    if invalid:
        actions.append("Fix malformed archived recommendation artifacts before relying on archive counts.")
    if records:
        actions.append("Inspect archived recommendations as audit history; apply decisions only through explicit review commands.")
    if not actions:
        actions.append("No archived review recommendations found.")
    return actions


def review_recommendation_state(
    root: Path,
) -> tuple[list[ReviewRecommendationRecord], list[InvalidReviewRecommendation]]:
    directory = resolve_review_recommendation_inbox_root(root)
    records: list[ReviewRecommendationRecord] = []
    invalid: list[InvalidReviewRecommendation] = []
    if not directory.exists():
        return records, invalid
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        relpath = path.absolute().relative_to(root.resolve()).as_posix()
        if path.is_symlink():
            invalid.append(InvalidReviewRecommendation(path=relpath, error="review recommendation entry must not be a symlink"))
            continue
        source = path.resolve()
        try:
            source.relative_to(directory)
        except ValueError:
            invalid.append(InvalidReviewRecommendation(path=relpath, error="review recommendation entry must stay under inbox root"))
            continue
        try:
            data = parse_review_recommendation_frontmatter_text(path.read_text(encoding="utf-8"), path)
            records.append(parse_review_recommendation_record(relpath, data))
        except (OSError, FrontmatterError, ReviewError) as exc:
            invalid.append(safe_invalid_review_recommendation(relpath, str(exc)))
    return records, invalid


def review_recommendation_outcome_age_days(outcome_reviewed_at: str | None) -> int | None:
    if not outcome_reviewed_at:
        return None
    try:
        reviewed_date = date.fromisoformat(str(outcome_reviewed_at)[:10])
    except ValueError:
        return None
    return (today() - reviewed_date).days


def resolve_review_recommendation_archive_root(root: Path, output: str | Path) -> Path:
    root_abs, target = resolve_review_recommendation_safe_path(root, output)
    archive_root = Path(os.path.abspath(root_abs / REVIEW_RECOMMENDATION_ARCHIVE_DIR))
    try:
        target.relative_to(archive_root)
    except ValueError as exc:
        raise ReviewError("review recommendation archive path must stay under archive/review-recommendations") from exc
    reject_review_recommendation_symlink_components(root_abs, target, "review recommendation archive path")
    return target


def resolve_review_recommendation_inbox_root(root: Path) -> Path:
    root_abs, target = resolve_review_recommendation_safe_path(root, REVIEW_RECOMMENDATION_DIR)
    reject_review_recommendation_symlink_components(root_abs, target, "review recommendation inbox path")
    return target


def resolve_review_recommendation_safe_path(root: Path, output: str | Path) -> tuple[Path, Path]:
    root_abs = Path(os.path.abspath(root))
    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = root_abs / candidate
    target = Path(os.path.abspath(candidate))
    try:
        target.relative_to(root_abs)
    except ValueError as exc:
        raise ReviewError("review recommendation path must stay inside the memory root") from exc
    return root_abs, target


def reject_review_recommendation_symlink_components(root_abs: Path, target: Path, label: str) -> None:
    current = root_abs
    for part in target.relative_to(root_abs).parts:
        current = current / part
        if current.is_symlink():
            raise ReviewError(f"{label} must not contain symlinks")


def iter_review_recommendation_archive_files(archive_target: Path, recursive: bool = False) -> list[Path]:
    pattern = "**/*.md" if recursive else "*.md"
    return sorted(path for path in archive_target.glob(pattern) if path.is_file() or path.is_symlink())


def archive_review_recommendations(
    root: Path,
    apply: bool = False,
    archive_root: str | Path = REVIEW_RECOMMENDATION_ARCHIVE_DIR,
    outcome_status: str = "reviewed",
    min_outcome_days: int = 0,
    limit: int = 20,
) -> ReviewRecommendationArchiveResult:
    if outcome_status not in {"reviewed", *REVIEW_RECOMMENDATION_OUTCOMES}:
        raise ReviewError("outcome status must be reviewed, accepted, or rejected")
    if min_outcome_days < 0:
        raise ReviewError("minimum outcome age must be zero or greater")
    if limit < 1:
        raise ReviewError("limit must be at least 1")

    archive_target = resolve_review_recommendation_archive_root(root, archive_root)
    inbox_root = resolve_review_recommendation_inbox_root(root)
    records, invalid = review_recommendation_state(root)
    candidates: list[dict[str, str]] = []
    archived: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for record in records:
        if record.outcome_status == "pending":
            skipped.append({"path": record.path, "id": record.id or "", "reason": "pending_outcome"})
            continue
        if outcome_status != "reviewed" and record.outcome_status != outcome_status:
            skipped.append({"path": record.path, "id": record.id or "", "reason": "outcome_status_filter"})
            continue
        age_days = review_recommendation_outcome_age_days(record.outcome_reviewed_at)
        if age_days is None:
            skipped.append({"path": record.path, "id": record.id or "", "reason": "invalid_outcome_reviewed_at"})
            continue
        if age_days < min_outcome_days:
            skipped.append({"path": record.path, "id": record.id or "", "reason": "outcome_too_recent"})
            continue

        source = (root / record.path).resolve()
        try:
            source.relative_to(inbox_root)
        except ValueError:
            skipped.append({"path": record.path, "id": record.id or "", "reason": "outside_recommendation_inbox"})
            continue
        destination = archive_target / source.name
        destination_relpath = repo_relative_path(destination, root)
        item = {
            "path": record.path,
            "archive_path": destination_relpath,
            "id": record.id or "",
            "kind": record.kind or "",
            "target_id": record.target_id or "",
            "recommendation": record.recommendation or "",
            "outcome_status": record.outcome_status,
            "outcome_reviewed_at": record.outcome_reviewed_at or "",
        }
        if destination.exists():
            skipped.append({**item, "reason": "archive_path_exists"})
            continue
        candidates.append(item)
        if apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
            archived.append(item)

    return ReviewRecommendationArchiveResult(
        dry_run=not apply,
        archive_root=repo_relative_path(archive_target, root),
        filters={"outcome_status": outcome_status},
        min_outcome_days=min_outcome_days,
        unfiltered_total_count=len(records),
        eligible_count=len(candidates),
        archived_count=len(archived),
        skipped_count=len(skipped),
        candidates=candidates[:limit],
        archived=archived[:limit],
        skipped=skipped[:limit],
        malformed_count=len(invalid),
        malformed=[asdict(item) for item in invalid[:limit]],
        writes_files=apply,
        applies_review_decisions=False,
        writes_canonical_memory=False,
        canonical_memory_updated=False,
    )


def restore_archived_review_recommendation(
    root: Path,
    recommendation_id: str,
    apply: bool = False,
    archive_root: str | Path = REVIEW_RECOMMENDATION_ARCHIVE_DIR,
    recursive: bool = False,
) -> ReviewRecommendationArchiveRestoreResult:
    recommendation_id = safe_review_text(recommendation_id, "recommendation_id")
    archive_target = resolve_review_recommendation_archive_root(root, archive_root)
    inbox_root = resolve_review_recommendation_inbox_root(root)
    candidates: list[dict[str, str]] = []
    restored: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    invalid: list[InvalidReviewRecommendation] = []

    if archive_target.exists():
        for path in iter_review_recommendation_archive_files(archive_target, recursive):
            relpath = path.absolute().relative_to(root.resolve()).as_posix()
            if path.is_symlink():
                skipped.append({"path": relpath, "id": "", "reason": "symlink_archive_entry"})
                continue
            source = path.resolve()
            try:
                source.relative_to(archive_target)
            except ValueError:
                skipped.append({"path": relpath, "id": "", "reason": "outside_archive_root"})
                continue
            try:
                data = parse_review_recommendation_frontmatter_text(path.read_text(encoding="utf-8"), path)
                record = parse_review_recommendation_record(relpath, data)
            except (OSError, FrontmatterError, ReviewError) as exc:
                invalid.append(safe_invalid_review_recommendation(relpath, str(exc)))
                continue
            if record.id != recommendation_id:
                continue
            destination = inbox_root / source.name
            destination_relpath = repo_relative_path(destination, root)
            item = {
                "path": relpath,
                "restore_path": destination_relpath,
                "id": record.id or "",
                "kind": record.kind or "",
                "target_id": record.target_id or "",
                "recommendation": record.recommendation or "",
                "outcome_status": record.outcome_status,
                "outcome_reviewed_at": record.outcome_reviewed_at or "",
            }
            if destination.exists():
                skipped.append({**item, "reason": "restore_path_exists"})
                continue
            candidates.append(item)
            if apply:
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.replace(destination)
                restored.append(item)

    if not candidates and not skipped:
        skipped.append({"path": "", "id": recommendation_id, "reason": "not_found"})

    return ReviewRecommendationArchiveRestoreResult(
        dry_run=not apply,
        archive_root=repo_relative_path(archive_target, root),
        inbox_root=REVIEW_RECOMMENDATION_DIR.as_posix(),
        requested_id=recommendation_id,
        recursive=recursive,
        restored_count=len(restored),
        skipped_count=len(skipped),
        candidates=candidates,
        restored=restored,
        skipped=skipped,
        malformed_count=len(invalid),
        malformed=[asdict(item) for item in invalid],
        writes_files=apply,
        applies_review_decisions=False,
        writes_canonical_memory=False,
        canonical_memory_updated=False,
    )


def parse_review_recommendation_frontmatter_text(text: str, path: Path | None = None) -> dict[str, Any]:
    data, _ = parse_review_recommendation_artifact_text(text, path)
    return data


def parse_review_recommendation_artifact_text(
    text: str,
    path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    label = str(path) if path else "<review-recommendation>"
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError(f"{label}: missing opening frontmatter delimiter")

    closing_index: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = idx
            break
    if closing_index is None:
        raise FrontmatterError(f"{label}: missing closing frontmatter delimiter")

    data: dict[str, Any] = {}
    current_key: str | None = None
    for line_no, line in enumerate(lines[1:closing_index], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  "):
            if current_key is None:
                raise FrontmatterError(f"{label}:{line_no}: nested field without parent")
            current_value = data[current_key]
            if stripped.startswith("- "):
                if current_value == {}:
                    current_value = []
                    data[current_key] = current_value
                if not isinstance(current_value, list):
                    raise FrontmatterError(f"{label}:{line_no}: list item under non-list field")
                current_value.append(parse_value(stripped[2:].strip()))
                continue
            if not isinstance(current_value, dict):
                raise FrontmatterError(f"{label}:{line_no}: nested map under non-map field")
            key, value = split_review_key_value(stripped, label, line_no)
            current_value[key] = parse_value(value)
            continue
        key, value = split_review_key_value(stripped, label, line_no)
        if value == "":
            data[key] = {}
            current_key = key
        else:
            data[key] = parse_value(value)
            current_key = None
    body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
    return data, body


def split_review_key_value(line: str, label: str, line_no: int) -> tuple[str, str]:
    if ":" not in line:
        raise FrontmatterError(f"{label}:{line_no}: expected 'key: value'")
    key, value = line.split(":", 1)
    key = key.strip()
    if not key:
        raise FrontmatterError(f"{label}:{line_no}: empty key")
    return key, value.strip()


def record_review_recommendation_outcome(
    root: Path,
    recommendation_id: str,
    outcome_status: str,
    reviewer: str,
    reason: str,
) -> dict[str, Any]:
    if outcome_status not in REVIEW_RECOMMENDATION_OUTCOMES:
        raise ReviewError(f"unknown review recommendation outcome status: {outcome_status}")
    recommendation_id = safe_review_text(recommendation_id, "recommendation_id")
    reviewer = safe_review_text(reviewer, "reviewer")
    reason = safe_review_text(reason, "reason")
    records, _ = review_recommendation_state(root)
    match = next((record for record in records if record.id == recommendation_id), None)
    if match is None:
        raise ReviewError(f"unknown review recommendation id: {recommendation_id}")
    path = (root / match.path).resolve()
    directory = (root / REVIEW_RECOMMENDATION_DIR).resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ReviewError("review recommendation outcome path must stay inside recommendation inbox") from exc
    data, body = parse_review_recommendation_artifact_text(path.read_text(encoding="utf-8"), path)
    data["outcome_status"] = outcome_status
    data["outcome_reviewed_by"] = reviewer
    data["outcome_reviewed_at"] = utc_now()
    data["outcome_reason"] = reason
    data["outcome_applies_review_decision"] = False
    data["outcome_writes_canonical_memory"] = False
    updated_text = render_review_recommendation_artifact_text(data, body)
    if scan_text(updated_text, "<review-recommendation-outcome>"):
        raise ReviewError("review recommendation outcome rejected by secret scan")
    path.write_text(updated_text, encoding="utf-8")
    refreshed = parse_review_recommendation_record(match.path, data)
    return {
        "path": match.path,
        "id": recommendation_id,
        "outcome_status": outcome_status,
        "outcome_reviewed_by": reviewer,
        "outcome_reviewed_at": data["outcome_reviewed_at"],
        "outcome_reason": reason,
        "outcome_applies_review_decision": False,
        "outcome_writes_canonical_memory": False,
        "writes_files": True,
        "writes_canonical_memory": False,
        "applies_review_decision": False,
        "recommendation": asdict(refreshed),
    }


def review_recommendation_outcome_records(
    root: Path,
    kind: str | None = None,
    outcome_status: str = "reviewed",
) -> tuple[list[ReviewRecommendationRecord], list[InvalidReviewRecommendation]]:
    if kind is not None and kind not in REVIEW_PLAN_KINDS:
        raise ReviewError(f"unknown review recommendation kind: {kind}")
    if outcome_status not in {"reviewed", *REVIEW_RECOMMENDATION_OUTCOMES}:
        raise ReviewError("outcome status must be reviewed, accepted, or rejected")
    records, invalid = review_recommendation_state(root)
    if kind is not None:
        records = [record for record in records if record.kind == kind]
    if outcome_status == "reviewed":
        records = [record for record in records if record.outcome_status in REVIEW_RECOMMENDATION_OUTCOMES]
    else:
        records = [record for record in records if record.outcome_status == outcome_status]
    records.sort(key=lambda item: (item.outcome_reviewed_at or "", item.created_at or "", item.path), reverse=True)
    invalid.sort(key=lambda item: item.path)
    return records, invalid


def review_recommendation_outcome_report_payload(
    root: Path,
    kind: str | None = None,
    outcome_status: str = "reviewed",
    limit: int = 50,
    offset: int = 0,
    invalid_offset: int = 0,
) -> dict[str, Any]:
    if limit < 1:
        raise ReviewError("limit must be at least 1")
    if offset < 0:
        raise ReviewError("offset must be zero or greater")
    if invalid_offset < 0:
        raise ReviewError("invalid_offset must be zero or greater")
    records, invalid = review_recommendation_outcome_records(root, kind=kind, outcome_status=outcome_status)
    accepted = sum(1 for record in records if record.outcome_status == "accepted")
    rejected = sum(1 for record in records if record.outcome_status == "rejected")
    page = records[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(records)
    invalid_page = invalid[invalid_offset : invalid_offset + limit]
    invalid_next_offset = invalid_offset + len(invalid_page)
    invalid_has_more = invalid_next_offset < len(invalid)
    return {
        "enabled": True,
        "mutates_system": False,
        "writes_files": False,
        "applies_review_decisions": False,
        "writes_canonical_memory": False,
        "filters": {
            "kind": kind,
            "outcome_status": outcome_status,
            "limit": limit,
            "offset": offset,
            "invalid_offset": invalid_offset,
        },
        "total_count": len(records),
        "returned_count": len(page),
        "offset": offset,
        "next_offset": next_offset if has_more else None,
        "has_more": has_more,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "status_counts": {"accepted": accepted, "rejected": rejected},
        "invalid_count": len(invalid),
        "invalid_returned_count": len(invalid_page),
        "invalid_offset": invalid_offset,
        "invalid_next_offset": invalid_next_offset if invalid_has_more else None,
        "invalid_has_more": invalid_has_more,
        "recommendations": [asdict(record) for record in page],
        "invalid": [asdict(item) for item in invalid_page],
        "next_actions": review_recommendation_outcome_report_next_actions(records, invalid),
    }


def review_recommendation_outcome_report_next_actions(
    records: list[ReviewRecommendationRecord],
    invalid: list[InvalidReviewRecommendation],
) -> list[str]:
    actions: list[str] = []
    if invalid:
        actions.append("Fix malformed review recommendation artifacts before outcome sign-off.")
    if records:
        actions.append("Archive reviewed recommendation artifacts after retention review if no follow-up is needed.")
    else:
        actions.append("No reviewed recommendation outcomes match the selected filters.")
    actions.append("This report does not apply review decisions or mutate canonical memory.")
    return actions


def render_review_recommendation_outcome_report(payload: dict[str, Any]) -> str:
    generated_at = utc_now()
    filters = payload["filters"]
    lines = [
        "# Review Recommendation Outcomes",
        "",
        f"Generated at: {generated_at}",
        "",
        "No review decisions were applied. No canonical memory files were modified.",
        "",
        "## Summary",
        "",
        f"- kind: `{filters.get('kind') or 'all'}`",
        f"- outcome_status: `{filters.get('outcome_status')}`",
        f"- limit: `{filters.get('limit')}`",
        f"- offset: `{payload['offset']}`",
        f"- next_offset: `{payload['next_offset']}`",
        f"- has_more: `{str(payload['has_more']).lower()}`",
        f"- total_count: `{payload['total_count']}`",
        f"- returned_count: `{payload['returned_count']}`",
        f"- accepted_count: `{payload['accepted_count']}`",
        f"- rejected_count: `{payload['rejected_count']}`",
        f"- invalid_count: `{payload['invalid_count']}`",
        f"- invalid_returned_count: `{payload['invalid_returned_count']}`",
        f"- invalid_offset: `{payload['invalid_offset']}`",
        f"- invalid_next_offset: `{payload['invalid_next_offset']}`",
        f"- invalid_has_more: `{str(payload['invalid_has_more']).lower()}`",
        f"- applies_review_decisions: `{str(payload['applies_review_decisions']).lower()}`",
        f"- writes_canonical_memory: `{str(payload['writes_canonical_memory']).lower()}`",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {action}" for action in payload["next_actions"])
    lines.append("")

    recommendations = payload["recommendations"]
    if recommendations:
        lines.extend(["## Reviewed Recommendations", ""])
        for item in recommendations:
            lines.extend(
                [
                    f"### {item.get('id') or item.get('path')}",
                    "",
                    f"- path: {markdown_code_span(item.get('path'))}",
                    f"- kind: {markdown_code_span(item.get('kind'), default='unknown')}",
                    f"- target_id: {markdown_code_span(item.get('target_id'), default='unknown')}",
                    f"- recommendation: {markdown_code_span(item.get('recommendation'), default='unknown')}",
                    f"- outcome_status: {markdown_code_span(item.get('outcome_status'))}",
                    f"- outcome_reviewed_by: {markdown_code_span(item.get('outcome_reviewed_by'), default='unknown')}",
                    f"- outcome_reviewed_at: {markdown_code_span(item.get('outcome_reviewed_at'), default='unknown')}",
                    f"- outcome_reason: {markdown_code_span(item.get('outcome_reason'))}",
                    f"- outcome_applies_review_decision: `{str(item.get('outcome_applies_review_decision')).lower()}`",
                    f"- outcome_writes_canonical_memory: `{str(item.get('outcome_writes_canonical_memory')).lower()}`",
                    f"- policy_violation: `{str(item.get('policy_violation')).lower()}`",
                    "",
                ]
            )
    else:
        lines.extend(["_No reviewed recommendation outcomes matched the selected filters._", ""])

    invalid = payload["invalid"]
    if invalid:
        lines.extend(["## Malformed Recommendation Artifacts", ""])
        for item in invalid:
            lines.extend([f"- {markdown_code_span(item.get('path'))}: {markdown_code_span(item.get('error'))}", ""])
    return "\n".join(lines).rstrip() + "\n"


def write_review_recommendation_outcome_report(
    root: Path,
    output: str | Path = REVIEW_RECOMMENDATION_OUTCOME_REPORT,
    kind: str | None = None,
    outcome_status: str = "reviewed",
    limit: int = 50,
    offset: int = 0,
    invalid_offset: int = 0,
) -> tuple[Path, dict[str, Any]]:
    path = resolve_generated_report_path(root, output)
    payload = review_recommendation_outcome_report_payload(
        root,
        kind=kind,
        outcome_status=outcome_status,
        limit=limit,
        offset=offset,
        invalid_offset=invalid_offset,
    )
    text = render_review_recommendation_outcome_report(payload)
    if scan_text(text, "<review-recommendation-outcome-report>"):
        raise ReviewError("review recommendation outcome report rejected by secret scan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, payload


def render_review_recommendation_artifact_text(data: dict[str, Any], body: str) -> str:
    order = [
        "id",
        "type",
        "kind",
        "target_id",
        "recommendation",
        "confidence",
        "recommended_by",
        "mode",
        "allowed_by_mode",
        "policy_violation",
        "requires_human_approval",
        "applies_review_decision",
        "writes_canonical_memory",
        "created_at",
        "evidence",
        "outcome_status",
        "outcome_reviewed_by",
        "outcome_reviewed_at",
        "outcome_reason",
        "outcome_applies_review_decision",
        "outcome_writes_canonical_memory",
    ]
    emitted: set[str] = set()
    lines = ["---"]
    for key in order:
        if key not in data:
            continue
        emitted.add(key)
        value = data[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            if value:
                lines.extend(f"  - {frontmatter_scalar(item)}" for item in value)
            else:
                lines.append("  - null")
        else:
            lines.append(f"{key}: {frontmatter_scalar(value)}")
    for key in sorted(str(item) for item in data if str(item) not in emitted):
        value = data[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {frontmatter_scalar(item)}" for item in value)
        elif isinstance(value, dict):
            continue
        else:
            lines.append(f"{key}: {frontmatter_scalar(value)}")
    lines.extend(["---", ""])
    if body:
        lines.append(body.rstrip())
        lines.append("")
    return "\n".join(lines)


def parse_review_recommendation_record(relpath: str, data: dict[str, Any]) -> ReviewRecommendationRecord:
    if data.get("type") != "review-recommendation":
        raise ReviewError("recommendation artifact must have type: review-recommendation")
    redacted = False
    fields: dict[str, str | None] = {}
    for field in (
        "id",
        "kind",
        "target_id",
        "recommendation",
        "recommended_by",
        "mode",
        "created_at",
        "outcome_status",
        "outcome_reviewed_by",
        "outcome_reviewed_at",
        "outcome_reason",
    ):
        value, flagged = safe_review_metadata_text(data.get(field), field, relpath)
        fields[field] = value
        redacted = redacted or flagged
    evidence_values, evidence_redacted = safe_review_metadata_list(data.get("evidence"), "evidence", relpath)
    redacted = redacted or evidence_redacted
    kind = fields["kind"]
    if kind is not None and kind not in REVIEW_PLAN_KINDS:
        raise ReviewError(f"unknown recommendation kind: {kind}")
    recommendation = fields["recommendation"]
    if recommendation is not None and recommendation not in REVIEW_RECOMMENDATION_ACTIONS:
        raise ReviewError(f"unknown recommendation action: {recommendation}")
    outcome_status = fields["outcome_status"] or "pending"
    if outcome_status not in {"pending"} | REVIEW_RECOMMENDATION_OUTCOMES:
        raise ReviewError(f"unknown recommendation outcome status: {outcome_status}")
    confidence = parse_optional_confidence(data.get("confidence"))
    return ReviewRecommendationRecord(
        path=relpath,
        id=fields["id"],
        kind=kind,
        target_id=fields["target_id"],
        recommendation=recommendation,
        confidence=confidence,
        recommended_by=fields["recommended_by"],
        mode=fields["mode"],
        allowed_by_mode=optional_bool(data.get("allowed_by_mode")),
        policy_violation=bool(data.get("policy_violation") is True),
        requires_human_approval=bool(data.get("requires_human_approval") is True),
        applies_review_decision=bool(data.get("applies_review_decision") is True),
        writes_canonical_memory=bool(data.get("writes_canonical_memory") is True),
        created_at=fields["created_at"],
        evidence=evidence_values,
        redacted_fields=redacted,
        outcome_status=outcome_status,
        outcome_reviewed_by=fields["outcome_reviewed_by"],
        outcome_reviewed_at=fields["outcome_reviewed_at"],
        outcome_reason=fields["outcome_reason"],
        outcome_applies_review_decision=bool(data.get("outcome_applies_review_decision") is True),
        outcome_writes_canonical_memory=bool(data.get("outcome_writes_canonical_memory") is True),
    )


def safe_review_metadata_text(value: Any, field: str, relpath: str) -> tuple[str | None, bool]:
    if not isinstance(value, str) or not value.strip():
        return None, False
    text = " ".join(value.split()).strip()
    if scan_text(f"{field}: {text}", relpath):
        return "<redacted:secret-like>", True
    return text, False


def safe_review_metadata_list(value: Any, field: str, relpath: str) -> tuple[list[str], bool]:
    if value is None or value == "":
        return [], False
    items = value if isinstance(value, list) else [value]
    output: list[str] = []
    redacted = False
    for index, item in enumerate(items, start=1):
        if item is None:
            continue
        text, flagged = safe_review_metadata_text(str(item), f"{field}_{index}", relpath)
        if text:
            output.append(text)
        redacted = redacted or flagged
    return output, redacted


def parse_optional_confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise ReviewError(f"invalid recommendation confidence: {value}") from exc
    if confidence < 0 or confidence > 1:
        raise ReviewError("recommendation confidence must be between 0 and 1")
    return confidence


def optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "on"}:
            return True
        if lowered in {"false", "no", "0", "off"}:
            return False
    raise ReviewError(f"invalid boolean recommendation metadata: {value}")


def review_recommendation_next_actions(
    records: list[ReviewRecommendationRecord],
    invalid: list[InvalidReviewRecommendation],
) -> list[str]:
    actions: list[str] = []
    if invalid:
        actions.append("Fix or remove malformed review recommendation artifacts before review sign-off.")
    if records:
        actions.append("Review recommendation artifacts, then run explicit human-approved review commands for accepted outcomes.")
    else:
        actions.append("No advisory review recommendations are pending.")
    if any(record.policy_violation for record in records):
        actions.append("Escalate policy-violation recommendations before taking any review action.")
    actions.append("Run `ai-dememory review plan --kind <kind>` before accepting a recommendation.")
    return actions


def recommendation_link_values(
    root: Path,
    recommendation_id: str | None,
    *,
    kind: str,
    target_id: str,
    expected_actions: set[str],
) -> dict[str, Any]:
    if recommendation_id is None or recommendation_id == "":
        return {}
    recommendation_id = safe_review_text(recommendation_id, "recommendation_id")
    records, _ = review_recommendation_state(root)
    match = next((record for record in records if record.id == recommendation_id), None)
    if match is None:
        raise ReviewError(f"unknown review recommendation id: {recommendation_id}")
    if match.kind != kind:
        raise ReviewError(f"recommendation {recommendation_id} has kind {match.kind}; expected {kind}")
    if match.target_id != target_id:
        raise ReviewError(
            f"recommendation {recommendation_id} targets {match.target_id}; expected {target_id}"
        )
    if match.recommendation not in expected_actions:
        expected = ", ".join(sorted(expected_actions))
        raise ReviewError(
            f"recommendation {recommendation_id} action {match.recommendation}; expected one of {expected}"
        )
    return {
        "recommendation_id": recommendation_id,
        "recommendation_path": match.path,
        "recommendation_action": match.recommendation,
        "recommendation_policy_violation": match.policy_violation,
    }


def safe_review_list(values: list[str], field: str) -> list[str]:
    output: list[str] = []
    for index, value in enumerate(values, start=1):
        output.append(safe_review_text(str(value), f"{field}_{index}"))
    return output


def recommendation_allowed_by_mode(mode: ReviewMode, kind: str, recommendation: str) -> bool:
    if recommendation in {"collect_evidence", "escalate", "no_action"}:
        return True
    if kind == "false-positive":
        return mode.allow_llm_false_positive_triage
    if kind == "conflict":
        return mode.allow_llm_conflict_recommendations
    if kind == "inbox":
        return mode.allow_autonomous_inbox_proposals or recommendation in {"reject_candidate", "dismiss_candidate"}
    if kind == "promotion":
        return mode.name != "strict"
    if kind == "maintenance":
        return recommendation == "maintenance_follow_up"
    return False


def render_review_recommendation(
    recommendation_id: str,
    kind: str,
    target_id: str,
    recommendation: str,
    rationale: str,
    recommended_by: str,
    confidence: float | None,
    evidence: list[str],
    mode: str,
    allowed_by_mode: bool,
    policy: dict[str, Any],
    created_at: str,
) -> str:
    policy_violation = not allowed_by_mode
    lines = [
        "---",
        f"id: {frontmatter_scalar(recommendation_id)}",
        "type: review-recommendation",
        f"kind: {frontmatter_scalar(kind)}",
        f"target_id: {frontmatter_scalar(target_id)}",
        f"recommendation: {frontmatter_scalar(recommendation)}",
        f"confidence: {frontmatter_scalar(confidence)}",
        f"recommended_by: {frontmatter_scalar(recommended_by)}",
        f"mode: {frontmatter_scalar(mode)}",
        f"allowed_by_mode: {frontmatter_scalar(allowed_by_mode)}",
        f"policy_violation: {frontmatter_scalar(policy_violation)}",
        "requires_human_approval: true",
        "applies_review_decision: false",
        "writes_canonical_memory: false",
        f"created_at: {frontmatter_scalar(created_at)}",
        "evidence:",
    ]
    if evidence:
        lines.extend(f"  - {frontmatter_scalar(item)}" for item in evidence)
    else:
        lines.append("  - null")
    lines.extend(
        [
            "---",
            "",
            f"# Review Recommendation: {kind} `{target_id}`",
            "",
            f"- recommendation: `{recommendation}`",
            f"- confidence: `{confidence if confidence is not None else 'unknown'}`",
            f"- recommended_by: `{recommended_by}`",
            f"- active mode: `{mode}`",
            f"- allowed by mode: `{str(allowed_by_mode).lower()}`",
            f"- policy violation: `{str(policy_violation).lower()}`",
            "- requires human approval: `true`",
            "- applies review decision: `false`",
            "- writes canonical memory: `false`",
            "",
            "## Rationale",
            "",
            rationale,
            "",
            "## Evidence",
            "",
        ]
    )
    if evidence:
        lines.extend(f"- {item}" for item in evidence)
    else:
        lines.append("_No evidence supplied._")
    lines.extend(
        [
            "",
            "## Active Policy Snapshot",
            "",
            "```json",
            json.dumps(policy, indent=2, sort_keys=True),
            "```",
            "",
            "## Boundaries",
            "",
            "- This artifact stores an advisory recommendation only.",
            "- It does not suppress false positives, resolve conflicts, promote memory, or edit canonical memory.",
            "- A human reviewer must run the explicit review command for any accepted outcome.",
            "",
        ]
    )
    return "\n".join(lines)


def frontmatter_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(" ".join(str(value).splitlines()).strip())


def review_policy_config(root: Path) -> dict[str, Any]:
    config = load_config(root)
    false_positive_config = config.get("false_positives", {})
    conflict_config = config.get("conflicts", {})
    return {
        "false_positives": {
            "enabled": config_bool(false_positive_config.get("enabled"), True),
            "triage_policy": config_enum(
                false_positive_config.get("triage_policy"),
                FALSE_POSITIVE_TRIAGE_POLICIES,
                "human_only",
                "false-positive triage policy",
            ),
            "allow_ignore_file": config_bool(false_positive_config.get("allow_ignore_file"), True),
            "ignore_file": str(false_positive_config.get("ignore_file") or IGNORE_NAME),
            "review_after_days": false_positive_review_after_days(root),
        },
        "conflicts": {
            "enabled": config_bool(conflict_config.get("enabled"), True),
            "scan_on_validate": config_bool(conflict_config.get("scan_on_validate"), True),
            "scan_on_consolidate": config_bool(conflict_config.get("scan_on_consolidate"), True),
            "resolution_policy": config_enum(
                conflict_config.get("resolution_policy"),
                CONFLICT_RESOLUTION_POLICIES,
                "human_only",
                "conflict resolution policy",
            ),
            "llm_preselect_min_confidence": config_float(
                conflict_config.get("llm_preselect_min_confidence"),
                0.85,
                "conflict LLM preselect minimum confidence",
            ),
            "human_required_severities": config_string_list(
                conflict_config.get("human_required_severities"),
                DEFAULT_HUMAN_REQUIRED_SEVERITIES,
            ),
            "llm_auto_deny_categories": config_string_list(
                conflict_config.get("llm_auto_deny_categories"),
                DEFAULT_LLM_AUTO_DENY_CATEGORIES,
            ),
        },
    }


def require_false_positive_review_enabled(root: Path) -> None:
    if not review_policy_config(root)["false_positives"]["enabled"]:
        raise ReviewError("false-positive review is disabled by .ai-dememory.toml")


def require_conflict_review_enabled(root: Path) -> None:
    if not review_policy_config(root)["conflicts"]["enabled"]:
        raise ReviewError("conflict review is disabled by .ai-dememory.toml")


def false_positive_review_metadata(root: Path) -> dict[str, Any]:
    policy = review_policy_config(root)["false_positives"]
    return {
        "enabled": policy["enabled"],
        "policy": {
            "triage_policy": policy["triage_policy"],
            "allow_ignore_file": policy["allow_ignore_file"],
            "ignore_file": policy["ignore_file"],
            "review_after_days": policy["review_after_days"],
        },
    }


def conflict_review_metadata(root: Path) -> dict[str, Any]:
    policy = review_policy_config(root)["conflicts"]
    return {
        "enabled": policy["enabled"],
        "policy": {
            "scan_on_validate": policy["scan_on_validate"],
            "scan_on_consolidate": policy["scan_on_consolidate"],
            "resolution_policy": policy["resolution_policy"],
            "llm_preselect_min_confidence": policy["llm_preselect_min_confidence"],
            "human_required_severities": policy["human_required_severities"],
            "llm_auto_deny_categories": policy["llm_auto_deny_categories"],
        },
    }


def config_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ReviewError(f"invalid boolean config value: {value}")


def config_enum(value: Any, allowed: set[str], default: str, label: str) -> str:
    if value is None or value == "":
        return default
    selected = str(value)
    if selected not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ReviewError(f"unknown {label}: {selected}; expected one of {allowed_values}")
    return selected


def config_float(value: Any, default: float, label: str) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ReviewError(f"invalid {label}: {value}") from exc


def config_string_list(value: Any, default: list[str]) -> list[str]:
    if value is None or value == "":
        return list(default)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, (tuple, set)):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip().startswith("["):
        stripped = value.strip()
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if stripped.endswith("]"):
            return [
                item.strip().strip("\"'")
                for item in stripped[1:-1].split(",")
                if item.strip().strip("\"'")
            ]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def llm_actions_for_kind(mode: ReviewMode, kind: str) -> list[str]:
    actions = ["Collect evidence and cite memory ids, paths, and report ids."]
    if kind == "false-positive" and mode.allow_llm_false_positive_triage:
        actions.append("Draft false-positive triage notes for human approval.")
    if kind == "conflict" and mode.allow_llm_conflict_recommendations:
        actions.append("Recommend conflict outcomes with supporting evidence.")
    if kind == "conflict" and mode.allow_llm_merge_proposals:
        actions.append("Draft conflict merge proposals under inbox/conflict-resolution/.")
    if kind == "inbox" and mode.allow_autonomous_inbox_proposals:
        actions.append("Organize or deduplicate low-risk inbox proposals without touching canonical memory.")
    if kind == "inbox":
        actions.append("Summarize non-sensitive inbox candidates for review.")
    if kind == "maintenance":
        actions.append("Summarize generated reports and identify follow-up candidates.")
    if kind == "promotion" and mode.name != "strict":
        actions.append("Draft canonical memory text for human review.")
    return actions


def human_actions_for_kind(mode: ReviewMode, kind: str) -> list[str]:
    actions = ["Approve or reject the recommendation explicitly."]
    if mode.require_human_for_durable:
        actions.append("Approve every durable memory write and set reviewed provenance.")
    if kind == "false-positive":
        actions.append("Confirm the redacted finding is a false positive before suppressing it.")
    if kind == "conflict":
        actions.append("Choose dismiss, keep, supersede, or merge after reading the source memories.")
    if kind == "promotion":
        actions.append("Move approved content into memories/ manually or through an explicit reviewed apply step.")
    if kind == "maintenance":
        actions.append("Decide whether generated maintenance findings should become inbox candidates.")
    return actions


def checks_for_kind(mode: ReviewMode, kind: str) -> list[str]:
    checks = ["ai-dememory validate"]
    if mode.require_secret_scan_before_promotion or kind in {"false-positive", "promotion", "inbox"}:
        checks.append("ai-dememory secret-scan")
    if kind == "conflict":
        checks.append("ai-dememory review conflicts")
    if kind == "false-positive":
        checks.append("ai-dememory review false-positives")
    if kind == "promotion":
        checks.extend(["ai-dememory index", "ai-dememory eval-recall"])
    return checks


def safe_review_text(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ReviewError(f"{field} is required")
    findings = scan_text(value, f"<{field}>")
    if findings:
        kinds = ", ".join(sorted({finding.kind for finding in findings}))
        raise ReviewError(f"{field} contains secret-like content: {kinds}")
    return value


def false_positive_reviews(root: Path) -> list[FalsePositiveReview]:
    if not review_policy_config(root)["false_positives"]["enabled"]:
        return []
    config = load_review_config(root)
    reviews: list[FalsePositiveReview] = []
    for finding in scan_paths(root):
        fp_id = finding_id(finding)
        metadata = config.get(f"false_positives.{fp_id}", {})
        ignored = metadata.get("ignored") is True
        review_after = string_or_none(metadata.get("review_after"))
        review_due, review_after_status = review_after_state(ignored, review_after)
        reviews.append(
            FalsePositiveReview(
                id=fp_id,
                path=finding.path,
                line=finding.line,
                kind=finding.kind,
                redacted_line=finding.redacted_line,
                ignored=ignored,
                reason=string_or_none(metadata.get("reason")),
                reviewer=string_or_none(metadata.get("reviewer")),
                reviewed_at=string_or_none(metadata.get("reviewed_at")),
                review_after=review_after,
                review_due=review_due,
                review_after_status=review_after_status,
                recommendation_id=string_or_none(metadata.get("recommendation_id")),
                recommendation_path=string_or_none(metadata.get("recommendation_path")),
                recommendation_action=string_or_none(metadata.get("recommendation_action")),
                recommendation_policy_violation=optional_bool(metadata.get("recommendation_policy_violation")),
            )
        )
    return sorted(reviews, key=lambda item: (item.path, item.line, item.kind, item.id))


def require_false_positive_review_id(root: Path, fp_id: str, *, allow_stale: bool = False) -> str:
    if not FALSE_POSITIVE_ID_RE.fullmatch(fp_id):
        raise ReviewError("invalid false-positive id")
    if any(review.id == fp_id for review in false_positive_reviews(root)):
        return fp_id
    if allow_stale:
        metadata = load_review_config(root).get(f"false_positives.{fp_id}", {})
        if metadata.get("ignored") is True:
            return fp_id
    raise ReviewError(f"unknown false-positive id: {fp_id}")


def review_after_state(ignored: bool, review_after: str | None) -> tuple[bool, str]:
    if not ignored:
        return False, "not_ignored"
    if not review_after:
        return False, "not_scheduled"
    try:
        due_date = datetime.fromisoformat(review_after).date()
    except ValueError:
        return True, "invalid"
    if due_date <= today():
        return True, "due"
    return False, "scheduled"


def ignore_false_positive(
    root: Path,
    fp_id: str,
    reason: str,
    reviewer: str,
    review_after_days: int | None = None,
    recommendation_id: str | None = None,
) -> Path:
    require_false_positive_review_enabled(root)
    fp_id = require_false_positive_review_id(root, fp_id)
    reason = safe_review_text(reason, "reason")
    reviewer = safe_review_text(reviewer, "reviewer")
    effective_review_after_days = false_positive_review_after_days(root, review_after_days)
    values: dict[str, Any] = {
        "ignored": True,
        "reason": reason,
        "reviewer": reviewer,
        "reviewed_at": today().isoformat(),
    }
    values.update(
        recommendation_link_values(
            root,
            recommendation_id,
            kind="false-positive",
            target_id=fp_id,
            expected_actions={"ignore_false_positive"},
        )
    )
    if effective_review_after_days is not None:
        values["review_after"] = (today() + timedelta(days=max(1, effective_review_after_days))).isoformat()
    return set_section_path(ignore_path(root), f"false_positives.{fp_id}", values, root=root)


def false_positive_review_after_days(root: Path, override: int | None = None) -> int | None:
    if override is not None:
        return max(1, int(override))
    config = load_config(root)
    value = config.get("false_positives", {}).get("review_after_days")
    if value in {None, ""}:
        return DEFAULT_FALSE_POSITIVE_REVIEW_AFTER_DAYS
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return DEFAULT_FALSE_POSITIVE_REVIEW_AFTER_DAYS


def unignore_false_positive(root: Path, fp_id: str, reviewer: str, recommendation_id: str | None = None) -> Path:
    require_false_positive_review_enabled(root)
    fp_id = require_false_positive_review_id(root, fp_id, allow_stale=True)
    reviewer = safe_review_text(reviewer, "reviewer")
    values: dict[str, Any] = {
        "ignored": False,
        "reason": "unignored after review",
        "reviewer": reviewer,
        "reviewed_at": today().isoformat(),
    }
    values.update(
        recommendation_link_values(
            root,
            recommendation_id,
            kind="false-positive",
            target_id=fp_id,
            expected_actions={"keep_finding_active"},
        )
    )
    return set_section_path(
        ignore_path(root),
        f"false_positives.{fp_id}",
        values,
        root=root,
    )


def filter_false_positive_reviews(reviews: list[FalsePositiveReview], due_only: bool = False) -> list[FalsePositiveReview]:
    if not due_only:
        return reviews
    return [item for item in reviews if item.review_due]


def stale_false_positive_suppressions(
    root: Path,
    current_reviews: list[FalsePositiveReview] | None = None,
) -> list[StaleFalsePositiveSuppression]:
    if not review_policy_config(root)["false_positives"]["enabled"]:
        return []
    config = load_review_config(root)
    reviews = current_reviews if current_reviews is not None else false_positive_reviews(root)
    current_ids = {item.id for item in reviews}
    stale: list[StaleFalsePositiveSuppression] = []
    for section, metadata in sorted(config.items()):
        prefix = "false_positives."
        if not section.startswith(prefix):
            continue
        fp_id = section.removeprefix(prefix)
        if fp_id in current_ids or metadata.get("ignored") is not True:
            continue
        review_after = string_or_none(metadata.get("review_after"))
        review_due, review_after_status = review_after_state(True, review_after)
        stale.append(
            StaleFalsePositiveSuppression(
                id=fp_id,
                ignored=True,
                reason=string_or_none(metadata.get("reason")),
                reviewer=string_or_none(metadata.get("reviewer")),
                reviewed_at=string_or_none(metadata.get("reviewed_at")),
                review_after=review_after,
                review_due=review_due,
                review_after_status=review_after_status,
                status="stale_suppression",
            )
        )
    return stale


def render_report_policy_lines(metadata: dict[str, Any] | None) -> list[str]:
    if metadata is None:
        return []
    lines = [
        "## Review Policy",
        "",
        f"- enabled: `{format_report_policy_value(metadata.get('enabled', True))}`",
    ]
    policy = metadata.get("policy")
    if isinstance(policy, dict):
        for key, value in policy.items():
            lines.append(f"- {key}: `{format_report_policy_value(value)}`")
    lines.append("")
    return lines


def format_report_policy_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def render_false_positive_report(
    reviews: list[FalsePositiveReview],
    due_only: bool = False,
    metadata: dict[str, Any] | None = None,
) -> str:
    generated_at = utc_now()
    active = [item for item in reviews if not item.ignored]
    ignored = [item for item in reviews if item.ignored]
    due = [item for item in ignored if item.review_due]
    lines = [
        "# False Positive Review",
        "",
        f"Generated at: {generated_at}",
        "",
        "No memory files were modified.",
        "",
        "## Summary",
        "",
        f"- filter: `{'due_only' if due_only else 'all'}`",
        f"- findings: {len(reviews)}",
        f"- active: {len(active)}",
        f"- ignored: {len(ignored)}",
        f"- review_due: {len(due)}",
        "",
    ]
    lines.extend(render_report_policy_lines(metadata))
    if not reviews:
        message = "_No false-positive suppressions are due for review._" if due_only else "_No suspected secret findings._"
        lines.extend([message, ""])
        return "\n".join(lines)

    for item in reviews:
        lines.extend(
            [
                f"## {item.id}",
                "",
                f"- status: `{'ignored' if item.ignored else 'active'}`",
                f"- path: `{item.path}`",
                f"- line: `{item.line}`",
                f"- kind: `{item.kind}`",
                f"- redacted: `{item.redacted_line}`",
            ]
        )
        if item.ignored:
            lines.extend(
                [
                    f"- reason: {item.reason or ''}",
                    f"- reviewer: `{item.reviewer or ''}`",
                    f"- reviewed_at: `{item.reviewed_at or ''}`",
                    f"- review_after: `{item.review_after or ''}`",
                    f"- review_after_status: `{item.review_after_status}`",
                    f"- review_due: `{str(item.review_due).lower()}`",
                    f"- recommendation_id: `{item.recommendation_id or ''}`",
                    f"- recommendation_action: `{item.recommendation_action or ''}`",
                    f"- recommendation_policy_violation: `{str(item.recommendation_policy_violation).lower() if item.recommendation_policy_violation is not None else ''}`",
                ]
            )
        lines.append("")
    return "\n".join(lines)


def render_stale_false_positive_report(
    items: list[StaleFalsePositiveSuppression],
    metadata: dict[str, Any] | None = None,
) -> str:
    generated_at = utc_now()
    due = [item for item in items if item.review_due]
    lines = [
        "# Stale False-Positive Suppression Review",
        "",
        f"Generated at: {generated_at}",
        "",
        "No memory files were modified.",
        "",
        "## Summary",
        "",
        f"- stale_suppressions: {len(items)}",
        f"- review_due: {len(due)}",
        "",
    ]
    lines.extend(render_report_policy_lines(metadata))
    if not items:
        lines.extend(["_No stale false-positive suppressions._", ""])
        return "\n".join(lines)
    for item in items:
        lines.extend(
            [
                f"## {item.id}",
                "",
                f"- status: `{item.status}`",
                f"- ignored: `{str(item.ignored).lower()}`",
                f"- reason: {item.reason or ''}",
                f"- reviewer: `{item.reviewer or ''}`",
                f"- reviewed_at: `{item.reviewed_at or ''}`",
                f"- review_after: `{item.review_after or ''}`",
                f"- review_after_status: `{item.review_after_status}`",
                f"- review_due: `{str(item.review_due).lower()}`",
                "",
            ]
        )
    return "\n".join(lines)


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    return unresolved_repo_path(root, path).resolve()


def unresolved_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate


def resolve_report_path(root: Path, output: str | Path) -> Path:
    target = resolve_repo_path(root, output)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewError("report path must stay inside the memory root") from exc
    return target


def resolve_generated_report_path(root: Path, output: str | Path) -> Path:
    target = unresolved_repo_path(root, output)
    try:
        target.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewError("report path must stay inside the memory root") from exc
    try:
        ensure_safe_write_path(target, root=root)
    except ValueError as exc:
        raise ReviewError(str(exc)) from exc
    reports_root = (root / "reports").resolve()
    try:
        target.resolve(strict=False).relative_to(reports_root)
    except ValueError as exc:
        raise ReviewError("report path must stay under reports/") from exc
    return target


def configured_path(root: Path, section: str, key: str, default: str | Path) -> str | Path:
    value = load_config(root).get(section, {}).get(key)
    if value in {None, ""}:
        return default
    return str(value)


def conflict_report_path(root: Path, output: str | Path | None = None) -> Path:
    selected = output if output is not None else configured_path(root, "conflicts", "report_path", CONFLICT_REPORT)
    return resolve_generated_report_path(root, selected)


def conflict_proposal_dir(root: Path) -> Path:
    selected = configured_path(root, "conflicts", "proposal_path", CONFLICT_PROPOSAL_DIR)
    target = unresolved_repo_path(root, selected)
    try:
        target.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewError("conflict proposal path must stay inside the memory root") from exc
    try:
        ensure_safe_write_path(target, root=root)
    except ValueError as exc:
        raise ReviewError(str(exc)) from exc
    try:
        target.resolve(strict=False).relative_to((root / "inbox").resolve())
    except ValueError as exc:
        raise ReviewError("conflict proposal path must stay under inbox/") from exc
    return target


def write_false_positive_report(
    root: Path,
    output: Path = FALSE_POSITIVE_REPORT,
    due_only: bool = False,
) -> tuple[Path, list[FalsePositiveReview]]:
    path = resolve_generated_report_path(root, output)
    reviews = filter_false_positive_reviews(false_positive_reviews(root), due_only=due_only)
    text = render_false_positive_report(
        reviews,
        due_only=due_only,
        metadata=false_positive_review_metadata(root),
    )
    if scan_text(text, "<false-positive-report>"):
        raise ReviewError("false-positive report rejected by secret scan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, reviews


def write_stale_false_positive_report(
    root: Path,
    output: Path = Path("reports/stale-false-positives.md"),
) -> tuple[Path, list[StaleFalsePositiveSuppression]]:
    path = resolve_generated_report_path(root, output)
    items = stale_false_positive_suppressions(root)
    text = render_stale_false_positive_report(items, metadata=false_positive_review_metadata(root))
    if scan_text(text, "<stale-false-positive-report>"):
        raise ReviewError("stale false-positive report rejected by secret scan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, items


def conflict_reviews(root: Path) -> list[ConflictReview]:
    if not review_policy_config(root)["conflicts"]["enabled"]:
        return []
    documents, errors = validate_memories(root)
    if errors:
        raise ReviewError("memory validation failed:\n" + "\n".join(errors))

    grouped: dict[tuple[str, str], list[MemoryDocument]] = {}
    for document in documents:
        if document.frontmatter.get("status") in {"archived", "superseded", "expired"}:
            continue
        for key in document_keys(document):
            grouped.setdefault(key, []).append(document)

    by_pair: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for (source, value), matches in grouped.items():
        unique = dedupe_documents(matches)
        if len(unique) < 2:
            continue
        category = classify_conflict(unique)
        ids = tuple(sorted(str(document.frontmatter["id"]) for document in unique))
        bucket = by_pair.setdefault(
            (category, ids),
            {"category": category, "documents": unique, "overlap": []},
        )
        bucket["overlap"].append(f"{source}:{value}")

    config = load_review_config(root)
    conflicts: list[ConflictReview] = []
    for (_, ids), bucket in sorted(by_pair.items(), key=lambda item: (item[0][0], item[0][1])):
        documents = sorted(bucket["documents"], key=lambda item: str(item.frontmatter["id"]))
        category = str(bucket["category"])
        conf_id = conflict_id(category, ids)
        metadata = config.get(f"conflicts.{conf_id}", {})
        status = string_or_none(metadata.get("status")) or "active"
        confidence = min(0.95, 0.65 + 0.1 * len(bucket["overlap"]))
        conflicts.append(
            ConflictReview(
                id=conf_id,
                category=category,
                memory_ids=list(ids),
                paths=[repo_relative_path(document.path, root) for document in documents],
                titles=[str(document.frontmatter["title"]) for document in documents],
                overlap=sorted(set(str(item) for item in bucket["overlap"])),
                status=status,
                confidence=confidence,
                reason=conflict_reason(category, bucket["overlap"]),
                suggested_action=suggested_action(category),
                decision=string_or_none(metadata.get("decision")),
                proposal_path=string_or_none(metadata.get("proposal_path")),
                reviewer=string_or_none(metadata.get("reviewer")),
                reviewed_at=string_or_none(metadata.get("reviewed_at")),
                recommendation_id=string_or_none(metadata.get("recommendation_id")),
                recommendation_path=string_or_none(metadata.get("recommendation_path")),
                recommendation_action=string_or_none(metadata.get("recommendation_action")),
                recommendation_policy_violation=optional_bool(metadata.get("recommendation_policy_violation")),
                summaries=[safe_summary(document) for document in documents],
            )
        )
    return conflicts


def document_keys(document: MemoryDocument) -> list[tuple[str, str]]:
    data = document.frontmatter
    keys = [("title", normalize_key(str(data.get("title", ""))))]
    for alias in data.get("aliases") or []:
        normalized = normalize_key(str(alias))
        if normalized:
            keys.append(("alias", normalized))
    return [(source, value) for source, value in keys if value]


def normalize_key(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def dedupe_documents(documents: list[MemoryDocument]) -> list[MemoryDocument]:
    seen: set[str] = set()
    output: list[MemoryDocument] = []
    for document in documents:
        memory_id = str(document.frontmatter["id"])
        if memory_id in seen:
            continue
        seen.add(memory_id)
        output.append(document)
    return output


def classify_conflict(documents: list[MemoryDocument]) -> str:
    sensitivities = {str(document.frontmatter.get("sensitivity")) for document in documents}
    if sensitivities & {"private", "sensitive", "secret-prohibited"}:
        return "restricted_conflict"

    statuses = {str(document.frontmatter.get("status")) for document in documents}
    if "stale" in statuses and "active" in statuses:
        return "stale_vs_current"

    tags = {
        str(tag).lower()
        for document in documents
        for tag in (document.frontmatter.get("tags") or [])
    }
    types = {str(document.frontmatter.get("type")) for document in documents}
    if "tool" in types and any(document_has_policy_marker(document) for document in documents):
        return "tool_policy_conflict"
    if "preference" in tags or "preferences" in tags or "policy" in tags:
        return "preference_conflict"
    if "project" in types:
        return "project_decision_conflict"
    return "duplicate"


def document_has_policy_marker(document: MemoryDocument) -> bool:
    data = document.frontmatter
    tags = {str(tag).lower() for tag in (data.get("tags") or [])}
    if tags & {"policy", "tool-policy", "tool_policy"}:
        return True
    title = normalize_key(str(data.get("title", "")))
    aliases = [normalize_key(str(alias)) for alias in (data.get("aliases") or [])]
    return "policy" in title.split() or any("policy" in alias.split() for alias in aliases)


def conflict_reason(category: str, overlap: list[str]) -> str:
    joined = ", ".join(sorted(set(overlap)))
    if category == "restricted_conflict":
        return f"Restricted memories share identifying keys: {joined}."
    if category == "stale_vs_current":
        return f"Stale and current memories share identifying keys: {joined}."
    if category == "tool_policy_conflict":
        return f"Tool policy memories share identifying keys: {joined}."
    if category == "preference_conflict":
        return f"Preference or policy memories share identifying keys: {joined}."
    if category == "project_decision_conflict":
        return f"Project decision memories share identifying keys: {joined}."
    return f"Memories share duplicate title or alias keys: {joined}."


def suggested_action(category: str) -> str:
    if category == "restricted_conflict":
        return "Review manually and avoid copying restricted content into reports."
    if category == "stale_vs_current":
        return "Confirm whether the stale memory should stay stale, be superseded, or be refreshed."
    if category == "tool_policy_conflict":
        return "Review tool-policy precedence and write a merge proposal before changing canonical policy."
    if category in {"preference_conflict", "project_decision_conflict"}:
        return "Decide whether one memory supersedes the other or write a merge proposal."
    return "Dismiss if intentional, or merge/supersede duplicates after review."


def safe_summary(document: MemoryDocument) -> str:
    if document.frontmatter.get("sensitivity") not in SAFE_SUMMARY_SENSITIVITIES:
        return "_Summary omitted because sensitivity is restricted._"
    return extract_summary(document.content) or "_No summary available._"


def dismiss_conflict(
    root: Path,
    conf_id: str,
    reason: str,
    reviewer: str,
    recommendation_id: str | None = None,
) -> Path:
    require_conflict_review_enabled(root)
    conf_id = require_conflict(root, conf_id).id
    reason = safe_review_text(reason, "reason")
    reviewer = safe_review_text(reviewer, "reviewer")
    values: dict[str, Any] = {
        "status": "dismissed",
        "decision": reason,
        "reviewer": reviewer,
        "reviewed_at": today().isoformat(),
    }
    values.update(
        recommendation_link_values(
            root,
            recommendation_id,
            kind="conflict",
            target_id=conf_id,
            expected_actions={"dismiss_conflict"},
        )
    )
    return set_section_path(
        ignore_path(root),
        f"conflicts.{conf_id}",
        values,
        root=root,
    )


def resolve_conflict(
    root: Path,
    conf_id: str,
    reviewer: str,
    keep: str | None = None,
    merge_proposal: bool = False,
    recommendation_id: str | None = None,
) -> Path:
    require_conflict_review_enabled(root)
    reviewer = safe_review_text(reviewer, "reviewer")
    if keep and merge_proposal:
        raise ReviewError("--keep and --merge-proposal are mutually exclusive")
    conflict = require_conflict(root, conf_id)
    conf_id = conflict.id
    if keep:
        keep = safe_review_text(keep, "keep")
        if keep not in conflict.memory_ids:
            raise ReviewError(f"keep memory id must belong to conflict {conf_id}: {keep}")
        values: dict[str, Any] = {
            "status": "resolved",
            "decision": f"keep:{keep}",
            "reviewer": reviewer,
            "reviewed_at": today().isoformat(),
        }
        values.update(
            recommendation_link_values(
                root,
                recommendation_id,
                kind="conflict",
                target_id=conf_id,
                expected_actions={"keep_memory"},
            )
        )
        return set_section_path(
            ignore_path(root),
            f"conflicts.{conf_id}",
            values,
            root=root,
        )
    if merge_proposal:
        link_values = recommendation_link_values(
            root,
            recommendation_id,
            kind="conflict",
            target_id=conf_id,
            expected_actions={"merge_proposal"},
        )
        proposal = write_conflict_merge_proposal(root, conflict, reviewer)
        values = {
            "status": "review_proposed",
            "decision": "merge_proposal",
            "proposal_path": repo_relative_path(proposal, root),
            "reviewer": reviewer,
            "reviewed_at": today().isoformat(),
        }
        values.update(link_values)
        return set_section_path(
            ignore_path(root),
            f"conflicts.{conf_id}",
            values,
            root=root,
        )
    raise ReviewError("resolve requires --keep <memory-id> or --merge-proposal")


def require_conflict(root: Path, conf_id: str) -> ConflictReview:
    if not CONFLICT_ID_RE.fullmatch(conf_id):
        raise ReviewError("invalid conflict id")
    for conflict in conflict_reviews(root):
        if conflict.id == conf_id:
            return conflict
    raise ReviewError(f"unknown conflict id: {conf_id}")


def write_conflict_merge_proposal(root: Path, conflict: ConflictReview, reviewer: str) -> Path:
    directory = conflict_proposal_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    slug = slugify(conflict.id, fallback="conflict")
    path = directory / f"{utc_file_stamp()}-{slug}.md"
    lines = [
        f"# Conflict Merge Proposal: {conflict.id}",
        "",
        f"- reviewer: `{reviewer}`",
        f"- category: `{conflict.category}`",
        f"- status: `{conflict.status}`",
        f"- confidence: `{conflict.confidence:.2f}`",
        f"- memory_ids: `{', '.join(conflict.memory_ids)}`",
        f"- paths: `{', '.join(conflict.paths)}`",
        f"- overlap: `{', '.join(conflict.overlap)}`",
        "",
        "## Reason",
        "",
        conflict.reason,
        "",
        "## Suggested Resolution",
        "",
        "- Choose one canonical memory to keep, or create a reviewed replacement.",
        "- Mark superseded memories only after human approval.",
        "- Re-run `ai-dememory review conflicts` after the change.",
        "",
        "## Summaries",
        "",
    ]
    for memory_id, path_value, summary in zip(conflict.memory_ids, conflict.paths, conflict.summaries):
        lines.extend([f"### {memory_id}", "", f"- path: `{path_value}`", "", summary, ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def render_conflict_report(
    conflicts: list[ConflictReview],
    metadata: dict[str, Any] | None = None,
) -> str:
    generated_at = utc_now()
    active = [item for item in conflicts if item.status == "active"]
    lines = [
        "# Memory Conflict Review",
        "",
        f"Generated at: {generated_at}",
        "",
        "No memory files were modified.",
        "",
        "## Summary",
        "",
        f"- conflicts: {len(conflicts)}",
        f"- active: {len(active)}",
        f"- reviewed: {len(conflicts) - len(active)}",
        "",
    ]
    lines.extend(render_report_policy_lines(metadata))
    if not conflicts:
        lines.extend(["_No conflicts detected._", ""])
        return "\n".join(lines)

    for item in conflicts:
        lines.extend(
            [
                f"## {item.id}",
                "",
                f"- category: `{item.category}`",
                f"- status: `{item.status}`",
                f"- confidence: `{item.confidence:.2f}`",
                f"- memory_ids: `{', '.join(item.memory_ids)}`",
                f"- paths: `{', '.join(item.paths)}`",
                f"- titles: `{', '.join(item.titles)}`",
                f"- overlap: `{', '.join(item.overlap)}`",
                f"- reason: {item.reason}",
                f"- suggested_action: {item.suggested_action}",
            ]
        )
        if item.decision:
            lines.append(f"- decision: {item.decision}")
        if item.proposal_path:
            lines.append(f"- proposal_path: `{item.proposal_path}`")
        if item.reviewer:
            lines.append(f"- reviewer: `{item.reviewer}`")
        if item.reviewed_at:
            lines.append(f"- reviewed_at: `{item.reviewed_at}`")
        if item.recommendation_id:
            lines.append(f"- recommendation_id: `{item.recommendation_id}`")
        if item.recommendation_action:
            lines.append(f"- recommendation_action: `{item.recommendation_action}`")
        if item.recommendation_policy_violation is not None:
            lines.append(f"- recommendation_policy_violation: `{str(item.recommendation_policy_violation).lower()}`")
        lines.extend(["", "### Summaries", ""])
        for memory_id, summary in zip(item.memory_ids, item.summaries):
            lines.extend([f"- `{memory_id}`: {summary}"])
        lines.append("")
    return "\n".join(lines)


def write_conflict_report(root: Path, output: str | Path | None = None) -> tuple[Path, list[ConflictReview]]:
    path = conflict_report_path(root, output)
    conflicts = conflict_reviews(root)
    text = render_conflict_report(conflicts, metadata=conflict_review_metadata(root))
    if scan_text(text, "<conflict-report>"):
        raise ReviewError("conflict report rejected by secret scan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, conflicts


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value)
    return value if value else None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2))


def display_path(path: Path, root: Path) -> str:
    try:
        return repo_relative_path(path, root)
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Generate review reports.")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    false_report = review_sub.add_parser("false-positives", help="Write false-positive review report.")
    false_report.add_argument("--output", default=str(FALSE_POSITIVE_REPORT))
    false_report.add_argument("--report-path", default=None, help="Report path inside the memory root.")
    false_report.add_argument("--due-only", action="store_true", help="Only include ignored findings whose review-after date is due.")
    false_report.add_argument("--json", action="store_true")
    stale_false_report = review_sub.add_parser("stale-false-positives", help="Write stale false-positive suppression report.")
    stale_false_report.add_argument("--output", default="reports/stale-false-positives.md")
    stale_false_report.add_argument("--report-path", default=None, help="Report path inside the memory root.")
    stale_false_report.add_argument("--json", action="store_true")
    conflict_report = review_sub.add_parser("conflicts", help="Write memory conflict review report.")
    conflict_report.add_argument("--output", default=None)
    conflict_report.add_argument("--report-path", default=None, help="Report path inside the memory root.")
    conflict_report.add_argument("--json", action="store_true")
    modes_cmd = review_sub.add_parser("modes", help="List built-in review modes and the active mode.")
    modes_cmd.add_argument("--json", action="store_true")
    configure_mode = review_sub.add_parser("configure-mode", help="Persist the active review mode.")
    configure_mode.add_argument("--mode", choices=sorted(set(REVIEW_MODES) | set(REVIEW_MODE_ALIASES)), required=True)
    configure_mode.add_argument("--reviewer", default=None)
    plan_cmd = review_sub.add_parser("plan", help="Print the mode-specific review plan.")
    plan_cmd.add_argument("--kind", choices=sorted(REVIEW_PLAN_KINDS), default="inbox")
    plan_cmd.add_argument("--json", action="store_true")
    recommendation_cmd = review_sub.add_parser(
        "recommendation",
        help="Store an advisory LLM/client review recommendation under inbox/review-recommendations/.",
    )
    recommendation_cmd.add_argument("--kind", choices=sorted(REVIEW_PLAN_KINDS), required=True)
    recommendation_cmd.add_argument("--target-id", required=True)
    recommendation_cmd.add_argument("--recommendation", choices=sorted(REVIEW_RECOMMENDATION_ACTIONS), required=True)
    recommendation_cmd.add_argument("--rationale", required=True)
    recommendation_cmd.add_argument("--recommended-by", required=True)
    recommendation_cmd.add_argument("--confidence", type=float, default=None)
    recommendation_cmd.add_argument("--evidence", action="append", default=[])
    recommendation_cmd.add_argument("--json", action="store_true")
    recommendations_cmd = review_sub.add_parser(
        "recommendations",
        help="List advisory review recommendation artifacts without applying outcomes.",
    )
    recommendations_cmd.add_argument("--kind", choices=sorted(REVIEW_PLAN_KINDS), default=None)
    recommendations_cmd.add_argument(
        "--outcome-status",
        choices=["pending", *sorted(REVIEW_RECOMMENDATION_OUTCOMES)],
        default=None,
    )
    recommendations_cmd.add_argument("--policy-violations-only", action="store_true")
    recommendations_cmd.add_argument("--json", action="store_true")
    recommendation_outcome_cmd = review_sub.add_parser(
        "recommendation-outcome",
        help="Record reviewed accepted/rejected status on an advisory recommendation artifact.",
    )
    recommendation_outcome_cmd.add_argument("--id", required=True)
    recommendation_outcome_cmd.add_argument("--status", choices=sorted(REVIEW_RECOMMENDATION_OUTCOMES), required=True)
    recommendation_outcome_cmd.add_argument("--reviewer", required=True)
    recommendation_outcome_cmd.add_argument("--reason", required=True)
    recommendation_outcome_cmd.add_argument("--json", action="store_true")
    recommendation_outcomes_cmd = review_sub.add_parser(
        "recommendation-outcomes",
        help="Write a read-only reviewed recommendation outcome report.",
    )
    recommendation_outcomes_cmd.add_argument("--output", default=str(REVIEW_RECOMMENDATION_OUTCOME_REPORT))
    recommendation_outcomes_cmd.add_argument("--report-path", default=None, help="Report path inside the memory root.")
    recommendation_outcomes_cmd.add_argument("--kind", choices=sorted(REVIEW_PLAN_KINDS), default=None)
    recommendation_outcomes_cmd.add_argument(
        "--outcome-status",
        choices=["reviewed", *sorted(REVIEW_RECOMMENDATION_OUTCOMES)],
        default="reviewed",
    )
    recommendation_outcomes_cmd.add_argument("--limit", type=int, default=50)
    recommendation_outcomes_cmd.add_argument("--offset", type=int, default=0)
    recommendation_outcomes_cmd.add_argument("--invalid-offset", type=int, default=0)
    recommendation_outcomes_cmd.add_argument("--json", action="store_true")
    recommendations_archive_cmd = review_sub.add_parser(
        "recommendations-archive",
        help="Preview or archive accepted/rejected recommendation artifacts.",
    )
    recommendations_archive_cmd.add_argument("--apply", action="store_true")
    recommendations_archive_cmd.add_argument("--archive-root", default=str(REVIEW_RECOMMENDATION_ARCHIVE_DIR))
    recommendations_archive_cmd.add_argument(
        "--outcome-status",
        choices=["reviewed", *sorted(REVIEW_RECOMMENDATION_OUTCOMES)],
        default="reviewed",
    )
    recommendations_archive_cmd.add_argument("--min-outcome-days", type=int, default=0)
    recommendations_archive_cmd.add_argument("--limit", type=int, default=20)
    recommendations_archive_cmd.add_argument("--json", action="store_true")
    recommendations_archive_status_cmd = review_sub.add_parser(
        "recommendations-archive-status",
        help="List archived accepted/rejected recommendation artifacts without moving files.",
    )
    recommendations_archive_status_cmd.add_argument("--archive-root", default=str(REVIEW_RECOMMENDATION_ARCHIVE_DIR))
    recommendations_archive_status_cmd.add_argument("--recursive", action="store_true")
    recommendations_archive_status_cmd.add_argument("--kind", choices=sorted(REVIEW_PLAN_KINDS), default=None)
    recommendations_archive_status_cmd.add_argument(
        "--outcome-status",
        choices=sorted(REVIEW_RECOMMENDATION_OUTCOMES),
        default=None,
    )
    recommendations_archive_status_cmd.add_argument("--limit", type=int, default=50)
    recommendations_archive_status_cmd.add_argument("--offset", type=int, default=0)
    recommendations_archive_status_cmd.add_argument("--invalid-offset", type=int, default=0)
    recommendations_archive_status_cmd.add_argument("--json", action="store_true")
    recommendations_archive_restore_cmd = review_sub.add_parser(
        "recommendations-archive-restore",
        help="Preview or restore one archived recommendation artifact to the active inbox.",
    )
    recommendations_archive_restore_cmd.add_argument("--id", required=True)
    recommendations_archive_restore_cmd.add_argument("--apply", action="store_true")
    recommendations_archive_restore_cmd.add_argument("--archive-root", default=str(REVIEW_RECOMMENDATION_ARCHIVE_DIR))
    recommendations_archive_restore_cmd.add_argument("--recursive", action="store_true")
    recommendations_archive_restore_cmd.add_argument("--json", action="store_true")

    fp = subparsers.add_parser("false-positive", help="Manage false-positive suppressions.")
    fp_sub = fp.add_subparsers(dest="fp_command", required=True)
    fp_ignore = fp_sub.add_parser("ignore")
    fp_ignore.add_argument("--id", required=True)
    fp_ignore.add_argument("--reason", required=True)
    fp_ignore.add_argument("--reviewer", required=True)
    fp_ignore.add_argument("--review-after-days", type=int, default=None)
    fp_ignore.add_argument("--recommendation-id", default=None)
    fp_unignore = fp_sub.add_parser("unignore")
    fp_unignore.add_argument("--id", required=True)
    fp_unignore.add_argument("--reviewer", required=True)
    fp_unignore.add_argument("--recommendation-id", default=None)

    conflict = subparsers.add_parser("conflict", help="Manage memory conflict review state.")
    conflict_sub = conflict.add_subparsers(dest="conflict_command", required=True)
    conflict_dismiss = conflict_sub.add_parser("dismiss")
    conflict_dismiss.add_argument("--id", required=True)
    conflict_dismiss.add_argument("--reason", required=True)
    conflict_dismiss.add_argument("--reviewer", required=True)
    conflict_dismiss.add_argument("--recommendation-id", default=None)
    conflict_resolve = conflict_sub.add_parser("resolve")
    conflict_resolve.add_argument("--id", required=True)
    conflict_resolve.add_argument("--reviewer", required=True)
    conflict_resolve.add_argument("--keep", default=None)
    conflict_resolve.add_argument("--merge-proposal", action="store_true")
    conflict_resolve.add_argument("--recommendation-id", default=None)

    args = parser.parse_args(argv)
    root = repo_root(args.root)

    try:
        if args.command == "review" and args.review_command == "false-positives":
            path, reviews = write_false_positive_report(
                root,
                Path(args.report_path or args.output),
                due_only=bool(args.due_only),
            )
            if args.json:
                metadata = false_positive_review_metadata(root)
                print_json(
                    {
                        "path": display_path(path, root),
                        **metadata,
                        "due_only": bool(args.due_only),
                        "returned_count": len(reviews),
                        "findings": [asdict(item) for item in reviews],
                    }
                )
            else:
                print(f"Wrote {display_path(path, root)} ({len(reviews)} finding(s))")
            return 0
        if args.command == "review" and args.review_command == "stale-false-positives":
            path, items = write_stale_false_positive_report(root, Path(args.report_path or args.output))
            if args.json:
                metadata = false_positive_review_metadata(root)
                print_json(
                    {
                        "path": display_path(path, root),
                        **metadata,
                        "stale_count": len(items),
                        "items": [asdict(item) for item in items],
                    }
                )
            else:
                print(f"Wrote {display_path(path, root)} ({len(items)} stale suppression(s))")
            return 0
        if args.command == "review" and args.review_command == "conflicts":
            output = Path(args.report_path or args.output) if (args.report_path or args.output) else None
            path, conflicts = write_conflict_report(root, output)
            if args.json:
                metadata = conflict_review_metadata(root)
                print_json(
                    {
                        "path": display_path(path, root),
                        **metadata,
                        "conflicts": [asdict(item) for item in conflicts],
                    }
                )
            else:
                print(f"Wrote {display_path(path, root)} ({len(conflicts)} conflict(s))")
            return 0
        if args.command == "review" and args.review_command == "modes":
            modes = review_modes(root)
            if args.json:
                print_json(modes)
            else:
                print(render_review_modes(modes))
            return 0
        if args.command == "review" and args.review_command == "configure-mode":
            path = configure_review_mode(root, args.mode, args.reviewer)
            print(f"Updated {repo_relative_path(path, root)}")
            return 0
        if args.command == "review" and args.review_command == "plan":
            plan = review_plan(root, args.kind)
            if args.json:
                print_json(asdict(plan))
            else:
                print(render_review_plan(plan))
            return 0
        if args.command == "review" and args.review_command == "recommendation":
            result = capture_review_recommendation(
                root,
                kind=args.kind,
                target_id=args.target_id,
                recommendation=args.recommendation,
                rationale=args.rationale,
                recommended_by=args.recommended_by,
                confidence=args.confidence,
                evidence=list(args.evidence or []),
            )
            if args.json:
                print_json(asdict(result))
            else:
                print(
                    "Wrote "
                    f"{result.path} ({result.kind} {result.target_id}: {result.recommendation}; "
                    f"allowed_by_mode={str(result.allowed_by_mode).lower()})"
                )
            return 0
        if args.command == "review" and args.review_command == "recommendations":
            result = review_recommendations(
                root,
                kind=args.kind,
                policy_violations_only=bool(args.policy_violations_only),
                outcome_status=args.outcome_status,
            )
            if args.json:
                print_json(result)
            else:
                print(
                    "Review recommendations: "
                    f"{result['total_count']} pending, "
                    f"{result['policy_violation_count']} policy violation(s), "
                    f"{result['invalid_count']} invalid artifact(s)."
                )
                for action in result["next_actions"]:
                    print(f"- {action}")
                for item in result["recommendations"]:
                    print(
                        f"- {item['path']}: {item.get('kind') or 'unknown'} "
                        f"{item.get('target_id') or 'unknown'} -> {item.get('recommendation') or 'unknown'}"
                    )
            return 0
        if args.command == "review" and args.review_command == "recommendation-outcome":
            result = record_review_recommendation_outcome(
                root,
                recommendation_id=args.id,
                outcome_status=args.status,
                reviewer=args.reviewer,
                reason=args.reason,
            )
            if args.json:
                print_json(result)
            else:
                print(f"Updated {result['path']} ({result['outcome_status']})")
            return 0
        if args.command == "review" and args.review_command == "recommendation-outcomes":
            output = Path(args.report_path or args.output)
            path, payload = write_review_recommendation_outcome_report(
                root,
                output,
                kind=args.kind,
                outcome_status=args.outcome_status,
                limit=args.limit,
                offset=args.offset,
                invalid_offset=args.invalid_offset,
            )
            if args.json:
                print_json(
                    {
                        **payload,
                        "path": display_path(path, root),
                        "report_path": display_path(path, root),
                        "writes_files": True,
                    }
                )
            else:
                print(f"Wrote {display_path(path, root)} ({payload['total_count']} outcome(s))")
            return 0
        if args.command == "review" and args.review_command == "recommendations-archive":
            result = archive_review_recommendations(
                root,
                apply=bool(args.apply),
                archive_root=args.archive_root,
                outcome_status=args.outcome_status,
                min_outcome_days=args.min_outcome_days,
                limit=args.limit,
            )
            if args.json:
                print_json(asdict(result))
            else:
                action = "Archived" if args.apply else "Would archive"
                count = result.archived_count if args.apply else result.eligible_count
                print(f"{action} {count} review recommendation artifact(s).")
                print(f"Archive: {result.archive_root}")
            return 0
        if args.command == "review" and args.review_command == "recommendations-archive-status":
            result = archived_review_recommendations(
                root,
                archive_root=args.archive_root,
                kind=args.kind,
                outcome_status=args.outcome_status,
                limit=args.limit,
                offset=args.offset,
                invalid_offset=args.invalid_offset,
                recursive=bool(args.recursive),
            )
            if args.json:
                print_json(result)
            else:
                print(
                    "Archived review recommendations: "
                    f"{result['total_count']} total, "
                    f"{result['accepted_count']} accepted, "
                    f"{result['rejected_count']} rejected, "
                    f"{result['invalid_count']} invalid."
                )
                for action in result["next_actions"]:
                    print(f"- {action}")
                for item in result["recommendations"]:
                    print(
                        f"- {item['path']}: {item.get('kind') or 'unknown'} "
                        f"{item.get('target_id') or 'unknown'} -> {item.get('recommendation') or 'unknown'} "
                        f"({item.get('outcome_status') or 'unknown'})"
                    )
            return 0
        if args.command == "review" and args.review_command == "recommendations-archive-restore":
            result = restore_archived_review_recommendation(
                root,
                recommendation_id=args.id,
                apply=bool(args.apply),
                archive_root=args.archive_root,
                recursive=bool(args.recursive),
            )
            if args.json:
                print_json(asdict(result))
            else:
                action = "Restored" if args.apply else "Would restore"
                count = result.restored_count if args.apply else len(result.candidates)
                print(f"{action} {count} review recommendation artifact(s).")
                print(f"Archive: {result.archive_root}")
                if result.skipped:
                    for item in result.skipped:
                        print(f"- skipped {item.get('id') or result.requested_id}: {item.get('reason')}")
            return 0
        if args.command == "false-positive" and args.fp_command == "ignore":
            path = ignore_false_positive(
                root,
                args.id,
                args.reason,
                args.reviewer,
                args.review_after_days,
                recommendation_id=args.recommendation_id,
            )
            print(f"Updated {repo_relative_path(path, root)}")
            return 0
        if args.command == "false-positive" and args.fp_command == "unignore":
            path = unignore_false_positive(root, args.id, args.reviewer, recommendation_id=args.recommendation_id)
            print(f"Updated {repo_relative_path(path, root)}")
            return 0
        if args.command == "conflict" and args.conflict_command == "dismiss":
            path = dismiss_conflict(root, args.id, args.reason, args.reviewer, recommendation_id=args.recommendation_id)
            print(f"Updated {repo_relative_path(path, root)}")
            return 0
        if args.command == "conflict" and args.conflict_command == "resolve":
            path = resolve_conflict(
                root,
                args.id,
                args.reviewer,
                args.keep,
                args.merge_proposal,
                recommendation_id=args.recommendation_id,
            )
            print(f"Updated {repo_relative_path(path, root)}")
            return 0
    except ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.error("unhandled command")
    return 2


def render_review_modes(modes: dict[str, Any]) -> str:
    lines = ["# Review Modes", "", f"Active: `{modes['active']}`", ""]
    lines.extend(render_policy_lines(modes["policy"]))
    lines.append("")
    for mode in modes["modes"]:
        marker = " (active)" if mode["active"] else ""
        lines.extend(
            [
                f"## {mode['name']}{marker}",
                "",
                mode["summary"],
                "",
                f"- human durable approval: `{mode['require_human_for_durable']}`",
                f"- LLM false-positive triage: `{mode['allow_llm_false_positive_triage']}`",
                f"- LLM conflict recommendations: `{mode['allow_llm_conflict_recommendations']}`",
                f"- LLM merge proposals: `{mode['allow_llm_merge_proposals']}`",
                f"- autonomous inbox proposals: `{mode['allow_autonomous_inbox_proposals']}`",
                f"- apply reviewed changes: `{mode['allow_apply_reviewed']}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def render_review_plan(plan: ReviewPlan) -> str:
    lines = [
        f"# Review Plan: {plan.kind}",
        "",
        f"- mode: `{plan.mode}`",
        f"- summary: {plan.summary}",
        "",
    ]
    lines.extend(render_policy_lines(plan.policy))
    lines.extend(
        [
            "",
            "## Allowed LLM Actions",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in plan.allowed_llm_actions)
    lines.extend(["", "## Required Human Actions", ""])
    lines.extend(f"- {item}" for item in plan.required_human_actions)
    lines.extend(["", "## Required Checks", ""])
    lines.extend(f"- `{item}`" for item in plan.required_checks)
    lines.extend(["", "## Forbidden Actions", ""])
    lines.extend(f"- {item}" for item in plan.forbidden_actions)
    return "\n".join(lines).rstrip()


def render_policy_lines(policy: dict[str, Any]) -> list[str]:
    false_positives = policy["false_positives"]
    conflicts = policy["conflicts"]
    return [
        "## Configured Review Policy",
        "",
        f"- false positives enabled: `{false_positives['enabled']}`",
        f"- false-positive triage policy: `{false_positives['triage_policy']}`",
        f"- false-positive review state: `{false_positives['ignore_file']}`",
        f"- false-positive review-after days: `{false_positives['review_after_days']}`",
        f"- conflicts enabled: `{conflicts['enabled']}`",
        f"- conflict resolution policy: `{conflicts['resolution_policy']}`",
        f"- conflict scan on validate: `{conflicts['scan_on_validate']}`",
        f"- conflict scan on consolidate: `{conflicts['scan_on_consolidate']}`",
        f"- LLM preselect minimum confidence: `{conflicts['llm_preselect_min_confidence']}`",
        f"- human-required severities: `{', '.join(conflicts['human_required_severities'])}`",
        f"- LLM auto-deny categories: `{', '.join(conflicts['llm_auto_deny_categories'])}`",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
