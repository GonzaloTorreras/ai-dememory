#!/usr/bin/env python3
"""Summarize automated and manual v2 release readiness evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any

from memorylib import repo_relative_path, repo_root
from manual_acceptance import acceptance_plan, acceptance_status
from mcp_inventory import build_inventory, validate_inventory_docs
from maintenance import maintenance_status
from publish_guard import validate_publish_workflow
from recall_fixtures import recall_fixture_review_plan
from release_check import run_release_checks
from secret_scan import scan_text
from setup_plan import setup_health
from vector_gate import evaluate_vector_readiness


DEFAULT_RELEASE_EVIDENCE_REPORT = Path("reports/v2-release-evidence.md")


def markdown_code_span(value: str | None, default: str = "Not provided.") -> str:
    text = value if isinstance(value, str) and value else default
    text = re.sub(r"\s+", " ", text).strip() or default
    max_backtick_run = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    delimiter = "`" * (max_backtick_run + 1)
    if text.startswith("`") or text.endswith("`"):
        text = f" {text} "
    return f"{delimiter}{text}{delimiter}"


@dataclass(frozen=True)
class ReleaseEvidence:
    generated_at: str
    branch: str
    head: str
    clean: bool
    pr_url: str | None
    reviewer: str | None
    automated_checks: list[dict[str, str]]
    automated_summary: dict[str, int]
    release_ready: bool
    release_blockers: list[dict[str, Any]]
    next_actions: list[str]
    handoff_commands: dict[str, Any]
    recall_fixture_freshness: dict[str, Any]
    recall_fixture_review_plan: dict[str, Any]
    vector_readiness: dict[str, Any]
    setup_health_summary: dict[str, Any]
    maintenance_summary: dict[str, Any]
    mcp_tool_count: int
    mcp_prompt_count: int
    mcp_resource_templates: list[str]
    publish_guard_issues: int
    inventory_doc_issues: int
    manual_acceptance_total: int
    manual_acceptance_completed: list[str]
    manual_acceptance_blocked: list[dict[str, Any]]
    manual_acceptance_remaining: list[str]
    manual_acceptance_plan: dict[str, Any]


def git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def blocked_acceptance_items(manual_status: list[Any]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    for item in manual_status:
        if item.completed:
            continue
        records = [record for record in item.records if record.status == "blocked"]
        if not records:
            continue
        blocked.append(
            {
                "id": item.id,
                "description": item.description,
                "records": [
                    {
                        "path": record.path,
                        "reviewed_by": record.reviewed_by,
                        "reviewed_at": record.reviewed_at,
                        "summary": record.summary,
                        "artifacts": record.artifacts,
                    }
                    for record in records
                ],
            }
        )
    return blocked


def recall_review_blocks_release(recall_plan: dict[str, Any], vector_readiness: dict[str, Any]) -> bool:
    recall_freshness = dict(recall_plan.get("freshness") or {})
    if not recall_freshness.get("stale"):
        return False

    pending_count = int(recall_plan.get("pending_count") or 0)
    invalid_count = int(recall_plan.get("invalid_count") or 0)
    if pending_count or invalid_count:
        return True

    recall_eval = dict(vector_readiness.get("recall") or {})
    clean_current_eval = (
        bool(vector_readiness.get("available"))
        and vector_readiness.get("decision") == "not_justified"
        and int(recall_eval.get("failed_cases") or 0) == 0
    )
    return not clean_current_eval


def release_blockers(
    dirty_status: str,
    checks: list[Any],
    manual_remaining: list[str],
    manual_blocked: list[dict[str, Any]],
    recall_plan: dict[str, Any],
    vector_readiness: dict[str, Any],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if dirty_status:
        dirty_paths = [line.strip() for line in dirty_status.splitlines() if line.strip()]
        blockers.append(
            {
                "id": "dirty_worktree",
                "kind": "repository",
                "summary": "Worktree has uncommitted changes.",
                "count": len(dirty_paths),
                "items": dirty_paths,
            }
        )

    failed_checks = [asdict(check) for check in checks if check.status == "fail"]
    if failed_checks:
        blockers.append(
            {
                "id": "automated_failures",
                "kind": "automated",
                "summary": "Automated release checks have failures.",
                "count": len(failed_checks),
                "items": failed_checks,
            }
        )

    warning_checks = [asdict(check) for check in checks if check.status == "warn"]
    if warning_checks:
        blockers.append(
            {
                "id": "automated_warnings",
                "kind": "automated",
                "summary": "Automated release checks have warnings.",
                "count": len(warning_checks),
                "items": warning_checks,
            }
        )

    if recall_review_blocks_release(recall_plan, vector_readiness):
        blockers.append(
            {
                "id": "recall_fixture_review",
                "kind": "quality",
                "summary": "Recall fixtures need review because stale or unresolved recall miss evidence exists.",
                "count": 1,
                "items": [recall_plan],
            }
        )

    if vector_readiness.get("decision") == "eligible_for_vector_experiment":
        failed_case_ids = list(vector_readiness.get("failed_case_ids") or [])
        blockers.append(
            {
                "id": "vector_readiness_review",
                "kind": "quality",
                "summary": "Recall failures make a vector experiment eligible for review.",
                "count": len(failed_case_ids) or 1,
                "items": [vector_readiness],
            }
        )

    if manual_remaining:
        blockers.append(
            {
                "id": "manual_acceptance_remaining",
                "kind": "manual_acceptance",
                "summary": "Manual acceptance items still need reviewed passing evidence.",
                "count": len(manual_remaining),
                "items": manual_remaining,
            }
        )

    if manual_blocked:
        blockers.append(
            {
                "id": "manual_acceptance_blocked",
                "kind": "manual_acceptance",
                "summary": "Manual acceptance items have reviewed blocker evidence but no passing record.",
                "count": len(manual_blocked),
                "items": manual_blocked,
            }
        )
    return blockers


def release_next_actions(
    blockers: list[dict[str, Any]],
    manual_plan: dict[str, Any],
    recall_plan: dict[str, Any],
    vector_readiness: dict[str, Any],
    setup_health_summary: dict[str, Any],
    maintenance_summary: dict[str, Any],
    *,
    limit: int = 20,
) -> list[str]:
    blocker_actions = {
        "dirty_worktree": "Commit or discard local changes before release sign-off.",
        "automated_failures": "Fix failing automated release checks.",
        "automated_warnings": "Review automated release warnings before release sign-off.",
        "recall_fixture_review": "Promote or reject reviewed recall misses before release sign-off.",
        "vector_readiness_review": "Review vector readiness evidence before approving any vector experiment.",
        "manual_acceptance_remaining": "Record reviewed passing manual acceptance evidence for remaining items.",
        "manual_acceptance_blocked": "Resolve blocked manual acceptance items or record passing evidence.",
    }
    actions: list[str] = []

    def add(action: Any) -> None:
        if not isinstance(action, str):
            return
        normalized = action.strip()
        if normalized and normalized not in actions:
            actions.append(normalized)

    for blocker in blockers:
        add(blocker_actions.get(str(blocker.get("id"))))
    for action in manual_plan.get("next_actions", []):
        add(action)
    blocker_ids = {str(blocker.get("id")) for blocker in blockers}
    if "recall_fixture_review" in blocker_ids:
        for action in recall_plan.get("next_actions", []):
            add(action)
    for action in vector_readiness.get("next_actions", []):
        add(action)
    for action in setup_health_summary.get("next_actions", []):
        add(action)

    generated_packet_archives = dict(maintenance_summary.get("generated_packet_archives") or {})
    if int(generated_packet_archives.get("prunable_count", 0)) > 0:
        add("Review generated packet archive retention previews before cleanup.")
    artifact_freshness = dict(maintenance_summary.get("artifact_freshness") or {})
    if bool(artifact_freshness.get("needs_maintenance", False)):
        add("Review artifact freshness and approve any maintenance refresh before running it.")
    review_recommendations = dict(maintenance_summary.get("review_recommendations") or {})
    if int(review_recommendations.get("pending_count", 0)) > 0:
        add("Review pending advisory recommendations before release handoff.")

    return actions[:limit]


def release_handoff_commands(pr_url: str | None = None, reviewer: str | None = None) -> dict[str, Any]:
    pr_value = pr_url or "<pr-url>"
    reviewer_value = reviewer or "<reviewer>"
    commands = {
        "release_evidence_report": [
            "ai-dememory",
            "release-evidence",
            "--write-report",
            "--report-path",
            DEFAULT_RELEASE_EVIDENCE_REPORT.as_posix(),
            "--pr-url",
            pr_value,
            "--reviewer",
            reviewer_value,
        ],
        "strict_release_evidence": [
            "ai-dememory",
            "release-evidence",
            "--strict",
            "--pr-url",
            pr_value,
            "--reviewer",
            reviewer_value,
        ],
        "acceptance_plan": [
            "ai-dememory",
            "acceptance",
            "plan",
            "--reviewer",
            reviewer_value,
            "--pr-url",
            pr_value,
            "--json",
        ],
        "acceptance_template": [
            "ai-dememory",
            "acceptance",
            "template",
            "--item",
            "<item-id>",
            "--reviewer",
            reviewer_value,
            "--pr-url",
            pr_value,
            "--json",
        ],
        "acceptance_packet": [
            "ai-dememory",
            "acceptance",
            "packet",
            "--write-report",
            "--reviewer",
            reviewer_value,
            "--pr-url",
            pr_value,
        ],
        "acceptance_verify": ["ai-dememory", "acceptance", "verify"],
        "recall_review_packet": [
            "ai-dememory",
            "recall-fixtures",
            "packet",
            "--write-report",
            "--reviewer",
            reviewer_value,
            "--pr-url",
            pr_value,
        ],
        "recall_review_status": [
            "ai-dememory",
            "recall-fixtures",
            "status",
            "--strict",
            "--max-age-days",
            "14",
        ],
        "publish_plan_testpypi": [
            "ai-dememory",
            "publish-plan",
            "--repository",
            "testpypi",
            "--pr-url",
            pr_value,
        ],
        "publish_plan_pypi": [
            "ai-dememory",
            "publish-plan",
            "--repository",
            "pypi",
            "--pr-url",
            pr_value,
        ],
        "publish_guard": ["ai-dememory", "publish-guard"],
    }
    command_side_effects = {
        name: {
            "runs_commands": name in {"publish_plan_testpypi", "publish_plan_pypi"},
            "records_evidence": False,
            "writes_files": name in {"release_evidence_report", "acceptance_packet", "recall_review_packet"},
            "publishes_package": False,
            "mutates_system": False,
        }
        for name in commands
    }
    return {
        "payload_mutates_system": False,
        "payload_runs_commands": False,
        "payload_records_evidence": False,
        "payload_writes_files": False,
        "commands_mutate_system": any(effect["mutates_system"] for effect in command_side_effects.values()),
        "commands_run_commands": any(effect["runs_commands"] for effect in command_side_effects.values()),
        "commands_record_evidence": any(effect["records_evidence"] for effect in command_side_effects.values()),
        "commands_write_files": any(effect["writes_files"] for effect in command_side_effects.values()),
        "commands_publish_package": any(effect["publishes_package"] for effect in command_side_effects.values()),
        "command_side_effects": command_side_effects,
        "commands": commands,
        "next_step": "Run these commands only as review or preflight aids; they do not replace human acceptance records.",
    }


def release_vector_readiness(root: Path) -> dict[str, Any]:
    try:
        result = asdict(evaluate_vector_readiness(root))
    except FileNotFoundError as exc:
        fixtures_path = root / "quality" / "recall-fixtures.json"
        if fixtures_path.exists():
            rationale = "The generated memory index is required before evaluating vector readiness."
            next_action = "Run `ai-dememory index` before evaluating vector readiness."
        else:
            rationale = "Recall fixtures are required before evaluating vector readiness."
            next_action = "Add `quality/recall-fixtures.json` before evaluating vector readiness."
        return {
            "available": False,
            "decision": "unavailable",
            "rationale": rationale,
            "recall": {},
            "failed_case_ids": [],
            "errors": [str(exc)],
            "next_actions": [next_action],
            "mutates_system": False,
            "runs_commands": False,
            "writes_files": False,
            "creates_embeddings": False,
        }
    except ValueError as exc:
        return {
            "available": False,
            "decision": "unavailable",
            "rationale": "Recall fixtures could not be evaluated for vector readiness.",
            "recall": {},
            "failed_case_ids": [],
            "errors": [str(exc)],
            "next_actions": ["Fix recall fixtures before evaluating vector readiness."],
            "mutates_system": False,
            "runs_commands": False,
            "writes_files": False,
            "creates_embeddings": False,
        }
    result["available"] = True
    result["errors"] = []
    result["next_actions"] = []
    if result.get("decision") == "eligible_for_vector_experiment":
        result["next_actions"].append("Review vector readiness evidence before approving any vector-search experiment.")
    result["mutates_system"] = False
    result["runs_commands"] = False
    result["writes_files"] = False
    result["creates_embeddings"] = False
    return result


def release_setup_health_summary(root: Path) -> dict[str, Any]:
    health = setup_health(root)
    recall_review = dict(health.get("recall_review") or {})
    vector_readiness = dict(health.get("vector_readiness") or {})
    schedule_environment = dict(health.get("schedule_environment") or {})
    schedule_status = dict(health.get("schedule_status") or {})
    manual_acceptance = dict(health.get("manual_acceptance") or {})
    context_config = dict(health.get("context_config") or {})
    validation_status = dict(health.get("validation_status") or {})
    hook_status = dict(health.get("hook_status") or {})
    hook_captures = dict(hook_status.get("captures") or {})
    provider_readiness = dict(health.get("provider_readiness") or {})
    generated_packet_archives = dict(health.get("generated_packet_archives") or {})
    generated_packet_archive_summary = dict(generated_packet_archives.get("summary") or {})
    artifact_freshness = dict(health.get("artifact_freshness") or {})
    review_due = dict(health.get("review_due") or {})
    conflict_review = dict(health.get("conflict_review") or {})
    return {
        "ready": bool(health.get("ready", False)),
        "platform": health.get("platform"),
        "mode": health.get("mode"),
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "validation_ok": bool(validation_status.get("ok", False)),
        "context_valid": bool(context_config.get("valid", True)),
        "schedule_ready": bool(schedule_environment.get("ready", False)),
        "schedule_valid": bool(schedule_status.get("valid", True)),
        "manual_acceptance": {
            "complete": bool(manual_acceptance.get("complete", False)),
            "completed_count": int(manual_acceptance.get("completed_count", 0)),
            "blocked_count": int(manual_acceptance.get("blocked_count", 0)),
            "remaining_count": int(manual_acceptance.get("remaining_count", 0)),
            "records_evidence": False,
        },
        "recall_review": {
            "available": bool(recall_review.get("available", False)),
            "status": recall_review.get("status"),
            "pending_count": int(recall_review.get("pending_count", 0)),
            "invalid_count": int(recall_review.get("invalid_count", 0)),
            "resolved_count": int(recall_review.get("resolved_count", 0)),
        },
        "vector_readiness": {
            "available": bool(vector_readiness.get("available", False)),
            "decision": vector_readiness.get("decision"),
            "creates_embeddings": False,
        },
        "hook_captures": {
            "review_due_count": int(hook_captures.get("review_due_count", 0)),
            "reads_raw_payloads": False,
        },
        "provider_readiness": {
            "configured_count": int(provider_readiness.get("configured_count", 0)),
            "enabled_count": int(provider_readiness.get("enabled_count", 0)),
            "import_ready_count": int(provider_readiness.get("import_ready_count", 0)),
        },
        "generated_packet_archives": {
            "available": bool(generated_packet_archives.get("available", False)),
            "total_count": int(generated_packet_archive_summary.get("total_count", 0)),
            "prunable_count": int(generated_packet_archive_summary.get("prunable_count", 0)),
            "has_prunable": bool(generated_packet_archive_summary.get("has_prunable", False)),
            "writes_files": False,
            "deletes_files": False,
        },
        "artifact_freshness": {
            "missing_count": int(artifact_freshness.get("missing_count", 0)),
            "stale_count": int(artifact_freshness.get("stale_count", 0)),
            "needs_maintenance": bool(artifact_freshness.get("needs_maintenance", False)),
            "writes_files": False,
        },
        "review_due": {
            "due_findings": int(review_due.get("due_findings", 0)),
            "stale_suppressions": int(review_due.get("stale_suppressions", 0)),
        },
        "conflict_review": {
            "active_conflicts": int(conflict_review.get("active_conflicts", 0)),
        },
        "next_actions": list(health.get("next_actions") or []),
    }


def release_maintenance_summary(root: Path) -> dict[str, Any]:
    status = maintenance_status(root)
    provider_readiness = dict(status.get("provider_readiness") or {})
    review_due = dict(status.get("review_due") or {})
    conflict_review = dict(status.get("conflict_review") or {})
    review_recommendations = dict(status.get("review_recommendations") or {})
    packet_archives = dict(status.get("generated_packet_archives") or {})
    packet_archive_summary = dict(packet_archives.get("summary") or {})
    artifact_freshness = dict(status.get("artifact_freshness") or {})
    artifacts = status.get("artifacts") if isinstance(status.get("artifacts"), dict) else {}
    artifact_values = [item for item in artifacts.values() if isinstance(item, dict)]
    recent_reports = status.get("recent_reports") if isinstance(status.get("recent_reports"), list) else []
    return {
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "deletes_files": False,
        "lock_exists": bool(status.get("lock_exists", False)),
        "recent_report_count": len(recent_reports),
        "latest_report": recent_reports[0] if recent_reports else None,
        "artifact_present_count": sum(1 for item in artifact_values if bool(item.get("exists", False))),
        "artifact_missing_count": sum(1 for item in artifact_values if not bool(item.get("exists", False))),
        "artifact_freshness": {
            "missing_count": int(artifact_freshness.get("missing_count", 0)),
            "stale_count": int(artifact_freshness.get("stale_count", 0)),
            "fresh_count": int(artifact_freshness.get("fresh_count", 0)),
            "needs_maintenance": bool(artifact_freshness.get("needs_maintenance", False)),
            "writes_files": False,
        },
        "provider_readiness": {
            "configured_count": int(provider_readiness.get("configured_count", 0)),
            "enabled_count": int(provider_readiness.get("enabled_count", 0)),
            "import_ready_count": int(provider_readiness.get("import_ready_count", 0)),
            "reads_provider_files": False,
            "writes_import_candidates": False,
        },
        "review_due": {
            "due_findings": int(review_due.get("due_findings", 0)),
            "stale_suppressions": int(review_due.get("stale_suppressions", 0)),
            "canonical_memory_updated": False,
        },
        "conflict_review": {
            "active_conflicts": int(conflict_review.get("active_conflicts", 0)),
            "canonical_memory_updated": False,
        },
        "review_recommendations": {
            "pending_count": int(review_recommendations.get("pending_count", 0)),
            "invalid_count": int(review_recommendations.get("invalid_count", 0)),
            "applies_review_decisions": False,
            "canonical_memory_updated": False,
        },
        "generated_packet_archives": {
            "available": bool(packet_archives.get("available", False)),
            "total_count": int(packet_archive_summary.get("total_count", 0)),
            "prunable_count": int(packet_archive_summary.get("prunable_count", 0)),
            "has_prunable": bool(packet_archive_summary.get("has_prunable", False)),
            "writes_files": False,
            "deletes_files": False,
        },
    }


def build_release_evidence(root: Path, pr_url: str | None = None, reviewer: str | None = None) -> ReleaseEvidence:
    status = git_output(root, "status", "--short")
    inventory = build_inventory(root)
    manual_status = acceptance_status(root)
    clean_reviewer = reviewer.strip() if isinstance(reviewer, str) and reviewer.strip() else None
    clean_pr_url = pr_url.strip() if isinstance(pr_url, str) and pr_url.strip() else None
    checks = run_release_checks(root, pr_url=clean_pr_url)
    manual_plan = acceptance_plan(root, reviewer=clean_reviewer, pr_url=clean_pr_url)
    recall_plan = asdict(recall_fixture_review_plan(root))
    vector_readiness = release_vector_readiness(root)
    setup_health_summary = release_setup_health_summary(root)
    maintenance_summary = release_maintenance_summary(root)
    freshness = dict(recall_plan["freshness"])
    automated_summary = {
        "ok": sum(1 for check in checks if check.status == "ok"),
        "warn": sum(1 for check in checks if check.status == "warn"),
        "fail": sum(1 for check in checks if check.status == "fail"),
        "total": len(checks),
    }
    manual_remaining = [item.description for item in manual_status if not item.completed]
    manual_blocked = blocked_acceptance_items(manual_status)
    blockers = release_blockers(status, checks, manual_remaining, manual_blocked, recall_plan, vector_readiness)
    next_actions = release_next_actions(
        blockers,
        asdict(manual_plan),
        recall_plan,
        vector_readiness,
        setup_health_summary,
        maintenance_summary,
    )
    return ReleaseEvidence(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        branch=git_output(root, "branch", "--show-current"),
        head=git_output(root, "rev-parse", "--short", "HEAD"),
        clean=not bool(status),
        pr_url=clean_pr_url,
        reviewer=clean_reviewer,
        automated_checks=[asdict(check) for check in checks],
        automated_summary=automated_summary,
        release_ready=not blockers,
        release_blockers=blockers,
        next_actions=next_actions,
        handoff_commands=release_handoff_commands(clean_pr_url, clean_reviewer),
        recall_fixture_freshness=freshness,
        recall_fixture_review_plan=recall_plan,
        vector_readiness=vector_readiness,
        setup_health_summary=setup_health_summary,
        maintenance_summary=maintenance_summary,
        mcp_tool_count=int(inventory["tool_count"]),
        mcp_prompt_count=int(inventory["prompt_count"]),
        mcp_resource_templates=list(inventory["resource_templates"]),
        publish_guard_issues=len(validate_publish_workflow(root)),
        inventory_doc_issues=len(validate_inventory_docs(root)),
        manual_acceptance_total=len(manual_status),
        manual_acceptance_completed=[item.description for item in manual_status if item.completed],
        manual_acceptance_blocked=manual_blocked,
        manual_acceptance_remaining=manual_remaining,
        manual_acceptance_plan=asdict(manual_plan),
    )


def render_markdown(evidence: ReleaseEvidence) -> str:
    checks = "\n".join(
        f"- {item['status'].upper()} `{item['name']}`: {markdown_code_span(item['detail'])}"
        for item in evidence.automated_checks
    )
    completed = "\n".join(f"- [x] {item}" for item in evidence.manual_acceptance_completed)
    if not completed:
        completed = "_No manual acceptance evidence recorded._"
    blocked_lines: list[str] = []
    for item in evidence.manual_acceptance_blocked:
        blocked_lines.append(f"- [!] {item['id']}: {item['description']}")
        for record in item["records"]:
            blocked_lines.append(
                f"  - {record['reviewed_at']} by {record['reviewed_by']}: "
                f"{record['summary']} (`{record['path']}`)"
            )
    blocked = "\n".join(blocked_lines)
    if not blocked:
        blocked = "_No blocked manual acceptance evidence recorded._"
    manual = "\n".join(f"- [ ] {item}" for item in evidence.manual_acceptance_remaining)
    if not manual:
        manual = "_All manual acceptance items have reviewed evidence._"
    plan_lines: list[str] = []
    for item in evidence.manual_acceptance_plan.get("items", []):
        if item.get("completed"):
            continue
        plan_lines.append(f"- `{item['id']}` ({item['status']}): {item['next_action']}")
        suggested = item.get("suggested_artifacts") or []
        if suggested:
            plan_lines.append("  - suggested artifacts:")
            for artifact in suggested:
                plan_lines.append(f"    - {artifact}")
        if item.get("pass_command"):
            plan_lines.append(f"  - pass: {markdown_code_span(item['pass_command'])}")
        if item.get("blocked_command"):
            plan_lines.append(f"  - block: {markdown_code_span(item['blocked_command'])}")
    for action in evidence.manual_acceptance_plan.get("next_actions", []):
        plan_lines.append(f"- {action}")
    plan = "\n".join(plan_lines)
    if not plan:
        plan = "_No manual acceptance actions remain._"
    pr_line = markdown_code_span(evidence.pr_url)
    reviewer_line = markdown_code_span(evidence.reviewer)
    blocker_lines = [
        f"- `{item['id']}` ({item['kind']}): {item['summary']} Count: `{item['count']}`"
        for item in evidence.release_blockers
    ]
    blockers = "\n".join(blocker_lines) if blocker_lines else "_No release blockers._"
    next_actions = "\n".join(f"- {action}" for action in evidence.next_actions)
    if not next_actions:
        next_actions = "_No next actions._"
    handoff_command_lines: list[str] = []
    handoff_commands = evidence.handoff_commands.get("commands", {})
    if isinstance(handoff_commands, dict):
        for name, command in handoff_commands.items():
            if isinstance(command, list) and all(isinstance(part, str) for part in command):
                handoff_command_lines.append(f"- {name}: {markdown_code_span(shlex.join(command))}")
    if isinstance(evidence.handoff_commands.get("next_step"), str):
        handoff_command_lines.append(f"- note: {evidence.handoff_commands['next_step']}")
    handoff = "\n".join(handoff_command_lines) if handoff_command_lines else "_No handoff commands._"
    recall = evidence.recall_fixture_freshness
    recall_plan_lines = [
        f"- status: `{evidence.recall_fixture_review_plan['status']}`",
        f"- pending misses: `{evidence.recall_fixture_review_plan['pending_count']}`",
        f"- invalid miss files: `{evidence.recall_fixture_review_plan['invalid_count']}`",
        f"- resolved misses: `{evidence.recall_fixture_review_plan.get('resolved_count', 0)}`",
    ]
    candidate_command = evidence.recall_fixture_review_plan.get("candidate_check_command") or []
    if candidate_command:
        recall_plan_lines.append(f"- candidate check: `{' '.join(candidate_command)}`")
    for action in evidence.recall_fixture_review_plan.get("next_actions", []):
        recall_plan_lines.append(f"- {action}")
    for miss in evidence.recall_fixture_review_plan.get("pending_misses", []):
        recall_plan_lines.append(
            f"- pending `{miss['path']}`: {miss.get('query') or 'no query'}"
        )
    for miss in evidence.recall_fixture_review_plan.get("invalid_misses", []):
        recall_plan_lines.append(f"- invalid `{miss['path']}`: {miss['error']}")
    for miss in evidence.recall_fixture_review_plan.get("recent_resolved_misses", []):
        recall_plan_lines.append(
            f"- resolved `{miss['path']}` ({miss['status']}): {miss.get('query') or 'no query'}"
        )
    recall_plan = "\n".join(recall_plan_lines)
    vector = evidence.vector_readiness
    vector_lines = [
        f"- decision: `{vector.get('decision', 'unknown')}`",
        f"- available: `{str(bool(vector.get('available', False))).lower()}`",
        f"- creates embeddings: `{str(bool(vector.get('creates_embeddings', False))).lower()}`",
    ]
    if vector.get("recall"):
        recall_summary = vector["recall"]
        vector_lines.append(
            "- recall: "
            f"`{recall_summary.get('recall')}` "
            f"({recall_summary.get('passed_cases')}/{recall_summary.get('total_cases')} cases passed)"
        )
    failed_case_ids = vector.get("failed_case_ids") or []
    if failed_case_ids:
        vector_lines.append(f"- failed cases: `{', '.join(str(item) for item in failed_case_ids)}`")
    if vector.get("rationale"):
        vector_lines.append(f"- rationale: {vector['rationale']}")
    for action in vector.get("next_actions", []):
        vector_lines.append(f"- next action: {action}")
    for error in vector.get("errors", []):
        vector_lines.append(f"- error: {error}")
    vector_readiness = "\n".join(vector_lines)
    setup = evidence.setup_health_summary
    setup_lines = [
        f"- ready: `{str(bool(setup.get('ready', False))).lower()}`",
        f"- platform: `{setup.get('platform')}`",
        f"- mode: `{setup.get('mode')}`",
        f"- validation ok: `{str(bool(setup.get('validation_ok', False))).lower()}`",
        f"- context valid: `{str(bool(setup.get('context_valid', True))).lower()}`",
        f"- scheduler ready: `{str(bool(setup.get('schedule_ready', False))).lower()}`",
        f"- scheduler config valid: `{str(bool(setup.get('schedule_valid', True))).lower()}`",
        f"- manual acceptance remaining: `{setup.get('manual_acceptance', {}).get('remaining_count', 0)}`",
        f"- recall review: `{setup.get('recall_review', {}).get('status')}`",
        f"- vector readiness: `{setup.get('vector_readiness', {}).get('decision')}`",
        f"- hook captures due: `{setup.get('hook_captures', {}).get('review_due_count', 0)}`",
        f"- provider import ready: `{setup.get('provider_readiness', {}).get('import_ready_count', 0)}`",
        f"- artifact freshness stale: `{setup.get('artifact_freshness', {}).get('stale_count', 0)}`",
        f"- generated packet archive prunable: `{setup.get('generated_packet_archives', {}).get('prunable_count', 0)}`",
    ]
    for action in setup.get("next_actions", []):
        setup_lines.append(f"- next action: {action}")
    setup_health_summary = "\n".join(setup_lines)
    maintenance = evidence.maintenance_summary
    maintenance_lines = [
        f"- recent reports: `{maintenance.get('recent_report_count', 0)}`",
        f"- latest report: `{maintenance.get('latest_report') or 'none'}`",
        f"- lock exists: `{str(bool(maintenance.get('lock_exists', False))).lower()}`",
        f"- artifacts present: `{maintenance.get('artifact_present_count', 0)}`",
        f"- artifacts missing: `{maintenance.get('artifact_missing_count', 0)}`",
        f"- artifact freshness stale: `{maintenance.get('artifact_freshness', {}).get('stale_count', 0)}`",
        f"- artifact freshness needs maintenance: `{str(bool(maintenance.get('artifact_freshness', {}).get('needs_maintenance', False))).lower()}`",
        f"- provider import ready: `{maintenance.get('provider_readiness', {}).get('import_ready_count', 0)}`",
        f"- false-positive review due: `{maintenance.get('review_due', {}).get('due_findings', 0)}`",
        f"- stale suppressions: `{maintenance.get('review_due', {}).get('stale_suppressions', 0)}`",
        f"- active conflicts: `{maintenance.get('conflict_review', {}).get('active_conflicts', 0)}`",
        f"- pending review recommendations: `{maintenance.get('review_recommendations', {}).get('pending_count', 0)}`",
        f"- generated packet archive prunable: `{maintenance.get('generated_packet_archives', {}).get('prunable_count', 0)}`",
        f"- deletes archives: `{str(bool(maintenance.get('generated_packet_archives', {}).get('deletes_files', False))).lower()}`",
    ]
    maintenance_summary = "\n".join(maintenance_lines)
    return f"""# v2 Release Evidence

