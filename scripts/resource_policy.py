#!/usr/bin/env python3
"""Resolve bounded autonomy, resource, and host-model policy profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Any

from config_file import load_config
from resource_limits import (
    GRAPH_MAX_EDGES,
    GRAPH_MAX_LIMIT,
    GRAPH_MAX_NODES,
    MAX_CONSOLIDATION_LOG_ROWS,
    MAX_MEMORY_FILE_BYTES,
    MAX_MEMORY_FILES,
    MAX_MEMORY_SCAN_ENTRIES,
    MAX_MEMORY_TOTAL_BYTES,
    MAX_OUTCOME_LOG_ROWS,
    MAX_RETRIEVAL_LOG_ROWS,
    MAX_SECRET_SCAN_ENTRIES,
    MAX_SECRET_SCAN_FILE_BYTES,
    MAX_SECRET_SCAN_FILES,
    MAX_SECRET_SCAN_FINDINGS,
    MAX_SECRET_SCAN_TOTAL_BYTES,
)


PROFILE_VERSION = 1
DEFAULT_INTENSITY = "balanced"
DEFAULT_MODEL_POLICY = "off"

HARD_LIMITS: dict[str, dict[str, object]] = {
    "context_budget_tokens": {"minimum": 400, "maximum": 8000, "unit": "tokens", "enforcement": "hard"},
    "recall_budget_tokens": {"minimum": 200, "maximum": 8000, "unit": "tokens", "enforcement": "hard"},
    "min_relevance_score": {"minimum": 0.0, "maximum": 1.0, "unit": "score", "enforcement": "hard"},
    "baseline_budget_tokens": {"minimum": 0, "maximum": 4000, "unit": "tokens", "enforcement": "hard"},
    "max_keywords": {"minimum": 3, "maximum": 30, "unit": "keywords", "enforcement": "hard"},
    "provider_file_limit": {"minimum": 1, "maximum": 100, "unit": "new candidates/run", "enforcement": "hard"},
    "provider_max_file_bytes": {"minimum": 16384, "maximum": 262144, "unit": "bytes/file", "enforcement": "hard"},
    "provider_scan_entries": {"minimum": 100, "maximum": 20000, "unit": "filesystem entries/run", "enforcement": "hard"},
    "maintenance_report_retention": {"minimum": 4, "maximum": 100, "unit": "reports", "enforcement": "hard"},
    "maintenance_timeout_seconds": {
        "minimum": 60,
        "maximum": 1800,
        "unit": "seconds",
        "enforcement": "owned_process_tree",
    },
    "mcp_idle_timeout_seconds": {"minimum": 30, "maximum": 3600, "unit": "seconds", "enforcement": "hard"},
    "hook_capture_max_pending": {"minimum": 0, "maximum": 500, "unit": "pending captures", "enforcement": "hard"},
    "canonical_scan_entries": {"minimum": 1, "maximum": MAX_MEMORY_SCAN_ENTRIES, "unit": "filesystem entries/scan", "enforcement": "hard"},
    "canonical_memory_files": {"minimum": 1, "maximum": MAX_MEMORY_FILES, "unit": "files/vault", "enforcement": "hard"},
    "canonical_memory_file_bytes": {"minimum": 1, "maximum": MAX_MEMORY_FILE_BYTES, "unit": "bytes/file", "enforcement": "hard"},
    "canonical_memory_total_bytes": {"minimum": 1, "maximum": MAX_MEMORY_TOTAL_BYTES, "unit": "bytes/scan", "enforcement": "hard"},
    "secret_scan_entries": {"minimum": 1, "maximum": MAX_SECRET_SCAN_ENTRIES, "unit": "filesystem entries/scan", "enforcement": "hard"},
    "secret_scan_files": {"minimum": 1, "maximum": MAX_SECRET_SCAN_FILES, "unit": "files/scan", "enforcement": "hard"},
    "secret_scan_file_bytes": {"minimum": 1, "maximum": MAX_SECRET_SCAN_FILE_BYTES, "unit": "bytes/file", "enforcement": "hard"},
    "secret_scan_total_bytes": {"minimum": 1, "maximum": MAX_SECRET_SCAN_TOTAL_BYTES, "unit": "bytes/scan", "enforcement": "hard"},
    "secret_scan_findings": {"minimum": 1, "maximum": MAX_SECRET_SCAN_FINDINGS, "unit": "findings/scan", "enforcement": "hard"},
    "graph_memories": {"minimum": 1, "maximum": GRAPH_MAX_LIMIT, "unit": "memories/page", "enforcement": "hard"},
    "graph_nodes": {"minimum": 1, "maximum": GRAPH_MAX_NODES, "unit": "nodes/page", "enforcement": "hard"},
    "graph_edges": {"minimum": 1, "maximum": GRAPH_MAX_EDGES, "unit": "edges/page", "enforcement": "hard"},
    "retrieval_log_rows": {"minimum": 1, "maximum": MAX_RETRIEVAL_LOG_ROWS, "unit": "rows", "enforcement": "retention"},
    "outcome_log_rows": {"minimum": 1, "maximum": MAX_OUTCOME_LOG_ROWS, "unit": "rows", "enforcement": "retention"},
    "consolidation_log_rows": {"minimum": 1, "maximum": MAX_CONSOLIDATION_LOG_ROWS, "unit": "rows", "enforcement": "retention"},
}


@dataclass(frozen=True)
class ResourceProfile:
    name: str
    summary: str
    recommended_for: str
    context_budget_tokens: int
    recall_enabled: bool
    recall_per_turn: bool
    recall_budget_tokens: int
    baseline_budget_tokens: int
    max_keywords: int
    min_relevance_score: float
    mcp_profile: str
    daily_enabled: bool
    weekly_enabled: bool
    provider_file_limit: int
    provider_max_file_bytes: int
    provider_scan_entries: int
    maintenance_report_retention: int
    maintenance_timeout_seconds: int
    mcp_idle_timeout_seconds: int
    hook_metadata: bool
    hook_capture_max_pending: int


@dataclass(frozen=True)
class ModelPolicy:
    name: str
    summary: str
    review_mode: str
    session_proposals: bool
    runtime_model_calls: int = 0
    runtime_embedding_calls: int = 0
    durable_auto_promotion: bool = False


RESOURCE_PROFILES: dict[str, ResourceProfile] = {
    "minimal": ResourceProfile(
        name="minimal",
        summary="Manual recall and one bounded weekly maintenance job.",
        recommended_for="small vaults, laptops, CI, or users who want near-zero background work",
        context_budget_tokens=800,
        recall_enabled=True,
        recall_per_turn=False,
        recall_budget_tokens=400,
        baseline_budget_tokens=160,
        max_keywords=6,
        min_relevance_score=0.24,
        mcp_profile="core",
        daily_enabled=False,
        weekly_enabled=True,
        provider_file_limit=5,
        provider_max_file_bytes=32 * 1024,
        provider_scan_entries=500,
        maintenance_report_retention=8,
        maintenance_timeout_seconds=120,
        mcp_idle_timeout_seconds=120,
        hook_metadata=False,
        hook_capture_max_pending=25,
    ),
    "balanced": ResourceProfile(
        name="balanced",
        summary="Bounded per-turn recall with daily and weekly one-shot maintenance.",
        recommended_for="most personal vaults and the default first installation",
        context_budget_tokens=2000,
        recall_enabled=True,
        recall_per_turn=True,
        recall_budget_tokens=1200,
        baseline_budget_tokens=480,
        max_keywords=12,
        min_relevance_score=0.18,
        mcp_profile="core",
        daily_enabled=True,
        weekly_enabled=True,
        provider_file_limit=20,
        provider_max_file_bytes=64 * 1024,
        provider_scan_entries=2500,
        maintenance_report_retention=20,
        maintenance_timeout_seconds=300,
        mcp_idle_timeout_seconds=600,
        hook_metadata=False,
        hook_capture_max_pending=100,
    ),
    "active": ResourceProfile(
        name="active",
        summary="Larger recall and import budgets with review-first working tools.",
        recommended_for="large, frequently changing vaults on an always-on workstation",
        context_budget_tokens=4000,
        recall_enabled=True,
        recall_per_turn=True,
        recall_budget_tokens=2400,
        baseline_budget_tokens=800,
        max_keywords=20,
        min_relevance_score=0.14,
        mcp_profile="working",
        daily_enabled=True,
        weekly_enabled=True,
        provider_file_limit=50,
        provider_max_file_bytes=128 * 1024,
        provider_scan_entries=10000,
        maintenance_report_retention=40,
        maintenance_timeout_seconds=900,
        mcp_idle_timeout_seconds=1800,
        hook_metadata=True,
        hook_capture_max_pending=500,
    ),
}

MODEL_POLICIES: dict[str, ModelPolicy] = {
    "off": ModelPolicy(
        name="off",
        summary="No host-model review automation; deterministic local tools only.",
        review_mode="strict",
        session_proposals=False,
    ),
    "advisory": ModelPolicy(
        name="advisory",
        summary="The already active host agent may triage and recommend; a human still decides.",
        review_mode="balanced",
        session_proposals=False,
    ),
    "proposals": ModelPolicy(
        name="proposals",
        summary="The already active host agent may create review-first inbox proposals, never durable promotions.",
        review_mode="autonomous_proposals",
        session_proposals=True,
    ),
}


def profile_names() -> tuple[str, ...]:
    return tuple(RESOURCE_PROFILES)


def model_policy_names() -> tuple[str, ...]:
    return tuple(MODEL_POLICIES)


def get_resource_profile(name: str | None) -> ResourceProfile:
    value = str(name or DEFAULT_INTENSITY).strip().lower()
    try:
        return RESOURCE_PROFILES[value]
    except KeyError:
        # Configuration values are untrusted input.  Keep the diagnostic useful
        # without echoing the supplied value (including through a chained
        # KeyError traceback).
        raise ValueError("unknown intensity") from None


def get_model_policy(name: str | None) -> ModelPolicy:
    value = str(name or DEFAULT_MODEL_POLICY).strip().lower()
    try:
        return MODEL_POLICIES[value]
    except KeyError:
        raise ValueError("unknown model policy") from None


def profile_catalog() -> list[dict[str, object]]:
    return [profile_projection(profile) for profile in RESOURCE_PROFILES.values()]


def model_policy_catalog() -> list[dict[str, object]]:
    return [asdict(policy) for policy in MODEL_POLICIES.values()]


def profile_projection(profile: ResourceProfile) -> dict[str, object]:
    data = asdict(profile)
    data.update(
        {
            "profile_version": PROFILE_VERSION,
            "estimated_local_runs_per_week": int(profile.daily_enabled) * 7 + int(profile.weekly_enabled),
            "automatic_recall_max_tokens_per_eligible_turn": (
                profile.recall_budget_tokens if profile.recall_enabled and profile.recall_per_turn else 0
            ),
            "runtime_model_calls_per_maintenance_run": 0,
            "runtime_embedding_calls_per_maintenance_run": 0,
        }
    )
    return data


def resolved_resource_policy(
    root: Path,
    intensity: str | None = None,
    model_policy: str | None = None,
) -> dict[str, object]:
    """Resolve persisted overrides without allowing values past hard ceilings."""
    config = load_config(root)
    automation = section(config, "automation")
    resources = section(config, "resources")
    recall = section(config, "recall")
    context = section(config, "context")
    schedule = section(config, "schedule")
    learning = section(config, "learning")
    errors: list[str] = []

    intensity_name = str(
        intensity
        or automation.get("intensity")
        or schedule.get("intensity")
        or DEFAULT_INTENSITY
    )
    model_policy_name = str(model_policy or automation.get("model_policy") or DEFAULT_MODEL_POLICY)
    try:
        profile = get_resource_profile(intensity_name)
    except ValueError:
        errors.append("invalid_automation_setting:intensity")
        profile = get_resource_profile(DEFAULT_INTENSITY)
    try:
        host_policy = get_model_policy(model_policy_name)
    except ValueError:
        errors.append("invalid_automation_setting:model_policy")
        host_policy = get_model_policy(DEFAULT_MODEL_POLICY)

    values = {
        "context_budget_tokens": bounded_config_int(
            context,
            "default_budget_tokens",
            profile.context_budget_tokens,
            "context_budget_tokens",
            errors,
        ),
        "recall_budget_tokens": bounded_config_int(
            recall,
            "default_budget_tokens",
            profile.recall_budget_tokens,
            "recall_budget_tokens",
            errors,
        ),
        "baseline_budget_tokens": bounded_config_int(
            recall,
            "baseline_budget_tokens",
            profile.baseline_budget_tokens,
            "baseline_budget_tokens",
            errors,
        ),
        "max_keywords": bounded_config_int(
            recall,
            "max_keywords",
            profile.max_keywords,
            "max_keywords",
            errors,
        ),
        "provider_file_limit": bounded_config_int(
            resources,
            "provider_file_limit",
            profile.provider_file_limit,
            "provider_file_limit",
            errors,
        ),
        "provider_max_file_bytes": bounded_config_int(
            resources,
            "provider_max_file_bytes",
            profile.provider_max_file_bytes,
            "provider_max_file_bytes",
            errors,
        ),
        "provider_scan_entries": bounded_config_int(
            resources,
            "provider_scan_entries",
            profile.provider_scan_entries,
            "provider_scan_entries",
            errors,
        ),
        "maintenance_report_retention": bounded_config_int(
            resources,
            "maintenance_report_retention",
            profile.maintenance_report_retention,
            "maintenance_report_retention",
            errors,
        ),
        "maintenance_timeout_seconds": bounded_config_int(
            resources,
            "maintenance_timeout_seconds",
            profile.maintenance_timeout_seconds,
            "maintenance_timeout_seconds",
            errors,
        ),
        "mcp_idle_timeout_seconds": bounded_config_int(
            resources,
            "mcp_idle_timeout_seconds",
            profile.mcp_idle_timeout_seconds,
            "mcp_idle_timeout_seconds",
            errors,
        ),
        "hook_capture_max_pending": bounded_config_int(
            resources,
            "hook_capture_max_pending",
            profile.hook_capture_max_pending,
            "hook_capture_max_pending",
            errors,
        ),
    }
    values["baseline_budget_tokens"] = min(
        int(values["baseline_budget_tokens"]),
        int(values["recall_budget_tokens"]),
    )
    recall_enabled = config_bool(recall, "enabled", profile.recall_enabled, errors, "recall")
    recall_per_turn = config_bool(recall, "per_turn", profile.recall_per_turn, errors, "recall")
    daily_enabled = config_bool(schedule, "daily_enabled", profile.daily_enabled, errors, "schedule")
    weekly_enabled = config_bool(schedule, "weekly_enabled", profile.weekly_enabled, errors, "schedule")
    hook_metadata = config_bool(learning, "hook_metadata", profile.hook_metadata, errors, "learning")
    min_relevance_score = bounded_config_float(
        recall,
        "min_relevance_score",
        profile.min_relevance_score,
        "min_relevance_score",
        errors,
    )

    return {
        "profile_version": PROFILE_VERSION,
        "intensity": profile.name,
        "model_policy": host_policy.name,
        "valid": not errors,
        "validation_errors": errors,
        "summary": profile.summary,
        "recommended_for": profile.recommended_for,
        "mcp_profile": profile.mcp_profile,
        "recall_enabled": recall_enabled,
        "recall_per_turn": recall_per_turn,
        "min_relevance_score": min_relevance_score,
        "daily_enabled": daily_enabled,
        "weekly_enabled": weekly_enabled,
        "estimated_local_runs_per_week": int(daily_enabled) * 7 + int(weekly_enabled),
        "hook_metadata": hook_metadata,
        "automatic_recall_max_tokens_per_eligible_turn": (
            values["recall_budget_tokens"] if recall_enabled and recall_per_turn else 0
        ),
        "manual_context_default_tokens": values["context_budget_tokens"],
        "resources": values,
        "host_model": asdict(host_policy),
        "runtime_model_calls_per_maintenance_run": 0,
        "runtime_embedding_calls_per_maintenance_run": 0,
        "hard_limits": HARD_LIMITS,
        "enforcement_notes": [
            "Token, file-count, byte, scan-entry, retention, and capture ceilings are enforced in-process.",
            "Supervised installed-mode deadlines terminate and reap the owned process tree; direct runs without "
            "--timeout-seconds remain operator-bounded.",
            "Scheduled Docker mode adds CPU, memory, PID, and wall-clock ceilings; installed host mode "
            "guarantees owned-process-tree cleanup and wall-clock deadlines, not native CPU or memory quotas.",
            "ai-dememory does not call a model or embedding provider; host-agent context is the only model-token input.",
            "No profile auto-promotes durable memory or installs hooks/schedules without an explicit reviewed apply step.",
        ],
    }


def section(config: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


def bounded_config_int(
    values: dict[str, Any],
    key: str,
    default: int,
    limit_name: str,
    errors: list[str],
) -> int:
    value = values.get(key)
    if value is None:
        return default
    limits = HARD_LIMITS[limit_name]
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"invalid_resource_setting:{key}")
        return default
    minimum = int(limits["minimum"])
    maximum = int(limits["maximum"])
    if value < minimum or value > maximum:
        errors.append(f"out_of_bounds_resource_setting:{key}")
        return default
    return value


def bounded_config_float(
    values: dict[str, Any],
    key: str,
    default: float,
    limit_name: str,
    errors: list[str],
) -> float:
    value = values.get(key)
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"invalid_resource_setting:{key}")
        return default
    limits = HARD_LIMITS[limit_name]
    minimum = float(limits["minimum"])
    maximum = float(limits["maximum"])
    if isinstance(value, bool) or not math.isfinite(parsed) or parsed < minimum or parsed > maximum:
        errors.append(f"out_of_bounds_resource_setting:{key}")
        return default
    return parsed


def config_bool(
    values: dict[str, Any],
    key: str,
    default: bool,
    errors: list[str],
    section_name: str,
) -> bool:
    value = values.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    errors.append(f"invalid_{section_name}_setting:{key}")
    return default
