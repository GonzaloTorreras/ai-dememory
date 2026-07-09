#!/usr/bin/env python3
"""Build a read-only review plan for local ai-dememory setup."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from context_memory import context_defaults_status
from maintenance import generated_packet_archive_summary, maintenance_artifact_targets, maintenance_status
from hook_event import hook_status_summary
from manual_acceptance import acceptance_plan
from memorylib import repo_root
from provider_import import provider_setup_plan
from recall_fixtures import recall_fixture_review_plan
from schedule_memory import schedule_environment, schedule_status
from validate_memory import validate_repo_result
from vector_gate import evaluate_vector_readiness


CLIENTS = ("codex", "claude", "generic")
MODES = ("installed", "docker", "both")


def selected_clients(client: str) -> list[str]:
    return list(CLIENTS) if client == "all" else [client]


def mcp_config_command(command: str, client: str, mode: str, root: Path, image: str) -> list[str]:
    args = [command, "mcp-config", "--client", client, "--mode", mode, "--root", str(root)]
    if mode == "docker":
        args.extend(["--image", image])
    return args


def setup_plan(
    root: Path,
    client: str = "all",
    mode: str = "installed",
    command: str = "ai-dememory",
    image: str = "ai-dememory:local",
) -> dict[str, Any]:
    clients = selected_clients(client)
    modes = ["installed", "docker"] if mode == "both" else [mode]
    commands: dict[str, Any] = {
        "doctor": [command, "doctor"],
        "index": [command, "index"],
        "graph": [command, "graph"],
        "provider_plan": [command, "providers", "plan", "--json"],
        "hook_install_dry_run": [command, "hooks", "install", "--client", "all", "--dry-run"],
        "schedule_environment": [command, "schedule", "doctor", "--json"],
        "schedule_plan": [command, "schedule", "plan", "--json"],
        "schedule_dry_run": [command, "schedule", "setup", "--dry-run"],
        "schedule_cron": [command, "schedule", "cron"],
        "docker_schedule_environment": [
            command,
            "schedule",
            "doctor",
            "--json",
            "--mode",
            "docker",
        ],
        "docker_schedule_plan": [
            command,
            "schedule",
            "plan",
            "--json",
            "--mode",
            "docker",
            "--image",
            image,
        ],
        "docker_schedule_dry_run": [
            command,
            "schedule",
            "setup",
            "--dry-run",
            "--mode",
            "docker",
            "--image",
            image,
        ],
        "docker_schedule_cron": [command, "schedule", "cron", "--mode", "docker", "--image", image],
        "daily_maintenance": [command, "maintenance", "run", "--profile", "daily"],
        "weekly_maintenance": [command, "maintenance", "run", "--profile", "weekly"],
        "acceptance_plan": [command, "acceptance", "plan", "--json"],
        "generated_reports": {
            "recall_review_plan": [command, "recall-fixtures", "review-plan", "--write-report"],
            "recall_review_packet": [command, "recall-fixtures", "packet", "--write-report"],
            "manual_acceptance_plan": [command, "acceptance", "plan", "--write-report"],
            "manual_acceptance_packet": [command, "acceptance", "packet", "--write-report"],
            "hook_capture_review": [command, "hooks", "captures", "--write-report"],
            "release_evidence": [command, "release-evidence", "--write-report"],
        },
        "generated_archive_status": {
            "recall_review_packets": [command, "recall-fixtures", "packet-archive-status", "--json"],
            "manual_acceptance_packets": [command, "acceptance", "packet-archive-status", "--json"],
        },
        "generated_archive_retention": {
            "recall_review_packets": [command, "recall-fixtures", "packet-archive-retention-plan", "--json"],
            "manual_acceptance_packets": [command, "acceptance", "packet-archive-retention-plan", "--json"],
        },
    }
    commands["mcp_configs"] = [
        mcp_config_command(command, selected, selected_mode, root, image)
        for selected_mode in modes
        for selected in clients
    ]
    commands["hook_configs"] = [
        [command, "hooks", "config", "--client", selected, "--root", str(root)]
        for selected in clients
        if selected in {"codex", "claude"}
    ]
    provider_plan = provider_setup_plan(root, command=command)
    return {
        "root": str(root),
        "client": client,
        "mode": mode,
        "mutates_system": False,
        "writes_files": False,
        "reads_provider_files": False,
        "writes_import_candidates": False,
        "installs_schedules": False,
        "installs_hooks": False,
        "suggests_generated_reports": True,
        "suggests_generated_archive_status": True,
        "suggests_generated_archive_retention": True,
        "commands": commands,
        "provider_plan": provider_plan,
        "next_actions": [
            "Run doctor and index after creating or opening a vault.",
            "Copy an MCP config for the client you actually use.",
            "Generate report artifacts only when you need a release or review handoff.",
            "Review provider paths before running any providers configure command.",
            "Review structured scheduler plans before installing host scheduler jobs.",
            "Preview hooks and schedules with dry-run/config commands before installing anything.",
            "Record real-client and reviewed manual acceptance evidence only after a human check.",
        ],
    }


def setup_health(
    root: Path,
    target_platform: str | None = None,
    mode: str = "installed",
) -> dict[str, Any]:
    schedule_env = schedule_environment(target_platform=target_platform, mode=mode)
    schedule = schedule_status(root, target_platform=target_platform)
    maintenance = maintenance_status(root)
    hooks = hook_status_summary(root)
    validation = validate_repo_result(root)
    recall_review = setup_health_recall_review(root)
    context_config = context_defaults_status(root)
    manual_acceptance = setup_health_manual_acceptance(root)
    vector_readiness = setup_health_vector_readiness(root)
    maintenance_preflight = setup_health_maintenance_preflight(root, maintenance)
    generated_packet_archives = setup_health_generated_packet_archives(root)
    review_due = maintenance["review_due"]
    conflict_review = maintenance["conflict_review"]
    review_recommendations = maintenance["review_recommendations"]
    artifact_freshness = maintenance.get("artifact_freshness", {})
    next_actions: list[str] = []
    if not bool(validation.get("ok", False)):
        next_actions.append("Fix memory validation errors with `ai-dememory validate --json` before indexing or enabling schedules.")
    if not schedule_env["ready"]:
        missing = ", ".join(str(item) for item in schedule_env["required_missing"])
        next_actions.append(f"Install or choose a supported scheduler path for missing requirement(s): {missing}.")
    if not schedule["valid"]:
        next_actions.append("Fix persisted schedule config before installing or relying on maintenance schedules.")
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
    return {
        "root": str(root),
        "platform": schedule_env["platform"],
        "mode": mode,
        "ready": bool(validation.get("ok", False) and schedule_env["ready"] and schedule["valid"]),
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "validation_status": validation,
        "recall_review": recall_review,
        "context_config": context_config,
        "manual_acceptance": manual_acceptance,
        "vector_readiness": vector_readiness,
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
        "daily_dry_run_command": ["ai-dememory", "maintenance", "run", "--profile", "daily", "--dry-run", "--json"],
        "weekly_dry_run_command": ["ai-dememory", "maintenance", "run", "--profile", "weekly", "--dry-run", "--json"],
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Vault root. Defaults to the current vault or checkout.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    plan = subparsers.add_parser("plan", help="Print a read-only local setup plan.")
    plan.add_argument("--client", choices=(*CLIENTS, "all"), default="all")
    plan.add_argument("--mode", choices=MODES, default="installed")
    plan.add_argument("--command", default="ai-dememory", help="CLI command to include in generated command arrays.")
    plan.add_argument("--image", default="ai-dememory:local", help="Docker image for Docker command examples.")
    plan.add_argument("--json", action="store_true", help="Emit JSON output.")
    health = subparsers.add_parser("health", help="Print read-only local setup health.")
    health.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
    health.add_argument("--mode", choices=("installed", "docker"), default="installed")
    health.add_argument("--json", action="store_true", help="Emit JSON output.")

    args = parser.parse_args(argv)
    root = repo_root(args.root)

    if args.command_name == "plan":
        result = setup_plan(
            root,
            client=args.client,
            mode=args.mode,
            command=args.command,
            image=args.image,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("ai-dememory setup plan")
            print("Package, plugin, and plan commands are passive; review before installing hooks or schedules.")
            for name, value in result["commands"].items():
                if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
                    print(f"- {name}: {' '.join(value)}")
                elif isinstance(value, dict):
                    print(f"- {name}:")
                    for report_name, report_command in value.items():
                        if isinstance(report_command, list) and all(isinstance(item, str) for item in report_command):
                            print(f"  - {report_name}: {' '.join(report_command)}")
            print("Next: run the commands for the client and provider paths you choose.")
        return 0

    if args.command_name == "health":
        result = setup_health(root, target_platform=args.platform, mode=args.mode)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("ai-dememory setup health")
            print(f"ready: {str(result['ready']).lower()}")
            print(f"platform: {result['platform']}")
            print(f"mode: {result['mode']}")
            for action in result["next_actions"]:
                print(f"- {action}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