Generated: `{evidence.generated_at}`

Branch: `{evidence.branch}`

HEAD: `{evidence.head}`

Clean worktree: `{str(evidence.clean).lower()}`

PR URL: {pr_line}

Reviewer: {reviewer_line}

Release ready: `{str(evidence.release_ready).lower()}`

## Release Blockers

{blockers}

## Next Actions

{next_actions}

## Handoff Commands

{handoff}

## Recall Fixture Freshness

- status: `{recall['status']}`
- stale: `{str(recall['stale']).lower()}`
- reviewed promotions: `{recall['reviewed_promotions']}`
- seed fixtures: `{recall['seed_fixtures']}`
- latest reviewed: `{recall['latest_reviewed_at'] or 'none'}`
- next action: {recall['next_action']}

## Recall Review Plan

{recall_plan}

## Vector Readiness

{vector_readiness}

## Setup Health Summary

{setup_health_summary}

## Maintenance Summary

{maintenance_summary}

## Automated Evidence

- ok: `{evidence.automated_summary['ok']}`
- warn: `{evidence.automated_summary['warn']}`
- fail: `{evidence.automated_summary['fail']}`
- total: `{evidence.automated_summary['total']}`

{checks}

## MCP Inventory

- tools: `{evidence.mcp_tool_count}`
- prompts: `{evidence.mcp_prompt_count}`
- resource templates: `{", ".join(evidence.mcp_resource_templates)}`
- inventory doc issues: `{evidence.inventory_doc_issues}`

