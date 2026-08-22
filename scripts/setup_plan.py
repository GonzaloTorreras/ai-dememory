#!/usr/bin/env python3
"""Build a read-only review plan for local ai-dememory setup."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (SOURCE_ROOT / "pyproject.toml").is_file() and str(SOURCE_ROOT) not in sys.path:
    # A direct source-checkout command must not mix with an older installed
    # ai_dememory_tool package that happens to appear earlier on sys.path.
    sys.path.insert(0, str(SOURCE_ROOT))

from ai_dememory_tool.argument_safety import (  # noqa: E402
    reject_duplicate_options,
    validate_docker_image_argument,
)

from context_memory import context_defaults_status
from command_render import render_copy_command
from maintenance import generated_packet_archive_summary, maintenance_artifact_targets, maintenance_status
from hook_event import hook_status_summary
from manual_acceptance import acceptance_plan
from memorylib import repo_root
from provider_import import provider_setup_plan
from recall_fixtures import recall_fixture_review_plan
from resource_policy import (
    DEFAULT_INTENSITY,
    DEFAULT_MODEL_POLICY,
    model_policy_catalog,
    model_policy_names,
    profile_catalog,
    profile_names,
    resolved_resource_policy,
)
from runtime_identity import current_package_version
from schedule_memory import immutable_docker_image, schedule_environment, schedule_status
from validate_memory import validate_repo_result
from vector_gate import evaluate_vector_readiness


CLIENTS = ("codex", "claude", "generic")
MODES = ("installed", "docker", "both")


PACKAGE_VERSION = current_package_version()


def selected_clients(client: str) -> list[str]:
    return list(CLIENTS) if client == "all" else [client]


def _root_bound_command(command: str, root: Path, *arguments: str) -> list[str]:
    """Build one generated CLI command with its sole global vault binding."""
    if any(argument == "--root" or argument.startswith("--root=") for argument in arguments):
        raise ValueError("generated command arguments must not contain a second --root binding")
    return [command, "--root", str(root.expanduser().resolve()), *arguments]


def _bind_nested_plan_commands(value: Any, *, command: str, root: Path) -> Any:
    """Bind command arrays returned by a nested setup-plan producer to *root*.

    ``provider_setup_plan`` is intentionally reusable on its own, but its
    command arrays become part of this root-bound setup plan when embedded
    here.  Only arrays whose executable is the configured command are changed;
    explanatory lists and other metadata remain untouched.
    """
    if isinstance(value, list):
        if value and all(isinstance(item, str) for item in value):
            if value[0] == command:
                root_indexes = [
                    index
                    for index, argument in enumerate(value)
                    if argument == "--root" or argument.startswith("--root=")
                ]
                if not root_indexes:
                    return _root_bound_command(command, root, *value[1:])
                if len(value) < 3 or root_indexes != [1] or value[1] != "--root":
                    raise ValueError(
                        "nested generated command must use exactly one global --root binding"
                    )
                try:
                    nested_root = Path(value[2]).expanduser().resolve()
                    expected_root = root.expanduser().resolve()
                except (OSError, RuntimeError, ValueError) as exc:
                    raise ValueError("nested generated command has an invalid --root binding") from exc
                if nested_root != expected_root:
                    raise ValueError("nested generated command is bound to a different vault root")
                return list(value)
            return list(value)
        return [
            _bind_nested_plan_commands(item, command=command, root=root)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _bind_nested_plan_commands(item, command=command, root=root)
            for key, item in value.items()
        }
    return value


def mcp_config_command(
    command: str,
    client: str,
    mode: str,
    root: Path,
    image: str,
    idle_timeout_seconds: int,
    profile: str,
) -> list[str]:
    args = _root_bound_command(
        command,
        root,
        "mcp-config",
        "--client",
        client,
        "--mode",
        mode,
        "--idle-timeout-seconds",
        str(idle_timeout_seconds),
        "--profile",
        profile,
    )
    if mode == "docker":
        args.extend(["--image", image])
    return args


def setup_plan(
    root: Path,
    client: str = "all",
    mode: str = "installed",
    command: str = "ai-dememory",
    image: str = "ai-dememory:local",
    intensity: str = DEFAULT_INTENSITY,
    model_policy: str = DEFAULT_MODEL_POLICY,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if mode in {"docker", "both"}:
        image = validate_docker_image_argument(image)
    clients = selected_clients(client)
    modes = ["installed", "docker"] if mode == "both" else [mode]
    resource_policy = resolved_resource_policy(root, intensity=intensity, model_policy=model_policy)
    idle_timeout_seconds = int(resource_policy["resources"]["mcp_idle_timeout_seconds"])
    docker_schedule_installable = immutable_docker_image(image)
    plan_command = lambda *arguments: _root_bound_command(command, root, *arguments)
    commands: dict[str, Any] = {
        "setup_preview": plan_command(
            "setup",
            "wizard",
            "--intensity",
            intensity,
            "--model-policy",
            model_policy,
            "--json",
        ),
        "setup_apply": plan_command(
            "setup",
            "wizard",
            "--intensity",
            intensity,
            "--model-policy",
            model_policy,
            "--apply",
            "--expect-plan-sha256",
            "<preview plan_sha256>",
            "--json",
        ),
        "optional_onboarding_preview": plan_command(
            "onboard",
            "--input-file",
            "<reviewed-onboarding.json>",
            "--json",
        ),
        "optional_onboarding_apply": plan_command(
            "onboard",
            "--input-file",
            "<reviewed-onboarding.json>",
            "--apply",
            "--expect-plan-sha256",
            "<preview plan_sha256>",
            "--json",
        ),
        "doctor": plan_command("doctor"),
        "index": plan_command("index"),
        "graph": plan_command("graph"),
        "provider_plan": plan_command("providers", "plan", "--json"),
        "hook_install_dry_run": plan_command("hooks", "install", "--client", "all", "--dry-run"),
        "schedule_environment": plan_command("schedule", "doctor", "--json"),
        "schedule_plan": plan_command("schedule", "plan", "--intensity", intensity, "--json"),
        "schedule_dry_run": plan_command("schedule", "setup", "--intensity", intensity, "--dry-run"),
        "schedule_cron": plan_command("schedule", "cron", "--intensity", intensity),
        "docker_schedule_environment": plan_command(
            "schedule",
            "doctor",
            "--json",
            "--mode",
            "docker",
        ),
        "docker_schedule_plan": plan_command(
            "schedule",
            "plan",
            "--json",
            "--mode",
            "docker",
            "--intensity",
            intensity,
            "--image",
            image,
        ),
        "docker_schedule_dry_run": plan_command(
            "schedule",
            "setup",
            "--dry-run",
            "--intensity",
            intensity,
            "--mode",
            "docker",
            "--image",
            image,
        ) if docker_schedule_installable else [],
        "docker_schedule_cron": plan_command(
            "schedule",
            "cron",
            "--intensity",
            intensity,
            "--mode",
            "docker",
            "--image",
            image,
        ) if docker_schedule_installable else [],
        "daily_maintenance": plan_command("maintenance", "run", "--profile", "daily"),
        "weekly_maintenance": plan_command("maintenance", "run", "--profile", "weekly"),
        "acceptance_plan": plan_command("acceptance", "plan", "--json"),
        "generated_reports": {
            "recall_review_plan": plan_command("recall-fixtures", "review-plan", "--write-report"),
            "recall_review_packet": plan_command("recall-fixtures", "packet", "--write-report"),
            "manual_acceptance_plan": plan_command("acceptance", "plan", "--write-report"),
            "manual_acceptance_packet": plan_command("acceptance", "packet", "--write-report"),
            "hook_capture_review": plan_command("hooks", "captures", "--write-report"),
            "release_evidence": plan_command("release-evidence", "--write-report"),
        },
        "generated_archive_status": {
            "recall_review_packets": plan_command("recall-fixtures", "packet-archive-status", "--json"),
            "manual_acceptance_packets": plan_command("acceptance", "packet-archive-status", "--json"),
        },
        "generated_archive_retention": {
            "recall_review_packets": plan_command("recall-fixtures", "packet-archive-retention-plan", "--json"),
            "manual_acceptance_packets": plan_command("acceptance", "packet-archive-retention-plan", "--json"),
        },
    }
    commands["mcp_configs"] = [
        mcp_config_command(
            command,
            selected,
            selected_mode,
            root,
            image,
            idle_timeout_seconds,
            str(resource_policy["mcp_profile"]),
        )
        for selected_mode in modes
        for selected in clients
    ]
    commands["hook_configs"] = [
        plan_command("hooks", "config", "--client", selected)
        for selected in clients
        if selected in {"codex", "claude"}
    ]
    provider_plan = _bind_nested_plan_commands(
        provider_setup_plan(root, command=command),
        command=command,
        root=root,
    )
    result = {
        "root": str(root),
        "generated_by_version": PACKAGE_VERSION,
        "client": client,
        "mode": mode,
        "intensity": intensity,
        "model_policy": model_policy,
        "resource_policy": resource_policy,
        "resource_profiles": profile_catalog(),
        "model_policies": model_policy_catalog(),
        "mutates_system": False,
        "writes_files": False,
        "reads_provider_files": False,
        "writes_import_candidates": False,
        "installs_schedules": False,
        "installs_hooks": False,
        "docker_schedule_installable": docker_schedule_installable,
        "suggests_generated_reports": True,
        "suggests_generated_archive_status": True,
        "suggests_generated_archive_retention": True,
        "commands": commands,
        "provider_plan": provider_plan,
        "next_actions": [
            "After a successful setup, no further command is required; this plan remains a preview until you explicitly apply a reviewed fingerprint.",
            "Optional configuration: if you want these operational settings, preview the config-only wizard and review its selected intensity, hard caps, zero-runtime-model-call statement, and host-model policy before applying it.",
            "Optional diagnostics: doctor and setup health report local state; they are not setup requirements.",
            "Optional search: rebuild the index only after you add or review Markdown that you want searchable.",
            "Optional durable baseline: preview "
            + render_copy_command(plan_command("onboard"))
            + " only if you choose to record reviewed values, preferences, recommendations, or project aliases.",
            "Optional MCP: choose one client first, then copy only that generated config.",
            "Optional providers, hooks, and scheduling: preview their paths, config, or plan only if you choose those integrations; inspect before every explicit install.",
            "Optional reports and manual acceptance: generate or record them only when you need a review or release handoff after a human check.",
        ],
    }
    if not docker_schedule_installable:
        result["next_actions"].insert(
            0,
            "Optional Docker scheduling: Resolve the Docker image to sha256:<image-id> or repository@sha256:<digest> only if you intend to preview unattended Docker apply/cron commands.",
        )
    return result


def setup_health(
    root: Path,
    target_platform: str | None = None,
    mode: str = "installed",
) -> dict[str, Any]:
    schedule = schedule_status(root, target_platform=target_platform)
    effective_schedule_mode = (
        str(schedule.get("mode") or mode)
        if schedule.get("configured", False)
        else mode
    )
    schedule_env = schedule_environment(
        target_platform=target_platform,
        mode=effective_schedule_mode,
    )
    maintenance = maintenance_status(root)
    hooks = hook_status_summary(root)
    validation = validate_repo_result(root)
    recall_review = setup_health_recall_review(root)
    context_config = context_defaults_status(root)
    manual_acceptance = setup_health_manual_acceptance(root)
    vector_readiness = setup_health_vector_readiness(root)
    maintenance_preflight = setup_health_maintenance_preflight(root, maintenance)
    generated_packet_archives = setup_health_generated_packet_archives(root)
    resource_policy = resolved_resource_policy(root)
    review_due = maintenance["review_due"]
    conflict_review = maintenance["conflict_review"]
    review_recommendations = maintenance["review_recommendations"]
    artifact_freshness = maintenance.get("artifact_freshness", {})
    next_actions: list[str] = []
    if not bool(resource_policy.get("valid", False)):
        next_actions.append("Fix invalid automation/resource settings before enabling autonomous maintenance.")
    if not bool(validation.get("ok", False)):
        next_actions.append("Fix memory validation errors with `ai-dememory validate --json` before indexing or enabling schedules.")
    if not schedule_env["ready"]:
        missing = ", ".join(str(item) for item in schedule_env["required_missing"])
        next_actions.append(f"Install or choose a supported scheduler path for missing requirement(s): {missing}.")
    if not schedule["valid"]:
        next_actions.append("Fix persisted schedule config before installing or relying on maintenance schedules.")
    if not schedule["configured"]:
        next_actions.append("Review `ai-dememory schedule plan --json` before explicitly enabling autonomous maintenance.")
    elif not schedule.get("install_receipt_valid", False):
        next_actions.append("Reinstall the scheduler from a reviewed fingerprint because its install receipt is missing or drifted.")
    elif not schedule.get("host_state_verified", False):
        next_actions.append("Run `ai-dememory schedule status` to verify the persisted jobs against the host scheduler.")
    if int(review_due.get("due_findings", 0)) > 0:
        next_actions.append("Review due false-positive suppressions with `ai-dememory review false-positives --due-only`.")
    if int(review_due.get("stale_suppressions", 0)) > 0:
        next_actions.append("Review stale false-positive suppressions with `ai-dememory review stale-false-positives`.")
    if int(conflict_review.get("active_conflicts", 0)) > 0:
        next_actions.append("Review active memory conflicts with `ai-dememory review conflicts`.")
    if int(review_recommendations.get("pending_count", 0)) > 0:
        next_actions.append("Close pending advisory review recommendations with `ai-dememory review recommendations --outcome-status pending`.")
    if int(review_recommendations.get("invalid_count", 0)) > 0:
        next_actions.append("Fix malformed advisory review recommendation artifacts under `inbox/review-recommendations/`.")
    if bool(artifact_freshness.get("needs_maintenance", False)):
        next_actions.append("Run `ai-dememory maintenance run --profile daily` to refresh missing or stale generated artifacts.")
    hook_captures = hooks.get("captures", {}) if isinstance(hooks.get("captures"), dict) else {}
    if int(hook_captures.get("review_due_count", 0)) > 0:
        next_actions.append("Review due hook capture candidates under `inbox/session-events/`.")
    if not bool(recall_review.get("available", False)):
        next_actions.append("Add `quality/recall-fixtures.json` before running weekly recall review.")
    if bool(recall_review.get("stale", False)):
        next_actions.append("Review recall quality with `ai-dememory recall-fixtures review-plan --json`.")
    if int(recall_review.get("pending_count", 0)) > 0:
        next_actions.append("Promote or reject pending recall misses under `inbox/recall-feedback/`.")
    if int(recall_review.get("invalid_count", 0)) > 0:
        next_actions.append("Fix malformed recall miss files before weekly recall review sign-off.")
    if (
        bool(vector_readiness.get("available", False))
        and vector_readiness.get("decision") == "eligible_for_vector_experiment"
    ):
        next_actions.append("Review vector readiness evidence before approving any vector-search experiment.")
    if not bool(vector_readiness.get("available", False)):
        next_actions.extend(str(action) for action in vector_readiness.get("next_actions", []))
    if not bool(context_config.get("valid", True)):
        next_actions.append("Fix invalid `[context]` defaults in `.ai-dememory.toml` before relying on auto context.")
    if int(manual_acceptance.get("blocked_count", 0)) > 0:
        next_actions.append("Resolve blocked manual acceptance checks before marking v2 release-ready.")
    if int(manual_acceptance.get("remaining_count", 0)) > 0:
        next_actions.append("Complete remaining manual acceptance checks before release sign-off.")
    archive_summary = generated_packet_archives.get("summary", {})
    if int(archive_summary.get("prunable_count", 0)) > 0:
        next_actions.append("Review generated packet archive retention previews before cleanup.")
    if int(maintenance["provider_readiness"].get("configured_count", 0)) == 0:
        next_actions.append("Review provider setup with `ai-dememory providers plan --json` before importing chats.")
    if int(maintenance["provider_readiness"].get("import_ready_count", 0)) > 0:
        next_actions.append("Preview maintenance with `ai-dememory maintenance run --profile daily --dry-run --json` before enabling schedules.")
    if not next_actions:
        next_actions.append("Setup health has no immediate review actions.")
    resource_policy_valid = bool(resource_policy.get("valid", False))
    core_ready = bool(
        validation.get("ok", False)
        and context_config.get("valid", True)
        and resource_policy_valid
    )
    recall_freshness = recall_review.get("freshness", {})
    if not isinstance(recall_freshness, dict):
        recall_freshness = {}
    retrieval_evaluated = bool(
        recall_review.get("available", False)
        and int(recall_review.get("invalid_count", 0)) == 0
        and int(recall_freshness.get("reviewed_promotions", 0)) > 0
        and not recall_freshness.get("stale", True)
    )
    manual_maintenance_ready = bool(
        schedule.get("valid", False)
        and resource_policy_valid
        and not artifact_freshness.get("needs_maintenance", False)
        and not maintenance.get("lock_exists", False)
    )
    automation_ready = bool(
        manual_maintenance_ready
        and schedule_env.get("ready", False)
        and schedule.get("configured", False)
        and schedule.get("install_receipt_valid", False)
        and schedule.get("host_state_verified", False)
    )
    maintenance_ready = automation_ready
    integration_configured = bool(
        int(hooks.get("installed_count", 0)) > 0
        or int(maintenance["provider_readiness"].get("enabled_count", 0)) > 0
    )
    integrations_ready = bool(
        integration_configured
        and int(hook_captures.get("malformed_count", 0)) == 0
    )
    review_queues_clear = bool(
        int(review_due.get("due_findings", 0)) == 0
        and int(conflict_review.get("active_conflicts", 0)) == 0
        and int(review_recommendations.get("pending_count", 0)) == 0
        and int(review_recommendations.get("invalid_count", 0)) == 0
        and int(hook_captures.get("review_due_count", 0)) == 0
    )
    autonomy_ready = bool(automation_ready and integrations_ready and resource_policy_valid)
    release_ready = bool(
        core_ready
        and resource_policy_valid
        and retrieval_evaluated
        and maintenance_ready
        and integrations_ready
        and manual_acceptance.get("complete", False)
        and review_queues_clear
    )
    return {
        "root": str(root),
        "platform": schedule_env["platform"],
        "mode": mode,
        # Deprecated compatibility field. It now has the explicit narrow
        # meaning documented by ready_scope instead of implying full health.
        "ready": core_ready,
        "ready_deprecated": True,
        "ready_scope": "core_ready",
        "core_ready": core_ready,
        "retrieval_evaluated": retrieval_evaluated,
        "maintenance_ready": maintenance_ready,
        "manual_maintenance_ready": manual_maintenance_ready,
        "automation_ready": automation_ready,
        "autonomy_ready": autonomy_ready,
        "autonomy_requested": bool(schedule.get("configured", False)),
        "integrations_ready": integrations_ready,
        "release_ready": release_ready,
        "readiness": {
            "core": {
                "ready": core_ready,
                "requires": ["valid memories", "valid context config", "valid resource policy"],
            },
            "retrieval": {
                "evaluated": retrieval_evaluated,
                "requires": ["valid recall fixtures", "at least one fresh reviewed promotion"],
            },
            "maintenance": {
                "ready": maintenance_ready,
                "manual_ready": manual_maintenance_ready,
                "automation_ready": automation_ready,
                "requires": [
                    "scheduler available",
                    "valid installed and verified schedule receipt",
                    "fresh artifacts",
                    "no active lock",
                ],
            },
            "integrations": {
                "ready": integrations_ready,
                "configured": integration_configured,
                "requires": ["at least one configured provider or hook", "no malformed hook captures"],
            },
            "release": {
                "ready": release_ready,
                "requires": ["all readiness dimensions", "manual acceptance complete", "review queues clear"],
            },
        },
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "validation_status": validation,
        "recall_review": recall_review,
        "context_config": context_config,
        "manual_acceptance": manual_acceptance,
        "vector_readiness": vector_readiness,
        "resource_policy": resource_policy,
        "generated_packet_archives": generated_packet_archives,
        "schedule_environment": schedule_env,
        "schedule_status": schedule,
        "hook_status": hooks,
        "provider_readiness": maintenance["provider_readiness"],
        "maintenance_preflight": maintenance_preflight,
        "review_due": review_due,
        "conflict_review": conflict_review,
        "review_recommendations": review_recommendations,
        "artifacts": maintenance["artifacts"],
        "artifact_freshness": artifact_freshness,
        "lock_exists": maintenance["lock_exists"],
        "next_actions": next_actions,
    }


def setup_health_generated_packet_archives(root: Path) -> dict[str, Any]:
    return generated_packet_archive_summary(root)


def setup_health_maintenance_preflight(root: Path, maintenance: dict[str, Any]) -> dict[str, Any]:
    provider_readiness = maintenance["provider_readiness"]
    return {
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "reads_provider_files": False,
        "writes_import_candidates": False,
        "provider_counts": {
            "configured": provider_readiness.get("configured_count", 0),
            "enabled": provider_readiness.get("enabled_count", 0),
            "import_ready": provider_readiness.get("import_ready_count", 0),
        },
        "daily_dry_run_command": _root_bound_command(
            "ai-dememory",
            root,
            "maintenance",
            "run",
            "--profile",
            "daily",
            "--dry-run",
            "--json",
        ),
        "weekly_dry_run_command": _root_bound_command(
            "ai-dememory",
            root,
            "maintenance",
            "run",
            "--profile",
            "weekly",
            "--dry-run",
            "--json",
        ),
        "daily_artifacts": maintenance_artifact_targets(root, "daily"),
        "weekly_artifacts": maintenance_artifact_targets(root, "weekly"),
    }


def setup_health_manual_acceptance(root: Path) -> dict[str, Any]:
    plan = acceptance_plan(root)
    return {
        "complete": plan.complete,
        "total": plan.total,
        "completed_count": plan.completed_count,
        "blocked_count": plan.blocked_count,
        "remaining_count": plan.remaining_count,
        "next_actions": plan.next_actions,
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "records_evidence": False,
    }


def setup_health_vector_readiness(root: Path) -> dict[str, Any]:
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


def setup_health_recall_review(root: Path) -> dict[str, Any]:
    try:
        result = asdict(recall_fixture_review_plan(root))
    except FileNotFoundError as exc:
        return {
            "available": False,
            "status": "unavailable",
            "stale": False,
            "pending_count": 0,
            "invalid_count": 0,
            "resolved_count": 0,
            "errors": [str(exc)],
            "next_actions": [
                "Add `quality/recall-fixtures.json` before running weekly recall review.",
            ],
        }
    result["available"] = True
    result["errors"] = []
    return result


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", default=None, help="Vault root. Defaults to the current vault or checkout.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    plan = subparsers.add_parser("plan", help="Print a read-only local setup plan.", allow_abbrev=False)
    plan.add_argument("--client", choices=(*CLIENTS, "all"), default="all")
    plan.add_argument("--mode", choices=MODES, default="installed")
    plan.add_argument("--command", default="ai-dememory", help="CLI command to include in generated command arrays.")
    plan.add_argument("--image", default="ai-dememory:local", help="Docker image for Docker command examples.")
    plan.add_argument("--intensity", choices=profile_names(), default=DEFAULT_INTENSITY)
    plan.add_argument("--model-policy", choices=model_policy_names(), default=DEFAULT_MODEL_POLICY)
    # Earlier configurations and runbooks may still pass this option. It is
    # parsed only for upgrade compatibility and is never emitted in a new plan.
    plan.add_argument("--require-version", metavar="VERSION", help=argparse.SUPPRESS)
    plan.add_argument("--json", action="store_true", help="Emit JSON output.")
    health = subparsers.add_parser("health", help="Print read-only local setup health.", allow_abbrev=False)
    health.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
    health.add_argument("--mode", choices=("installed", "docker"), default="installed")
    health.add_argument("--json", action="store_true", help="Emit JSON output.")

    reject_duplicate_options(
        parser,
        argv,
        (
            "--root",
            "--client",
            "--mode",
            "--command",
            "--image",
            "--intensity",
            "--model-policy",
            "--require-version",
            "--platform",
        ),
    )
    args = parser.parse_args(argv)
    root_was_supplied = any(
        argument == "--root" or argument.startswith("--root=")
        for argument in argv
    )
    if root_was_supplied and (not args.root or not args.root.strip()):
        parser.error("--root requires a non-empty vault path")
    explicit_root = args.root if args.root and args.root.strip() else None
    configured_root = os.environ.get("AI_DEMEMORY_ROOT")
    configured_root = configured_root if configured_root and configured_root.strip() else None
    if (
        args.command_name in {"plan", "health"}
        and not explicit_root
        and not configured_root
    ):
        parser.error(
            f"setup {args.command_name} requires an explicit vault binding; "
            "pass --root <vault-path> or set AI_DEMEMORY_ROOT"
        )
    root = repo_root(explicit_root)

    if args.command_name == "plan":
        result = setup_plan(
            root,
            client=args.client,
            mode=args.mode,
            command=args.command,
            image=args.image,
            intensity=args.intensity,
            model_policy=args.model_policy,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("ai-dememory setup plan")
            print("Package, plugin, and plan commands are passive; review before installing hooks or schedules.")
            for name, value in result["commands"].items():
                if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
                    print(f"- {name}: {render_copy_command(value)}")
                elif isinstance(value, dict):
                    print(f"- {name}:")
                    for report_name, report_command in value.items():
                        if isinstance(report_command, list) and all(isinstance(item, str) for item in report_command):
                            print(
                                f"  - {report_name}: {render_copy_command(report_command)}"
                            )
            print(
                "Optional commands: choose only the diagnostics or integration paths you want; "
                "nothing installs automatically."
            )
        return 0

    if args.command_name == "health":
        result = setup_health(root, target_platform=args.platform, mode=args.mode)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("ai-dememory setup health")
            print(f"core_ready: {str(result['core_ready']).lower()}")
            print(f"retrieval_evaluated: {str(result['retrieval_evaluated']).lower()}")
            print(f"maintenance_ready: {str(result['maintenance_ready']).lower()}")
            print(f"manual_maintenance_ready: {str(result['manual_maintenance_ready']).lower()}")
            print(f"automation_ready: {str(result['automation_ready']).lower()}")
            print(f"autonomy_ready: {str(result['autonomy_ready']).lower()}")
            print(f"integrations_ready: {str(result['integrations_ready']).lower()}")
            print(f"release_ready: {str(result['release_ready']).lower()}")
            print("ready: deprecated alias for core_ready")
            print(f"platform: {result['platform']}")
            print(f"mode: {result['mode']}")
            for action in result["next_actions"]:
                print(f"- {action}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
