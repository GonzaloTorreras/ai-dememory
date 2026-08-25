#!/usr/bin/env python3
"""Run fresh install smoke checks for package and local Docker distribution."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from process_control import run_owned_capture

from build_artifacts import cleanup_created_build_paths, snapshot_generated_build_paths
from memorylib import repo_root
from runtime_identity import current_package_version


PACKAGE_VERSION = current_package_version()


MCP_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}
MCP_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
MCP_PING = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
PINNED_SMOKE_IMAGE = "sha256:" + ("a" * 64)
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
INSTALL_SMOKE_PUBLIC_MEMORY = """---
id: mem_install_smoke_public
title: Install Smoke Public Ceiling
type: tool
reviewed: true
reviewed_by: Install Smoke
reviewed_at: 2026-07-26
status: active
scope: tool
project: null
tags: [install-smoke, public-ceiling]
aliases: [public package recall]
created_at: 2026-07-26
updated_at: 2026-07-26
confidence: 0.9
sensitivity: public
source:
  kind: manual
  ref: install-smoke
pin: false
decay: normal
review_after: 2026-10-26
---

Public ceiling package recall verifies public-only behavior from the installed artifact.
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
    completed = run_owned_capture(
        command,
        cwd=cwd,
        env=env,
        input_text=input_text,
        timeout_seconds=timeout,
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


def assert_mcp_initialize_and_ping(
    stdout: str,
    *,
    expected_version: str = PACKAGE_VERSION,
) -> None:
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
    server_info = init.get("serverInfo")
    if not isinstance(server_info, dict):
        raise InstallSmokeError("MCP initialize result missing serverInfo")
    if server_info.get("name") != "ai-dememory":
        raise InstallSmokeError("MCP initialize serverInfo name was not ai-dememory")
    if server_info.get("version") != expected_version:
        raise InstallSmokeError(
            "MCP initialize serverInfo version did not match installed package "
            f"{expected_version}"
        )
    if server_info.get("profile") != "core":
        raise InstallSmokeError("MCP initialize serverInfo profile was not core")
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


def installed_cli_version(stdout: str) -> str:
    match = re.fullmatch(r"ai-dememory\s+(\S+)\s*", stdout)
    if not match:
        raise InstallSmokeError("installed ai-dememory --version output was invalid")
    return match.group(1)


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
    resource_policy = data.get("resource_policy")
    if not isinstance(resource_policy, dict) or resource_policy.get("valid") is not True:
        raise InstallSmokeError("maintenance status missing a valid resource policy")
    if resource_policy.get("runtime_model_calls_per_maintenance_run") != 0:
        raise InstallSmokeError("maintenance status must report zero runtime model calls")
    if resource_policy.get("runtime_embedding_calls_per_maintenance_run") != 0:
        raise InstallSmokeError("maintenance status must report zero runtime embedding calls")


def string_argv(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(argument, str) for argument in value)


def expected_maintenance_run_command(
    *,
    profile: str,
    expected_root: str,
    mode: str,
    executable: str,
    image: str,
) -> list[str]:
    suffix = [
        "--root",
        "/memory" if mode == "docker" else expected_root,
        "maintenance",
        "run",
        "--profile",
        profile,
        "--timeout-seconds",
        "300",
    ]
    if mode == "installed":
        return [executable, *suffix]
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        "1.0",
        "--memory",
        "512m",
        "--pids-limit",
        "128",
        "-e",
        "AI_DEMEMORY_ROOT=/memory",
        "-v",
        f"{expected_root}:/memory",
        image,
        *suffix,
    ]


def expected_schedule_apply_command(
    *,
    expected_root: str,
    platform: str,
    mode: str,
    executable: str,
    image: str,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    intensity: str,
    fingerprint: str,
) -> list[str]:
    command = [
        "ai-dememory",
        "schedule",
        "--root",
        expected_root,
        "--command",
        executable,
        "setup",
        "--platform",
        platform,
        "--mode",
        mode,
        "--daily-time",
        daily_time,
        "--weekly-day",
        weekly_day,
        "--weekly-time",
        weekly_time,
        "--daily",
        "--weekly",
        "--intensity",
        intensity,
        "--expect-plan-sha256",
        fingerprint,
    ]
    if mode == "docker":
        command.extend(["--image", image])
    return command