## Publish Workflow

- publish guard issues: `{evidence.publish_guard_issues}`

## Manual Acceptance Completed

- completed: `{len(evidence.manual_acceptance_completed)}/{evidence.manual_acceptance_total}`

{completed}

## Manual Acceptance Blocked

{blocked}

## Manual Acceptance Remaining

{manual}

## Manual Acceptance Plan

{plan}
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
    evidence: ReleaseEvidence,
    report_path: str | Path = DEFAULT_RELEASE_EVIDENCE_REPORT,
) -> Path:
    target = resolve_report_path(root, report_path)
    text = render_markdown(evidence)
    if scan_text(text, "<release-evidence-report>"):
        raise ValueError("release evidence report rejected by secret scan")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def evidence_to_dict(evidence: ReleaseEvidence) -> dict[str, Any]:
    return asdict(evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--pr-url", default=None, help="PR URL to include in the evidence report. Defaults to AI_DEMEMORY_PR_URL.")
    parser.add_argument("--reviewer", default=None, help="Reviewer name to include in acceptance handoff commands.")
    parser.add_argument("--write-report", action="store_true", help="Write reports/v2-release-evidence.md.")
    parser.add_argument("--report-path", default=str(DEFAULT_RELEASE_EVIDENCE_REPORT), help="Report path inside the memory root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero unless release_ready is true.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        evidence = build_release_evidence(
            root,
            pr_url=args.pr_url or os.environ.get("AI_DEMEMORY_PR_URL") or None,
            reviewer=args.reviewer or os.environ.get("AI_DEMEMORY_REVIEWER") or None,
        )
    except subprocess.CalledProcessError as exc:
        print(f"git command failed: {exc}", file=sys.stderr)
        return 1

    try:
        report_path = write_report(root, evidence, args.report_path) if args.write_report else None
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    output = evidence_to_dict(evidence)
    if report_path:
        output["report_path"] = repo_relative_path(report_path, root)

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(render_markdown(evidence))
        if report_path:
            print(f"Wrote {repo_relative_path(report_path, root)}")
    return 0 if not args.strict or evidence.release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
