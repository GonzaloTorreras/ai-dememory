#!/usr/bin/env python3
"""Minimal stdio MCP-compatible server for the local memory repository."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any
from urllib.parse import quote, unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from consolidate_memory import build_report  # noqa: E402
from context_memory import assemble_context, context_defaults, resolve_context_query  # noqa: E402
from capture_miss import capture_miss  # noqa: E402
from doctor import doctor_profile, run_checks as run_doctor_checks, summarize_checks  # noqa: E402
from durable_provenance import audit_durable_provenance  # noqa: E402
from graph_memory import build_graph  # noqa: E402
from git_lessons import learn_git  # noqa: E402
from hook_event import (  # noqa: E402
    HOOK_CAPTURE_REVIEW_STATUSES,
    hook_config,
    hook_events,
    hook_status_summary,
    review_hook_capture,
)
from index_memory import default_db_path, rebuild_index  # noqa: E402
from lifecycle import lifecycle_scores, record_outcome  # noqa: E402
from maintenance import dry_run_maintenance, maintenance_status, run_maintenance  # noqa: E402
from manual_acceptance import (  # noqa: E402
    ACCEPTANCE_ITEMS,
    annotate_acceptance_packet_plan,
    acceptance_packet_archive_retention_plan,
    acceptance_packet_archive_status,
    acceptance_plan,
    acceptance_status,
    acceptance_template,
    paginate_acceptance_packet_plan,
    render_acceptance_packet_report,
    status_to_dict,
    verify_acceptance,
)
from memorylib import (  # noqa: E402
    SOURCE_KINDS,
    discover_memory_files,
    extract_summary,
    is_memory_file,
    load_memory,
    repo_relative_path,
    repo_root,
    slugify,
)
from search_memory import result_to_dict, search  # noqa: E402
from provider_import import CAPTURE_KINDS, capture_source, detect_providers, import_chats, provider_setup_plan, providers_status  # noqa: E402
from publish_plan import REPOSITORIES, publish_plan  # noqa: E402
from recall_fixtures import (  # noqa: E402
    annotate_recall_review_packet_plan,
    paginate_recall_review_plan,
    recall_fixture_freshness,
    recall_miss_candidate,
    recall_fixture_review_plan,
    recall_review_packet_archive_retention_plan,
    recall_review_packet_archive_status,
    render_recall_review_packet,
    review_recall_miss,
)
from release_evidence import build_release_evidence, evidence_to_dict, render_markdown as render_release_evidence_markdown  # noqa: E402
from roadmap_status import roadmap_status  # noqa: E402
from review_memory import (  # noqa: E402
    REVIEW_MODE_ALIASES,
    REVIEW_MODES,
    REVIEW_RECOMMENDATION_ACTIONS,
    archived_review_recommendations,
    conflict_review_metadata,
    capture_review_recommendation,
    configure_review_mode,
    conflict_reviews,
    dismiss_conflict,
    false_positive_review_metadata,
    false_positive_reviews,
    filter_false_positive_reviews,
    ignore_false_positive,
    load_review_config,
    optional_bool,
    review_after_state,
    review_modes,
    review_plan,
    record_review_recommendation_outcome,
    render_review_recommendation_outcome_report,
    review_recommendation_outcome_report_payload,
    review_recommendations,
    resolve_conflict,
    restore_archived_review_recommendation,
    stale_false_positive_suppressions,
    string_or_none,
    unignore_false_positive,
)
from schedule_memory import schedule_environment, schedule_plan, schedule_status  # noqa: E402
from setup_plan import setup_health, setup_plan  # noqa: E402
from secret_scan import scan_paths, scan_text  # noqa: E402
from sleep_consolidation import apply_review_packets, build_sleep_plan  # noqa: E402
from validate_memory import validate_repo_result  # noqa: E402
from vector_gate import DEFAULT_MIN_FAILED_CASES, DEFAULT_RECALL_THRESHOLD, evaluate_vector_readiness  # noqa: E402
from working_memory import (  # noqa: E402
    handoff as write_working_handoff,
    show_current,
    snapshot as write_working_snapshot,
    working_status,
)


SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2024-11-05")
SAFE_CONTEXT_SENSITIVITIES = {"public", "internal"}
MAX_TOOL_LIMIT = 50
MAX_PROPOSAL_CHARS = 20000
MAX_WORKING_CHARS = 12000
DEFAULT_PAGE_SIZE = 100
RESOURCE_URI_PREFIX = "memory://"

SERVER_CAPABILITIES: dict[str, Any] = {
    "tools": {"listChanged": False},
    "resources": {"listChanged": False},
    "prompts": {"listChanged": False},
}


def object_schema(
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
    additional_properties: bool = False,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": additional_properties,
    }
    if required:
        schema["required"] = required
    return schema


TOOLS: list[dict[str, Any]] = [
    {
        "name": "memory.doctor",
        "title": "Memory Doctor",
        "description": "Return local ai-dememory readiness checks without mutating files.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "checks": {"type": "array", "items": {"type": "object"}},
                "profile": {"type": "string"},
                "summary": {"type": "object"},
            },
            ["checks", "profile", "summary"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.validate_status",
        "title": "Validate Memory Status",
        "description": "Return structured Markdown memory validation and conflict scan status without mutating files.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "ok": {"type": "boolean"},
                "exit_code": {"type": "integer"},
                "memory_count": {"type": "integer"},
                "messages": {"type": "array", "items": {"type": "string"}},
                "errors": {"type": "array", "items": {"type": "string"}},
                "conflict_review": {"type": "object"},
            },
            ["ok", "exit_code", "memory_count", "messages", "errors", "conflict_review"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.search",
        "title": "Search Memory",
        "description": "Search ranked local memory results from the SQLite index.",
        "inputSchema": object_schema(
            {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 10},
                "include_sensitive": {"type": "boolean", "default": False},
            },
            ["query"],
        ),
        "outputSchema": object_schema(
            {
                "results": {
                    "type": "array",
                    "items": {"type": "object"},
                }
            },
            ["results"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.get",
        "title": "Get Memory",
        "description": "Read a memory document by id or repository-relative path.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "path": {"type": "string"},
                "include_sensitive": {"type": "boolean", "default": False},
            },
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "frontmatter": {"type": "object"},
                "content": {"type": "string"},
            },
            ["path", "frontmatter", "content"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.write_proposal",
        "title": "Write Memory Proposal",
        "description": "Write a reviewed proposal candidate to inbox/llm-captures/.",
        "inputSchema": object_schema(
            {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "project": {"type": ["string", "null"]},
                "tags": {"type": "array", "items": {"type": "string"}},
                "source_kind": {"type": "string", "enum": sorted(SOURCE_KINDS), "default": "codex"},
                "source_ref": {"type": ["string", "null"]},
            },
            ["title", "content"],
        ),
        "outputSchema": object_schema({"path": {"type": "string"}}, ["path"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.context",
        "title": "Assemble Memory Context",
        "description": "Return token-budgeted memory context for an explicit query or generated working context.",
        "inputSchema": object_schema(
            {
                "query": {"type": ["string", "null"]},
                "auto": {"type": "boolean", "default": False},
                "budget_tokens": {"type": "integer", "minimum": 200, "maximum": 20000, "default": 2000},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 20},
                "include_sensitive": {"type": "boolean", "default": False},
                "include_working_memory": {"type": "boolean", "default": True},
                "explain_results": {"type": "boolean", "default": False},
            },
        ),
        "outputSchema": object_schema(
            {
                "query": {"type": "string"},
                "query_source": {"type": "string", "enum": ["explicit", "working_memory"]},
                "budget_tokens": {"type": "integer"},
                "estimated_tokens": {"type": "integer"},
                "remaining_tokens": {"type": "integer"},
                "explain_results": {"type": "boolean"},
                "items": {"type": "array", "items": {"type": "object"}},
                "text": {"type": "string"},
            },
            ["query", "query_source", "budget_tokens", "estimated_tokens", "remaining_tokens", "explain_results", "items", "text"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.mark_seen",
        "title": "Mark Memory Seen",
        "description": "Log that a memory search result was used.",
        "inputSchema": object_schema(
            {
                "query": {"type": "string"},
                "selected_memory_id": {"type": ["string", "null"]},
                "score": {"type": ["number", "null"]},
                "used_by": {"type": ["string", "null"]},
            },
            ["query"],
        ),
        "outputSchema": object_schema(
            {
                "query": {"type": "string"},
                "selected_memory_id": {"type": ["string", "null"]},
                "score": {"type": ["number", "null"]},
                "used_by": {"type": ["string", "null"]},
                "lifecycle_updated": {"type": "boolean"},
                "created_at": {"type": "string"},
            },
            ["query", "lifecycle_updated", "created_at"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.reindex",
        "title": "Rebuild Memory Index",
        "description": "Run secret scan, validation, and rebuild the SQLite index.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {"path": {"type": "string"}, "count": {"type": "integer"}},
            ["path", "count"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.consolidate",
        "title": "Consolidation Dry Run",
        "description": "Generate a consolidation dry-run report. Does not mutate memories.",
        "inputSchema": object_schema({"dry_run": {"type": "boolean", "default": True}}),
        "outputSchema": object_schema({"report": {"type": "string"}}, ["report"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.secret_scan",
        "title": "Secret Scan",
        "description": "Scan selected paths or the repository for suspected secrets.",
        "inputSchema": object_schema({"paths": {"type": "array", "items": {"type": "string"}}}),
        "outputSchema": object_schema({"findings": {"type": "array", "items": {"type": "object"}}}, ["findings"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.graph",
        "title": "Memory Graph",
        "description": "Return a lightweight graph of memory, tag, project, type, scope, and reference relationships.",
        "inputSchema": object_schema(
            {
                "include_sensitive": {"type": "boolean", "default": False},
            },
        ),
        "outputSchema": object_schema(
            {
                "nodes": {"type": "array", "items": {"type": "object"}},
                "edges": {"type": "array", "items": {"type": "object"}},
            },
            ["nodes", "edges"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.outcome",
        "title": "Record Memory Outcome",
        "description": "Record good/bad usefulness feedback for a memory or last seen memory.",
        "inputSchema": object_schema(
            {
                "id": {"type": ["string", "null"]},
                "last": {"type": "boolean", "default": False},
                "outcome": {"type": "string", "enum": ["good", "bad"]},
                "note": {"type": ["string", "null"]},
            },
            ["outcome"],
        ),
        "outputSchema": object_schema(
            {
                "memory_id": {"type": "string"},
                "target_source": {"type": "string", "enum": ["explicit", "last_seen"]},
                "outcome": {"type": "string", "enum": ["good", "bad"]},
                "note_recorded": {"type": "boolean"},
                "positive_outcomes": {"type": "integer"},
                "negative_outcomes": {"type": "integer"},
                "strength": {"type": "number"},
                "reward_factor": {"type": "number"},
                "lifecycle_updated": {"type": "boolean"},
                "created_at": {"type": "string"},
            },
            [
                "memory_id",
                "target_source",
                "outcome",
                "note_recorded",
                "positive_outcomes",
                "negative_outcomes",
                "strength",
                "reward_factor",
                "lifecycle_updated",
                "created_at",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.lifecycle_scores",
        "title": "Lifecycle Scores",
        "description": "Return generated lifecycle scores from retrieval and outcome feedback.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema({"scores": {"type": "array", "items": {"type": "object"}}}, ["scores"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.sleep_plan",
        "title": "Sleep Consolidation Plan",
        "description": "Return safe sleep consolidation candidates without mutating memory.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "generated_at": {"type": "string"},
                "candidates": {"type": "array", "items": {"type": "object"}},
            },
            ["generated_at", "candidates"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.sleep_apply_reviewed",
        "title": "Write Sleep Review Packets",
        "description": "Write selected sleep consolidation candidates to inbox/sleep-consolidation/.",
        "inputSchema": object_schema(
            {
                "ids": {"type": "array", "items": {"type": "string"}},
                "all": {"type": "boolean", "default": False},
            },
        ),
        "outputSchema": object_schema({"written": {"type": "array", "items": {"type": "string"}}}, ["written"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.working_current",
        "title": "Current Working Memory",
        "description": "Read the generated working/current.json snapshot if present.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "current": {"type": "object"},
                "exists": {"type": "boolean"},
            },
            ["current", "exists"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.working_status",
        "title": "Working Memory Status",
        "description": "Summarize current working state, recent-session file, and recent handoffs.",
        "inputSchema": object_schema(
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
        ),
        "outputSchema": object_schema(
            {
                "current_exists": {"type": "boolean"},
                "current_path": {"type": ["string", "null"]},
                "current": {"type": "object"},
                "recent_session_exists": {"type": "boolean"},
                "recent_session_path": {"type": ["string", "null"]},
                "handoff_count": {"type": "integer"},
                "handoffs": {"type": "array", "items": {"type": "object"}},
            },
            ["current_exists", "recent_session_exists", "handoff_count", "handoffs"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.working_snapshot",
        "title": "Write Working Snapshot",
        "description": "Write generated working/current.json and working/recent-session.md after secret scanning.",
        "inputSchema": object_schema(
            {
                "title": {"type": "string"},
                "notes": {"type": "string"},
                "task": {"type": ["string", "null"]},
            },
            ["title", "notes"],
        ),
        "outputSchema": object_schema({"path": {"type": "string"}}, ["path"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.working_handoff",
        "title": "Write Working Handoff",
        "description": "Write a generated working/handoffs/ Markdown handoff after secret scanning.",
        "inputSchema": object_schema(
            {
                "title": {"type": "string"},
                "notes": {"type": "string"},
            },
            ["title", "notes"],
        ),
        "outputSchema": object_schema({"path": {"type": "string"}}, ["path"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.capture_miss",
        "title": "Capture Recall Miss",
        "description": "Write a reviewed recall miss candidate to inbox/recall-feedback/.",
        "inputSchema": object_schema(
            {
                "query": {"type": "string"},
                "reason": {"type": "string"},
                "expected_id": {"type": ["string", "null"]},
                "expected_path": {"type": ["string", "null"]},
            },
            ["query", "reason"],
        ),
        "outputSchema": object_schema({"path": {"type": "string"}}, ["path"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_fixture_status",
        "title": "Recall Fixture Status",
        "description": "Report recall fixture provenance and reviewed-promotion freshness.",
        "inputSchema": object_schema(
            {
                "max_age_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 14},
            },
        ),
        "outputSchema": object_schema(
            {
                "fixtures_path": {"type": "string"},
                "total_fixtures": {"type": "integer"},
                "reviewed_promotions": {"type": "integer"},
                "seed_fixtures": {"type": "integer"},
                "latest_reviewed_at": {"type": ["string", "null"]},
                "latest_created_at": {"type": ["string", "null"]},
                "max_age_days": {"type": "integer"},
                "days_since_latest_review": {"type": ["integer", "null"]},
                "needs_reviewed_promotion": {"type": "boolean"},
                "stale": {"type": "boolean"},
                "status": {"type": "string"},
                "next_action": {"type": "string"},
            },
            [
                "fixtures_path",
                "total_fixtures",
                "reviewed_promotions",
                "seed_fixtures",
                "max_age_days",
                "needs_reviewed_promotion",
                "stale",
                "status",
                "next_action",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_miss_candidate",
        "title": "Check Recall Miss Candidate",
        "description": "Check whether a query and expected memory are a recall miss candidate without writing files.",
        "inputSchema": object_schema(
            {
                "query": {"type": "string"},
                "expected_id": {"type": ["string", "null"]},
                "expected_path": {"type": ["string", "null"]},
                "min_rank": {"type": "integer", "minimum": 1, "maximum": 100, "default": 5},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                "include_sensitive": {"type": "boolean", "default": False},
            },
            ["query"],
        ),
        "outputSchema": object_schema(
            {
                "query": {"type": "string"},
                "expected_id": {"type": "string"},
                "expected_path": {"type": ["string", "null"]},
                "expected_rank": {"type": ["integer", "null"]},
                "min_rank": {"type": "integer"},
                "searched_limit": {"type": "integer"},
                "candidate_miss": {"type": "boolean"},
                "reason": {"type": "string"},
                "top_results": {"type": "array", "items": {"type": "object"}},
                "capture_dry_run_command": {"type": "array", "items": {"type": "string"}},
                "capture_write_command": {"type": "array", "items": {"type": "string"}},
                "writes_files": {"type": "boolean"},
            },
            [
                "query",
                "expected_id",
                "expected_rank",
                "min_rank",
                "searched_limit",
                "candidate_miss",
                "reason",
                "top_results",
                "capture_dry_run_command",
                "capture_write_command",
                "writes_files",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_review_plan",
        "title": "Recall Review Plan",
        "description": "Report pending recall miss review work without writing fixture files.",
        "inputSchema": object_schema(
            {
                "max_age_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 14},
                "resolved_limit": {"type": "integer", "minimum": 0, "maximum": 50, "default": 5},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "pending_offset": {"type": "integer", "minimum": 0, "default": 0},
                "invalid_offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        ),
        "outputSchema": object_schema(
            {
                "fixtures_path": {"type": "string"},
                "status": {"type": "string"},
                "stale": {"type": "boolean"},
                "pending_count": {"type": "integer"},
                "invalid_count": {"type": "integer"},
                "resolved_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "pending_returned_count": {"type": "integer"},
                "pending_offset": {"type": "integer"},
                "pending_next_offset": {"type": ["integer", "null"]},
                "pending_has_more": {"type": "boolean"},
                "invalid_returned_count": {"type": "integer"},
                "invalid_offset": {"type": "integer"},
                "invalid_next_offset": {"type": ["integer", "null"]},
                "invalid_has_more": {"type": "boolean"},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
                "freshness": {"type": "object"},
                "pending_misses": {"type": "array", "items": {"type": "object"}},
                "invalid_misses": {"type": "array", "items": {"type": "object"}},
                "recent_resolved_misses": {"type": "array", "items": {"type": "object"}},
                "candidate_check_command": {"type": "array", "items": {"type": "string"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "fixtures_path",
                "status",
                "stale",
                "pending_count",
                "invalid_count",
                "resolved_count",
                "limit",
                "pending_returned_count",
                "pending_offset",
                "pending_next_offset",
                "pending_has_more",
                "invalid_returned_count",
                "invalid_offset",
                "invalid_next_offset",
                "invalid_has_more",
                "reviewer",
                "pr_url",
                "freshness",
                "pending_misses",
                "invalid_misses",
                "recent_resolved_misses",
                "candidate_check_command",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_review_packet",
        "title": "Recall Review Packet",
        "description": "Render the weekly recall review packet without writing reports, fixture files, or miss outcomes.",
        "inputSchema": object_schema(
            {
                "max_age_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 14},
                "resolved_limit": {"type": "integer", "minimum": 0, "maximum": 50, "default": 5},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 50},
                "pending_offset": {"type": "integer", "minimum": 0, "default": 0},
                "invalid_offset": {"type": "integer", "minimum": 0, "default": 0},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema(
            {
                "fixtures_path": {"type": "string"},
                "status": {"type": "string"},
                "stale": {"type": "boolean"},
                "pending_count": {"type": "integer"},
                "invalid_count": {"type": "integer"},
                "resolved_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "pending_returned_count": {"type": "integer"},
                "pending_offset": {"type": "integer"},
                "pending_next_offset": {"type": ["integer", "null"]},
                "pending_has_more": {"type": "boolean"},
                "invalid_returned_count": {"type": "integer"},
                "invalid_offset": {"type": "integer"},
                "invalid_next_offset": {"type": ["integer", "null"]},
                "invalid_has_more": {"type": "boolean"},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
                "pending_misses": {"type": "array", "items": {"type": "object"}},
                "invalid_misses": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "records_fixture_promotions": {"type": "boolean"},
                "writes_fixture_file": {"type": "boolean"},
                "closes_miss_files": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "report_path": {"type": ["string", "null"]},
                "markdown": {"type": "string"},
            },
            [
                "fixtures_path",
                "status",
                "stale",
                "pending_count",
                "invalid_count",
                "resolved_count",
                "limit",
                "pending_returned_count",
                "pending_offset",
                "pending_next_offset",
                "pending_has_more",
                "invalid_returned_count",
                "invalid_offset",
                "invalid_next_offset",
                "invalid_has_more",
                "reviewer",
                "pr_url",
                "pending_misses",
                "invalid_misses",
                "mutates_system",
                "records_fixture_promotions",
                "writes_fixture_file",
                "closes_miss_files",
                "writes_files",
                "report_path",
                "markdown",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_review_packet_archive_status",
        "title": "Recall Review Packet Archive Status",
        "description": "List generated recall review packet archives without writing files, fixtures, or miss outcomes.",
        "inputSchema": object_schema(
            {
                "archive_dir": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        ),
        "outputSchema": object_schema(
            {
                "archive_root": {"type": "string"},
                "total_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "archives": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "records_fixture_promotions": {"type": "boolean"},
                "writes_fixture_file": {"type": "boolean"},
                "closes_miss_files": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
            },
            [
                "archive_root",
                "total_count",
                "limit",
                "offset",
                "returned_count",
                "next_offset",
                "has_more",
                "archives",
                "mutates_system",
                "records_fixture_promotions",
                "writes_fixture_file",
                "closes_miss_files",
                "writes_files",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_review_packet_archive_retention_plan",
        "title": "Recall Review Packet Archive Retention Plan",
        "description": "Plan generated recall review packet archive pruning without deleting files, writing fixtures, or closing misses.",
        "inputSchema": object_schema(
            {
                "archive_dir": {"type": ["string", "null"]},
                "keep": {"type": "integer", "minimum": 1, "default": 30},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        ),
        "outputSchema": object_schema(
            {
                "archive_root": {"type": "string"},
                "total_count": {"type": "integer"},
                "keep": {"type": "integer"},
                "retained_count": {"type": "integer"},
                "prunable_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "prune_candidates": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "records_fixture_promotions": {"type": "boolean"},
                "writes_fixture_file": {"type": "boolean"},
                "closes_miss_files": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "deletes_files": {"type": "boolean"},
            },
            [
                "archive_root",
                "total_count",
                "keep",
                "retained_count",
                "prunable_count",
                "limit",
                "offset",
                "returned_count",
                "next_offset",
                "has_more",
                "prune_candidates",
                "mutates_system",
                "records_fixture_promotions",
                "writes_fixture_file",
                "closes_miss_files",
                "writes_files",
                "deletes_files",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.recall_miss_review",
        "title": "Review Recall Miss",
        "description": "Reject or dismiss a reviewed recall miss without writing recall fixtures or canonical memory.",
        "inputSchema": object_schema(
            {
                "miss": {"type": "string"},
                "status": {"type": "string", "enum": ["dismissed", "rejected"]},
                "reviewer": {"type": "string"},
                "reason": {"type": "string"},
            },
            ["miss", "status", "reviewer", "reason"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "status": {"type": "string", "enum": ["dismissed", "rejected"]},
                "reviewed_by": {"type": "string"},
                "reviewed_at": {"type": "string"},
                "reason": {"type": "string"},
                "fixture_updated": {"type": "boolean"},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "status", "reviewed_by", "reviewed_at", "reason", "fixture_updated", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.vector_status",
        "title": "Vector Readiness Status",
        "description": "Report whether recall fixtures justify a future vector search experiment.",
        "inputSchema": object_schema(
            {
                "recall_threshold": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": DEFAULT_RECALL_THRESHOLD,
                },
                "min_failed_cases": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": DEFAULT_MIN_FAILED_CASES,
                },
            },
        ),
        "outputSchema": object_schema(
            {
                "decision": {"type": "string"},
                "rationale": {"type": "string"},
                "recall_threshold": {"type": "number"},
                "min_failed_cases": {"type": "integer"},
                "recall": {"type": "object"},
                "failed_case_ids": {"type": "array", "items": {"type": "string"}},
                "generated_at": {"type": "string"},
            },
            [
                "decision",
                "rationale",
                "recall_threshold",
                "min_failed_cases",
                "recall",
                "failed_case_ids",
                "generated_at",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.provenance_status",
        "title": "Durable Provenance Status",
        "description": "Audit durable memories for reviewed provenance metadata.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "generated_at": {"type": "string"},
                "durable_count": {"type": "integer"},
                "issue_count": {"type": "integer"},
                "issues": {"type": "array", "items": {"type": "object"}},
            },
            ["generated_at", "durable_count", "issue_count", "issues"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.maintenance_status",
        "title": "Memory Maintenance Status",
        "description": "Show configured providers, schedule settings, generated artifacts, generated packet archives, recent reports, and lock state.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "schedule": {"type": "object"},
                "providers": {"type": "object"},
                "provider_readiness": {"type": "object"},
                "review_due": {"type": "object"},
                "conflict_review": {"type": "object"},
                "review_recommendations": {"type": "object"},
                "generated_packet_archives": {"type": "object"},
                "hook_captures": {"type": "object"},
                "recent_reports": {"type": "array", "items": {"type": "string"}},
                "artifacts": {"type": "object"},
                "artifact_freshness": {"type": "object"},
                "lock_exists": {"type": "boolean"},
            },
            [
                "schedule",
                "providers",
                "provider_readiness",
                "review_due",
                "conflict_review",
                "review_recommendations",
                "generated_packet_archives",
                "hook_captures",
                "recent_reports",
                "artifacts",
                "artifact_freshness",
                "lock_exists",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.import_chats",
        "title": "Import Chat Candidates",
        "description": "Import configured provider chat/session files into inbox/imports/ for review.",
        "inputSchema": object_schema(
            {
                "provider": {"type": "string", "enum": ["claude", "codex", "cursor", "windsurf"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                "dry_run": {"type": "boolean", "default": False},
            },
            ["provider"],
        ),
        "outputSchema": object_schema({"result": {"type": "object"}}, ["result"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.capture_import",
        "title": "Capture Import Candidate",
        "description": "Capture explicit text or a repository-local file into inbox/imports/ for review.",
        "inputSchema": object_schema(
            {
                "kind": {"type": "string", "enum": sorted(CAPTURE_KINDS)},
                "text": {"type": ["string", "null"]},
                "path": {"type": ["string", "null"]},
                "title": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20},
            },
            ["kind"],
        ),
        "outputSchema": object_schema({"result": {"type": "object"}}, ["result"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.git_lessons",
        "title": "Capture Git Lesson Candidates",
        "description": "Inspect local git history and preview review-first lesson candidates; dry_run=false writes into inbox/git-lessons/.",
        "inputSchema": object_schema(
            {
                "repo": {"type": ["string", "null"]},
                "repos": {"type": "array", "items": {"type": "string"}},
                "days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 7},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 50},
                "dry_run": {"type": "boolean", "default": True},
            },
        ),
        "outputSchema": object_schema({"result": {"type": "object"}}, ["result"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.maintenance_run",
        "title": "Run Memory Maintenance",
        "description": "Run an opt-in daily or weekly maintenance profile.",
        "inputSchema": object_schema(
            {
                "profile": {"type": "string", "enum": ["daily", "weekly"], "default": "daily"},
                "dry_run": {"type": "boolean", "default": False},
                "report_dir": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema({"result": {"type": "object"}}, ["result"]),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.schedule_plan",
        "title": "Plan Memory Schedule",
        "description": "Return platform scheduler commands and reviewed cron export entries without installing them.",
        "inputSchema": object_schema(
            {
                "action": {"type": "string", "enum": ["install", "status", "remove"], "default": "install"},
                "platform": {"type": "string", "enum": ["windows", "linux", "macos"]},
                "mode": {"type": "string", "enum": ["installed", "docker"], "default": "installed"},
                "image": {"type": "string", "default": "ai-dememory:local"},
            },
        ),
        "outputSchema": object_schema(
            {
                "root": {"type": "string"},
                "action": {"type": "string"},
                "platform": {"type": "string"},
                "mode": {"type": "string"},
                "image": {"type": "string"},
                "schedule": {"type": "object"},
                "commands": {"type": "array", "items": {"type": "object"}},
                "cron_entries": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "runs_commands": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "installs_schedules": {"type": "boolean"},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "root",
                "action",
                "platform",
                "mode",
                "image",
                "schedule",
                "commands",
                "cron_entries",
                "mutates_system",
                "runs_commands",
                "writes_files",
                "installs_schedules",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.schedule_status",
        "title": "Memory Schedule Status",
        "description": "Return configured schedule settings and platform status commands without querying or mutating the OS scheduler.",
        "inputSchema": object_schema(
            {
                "platform": {"type": "string", "enum": ["windows", "linux", "macos"]},
            },
        ),
        "outputSchema": object_schema(
            {
                "configured": {"type": "boolean"},
                "valid": {"type": "boolean"},
                "validation_errors": {"type": "array", "items": {"type": "string"}},
                "platform": {"type": "string"},
                "mode": {"type": "string"},
                "image": {"type": "string"},
                "schedule": {"type": "object"},
                "review_due": {"type": "object"},
                "status_commands": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
            },
            [
                "configured",
                "valid",
                "validation_errors",
                "platform",
                "mode",
                "schedule",
                "review_due",
                "status_commands",
                "mutates_system",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.schedule_environment",
        "title": "Memory Schedule Environment",
        "description": "Check local scheduler, Docker, and crontab command availability without running commands.",
        "inputSchema": object_schema(
            {
                "platform": {"type": "string", "enum": ["windows", "linux", "macos"]},
                "mode": {"type": "string", "enum": ["installed", "docker"], "default": "installed"},
            },
        ),
        "outputSchema": object_schema(
            {
                "platform": {"type": "string"},
                "mode": {"type": "string"},
                "ready": {"type": "boolean"},
                "required_missing": {"type": "array", "items": {"type": "string"}},
                "checks": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "runs_commands": {"type": "boolean"},
            },
            ["platform", "mode", "ready", "required_missing", "checks", "mutates_system", "runs_commands"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_status",
        "title": "Manual Acceptance Status",
        "description": "Return reviewed manual release acceptance evidence status.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema({"items": {"type": "array", "items": {"type": "object"}}}, ["items"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_verify",
        "title": "Verify Manual Acceptance",
        "description": "Return manual acceptance completion state without recording evidence.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema({"verification": {"type": "object"}}, ["verification"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_plan",
        "title": "Manual Acceptance Plan",
        "description": "Return remaining and blocked manual acceptance next actions without recording evidence.",
        "inputSchema": object_schema(
            {
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema({"plan": {"type": "object"}}, ["plan"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_template",
        "title": "Manual Acceptance Evidence Template",
        "description": "Return a reviewed-evidence template and record command without recording acceptance evidence.",
        "inputSchema": object_schema(
            {
                "item": {"type": "string", "enum": sorted(ACCEPTANCE_ITEMS)},
                "status": {"type": "string", "enum": ["passed", "blocked"], "default": "passed"},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
            },
            ["item"],
        ),
        "outputSchema": object_schema(
            {
                "item": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string"},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
                "suggested_artifacts": {"type": "array", "items": {"type": "string"}},
                "command": {"type": "string"},
                "markdown": {"type": "string"},
                "mutates_system": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "records_evidence": {"type": "boolean"},
            },
            [
                "item",
                "description",
                "status",
                "reviewer",
                "pr_url",
                "suggested_artifacts",
                "command",
                "markdown",
                "mutates_system",
                "writes_files",
                "records_evidence",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_packet",
        "title": "Manual Acceptance Packet",
        "description": "Render the manual acceptance review packet without writing reports or recording evidence.",
        "inputSchema": object_schema(
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema(
            {
                "complete": {"type": "boolean"},
                "total": {"type": "integer"},
                "completed_count": {"type": "integer"},
                "blocked_count": {"type": "integer"},
                "remaining_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "offset": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "reviewer": {"type": ["string", "null"]},
                "pr_url": {"type": ["string", "null"]},
                "items": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "records_evidence": {"type": "boolean"},
                "writes_acceptance_records": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "report_path": {"type": ["string", "null"]},
                "markdown": {"type": "string"},
            },
            [
                "complete",
                "total",
                "completed_count",
                "blocked_count",
                "remaining_count",
                "limit",
                "returned_count",
                "offset",
                "next_offset",
                "has_more",
                "reviewer",
                "pr_url",
                "items",
                "mutates_system",
                "records_evidence",
                "writes_acceptance_records",
                "writes_files",
                "report_path",
                "markdown",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_packet_archive_status",
        "title": "Manual Acceptance Packet Archive Status",
        "description": "List generated manual acceptance packet archives without writing files or recording evidence.",
        "inputSchema": object_schema(
            {
                "archive_dir": {"type": ["string", "null"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        ),
        "outputSchema": object_schema(
            {
                "archive_root": {"type": "string"},
                "total_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "archives": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "records_evidence": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "writes_acceptance_records": {"type": "boolean"},
            },
            [
                "archive_root",
                "total_count",
                "limit",
                "offset",
                "returned_count",
                "next_offset",
                "has_more",
                "archives",
                "mutates_system",
                "records_evidence",
                "writes_files",
                "writes_acceptance_records",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.acceptance_packet_archive_retention_plan",
        "title": "Manual Acceptance Packet Archive Retention Plan",
        "description": "Plan generated manual acceptance packet archive pruning without deleting files or recording evidence.",
        "inputSchema": object_schema(
            {
                "archive_dir": {"type": ["string", "null"]},
                "keep": {"type": "integer", "minimum": 1, "default": 30},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        ),
        "outputSchema": object_schema(
            {
                "archive_root": {"type": "string"},
                "total_count": {"type": "integer"},
                "keep": {"type": "integer"},
                "retained_count": {"type": "integer"},
                "prunable_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "prune_candidates": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "records_evidence": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "deletes_files": {"type": "boolean"},
                "writes_acceptance_records": {"type": "boolean"},
            },
            [
                "archive_root",
                "total_count",
                "keep",
                "retained_count",
                "prunable_count",
                "limit",
                "offset",
                "returned_count",
                "next_offset",
                "has_more",
                "prune_candidates",
                "mutates_system",
                "records_evidence",
                "writes_files",
                "deletes_files",
                "writes_acceptance_records",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.release_evidence",
        "title": "Release Evidence",
        "description": "Return local v2 release evidence without writing report files.",
        "inputSchema": object_schema(
            {
                "pr_url": {"type": ["string", "null"]},
                "reviewer": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema(
            {
                "available": {"type": "boolean"},
                "reason": {"type": ["string", "null"]},
                "evidence": {"type": ["object", "null"]},
            },
            ["available", "reason", "evidence"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.release_evidence_report",
        "title": "Release Evidence Report",
        "description": "Render the v2 release evidence Markdown report without writing report files.",
        "inputSchema": object_schema(
            {
                "pr_url": {"type": ["string", "null"]},
                "reviewer": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema(
            {
                "available": {"type": "boolean"},
                "reason": {"type": ["string", "null"]},
                "release_ready": {"type": ["boolean", "null"]},
                "release_blocker_count": {"type": ["integer", "null"]},
                "mutates_system": {"type": "boolean"},
                "records_evidence": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "report_path": {"type": ["string", "null"]},
                "markdown": {"type": ["string", "null"]},
            },
            [
                "available",
                "reason",
                "release_ready",
                "release_blocker_count",
                "mutates_system",
                "records_evidence",
                "writes_files",
                "report_path",
                "markdown",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.publish_plan",
        "title": "Publish Plan",
        "description": "Plan manual TestPyPI or PyPI publishing without uploading packages.",
        "inputSchema": object_schema(
            {
                "repository": {"type": "string", "enum": list(REPOSITORIES), "default": "testpypi"},
                "pr_url": {"type": ["string", "null"]},
                "command": {"type": "string", "default": "ai-dememory"},
            },
        ),
        "outputSchema": object_schema(
            {
                "root": {"type": "string"},
                "workflow": {"type": "string"},
                "repository": {"type": "string"},
                "target_environment": {"type": "string"},
                "dispatch_inputs": {"type": "object"},
                "mutates_system": {"type": "boolean"},
                "runs_commands": {"type": "boolean"},
                "runs_publish_commands": {"type": "boolean"},
                "runs_preflight_commands": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "publishes_package": {"type": "boolean"},
                "local_inspection_commands": {"type": "array", "items": {"type": "string"}},
                "requires_manual_dispatch": {"type": "boolean"},
                "requires_confirmation": {"type": "boolean"},
                "requires_pr_url": {"type": "boolean"},
                "uses_trusted_publishing": {"type": "boolean"},
                "guard_issue_count": {"type": "integer"},
                "guard_issues": {"type": "array", "items": {"type": "object"}},
                "release_evidence_available": {"type": "boolean"},
                "release_evidence_error": {"type": ["string", "null"]},
                "release_ready": {"type": "boolean"},
                "publish_ready": {"type": "boolean"},
                "release_blocker_count": {"type": "integer"},
                "release_blocker_ids": {"type": "array", "items": {"type": "string"}},
                "publish_blocker_count": {"type": "integer"},
                "publish_blocker_ids": {"type": "array", "items": {"type": "string"}},
                "publish_blockers": {"type": "array", "items": {"type": "object"}},
                "deferred_manual_acceptance_items": {"type": "array", "items": {"type": "string"}},
                "manual_acceptance_remaining_count": {"type": ["integer", "null"]},
                "recall_fixture_status": {"type": ["string", "null"]},
                "preflight_commands": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                "workflow_url": {"type": "string"},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "root",
                "workflow",
                "repository",
                "target_environment",
                "dispatch_inputs",
                "mutates_system",
                "runs_commands",
                "runs_publish_commands",
                "runs_preflight_commands",
                "writes_files",
                "publishes_package",
                "local_inspection_commands",
                "requires_manual_dispatch",
                "requires_confirmation",
                "requires_pr_url",
                "uses_trusted_publishing",
                "guard_issue_count",
                "guard_issues",
                "release_evidence_available",
                "release_evidence_error",
                "release_ready",
                "publish_ready",
                "release_blocker_count",
                "release_blocker_ids",
                "publish_blocker_count",
                "publish_blocker_ids",
                "publish_blockers",
                "deferred_manual_acceptance_items",
                "manual_acceptance_remaining_count",
                "recall_fixture_status",
                "preflight_commands",
                "workflow_url",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.roadmap_status",
        "title": "Roadmap Status",
        "description": "Return read-only implementation status for the v2 operational roadmap phases.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "root": {"type": "string"},
                "mutates_files": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "phase_count": {"type": "integer"},
                "status_counts": {"type": "object"},
                "phases": {"type": "array", "items": {"type": "object"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            ["root", "mutates_files", "writes_files", "phase_count", "status_counts", "phases", "next_actions"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.hook_events",
        "title": "Hook Events",
        "description": "Return supported local provider hook events.",
        "inputSchema": object_schema(
            {
                "provider": {"type": ["string", "null"], "enum": ["codex", "claude", None]},
            },
        ),
        "outputSchema": object_schema({"providers": {"type": "object"}}, ["providers"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.hook_config",
        "title": "Hook Config",
        "description": "Return local hook config fragments for Codex or Claude Code.",
        "inputSchema": object_schema(
            {
                "client": {"type": "string", "enum": ["codex", "claude"], "default": "codex"},
                "command": {"type": "string", "default": "ai-dememory"},
                "root": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema({"config": {"type": "object"}}, ["config"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.hook_status",
        "title": "Hook Status",
        "description": "Return managed hook instruction install status without writing files.",
        "inputSchema": object_schema(
            {
                "client": {"type": "string", "enum": ["codex", "claude", "all"], "default": "all"},
                "capture_provider": {"type": ["string", "null"], "enum": ["codex", "claude", None]},
                "capture_event": {
                    "type": ["string", "null"],
                    "enum": [
                        "Notification",
                        "PostCompact",
                        "PreCompact",
                        "SessionStart",
                        "Stop",
                        "SubagentStop",
                        "UserPromptSubmit",
                        None,
                    ],
                },
                "capture_review_status": {
                    "type": ["string", "null"],
                    "enum": ["dismissed", "pending", "rejected", "resolved", "reviewed", None],
                },
                "capture_created_from": {"type": ["string", "null"]},
                "capture_created_to": {"type": ["string", "null"]},
                "capture_review_after_from": {"type": ["string", "null"]},
                "capture_review_after_to": {"type": ["string", "null"]},
            },
        ),
        "outputSchema": object_schema(
            {
                "mutates_system": {"type": "boolean"},
                "runs_commands": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "supported_clients": {"type": "array", "items": {"type": "string"}},
                "installed_count": {"type": "integer"},
                "all_installed": {"type": "boolean"},
                "hooks": {"type": "array", "items": {"type": "object"}},
                "captures": {"type": "object"},
            },
            [
                "mutates_system",
                "runs_commands",
                "writes_files",
                "supported_clients",
                "installed_count",
                "all_installed",
                "hooks",
                "captures",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.hook_capture_review",
        "title": "Review Hook Capture",
        "description": "Record a reviewed outcome on a hook capture under inbox/session-events/ without promoting memory.",
        "inputSchema": object_schema(
            {
                "path": {"type": "string"},
                "status": {"type": "string", "enum": sorted(HOOK_CAPTURE_REVIEW_STATUSES)},
                "reviewed_by": {"type": "string"},
                "reason": {"type": "string"},
            },
            ["path", "status", "reviewed_by", "reason"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "review_status": {"type": "string"},
                "reviewed_by": {"type": "string"},
                "reviewed_at": {"type": "string"},
                "reason": {"type": "string"},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "review_status", "reviewed_by", "reviewed_at", "reason", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.providers_detect",
        "title": "Detect Memory Providers",
        "description": "Detect known local LLM provider folders for optional chat import.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema({"providers": {"type": "array", "items": {"type": "object"}}}, ["providers"]),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.providers_status",
        "title": "Provider Import Status",
        "description": "Return configured provider import readiness without reading or importing chat files.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "providers": {"type": "array", "items": {"type": "object"}},
                "configured_count": {"type": "integer"},
                "enabled_count": {"type": "integer"},
                "import_ready_count": {"type": "integer"},
                "mutates_system": {"type": "boolean"},
                "reads_provider_files": {"type": "boolean"},
                "writes_import_candidates": {"type": "boolean"},
            },
            [
                "providers",
                "configured_count",
                "enabled_count",
                "import_ready_count",
                "mutates_system",
                "reads_provider_files",
                "writes_import_candidates",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.providers_plan",
        "title": "Provider Setup Plan",
        "description": "Return reviewable provider configure/import commands without mutating config or reading provider files.",
        "inputSchema": object_schema({"command": {"type": "string", "default": "ai-dememory"}}),
        "outputSchema": object_schema(
            {
                "providers": {"type": "array", "items": {"type": "object"}},
                "mutates_system": {"type": "boolean"},
                "reads_provider_files": {"type": "boolean"},
                "writes_import_candidates": {"type": "boolean"},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            ["providers", "mutates_system", "reads_provider_files", "writes_import_candidates", "next_actions"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.setup_plan",
        "title": "Local Setup Plan",
        "description": "Return review-first vault, MCP, provider, hook, and scheduler setup commands without mutating files.",
        "inputSchema": object_schema(
            {
                "client": {"type": "string", "enum": ["codex", "claude", "generic", "all"], "default": "all"},
                "mode": {"type": "string", "enum": ["installed", "docker", "both"], "default": "installed"},
                "command": {"type": "string", "default": "ai-dememory"},
                "image": {"type": "string", "default": "ai-dememory:local"},
            },
        ),
        "outputSchema": object_schema(
            {
                "root": {"type": "string"},
                "mutates_system": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "reads_provider_files": {"type": "boolean"},
                "writes_import_candidates": {"type": "boolean"},
                "installs_schedules": {"type": "boolean"},
                "installs_hooks": {"type": "boolean"},
                "commands": {"type": "object"},
                "provider_plan": {"type": "object"},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "root",
                "mutates_system",
                "writes_files",
                "reads_provider_files",
                "writes_import_candidates",
                "installs_schedules",
                "installs_hooks",
                "commands",
                "provider_plan",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.setup_health",
        "title": "Local Setup Health",
        "description": "Return combined validation, context config, manual acceptance, recall, vector, provider, scheduler, maintenance, and review health without running commands or writing files.",
        "inputSchema": object_schema(
            {
                "platform": {"type": "string", "enum": ["windows", "linux", "macos"]},
                "mode": {"type": "string", "enum": ["installed", "docker"], "default": "installed"},
            },
        ),
        "outputSchema": object_schema(
            {
                "root": {"type": "string"},
                "platform": {"type": "string"},
                "mode": {"type": "string"},
                "ready": {"type": "boolean"},
                "mutates_system": {"type": "boolean"},
                "runs_commands": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "validation_status": {"type": "object"},
                "recall_review": {"type": "object"},
                "context_config": {"type": "object"},
                "manual_acceptance": {"type": "object"},
                "vector_readiness": {"type": "object"},
                "schedule_environment": {"type": "object"},
                "schedule_status": {"type": "object"},
                "hook_status": {"type": "object"},
                "provider_readiness": {"type": "object"},
                "maintenance_preflight": {"type": "object"},
                "artifact_freshness": {"type": "object"},
                "review_due": {"type": "object"},
                "conflict_review": {"type": "object"},
                "review_recommendations": {"type": "object"},
                "generated_packet_archives": {"type": "object"},
                "artifacts": {"type": "object"},
                "lock_exists": {"type": "boolean"},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "root",
                "platform",
                "mode",
                "ready",
                "mutates_system",
                "runs_commands",
                "writes_files",
                "validation_status",
                "recall_review",
                "context_config",
                "manual_acceptance",
                "vector_readiness",
                "schedule_environment",
                "schedule_status",
                "hook_status",
                "provider_readiness",
                "maintenance_preflight",
                "artifact_freshness",
                "review_due",
                "conflict_review",
                "review_recommendations",
                "generated_packet_archives",
                "artifacts",
                "lock_exists",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_false_positives",
        "title": "Review False Positives",
        "description": "Return secret-scan findings with deterministic review ids and suppression metadata.",
        "inputSchema": object_schema({"due_only": {"type": "boolean", "default": False}}),
        "outputSchema": object_schema(
            {
                "enabled": {"type": "boolean"},
                "policy": {"type": "object"},
                "due_only": {"type": "boolean"},
                "returned_count": {"type": "integer"},
                "findings": {"type": "array", "items": {"type": "object"}},
            },
            ["enabled", "policy", "findings", "due_only", "returned_count"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_stale_false_positives",
        "title": "Review Stale False Positives",
        "description": "Return ignored false-positive suppressions whose current scanner finding no longer exists.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "enabled": {"type": "boolean"},
                "policy": {"type": "object"},
                "stale_count": {"type": "integer"},
                "items": {"type": "array", "items": {"type": "object"}},
            },
            ["enabled", "policy", "stale_count", "items"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.false_positive_ignore",
        "title": "Ignore False Positive",
        "description": "Record a reviewed secret-scan false-positive suppression in .ai-dememory-ignore.toml.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "reason": {"type": "string"},
                "reviewer": {"type": "string"},
                "review_after_days": {"type": ["integer", "null"], "minimum": 1},
                "recommendation_id": {"type": ["string", "null"]},
            },
            ["id", "reason", "reviewer"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "id": {"type": "string"},
                "ignored": {"type": "boolean"},
                "reviewer": {"type": ["string", "null"]},
                "reviewed_at": {"type": ["string", "null"]},
                "review_after": {"type": ["string", "null"]},
                "review_due": {"type": "boolean"},
                "review_after_status": {"type": "string"},
                "recommendation_id": {"type": ["string", "null"]},
                "recommendation_path": {"type": ["string", "null"]},
                "recommendation_action": {"type": ["string", "null"]},
                "recommendation_policy_violation": {"type": ["boolean", "null"]},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "id", "ignored", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.false_positive_unignore",
        "title": "Unignore False Positive",
        "description": "Record a reviewed false-positive unsuppression in .ai-dememory-ignore.toml.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "reviewer": {"type": "string"},
                "recommendation_id": {"type": ["string", "null"]},
            },
            ["id", "reviewer"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "id": {"type": "string"},
                "ignored": {"type": "boolean"},
                "reviewer": {"type": ["string", "null"]},
                "reviewed_at": {"type": ["string", "null"]},
                "review_after": {"type": ["string", "null"]},
                "review_due": {"type": "boolean"},
                "review_after_status": {"type": "string"},
                "recommendation_id": {"type": ["string", "null"]},
                "recommendation_path": {"type": ["string", "null"]},
                "recommendation_action": {"type": ["string", "null"]},
                "recommendation_policy_violation": {"type": ["boolean", "null"]},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "id", "ignored", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_conflicts",
        "title": "Review Memory Conflicts",
        "description": "Return duplicate, preference, project decision, and restricted memory conflict candidates.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "enabled": {"type": "boolean"},
                "policy": {"type": "object"},
                "conflicts": {"type": "array", "items": {"type": "object"}},
            },
            ["enabled", "policy", "conflicts"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.conflict_dismiss",
        "title": "Dismiss Memory Conflict",
        "description": "Record that a conflict candidate was reviewed and intentionally dismissed.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "reason": {"type": "string"},
                "reviewer": {"type": "string"},
                "recommendation_id": {"type": ["string", "null"]},
            },
            ["id", "reason", "reviewer"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "id": {"type": "string"},
                "status": {"type": "string"},
                "decision": {"type": "string"},
                "reviewer": {"type": ["string", "null"]},
                "reviewed_at": {"type": ["string", "null"]},
                "recommendation_id": {"type": ["string", "null"]},
                "recommendation_path": {"type": ["string", "null"]},
                "recommendation_action": {"type": ["string", "null"]},
                "recommendation_policy_violation": {"type": ["boolean", "null"]},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "id", "status", "decision", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.conflict_merge_proposal",
        "title": "Write Conflict Merge Proposal",
        "description": "Write a conflict merge proposal under inbox/conflict-resolution/ and audit the decision.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "reviewer": {"type": "string"},
                "recommendation_id": {"type": ["string", "null"]},
            },
            ["id", "reviewer"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "id": {"type": "string"},
                "status": {"type": "string"},
                "decision": {"type": "string"},
                "reviewer": {"type": ["string", "null"]},
                "reviewed_at": {"type": ["string", "null"]},
                "proposal_path": {"type": ["string", "null"]},
                "recommendation_id": {"type": ["string", "null"]},
                "recommendation_path": {"type": ["string", "null"]},
                "recommendation_action": {"type": ["string", "null"]},
                "recommendation_policy_violation": {"type": ["boolean", "null"]},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "id", "status", "decision", "proposal_path", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.conflict_keep",
        "title": "Resolve Conflict Keep Memory",
        "description": "Record a reviewed keep decision for a conflict without editing canonical memory.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "keep": {"type": "string"},
                "reviewer": {"type": "string"},
                "recommendation_id": {"type": ["string", "null"]},
            },
            ["id", "keep", "reviewer"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "id": {"type": "string"},
                "keep": {"type": "string"},
                "status": {"type": "string"},
                "decision": {"type": "string"},
                "reviewer": {"type": ["string", "null"]},
                "reviewed_at": {"type": ["string", "null"]},
                "recommendation_id": {"type": ["string", "null"]},
                "recommendation_path": {"type": ["string", "null"]},
                "recommendation_action": {"type": ["string", "null"]},
                "recommendation_policy_violation": {"type": ["boolean", "null"]},
                "canonical_memory_updated": {"type": "boolean"},
            },
            ["path", "id", "keep", "status", "decision", "reviewer", "reviewed_at", "canonical_memory_updated"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_modes",
        "title": "Review Modes",
        "description": "Return built-in review modes and the active configured mode.",
        "inputSchema": object_schema(),
        "outputSchema": object_schema(
            {
                "active": {"type": "string"},
                "policy": {"type": "object"},
                "modes": {"type": "array", "items": {"type": "object"}},
            },
            ["active", "policy", "modes"],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_configure_mode",
        "title": "Configure Review Mode",
        "description": "Persist the active review mode in .ai-dememory.toml without editing canonical memory.",
        "inputSchema": object_schema(
            {
                "mode": {"type": "string", "enum": sorted(set(REVIEW_MODES) | set(REVIEW_MODE_ALIASES))},
                "reviewer": {"type": ["string", "null"]},
            },
            ["mode"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "requested_mode": {"type": "string"},
                "active": {"type": "string"},
                "reviewer": {"type": ["string", "null"]},
                "require_human_for_durable": {"type": "boolean"},
                "allow_llm_false_positive_triage": {"type": "boolean"},
                "allow_llm_conflict_recommendations": {"type": "boolean"},
                "allow_llm_merge_proposals": {"type": "boolean"},
                "allow_autonomous_inbox_proposals": {"type": "boolean"},
                "allow_apply_reviewed": {"type": "boolean"},
                "canonical_memory_updated": {"type": "boolean"},
            },
            [
                "path",
                "requested_mode",
                "active",
                "require_human_for_durable",
                "allow_llm_false_positive_triage",
                "allow_llm_conflict_recommendations",
                "allow_llm_merge_proposals",
                "allow_autonomous_inbox_proposals",
                "allow_apply_reviewed",
                "canonical_memory_updated",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_plan",
        "title": "Review Plan",
        "description": "Return mode-specific LLM, human, and validation steps for a review kind.",
        "inputSchema": object_schema(
            {
                "kind": {
                    "type": "string",
                    "enum": ["conflict", "false-positive", "inbox", "maintenance", "promotion"],
                    "default": "inbox",
                },
            },
        ),
        "outputSchema": object_schema(
            {
                "kind": {"type": "string"},
                "mode": {"type": "string"},
                "summary": {"type": "string"},
                "policy": {"type": "object"},
                "allowed_llm_actions": {"type": "array", "items": {"type": "string"}},
                "required_human_actions": {"type": "array", "items": {"type": "string"}},
                "required_checks": {"type": "array", "items": {"type": "string"}},
                "forbidden_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "kind",
                "mode",
                "summary",
                "policy",
                "allowed_llm_actions",
                "required_human_actions",
                "required_checks",
                "forbidden_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_recommendation",
        "title": "Store Review Recommendation",
        "description": "Store an advisory LLM/client review recommendation under inbox/review-recommendations/ without applying it.",
        "inputSchema": object_schema(
            {
                "kind": {
                    "type": "string",
                    "enum": ["conflict", "false-positive", "inbox", "maintenance", "promotion"],
                },
                "target_id": {"type": "string"},
                "recommendation": {"type": "string", "enum": sorted(REVIEW_RECOMMENDATION_ACTIONS)},
                "rationale": {"type": "string"},
                "recommended_by": {"type": "string"},
                "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            ["kind", "target_id", "recommendation", "rationale", "recommended_by"],
        ),
        "outputSchema": object_schema(
            {
                "id": {"type": "string"},
                "path": {"type": "string"},
                "kind": {"type": "string"},
                "target_id": {"type": "string"},
                "recommendation": {"type": "string"},
                "confidence": {"type": ["number", "null"]},
                "recommended_by": {"type": "string"},
                "mode": {"type": "string"},
                "allowed_by_mode": {"type": "boolean"},
                "policy_violation": {"type": "boolean"},
                "requires_human_approval": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "applies_review_decision": {"type": "boolean"},
                "writes_canonical_memory": {"type": "boolean"},
                "created_at": {"type": "string"},
            },
            [
                "id",
                "path",
                "kind",
                "target_id",
                "recommendation",
                "recommended_by",
                "mode",
                "allowed_by_mode",
                "policy_violation",
                "requires_human_approval",
                "writes_files",
                "applies_review_decision",
                "writes_canonical_memory",
                "created_at",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_recommendations",
        "title": "List Review Recommendations",
        "description": "List advisory review recommendation artifacts without applying review outcomes.",
        "inputSchema": object_schema(
            {
                "kind": {
                    "type": ["string", "null"],
                    "enum": ["conflict", "false-positive", "inbox", "maintenance", "promotion", None],
                },
                "outcome_status": {
                    "type": ["string", "null"],
                    "enum": ["accepted", "pending", "rejected", None],
                },
                "policy_violations_only": {"type": "boolean", "default": False},
            },
        ),
        "outputSchema": object_schema(
            {
                "enabled": {"type": "boolean"},
                "mutates_system": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "applies_review_decisions": {"type": "boolean"},
                "writes_canonical_memory": {"type": "boolean"},
                "recommendation_dir": {"type": "string"},
                "filters": {"type": "object"},
                "total_count": {"type": "integer"},
                "invalid_count": {"type": "integer"},
                "policy_violation_count": {"type": "integer"},
                "allowed_count": {"type": "integer"},
                "requires_human_approval_count": {"type": "integer"},
                "pending_count": {"type": "integer"},
                "accepted_count": {"type": "integer"},
                "rejected_count": {"type": "integer"},
                "latest_created_at": {"type": ["string", "null"]},
                "recommendations": {"type": "array", "items": {"type": "object"}},
                "invalid": {"type": "array", "items": {"type": "object"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "enabled",
                "mutates_system",
                "writes_files",
                "applies_review_decisions",
                "writes_canonical_memory",
                "recommendation_dir",
                "filters",
                "total_count",
                "invalid_count",
                "policy_violation_count",
                "allowed_count",
                "requires_human_approval_count",
                "pending_count",
                "accepted_count",
                "rejected_count",
                "recommendations",
                "invalid",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_recommendation_archive_status",
        "title": "Archived Review Recommendation Status",
        "description": "List archived accepted/rejected advisory recommendation artifacts without moving files.",
        "inputSchema": object_schema(
            {
                "archive_root": {"type": "string", "default": "archive/review-recommendations"},
                "kind": {
                    "type": ["string", "null"],
                    "enum": ["conflict", "false-positive", "inbox", "maintenance", "promotion", None],
                },
                "outcome_status": {
                    "type": ["string", "null"],
                    "enum": ["accepted", "rejected", None],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "invalid_offset": {"type": "integer", "minimum": 0, "default": 0},
                "recursive": {"type": "boolean", "default": False},
            },
        ),
        "outputSchema": object_schema(
            {
                "enabled": {"type": "boolean"},
                "mutates_system": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "applies_review_decisions": {"type": "boolean"},
                "writes_canonical_memory": {"type": "boolean"},
                "archive_root": {"type": "string"},
                "filters": {"type": "object"},
                "total_count": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "offset": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "invalid_count": {"type": "integer"},
                "invalid_returned_count": {"type": "integer"},
                "invalid_offset": {"type": "integer"},
                "invalid_next_offset": {"type": ["integer", "null"]},
                "invalid_has_more": {"type": "boolean"},
                "accepted_count": {"type": "integer"},
                "rejected_count": {"type": "integer"},
                "status_counts": {"type": "object"},
                "kind_counts": {"type": "object"},
                "recommendations": {"type": "array", "items": {"type": "object"}},
                "invalid": {"type": "array", "items": {"type": "object"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            [
                "enabled",
                "mutates_system",
                "writes_files",
                "applies_review_decisions",
                "writes_canonical_memory",
                "archive_root",
                "filters",
                "total_count",
                "returned_count",
                "offset",
                "next_offset",
                "has_more",
                "invalid_count",
                "invalid_returned_count",
                "invalid_offset",
                "invalid_next_offset",
                "invalid_has_more",
                "accepted_count",
                "rejected_count",
                "status_counts",
                "kind_counts",
                "recommendations",
                "invalid",
                "next_actions",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_recommendation_archive_restore_preview",
        "title": "Preview Review Recommendation Archive Restore",
        "description": "Preview restoring one archived advisory recommendation artifact to the active inbox without moving files.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "archive_root": {"type": "string", "default": "archive/review-recommendations"},
                "recursive": {"type": "boolean", "default": False},
            },
            ["id"],
        ),
        "outputSchema": object_schema(
            {
                "dry_run": {"type": "boolean"},
                "archive_root": {"type": "string"},
                "inbox_root": {"type": "string"},
                "requested_id": {"type": "string"},
                "recursive": {"type": "boolean"},
                "restored_count": {"type": "integer"},
                "skipped_count": {"type": "integer"},
                "candidates": {"type": "array", "items": {"type": "object"}},
                "restored": {"type": "array", "items": {"type": "object"}},
                "skipped": {"type": "array", "items": {"type": "object"}},
                "malformed_count": {"type": "integer"},
                "malformed": {"type": "array", "items": {"type": "object"}},
                "writes_files": {"type": "boolean"},
                "applies_review_decisions": {"type": "boolean"},
                "writes_canonical_memory": {"type": "boolean"},
                "canonical_memory_updated": {"type": "boolean"},
            },
            [
                "dry_run",
                "archive_root",
                "inbox_root",
                "requested_id",
                "recursive",
                "restored_count",
                "skipped_count",
                "candidates",
                "restored",
                "skipped",
                "malformed_count",
                "malformed",
                "writes_files",
                "applies_review_decisions",
                "writes_canonical_memory",
                "canonical_memory_updated",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_recommendation_outcome_report",
        "title": "Review Recommendation Outcome Report",
        "description": "Render the reviewed recommendation outcome sign-off report without writing files.",
        "inputSchema": object_schema(
            {
                "kind": {
                    "type": ["string", "null"],
                    "enum": ["conflict", "false-positive", "inbox", "maintenance", "promotion", None],
                },
                "outcome_status": {
                    "type": "string",
                    "enum": ["reviewed", "accepted", "rejected"],
                    "default": "reviewed",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TOOL_LIMIT, "default": 50},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "invalid_offset": {"type": "integer", "minimum": 0, "default": 0},
            },
        ),
        "outputSchema": object_schema(
            {
                "enabled": {"type": "boolean"},
                "mutates_system": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "applies_review_decisions": {"type": "boolean"},
                "writes_canonical_memory": {"type": "boolean"},
                "filters": {"type": "object"},
                "total_count": {"type": "integer"},
                "returned_count": {"type": "integer"},
                "offset": {"type": "integer"},
                "next_offset": {"type": ["integer", "null"]},
                "has_more": {"type": "boolean"},
                "accepted_count": {"type": "integer"},
                "rejected_count": {"type": "integer"},
                "status_counts": {"type": "object"},
                "invalid_count": {"type": "integer"},
                "invalid_returned_count": {"type": "integer"},
                "invalid_offset": {"type": "integer"},
                "invalid_next_offset": {"type": ["integer", "null"]},
                "invalid_has_more": {"type": "boolean"},
                "recommendations": {"type": "array", "items": {"type": "object"}},
                "invalid": {"type": "array", "items": {"type": "object"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
                "report_path": {"type": ["string", "null"]},
                "markdown": {"type": "string"},
            },
            [
                "enabled",
                "mutates_system",
                "writes_files",
                "applies_review_decisions",
                "writes_canonical_memory",
                "filters",
                "total_count",
                "returned_count",
                "offset",
                "next_offset",
                "has_more",
                "accepted_count",
                "rejected_count",
                "status_counts",
                "invalid_count",
                "invalid_returned_count",
                "invalid_offset",
                "invalid_next_offset",
                "invalid_has_more",
                "recommendations",
                "invalid",
                "next_actions",
                "report_path",
                "markdown",
            ],
        ),
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
    {
        "name": "memory.review_recommendation_outcome",
        "title": "Record Review Recommendation Outcome",
        "description": "Record accepted/rejected status on an advisory review recommendation artifact without applying it.",
        "inputSchema": object_schema(
            {
                "id": {"type": "string"},
                "status": {"type": "string", "enum": ["accepted", "rejected"]},
                "reviewer": {"type": "string"},
                "reason": {"type": "string"},
            },
            ["id", "status", "reviewer", "reason"],
        ),
        "outputSchema": object_schema(
            {
                "path": {"type": "string"},
                "id": {"type": "string"},
                "outcome_status": {"type": "string"},
                "outcome_reviewed_by": {"type": "string"},
                "outcome_reviewed_at": {"type": "string"},
                "outcome_reason": {"type": "string"},
                "outcome_applies_review_decision": {"type": "boolean"},
                "outcome_writes_canonical_memory": {"type": "boolean"},
                "writes_files": {"type": "boolean"},
                "writes_canonical_memory": {"type": "boolean"},
                "applies_review_decision": {"type": "boolean"},
                "recommendation": {"type": "object"},
            },
            [
                "path",
                "id",
                "outcome_status",
                "outcome_reviewed_by",
                "outcome_reviewed_at",
                "outcome_reason",
                "outcome_applies_review_decision",
                "outcome_writes_canonical_memory",
                "writes_files",
                "writes_canonical_memory",
                "applies_review_decision",
                "recommendation",
            ],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        "execution": {"taskSupport": "forbidden"},
    },
]

PROMPTS: list[dict[str, Any]] = [
    {
        "name": "memory_recall_context",
        "title": "Recall Memory Context",
        "description": "Prepare a memory search request and instructions for using retrieved context.",
        "arguments": [
            {"name": "query", "description": "Topic, project, or decision to recall.", "required": True},
            {"name": "limit", "description": "Maximum result count.", "required": False},
        ],
    },
    {
        "name": "memory_capture_proposal",
        "title": "Capture Memory Proposal",
        "description": "Prepare a reviewed inbox capture proposal without modifying durable memory.",
        "arguments": [
            {"name": "title", "description": "Short proposal title.", "required": True},
            {"name": "content", "description": "Memory candidate content.", "required": True},
            {"name": "project", "description": "Optional project slug.", "required": False},
        ],
    },
    {
        "name": "memory_review_inbox",
        "title": "Review Memory Inbox",
        "description": "Guide a human review of proposed memory captures.",
        "arguments": [],
    },
]


def paginate(items: list[dict[str, Any]], cursor: Any = None, page_size: int = DEFAULT_PAGE_SIZE) -> tuple[list[dict[str, Any]], str | None]:
    try:
        offset = int(cursor or 0)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)
    page = items[offset : offset + page_size]
    next_offset = offset + page_size
    next_cursor = str(next_offset) if next_offset < len(items) else None
    return page, next_cursor


def false_positive_review_state_receipt(root: Path, path: Path, fp_id: str, reviewer: str, recommendation_id: Any) -> dict[str, Any]:
    metadata = load_review_config(root).get(f"false_positives.{fp_id}", {})
    ignored = metadata.get("ignored") is True
    review_after = string_or_none(metadata.get("review_after"))
    review_due, review_after_status = review_after_state(ignored, review_after)
    return {
        "path": repo_relative_path(path, root),
        "id": fp_id,
        "ignored": ignored,
        "reviewer": string_or_none(metadata.get("reviewer")) or reviewer,
        "reviewed_at": string_or_none(metadata.get("reviewed_at")),
        "review_after": review_after,
        "review_due": review_due,
        "review_after_status": review_after_status,
        "recommendation_id": string_or_none(metadata.get("recommendation_id")) or recommendation_id,
        "recommendation_path": string_or_none(metadata.get("recommendation_path")),
        "recommendation_action": string_or_none(metadata.get("recommendation_action")),
        "recommendation_policy_violation": optional_bool(metadata.get("recommendation_policy_violation")),
        "canonical_memory_updated": False,
    }


def call_tool(name: str, arguments: dict[str, Any] | None = None, root: Path | None = None) -> Any:
    arguments = arguments or {}
    root = root or REPO_ROOT

    if name == "memory.doctor":
        check_rows = run_doctor_checks(root)
        checks = [asdict(check) for check in check_rows]
        return {"checks": checks, "profile": doctor_profile(root), "summary": summarize_checks(check_rows)}

    if name == "memory.validate_status":
        return validate_repo_result(root)

    if name == "memory.search":
        results = search(
            str(arguments["query"]),
            root,
            limit=normalize_limit(arguments.get("limit", 10)),
            include_sensitive=bool(arguments.get("include_sensitive", False)),
        )
        return [result_to_dict(result) for result in results]

    if name == "memory.get":
        return get_memory(
            root,
            arguments.get("id"),
            arguments.get("path"),
            include_sensitive=bool(arguments.get("include_sensitive", False)),
        )

    if name == "memory.context":
        defaults = context_defaults(root)
        include_working_memory = (
            defaults.include_working_memory
            if arguments.get("include_working_memory") is None
            else bool(arguments.get("include_working_memory"))
        )
        explain_results = (
            defaults.explain_results
            if arguments.get("explain_results") is None
            else bool(arguments.get("explain_results"))
        )
        query, query_source = resolve_context_query(
            root,
            str(arguments.get("query") or ""),
            auto=bool(arguments.get("auto", False)),
        )
        return assemble_context(
            root,
            query,
            normalize_int(arguments.get("budget_tokens"), 200, 20000, defaults.budget_tokens),
            limit=normalize_limit(arguments.get("limit", 20), default=20),
            include_sensitive=bool(arguments.get("include_sensitive", False)),
            include_working_memory=include_working_memory,
            explain_results=explain_results,
            query_source=query_source,
        )

    if name == "memory.write_proposal":
        return write_proposal(
            root,
            title=str(arguments["title"]),
            content=str(arguments["content"]),
            project=arguments.get("project"),
            tags=arguments.get("tags") or [],
            source_kind=str(arguments.get("source_kind") or "codex"),
            source_ref=arguments.get("source_ref"),
        )

    if name == "memory.mark_seen":
        return mark_seen(
            root,
            query=str(arguments["query"]),
            selected_memory_id=arguments.get("selected_memory_id"),
            score=arguments.get("score"),
            used_by=arguments.get("used_by"),
        )

    if name == "memory.outcome":
        memory_id = None if arguments.get("last") else arguments.get("id")
        return record_outcome(root, memory_id, str(arguments["outcome"]), note=arguments.get("note"))

    if name == "memory.lifecycle_scores":
        return {"scores": [asdict(item) for item in lifecycle_scores(root)]}

    if name == "memory.sleep_plan":
        return asdict(build_sleep_plan(root))

    if name == "memory.sleep_apply_reviewed":
        ids = arguments.get("ids")
        if ids is not None and (not isinstance(ids, list) or not all(isinstance(item, str) for item in ids)):
            raise ValueError("ids must be an array of candidate id strings")
        if not arguments.get("all") and not ids:
            raise ValueError("memory.sleep_apply_reviewed requires all=true or ids")
        written = apply_review_packets(root, None if arguments.get("all") else ids)
        return {"written": [repo_relative_path(path, root) for path in written]}

    if name == "memory.working_current":
        text = show_current(root)
        try:
            current = json.loads(text)
        except json.JSONDecodeError:
            current = {}
        return {"current": current, "exists": bool(current)}

    if name == "memory.working_status":
        return working_status(root, limit=normalize_int(arguments.get("limit"), 1, 20, 5))

    if name == "memory.working_snapshot":
        path = write_working_snapshot(
            root,
            working_text_arg(arguments.get("title"), "title"),
            working_text_arg(arguments.get("notes"), "notes"),
            task=working_optional_text_arg(arguments.get("task"), "task"),
        )
        return {"path": repo_relative_path(path, root)}

    if name == "memory.working_handoff":
        path = write_working_handoff(
            root,
            working_text_arg(arguments.get("title"), "title"),
            working_text_arg(arguments.get("notes"), "notes"),
        )
        return {"path": repo_relative_path(path, root)}

    if name == "memory.reindex":
        path, count = rebuild_index(root)
        return {"path": repo_relative_path(path, root), "count": count}

    if name == "memory.consolidate":
        if arguments.get("dry_run", True) is not True:
            raise ValueError("memory.consolidate only supports dry_run=true")
        return {"report": build_report(root)}

    if name == "memory.secret_scan":
        paths = validate_scan_paths(root, arguments.get("paths"))
        findings = scan_paths(root, paths)
        return {"findings": [finding.__dict__ for finding in findings]}

    if name == "memory.graph":
        return build_graph(root, include_sensitive=bool(arguments.get("include_sensitive", False)))

    if name == "memory.capture_miss":
        path = capture_miss(
            root,
            str(arguments["query"]),
            str(arguments["reason"]),
            expected_id=arguments.get("expected_id"),
            expected_path=arguments.get("expected_path"),
        )
        return {"path": repo_relative_path(path, root)}

    if name == "memory.recall_fixture_status":
        return asdict(
            recall_fixture_freshness(
                root,
                max_age_days=normalize_int(arguments.get("max_age_days"), 1, 365, 14),
            )
        )

    if name == "memory.recall_miss_candidate":
        return asdict(
            recall_miss_candidate(
                root,
                str(arguments["query"]),
                expected_id=arguments.get("expected_id"),
                expected_path=arguments.get("expected_path"),
                min_rank=normalize_int(arguments.get("min_rank"), 1, 100, 5),
                limit=normalize_int(arguments.get("limit"), 1, 100, 10),
                include_sensitive=bool(arguments.get("include_sensitive", False)),
            )
        )

    if name == "memory.recall_review_plan":
        plan = recall_fixture_review_plan(
            root,
            max_age_days=normalize_int(arguments.get("max_age_days"), 1, 365, 14),
            resolved_limit=normalize_int(arguments.get("resolved_limit"), 0, 50, 5),
        )
        plan = paginate_recall_review_plan(
            plan,
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            pending_offset=int(arguments.get("pending_offset", 0)),
            invalid_offset=int(arguments.get("invalid_offset", 0)),
        )
        return asdict(plan)

    if name == "memory.recall_review_packet":
        plan = recall_fixture_review_plan(
            root,
            max_age_days=normalize_int(arguments.get("max_age_days"), 1, 365, 14),
            resolved_limit=normalize_int(arguments.get("resolved_limit"), 0, 50, 5),
        )
        plan = paginate_recall_review_plan(
            plan,
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            pending_offset=int(arguments.get("pending_offset", 0)),
            invalid_offset=int(arguments.get("invalid_offset", 0)),
        )
        reviewer = arguments.get("reviewer")
        pr_url = arguments.get("pr_url")
        if reviewer is not None and not isinstance(reviewer, str):
            raise ValueError("memory.recall_review_packet reviewer must be a string or null")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.recall_review_packet pr_url must be a string or null")
        plan = annotate_recall_review_packet_plan(plan, reviewer=reviewer, pr_url=pr_url)
        markdown = render_recall_review_packet(plan)
        if scan_text(markdown, "<recall-review-packet-mcp>"):
            raise ValueError("recall review packet rejected by secret scan")
        return {
            "fixtures_path": plan.fixtures_path,
            "status": plan.status,
            "stale": plan.stale,
            "pending_count": plan.pending_count,
            "invalid_count": plan.invalid_count,
            "resolved_count": plan.resolved_count,
            "limit": plan.limit,
            "pending_returned_count": plan.pending_returned_count,
            "pending_offset": plan.pending_offset,
            "pending_next_offset": plan.pending_next_offset,
            "pending_has_more": plan.pending_has_more,
            "invalid_returned_count": plan.invalid_returned_count,
            "invalid_offset": plan.invalid_offset,
            "invalid_next_offset": plan.invalid_next_offset,
            "invalid_has_more": plan.invalid_has_more,
            "reviewer": plan.reviewer,
            "pr_url": plan.pr_url,
            "pending_misses": [asdict(item) for item in plan.pending_misses],
            "invalid_misses": [asdict(item) for item in plan.invalid_misses],
            "mutates_system": False,
            "records_fixture_promotions": False,
            "writes_fixture_file": False,
            "closes_miss_files": False,
            "writes_files": False,
            "report_path": None,
            "markdown": markdown,
        }

    if name == "memory.recall_review_packet_archive_status":
        archive_dir = arguments.get("archive_dir")
        if archive_dir is not None and not isinstance(archive_dir, str):
            raise ValueError("memory.recall_review_packet_archive_status archive_dir must be a string or null")
        return recall_review_packet_archive_status(
            root,
            archive_dir=archive_dir or "reports/recall-review-packets",
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            offset=int(arguments.get("offset", 0)),
        )

    if name == "memory.recall_review_packet_archive_retention_plan":
        archive_dir = arguments.get("archive_dir")
        if archive_dir is not None and not isinstance(archive_dir, str):
            raise ValueError("memory.recall_review_packet_archive_retention_plan archive_dir must be a string or null")
        return recall_review_packet_archive_retention_plan(
            root,
            archive_dir=archive_dir or "reports/recall-review-packets",
            keep=normalize_int(arguments.get("keep"), 1, 10000, 30),
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            offset=int(arguments.get("offset", 0)),
        )

    if name == "memory.recall_miss_review":
        return asdict(
            review_recall_miss(
                root,
                str(arguments["miss"]),
                str(arguments["status"]),
                str(arguments["reviewer"]),
                str(arguments["reason"]),
            )
        )

    if name == "memory.vector_status":
        return asdict(
            evaluate_vector_readiness(
                root,
                recall_threshold=normalize_float(
                    arguments.get("recall_threshold"),
                    0.0,
                    1.0,
                    DEFAULT_RECALL_THRESHOLD,
                ),
                min_failed_cases=normalize_int(
                    arguments.get("min_failed_cases"),
                    1,
                    100,
                    DEFAULT_MIN_FAILED_CASES,
                ),
            )
        )

    if name == "memory.provenance_status":
        return asdict(audit_durable_provenance(root))

    if name == "memory.maintenance_status":
        return maintenance_status(root)

    if name == "memory.import_chats":
        return {
            "result": import_chats(
                root,
                str(arguments["provider"]),
                limit=normalize_limit(arguments.get("limit", 20), default=20),
                dry_run=bool(arguments.get("dry_run", False)),
            )
        }

    if name == "memory.capture_import":
        text = arguments.get("text")
        relpath = arguments.get("path")
        if not text and not relpath:
            raise ValueError("memory.capture_import requires text or path")
        if text and relpath:
            raise ValueError("memory.capture_import accepts text or path, not both")
        source_path = validate_capture_path(root, str(relpath)) if relpath else None
        return {
            "result": capture_source(
                root,
                str(arguments["kind"]),
                source_path=source_path,
                text=str(text) if text is not None else None,
                title=arguments.get("title"),
                limit=normalize_int(arguments.get("limit", 20), 1, 20, 20),
            )
        }

    if name == "memory.git_lessons":
        return {
            "result": learn_git(
                root,
                normalize_git_lesson_repos(arguments.get("repo"), arguments.get("repos"), root),
                days=normalize_int(arguments.get("days"), 1, 365, 7),
                limit=normalize_int(arguments.get("limit"), 1, 50, 50),
                dry_run=bool(arguments.get("dry_run", True)),
            )
        }

    if name == "memory.maintenance_run":
        report_dir = Path(str(arguments.get("report_dir") or "reports/maintenance"))
        if bool(arguments.get("dry_run", False)):
            return {
                "result": dry_run_maintenance(
                    root,
                    str(arguments.get("profile") or "daily"),
                    report_dir=report_dir,
                )
            }
        result = run_maintenance(root, str(arguments.get("profile") or "daily"), report_dir=report_dir)
        return {"result": result.__dict__}

    if name == "memory.schedule_plan":
        return schedule_plan(
            root,
            action=str(arguments.get("action") or "install"),
            target_platform=arguments.get("platform"),
            mode=str(arguments.get("mode") or "installed"),
            image=str(arguments.get("image") or "ai-dememory:local"),
        )

    if name == "memory.schedule_status":
        return schedule_status(root, target_platform=arguments.get("platform"))

    if name == "memory.schedule_environment":
        return schedule_environment(
            target_platform=arguments.get("platform"),
            mode=str(arguments.get("mode") or "installed"),
        )

    if name == "memory.acceptance_status":
        return {"items": status_to_dict(acceptance_status(root))}

    if name == "memory.acceptance_verify":
        return {"verification": asdict(verify_acceptance(acceptance_status(root)))}

    if name == "memory.acceptance_plan":
        reviewer = arguments.get("reviewer")
        pr_url = arguments.get("pr_url")
        if reviewer is not None and not isinstance(reviewer, str):
            raise ValueError("memory.acceptance_plan reviewer must be a string or null")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.acceptance_plan pr_url must be a string or null")
        return {"plan": asdict(acceptance_plan(root, reviewer=reviewer, pr_url=pr_url))}

    if name == "memory.acceptance_template":
        reviewer = arguments.get("reviewer")
        pr_url = arguments.get("pr_url")
        if reviewer is not None and not isinstance(reviewer, str):
            raise ValueError("memory.acceptance_template reviewer must be a string or null")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.acceptance_template pr_url must be a string or null")
        return asdict(
            acceptance_template(
                str(arguments["item"]),
                status=str(arguments.get("status") or "passed"),
                reviewer=reviewer,
                pr_url=pr_url,
            )
        )

    if name == "memory.acceptance_packet":
        plan = paginate_acceptance_packet_plan(
            acceptance_plan(root),
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            offset=int(arguments.get("offset", 0)),
        )
        reviewer = arguments.get("reviewer")
        pr_url = arguments.get("pr_url")
        if reviewer is not None and not isinstance(reviewer, str):
            raise ValueError("memory.acceptance_packet reviewer must be a string or null")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.acceptance_packet pr_url must be a string or null")
        plan = annotate_acceptance_packet_plan(plan, reviewer=reviewer, pr_url=pr_url)
        markdown = render_acceptance_packet_report(plan)
        if scan_text(markdown, "<manual-acceptance-packet-mcp>"):
            raise ValueError("acceptance packet rejected by secret scan")
        return {
            "complete": plan.complete,
            "total": plan.total,
            "completed_count": plan.completed_count,
            "blocked_count": plan.blocked_count,
            "remaining_count": plan.remaining_count,
            "limit": plan.limit,
            "returned_count": plan.returned_count,
            "offset": plan.offset,
            "next_offset": plan.next_offset,
            "has_more": plan.has_more,
            "reviewer": plan.reviewer,
            "pr_url": plan.pr_url,
            "items": [asdict(item) for item in plan.items if not item.completed],
            "mutates_system": False,
            "records_evidence": False,
            "writes_acceptance_records": False,
            "writes_files": False,
            "report_path": None,
            "markdown": markdown,
        }

    if name == "memory.acceptance_packet_archive_status":
        archive_dir = arguments.get("archive_dir")
        if archive_dir is not None and not isinstance(archive_dir, str):
            raise ValueError("memory.acceptance_packet_archive_status archive_dir must be a string or null")
        return acceptance_packet_archive_status(
            root,
            archive_dir=archive_dir or "reports/manual-acceptance-packets",
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            offset=int(arguments.get("offset", 0)),
        )

    if name == "memory.acceptance_packet_archive_retention_plan":
        archive_dir = arguments.get("archive_dir")
        if archive_dir is not None and not isinstance(archive_dir, str):
            raise ValueError("memory.acceptance_packet_archive_retention_plan archive_dir must be a string or null")
        return acceptance_packet_archive_retention_plan(
            root,
            archive_dir=archive_dir or "reports/manual-acceptance-packets",
            keep=normalize_int(arguments.get("keep"), 1, 10000, 30),
            limit=normalize_limit(arguments.get("limit", 50), default=50),
            offset=int(arguments.get("offset", 0)),
        )

    if name == "memory.release_evidence":
        pr_url = arguments.get("pr_url")
        reviewer = arguments.get("reviewer")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.release_evidence pr_url must be a string or null")
        if reviewer is not None and not isinstance(reviewer, str):
            raise ValueError("memory.release_evidence reviewer must be a string or null")
        if not is_distribution_checkout(root):
            return {
                "available": False,
                "reason": "release evidence requires a git distribution checkout",
                "evidence": None,
            }
        evidence = build_release_evidence(root, pr_url=pr_url or None, reviewer=reviewer or None)
        return {"available": True, "reason": None, "evidence": evidence_to_dict(evidence)}

    if name == "memory.release_evidence_report":
        pr_url = arguments.get("pr_url")
        reviewer = arguments.get("reviewer")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.release_evidence_report pr_url must be a string or null")
        if reviewer is not None and not isinstance(reviewer, str):
            raise ValueError("memory.release_evidence_report reviewer must be a string or null")
        if not is_distribution_checkout(root):
            return {
                "available": False,
                "reason": "release evidence report requires a git distribution checkout",
                "release_ready": None,
                "release_blocker_count": None,
                "mutates_system": False,
                "records_evidence": False,
                "writes_files": False,
                "report_path": None,
                "markdown": None,
            }
        evidence = build_release_evidence(root, pr_url=pr_url or None, reviewer=reviewer or None)
        markdown = render_release_evidence_markdown(evidence)
        if scan_text(markdown, "<release-evidence-report-mcp>"):
            raise ValueError("release evidence report rejected by secret scan")
        return {
            "available": True,
            "reason": None,
            "release_ready": evidence.release_ready,
            "release_blocker_count": len(evidence.release_blockers),
            "mutates_system": False,
            "records_evidence": False,
            "writes_files": False,
            "report_path": None,
            "markdown": markdown,
        }

    if name == "memory.publish_plan":
        repository = arguments.get("repository") or "testpypi"
        pr_url = arguments.get("pr_url")
        command = arguments.get("command") or "ai-dememory"
        if repository not in REPOSITORIES:
            raise ValueError("memory.publish_plan repository must be testpypi or pypi")
        if pr_url is not None and not isinstance(pr_url, str):
            raise ValueError("memory.publish_plan pr_url must be a string or null")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("memory.publish_plan command must be a non-empty string")
        return publish_plan(root, repository=repository, pr_url=pr_url or None, command=command)

    if name == "memory.roadmap_status":
        return roadmap_status(root)

    if name == "memory.hook_events":
        return {"providers": hook_events(arguments.get("provider"))}

    if name == "memory.hook_config":
        config_root = arguments.get("root")
        return {
            "config": hook_config(
                str(arguments.get("client") or "codex"),
                command=str(arguments.get("command") or "ai-dememory"),
                root=Path(config_root) if config_root else root,
            )
        }

    if name == "memory.hook_status":
        client = str(arguments.get("client") or "all")
        return hook_status_summary(
            root,
            [client],
            capture_provider=arguments.get("capture_provider"),
            capture_event=arguments.get("capture_event"),
            capture_review_status=arguments.get("capture_review_status"),
            capture_created_from=arguments.get("capture_created_from"),
            capture_created_to=arguments.get("capture_created_to"),
            capture_review_after_from=arguments.get("capture_review_after_from"),
            capture_review_after_to=arguments.get("capture_review_after_to"),
        )

    if name == "memory.hook_capture_review":
        return asdict(
            review_hook_capture(
                root,
                str(arguments["path"]),
                str(arguments["status"]),
                str(arguments["reviewed_by"]),
                str(arguments["reason"]),
            )
        )

    if name == "memory.providers_detect":
        return {"providers": [candidate.__dict__ for candidate in detect_providers(root)]}

    if name == "memory.providers_status":
        return providers_status(root)

    if name == "memory.providers_plan":
        return provider_setup_plan(root, command=str(arguments.get("command") or "ai-dememory"))

    if name == "memory.setup_plan":
        return setup_plan(
            root,
            client=str(arguments.get("client") or "all"),
            mode=str(arguments.get("mode") or "installed"),
            command=str(arguments.get("command") or "ai-dememory"),
            image=str(arguments.get("image") or "ai-dememory:local"),
        )

    if name == "memory.setup_health":
        return setup_health(
            root,
            target_platform=arguments.get("platform"),
            mode=str(arguments.get("mode") or "installed"),
        )

    if name == "memory.review_false_positives":
        due_only = bool(arguments.get("due_only", False))
        findings = filter_false_positive_reviews(false_positive_reviews(root), due_only=due_only)
        return {
            **false_positive_review_metadata(root),
            "due_only": due_only,
            "returned_count": len(findings),
            "findings": [asdict(item) for item in findings],
        }

    if name == "memory.review_stale_false_positives":
        items = stale_false_positive_suppressions(root)
        return {
            **false_positive_review_metadata(root),
            "stale_count": len(items),
            "items": [asdict(item) for item in items],
        }

    if name == "memory.false_positive_ignore":
        fp_id = str(arguments["id"])
        path = ignore_false_positive(
            root,
            fp_id,
            str(arguments["reason"]),
            str(arguments["reviewer"]),
            arguments.get("review_after_days"),
            recommendation_id=str(arguments["recommendation_id"]) if arguments.get("recommendation_id") is not None else None,
        )
        receipt = {
            "path": repo_relative_path(path, root),
            "id": fp_id,
            "ignored": True,
            "reviewer": str(arguments["reviewer"]),
            "reviewed_at": None,
            "review_after": None,
            "review_due": False,
            "review_after_status": "unknown",
            "recommendation_id": arguments.get("recommendation_id"),
            "recommendation_path": None,
            "recommendation_action": None,
            "recommendation_policy_violation": None,
            "canonical_memory_updated": False,
        }
        for review in false_positive_reviews(root):
            if review.id == fp_id:
                receipt.update(
                    {
                        "ignored": review.ignored,
                        "reviewer": review.reviewer,
                        "reviewed_at": review.reviewed_at,
                        "review_after": review.review_after,
                        "review_due": review.review_due,
                        "review_after_status": review.review_after_status,
                        "recommendation_id": review.recommendation_id,
                        "recommendation_path": review.recommendation_path,
                        "recommendation_action": review.recommendation_action,
                        "recommendation_policy_violation": review.recommendation_policy_violation,
                    }
                )
                break
        return receipt

    if name == "memory.false_positive_unignore":
        fp_id = str(arguments["id"])
        path = unignore_false_positive(
            root,
            fp_id,
            str(arguments["reviewer"]),
            recommendation_id=str(arguments["recommendation_id"]) if arguments.get("recommendation_id") is not None else None,
        )
        receipt = false_positive_review_state_receipt(root, path, fp_id, str(arguments["reviewer"]), arguments.get("recommendation_id"))
        for review in false_positive_reviews(root):
            if review.id == fp_id:
                receipt.update(
                    {
                        "ignored": review.ignored,
                        "reviewer": review.reviewer,
                        "reviewed_at": review.reviewed_at,
                        "review_after": review.review_after,
                        "review_due": review.review_due,
                        "review_after_status": review.review_after_status,
                        "recommendation_id": review.recommendation_id,
                        "recommendation_path": review.recommendation_path,
                        "recommendation_action": review.recommendation_action,
                        "recommendation_policy_violation": review.recommendation_policy_violation,
                    }
                )
                break
        return receipt

    if name == "memory.review_conflicts":
        return {
            **conflict_review_metadata(root),
            "conflicts": [asdict(item) for item in conflict_reviews(root)],
        }

    if name == "memory.conflict_dismiss":
        conflict_id = str(arguments["id"])
        reason = str(arguments["reason"])
        reviewer = str(arguments["reviewer"])
        path = dismiss_conflict(
            root,
            conflict_id,
            reason,
            reviewer,
            recommendation_id=str(arguments["recommendation_id"]) if arguments.get("recommendation_id") is not None else None,
        )
        receipt = {
            "path": repo_relative_path(path, root),
            "id": conflict_id,
            "status": "dismissed",
            "decision": reason,
            "reviewer": reviewer,
            "reviewed_at": None,
            "recommendation_id": arguments.get("recommendation_id"),
            "recommendation_path": None,
            "recommendation_action": None,
            "recommendation_policy_violation": None,
            "canonical_memory_updated": False,
        }
        for conflict in conflict_reviews(root):
            if conflict.id == conflict_id:
                receipt.update(
                    {
                        "status": conflict.status,
                        "decision": conflict.decision or reason,
                        "reviewer": conflict.reviewer,
                        "reviewed_at": conflict.reviewed_at,
                        "recommendation_id": conflict.recommendation_id,
                        "recommendation_path": conflict.recommendation_path,
                        "recommendation_action": conflict.recommendation_action,
                        "recommendation_policy_violation": conflict.recommendation_policy_violation,
                    }
                )
                break
        return receipt

    if name == "memory.conflict_merge_proposal":
        conflict_id = str(arguments["id"])
        reviewer = str(arguments["reviewer"])
        path = resolve_conflict(
            root,
            conflict_id,
            reviewer,
            merge_proposal=True,
            recommendation_id=str(arguments["recommendation_id"]) if arguments.get("recommendation_id") is not None else None,
        )
        receipt = {
            "path": repo_relative_path(path, root),
            "id": conflict_id,
            "status": "review_proposed",
            "decision": "merge_proposal",
            "reviewer": reviewer,
            "reviewed_at": None,
            "proposal_path": None,
            "recommendation_id": arguments.get("recommendation_id"),
            "recommendation_path": None,
            "recommendation_action": None,
            "recommendation_policy_violation": None,
            "canonical_memory_updated": False,
        }
        for conflict in conflict_reviews(root):
            if conflict.id == conflict_id:
                receipt.update(
                    {
                        "status": conflict.status,
                        "decision": conflict.decision or receipt["decision"],
                        "reviewer": conflict.reviewer,
                        "reviewed_at": conflict.reviewed_at,
                        "proposal_path": conflict.proposal_path,
                        "recommendation_id": conflict.recommendation_id,
                        "recommendation_path": conflict.recommendation_path,
                        "recommendation_action": conflict.recommendation_action,
                        "recommendation_policy_violation": conflict.recommendation_policy_violation,
                    }
                )
                break
        return receipt

    if name == "memory.conflict_keep":
        conflict_id = str(arguments["id"])
        keep = str(arguments["keep"])
        path = resolve_conflict(
            root,
            conflict_id,
            str(arguments["reviewer"]),
            keep=keep,
            recommendation_id=str(arguments["recommendation_id"]) if arguments.get("recommendation_id") is not None else None,
        )
        receipt = {
            "path": repo_relative_path(path, root),
            "id": conflict_id,
            "keep": keep,
            "status": "resolved",
            "decision": f"keep:{keep}",
            "reviewer": str(arguments["reviewer"]),
            "reviewed_at": None,
            "recommendation_id": arguments.get("recommendation_id"),
            "recommendation_path": None,
            "recommendation_action": None,
            "recommendation_policy_violation": None,
            "canonical_memory_updated": False,
        }
        for conflict in conflict_reviews(root):
            if conflict.id == conflict_id:
                receipt.update(
                    {
                        "status": conflict.status,
                        "decision": conflict.decision or receipt["decision"],
                        "reviewer": conflict.reviewer,
                        "reviewed_at": conflict.reviewed_at,
                        "recommendation_id": conflict.recommendation_id,
                        "recommendation_path": conflict.recommendation_path,
                        "recommendation_action": conflict.recommendation_action,
                        "recommendation_policy_violation": conflict.recommendation_policy_violation,
                    }
                )
                break
        return receipt

    if name == "memory.review_modes":
        return review_modes(root)

    if name == "memory.review_configure_mode":
        requested_mode = str(arguments["mode"])
        reviewer = arguments.get("reviewer")
        reviewer_value = str(reviewer) if reviewer is not None else None
        path = configure_review_mode(root, requested_mode, reviewer_value)
        modes = review_modes(root)
        active_mode = next(mode for mode in modes["modes"] if mode["active"])
        return {
            "path": repo_relative_path(path, root),
            "requested_mode": requested_mode,
            "active": modes["active"],
            "reviewer": reviewer_value,
            "require_human_for_durable": active_mode["require_human_for_durable"],
            "allow_llm_false_positive_triage": active_mode["allow_llm_false_positive_triage"],
            "allow_llm_conflict_recommendations": active_mode["allow_llm_conflict_recommendations"],
            "allow_llm_merge_proposals": active_mode["allow_llm_merge_proposals"],
            "allow_autonomous_inbox_proposals": active_mode["allow_autonomous_inbox_proposals"],
            "allow_apply_reviewed": active_mode["allow_apply_reviewed"],
            "canonical_memory_updated": False,
        }

    if name == "memory.review_plan":
        return asdict(review_plan(root, str(arguments.get("kind") or "inbox")))

    if name == "memory.review_recommendation":
        confidence_value = arguments.get("confidence")
        confidence = float(confidence_value) if confidence_value is not None else None
        evidence = arguments.get("evidence") or []
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise ValueError("evidence must be an array of strings")
        return asdict(
            capture_review_recommendation(
                root,
                kind=str(arguments["kind"]),
                target_id=str(arguments["target_id"]),
                recommendation=str(arguments["recommendation"]),
                rationale=str(arguments["rationale"]),
                recommended_by=str(arguments["recommended_by"]),
                confidence=confidence,
                evidence=evidence,
            )
        )

    if name == "memory.review_recommendations":
        kind_value = arguments.get("kind")
        return review_recommendations(
            root,
            kind=str(kind_value) if kind_value is not None else None,
            policy_violations_only=bool(arguments.get("policy_violations_only", False)),
            outcome_status=str(arguments["outcome_status"]) if arguments.get("outcome_status") is not None else None,
        )

    if name == "memory.review_recommendation_archive_status":
        kind_value = arguments.get("kind")
        outcome_status_value = arguments.get("outcome_status")
        archive_root = arguments.get("archive_root")
        payload = archived_review_recommendations(
            root,
            archive_root=str(archive_root) if archive_root is not None else "archive/review-recommendations",
            kind=str(kind_value) if kind_value is not None else None,
            outcome_status=str(outcome_status_value) if outcome_status_value is not None else None,
            limit=normalize_limit(arguments.get("limit", 50)),
            offset=int(arguments.get("offset", 0)),
            invalid_offset=int(arguments.get("invalid_offset", 0)),
            recursive=bool(arguments.get("recursive", False)),
        )
        if has_redacted_invalid_items(payload):
            raise ValueError("review recommendation archive status rejected by secret scan")
        return payload

    if name == "memory.review_recommendation_archive_restore_preview":
        archive_root = arguments.get("archive_root")
        payload = asdict(
            restore_archived_review_recommendation(
                root,
                recommendation_id=str(arguments["id"]),
                apply=False,
                archive_root=str(archive_root) if archive_root is not None else "archive/review-recommendations",
                recursive=bool(arguments.get("recursive", False)),
            )
        )
        if has_redacted_invalid_items(payload):
            raise ValueError("review recommendation archive restore preview rejected by secret scan")
        if scan_text(json.dumps(payload, sort_keys=True), "<review-recommendation-archive-restore-preview>"):
            raise ValueError("review recommendation archive restore preview rejected by secret scan")
        return payload

    if name == "memory.review_recommendation_outcome_report":
        kind_value = arguments.get("kind")
        outcome_status = str(arguments.get("outcome_status") or "reviewed")
        payload = review_recommendation_outcome_report_payload(
            root,
            kind=str(kind_value) if kind_value is not None else None,
            outcome_status=outcome_status,
            limit=normalize_limit(arguments.get("limit", 50)),
            offset=int(arguments.get("offset", 0)),
            invalid_offset=int(arguments.get("invalid_offset", 0)),
        )
        if has_redacted_invalid_items(payload):
            raise ValueError("review recommendation outcome report payload rejected by secret scan")
        if scan_text(json.dumps(payload, sort_keys=True), "<review-recommendation-outcome-report-payload>"):
            raise ValueError("review recommendation outcome report payload rejected by secret scan")
        markdown = render_review_recommendation_outcome_report(payload)
        if scan_text(markdown, "<review-recommendation-outcome-report>"):
            raise ValueError("review recommendation outcome report rejected by secret scan")
        return {
            **payload,
            "report_path": None,
            "markdown": markdown,
        }

    if name == "memory.review_recommendation_outcome":
        return record_review_recommendation_outcome(
            root,
            recommendation_id=str(arguments["id"]),
            outcome_status=str(arguments["status"]),
            reviewer=str(arguments["reviewer"]),
            reason=str(arguments["reason"]),
        )

    raise ValueError(f"Unknown tool: {name}")


def validate_scan_paths(root: Path, paths: Any) -> list[str] | None:
    if paths is None:
        return None
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError("paths must be an array of repository-relative strings")

    safe_paths: list[str] = []
    root_resolved = root.resolve()
    for relpath in paths:
        candidate_path = Path(relpath)
        if candidate_path.is_absolute():
            raise PermissionError("memory.secret_scan paths must be repository-relative")
        candidate = (root / candidate_path).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise PermissionError("memory.secret_scan paths must stay inside the repository") from exc
        safe_paths.append(candidate.relative_to(root_resolved).as_posix())
    return safe_paths


def validate_capture_path(root: Path, relpath: str) -> Path:
    candidate_path = Path(relpath)
    if candidate_path.is_absolute():
        raise PermissionError("memory.capture_import path must be repository-relative")
    root_resolved = root.resolve()
    candidate = (root / candidate_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise PermissionError("memory.capture_import path must stay inside the repository") from exc
    return candidate


def normalize_git_lesson_repos(repo: Any, repos: Any, root: Path) -> list[Path]:
    values: list[str] = []
    if isinstance(repo, str) and repo.strip():
        values.append(repo.strip())
    if isinstance(repos, list):
        values.extend(str(item).strip() for item in repos if str(item).strip())
    return [Path(value).expanduser() for value in values] or [root]


def normalize_limit(value: Any, default: int = 10) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, MAX_TOOL_LIMIT))


def has_redacted_invalid_items(payload: dict[str, Any]) -> bool:
    for key in ("invalid", "malformed"):
        items = payload.get(key, [])
        if isinstance(items, list) and any(isinstance(item, dict) and item.get("redacted") is True for item in items):
            return True
    return False


def normalize_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))


def normalize_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))


def working_text_arg(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"memory working {label} is required")
    text = value.strip()
    if len(text) > MAX_WORKING_CHARS:
        raise ValueError(f"memory working {label} exceeds {MAX_WORKING_CHARS} characters")
    return text


def working_optional_text_arg(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return working_text_arg(value, label)


def is_git_checkout(root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return False
    return completed.returncode == 0


def is_distribution_checkout(root: Path) -> bool:
    if not is_git_checkout(root):
        return False
    required_paths = [
        "pyproject.toml",
        "ai_dememory_tool/cli.py",
        "scripts/release_evidence.py",
        "mcp/server/memory_mcp.py",
    ]
    return all((root / path).is_file() for path in required_paths)


def is_safe_for_default_context(document: Any) -> bool:
    return document.frontmatter.get("sensitivity") in SAFE_CONTEXT_SENSITIVITIES


def memory_resource_uri(memory_id: str) -> str:
    return f"{RESOURCE_URI_PREFIX}id/{quote(memory_id, safe='')}"


def path_resource_uri(path: str) -> str:
    return f"{RESOURCE_URI_PREFIX}path/{quote(path, safe='')}"


def list_resources(root: Path, cursor: Any = None) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for path in discover_memory_files(root):
        document = load_memory(path)
        if not is_safe_for_default_context(document):
            continue
        data = document.frontmatter
        relpath = repo_relative_path(path, root)
        resources.append(
            {
                "uri": memory_resource_uri(data["id"]),
                "name": data["id"],
                "title": data["title"],
                "description": f"{data['type']} / {data['status']} at {relpath}: {extract_summary(document.content, 140)}",
                "mimeType": "text/markdown",
            }
        )
    page, next_cursor = paginate(resources, cursor)
    result: dict[str, Any] = {"resources": page}
    if next_cursor is not None:
        result["nextCursor"] = next_cursor
    return result


def list_resource_templates() -> dict[str, Any]:
    return {
        "resourceTemplates": [
            {
                "uriTemplate": "memory://id/{id}",
                "name": "memory_by_id",
                "title": "Memory by ID",
                "description": "Read a public/internal canonical memory document by id.",
                "mimeType": "text/markdown",
            },
            {
                "uriTemplate": "memory://path/{path}",
                "name": "memory_by_path",
                "title": "Memory by Path",
                "description": "Read a public/internal canonical memory document by repository-relative path.",
                "mimeType": "text/markdown",
            },
        ]
    }


def read_resource(root: Path, uri: str) -> dict[str, Any]:
    if not uri.startswith(RESOURCE_URI_PREFIX):
        raise PermissionError("unsupported resource URI")

    suffix = uri[len(RESOURCE_URI_PREFIX) :]
    if suffix.startswith("id/"):
        memory_id = unquote(suffix[len("id/") :])
        memory = get_memory(root, memory_id, None, include_sensitive=False)
    elif suffix.startswith("path/"):
        relpath = unquote(suffix[len("path/") :])
        memory = get_memory(root, None, relpath, include_sensitive=False)
    else:
        raise PermissionError("unsupported memory resource URI")

    text = render_memory_resource(memory)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "text/markdown",
                "text": text,
            }
        ]
    }


def render_memory_resource(memory: dict[str, Any]) -> str:
    frontmatter = "\n".join(
        [
            f"id: {memory['frontmatter']['id']}",
            f"title: {memory['frontmatter']['title']}",
            f"type: {memory['frontmatter']['type']}",
            f"status: {memory['frontmatter']['status']}",
            f"path: {memory['path']}",
            f"confidence: {float(memory['frontmatter']['confidence']):.2f}",
        ]
    )
    return f"---\n{frontmatter}\n---\n\n{memory['content']}"


def list_prompts(cursor: Any = None) -> dict[str, Any]:
    page, next_cursor = paginate(PROMPTS, cursor)
    result: dict[str, Any] = {"prompts": page}
    if next_cursor is not None:
        result["nextCursor"] = next_cursor
    return result


def get_prompt(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    if name == "memory_recall_context":
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        limit = normalize_limit(arguments.get("limit", 8), default=8)
        text = (
            f"Search personal memory for `{query}` with limit {limit}. "
            "Use `memory.search` first, then call `memory.get` only for relevant public/internal results. "
            "Do not request sensitive memory unless the user explicitly asks for it."
        )
        return prompt_response("Recall Memory Context", text)

    if name == "memory_capture_proposal":
        title = str(arguments.get("title") or "").strip()
        content = str(arguments.get("content") or "").strip()
        if not title or not content:
            raise ValueError("title and content are required")
        project = str(arguments.get("project") or "none")
        text = (
            "Prepare a memory proposal for human review. "
            f"Title: {title}\nProject: {project}\n\nCandidate content:\n{content}\n\n"
            "Write only to `inbox/llm-captures/` via `memory.write_proposal`; never overwrite durable memory."
        )
        return prompt_response("Capture Memory Proposal", text)

    if name == "memory_review_inbox":
        text = (
            "Review proposed captures in `inbox/`. Promote only durable, non-secret, human-approved facts. "
            "Rewrite unclear proposals, archive stale proposals, and never copy credential material into memory."
        )
        return prompt_response("Review Memory Inbox", text)

    raise ValueError(f"Unknown prompt: {name}")


def prompt_response(description: str, text: str) -> dict[str, Any]:
    return {
        "description": description,
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": text},
            }
        ],
    }


def get_memory(
    root: Path,
    memory_id: str | None,
    relpath: str | None,
    include_sensitive: bool = False,
) -> dict[str, Any]:
    path: Path | None = None
    if relpath:
        candidate = (root / relpath).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise PermissionError("path must stay inside the repository") from exc
        if not is_memory_file(candidate, root):
            raise PermissionError("memory.get path must point to a canonical memory file")
        path = candidate
    elif memory_id:
        db_path = default_db_path(root)
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT path FROM memories WHERE id = ?", (memory_id,)).fetchone()
            conn.close()
            if row:
                path = root / row[0]
        if path is None:
            for candidate in discover_memory_files(root):
                document = load_memory(candidate)
                if document.frontmatter.get("id") == memory_id:
                    path = candidate
                    break
    else:
        raise ValueError("memory.get requires id or path")

    if path is None or not path.exists():
        raise FileNotFoundError("memory not found")
    document = load_memory(path)
    if document.frontmatter["sensitivity"] in {"private", "sensitive"} and not include_sensitive:
        raise PermissionError("memory requires include_sensitive=true")
    return {
        "path": repo_relative_path(path, root),
        "frontmatter": document.frontmatter,
        "content": document.content,
    }


def write_proposal(
    root: Path,
    title: str,
    content: str,
    project: str | None,
    tags: list[str],
    source_kind: str,
    source_ref: str | None,
) -> dict[str, str]:
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"source_kind must be one of {sorted(SOURCE_KINDS)}")
    title = title.strip()
    content = content.strip()
    if not title:
        raise ValueError("title is required")
    if not content:
        raise ValueError("content is required")
    if len(content) > MAX_PROPOSAL_CHARS:
        raise ValueError(f"content exceeds {MAX_PROPOSAL_CHARS} characters")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be an array of strings")

    now = datetime.now(timezone.utc)
    created = now.date().isoformat()
    review_after = (now.date() + timedelta(days=7)).isoformat()
    slug = slugify(title)
    capture_dir = root / "inbox" / "llm-captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    path = capture_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}_{slug}.md"
    tag_list = ", ".join(slugify(tag, "tag") for tag in tags)
    title_value = frontmatter_scalar(title)
    project_value = frontmatter_scalar(project)
    source_value = frontmatter_scalar(source_ref or "mcp-write-proposal")
    text = f"""---