def apply_command_is_exact(
    command: Any,
    expected: list[str],
) -> bool:
    return string_argv(command) and command == expected


def expected_schedule_namespace(root: str) -> str:
    root_path = Path(root)
    resolved = str(root_path.expanduser().resolve()).replace("\\", "/").casefold()
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", root_path.name.casefold()).strip("-")[:24] or "vault"
    return f"ai-dememory-{slug}-{digest}"


def expected_host_schedule_commands(
    *,
    platform: str,
    namespace: str,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    run_commands: dict[str, list[str]],
) -> dict[str, tuple[list[str], list[str] | None]]:
    expected: dict[str, tuple[list[str], list[str] | None]] = {}
    if platform == "linux":
        expected[f"{namespace}-daemon-reload"] = (
            ["systemctl", "--user", "daemon-reload"],
            None,
        )
    elif platform not in {"windows", "macos"}:
        raise InstallSmokeError(f"schedule plan platform {platform!r} is unsupported")

    for profile in ("daily", "weekly"):
        name = f"{namespace}-{profile}"
        run_command = run_commands[profile]
        if platform == "windows":
            cadence = ["DAILY"] if profile == "daily" else ["WEEKLY", "/D", weekly_day]
            start_time = daily_time if profile == "daily" else weekly_time
            host_command = [
                "schtasks",
                "/Create",
                "/TN",
                name,
                "/SC",
                *cadence,
                "/ST",
                start_time,
                "/TR",
                subprocess.list2cmdline(run_command),
            ]
        elif platform == "macos":
            plist = str(Path.home() / "Library" / "LaunchAgents" / f"{name}.plist")
            host_command = ["launchctl", "load", "-w", plist]
        else:
            host_command = ["systemctl", "--user", "enable", "--now", f"{name}.timer"]
        expected[name] = (host_command, run_command)
    return expected


def expected_cron_schedules(daily_time: str, weekly_day: str, weekly_time: str) -> dict[str, str]:
    time_pattern = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    if not time_pattern.fullmatch(daily_time) or not time_pattern.fullmatch(weekly_time):
        raise InstallSmokeError("schedule plan times must use HH:MM 24-hour format")
    weekdays = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}
    if weekly_day not in weekdays:
        raise InstallSmokeError("schedule plan weekly day is invalid")
    daily_hour, daily_minute = daily_time.split(":", 1)
    weekly_hour, weekly_minute = weekly_time.split(":", 1)
    return {
        "daily": f"{int(daily_minute)} {int(daily_hour)} * * *",
        "weekly": f"{int(weekly_minute)} {int(weekly_hour)} * * {weekdays[weekly_day]}",
    }


def expected_cron_line(schedule: str, command: list[str]) -> str:
    rendered_command = shlex.join(command).replace("%", r"\%")
    return f"{schedule} {rendered_command}"


