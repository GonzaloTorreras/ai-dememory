#!/usr/bin/env python3
"""Preview/apply operational setup or an explicit reviewed personal baseline."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from ai_dememory_tool.cli import build_mcp_config
from config_file import load_config_path
from hook_event import hook_config
from memorylib import path_is_link_like, repo_root, slugify
from resource_policy import (
    DEFAULT_INTENSITY,
    DEFAULT_MODEL_POLICY,
    HARD_LIMITS,
    get_model_policy,
    get_resource_profile,
    model_policy_catalog,
    model_policy_names,
    profile_catalog,
    profile_names,
)
from review_memory import review_mode_config_values
from schedule_memory import immutable_docker_image
from secret_scan import scan_text


BASELINE_KINDS = ("values", "preferences", "recommendations")
ALLOWED_SENSITIVITY = {"public", "internal"}
DEFAULT_CLIENTS = ["codex", "claude"]
GUIDED_DECLINED_EXIT_CODE = 3


def onboarding_plan(
    root: Path,
    answers: dict[str, Any],
    *,
    _include_payloads: bool = False,
) -> dict[str, Any]:
    """Build a side-effect-free, memory-only onboarding plan."""
    normalized = normalize_answers(answers)
    documents = render_documents(normalized)
    return _durable_onboarding_plan(
        root,
        normalized,
        documents,
        _include_payloads=_include_payloads,
    )


def _durable_onboarding_plan(
    root: Path,
    normalized: dict[str, Any],
    documents: dict[str, str],
    *,
    _include_payloads: bool,
) -> dict[str, Any]:
    """Fingerprint only the reviewed durable writes, never operating policy."""
    root = Path(root).resolve()
    writes: list[dict[str, Any]] = []
    for relative_path, content in documents.items():
        target = safe_target(root, relative_path)
        writes.append(planned_write(root, target, content, kind="memory", allow_update=False))

    conflicts = [item["path"] for item in writes if item["status"] == "conflict"]
    plan = {
        "root": str(root),
        "setup_scope": "durable_baseline",
        "writes_config": False,
        "reviewed_by": normalized["reviewed_by"],
        "writes": writes,
        "created_count": sum(item["status"] == "create" for item in writes),
        "updated_count": 0,
        "unchanged_count": sum(item["status"] == "unchanged" for item in writes),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "can_apply": not conflicts,
        "mutates_system": False,
        "writes_files": False,
        "durable_memory_reviewed": True,
        "auto_promotes": False,
        "installs_hooks": False,
        "installs_schedules": False,
    }
    plan["plan_sha256"] = plan_fingerprint(plan)
    if _include_payloads:
        plan["_payloads"] = dict(documents)
    return plan


def operational_setup_plan(
    root: Path,
    answers: dict[str, Any],
    *,
    _include_payloads: bool = False,
) -> dict[str, Any]:
    """Build a config-only first-run plan without creating durable memory."""
    if not isinstance(answers, dict):
        raise ValueError("setup input must be a JSON object")
    personal_fields = [
        field
        for field in ("reviewed_by", *BASELINE_KINDS, "projects", "sensitivity")
        if field in answers
    ]
    if personal_fields:
        raise ValueError(
            "setup wizard configures operations only; use ai-dememory onboard for: "
            + ", ".join(personal_fields)
        )
    normalized = normalize_operational_answers(answers)
    return _setup_plan(
        root,
        normalized,
        documents={},
        setup_scope="operational",
        durable_memory_reviewed=False,
        write_config=True,
        _include_payloads=_include_payloads,
    )


def _setup_plan(
    root: Path,
    normalized: dict[str, Any],
    *,
    documents: dict[str, str],
    setup_scope: str,
    durable_memory_reviewed: bool,
    write_config: bool,
    _include_payloads: bool,
) -> dict[str, Any]:
    root = Path(root).resolve()
    writes: list[dict[str, Any]] = []
    for relative_path, content in documents.items():
        target = safe_target(root, relative_path)
        writes.append(planned_write(root, target, content, kind="memory", allow_update=False))

    updated_config: str | None = None
    schedule_preserved = False
    if write_config:
        config_path = safe_target(root, ".ai-dememory.toml")
        current_config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        existing_schedule = (
            load_config_path(config_path).get("schedule", {})
            if config_path.exists()
            else {}
        )
        schedule_preserved = bool(
            isinstance(existing_schedule, dict)
            and existing_schedule.get("enabled", False)
        )
        updated_config = merge_onboarding_config(
            current_config,
            normalized,
            preserve_schedule=schedule_preserved,
        )
        writes.append(planned_write(root, config_path, updated_config, kind="config", allow_update=True))

    conflicts = [item["path"] for item in writes if item["status"] == "conflict"]
    if schedule_preserved:
        conflicts.append(".ai-dememory.toml:[enabled-schedule]")
    plan = {
        "root": str(root),
        "setup_scope": setup_scope,
        "writes_config": write_config,
        "reviewed_by": normalized.get("reviewed_by"),
        "clients": normalized["clients"],
        "automation": normalized["automation"],
        "resource_policy": onboarding_resource_policy(normalized),
        "resource_profiles": profile_catalog(),
        "model_policies": model_policy_catalog(),
        "context": normalized["context"],
        "recall": normalized["recall"],
        "learning": normalized["learning"],
        "schedule": normalized["schedule"],
        "schedule_preserved": schedule_preserved,
        "integrations": integration_plan(root, normalized),
        "writes": writes,
        "created_count": sum(item["status"] == "create" for item in writes),
        "updated_count": sum(item["status"] == "update" for item in writes),
        "unchanged_count": sum(item["status"] == "unchanged" for item in writes),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "can_apply": not conflicts,
        "mutates_system": False,
        "writes_files": False,
        "durable_memory_reviewed": durable_memory_reviewed,
        "auto_promotes": False,
        "installs_hooks": False,
        "installs_schedules": False,
    }
    plan["plan_sha256"] = plan_fingerprint(plan)
    if _include_payloads:
        plan["_payloads"] = dict(documents)
        if updated_config is not None:
            plan["_payloads"][".ai-dememory.toml"] = updated_config
    return plan


def apply_onboarding(root: Path, answers: dict[str, Any], expected_plan_sha256: str | None = None) -> dict[str, Any]:
    """Apply exactly one reviewed onboarding plan, refusing memory overwrites."""
    plan = onboarding_plan(root, answers, _include_payloads=True)
    return _apply_setup_plan(root, plan, expected_plan_sha256)


def apply_operational_setup(
    root: Path,
    answers: dict[str, Any],
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Apply exactly one reviewed config-only first-run plan."""
    plan = operational_setup_plan(root, answers, _include_payloads=True)
    return _apply_setup_plan(root, plan, expected_plan_sha256)