id: proposal_{now.strftime('%Y%m%d_%H%M%S')}_{slug}
title: {title_value}
type: session
status: proposed
scope: session
project: {project_value}
tags: [{tag_list}]
aliases: []
created_at: {created}
updated_at: {created}
confidence: 0.5
sensitivity: internal
source:
  kind: {source_kind}
  ref: {source_value}
pin: false
decay: fast
review_after: {review_after}
---

# {title}

{content}
"""
    findings = scan_text(text, "<memory.write_proposal>")
    if findings:
        raise ValueError("proposal rejected by secret scan")
    path.write_text(text, encoding="utf-8")
    return {"path": repo_relative_path(path, root)}


def frontmatter_scalar(value: str | None) -> str:
    if value is None or value == "":
        return "null"
    clean = " ".join(str(value).splitlines()).strip().replace('"', "'")
    return json.dumps(clean)


def mark_seen(
    root: Path,
    query: str,
    selected_memory_id: str | None,
    score: float | None,
    used_by: str | None,
) -> dict[str, Any]:
    for label, value in (("query", query), ("selected_memory_id", selected_memory_id or ""), ("used_by", used_by or "")):
        if value:
            findings = scan_text(value, f"<memory.mark_seen.{label}>")
            if findings:
                raise ValueError(f"memory.mark_seen rejected secret-like {label}")
    db_path = default_db_path(root)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} does not exist. Run memory.reindex first.")
    conn = sqlite3.connect(db_path)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute(
        """
        INSERT INTO retrieval_log (query, selected_memory_id, score, used_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (query, selected_memory_id, score, used_by, created_at),
    )
    if selected_memory_id:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_lifecycle (
              memory_id TEXT PRIMARY KEY,
              retrieval_count INTEGER NOT NULL DEFAULT 0,
              last_retrieved_at TEXT,
              strength REAL NOT NULL DEFAULT 0.0,
              positive_outcomes INTEGER NOT NULL DEFAULT 0,
              negative_outcomes INTEGER NOT NULL DEFAULT 0,
              reward_factor REAL NOT NULL DEFAULT 1.0,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO memory_lifecycle (memory_id, retrieval_count, last_retrieved_at, strength, updated_at)
            VALUES (?, 1, ?, 0.1, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
              retrieval_count = retrieval_count + 1,
              last_retrieved_at = excluded.last_retrieved_at,
              strength = min(1.0, strength + 0.03),
              updated_at = excluded.updated_at
            """,
            (selected_memory_id, created_at, created_at),
        )
    conn.commit()
    conn.close()
    return {
        "query": query,
        "selected_memory_id": selected_memory_id,
        "score": score,
        "used_by": used_by,
        "lifecycle_updated": bool(selected_memory_id),
        "created_at": created_at,
    }


def respond(request_id: Any, result: Any = None, error: Exception | None = None) -> str:
    if error is not None:
        payload = {"jsonrpc": "2.0", "id": request_id, "error": error_payload(error)}
    else:
        payload = {"jsonrpc": "2.0", "id": request_id, "result": result}
    return json.dumps(payload)


def error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, (ValueError, PermissionError, FileNotFoundError)):
        code = -32602
    else:
        code = -32000
    return {"code": code, "message": str(error)}


def tool_result(result: Any) -> dict[str, Any]:
    structured = {"results": result} if isinstance(result, list) else result
    return {
        "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
        "structuredContent": structured,
        "isError": False,
    }


def tool_error_result(error: Exception) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": str(error)}],
        "isError": True,
    }


def list_tools(cursor: Any = None) -> dict[str, Any]:
    page, next_cursor = paginate(TOOLS, cursor)
    result: dict[str, Any] = {"tools": page}
    if next_cursor is not None:
        result["nextCursor"] = next_cursor
    return result


def negotiate_protocol_version(message: dict[str, Any]) -> str:
    requested = (message.get("params") or {}).get("protocolVersion")
    if requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return SUPPORTED_PROTOCOL_VERSIONS[0]


def handle_rpc(message: dict[str, Any], root: Path) -> dict[str, Any] | None:
    method = message.get("method")
    if method == "initialize":
        return {
            "protocolVersion": negotiate_protocol_version(message),
            "capabilities": SERVER_CAPABILITIES,
            "serverInfo": {"name": "ai-dememory", "version": "2.0.0rc3"},
        }
    if method == "ping":
        return {}
    if method in {
        "notifications/initialized",
        "notifications/cancelled",
        "notifications/progress",
    }:
        return None
    if method == "tools/list":
        return list_tools((message.get("params") or {}).get("cursor"))
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = call_tool(name, arguments, root)
            return tool_result(result)
        except Exception as exc:
            return tool_error_result(exc)
    if method == "resources/list":
        return list_resources(root, (message.get("params") or {}).get("cursor"))
    if method == "resources/templates/list":
        return list_resource_templates()
    if method == "resources/read":
        params = message.get("params") or {}
        return read_resource(root, str(params.get("uri") or ""))
    if method == "prompts/list":
        return list_prompts((message.get("params") or {}).get("cursor"))
    if method == "prompts/get":
        params = message.get("params") or {}
        return get_prompt(str(params.get("name") or ""), params.get("arguments") or {})
    raise ValueError(f"Unsupported method: {method}")


def run_stdio(root: Path) -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            result = handle_rpc(message, root)
            if "id" in message and result is not None:
                print(respond(message.get("id"), result), flush=True)
        except Exception as exc:
            request_id = message.get("id") if "message" in locals() else None
            if request_id is not None:
                print(respond(request_id, error=exc), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--stdio", action="store_true", help="Run JSON-RPC stdio server.")
    parser.add_argument("--list-tools", action="store_true", help="Print tool definitions.")
    parser.add_argument("--call", help="Call one tool directly by name.")
    parser.add_argument("--args", default="{}", help="JSON arguments for --call.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    if args.stdio:
        return run_stdio(root)
    if args.list_tools:
        print(json.dumps({"tools": TOOLS}, indent=2))
        return 0
    if args.call:
        result = call_tool(args.call, json.loads(args.args), root)
        print(json.dumps(result, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