def recompute_schedule_plan_fingerprint(data: dict[str, Any]) -> str:
    projection_fields = (
        "root",
        "action",
        "platform",
        "mode",
        "command",
        "image",
        "docker_image_immutable",
        "installable",
        "task_namespace",
        "intensity",
        "schedule",
        "commands",
        "cron_entries",
    )
    try:
        projection = {field: data[field] for field in projection_fields}
    except KeyError as exc:
        raise InstallSmokeError(f"schedule plan fingerprint projection missing field {exc.args[0]}") from exc
    encoded = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assert_schedule_plan(
    stdout: str,
    expected_mode: str = "installed",
    expected_root: str | None = None,
    expected_image: str | None = None,
) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"schedule plan did not return JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise InstallSmokeError("schedule plan JSON must be an object")

    if data.get("action") != "install":
        raise InstallSmokeError("schedule plan did not default to install action")
    if data.get("mode") != expected_mode:
        raise InstallSmokeError(f"schedule plan mode was {data.get('mode')!r}, expected {expected_mode!r}")
    reported_root = data.get("root")
    if not isinstance(reported_root, str) or not reported_root:
        raise InstallSmokeError("schedule plan missing vault root")
    if expected_root is not None and reported_root != expected_root:
        raise InstallSmokeError("schedule plan root does not match expected vault root")
    bound_root = expected_root or reported_root
    platform = data.get("platform")
    if platform not in {"windows", "linux", "macos"}:
        raise InstallSmokeError("schedule plan target platform must be windows, linux, or macos")
    executable = data.get("command")
    if executable != "ai-dememory":
        raise InstallSmokeError("schedule plan did not use the installed ai-dememory executable")
    image = data.get("image")
    if expected_mode == "installed":
        if image != "":
            raise InstallSmokeError("installed schedule plan must not include a Docker image")
    else:
        if not isinstance(image, str) or not image:
            raise InstallSmokeError("Docker schedule plan missing image")
        immutable_image = bool(
            re.fullmatch(r"sha256:[0-9a-fA-F]{64}", image)
            or re.fullmatch(r"[A-Za-z0-9._:/-]+@sha256:[0-9a-fA-F]{64}", image)
        )
        if not immutable_image:
            raise InstallSmokeError("Docker schedule plan image must be immutable")
        if expected_image is not None and image != expected_image:
            raise InstallSmokeError("Docker schedule plan image does not match expected image")
    for flag in ("mutates_system", "runs_commands", "writes_files", "installs_schedules"):
        if data.get(flag) is not False:
            raise InstallSmokeError(f"schedule plan {flag} must be false")
    if data.get("installable") is not True:
        raise InstallSmokeError("schedule plan must be installable")
    if data.get("resource_policy_valid") is not True:
        raise InstallSmokeError("schedule plan resource policy must be valid")
    if data.get("validation_errors") != []:
        raise InstallSmokeError("schedule plan validation errors must be empty")
    if data.get("docker_image_immutable") is not True:
        raise InstallSmokeError("schedule plan Docker image immutability flag must be true")

    schedule = data.get("schedule")
    if not isinstance(schedule, dict):
        raise InstallSmokeError("schedule plan missing schedule object")
    for field in ("daily_time", "weekly_day", "weekly_time"):
        if not isinstance(schedule.get(field), str) or not schedule[field]:
            raise InstallSmokeError(f"schedule plan missing schedule field {field}")
    if schedule.get("daily_enabled") is not True or schedule.get("weekly_enabled") is not True:
        raise InstallSmokeError("schedule plan smoke requires daily and weekly schedules")
    daily_time = schedule["daily_time"]
    weekly_day = schedule["weekly_day"]
    weekly_time = schedule["weekly_time"]
    cron_schedules = expected_cron_schedules(daily_time, weekly_day, weekly_time)

    commands = data.get("commands")
    if not isinstance(commands, list) or len(commands) < 2:
        raise InstallSmokeError("schedule plan missing scheduler commands")
    if not all(isinstance(command, dict) for command in commands):
        raise InstallSmokeError("schedule plan commands must be objects")
    namespace = data.get("task_namespace")
    if namespace != expected_schedule_namespace(bound_root):
        raise InstallSmokeError("schedule plan task namespace does not match the bound vault root")
    intensity = data.get("intensity")
    if intensity != "balanced":
        raise InstallSmokeError("schedule plan did not report the balanced default intensity")
    fingerprint = data.get("plan_sha256")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise InstallSmokeError("schedule plan missing review fingerprint")
    apply_command = data.get("apply_command")
    expected_apply = expected_schedule_apply_command(
        expected_root=bound_root,
        platform=platform,
        mode=expected_mode,
        executable=executable,
        image=image,
        daily_time=daily_time,
        weekly_day=weekly_day,
        weekly_time=weekly_time,
        intensity=intensity,
        fingerprint=fingerprint,
    )
    if not apply_command_is_exact(apply_command, expected_apply):
        raise InstallSmokeError(
            "schedule plan fingerprint-bound apply command did not match the exact schedule setup grammar"
        )

    run_commands = {
        profile: expected_maintenance_run_command(
            profile=profile,
            expected_root=bound_root,
            mode=expected_mode,
            executable=executable,
            image=image,
        )
        for profile in ("daily", "weekly")
    }
    for profile in ("daily", "weekly"):
        expected_name = f"{namespace}-{profile}"
        matching_commands = [command for command in commands if command.get("name") == expected_name]
        if len(matching_commands) != 1:
            raise InstallSmokeError(f"schedule plan must include exactly one named {profile} scheduler command")

    expected_host_commands = expected_host_schedule_commands(
        platform=platform,
        namespace=namespace,
        daily_time=daily_time,
        weekly_day=weekly_day,
        weekly_time=weekly_time,
        run_commands=run_commands,
    )
    observed_names = [command.get("name") for command in commands]
    if (
        not all(isinstance(name, str) for name in observed_names)
        or observed_names != list(expected_host_commands)
    ):
        raise InstallSmokeError(
            "schedule plan host commands must use the exact ordered daily, weekly, and Linux daemon-reload set"
        )
    for command in commands:
        name = command["name"]
        expected_host_command, expected_run_command = expected_host_commands[name]
        if command.get("platform") != platform or command.get("action") != "install":
            raise InstallSmokeError(f"schedule plan host command {name} has the wrong platform or action")
        if not string_argv(command.get("command")) or command.get("command") != expected_host_command:
            raise InstallSmokeError(f"schedule plan host command {name} did not match the exact {platform} grammar")
        if expected_run_command is None:
            if command.get("run_command") is not None:
                raise InstallSmokeError("schedule plan Linux daemon-reload must not include a maintenance command")
        elif not string_argv(command.get("run_command")) or command.get("run_command") != expected_run_command:
            profile = "daily" if name.endswith("-daily") else "weekly"
            raise InstallSmokeError(
                f"schedule plan {profile} maintenance run command did not match the exact {expected_mode} grammar"
            )

    cron_entries = data.get("cron_entries")
    if not isinstance(cron_entries, list) or len(cron_entries) != 2:
        raise InstallSmokeError("schedule plan should include exactly one daily and one weekly cron entry")
    if not all(isinstance(entry, dict) for entry in cron_entries):
        raise InstallSmokeError("schedule plan cron entries must be objects")
    for profile in ("daily", "weekly"):
        expected_name = f"{namespace}-{profile}"
        matching_entries = [entry for entry in cron_entries if entry.get("name") == expected_name]
        if len(matching_entries) != 1:
            raise InstallSmokeError(f"schedule plan must include exactly one named {profile} cron entry")
        entry = matching_entries[0]
        if entry.get("profile") != profile:
            raise InstallSmokeError(f"schedule plan {profile} cron entry has the wrong profile")
        expected_command = run_commands[profile]
        if not string_argv(entry.get("command")) or entry.get("command") != expected_command:
            raise InstallSmokeError(
                f"schedule plan {profile} maintenance cron command did not match the exact {expected_mode} grammar"
            )
        expected_schedule = cron_schedules[profile]
        if entry.get("schedule") != expected_schedule:
            raise InstallSmokeError(f"schedule plan {profile} cron schedule was not canonical")
        line = entry.get("line")
        if not isinstance(line, str) or line != expected_cron_line(expected_schedule, expected_command):
            raise InstallSmokeError(f"schedule plan {profile} maintenance cron line was not canonical")

    recomputed_fingerprint = recompute_schedule_plan_fingerprint(data)
    if fingerprint != recomputed_fingerprint:
        raise InstallSmokeError("schedule plan fingerprint did not match the canonical plan projection")


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
    if data.get("uses_trusted_publishing") is not False:
        raise InstallSmokeError("legacy publish preflight must not use trusted publishing")
    dispatch_inputs = data.get("dispatch_inputs")
    if (
        not isinstance(dispatch_inputs, dict)
        or dispatch_inputs.get("confirm") != "preflight"
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


def assert_onboarding(stdout: str, *, applied: bool) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"onboarding did not return JSON: {exc}") from exc
    if data.get("ok") is not True or data.get("applied") is not applied:
        raise InstallSmokeError("onboarding apply/preview state was incorrect")
    if data.get("auto_promotes") is not False or data.get("durable_memory_reviewed") is not True:
        raise InstallSmokeError("onboarding review-first boundary was missing")
    if data.get("setup_scope") != "durable_baseline" or data.get("writes_config") is not False:
        raise InstallSmokeError("onboarding crossed the memory-only boundary")
    if not isinstance(data.get("writes"), list) or len(data["writes"]) < 4:
        raise InstallSmokeError("onboarding did not plan the minimum memory baseline")
    if any(item.get("kind") != "memory" for item in data["writes"] if isinstance(item, dict)):
        raise InstallSmokeError("onboarding planned a non-memory write")
    if not isinstance(data.get("plan_sha256"), str) or len(data["plan_sha256"]) != 64:
        raise InstallSmokeError("onboarding did not return a reviewable plan fingerprint")
    if applied and not data.get("changed"):
        raise InstallSmokeError("onboarding apply did not write the reviewed baseline")
    if "resource_policy" in data or "integrations" in data:
        raise InstallSmokeError("onboarding leaked operational setup into its fingerprint")