def _apply_setup_plan(
    root: Path,
    plan: dict[str, Any],
    expected_plan_sha256: str | None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    payloads = plan.pop("_payloads")
    if not isinstance(payloads, dict):
        raise ValueError("setup plan payloads are unavailable")
    if not expected_plan_sha256:
        raise ValueError("--expect-plan-sha256 is required; preview and review the setup plan first")
    if not hmac.compare_digest(expected_plan_sha256, str(plan["plan_sha256"])):
        raise ValueError("setup plan changed after preview; review the new plan before apply")
    if plan["conflicts"]:
        raise ValueError("setup conflicts must be reviewed before apply: " + ", ".join(plan["conflicts"]))

    changed: list[str] = []
    batch: list[tuple[Path, str, bool, str | None]] = []
    for item in plan["writes"]:
        relative_path = str(item["path"])
        target = safe_target(root, relative_path)
        assert_write_precondition(target, item.get("current_sha256"))
        if item["status"] == "unchanged":
            continue
        batch.append(
            (
                target,
                str(payloads[relative_path]),
                item["kind"] == "config",
                item.get("current_sha256"),
            )
        )
        changed.append(relative_path)
    atomic_batch_write(batch)

    applied = dict(plan)
    applied.update(
        {
            "applied": True,
            "changed": changed,
            "mutates_system": bool(changed),
            "writes_files": bool(changed),
        }
    )
    return applied


def plan_fingerprint(plan: dict[str, Any]) -> str:
    canonical = {
        "root": plan["root"],
        "setup_scope": plan["setup_scope"],
        "writes_config": plan["writes_config"],
        "durable_memory_reviewed": plan["durable_memory_reviewed"],
        "reviewed_by": plan["reviewed_by"],
        "writes": [
            {
                key: item[key]
                for key in ("path", "kind", "status", "sha256", "current_sha256")
            }
            for item in plan["writes"]
        ],
    }
    if plan["setup_scope"] == "operational":
        canonical.update(
            {
                "clients": plan["clients"],
                "automation": plan["automation"],
                "resource_policy": plan["resource_policy"],
                "context": plan["context"],
                "recall": plan["recall"],
                "learning": plan["learning"],
                "schedule": plan["schedule"],
                "schedule_preserved": plan["schedule_preserved"],
                "integrations": plan["integrations"],
            }
        )
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_answers(answers: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(answers, dict):
        raise ValueError("onboarding input must be a JSON object")
    reviewed_by = clean_scalar(answers.get("reviewed_by"))
    if not reviewed_by:
        raise ValueError("reviewed_by is required before durable onboarding")

    baseline = {kind: clean_list(answers.get(kind)) for kind in BASELINE_KINDS}
    missing = [kind for kind, values in baseline.items() if not values]
    if missing:
        raise ValueError("minimum onboarding requires: " + ", ".join(missing))

    sensitivity = clean_scalar(answers.get("sensitivity")) or "internal"
    if sensitivity not in ALLOWED_SENSITIVITY:
        raise ValueError("sensitivity must be public or internal for injectable baseline memory")

    operational_fields = sorted(
        field
        for field in (
            "clients",
            "automation",
            "context",
            "recall",
            "learning",
            "resources",
            "review",
            "schedule",
            "intensity",
            "model_policy",
        )
        if field in answers
    )
    if operational_fields:
        raise ValueError(
            "onboard writes durable memory only; use ai-dememory setup wizard for: "
            + ", ".join(operational_fields)
        )
    projects = normalize_projects(answers.get("projects"))
    return {
        "reviewed_by": reviewed_by,
        **baseline,
        "projects": projects,
        "sensitivity": sensitivity,
    }


def normalize_operational_answers(
    answers: dict[str, Any],
    *,
    reviewed_by: str | None = None,
) -> dict[str, Any]:
    """Normalize bounded first-run policy without requiring personal memory."""
    if not isinstance(answers, dict):
        raise ValueError("setup input must be a JSON object")

    clients = clean_list(answers.get("clients")) or list(DEFAULT_CLIENTS)
    clients = unique(slugify(client, fallback="") for client in clients)
    clients = [client for client in clients if client]
    if not clients:
        raise ValueError("at least one client is required")

    automation_input = answers.get("automation") if isinstance(answers.get("automation"), dict) else {}
    intensity = clean_scalar(automation_input.get("intensity") or answers.get("intensity")) or DEFAULT_INTENSITY
    model_policy_name = (
        clean_scalar(automation_input.get("model_policy") or answers.get("model_policy"))
        or DEFAULT_MODEL_POLICY
    )
    profile = get_resource_profile(intensity)
    host_policy = get_model_policy(model_policy_name)
    automation = {
        "profile_version": 1,
        "intensity": profile.name,
        "model_policy": host_policy.name,
    }

    context_input = answers.get("context") if isinstance(answers.get("context"), dict) else {}
    recall_input = answers.get("recall") if isinstance(answers.get("recall"), dict) else {}
    learning_input = answers.get("learning") if isinstance(answers.get("learning"), dict) else {}
    resources_input = answers.get("resources") if isinstance(answers.get("resources"), dict) else {}
    schedule_input = answers.get("schedule") if isinstance(answers.get("schedule"), dict) else {}

    context = {
        "default_budget_tokens": bounded_from_limit(
            context_input.get("default_budget_tokens"),
            profile.context_budget_tokens,
            "context_budget_tokens",
        ),
        "include_working_memory": clean_bool(context_input.get("include_working_memory"), True),
        "explain_results": clean_bool(context_input.get("explain_results"), False),
    }
    default_budget = bounded_from_limit(
        recall_input.get("default_budget_tokens"),
        profile.recall_budget_tokens,
        "recall_budget_tokens",
    )
    baseline_budget = bounded_int(
        recall_input.get("baseline_budget_tokens"),
        min(profile.baseline_budget_tokens, default_budget),
        int(HARD_LIMITS["baseline_budget_tokens"]["minimum"]),
        min(default_budget, int(HARD_LIMITS["baseline_budget_tokens"]["maximum"])),
    )
    recall = {
        "enabled": clean_bool(recall_input.get("enabled"), profile.recall_enabled),
        "per_turn": clean_bool(recall_input.get("per_turn"), profile.recall_per_turn),
        "default_budget_tokens": default_budget,
        "baseline_budget_tokens": baseline_budget,
        "max_keywords": bounded_from_limit(
            recall_input.get("max_keywords"),
            profile.max_keywords,
            "max_keywords",
        ),
        "project_from_cwd": clean_bool(recall_input.get("project_from_cwd"), True),
        "min_relevance_score": bounded_float(
            recall_input.get("min_relevance_score"),
            profile.min_relevance_score,
            0.0,
            1.0,
        ),
        "hook_public_only": clean_bool(recall_input.get("hook_public_only"), True),
    }
    requested_learning_proposals = clean_bool(
        learning_input.get("session_proposals"),
        host_policy.session_proposals,
    )
    if requested_learning_proposals and not host_policy.session_proposals:
        raise ValueError("learning.session_proposals requires model_policy=proposals")
    learning = {
        "hook_metadata": clean_bool(learning_input.get("hook_metadata"), profile.hook_metadata),
        "session_proposals": requested_learning_proposals,
        "clients": clients,
    }
    resources = {
        "provider_file_limit": bounded_from_limit(
            resources_input.get("provider_file_limit"),
            profile.provider_file_limit,
            "provider_file_limit",
        ),
        "provider_max_file_bytes": bounded_from_limit(
            resources_input.get("provider_max_file_bytes"),
            profile.provider_max_file_bytes,
            "provider_max_file_bytes",
        ),
        "provider_scan_entries": bounded_from_limit(
            resources_input.get("provider_scan_entries"),
            profile.provider_scan_entries,
            "provider_scan_entries",
        ),
        "maintenance_report_retention": bounded_from_limit(
            resources_input.get("maintenance_report_retention"),
            profile.maintenance_report_retention,
            "maintenance_report_retention",
        ),
        "maintenance_timeout_seconds": bounded_from_limit(
            resources_input.get("maintenance_timeout_seconds"),
            profile.maintenance_timeout_seconds,
            "maintenance_timeout_seconds",
        ),
        "mcp_idle_timeout_seconds": bounded_from_limit(
            resources_input.get("mcp_idle_timeout_seconds"),
            profile.mcp_idle_timeout_seconds,
            "mcp_idle_timeout_seconds",
        ),
        "hook_capture_max_pending": bounded_from_limit(
            resources_input.get("hook_capture_max_pending"),
            profile.hook_capture_max_pending,
            "hook_capture_max_pending",
        ),
    }
    schedule_mode = normalize_schedule_mode(clean_scalar(schedule_input.get("mode")) or "installed")
    schedule_image = clean_scalar(schedule_input.get("image")) or "ai-dememory:local"
    if schedule_mode == "docker" and not immutable_docker_image(schedule_image):
        raise ValueError("setup Docker schedules require an immutable repo@sha256:<digest> image")
    schedule = {
        "enabled": False,
        "daily_enabled": clean_bool(schedule_input.get("daily_enabled"), profile.daily_enabled),
        "weekly_enabled": clean_bool(schedule_input.get("weekly_enabled"), profile.weekly_enabled),
        "daily_time": normalize_time(clean_scalar(schedule_input.get("daily_time")) or "03:00", "daily_time"),
        "weekly_day": normalize_weekday(clean_scalar(schedule_input.get("weekly_day")) or "SUN"),
        "weekly_time": normalize_time(clean_scalar(schedule_input.get("weekly_time")) or "04:00", "weekly_time"),
        "mode": schedule_mode,
        "image": schedule_image,
    }
    review = review_mode_config_values(host_policy.review_mode, reviewed_by)
    return {
        "reviewed_by": reviewed_by,
        "clients": clients,
        "automation": automation,
        "context": context,
        "recall": recall,
        "learning": learning,
        "resources": resources,
        "schedule": schedule,
        "review": review,
    }


def onboarding_resource_policy(answers: dict[str, Any]) -> dict[str, Any]:
    profile = get_resource_profile(str(answers["automation"]["intensity"]))
    host_policy = get_model_policy(str(answers["automation"]["model_policy"]))
    recall = answers["recall"]
    schedule = answers["schedule"]
    return {
        "profile_version": answers["automation"]["profile_version"],
        "intensity": profile.name,
        "model_policy": host_policy.name,
        "summary": profile.summary,
        "recommended_for": profile.recommended_for,
        "mcp_profile": profile.mcp_profile,
        "automatic_recall_max_tokens_per_eligible_turn": (
            recall["default_budget_tokens"]
            if recall["enabled"] and recall["per_turn"]
            else 0
        ),
        "manual_context_default_tokens": answers["context"]["default_budget_tokens"],
        "estimated_local_runs_per_week": (
            int(schedule["daily_enabled"]) * 7 + int(schedule["weekly_enabled"])
        ),
        "scheduler_image_immutable": (
            schedule["mode"] != "docker" or immutable_docker_image(str(schedule["image"]))
        ),
        "runtime_model_calls_per_maintenance_run": 0,
        "runtime_embedding_calls_per_maintenance_run": 0,
        "resources": answers["resources"],
        "host_model": {
            "review_mode": host_policy.review_mode,
            "session_proposals": answers["learning"]["session_proposals"],
            "runtime_model_calls": 0,
            "runtime_embedding_calls": 0,
            "durable_auto_promotion": False,
        },
        "hard_limits": HARD_LIMITS,
    }


def integration_plan(root: Path, answers: dict[str, Any]) -> dict[str, Any]:
    profile = get_resource_profile(str(answers["automation"]["intensity"]))
    mcp_configs: dict[str, object] = {}
    hook_configs: dict[str, object] = {}
    skipped_clients: list[str] = []
    for client in answers["clients"]:
        if client in {"codex", "claude", "generic"}:
            mcp_configs[client] = build_mcp_config(
                client,
                "installed",
                root,
                profile=profile.mcp_profile,
                idle_timeout_seconds=int(answers["resources"]["mcp_idle_timeout_seconds"]),
            )
        else:
            skipped_clients.append(client)
        if client in {"codex", "claude"}:
            hook_configs[client] = hook_config(client, root=root)
    schedule = answers["schedule"]
    schedule_plan_command = [
        "ai-dememory",
        "schedule",
        "plan",
        "--intensity",
        profile.name,
        "--mode",
        str(schedule["mode"]),
    ]
    if schedule["mode"] == "docker":
        schedule_plan_command.extend(["--image", str(schedule["image"])])
    schedule_plan_command.append("--json")
    return {
        "vault_bound": True,
        "binding_source": "absolute_onboarding_root",
        "cross_repo_ready": True,
        "mcp_profile": profile.mcp_profile,
        "mcp_configs": mcp_configs,
        "hook_configs": hook_configs,
        "skipped_clients": skipped_clients,
        "installs_client_config": False,
        "installs_hooks": False,
        "installs_schedules": False,
        "schedule_plan_command": schedule_plan_command,
        "scheduler_image_immutable": (
            schedule["mode"] != "docker" or immutable_docker_image(str(schedule["image"]))
        ),
        "next_actions": [
            "Copy only the generated MCP config for the client you use.",
            "Preview the vault-bound hook config before installing hooks.",
            "Review the schedule plan and fingerprint before an explicit scheduler apply.",
        ],
    }


def render_documents(answers: dict[str, Any]) -> dict[str, str]:
    today = date.today()
    documents: dict[str, str] = {}
    titles = {
        "values": "Personal Values",
        "preferences": "Working Preferences",
        "recommendations": "Agent Recommendations",
    }
    for kind in BASELINE_KINDS:
        relative_path = f"memories/durable/onboarding-{kind}.md"
        documents[relative_path] = render_memory(
            memory_id=f"onboarding_{kind}",
            title=titles[kind],
            memory_type="durable",
            scope="personal",
            project=None,
            tags=["onboarding", kind],
            aliases=[kind, titles[kind].lower()],
            reviewed_by=answers["reviewed_by"],
            sensitivity=answers["sensitivity"],
            review_after=today + timedelta(days=180),
            body="\n".join(f"- {item}" for item in answers[kind]),
        )

    for project in answers["projects"]:
        slug = slugify(project["name"])
        lines = [f"- Project: `{project['name']}`"]
        if project["paths"]:
            lines.extend(["", "## Paths", "", *[f"- `{item}`" for item in project["paths"]]])
        if project["keywords"]:
            lines.extend(["", "## Recall keywords", "", *[f"- {item}" for item in project["keywords"]]])
        if project["recommendations"]:
            lines.extend(["", "## Recommendations", "", *[f"- {item}" for item in project["recommendations"]]])
        documents[f"memories/projects/{slug}.md"] = render_memory(
            memory_id=f"project_{slug}",
            title=f"{project['name']} Project Profile",
            memory_type="project",
            scope="project",
            project=project["name"],
            tags=unique(["onboarding", "project", slug, *project["keywords"]]),
            aliases=unique([project["name"], *project["aliases"], *project["paths"]]),
            reviewed_by=answers["reviewed_by"],
            sensitivity=answers["sensitivity"],
            review_after=today + timedelta(days=90),
            body="\n".join(lines),
        )

    for path, content in documents.items():
        if scan_text(content, f"<onboarding:{path}>"):
            raise ValueError(f"onboarding content rejected by secret scan: {path}")
    return documents


def render_memory(
    *,
    memory_id: str,
    title: str,
    memory_type: str,
    scope: str,
    project: str | None,
    tags: list[str],
    aliases: list[str],
    reviewed_by: str,
    sensitivity: str,
    review_after: date,
    body: str,
) -> str:
    today = date.today().isoformat()
    project_value = "null" if project is None else yaml_string(project)
    return f"""---
id: {memory_id}
title: {yaml_string(title)}
type: {memory_type}
reviewed: true
reviewed_by: {yaml_string(reviewed_by)}
reviewed_at: {today}
status: active
scope: {scope}
project: {project_value}
tags: {yaml_list(tags)}
aliases: {yaml_list(aliases)}
created_at: {today}
updated_at: {today}
confidence: 1.0
sensitivity: {sensitivity}
source:
  kind: manual
  ref: onboard
pin: true
decay: none
review_after: {review_after.isoformat()}
---

# {title}

{body}
"""


def normalize_projects(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("projects must be a list")
    output: list[dict[str, Any]] = []
    project_slugs: set[str] = set()
    for item in value:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            raise ValueError("each project must be an object or name")
        name = clean_scalar(item.get("name"))
        if not name:
            raise ValueError("each project requires a name")
        project_slug = slugify(name)
        if project_slug in project_slugs:
            raise ValueError(f"project names must have unique normalized slugs: {project_slug}")
        project_slugs.add(project_slug)
        output.append(
            {
                "name": name,
                "aliases": clean_list(item.get("aliases")),
                "paths": clean_list(item.get("paths")),
                "keywords": clean_list(item.get("keywords")),
                "recommendations": clean_list(item.get("recommendations")),
            }
        )
    return output


def merge_onboarding_config(
    text: str,
    answers: dict[str, Any],
    *,
    preserve_schedule: bool = False,
) -> str:
    sections = {
        "automation": answers["automation"],
        "review": answers["review"],
        "context": answers["context"],
        "recall": {**answers["recall"], "clients": answers["clients"]},
        "learning": answers["learning"],
        "resources": answers["resources"],
    }
    if not preserve_schedule:
        sections["schedule"] = answers["schedule"]
    updated = text.rstrip() + ("\n" if text.strip() else "")
    for name, values in sections.items():
        updated = merge_toml_section(updated, name, values)
    if scan_text(updated, "<onboarding-config>"):
        raise ValueError("onboarding config rejected by secret scan")
    return updated.rstrip() + "\n"


def merge_toml_section(text: str, section: str, values: dict[str, Any]) -> str:
    lines = text.splitlines()
    header = f"[{section}]"
    start = next((index for index, line in enumerate(lines) if line.strip() == header), None)
    rendered = [f"{key} = {toml_value(value)}" for key, value in values.items()]
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([header, *rendered])
        return "\n".join(lines) + "\n"
    end = next(
        (index for index in range(start + 1, len(lines)) if re.fullmatch(r"\s*\[[^]]+\]\s*", lines[index])),
        len(lines),
    )
    managed = set(values)
    body = [
        line
        for line in lines[start + 1 : end]
        if not ("=" in line and line.split("=", 1)[0].strip() in managed)
    ]
    while body and not body[-1].strip():
        body.pop()
    lines[start:end] = [header, *body, *rendered, *([""] if end < len(lines) else [])]
    return "\n".join(lines) + "\n"


def planned_write(root: Path, path: Path, content: str, *, kind: str, allow_update: bool) -> dict[str, Any]:
    if path.exists():
        current_bytes = path.read_bytes()
        current = current_bytes.decode("utf-8")
        status = "unchanged" if current == content else ("update" if allow_update else "conflict")
        current_sha256: str | None = hashlib.sha256(current_bytes).hexdigest()
    else:
        status = "create"
        current_sha256 = None
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": kind,
        "status": status,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "current_sha256": current_sha256,
    }


def safe_target(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("onboarding paths must stay inside the vault")
    target = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if path_is_link_like(current):
            raise ValueError(f"onboarding path must not contain symlinks or junctions: {relative_path}")
    return target


def current_file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file() or path_is_link_like(path):
        raise ValueError(f"onboarding target is not a safe regular file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_write_precondition(path: Path, expected_sha256: object) -> None:
    expected = str(expected_sha256) if isinstance(expected_sha256, str) else None
    if current_file_sha256(path) != expected:
        raise ValueError(f"onboarding target changed after review: {path}")


def atomic_batch_write(batch: list[tuple[Path, str, bool, str | None]]) -> None:
    """Stage every file first, then commit with best-effort rollback on failure."""
    staged: list[tuple[Path, Path, bool, str | None]] = []
    states: list[dict[str, Any]] = []
    committed = False
    try:
        # Validate the complete reviewed snapshot before creating directories or
        # temporary files. Per-target checks below still close races that occur
        # after this batch-wide preflight.
        for path, _, _, expected_sha256 in batch:
            assert_write_precondition(path, expected_sha256)

        for path, content, allow_update, expected_sha256 in batch:
            assert_write_precondition(path, expected_sha256)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and not allow_update and path.read_text(encoding="utf-8") != content:
                raise FileExistsError(f"refusing to overwrite canonical memory: {path}")
            handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            temp_path = Path(temp_name)
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            staged.append((path, temp_path, allow_update, expected_sha256))

        for path, temp_path, allow_update, expected_sha256 in staged:
            state: dict[str, Any] = {"path": path, "backup": None, "installed": False}
            states.append(state)
            assert_write_precondition(path, expected_sha256)
            if path.exists():
                if not allow_update:
                    if path.read_text(encoding="utf-8") == temp_path.read_text(encoding="utf-8"):
                        temp_path.unlink()
                        continue
                    raise FileExistsError(f"refusing to overwrite canonical memory: {path}")
                backup = path.with_name(f".{path.name}.{os.getpid()}.bak")
                if backup.exists():
                    raise FileExistsError(f"onboarding backup path already exists: {backup}")
                os.replace(path, backup)
                state["backup"] = backup
                if current_file_sha256(backup) != expected_sha256:
                    os.replace(backup, path)
                    state["backup"] = None
                    raise ValueError(f"onboarding target changed during apply: {path}")
            os.replace(temp_path, path)
            state["installed"] = True
        committed = True
    except Exception as original_error:
        rollback_errors: list[str] = []
        for state in reversed(states):
            path = state["path"]
            backup = state["backup"]
            try:
                if state["installed"] and path.exists():
                    path.unlink()
                if isinstance(backup, Path) and backup.exists():
                    os.replace(backup, path)
            except OSError as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                "onboarding rollback incomplete; preserve any .bak files and review: "
                + "; ".join(rollback_errors)
            ) from original_error
        raise
    finally:
        for _, temp_path, _, _ in staged:
            if temp_path.exists():
                temp_path.unlink()
        if committed:
            for state in states:
                backup = state["backup"]
                if isinstance(backup, Path) and backup.exists():
                    try:
                        backup.unlink()
                    except OSError:
                        pass


def load_answers(args: argparse.Namespace) -> dict[str, Any]:
    sources = sum(bool(value) for value in (args.input_json, args.input_file, args.stdin))
    if sources > 1:
        raise ValueError("choose only one of --input-json, --input-file, or --stdin")
    if args.input_json:
        data = json.loads(args.input_json)
    elif args.input_file:
        data = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
    elif args.stdin:
        data = json.load(sys.stdin)
    elif args.reviewed_by or args.value or args.preference or args.recommendation or args.project:
        data = {
            "reviewed_by": args.reviewed_by,
            "values": args.value,
            "preferences": args.preference,
            "recommendations": args.recommendation,
            "projects": [parse_project_flag(item) for item in args.project],
        }
    else:
        data = interactive_answers()
    if not isinstance(data, dict):
        raise ValueError("onboarding input must be a JSON object")
    return data


def reject_personal_setup_flags(args: argparse.Namespace) -> None:
    fields = [
        name
        for name, present in (
            ("--reviewed-by", args.reviewed_by is not None),
            ("--value", bool(args.value)),
            ("--preference", bool(args.preference)),
            ("--recommendation", bool(args.recommendation)),
            ("--project", bool(args.project)),
        )
        if present
    ]
    if fields:
        raise ValueError(
            "setup wizard does not accept personal baseline flags; use ai-dememory onboard for: "
            + ", ".join(fields)
        )


def reject_operational_onboarding_flags(args: argparse.Namespace) -> None:
    fields = [
        name
        for name, present in (
            ("--client", bool(args.client)),
            ("--budget-tokens", args.budget_tokens is not None),
            ("--intensity", args.intensity is not None),
            ("--model-policy", args.model_policy is not None),
            ("--enable-auto-learning", args.enable_auto_learning),
        )
        if present
    ]
    if fields:
        raise ValueError(
            "onboard accepts durable baseline fields only; use ai-dememory setup wizard for: "
            + ", ".join(fields)
        )


def operational_answers_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Build non-personal setup answers from explicit flags and safe defaults."""
    learning: dict[str, Any] = {}
    if args.enable_auto_learning:
        learning["session_proposals"] = True
    return {
        "clients": args.client or list(DEFAULT_CLIENTS),
        "automation": {
            "intensity": args.intensity or DEFAULT_INTENSITY,
            "model_policy": args.model_policy or DEFAULT_MODEL_POLICY,
        },
        "recall": {"default_budget_tokens": args.budget_tokens} if args.budget_tokens else {},
        "learning": learning,
    }


def load_operational_answers(args: argparse.Namespace) -> dict[str, Any]:
    sources = sum(bool(value) for value in (args.input_json, args.input_file, args.stdin))
    if sources > 1:
        raise ValueError("choose only one of --input-json, --input-file, or --stdin")
    if args.input_json:
        data = json.loads(args.input_json)
    elif args.input_file:
        data = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
    elif args.stdin:
        data = json.load(sys.stdin)
    else:
        data = operational_answers_from_args(args)
    if not isinstance(data, dict):
        raise ValueError("setup input must be a JSON object")
    if args.intensity or args.model_policy:
        automation = data.get("automation")
        automation = dict(automation) if isinstance(automation, dict) else {}
        if args.intensity:
            automation["intensity"] = args.intensity
        if args.model_policy:
            automation["model_policy"] = args.model_policy
        data["automation"] = automation
    return data


def interactive_setup_answers(args: argparse.Namespace) -> dict[str, Any]:
    """Capture one guided operational plan without personal memory."""
    if not sys.stdin.isatty():
        raise ValueError("non-interactive setup requires --json or --dry-run")
    data = operational_answers_from_args(args)
    automation = dict(data["automation"])
    print(
        "Intensity: minimal (weekly/manual), balanced (recommended), "
        "active (maximum bounded budgets)."
    )
    if args.intensity:
        print(f"Intensity selected by command line: {args.intensity}")
    else:
        automation["intensity"] = input("Intensity [balanced]: ").strip().lower() or DEFAULT_INTENSITY
    print("Host model policy: off (zero advisory work), advisory, proposals (review-first only).")
    if args.model_policy:
        print(f"Host model policy selected by command line: {args.model_policy}")
    else:
        automation["model_policy"] = input("Host model policy [off]: ").strip().lower() or DEFAULT_MODEL_POLICY
    data["automation"] = automation

    if automation["model_policy"] == "proposals" and not args.enable_auto_learning:
        response = input("Create review-first Stop learning proposals? [Y/n]: ").strip().lower()
        data["learning"] = {"session_proposals": response not in {"n", "no"}}
    elif automation["model_policy"] != "proposals":
        data["learning"] = {"session_proposals": False}

    return data


def interactive_baseline_answers() -> dict[str, Any]:
    reviewed_by = input("Reviewer name: ").strip()
    values = prompt_list("Values (semicolon-separated): ")
    preferences = prompt_list("Working preferences (semicolon-separated): ")
    recommendations = prompt_list("Recommendations for agents (semicolon-separated): ")
    project_name = input("Primary project name (optional): ").strip()
    return {
        "reviewed_by": reviewed_by,
        "values": values,
        "preferences": preferences,
        "recommendations": recommendations,
        "projects": [{"name": project_name}] if project_name else [],
    }


def interactive_answers() -> dict[str, Any]:
    if not sys.stdin.isatty():
        raise ValueError("non-interactive onboarding requires JSON/stdin or explicit flags")
    return interactive_baseline_answers()


def prompt_list(prompt: str) -> list[str]:
    return [item.strip() for item in input(prompt).split(";") if item.strip()]


def parse_project_flag(value: str) -> dict[str, Any]:
    parts = [item.strip() for item in value.split("|")]
    return {
        "name": parts[0],
        "paths": [parts[1]] if len(parts) > 1 and parts[1] else [],
        "aliases": [item.strip() for item in parts[2].split(",") if item.strip()] if len(parts) > 2 else [],
    }


def clean_scalar(value: Any) -> str:
    return " ".join(str(value).split()).strip() if value is not None else ""


def clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("onboarding list fields must be arrays")
    return unique(clean_scalar(item) for item in value if clean_scalar(item))


def clean_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer")
    parsed = int(value)
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"integer must be between {minimum} and {maximum}")
    return parsed


def bounded_from_limit(value: Any, default: int, limit_name: str) -> int:
    limits = HARD_LIMITS[limit_name]
    return bounded_int(value, default, int(limits["minimum"]), int(limits["maximum"]))


def bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    if value is None:
        return default
    parsed = float(value)
    if isinstance(value, bool) or not math.isfinite(parsed) or parsed < minimum or parsed > maximum:
        raise ValueError(f"number must be between {minimum} and {maximum}")
    return parsed


def normalize_time(value: str, field: str) -> str:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"{field} must use HH:MM 24-hour time")
    hour, minute = (int(part) for part in parts)
    if hour > 23 or minute > 59:
        raise ValueError(f"{field} must use HH:MM 24-hour time")
    return f"{hour:02d}:{minute:02d}"


def normalize_weekday(value: str) -> str:
    weekday = value.strip().upper()
    if weekday not in {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"}:
        raise ValueError("weekly_day must be one of SUN, MON, TUE, WED, THU, FRI, SAT")
    return weekday


def normalize_schedule_mode(value: str) -> str:
    mode = value.strip().lower()
    if mode not in {"installed", "docker"}:
        raise ValueError("schedule mode must be installed or docker")
    return mode


def unique(values: Any) -> list[Any]:
    return list(dict.fromkeys(values))


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    return "[" + ", ".join(yaml_string(value) for value in values) + "]"


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    return str(value)


def build_parser(*, mode: str = "onboard") -> argparse.ArgumentParser:
    if mode not in {"onboard", "operational"}:
        raise ValueError(f"unsupported onboarding mode: {mode}")
    operational = mode == "operational"
    parser = argparse.ArgumentParser(
        description=(
            "Preview/apply operational vault configuration without personal memory."
            if operational
            else "Preview/apply an explicit reviewed personal baseline without operating policy."
        )
    )
    parser.add_argument("--root", default=None, help="Memory vault root.")
    payload_name = "setup" if operational else "onboarding"
    parser.add_argument("--input-json", default=None, help=f"Inline {payload_name} JSON object.")
    parser.add_argument("--input-file", default=None, help=f"Path to {payload_name} JSON.")
    parser.add_argument("--stdin", action="store_true", help=f"Read {payload_name} JSON from stdin.")
    personal_help = argparse.SUPPRESS if operational else None
    operational_help = None if operational else argparse.SUPPRESS
    parser.add_argument("--reviewed-by", default=None, help=personal_help)
    parser.add_argument("--value", action="append", default=[], help=personal_help)
    parser.add_argument("--preference", action="append", default=[], help=personal_help)
    parser.add_argument("--recommendation", action="append", default=[], help=personal_help)
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help=argparse.SUPPRESS if operational else "name|path|alias1,alias2",
    )
    parser.add_argument("--client", action="append", default=[], help=operational_help)
    parser.add_argument("--budget-tokens", type=int, default=None, help=operational_help)
    parser.add_argument("--intensity", choices=profile_names(), default=None, help=operational_help)
    parser.add_argument("--model-policy", choices=model_policy_names(), default=None, help=operational_help)
    parser.add_argument("--enable-auto-learning", action="store_true", help=operational_help)
    parser.add_argument("--apply", action="store_true", help="Apply a plan whose preview fingerprint was reviewed.")
    parser.add_argument("--expect-plan-sha256", default=None, help="Fingerprint returned by the reviewed preview.")
    parser.add_argument("--dry-run", action="store_true", help="Explicit preview alias; preview is the default.")
    parser.add_argument("--json", action="store_true")
    return parser


def uses_interactive_answers(args: argparse.Namespace) -> bool:
    return not any(
        (
            args.input_json,
            args.input_file,
            args.stdin,
            args.reviewed_by,
            args.value,
            args.preference,
            args.recommendation,
            args.project,
        )
    )


def print_human_result(result: dict[str, Any], *, include_apply_hint: bool = True) -> None:
    action = "Applied" if result["applied"] else "Preview"
    print(f"{action}: {result['created_count']} create, {result['updated_count']} update, "
          f"{result['unchanged_count']} unchanged, {result['conflict_count']} conflict")
    if result.get("setup_scope") == "operational":
        print("Scope: operational vault configuration only; no durable personal memory.")
    else:
        print("Scope: reviewed durable baseline only; operational vault configuration is unchanged.")
    if result.get("setup_scope") == "operational":
        policy = result["resource_policy"]
        print(
            f"Intensity: {policy['intensity']}; model policy: {policy['model_policy']}; "
            f"automatic recall ceiling: {policy['automatic_recall_max_tokens_per_eligible_turn']} tokens"
        )
        print(
            "ai-dememory runtime model/embedding calls per maintenance run: 0/0; "
            f"estimated local jobs/week after explicit install: {policy['estimated_local_runs_per_week']}"
        )
        resources = policy["resources"]
        print(
            f"MCP profile/idle lease: {policy['mcp_profile']}/"
            f"{resources['mcp_idle_timeout_seconds']}s; context/recall ceilings: "
            f"{policy['manual_context_default_tokens']}/"
            f"{policy['automatic_recall_max_tokens_per_eligible_turn']} tokens"
        )
        print(
            f"Provider/maintenance ceilings: {resources['provider_file_limit']} files, "
            f"{resources['provider_max_file_bytes']} bytes/file, "
            f"{resources['provider_scan_entries']} scanned entries, "
            f"{resources['maintenance_timeout_seconds']}s per maintenance run"
        )
    else:
        print(f"Reviewed by: {result['reviewed_by']}")
    for item in result["writes"]:
        print(f"- {item['status']}: {item['path']}")
    if not result["applied"] and result.get("can_apply"):
        fingerprint = result["plan_sha256"]
        print(f"plan_sha256: {fingerprint}")
        if include_apply_hint:
            print(
                "Next: rerun the same answers with "
                f"--apply --expect-plan-sha256 {fingerprint}"
            )


def print_guided_next_actions(result: dict[str, Any]) -> None:
    root = json.dumps(str(result["root"]), ensure_ascii=False)
    print("Next actions (nothing else was installed automatically):")
    print(f"- ai-dememory --root {root} doctor")
    print(f"- ai-dememory --root {root} index")
    print(f"- ai-dememory --root {root} setup health --json")
    clients = result.get("clients")
    if isinstance(clients, list):
        for client in clients:
            if client in {"codex", "claude", "generic"}:
                print(f"- ai-dememory mcp-config --root {root} --client {client}")
    print("- Review hook and scheduler previews separately before installing either one.")
    if result.get("setup_scope") == "operational":
        print(f"- Optional durable baseline: ai-dememory --root {root} onboard")


def main(argv: list[str] | None = None, *, mode: str = "onboard") -> int:
    operational_guided = mode == "operational"
    parser = build_parser(mode=mode)
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive")
    if args.json and uses_interactive_answers(args) and not operational_guided:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "JSON onboarding is non-interactive; provide --input-json, --input-file, "
                        "--stdin, or explicit baseline flags"
                    ),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1
    guided_interactive = (
        operational_guided
        and not args.apply
        and not args.dry_run
        and not args.json
        and not any((args.input_json, args.input_file, args.stdin))
    )
    try:
        root = repo_root(args.root)
        if operational_guided:
            reject_personal_setup_flags(args)
        else:
            reject_operational_onboarding_flags(args)
        if guided_interactive:
            answers = interactive_setup_answers(args)
            plan_builder = operational_setup_plan
            plan_applier = apply_operational_setup
        elif operational_guided:
            answers = load_operational_answers(args)
            plan_builder = operational_setup_plan
            plan_applier = apply_operational_setup
        else:
            answers = load_answers(args)
            plan_builder = onboarding_plan
            plan_applier = apply_onboarding
        result = (
            plan_applier(root, answers, args.expect_plan_sha256)
            if args.apply
            else plan_builder(root, answers)
        )
        result.setdefault("applied", False)
        if guided_interactive:
            print_human_result(result, include_apply_hint=False)
            if not result.get("can_apply"):
                raise ValueError("guided setup cannot apply until every conflict is reviewed")
            scope = "operational setup" if result.get("setup_scope") == "operational" else "reviewed onboarding"
            try:
                confirmation = input(
                    f"Apply this exact {scope} plan ({result['plan_sha256']}) now? [y/N]: "
                )
            except EOFError:
                confirmation = ""
            if confirmation.strip().lower() not in {"y", "yes"}:
                print("Setup was not applied. The existing vault is unchanged; setup is incomplete.")
                return GUIDED_DECLINED_EXIT_CODE
            result = plan_applier(root, answers, str(result["plan_sha256"]))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        else:
            print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True, **result}, indent=2, ensure_ascii=False))
    else:
        if not guided_interactive:
            print_human_result(result)
        else:
            print_human_result(result, include_apply_hint=False)
            print_guided_next_actions(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
