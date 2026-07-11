#!/usr/bin/env python3
"""Run opt-in ai-dememory maintenance profiles."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from typing import Iterator

from config_file import load_config
from consolidate_memory import write_report as write_consolidation_report
from eval_recall import DEFAULT_FIXTURES, evaluate, summary
from graph_memory import build_graph
from hook_event import hook_capture_files, hook_capture_summary, write_hook_capture_report
from index_memory import default_db_path, rebuild_index
from lifecycle import lifecycle_scores, write_lifecycle_report, write_lifecycle_scores
from manual_acceptance import acceptance_packet_archive_retention_plan, acceptance_packet_archive_status
from memorylib import discover_memory_files, load_memories, recency_score, repo_relative_path, repo_root
from provider_import import import_chats, provider_config, providers_status
from recall_fixtures import recall_review_packet_archive_retention_plan, recall_review_packet_archive_status
from review_memory import (
    ReviewError,
    conflict_reviews,
    false_positive_reviews,
    review_recommendations,
    stale_false_positive_suppressions,
)
from secret_scan import scan_paths, scan_text
from sleep_consolidation import DEFAULT_REPORT as DEFAULT_SLEEP_REPORT
from sleep_consolidation import write_sleep_report


DEFAULT_MAINTENANCE_REPORT_DIR = Path("reports/maintenance")

GENERATED_ARTIFACTS: dict[str, Path] = {
    "index": Path("indexes/memory.sqlite"),
    "graph": Path("indexes/memory-graph.json"),
    "weights": Path("indexes/memory-weights.json"),
    "lifecycle_scores": Path("indexes/memory-lifecycle.json"),
    "lifecycle_report": Path("reports/lifecycle.md"),
    "hook_capture_report": Path("reports/hook-captures.md"),
    "sleep_plan_report": DEFAULT_SLEEP_REPORT,
}

WEEKLY_GENERATED_ARTIFACTS = {"hook_capture_report", "sleep_plan_report"}


@dataclass(frozen=True)
class MaintenanceResult:
    profile: str
    started_at: str
    finished_at: str
    report: str
    imports: list[dict[str, object]]
    index_count: int
    graph_nodes: int
    graph_edges: int
    weights: str
    lifecycle_scores: str
    lifecycle_report: str
    lifecycle_count: int
    recall: dict[str, object] | None
    hook_capture_report: str | None
    hook_captures: dict[str, object] | None
    sleep_plan_report: str | None
    review_due: dict[str, object]
    conflict_review: dict[str, object]
    review_recommendations: dict[str, object]
    artifact_freshness: dict[str, object]
    generated_packet_archives: dict[str, object]
    cleanup_removed: int


def maintenance_artifact_targets(
    root: Path,
    profile: str,
    report_dir: Path = DEFAULT_MAINTENANCE_REPORT_DIR,
) -> list[str]:
    targets = [
        repo_relative_path(root / "indexes" / "memory.sqlite", root),
        repo_relative_path(root / "indexes" / "memory-graph.json", root),
        repo_relative_path(root / "indexes" / "memory-weights.json", root),
        repo_relative_path(root / "indexes" / "memory-lifecycle.json", root),
        repo_relative_path(root / "reports" / "lifecycle.md", root),
        repo_relative_path(resolve_report_dir(root, report_dir), root),
    ]
    if profile == "weekly":
        targets.append("reports/consolidation-dry-run.md")
        targets.append("reports/hook-captures.md")
        targets.append(repo_relative_path(root / DEFAULT_SLEEP_REPORT, root))
    return targets


@contextmanager
def maintenance_lock(root: Path) -> Iterator[None]:
    lock_path = root / "indexes" / ".maintenance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = lock_path.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError(f"maintenance already running: {repo_relative_path(lock_path, root)}") from exc
    try:
        fd.write(datetime.now(timezone.utc).isoformat())
        fd.close()
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def enabled_providers(root: Path) -> list[str]:
    return [
        name
        for name, values in provider_config(root).items()
        if bool(values.get("enabled", False))
    ]


def run_maintenance(
    root: Path,
    profile: str,
    report_dir: Path = DEFAULT_MAINTENANCE_REPORT_DIR,
) -> MaintenanceResult:
    if profile not in {"daily", "weekly"}:
        raise ValueError("profile must be daily or weekly")
    target_report_dir = resolve_report_dir(root, report_dir)

    with maintenance_lock(root):
        started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        imports: list[dict[str, object]] = []
        for provider in enabled_providers(root):
            try:
                imports.append(import_chats(root, provider))
            except Exception as exc:
                imports.append({"provider": provider, "error": str(exc)})

        findings = scan_paths(root)
        if findings:
            formatted = "\n".join(
                f"{finding.path}:{finding.line}: {finding.kind}: {finding.redacted_line}"
                for finding in findings[:20]
            )
            raise RuntimeError(f"secret scan failed before maintenance:\n{formatted}")

        _, index_count = rebuild_index(root)
        graph = build_graph(root)
        graph_path = root / "indexes" / "memory-graph.json"
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        weights_path = write_weights(root)
        lifecycle_scores_path, lifecycle_rows = write_lifecycle_scores(root)
        lifecycle_report_path, _ = write_lifecycle_report(root)
        review_due = review_due_summary(root)
        conflict_review = conflict_review_summary(root)
        recommendation_summary = review_recommendation_summary(root)
        packet_archive_summary = generated_packet_archive_summary(root)

        recall_summary: dict[str, object] | None = None
        hook_capture_report_path: Path | None = None
        hook_captures: dict[str, object] | None = None
        sleep_plan_report_path: Path | None = None
        cleanup_removed = 0
        if profile == "weekly":
            write_consolidation_report(root, Path("reports/consolidation-dry-run.md"))
            sleep_plan_report_path, _ = write_sleep_report(root, DEFAULT_SLEEP_REPORT)
            fixtures = root / DEFAULT_FIXTURES
            if fixtures.exists():
                recall_results = evaluate(root, fixtures)
                recall_summary = summary(recall_results)
            hook_capture_report_path, hook_captures = write_hook_capture_report(root)
            cleanup_removed = cleanup_reports(root)

        artifact_freshness = generated_artifact_freshness(root, profile=profile)
        finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        report_path = write_maintenance_report(
            root,
            profile,
            started_at,
            finished_at,
            imports,
            index_count,
            graph,
            weights_path,
            lifecycle_scores_path,
            lifecycle_report_path,
            len(lifecycle_rows),
            recall_summary,
            repo_relative_path(hook_capture_report_path, root) if hook_capture_report_path else None,
            hook_captures,
            repo_relative_path(sleep_plan_report_path, root) if sleep_plan_report_path else None,
            review_due,
            conflict_review,
            recommendation_summary,
            artifact_freshness,
            packet_archive_summary,
            cleanup_removed,
            target_report_dir,
        )
        return MaintenanceResult(
            profile=profile,
            started_at=started_at,
            finished_at=finished_at,
            report=repo_relative_path(report_path, root),
            imports=imports,
            index_count=index_count,
            graph_nodes=len(graph["nodes"]),
            graph_edges=len(graph["edges"]),
            weights=repo_relative_path(weights_path, root),
            lifecycle_scores=repo_relative_path(lifecycle_scores_path, root),
            lifecycle_report=repo_relative_path(lifecycle_report_path, root),
            lifecycle_count=len(lifecycle_rows),
            recall=recall_summary,
            hook_capture_report=repo_relative_path(hook_capture_report_path, root) if hook_capture_report_path else None,
            hook_captures=hook_captures,
            sleep_plan_report=repo_relative_path(sleep_plan_report_path, root) if sleep_plan_report_path else None,
            review_due=review_due,
            conflict_review=conflict_review,
            review_recommendations=recommendation_summary,
            artifact_freshness=artifact_freshness,
            generated_packet_archives=packet_archive_summary,
            cleanup_removed=cleanup_removed,
        )


def dry_run_maintenance(
    root: Path,
    profile: str,
    report_dir: Path = DEFAULT_MAINTENANCE_REPORT_DIR,
) -> dict[str, object]:
    if profile not in {"daily", "weekly"}:
        raise ValueError("profile must be daily or weekly")
    target_report_dir = resolve_report_dir(root, report_dir)
    imports: list[dict[str, object]] = []
    for provider in enabled_providers(root):
        try:
            imports.append(import_chats(root, provider, dry_run=True))
        except Exception as exc:
            imports.append({"provider": provider, "error": str(exc), "dry_run": True})
    return {
        "profile": profile,
        "dry_run": True,
        "mutates_system": False,
        "writes_files": False,
        "writes_import_candidates": False,
        "reads_provider_files": any(bool(item.get("reads_provider_files", False)) for item in imports),
        "would_imports": imports,
        "would_generate": maintenance_artifact_targets(root, profile, target_report_dir),
        "would_secret_scan": True,
        "would_rebuild_index": True,
        "would_refresh_graph": True,
        "would_recalculate_weights": True,
        "would_refresh_lifecycle": True,
        "would_write_report": True,
        "would_write_hook_capture_report": profile == "weekly",
        "would_write_sleep_plan_report": profile == "weekly",
        "would_run_recall": profile == "weekly",
        "would_cleanup_reports": profile == "weekly",
        "would_review_generated_packet_archives": True,
        "would_delete_generated_packet_archives": False,
        "artifact_freshness": generated_artifact_freshness(root, profile=profile),
        "lock_exists": (root / "indexes" / ".maintenance.lock").exists(),
    }


def write_weights(root: Path) -> Path:
    retrieval_counts = load_retrieval_counts(root)
    lifecycle_by_id = {item.memory_id: item for item in lifecycle_scores(root)}
    rows = []
    for document in load_memories(root):
        data = document.frontmatter
        memory_id = str(data["id"])
        lifecycle = lifecycle_by_id.get(memory_id)
        confidence = float(data["confidence"])
        recency = recency_score(str(data["updated_at"]), str(data["decay"]))
        retrieval_boost = min(0.25, retrieval_counts.get(memory_id, 0) * 0.02)
        lifecycle_boost = (lifecycle.score * 0.20) if lifecycle else 0.0
        pin_boost = 0.25 if data.get("pin") else 0.0
        weight = round((confidence * 0.45) + (recency * 0.20) + lifecycle_boost + retrieval_boost + pin_boost, 4)
        rows.append(
            {
                "id": memory_id,
                "path": repo_relative_path(document.path, root),
                "weight": min(weight, 1.0),
                "confidence": confidence,
                "recency": round(recency, 4),
                "retrieval_count": retrieval_counts.get(memory_id, 0),
                "lifecycle_score": lifecycle.score if lifecycle else 0.0,
                "positive_outcomes": lifecycle.positive_outcomes if lifecycle else 0,
                "negative_outcomes": lifecycle.negative_outcomes if lifecycle else 0,
                "recommendation": lifecycle.recommendation if lifecycle else "unproven",
                "pin": bool(data.get("pin")),
            }
        )
    rows.sort(key=lambda item: (-float(item["weight"]), str(item["id"])))
    path = root / "indexes" / "memory-weights.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path


def load_retrieval_counts(root: Path) -> dict[str, int]:
    db_path = default_db_path(root)
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT selected_memory_id, count(*)
            FROM retrieval_log
            WHERE selected_memory_id IS NOT NULL
            GROUP BY selected_memory_id
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    return {str(memory_id): int(count) for memory_id, count in rows}


def cleanup_reports(root: Path, keep: int = 20) -> int:
    report_dir = root / "reports" / "maintenance"
    if not report_dir.exists():
        return 0
    reports = sorted(report_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    removed = 0
    for stale in reports[keep:]:
        stale.unlink()
        removed += 1
    return removed


def artifact_status(root: Path) -> dict[str, dict[str, object]]:
    artifacts: dict[str, dict[str, object]] = {}
    for name, relpath in GENERATED_ARTIFACTS.items():
        path = root / relpath
        if path.exists():
            stat = path.stat()
            updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat()
            size_bytes: int | None = stat.st_size
        else:
            updated_at = None
            size_bytes = None
        artifacts[name] = {
            "path": repo_relative_path(path, root),
            "exists": path.exists(),
            "updated_at": updated_at,
            "size_bytes": size_bytes,
        }
    return artifacts


def generated_artifact_freshness(
    root: Path,
    artifacts: dict[str, dict[str, object]] | None = None,
    profile: str = "daily",
) -> dict[str, object]:
    if profile not in {"daily", "weekly"}:
        raise ValueError("profile must be daily or weekly")
    memory_source_paths = discover_memory_files(root)
    artifact_rows = artifacts if artifacts is not None else artifact_status(root)
    if profile == "daily":
        artifact_rows = {
            name: artifact
            for name, artifact in artifact_rows.items()
            if name not in WEEKLY_GENERATED_ARTIFACTS
        }

    hook_capture_sources = hook_capture_files(root / "inbox" / "session-events")

    def sources_for_artifact(name: str) -> list[Path]:
        if name == "hook_capture_report":
            return hook_capture_sources
        return memory_source_paths

    def latest_path_and_mtime(paths: list[Path]) -> tuple[Path | None, float]:
        latest_path: Path | None = None
        latest_mtime = 0.0
        for path in paths:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= latest_mtime:
                latest_path = path
                latest_mtime = mtime
        return latest_path, latest_mtime

    selected_source_paths: list[Path] = []
    seen_sources: set[str] = set()
    for name in artifact_rows:
        for source_path in sources_for_artifact(name):
            source_key = str(source_path)
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                selected_source_paths.append(source_path)

    latest_source, latest_source_mtime = latest_path_and_mtime(selected_source_paths)
    latest_source_updated_at = (
        datetime.fromtimestamp(latest_source_mtime, timezone.utc).replace(microsecond=0).isoformat()
        if latest_source
        else None
    )
    freshness_by_name: dict[str, dict[str, object]] = {}
    missing_count = 0
    stale_count = 0
    fresh_count = 0
    for name, artifact in artifact_rows.items():
        path = root / str(artifact["path"])
        exists = bool(artifact.get("exists", False))
        artifact_sources = sources_for_artifact(name)
        artifact_latest_source, artifact_latest_mtime = latest_path_and_mtime(artifact_sources)
        if not exists:
            status = "missing"
            missing_count += 1
            stale = True
        elif artifact_latest_source is None:
            status = "no_sources"
            fresh_count += 1
            stale = False
        else:
            try:
                stale = path.stat().st_mtime < artifact_latest_mtime
            except OSError:
                stale = True
            status = "stale" if stale else "fresh"
            if stale:
                stale_count += 1
            else:
                fresh_count += 1
        freshness_by_name[name] = {
            "path": artifact["path"],
            "exists": exists,
            "updated_at": artifact.get("updated_at"),
            "status": status,
            "stale": stale,
            "source_count": len(artifact_sources),
            "latest_source_path": repo_relative_path(artifact_latest_source, root) if artifact_latest_source else None,
            "latest_source_updated_at": (
                datetime.fromtimestamp(artifact_latest_mtime, timezone.utc).replace(microsecond=0).isoformat()
                if artifact_latest_source
                else None
            ),
        }

    needs_maintenance = missing_count > 0 or stale_count > 0
    next_action = (
        f"Run ai-dememory maintenance run --profile {profile}."
        if needs_maintenance
        else f"{profile.title()} generated artifacts are current."
    )
    return {
        "profile": profile,
        "source_count": len(selected_source_paths),
        "latest_source_path": repo_relative_path(latest_source, root) if latest_source else None,
        "latest_source_updated_at": latest_source_updated_at,
        "missing_count": missing_count,
        "stale_count": stale_count,
        "fresh_count": fresh_count,
        "needs_maintenance": needs_maintenance,
        "next_action": next_action,
        "artifacts": freshness_by_name,
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "deletes_files": False,
    }


def generated_packet_archive_summary(root: Path) -> dict[str, object]:
    def summarize(status: dict[str, object], retention: dict[str, object]) -> dict[str, object]:
        archives = status.get("archives")
        latest = archives[0] if isinstance(archives, list) and archives else None
        prunable_count = int(retention.get("prunable_count", 0))
        return {
            "archive_root": status.get("archive_root"),
            "total_count": int(status.get("total_count", 0)),
            "keep": int(retention.get("keep", 0)),
            "retained_count": int(retention.get("retained_count", 0)),
            "prunable_count": prunable_count,
            "has_prunable": prunable_count > 0,
            "latest": latest,
        }

    try:
        recall_status = recall_review_packet_archive_status(root, limit=1)
        recall_retention = recall_review_packet_archive_retention_plan(root, limit=1)
        acceptance_status = acceptance_packet_archive_status(root, limit=1)
        acceptance_retention = acceptance_packet_archive_retention_plan(root, limit=1)
    except (OSError, ValueError) as exc:
        return {
            "available": False,
            "errors": [str(exc)],
            "summary": {"total_count": 0, "prunable_count": 0, "has_prunable": False},
            "recall_review_packets": {},
            "manual_acceptance_packets": {},
            "mutates_system": False,
            "runs_commands": False,
            "writes_files": False,
            "deletes_files": False,
            "records_evidence": False,
            "records_fixture_promotions": False,
        }

    recall = summarize(recall_status, recall_retention)
    acceptance = summarize(acceptance_status, acceptance_retention)
    prunable_count = int(recall["prunable_count"]) + int(acceptance["prunable_count"])
    return {
        "available": True,
        "errors": [],
        "summary": {
            "total_count": int(recall["total_count"]) + int(acceptance["total_count"]),
            "prunable_count": prunable_count,
            "has_prunable": prunable_count > 0,
        },
        "recall_review_packets": recall,
        "manual_acceptance_packets": acceptance,
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "deletes_files": False,
        "records_evidence": False,
        "records_fixture_promotions": False,
    }


def review_due_summary(root: Path) -> dict[str, object]:
    reviews = false_positive_reviews(root)
    ignored = [item for item in reviews if item.ignored]
    due = [item for item in ignored if item.review_due]
    stale = stale_false_positive_suppressions(root, current_reviews=reviews)
    stale_due = [item for item in stale if item.review_due]
    status_counts: dict[str, int] = {}
    for item in reviews:
        status_counts[item.review_after_status] = status_counts.get(item.review_after_status, 0) + 1
    return {
        "false_positive_findings": len(reviews),
        "active_findings": len([item for item in reviews if not item.ignored]),
        "ignored_findings": len(ignored),
        "due_findings": len(due),
        "due_ids": [item.id for item in due[:20]],
        "stale_suppressions": len(stale),
        "stale_ids": [item.id for item in stale[:20]],
        "stale_review_due": len(stale_due),
        "stale_review_due_ids": [item.id for item in stale_due[:20]],
        "status_counts": dict(sorted(status_counts.items())),
        "canonical_memory_updated": False,
    }


def conflict_review_summary(root: Path) -> dict[str, object]:
    try:
        conflicts = conflict_reviews(root)
    except ReviewError as exc:
        return {
            "available": False,
            "errors": str(exc).splitlines()[:20],
            "conflicts": 0,
            "active_conflicts": 0,
            "reviewed_conflicts": 0,
            "active_ids": [],
            "status_counts": {},
            "category_counts": {},
            "canonical_memory_updated": False,
        }
    active = [item for item in conflicts if item.status == "active"]
    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in conflicts:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        category_counts[item.category] = category_counts.get(item.category, 0) + 1
    return {
        "available": True,
        "errors": [],
        "conflicts": len(conflicts),
        "active_conflicts": len(active),
        "reviewed_conflicts": len(conflicts) - len(active),
        "active_ids": [item.id for item in active[:20]],
        "status_counts": dict(sorted(status_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "canonical_memory_updated": False,
    }


def review_recommendation_summary(root: Path) -> dict[str, object]:
    try:
        status = review_recommendations(root)
    except ReviewError as exc:
        return {
            "available": False,
            "errors": str(exc).splitlines()[:20],
            "total_count": 0,
            "pending_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "invalid_count": 0,
            "policy_violation_count": 0,
            "requires_human_approval_count": 0,
            "pending_ids": [],
            "status_counts": {},
            "kind_counts": {},
            "latest_created_at": None,
            "applies_review_decisions": False,
            "writes_canonical_memory": False,
            "canonical_memory_updated": False,
        }
    recommendations = status.get("recommendations", [])
    status_counts = {
        "pending": int(status.get("pending_count", 0)),
        "accepted": int(status.get("accepted_count", 0)),
        "rejected": int(status.get("rejected_count", 0)),
    }
    kind_counts: dict[str, int] = {}
    pending_ids: list[str] = []
    recommendation_items = recommendations if isinstance(recommendations, list) else []
    for item in recommendation_items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        if item.get("outcome_status") == "pending" and isinstance(item.get("id"), str):
            pending_ids.append(str(item["id"]))
    return {
        "available": True,
        "errors": [],
        "total_count": int(status.get("total_count", 0)),
        "pending_count": status_counts["pending"],
        "accepted_count": status_counts["accepted"],
        "rejected_count": status_counts["rejected"],
        "invalid_count": int(status.get("invalid_count", 0)),
        "policy_violation_count": int(status.get("policy_violation_count", 0)),
        "requires_human_approval_count": int(status.get("requires_human_approval_count", 0)),
        "pending_ids": pending_ids[:20],
        "status_counts": status_counts,
        "kind_counts": dict(sorted(kind_counts.items())),
        "latest_created_at": status.get("latest_created_at"),
        "applies_review_decisions": False,
        "writes_canonical_memory": False,
        "canonical_memory_updated": False,
    }


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def resolve_report_dir(root: Path, report_dir: str | Path) -> Path:
    target = resolve_repo_path(root, report_dir)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("maintenance report directory must stay inside the memory root") from exc
    return target


def write_maintenance_report(
    root: Path,
    profile: str,
    started_at: str,
    finished_at: str,
    imports: list[dict[str, object]],
    index_count: int,
    graph: dict[str, list[dict[str, object]]],
    weights_path: Path,
    lifecycle_scores_path: Path,
    lifecycle_report_path: Path,
    lifecycle_count: int,
    recall_summary: dict[str, object] | None,
    hook_capture_report: str | None,
    hook_captures: dict[str, object] | None,
    sleep_plan_report: str | None,
    review_due: dict[str, object],
    conflict_review: dict[str, object],
    review_recommendations: dict[str, object],
    artifact_freshness: dict[str, object],
    generated_packet_archives: dict[str, object],
    cleanup_removed: int,
    report_dir: Path = DEFAULT_MAINTENANCE_REPORT_DIR,
) -> Path:
    target_dir = resolve_report_dir(root, report_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{profile}.md"
    path = target_dir / filename
    imported_count = sum(len(item.get("written", [])) for item in imports if isinstance(item, dict))
    packet_archive_counts = generated_packet_archives.get("summary", {})
    lines = [
        f"# {profile.title()} Maintenance",
        "",
        f"- started_at: `{started_at}`",
        f"- finished_at: `{finished_at}`",
        f"- imported_candidates: `{imported_count}`",
        f"- indexed_memories: `{index_count}`",
        f"- graph_nodes: `{len(graph['nodes'])}`",
        f"- graph_edges: `{len(graph['edges'])}`",
        f"- weights: `{repo_relative_path(weights_path, root)}`",
        f"- lifecycle_scores: `{repo_relative_path(lifecycle_scores_path, root)}`",
        f"- lifecycle_report: `{repo_relative_path(lifecycle_report_path, root)}`",
        f"- lifecycle_count: `{lifecycle_count}`",
        f"- sleep_plan_report: `{sleep_plan_report or ''}`",
        f"- hook_capture_report: `{hook_capture_report or ''}`",
        f"- hook_capture_review_due: `{(hook_captures or {}).get('review_due_count', 0)}`",
        f"- false_positive_review_due: `{review_due.get('due_findings', 0)}`",
        f"- false_positive_stale_suppressions: `{review_due.get('stale_suppressions', 0)}`",
        f"- active_conflicts: `{conflict_review.get('active_conflicts', 0)}`",
        f"- pending_review_recommendations: `{review_recommendations.get('pending_count', 0)}`",
        f"- artifact_freshness_missing: `{artifact_freshness.get('missing_count', 0)}`",
        f"- artifact_freshness_stale: `{artifact_freshness.get('stale_count', 0)}`",
        f"- generated_packet_archive_prunable: `{packet_archive_counts.get('prunable_count', 0)}`",
        f"- cleanup_removed: `{cleanup_removed}`",
        "",
        "## Provider Imports",
        "",
    ]
    if imports:
        for item in imports:
            lines.append(f"- `{item.get('provider', 'unknown')}`: {json.dumps(item, sort_keys=True)}")
    else:
        lines.append("_No providers enabled._")
    lines.append("")
    lines.extend(["## Review Due", "", f"```json\n{json.dumps(review_due, indent=2)}\n```", ""])
    lines.extend(["## Conflict Review", "", f"```json\n{json.dumps(conflict_review, indent=2)}\n```", ""])
    lines.extend(["## Review Recommendations", "", f"```json\n{json.dumps(review_recommendations, indent=2)}\n```", ""])
    lines.extend(["## Generated Artifact Freshness", "", f"```json\n{json.dumps(artifact_freshness, indent=2)}\n```", ""])
    lines.extend(["## Generated Packet Archives", "", f"```json\n{json.dumps(generated_packet_archives, indent=2)}\n```", ""])
    if recall_summary is not None:
        lines.extend(["## Recall", "", f"```json\n{json.dumps(recall_summary, indent=2)}\n```", ""])
    if hook_captures is not None:
        lines.extend(["## Hook Captures", "", f"```json\n{json.dumps(hook_captures, indent=2)}\n```", ""])
    text = "\n".join(lines)
    if scan_text(text, "<maintenance-report>"):
        raise RuntimeError("maintenance report rejected by secret scan")
    path.write_text(text, encoding="utf-8")
    return path


def maintenance_status(root: Path) -> dict[str, object]:
    config = load_config(root)
    report_dir = root / "reports" / "maintenance"
    reports = [
        repo_relative_path(path, root)
        for path in sorted(report_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:5]
    ] if report_dir.exists() else []
    artifacts = artifact_status(root)
    return {
        "schedule": config.get("schedule", {}),
        "providers": provider_config(root),
        "provider_readiness": providers_status(root),
        "review_due": review_due_summary(root),
        "conflict_review": conflict_review_summary(root),
        "review_recommendations": review_recommendation_summary(root),
        "generated_packet_archives": generated_packet_archive_summary(root),
        "hook_captures": hook_capture_summary(root),
        "recent_reports": reports,
        "artifacts": artifacts,
        "artifact_freshness": generated_artifact_freshness(root, artifacts),
        "lock_exists": (root / "indexes" / ".maintenance.lock").exists(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run a maintenance profile.")
    run.add_argument("--profile", choices=("daily", "weekly"), default="daily")
    run.add_argument("--report-dir", default=str(DEFAULT_MAINTENANCE_REPORT_DIR), help="Report directory inside the memory root.")
    run.add_argument("--dry-run", action="store_true", help="Preview maintenance work without writing files.")
    run.add_argument("--json", action="store_true")
    status = subparsers.add_parser("status", help="Show maintenance configuration and reports.")
    status.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    root = repo_root(args.root)
    if args.command == "status":
        data = maintenance_status(root)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(json.dumps(data, indent=2))
        return 0

    try:
        if args.dry_run:
            preview = dry_run_maintenance(root, args.profile, Path(args.report_dir))
            if args.json:
                print(json.dumps(preview, indent=2))
            else:
                print(f"Would run {args.profile} maintenance.")
                print("Would generate:")
                for item in preview["would_generate"]:
                    print(f"- {item}")
                print(f"Provider previews: {len(preview['would_imports'])}")
            return 0
        result = run_maintenance(root, args.profile, Path(args.report_dir))
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"Completed {result.profile} maintenance. Report: {result.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
