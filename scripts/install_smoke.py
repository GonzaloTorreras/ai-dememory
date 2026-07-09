#!/usr/bin/env python3
"""Run fresh install smoke checks for package and local Docker distribution."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from build_artifacts import cleanup_created_build_paths, snapshot_generated_build_paths
from memorylib import repo_root


MCP_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}
MCP_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
MCP_PING = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
INSTALL_SMOKE_MEMORY = """---
id: mem_install_smoke_policy
title: Install Smoke Policy
type: tool
status: active
scope: tool
project: null
tags: [install-smoke]
aliases: [package smoke]
created_at: 2026-06-19
updated_at: 2026-06-19
confidence: 0.9
sensitivity: internal
source:
  kind: manual
  ref: install-smoke
pin: false
decay: normal
review_after: 2026-09-19
---

Install smoke policy memory verifies packaged recall fixture promotion.
"""


class InstallSmokeError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeStep:
    name: str
    command: list[str]
    cwd: str | None
    returncode: int


def venv_paths(venv: Path) -> tuple[Path, Path, Path]:
    if os.name == "nt":
        scripts = venv / "Scripts"
        return scripts / "python.exe", scripts / "pip.exe", scripts / "ai-dememory.exe"
    bin_dir = venv / "bin"
    return bin_dir / "python", bin_dir / "pip", bin_dir / "ai-dememory"


def run_step(
    steps: list[SmokeStep],
    name: str,
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int = 180,
    allowed_returncodes: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    ok_returncodes = allowed_returncodes or {0}
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    steps.append(SmokeStep(name, command, str(cwd) if cwd else None, completed.returncode))
    if completed.returncode not in ok_returncodes:
        raise InstallSmokeError(
            f"{name} failed with exit {completed.returncode}\n"
            f"command: {command}\n"
            f"stdout:\n{tail(completed.stdout)}\n"
            f"stderr:\n{tail(completed.stderr)}"
        )
    return completed


def tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def mcp_payload() -> str:
    return "\n".join(json.dumps(message) for message in (MCP_INIT, MCP_INITIALIZED, MCP_PING)) + "\n"


def mcp_responses_by_id(stdout: str) -> dict[int, Any]:
    responses: dict[int, Any] = {}
    seen_messages = 0
    for raw_line in stdout.splitlines():
        if not raw_line.strip():
            continue
        seen_messages += 1
        try:
            message = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise InstallSmokeError(f"MCP smoke returned non-JSON output: {raw_line}") from exc
        if not isinstance(message, dict):
            raise InstallSmokeError("MCP smoke returned a non-object JSON-RPC message")
        if "id" not in message:
            continue
        request_id = message.get("id")
        if isinstance(request_id, bool) or not isinstance(request_id, int):
            raise InstallSmokeError(f"MCP smoke returned non-integer response id: {request_id!r}")
        if "error" in message:
            raise InstallSmokeError(f"MCP request {request_id} failed: {message['error']}")
        if request_id in responses:
            raise InstallSmokeError(f"MCP smoke returned duplicate response id: {request_id}")
        if "result" not in message:
            raise InstallSmokeError(f"MCP response id {request_id} did not include result or error")
        responses[request_id] = message.get("result")
    if seen_messages == 0:
        raise InstallSmokeError("MCP smoke returned no JSON-RPC messages")
    return responses


def assert_mcp_initialize_and_ping(stdout: str) -> None:
    responses = mcp_responses_by_id(stdout)
    unexpected_ids = sorted(set(responses) - {1, 2})
    if unexpected_ids:
        raise InstallSmokeError(f"MCP smoke returned unexpected response id(s): {unexpected_ids}")
    if 1 not in responses:
        raise InstallSmokeError("MCP initialize response id 1 was missing")
    if 2 not in responses:
        raise InstallSmokeError("MCP ping response id 2 was missing")
    init = responses[1]
    ping = responses.get(2)
    if not isinstance(init, dict):
        raise InstallSmokeError("MCP initialize returned a non-object result")
    if not isinstance(ping, dict):
        raise InstallSmokeError("MCP ping returned a non-object result")
    protocol_version = init.get("protocolVersion")
    if protocol_version is None:
        raise InstallSmokeError("MCP initialize result missing protocolVersion")
    if not isinstance(protocol_version, str):
        raise InstallSmokeError("MCP initialize protocolVersion was not a string")
    if protocol_version != "2025-11-25":
        raise InstallSmokeError("MCP initialize did not negotiate 2025-11-25")
    if ping != {}:
        raise InstallSmokeError("MCP ping did not return an empty result")


def assert_doctor_summary(stdout: str, expected_profile: str = "vault") -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"doctor summary did not return JSON: {exc}") from exc
    if data.get("profile") != expected_profile:
        actual_profile = data.get("profile")
        raise InstallSmokeError(
            f"doctor summary profile was {actual_profile!r}, expected {expected_profile!r}"
        )
    summary = data.get("summary")
    checks = data.get("checks")
    if not isinstance(summary, dict) or not isinstance(checks, list):
        raise InstallSmokeError("doctor summary missing summary or checks")
    required_counts = ("ok", "warn", "fail", "total")
    counts: dict[str, int] = {}
    for key in required_counts:
        value = summary.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise InstallSmokeError(f"doctor summary {key} count was not an integer")
        counts[key] = value
    if counts["total"] != len(checks):
        raise InstallSmokeError("doctor summary total does not match checks")
    observed = {"ok": 0, "warn": 0, "fail": 0}
    for check in checks:
        if not isinstance(check, dict):
            raise InstallSmokeError("doctor summary checks must be objects")
        status = check.get("status")
        if status not in observed:
            raise InstallSmokeError(f"doctor summary check had unexpected status: {status!r}")
        observed[status] += 1
    for key, observed_count in observed.items():
        if counts[key] != observed_count:
            raise InstallSmokeError(f"doctor summary {key} count does not match checks")
    if counts["fail"] != 0:
        raise InstallSmokeError("doctor summary reported failing checks")


def release_evidence_unavailable_payload(stdout: str) -> dict[str, object]:
    try:
        data: dict[str, object] = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"MCP release evidence did not return JSON: {exc}") from exc

    if data.get("available") is not False:
        raise InstallSmokeError("MCP release evidence should be unavailable from a plain vault")
    reason = data.get("reason")
    if not isinstance(reason, str) or "distribution checkout" not in reason:
        raise InstallSmokeError("MCP release evidence did not explain the distribution checkout requirement")
    return data


def assert_release_evidence_unavailable(stdout: str) -> None:
    data = release_evidence_unavailable_payload(stdout)
    if "evidence" not in data or data.get("evidence") is not None:
        raise InstallSmokeError("MCP release evidence returned evidence for a plain vault")
    if "markdown" in data:
        raise InstallSmokeError("MCP release evidence returned report markdown field")


def assert_release_evidence_report_unavailable(stdout: str) -> None:
    data = release_evidence_unavailable_payload(stdout)
    if "markdown" not in data or data.get("markdown") is not None:
        raise InstallSmokeError("MCP release evidence report returned markdown for a plain vault")
    if "evidence" in data:
        raise InstallSmokeError("MCP release evidence report returned evidence field")


def assert_maintenance_status_artifacts(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"maintenance status did not return JSON: {exc}") from exc

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        raise InstallSmokeError("maintenance status missing generated artifact map")
    expected = {
        "index",
        "graph",
        "weights",
        "lifecycle_scores",
        "lifecycle_report",
        "hook_capture_report",
        "sleep_plan_report",
    }
    missing = sorted(expected - set(artifacts))
    if missing:
        raise InstallSmokeError("maintenance status missing artifact(s): " + ", ".join(missing))
    for name in sorted(expected):
        item = artifacts.get(name)
        if not isinstance(item, dict):
            raise InstallSmokeError(f"maintenance status artifact {name!r} is not an object")
        if not isinstance(item.get("path"), str) or not item["path"]:
            raise InstallSmokeError(f"maintenance status artifact {name!r} missing path")
        if not isinstance(item.get("exists"), bool):
            raise InstallSmokeError(f"maintenance status artifact {name!r} missing exists boolean")
        if item.get("updated_at") is not None and not isinstance(item.get("updated_at"), str):
            raise InstallSmokeError(f"maintenance status artifact {name!r} has invalid updated_at")
        if item.get("size_bytes") is not None and not isinstance(item.get("size_bytes"), int):
            raise InstallSmokeError(f"maintenance status artifact {name!r} has invalid size_bytes")
    freshness = data.get("artifact_freshness")
    if not isinstance(freshness, dict):
        raise InstallSmokeError("maintenance status missing generated artifact freshness summary")
    if not isinstance(freshness.get("missing_count"), int):
        raise InstallSmokeError("maintenance status artifact freshness missing missing_count")
    if not isinstance(freshness.get("stale_count"), int):
        raise InstallSmokeError("maintenance status artifact freshness missing stale_count")
    if not isinstance(freshness.get("needs_maintenance"), bool):
        raise InstallSmokeError("maintenance status artifact freshness missing needs_maintenance boolean")
    freshness_artifacts = freshness.get("artifacts")
    if not isinstance(freshness_artifacts, dict):
        raise InstallSmokeError("maintenance status artifact freshness missing artifact map")
    freshness_profile = freshness.get("profile", "daily")
    expected_freshness = set(expected)
    if freshness_profile == "daily":
        expected_freshness -= {"hook_capture_report", "sleep_plan_report"}
    missing_freshness = sorted(expected_freshness - set(freshness_artifacts))
    if missing_freshness:
        raise InstallSmokeError("maintenance status artifact freshness missing artifact(s): " + ", ".join(missing_freshness))
    if freshness.get("writes_files") is not False:
        raise InstallSmokeError("maintenance status artifact freshness must not write files")
    review_due = data.get("review_due")
    if not isinstance(review_due, dict):
        raise InstallSmokeError("maintenance status missing review due summary")
    if not isinstance(review_due.get("due_findings"), int):
        raise InstallSmokeError("maintenance status review due summary missing due_findings")
    if not isinstance(review_due.get("stale_suppressions"), int):
        raise InstallSmokeError("maintenance status review due summary missing stale_suppressions")
    if not isinstance(review_due.get("canonical_memory_updated"), bool):
        raise InstallSmokeError("maintenance status review due summary missing canonical_memory_updated boolean")
    conflict_review = data.get("conflict_review")
    if not isinstance(conflict_review, dict):
        raise InstallSmokeError("maintenance status missing conflict review summary")
    if not isinstance(conflict_review.get("active_conflicts"), int):
        raise InstallSmokeError("maintenance status conflict review summary missing active_conflicts")
    if not isinstance(conflict_review.get("canonical_memory_updated"), bool):
        raise InstallSmokeError("maintenance status conflict review summary missing canonical_memory_updated boolean")
    recommendations = data.get("review_recommendations")
    if not isinstance(recommendations, dict):
        raise InstallSmokeError("maintenance status missing review recommendation summary")
    if not isinstance(recommendations.get("pending_count"), int):
        raise InstallSmokeError("maintenance status review recommendation summary missing pending_count")
    if not isinstance(recommendations.get("applies_review_decisions"), bool):
        raise InstallSmokeError("maintenance status review recommendation summary missing applies_review_decisions boolean")
    packet_archives = data.get("generated_packet_archives")
    if not isinstance(packet_archives, dict):
        raise InstallSmokeError("maintenance status missing generated packet archive summary")
    archive_counts = packet_archives.get("summary")
    if not isinstance(archive_counts, dict):
        raise InstallSmokeError("maintenance status generated packet archive summary missing counts")
    if not isinstance(archive_counts.get("prunable_count"), int):
        raise InstallSmokeError("maintenance status generated packet archive summary missing prunable_count")
    if packet_archives.get("deletes_files") is not False:
        raise InstallSmokeError("maintenance status generated packet archive summary must not delete files")


def command_has_profile(command: Any, profile: str) -> bool:
    if not isinstance(command, list):
        return False
    tokens = [str(part) for part in command]
    if "maintenance" not in tokens or "run" not in tokens:
        return False
    try:
        return tokens[tokens.index("--profile") + 1] == profile
    except (ValueError, IndexError):
        return False


def assert_schedule_plan(
    stdout: str,
    expected_mode: str = "installed",
    expected_root: str | None = None,
) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"schedule plan did not return JSON: {exc}") from exc

    if data.get("action") != "install":
        raise InstallSmokeError("schedule plan did not default to install action")
    if data.get("mode") != expected_mode:
        raise InstallSmokeError(f"schedule plan mode was {data.get('mode')!r}, expected {expected_mode!r}")
    if expected_root is not None and data.get("root") != expected_root:
        raise InstallSmokeError("schedule plan root does not match expected vault root")
    for flag in ("mutates_system", "runs_commands", "writes_files", "installs_schedules"):
        if data.get(flag) is not False:
            raise InstallSmokeError(f"schedule plan {flag} must be false")

    schedule = data.get("schedule")
    if not isinstance(schedule, dict):
        raise InstallSmokeError("schedule plan missing schedule object")
    for field in ("daily_time", "weekly_day", "weekly_time"):
        if not isinstance(schedule.get(field), str) or not schedule[field]:
            raise InstallSmokeError(f"schedule plan missing schedule field {field}")

    commands = data.get("commands")
    if not isinstance(commands, list) or len(commands) < 2:
        raise InstallSmokeError("schedule plan missing scheduler commands")
    if not all(isinstance(command, dict) for command in commands):
        raise InstallSmokeError("schedule plan commands must be objects")
    for profile in ("daily", "weekly"):
        expected_name = f"ai-dememory-{profile}"
        matching_commands = [command for command in commands if command.get("name") == expected_name]
        if not matching_commands:
            raise InstallSmokeError(f"schedule plan missing {profile} scheduler command")
        if not any(command_has_profile(command.get("run_command"), profile) for command in matching_commands):
            raise InstallSmokeError(f"schedule plan missing {profile} maintenance run command")

    cron_entries = data.get("cron_entries")
    if not isinstance(cron_entries, list) or len(cron_entries) != 2:
        raise InstallSmokeError("schedule plan should include daily and weekly cron entries")
    if not all(isinstance(entry, dict) for entry in cron_entries):
        raise InstallSmokeError("schedule plan cron entries must be objects")
    cron_profiles = sorted(str(entry.get("profile", "")) for entry in cron_entries)
    if cron_profiles != ["daily", "weekly"]:
        raise InstallSmokeError("schedule plan should include one daily and one weekly cron entry")
    for profile in ("daily", "weekly"):
        matching_entries = [entry for entry in cron_entries if entry.get("profile") == profile]
        if not matching_entries:
            raise InstallSmokeError(f"schedule plan missing {profile} cron entry")
        entry = matching_entries[0]
        if (
            f"maintenance run --profile {profile}" not in str(entry.get("line", ""))
            or not command_has_profile(entry.get("command"), profile)
        ):
            raise InstallSmokeError(f"schedule plan missing {profile} maintenance cron line")


def assert_roadmap_status(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"roadmap status did not return JSON: {exc}") from exc

    if data.get("phase_count") != 11:
        raise InstallSmokeError("roadmap status must report 11 v2 phases")
    if data.get("writes_files") is not False:
        raise InstallSmokeError("roadmap status must not write files")
    if data.get("mutates_files") is not False:
        raise InstallSmokeError("roadmap status must not mutate files")
    status_counts = data.get("status_counts")
    if not isinstance(status_counts, dict):
        raise InstallSmokeError("roadmap status missing status_counts")
    counted = sum(value for value in status_counts.values() if isinstance(value, int))
    if counted != data["phase_count"]:
        raise InstallSmokeError("roadmap status counts do not match phase_count")
    phases = data.get("phases")
    if not isinstance(phases, list) or len(phases) != data["phase_count"]:
        raise InstallSmokeError("roadmap status phases do not match phase_count")
    phase_numbers = [phase.get("phase") for phase in phases if isinstance(phase, dict)]
    if phase_numbers != list(range(data["phase_count"])):
        raise InstallSmokeError("roadmap status phases must include stable phase numbers")


def assert_publish_plan(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"publish plan did not return JSON: {exc}") from exc

    if data.get("repository") != "testpypi":
        raise InstallSmokeError("publish plan must default to TestPyPI")
    if data.get("runs_commands") is not True:
        raise InstallSmokeError("publish plan must report read-only local inspection commands")
    for flag in ("mutates_system", "runs_publish_commands", "runs_preflight_commands", "writes_files", "publishes_package"):
        if data.get(flag) is not False:
            raise InstallSmokeError(f"publish plan {flag} must be false")
    if data.get("requires_manual_dispatch") is not True:
        raise InstallSmokeError("publish plan must require manual workflow dispatch")
    if data.get("requires_confirmation") is not True:
        raise InstallSmokeError("publish plan must require explicit confirmation")
    if data.get("requires_pr_url") is not True:
        raise InstallSmokeError("publish plan must require a PR URL")
    dispatch_inputs = data.get("dispatch_inputs")
    if (
        not isinstance(dispatch_inputs, dict)
        or dispatch_inputs.get("confirm") != "publish"
        or "pr_url" not in dispatch_inputs
    ):
        raise InstallSmokeError("publish plan missing workflow dispatch confirmation")
    workflow_url = data.get("workflow_url")
    if not isinstance(workflow_url, str) or "/actions/workflows/publish.yml" not in workflow_url:
        raise InstallSmokeError("publish plan missing workflow URL")
    commands = data.get("preflight_commands")
    if not isinstance(commands, list) or not commands:
        raise InstallSmokeError("publish plan missing preflight commands")
    if not data.get("next_actions"):
        raise InstallSmokeError("publish plan missing next actions")


def assert_vault_template_export(stdout: str, target: Path, expected_reported_target: str | None = None) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"vault template export did not return JSON: {exc}") from exc

    reported_target = str(data.get("target", ""))
    expected_target = expected_reported_target or str(target.resolve())
    if reported_target != expected_target:
        raise InstallSmokeError("vault template export JSON target does not match requested directory")
    if not isinstance(data.get("copied"), int) or data["copied"] <= 0:
        raise InstallSmokeError("vault template export did not report copied files")
    for relpath in (".ai-dememory.toml", ".ai-dememory-ignore.toml", ".gitignore", "README.md"):
        if not (target / relpath).exists():
            raise InstallSmokeError(f"vault template export missing {relpath}")
    if not (target / "memories" / "durable" / "README.md").exists():
        raise InstallSmokeError("vault template export missing durable memory README")
    if not (target / "inbox" / "llm-captures" / "README.md").exists():
        raise InstallSmokeError("vault template export missing LLM capture inbox README")


def package_smoke_commands() -> list[tuple[str, list[str]]]:
    return [
        ("doctor", ["doctor"]),
        ("validate", ["validate"]),
        ("secret scan", ["secret-scan"]),
        ("index", ["index"]),
        (
            "working snapshot",
            [
                "working",
                "snapshot",
                "--title",
                "Install Smoke Working State",
                "--task",
                "install-smoke",
                "--notes",
                "Use install smoke package policy.",
            ],
        ),
        ("context auto", ["context", "--auto", "--budget", "700", "--json"]),
        (
            "mark seen receipt",
            ["mark-seen", "--id", "mem_install_smoke_policy", "--query", "install smoke package policy", "--json"],
        ),
        (
            "outcome receipt",
            ["outcome", "--last", "--good", "--note", "Install smoke selected expected memory.", "--json"],
        ),
        ("eval recall", ["eval-recall"]),
        ("recall fixtures status", ["recall-fixtures", "status", "--json"]),
        (
            "capture recall miss dry run",
            [
                "capture-miss",
                "--query",
                "missing install smoke policy",
                "--expected-id",
                "mem_install_smoke_policy",
                "--reason",
                "Expected install smoke policy memory was absent.",
                "--dry-run",
                "--json",
            ],
        ),
        (
            "recall miss candidate check",
            [
                "recall-fixtures",
                "check-miss",
                "--query",
                "install smoke package policy",
                "--expected-id",
                "mem_install_smoke_policy",
                "--json",
            ],
        ),
        ("recall fixtures review plan", ["recall-fixtures", "review-plan", "--json"]),
        ("recall fixtures review report", ["recall-fixtures", "review-plan", "--write-report", "--json"]),
        ("recall fixtures review packet", ["recall-fixtures", "packet", "--write-report", "--json"]),
        ("recall fixtures packet archive status", ["recall-fixtures", "packet-archive-status", "--json"]),
        (
            "recall fixtures packet archive retention plan",
            ["recall-fixtures", "packet-archive-retention-plan", "--json"],
        ),
        ("recall fixtures help", ["recall-fixtures", "promote-miss", "--help"]),
        ("recall miss review help", ["recall-fixtures", "review-miss", "--help"]),
        ("vector status", ["vector", "status"]),
        ("roadmap status", ["roadmap", "status", "--json"]),
        ("provenance", ["provenance", "--json"]),
        ("acceptance status", ["acceptance", "status", "--json"]),
        ("acceptance plan", ["acceptance", "plan", "--json"]),
        ("acceptance plan report", ["acceptance", "plan", "--write-report", "--json"]),
        ("acceptance packet report", ["acceptance", "packet", "--write-report", "--json"]),
        ("acceptance packet archive status", ["acceptance", "packet-archive-status", "--json"]),
        ("acceptance packet archive retention plan", ["acceptance", "packet-archive-retention-plan", "--json"]),
        ("acceptance template", ["acceptance", "template", "--item", "mcp-client-installed", "--json"]),
        ("acceptance verify help", ["acceptance", "verify", "--help"]),
        ("publish plan", ["publish-plan", "--json"]),
        (
            "mcp release evidence unavailable",
            ["mcp", "--call", "memory.release_evidence", "--args", "{}"],
        ),
        (
            "mcp release evidence report unavailable",
            ["mcp", "--call", "memory.release_evidence_report", "--args", "{}"],
        ),
        (
            "mcp publish plan",
            ["mcp", "--call", "memory.publish_plan", "--args", "{}"],
        ),
        ("api smoke", ["api-smoke"]),
        ("vault template export", ["vault-template", "export", "{template_export}", "--json"]),
        ("mcp config", ["mcp-config", "--client", "codex"]),
        ("setup plan", ["setup", "plan", "--json"]),
        ("setup health", ["setup", "health", "--json"]),
        ("mcp client config smoke", ["mcp-client-smoke", "--command", "{ai_dememory}"]),
        (
            "plugin mcp config smoke",
            ["mcp-client-smoke", "--config", "{plugin_mcp}", "--command", "{ai_dememory}"],
        ),
        ("docker mcp config", ["mcp-config", "--client", "codex", "--mode", "docker"]),
        ("hooks codex", ["hooks", "config", "--client", "codex"]),
        ("hooks claude", ["hooks", "config", "--client", "claude"]),
        ("hooks review help", ["hooks", "review", "--help"]),
        ("hooks archive help", ["hooks", "archive", "--help"]),
        ("hooks dry run", ["hooks", "install", "--client", "all", "--dry-run"]),
        ("providers detect", ["providers", "detect"]),
        ("providers plan", ["providers", "plan", "--json"]),
        ("capture markdown", ["capture", "markdown", "--path", "{sample}"]),
        ("learn git dry run", ["learn", "--git", "--repo", "{root}", "--days", "7", "--dry-run"]),
        ("maintenance status", ["maintenance", "status"]),
        ("maintenance dry run", ["maintenance", "run", "--profile", "daily", "--dry-run", "--json"]),
        ("schedule doctor", ["schedule", "doctor", "--json"]),
        ("schedule plan", ["schedule", "plan", "--json"]),
        ("schedule dry run", ["schedule", "setup", "--dry-run"]),
        ("docker schedule dry run", ["schedule", "setup", "--dry-run", "--mode", "docker", "--image", "ai-dememory:local"]),
        ("cron schedule export", ["schedule", "cron", "--json"]),
        ("review modes", ["review", "modes"]),
        ("review false positives due only", ["review", "false-positives", "--due-only", "--json"]),
        ("review plan conflict", ["review", "plan", "--kind", "conflict"]),
        (
            "review recommendation",
            [
                "review",
                "recommendation",
                "--kind",
                "conflict",
                "--target-id",
                "conf_install_smoke",
                "--recommendation",
                "collect_evidence",
                "--rationale",
                "Install smoke records advisory recommendation capture.",
                "--recommended-by",
                "Install Smoke",
                "--json",
            ],
        ),
        ("review recommendations", ["review", "recommendations", "--json"]),
        ("review recommendation outcome help", ["review", "recommendation-outcome", "--help"]),
        ("review recommendation outcomes help", ["review", "recommendation-outcomes", "--help"]),
        ("review recommendations archive help", ["review", "recommendations-archive", "--help"]),
        ("review recommendations archive status", ["review", "recommendations-archive-status", "--json"]),
        ("review recommendations archive restore help", ["review", "recommendations-archive-restore", "--help"]),
        ("working status", ["working", "status", "--json"]),
    ]


def materialize_args(
    args: list[str],
    root: Path,
    vault: Path,
    sample: Path,
    ai_dememory: Path,
    template_export: Path,
) -> list[str]:
    replacements = {
        "{root}": str(root),
        "{vault}": str(vault),
        "{sample}": str(sample),
        "{ai_dememory}": str(ai_dememory),
        "{plugin_mcp}": str(root / "plugins" / "ai-dememory" / ".mcp.json"),
        "{template_export}": str(template_export),
    }
    return [replacements.get(arg, arg) for arg in args]


def local_ai_dememory_command(root: Path) -> list[str]:
    script = root / "scripts" / "ai_dememory.py"
    if script.exists():
        return [sys.executable, str(script)]
    return ["ai-dememory"]


def docker_client_smoke_command(root: Path, vault: Path, image: str) -> list[str]:
    return [
        *local_ai_dememory_command(root),
        "--root",
        str(vault),
        "mcp-client-smoke",
        "--mode",
        "docker",
        "--image",
        image,
    ]


def docker_release_evidence_command(vault: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{vault}:/memory",
        "-e",
        "AI_DEMEMORY_ROOT=/memory",
        image,
        "mcp",
        "--call",
        "memory.release_evidence",
        "--args",
        "{}",
    ]


def docker_publish_plan_command(vault: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{vault}:/memory",
        "-e",
        "AI_DEMEMORY_ROOT=/memory",
        image,
        "mcp",
        "--call",
        "memory.publish_plan",
        "--args",
        "{}",
    ]


def docker_maintenance_status_command(vault: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{vault}:/memory",
        "-e",
        "AI_DEMEMORY_ROOT=/memory",
        image,
        "maintenance",
        "status",
    ]


def docker_schedule_plan_command(vault: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{vault}:/memory",
        "-e",
        "AI_DEMEMORY_ROOT=/memory",
        image,
        "schedule",
        "plan",
        "--json",
    ]


def docker_roadmap_status_command(vault: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{vault}:/memory",
        "-e",
        "AI_DEMEMORY_ROOT=/memory",
        image,
        "roadmap",
        "status",
        "--json",
    ]


def docker_vault_template_export_command(template_export: Path, image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{template_export}:/template",
        image,
        "vault-template",
        "export",
        "/template",
        "--force",
        "--json",
    ]


def write_install_smoke_memory(vault: Path) -> Path:
    path = vault / "memories" / "tools" / "install-smoke-policy.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(INSTALL_SMOKE_MEMORY, encoding="utf-8")
    return path


def run_recall_fixture_promotion_smoke(
    steps: list[SmokeStep],
    ai_dememory: Path,
    vault: Path,
    env: dict[str, str],
) -> None:
    run_step(
        steps,
        "capture recall miss",
        [
            str(ai_dememory),
            "capture-miss",
            "--query",
            "install smoke package policy",
            "--reason",
            "Package install smoke verifies recall fixture promotion.",
            "--expected-id",
            "mem_install_smoke_policy",
        ],
        cwd=vault,
        env=env,
    )
    feedback_dir = vault / "inbox" / "recall-feedback"
    misses = sorted(path for path in feedback_dir.glob("*.md") if path.name != "README.md")
    if not misses:
        raise InstallSmokeError("capture recall miss did not write a feedback file")
    run_step(
        steps,
        "promote recall fixture",
        [
            str(ai_dememory),
            "recall-fixtures",
            "promote-miss",
            "--miss",
            str(misses[-1]),
            "--reviewed-by",
            "Install Smoke",
            "--fixture-id",
            "recall_install_smoke_policy",
            "--min-rank",
            "5",
        ],
        cwd=vault,
        env=env,
    )
    run_step(steps, "eval promoted recall fixture", [str(ai_dememory), "eval-recall"], cwd=vault, env=env)


def run_package_smoke(root: Path, package: str, keep_temp: bool = False) -> list[SmokeStep]:
    steps: list[SmokeStep] = []
    existing_generated = snapshot_generated_build_paths(root)
    temp_path = Path(tempfile.mkdtemp(prefix="ai-dememory-install-smoke-"))
    try:
        venv = temp_path / "venv"
        vault = temp_path / "vault"
        template_export = temp_path / "vault-template-export"
        sample = vault / "sample.md"
        run_step(steps, "create venv", [sys.executable, "-m", "venv", str(venv)])
        python, pip, ai_dememory = venv_paths(venv)
        run_step(steps, "upgrade pip", [str(python), "-m", "pip", "install", "--upgrade", "pip"])
        run_step(steps, "install package", [str(pip), "install", package], cwd=root)
        run_step(steps, "init vault", [str(ai_dememory), "init", str(vault)])
        write_install_smoke_memory(vault)
        sample.write_text("# Install Smoke\n\nCapture this non-secret note.\n", encoding="utf-8")
        env = {**os.environ, "AI_DEMEMORY_ROOT": str(vault)}
        doctor_summary = run_step(
            steps,
            "doctor summary",
            [str(ai_dememory), "doctor", "--json", "--summary"],
            cwd=vault,
            env=env,
        )
        assert_doctor_summary(doctor_summary.stdout)
        for name, args in package_smoke_commands():
            completed = run_step(
                steps,
                name,
                [str(ai_dememory), *materialize_args(args, root, vault, sample, ai_dememory, template_export)],
                cwd=vault,
                env=env,
                allowed_returncodes={0, 1} if name == "roadmap status" else None,
            )
            if name == "mcp release evidence unavailable":
                assert_release_evidence_unavailable(completed.stdout)
            if name == "mcp release evidence report unavailable":
                assert_release_evidence_report_unavailable(completed.stdout)
            if name == "mcp publish plan":
                assert_publish_plan(completed.stdout)
            if name == "maintenance status":
                assert_maintenance_status_artifacts(completed.stdout)
            if name == "schedule plan":
                assert_schedule_plan(completed.stdout, expected_root=str(vault.resolve()))
            if name == "roadmap status":
                assert_roadmap_status(completed.stdout)
            if name == "publish plan":
                assert_publish_plan(completed.stdout)
            if name == "vault template export":
                assert_vault_template_export(completed.stdout, template_export)
        run_recall_fixture_promotion_smoke(steps, ai_dememory, vault, env)
        mcp = run_step(
            steps,
            "mcp initialize ping",
            [str(ai_dememory), "mcp", "--stdio"],
            cwd=vault,
            env=env,
            input_text=mcp_payload(),
        )
        assert_mcp_initialize_and_ping(mcp.stdout)
        return steps
    finally:
        try:
            cleanup_created_build_paths(root, existing_generated)
        except RuntimeError as exc:
            raise InstallSmokeError(str(exc)) from exc
        if keep_temp:
            print(f"Kept install smoke temp directory: {temp_path}", file=sys.stderr)
        else:
            shutil.rmtree(temp_path, ignore_errors=True)


def run_docker_smoke(root: Path, image: str, keep_temp: bool = False) -> list[SmokeStep]:
    if shutil.which("docker") is None:
        raise InstallSmokeError("docker executable was not found")
    steps: list[SmokeStep] = []
    temp_path = Path(tempfile.mkdtemp(prefix="ai-dememory-docker-smoke-"))
    try:
        vault = temp_path / "vault"
        template_export = temp_path / "vault-template-export"
        mount = f"{vault}:/memory"
        run_step(steps, "docker build", ["docker", "build", "-t", image, "."], cwd=root, timeout=600)
        run_step(steps, "docker init vault", ["docker", "run", "--rm", "-v", mount, image, "init", "/memory"])
        template_export.mkdir(parents=True, exist_ok=True)
        docker_template_export = run_step(
            steps,
            "docker vault template export",
            docker_vault_template_export_command(template_export, image),
        )
        assert_vault_template_export(docker_template_export.stdout, template_export, expected_reported_target="/template")
        run_step(
            steps,
            "docker doctor",
            ["docker", "run", "--rm", "-v", mount, "-e", "AI_DEMEMORY_ROOT=/memory", image, "doctor"],
        )
        docker_doctor_summary = run_step(
            steps,
            "docker doctor summary",
            [
                "docker",
                "run",
                "--rm",
                "-v",
                mount,
                "-e",
                "AI_DEMEMORY_ROOT=/memory",
                image,
                "doctor",
                "--json",
                "--summary",
            ],
        )
        assert_doctor_summary(docker_doctor_summary.stdout)
        docker_schedule_plan = run_step(
            steps,
            "docker schedule plan",
            docker_schedule_plan_command(vault, image),
        )
        assert_schedule_plan(docker_schedule_plan.stdout, expected_root="/memory")
        docker_roadmap_status = run_step(
            steps,
            "docker roadmap status",
            docker_roadmap_status_command(vault, image),
            allowed_returncodes={0, 1},
        )
        assert_roadmap_status(docker_roadmap_status.stdout)
        run_step(
            steps,
            "docker index",
            ["docker", "run", "--rm", "-v", mount, "-e", "AI_DEMEMORY_ROOT=/memory", image, "index"],
        )
        docker_maintenance_status = run_step(
            steps,
            "docker maintenance status",
            docker_maintenance_status_command(vault, image),
        )
        assert_maintenance_status_artifacts(docker_maintenance_status.stdout)
        docker_release_evidence = run_step(
            steps,
            "docker mcp release evidence unavailable",
            docker_release_evidence_command(vault, image),
        )
        assert_release_evidence_unavailable(docker_release_evidence.stdout)
        docker_publish_plan = run_step(
            steps,
            "docker mcp publish plan",
            docker_publish_plan_command(vault, image),
        )
        assert_publish_plan(docker_publish_plan.stdout)
        mcp = run_step(
            steps,
            "docker mcp initialize ping",
            ["docker", "run", "--rm", "-i", "-v", mount, "-e", "AI_DEMEMORY_ROOT=/memory", image],
            input_text=mcp_payload(),
        )
        assert_mcp_initialize_and_ping(mcp.stdout)
        run_step(
            steps,
            "docker mcp client config smoke",
            docker_client_smoke_command(root, vault, image),
            cwd=root,
        )
        return steps
    finally:
        if keep_temp:
            print(f"Kept Docker smoke temp directory: {temp_path}", file=sys.stderr)
        else:
            shutil.rmtree(temp_path, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--package", default=".", help="Package specifier or checkout path to install.")
    parser.add_argument("--skip-package", action="store_true", help="Skip fresh venv package smoke.")
    parser.add_argument("--docker", action="store_true", help="Run local Docker MCP smoke.")
    parser.add_argument("--image", default="ai-dememory:local", help="Docker image tag to build and test.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary smoke directories.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    all_steps: list[SmokeStep] = []
    try:
        if not args.skip_package:
            all_steps.extend(run_package_smoke(root, args.package, keep_temp=args.keep_temp))
        if args.docker:
            all_steps.extend(run_docker_smoke(root, args.image, keep_temp=args.keep_temp))
    except InstallSmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([asdict(step) for step in all_steps], indent=2))
    else:
        for step in all_steps:
            print(f"OK {step.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