def assert_operational_setup(stdout: str, *, applied: bool) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"operational setup did not return JSON: {exc}") from exc
    if data.get("ok") is not True or data.get("applied") is not applied:
        raise InstallSmokeError("operational setup apply/preview state was incorrect")
    if data.get("setup_scope") != "operational" or data.get("writes_config") is not True:
        raise InstallSmokeError("operational setup did not stay config-only")
    if data.get("durable_memory_reviewed") is not False or data.get("auto_promotes") is not False:
        raise InstallSmokeError("operational setup claimed durable memory review or promotion")
    writes = data.get("writes")
    if not isinstance(writes, list) or len(writes) != 1 or not isinstance(writes[0], dict):
        raise InstallSmokeError("operational setup must plan exactly one config write")
    if writes[0].get("path") != ".ai-dememory.toml" or writes[0].get("kind") != "config":
        raise InstallSmokeError("operational setup planned a write outside .ai-dememory.toml")
    if not isinstance(data.get("plan_sha256"), str) or len(data["plan_sha256"]) != 64:
        raise InstallSmokeError("operational setup did not return a reviewable fingerprint")
    if applied and data.get("changed") != [".ai-dememory.toml"]:
        raise InstallSmokeError("operational setup did not apply exactly the reviewed config")
    policy = data.get("resource_policy")
    if not isinstance(policy, dict) or policy.get("intensity") != "balanced":
        raise InstallSmokeError("operational setup did not expose the selected balanced resource policy")
    if policy.get("runtime_model_calls_per_maintenance_run") != 0:
        raise InstallSmokeError("operational setup must report zero runtime model calls")
    if policy.get("runtime_embedding_calls_per_maintenance_run") != 0:
        raise InstallSmokeError("operational setup must report zero runtime embedding calls")
    integrations = data.get("integrations")
    if not isinstance(integrations, dict) or integrations.get("vault_bound") is not True:
        raise InstallSmokeError("operational setup did not return vault-bound integration previews")
    if integrations.get("installs_hooks") is not False or integrations.get("installs_schedules") is not False:
        raise InstallSmokeError("operational setup crossed an integration apply boundary")


def assert_setup_plan(
    stdout: str,
    *,
    expected_root: Path,
) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"setup plan did not return JSON: {exc}") from exc
    commands = data.get("commands")
    if data.get("mode") != "both" or data.get("client") != "codex":
        raise InstallSmokeError("setup plan did not preserve the requested client and both runtime modes")
    if Path(str(data.get("root"))).resolve() != expected_root.resolve():
        raise InstallSmokeError("setup plan did not bind the expected absolute vault root")
    if not isinstance(commands, dict):
        raise InstallSmokeError("setup plan did not return a commands object")

    def require_global_root(command: object, label: str) -> list[str]:
        if not isinstance(command, list) or not all(isinstance(argument, str) for argument in command):
            raise InstallSmokeError(f"setup plan returned a malformed command for {label}")
        root_indexes = [
            index
            for index, argument in enumerate(command)
            if argument == "--root" or argument.startswith("--root=")
        ]
        if len(command) < 3 or root_indexes != [1] or command[1] != "--root":
            raise InstallSmokeError(
                f"setup plan {label} must use exactly one global vault root at argv positions 1-2"
            )
        if Path(command[2]).resolve() != expected_root.resolve():
            raise InstallSmokeError(f"setup plan {label} selected the wrong vault root")
        return command

    generated_commands: list[tuple[str, object]] = []
    for name, value in commands.items():
        if isinstance(value, dict):
            generated_commands.extend(
                (f"commands.{name}.{nested_name}", nested_value)
                for nested_name, nested_value in value.items()
            )
        elif isinstance(value, list):
            if not value:
                continue
            if all(isinstance(argument, str) for argument in value):
                generated_commands.append((f"commands.{name}", value))
            else:
                generated_commands.extend(
                    (f"commands.{name}[{index}]", nested_value)
                    for index, nested_value in enumerate(value)
                )
        else:
            raise InstallSmokeError(f"setup plan returned an unsupported command group for {name}")

    provider_plan = data.get("provider_plan")
    providers = provider_plan.get("providers") if isinstance(provider_plan, dict) else None
    if not isinstance(providers, list):
        raise InstallSmokeError("setup plan did not return a provider command plan")
    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            raise InstallSmokeError("setup plan returned a malformed provider command plan")
        for key in (
            "configure_dry_run_command",
            "configure_command",
            "disable_command",
            "import_dry_run_command",
            "import_command",
        ):
            generated_commands.append((f"provider_plan.providers[{index}].{key}", provider.get(key)))

    for label, command in generated_commands:
        require_global_root(command, label)

    mcp_configs = commands.get("mcp_configs")
    if not isinstance(mcp_configs, list) or len(mcp_configs) != 2:
        raise InstallSmokeError("setup plan did not return one installed and one Docker MCP command")
    observed_modes: set[str] = set()
    for command in mcp_configs:
        if not isinstance(command, list) or not all(isinstance(argument, str) for argument in command):
            raise InstallSmokeError("setup plan returned a malformed MCP configuration command")
        if "--require-version" in command:
            raise InstallSmokeError(
                "setup plan MCP configuration must not emit the legacy version gate"
            )
        mode_indexes = [index for index, argument in enumerate(command) if argument == "--mode"]
        if len(mode_indexes) != 1 or mode_indexes[0] + 1 >= len(command):
            raise InstallSmokeError("setup plan MCP configuration is missing one runtime mode")
        observed_modes.add(command[mode_indexes[0] + 1])
    if observed_modes != {"installed", "docker"}:
        raise InstallSmokeError("setup plan MCP commands did not cover installed and Docker modes")


def assert_turn_context(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"turn context did not return JSON: {exc}") from exc
    if data.get("decision") != "inject" or data.get("query_source") != "turn":
        raise InstallSmokeError("turn context did not inject prompt-aware memory")
    if not data.get("items") or not str(data.get("text", "")).strip():
        raise InstallSmokeError("turn context did not return bounded memory items")


def assert_public_context(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"public context did not return JSON: {exc}") from exc
    if data.get("public_only") is not True:
        raise InstallSmokeError("public context did not report the public-only ceiling")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise InstallSmokeError("public context did not return the public fixture")
    if any(item.get("sensitivity") != "public" for item in items if isinstance(item, dict)):
        raise InstallSmokeError("public context returned a non-public item")
    working = data.get("working_memory")
    if not isinstance(working, dict) or working.get("included") is not False:
        raise InstallSmokeError("public context included generated working memory")
    serialized = json.dumps(data)
    if "mem_install_smoke_policy" in serialized or "Install Smoke Working State" in serialized:
        raise InstallSmokeError("public context exposed internal memory or working state")


def assert_public_search(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"public search did not return JSON: {exc}") from exc
    if not isinstance(data, list) or [item.get("id") for item in data] != ["mem_install_smoke_public"]:
        raise InstallSmokeError("public search did not return only the public fixture")
    if any(item.get("sensitivity") not in {None, "public"} for item in data):
        raise InstallSmokeError("public search returned a non-public sensitivity")


def assert_hook_dispatch(stdout: str) -> None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise InstallSmokeError(f"hook dispatch did not return JSON: {exc}") from exc
    output = data.get("hookSpecificOutput")
    if not isinstance(output, dict) or output.get("hookEventName") != "UserPromptSubmit":
        raise InstallSmokeError("hook dispatch did not return UserPromptSubmit context")
    context = str(output.get("additionalContext", "")).strip()
    if not context:
        raise InstallSmokeError("hook dispatch additionalContext was empty")
    if "Install Smoke Public Ceiling" not in context:
        raise InstallSmokeError("hook dispatch did not return the public-only fixture")
    if "mem_install_smoke_policy" in context or "Install Smoke Policy" in context:
        raise InstallSmokeError("hook dispatch exposed the internal install-smoke fixture")


def package_smoke_commands() -> list[tuple[str, list[str]]]:
    return [
        ("doctor", ["doctor"]),
        (
            "setup preview",
            ["setup", "wizard", "--intensity", "balanced", "--json"],
        ),
        (
            "setup apply",
            ["setup", "wizard", "--intensity", "balanced", "--apply", "--json"],
        ),
        (
            "onboarding preview",
            [
                "onboard", "--reviewed-by", "Install Smoke", "--value", "Prefer safe package checks.",
                "--preference", "Run isolated install smoke first.", "--recommendation",
                "Recall install smoke project memory.", "--project", "install-smoke", "--json",
            ],
        ),
        (
            "onboarding apply",
            [
                "onboard", "--reviewed-by", "Install Smoke", "--value", "Prefer safe package checks.",
                "--preference", "Run isolated install smoke first.", "--recommendation",
                "Recall install smoke project memory.", "--project", "install-smoke", "--apply", "--json",
            ],
        ),
        ("validate", ["validate"]),
        ("secret scan", ["secret-scan"]),
        ("index", ["index"]),
        (
            "turn context",
            ["turn-context", "continue install smoke package policy", "--cwd", "{vault}", "--json"],
        ),
        (
            "hook prompt dispatch",
            ["hook-event", "dispatch", "--client", "codex", "--event", "UserPromptSubmit"],
        ),
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
            "context public only",
            [
                "context",
                "public",
                "ceiling",
                "package",
                "recall",
                "--public-only",
                "--no-working-memory",
                "--limit",
                "1",
                "--budget",
                "700",
                "--json",
            ],
        ),
        (
            "search public only",
            ["search", "public", "ceiling", "package", "recall", "--public-only", "--limit", "1", "--json"],
        ),
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
        (
            "mcp public context",
            [
                "mcp",
                "--call",
                "memory.context",
                "--args",
                '{"query":"public ceiling package recall","public_only":true,"include_working_memory":true,"limit":1}',
            ],
        ),
        ("api smoke", ["api-smoke"]),
        ("vault template export", ["vault-template", "export", "{template_export}", "--json"]),
        (
            "mcp config",
            ["mcp-config", "--client", "codex"],
        ),
        (
            "setup plan",
            [
                "setup",
                "plan",
                "--client",
                "codex",
                "--mode",
                "both",
                "--json",
            ],
        ),
        ("setup health", ["setup", "health", "--json"]),
        ("mcp client config smoke", ["mcp-client-smoke", "--command", "{ai_dememory}"]),
        (
            "plugin mcp config smoke",
            ["mcp-client-smoke", "--config", "{plugin_mcp}", "--command", "{ai_dememory}"],
        ),
        (
            "docker mcp config",
            [
                "mcp-config",
                "--client",
                "codex",
                "--mode",
                "docker",
            ],
        ),
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
        (
            "docker schedule plan",
            ["schedule", "plan", "--mode", "docker", "--image", PINNED_SMOKE_IMAGE, "--json"],
        ),
        ("schedule dry run", ["schedule", "setup", "--dry-run"]),
        ("docker schedule dry run", ["schedule", "setup", "--dry-run", "--mode", "docker", "--image", PINNED_SMOKE_IMAGE]),
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
    public_path = vault / "memories" / "tools" / "install-smoke-public.md"
    public_path.write_text(INSTALL_SMOKE_PUBLIC_MEMORY, encoding="utf-8")
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
        install_env = {**os.environ, "PIP_NO_CACHE_DIR": "1"}
        run_step(steps, "install package", [str(pip), "install", package], cwd=root, env=install_env)
        version_result = run_step(steps, "installed version", [str(ai_dememory), "--version"])
        expected_installed_version = installed_cli_version(version_result.stdout)
        if expected_installed_version != PACKAGE_VERSION:
            raise InstallSmokeError(
                "installed package version mismatch: "
                f"expected {PACKAGE_VERSION}, found {expected_installed_version}"
            )
        run_step(
            steps,
            "installed exact-version check",
            [str(ai_dememory), "version-check", PACKAGE_VERSION],
        )
        mismatch = run_step(
            steps,
            "installed version mismatch fails closed",
            [str(ai_dememory), "version-check", "0.0.0"],
            allowed_returncodes={1},
        )
        expected_mismatch = f"expected 0.0.0, found {expected_installed_version}"
        if expected_mismatch not in mismatch.stderr:
            raise InstallSmokeError("installed version-check mismatch did not report exact versions")
        run_step(steps, "init vault", [str(ai_dememory), "init", str(vault)])
        write_install_smoke_memory(vault)
        sample.write_text("# Install Smoke\n\nCapture this non-secret note.\n", encoding="utf-8")
        env = {**os.environ, "AI_DEMEMORY_ROOT": str(vault)}
        setup_plan_sha256: str | None = None
        setup_config_text: str | None = None
        onboarding_plan_sha256: str | None = None
        doctor_summary = run_step(
            steps,
            "doctor summary",
            [str(ai_dememory), "doctor", "--json", "--summary"],
            cwd=vault,
            env=env,
        )
        assert_doctor_summary(doctor_summary.stdout)
        for name, args in package_smoke_commands():
            input_text = None
            command_args = materialize_args(args, root, vault, sample, ai_dememory, template_export)
            if name == "setup apply":
                if not setup_plan_sha256:
                    raise InstallSmokeError("setup preview did not return a plan fingerprint")
                command_args.extend(["--expect-plan-sha256", setup_plan_sha256])
            if name == "onboarding apply":
                if not onboarding_plan_sha256:
                    raise InstallSmokeError("onboarding preview did not return a plan fingerprint")
                command_args.extend(["--expect-plan-sha256", onboarding_plan_sha256])
            if name == "hook prompt dispatch":
                input_text = json.dumps(
                    {
                        "prompt": "continue public ceiling package recall",
                        "cwd": str(vault),
                        "session_id": "install-smoke",
                    }
                )
            completed = run_step(
                steps,
                name,
                [str(ai_dememory), *command_args],
                cwd=vault,
                env=env,
                allowed_returncodes={0, 1} if name == "roadmap status" else None,
                input_text=input_text,
            )
            if name == "setup preview":
                assert_operational_setup(completed.stdout, applied=False)
                setup_plan_sha256 = str(json.loads(completed.stdout).get("plan_sha256") or "")
            if name == "setup plan":
                assert_setup_plan(
                    completed.stdout,
                    expected_root=vault,
                )
            if name == "setup apply":
                assert_operational_setup(completed.stdout, applied=True)
                setup_config_text = (vault / ".ai-dememory.toml").read_text(encoding="utf-8")
                for filename in (
                    "onboarding-values.md",
                    "onboarding-preferences.md",
                    "onboarding-recommendations.md",
                ):
                    if (vault / "memories" / "durable" / filename).exists():
                        raise InstallSmokeError("operational setup created personal durable memory")
            if name == "onboarding preview":
                assert_onboarding(completed.stdout, applied=False)
                onboarding_plan_sha256 = str(json.loads(completed.stdout).get("plan_sha256") or "")
            if name == "onboarding apply":
                assert_onboarding(completed.stdout, applied=True)
                if setup_config_text is None:
                    raise InstallSmokeError("operational setup config snapshot was unavailable")
                if (vault / ".ai-dememory.toml").read_text(encoding="utf-8") != setup_config_text:
                    raise InstallSmokeError("onboarding modified operational configuration")
            if name == "turn context":
                assert_turn_context(completed.stdout)
            if name in {"context public only", "mcp public context"}:
                assert_public_context(completed.stdout)
            if name == "search public only":
                assert_public_search(completed.stdout)
            if name == "hook prompt dispatch":
                assert_hook_dispatch(completed.stdout)
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
            if name == "docker schedule plan":
                assert_schedule_plan(
                    completed.stdout,
                    expected_mode="docker",
                    expected_root=str(vault.resolve()),
                    expected_image=PINNED_SMOKE_IMAGE,
                )
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
        assert_mcp_initialize_and_ping(mcp.stdout, expected_version=expected_installed_version)
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
