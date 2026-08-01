#!/usr/bin/env python3
"""Install, inspect, and remove opt-in ai-dememory maintenance schedules."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

from config_file import load_config
from config_file import set_section
from maintenance import review_due_summary
from memorylib import path_is_link_like, repo_root, safe_write_text
from process_control import run_owned_capture, run_owned_process
from resource_policy import get_resource_profile, profile_names, resolved_resource_policy


WEEKDAYS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}
SCHEDULER_COMMAND_TIMEOUT_SECONDS = 60
SCHEDULE_VERIFICATION_TTL_SECONDS = 300
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ScheduleCommand:
    name: str
    platform: str
    action: str
    command: list[str]
    run_command: list[str] | None = None
    definition_text: str | None = None


@dataclass(frozen=True)
class CronEntry:
    name: str
    profile: str
    schedule: str
    command: list[str]
    line: str


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    command: str
    available: bool
    path: str | None
    required: bool
    purpose: str


def immutable_docker_image(image: str) -> bool:
    """Return whether a Docker reference is pinned to immutable content."""

    normalized = image.strip()
    if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", normalized):
        return True
    if "@sha256:" not in normalized:
        return False
    repository, digest = normalized.rsplit("@sha256:", 1)
    return bool(
        repository
        and re.fullmatch(r"[A-Za-z0-9._:/-]+", repository)
        and re.fullmatch(r"[0-9a-fA-F]{64}", digest)
    )


def encode_definition_digests(digests: dict[str, str]) -> list[str]:
    return [f"{key}={value}" for key, value in sorted(digests.items())]


def decode_definition_digests(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        return {}
    decoded: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str) or "=" not in item:
            return {}
        key, digest = item.rsplit("=", 1)
        if not key or not SHA256_PATTERN.fullmatch(digest):
            return {}
        decoded[key] = digest
    return dict(sorted(decoded.items()))


def decode_plan_projection(value: object) -> dict[str, object]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def verification_fresh(verified_at: str, *, now: datetime | None = None) -> bool:
    if not verified_at:
        return False
    try:
        verified = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if verified.tzinfo is None:
        verified = verified.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    age = (current.astimezone(timezone.utc) - verified.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= SCHEDULE_VERIFICATION_TTL_SECONDS


def platform_name() -> str:
    name = platform.system().lower()
    if name.startswith("windows"):
        return "windows"
    if name == "darwin":
        return "macos"
    return "linux"


def host_scheduler_command(target_platform: str) -> str:
    if target_platform == "windows":
        return "schtasks"
    if target_platform == "macos":
        return "launchctl"
    return "systemctl"


def command_check(name: str, command: str, required: bool, purpose: str) -> EnvironmentCheck:
    path = shutil.which(command)
    return EnvironmentCheck(
        name=name,
        command=command,
        available=path is not None,
        path=path,
        required=required,
        purpose=purpose,
    )


def schedule_environment(
    target_platform: str | None = None,
    mode: str = "installed",
) -> dict[str, object]:
    if mode not in {"installed", "docker"}:
        raise ValueError("mode must be installed or docker")
    platform_value = target_platform or platform_name()
    checks = [
        command_check(
            "host_scheduler",
            host_scheduler_command(platform_value),
            True,
            "Previewed schedule setup/status/remove commands for the target platform.",
        ),
        command_check(
            "docker",
            "docker",
            mode == "docker",
            "Required only when schedule mode is docker.",
        ),
        command_check(
            "cron_export_installer",
            "crontab",
            False,
            "Optional helper for manually installing reviewed `schedule cron` output.",
        ),
    ]
    required_missing = [check for check in checks if check.required and not check.available]
    return {
        "platform": platform_value,
        "mode": mode,
        "ready": not required_missing,
        "required_missing": [check.name for check in required_missing],
        "checks": [asdict(check) for check in checks],
        "mutates_system": False,
        "runs_commands": False,
    }


def schedule_namespace(root: Path) -> str:
    resolved = str(root.expanduser().resolve()).replace("\\", "/").casefold()
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", root.name.casefold()).strip("-")[:24] or "vault"
    return f"ai-dememory-{slug}-{digest}"


def schedule_task_name(
    root: Path,
    profile: str,
    task_namespace: str | None = None,
) -> str:
    if profile not in {"daily", "weekly"}:
        raise ValueError("profile must be daily or weekly")
    namespace = task_namespace or schedule_namespace(root)
    if not re.fullmatch(r"ai-dememory-[a-z0-9-]{1,48}-[0-9a-f]{10}", namespace):
        raise ValueError("invalid schedule task namespace")
    return f"{namespace}-{profile}"


def configure_schedule(
    root: Path,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    mode: str,
    image: str,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    intensity: str | None = None,
    target_platform: str | None = None,
    plan_sha256: str = "",
    definition_digests: dict[str, str] | None = None,
    command: str = "ai-dememory",
) -> Path:
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    installed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    resolved_intensity = str(resolved_resource_policy(root, intensity=intensity)["intensity"])
    platform_value = target_platform or platform_name()
    digests = dict(sorted((definition_digests or {}).items()))
    if digests and not all(SHA256_PATTERN.fullmatch(value) for value in digests.values()):
        raise ValueError("schedule definition digests must be lowercase SHA-256 values")
    if plan_sha256 and not SHA256_PATTERN.fullmatch(plan_sha256):
        raise ValueError("schedule plan fingerprint must be a lowercase SHA-256 value")
    plan_projection = ""
    if plan_sha256:
        reviewed_plan = schedule_plan(
            root,
            action="install",
            daily_time=daily_time,
            weekly_day=weekly_day,
            weekly_time=weekly_time,
            command=command,
            mode=mode,
            image=image,
            target_platform=platform_value,
            daily_enabled=daily_enabled,
            weekly_enabled=weekly_enabled,
            intensity=resolved_intensity,
        )
        if not hmac.compare_digest(
            str(reviewed_plan["plan_sha256"]),
            plan_sha256,
        ):
            raise ValueError("schedule receipt does not match the exact reviewed plan")
        plan_projection = json.dumps(
            schedule_plan_projection(reviewed_plan),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    return set_section(
        root,
        "schedule",
        {
            "enabled": True,
            "daily_enabled": daily_enabled,
            "weekly_enabled": weekly_enabled,
            "daily_time": daily_time,
            "weekly_day": weekly_day,
            "weekly_time": weekly_time,
            "mode": mode,
            "image": image if mode == "docker" else "",
            "platform": platform_value,
            "intensity": resolved_intensity,
            "root": str(root.expanduser().resolve()),
            "command": command,
            "plan_sha256": plan_sha256,
            "plan_projection": plan_projection,
            "definition_digests": encode_definition_digests(digests),
            "task_namespace": schedule_namespace(root),
            "installed_profiles": [
                profile
                for profile, enabled in (("daily", daily_enabled), ("weekly", weekly_enabled))
                if enabled
            ],
            "installed_at": installed_at,
            "verified_at": installed_at if digests and plan_sha256 else "",
        },
    )


def disable_schedule(root: Path) -> Path:
    config = load_config(root).get("schedule", {})
    current = dict(config) if isinstance(config, dict) else {}
    current.update(
        {
            "enabled": False,
            "installed_profiles": [],
            "installed_at": "",
            "verified_at": "",
            "plan_sha256": "",
            "plan_projection": "",
            "definition_digests": [],
            "task_namespace": schedule_namespace(root),
        }
    )
    return set_section(root, "schedule", current)


def mark_schedule_verified(root: Path, observed_definition_digests: dict[str, str]) -> Path:
    config = load_config(root).get("schedule", {})
    current = dict(config) if isinstance(config, dict) else {}
    if not current.get("enabled", False):
        raise ValueError("cannot verify a schedule that is not configured as enabled")
    expected = decode_definition_digests(current.get("definition_digests"))
    if not expected:
        raise ValueError("cannot verify a schedule without an exact definition receipt")
    if not hmac.compare_digest(
        json.dumps(expected, sort_keys=True, separators=(",", ":")),
        json.dumps(observed_definition_digests, sort_keys=True, separators=(",", ":")),
    ):
        raise ValueError("host schedule definitions differ from the install receipt")
    current["verified_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return set_section(root, "schedule", current)


def clear_schedule_verification(root: Path) -> Path | None:
    config = load_config(root).get("schedule", {})
    current = dict(config) if isinstance(config, dict) else {}
    if not current.get("enabled", False) or not current.get("verified_at"):
        return None
    current["verified_at"] = ""
    return set_section(root, "schedule", current)


def maintenance_run_args(
    root: Path,
    profile: str,
    command: str,
    mode: str,
    image: str,
    intensity: str | None = None,
) -> list[str]:
    policy = resolved_resource_policy(root, intensity=intensity)
    timeout_seconds = int(policy["resources"]["maintenance_timeout_seconds"])
    if mode == "docker":
        intensity = str(policy["intensity"])
        docker_limits = {
            "minimal": ("0.5", "256m", "64"),
            "balanced": ("1.0", "512m", "128"),
            "active": ("2.0", "1g", "256"),
        }
        cpus, memory, pids = docker_limits[intensity]
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            cpus,
            "--memory",
            memory,
            "--pids-limit",
            pids,
            "-e",
            "AI_DEMEMORY_ROOT=/memory",
            "-v",
            f"{root}:/memory",
            image,
            "--root",
            "/memory",
            "maintenance",
            "run",
            "--profile",
            profile,
            "--timeout-seconds",
            str(timeout_seconds),
        ]
    return [
        command,
        "--root",
        str(root),
        "maintenance",
        "run",
        "--profile",
        profile,
        "--timeout-seconds",
        str(timeout_seconds),
    ]


def command_line(args: list[str]) -> str:
    return shlex.join(args)


def cron_command_line(args: list[str]) -> str:
    """Render a cron command while escaping cron's percent/newline syntax."""

    return command_line(args).replace("%", r"\%")


def windows_command_line(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def parse_time(value: str) -> tuple[int, int]:
    normalized = normalize_time(value, "time")
    hour, minute = normalized.split(":", 1)
    return int(hour), int(minute)


def normalize_time(value: str, field: str) -> str:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"{field} must use HH:MM 24-hour time")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"{field} must use HH:MM 24-hour time")
    return f"{hour:02d}:{minute:02d}"


def normalize_weekday(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in WEEKDAYS:
        raise ValueError("weekly_day must be one of SUN, MON, TUE, WED, THU, FRI, SAT")
    return normalized


def cron_weekday(value: str) -> int:
    return WEEKDAYS[normalize_weekday(value)]


def build_cron_entries(
    root: Path,
    daily_time: str = "03:00",
    weekly_day: str = "SUN",
    weekly_time: str = "04:00",
    command: str = "ai-dememory",
    mode: str = "installed",
    image: str = "ai-dememory:local",
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    intensity: str | None = None,
) -> list[CronEntry]:
    if mode not in {"installed", "docker"}:
        raise ValueError("mode must be installed or docker")
    if mode == "docker" and not immutable_docker_image(image):
        raise ValueError("scheduled Docker images must use an immutable sha256 digest")
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    daily_hour, daily_minute = parse_time(daily_time)
    weekly_hour, weekly_minute = parse_time(weekly_time)
    weekly_day_number = cron_weekday(weekly_day)
    entries = []
    if daily_enabled:
        entries.append(
            (
            schedule_task_name(root, "daily"),
            "daily",
            f"{daily_minute} {daily_hour} * * *",
            maintenance_run_args(root, "daily", command, mode, image, intensity),
            )
        )
    if weekly_enabled:
        entries.append(
            (
            schedule_task_name(root, "weekly"),
            "weekly",
            f"{weekly_minute} {weekly_hour} * * {weekly_day_number}",
            maintenance_run_args(root, "weekly", command, mode, image, intensity),
            )
        )
    if not entries:
        raise ValueError("at least one of daily_enabled or weekly_enabled must be true")
    return [
        CronEntry(
            name=name,
            profile=profile,
            schedule=schedule,
            command=args,
            line=f"{schedule} {cron_command_line(args)}",
        )
        for name, profile, schedule, args in entries
    ]


def render_cron_entries(entries: list[CronEntry]) -> str:
    lines = [
        "# ai-dememory maintenance schedule",
        "# Review before installing with crontab. Package/plugin install never writes cron jobs.",
    ]
    for entry in entries:
        lines.append(f"# {entry.name} ({entry.profile})")
        lines.append(entry.line)
    return "\n".join(lines) + "\n"


def build_schedule_commands(
    root: Path,
    action: str,
    daily_time: str = "03:00",
    weekly_day: str = "SUN",
    weekly_time: str = "04:00",
    command: str = "ai-dememory",
    mode: str = "installed",
    image: str = "ai-dememory:local",
    target_platform: str | None = None,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    intensity: str | None = None,
    task_namespace: str | None = None,
) -> list[ScheduleCommand]:
    if mode not in {"installed", "docker"}:
        raise ValueError("mode must be installed or docker")
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    system = target_platform or platform_name()
    daily_args = maintenance_run_args(root, "daily", command, mode, image, intensity)
    weekly_args = maintenance_run_args(root, "weekly", command, mode, image, intensity)
    selected = [
        (profile, args)
        for profile, args, enabled in (
            ("daily", daily_args, daily_enabled),
            ("weekly", weekly_args, weekly_enabled),
        )
        if enabled
    ]
    if not selected:
        raise ValueError("at least one of daily_enabled or weekly_enabled must be true")

    if system == "windows":
        output: list[ScheduleCommand] = []
        for profile, run_args in selected:
            name = schedule_task_name(root, profile, task_namespace)
            if action in {"install", "setup"}:
                cadence = ["DAILY"] if profile == "daily" else ["WEEKLY", "/D", weekly_day]
                start_time = daily_time if profile == "daily" else weekly_time
                output.append(
                    ScheduleCommand(
                        name,
                        system,
                        action,
                        [
                            "schtasks",
                            "/Create",
                            "/TN",
                            name,
                            "/SC",
                            *cadence,
                            "/ST",
                            start_time,
                            "/TR",
                            windows_command_line(run_args),
                        ],
                        run_args,
                    )
                )
            elif action == "remove":
                output.append(
                    ScheduleCommand(name, system, action, ["schtasks", "/Delete", "/TN", name, "/F"])
                )
            else:
                output.append(
                    ScheduleCommand(name, system, action, ["schtasks", "/Query", "/TN", name, "/XML"])
                )
        return output

    if system == "macos":
        output = []
        for profile, run_args in selected:
            name = schedule_task_name(root, profile, task_namespace)
            plist = str(Path.home() / "Library" / "LaunchAgents" / f"{name}.plist")
            verb = "load" if action in {"install", "setup"} else "unload" if action == "remove" else "list"
            command_args = ["launchctl", verb]
            if verb in {"load", "unload"}:
                command_args.extend(["-w", plist])
            else:
                command_args.append(name)
            output.append(
                ScheduleCommand(
                    name,
                    system,
                    action,
                    command_args,
                    run_args if action in {"install", "setup"} else None,
                )
            )
        return output

    output = []
    if action in {"install", "setup"}:
        output.append(
            ScheduleCommand(
                f"{task_namespace or schedule_namespace(root)}-daemon-reload",
                system,
                action,
                ["systemctl", "--user", "daemon-reload"],
            )
        )
    for profile, run_args in selected:
        name = schedule_task_name(root, profile, task_namespace)
        timer = f"{name}.timer"
        if action in {"install", "setup"}:
            command_args = ["systemctl", "--user", "enable", "--now", timer]
        elif action == "remove":
            command_args = ["systemctl", "--user", "disable", "--now", timer]
        else:
            command_args = ["systemctl", "--user", "status", timer]
        output.append(
            ScheduleCommand(
                name,
                system,
                action,
                command_args,
                run_args if action in {"install", "setup"} else None,
            )
        )
    return output


def schedule_plan(
    root: Path,
    action: str = "install",
    daily_time: str = "03:00",
    weekly_day: str = "SUN",
    weekly_time: str = "04:00",
    command: str = "ai-dememory",
    mode: str = "installed",
    image: str = "ai-dememory:local",
    target_platform: str | None = None,
    daily_enabled: bool | None = None,
    weekly_enabled: bool | None = None,
    intensity: str | None = None,
) -> dict[str, object]:
    if action == "setup":
        action = "install"
    if action not in {"install", "status", "remove"}:
        raise ValueError("action must be install, status, or remove")
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    platform_value = target_platform or platform_name()
    resource_policy = resolved_resource_policy(root, intensity=intensity)
    if daily_enabled is None:
        daily_enabled = bool(resource_policy["daily_enabled"])
    if weekly_enabled is None:
        weekly_enabled = bool(resource_policy["weekly_enabled"])
    docker_image_immutable = mode != "docker" or immutable_docker_image(image)
    installable = action != "install" or docker_image_immutable
    commands = build_schedule_commands(
        root,
        action,
        daily_time=daily_time,
        weekly_day=weekly_day,
        weekly_time=weekly_time,
        command=command,
        mode=mode,
        image=image,
        target_platform=platform_value,
        daily_enabled=daily_enabled,
        weekly_enabled=weekly_enabled,
        intensity=str(resource_policy["intensity"]),
    )
    cron_entries = (
        build_cron_entries(
            root,
            daily_time=daily_time,
            weekly_day=weekly_day,
            weekly_time=weekly_time,
            command=command,
            mode=mode,
            image=image,
            daily_enabled=daily_enabled,
            weekly_enabled=weekly_enabled,
            intensity=str(resource_policy["intensity"]),
        )
        if action == "install" and installable
        else []
    )
    result: dict[str, object] = {
        "root": str(root),
        "action": action,
        "platform": platform_value,
        "mode": mode,
        "command": command,
        "image": image if mode == "docker" else "",
        "docker_image_immutable": docker_image_immutable,
        "installable": installable,
        "task_namespace": schedule_namespace(root),
        "intensity": resource_policy["intensity"],
        "schedule": {
            "daily_enabled": daily_enabled,
            "weekly_enabled": weekly_enabled,
            "daily_time": daily_time,
            "weekly_day": weekly_day,
            "weekly_time": weekly_time,
        },
        "commands": [asdict(item) for item in commands],
        "cron_entries": [asdict(item) for item in cron_entries],
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "installs_schedules": False,
        "next_actions": [
            "Review the platform scheduler commands and plan fingerprint before applying them.",
            "Use the cron entries only on hosts where reviewed crontab installation is appropriate.",
            "Run `ai-dememory schedule doctor --json` to check local scheduler command availability.",
        ],
    }
    if not installable:
        result["next_actions"].insert(
            0,
            "Resolve the Docker image to repo@sha256:<digest>; mutable tags cannot be installed unattended.",
        )
    result["plan_sha256"] = schedule_plan_fingerprint(result)
    apply_command = [
        "ai-dememory",
        "schedule",
        "--root",
        str(root),
        "--command",
        command,
        "setup",
        "--platform",
        platform_value,
        "--mode",
        mode,
        "--daily-time",
        daily_time,
        "--weekly-day",
        weekly_day,
        "--weekly-time",
        weekly_time,
        "--daily" if daily_enabled else "--no-daily",
        "--weekly" if weekly_enabled else "--no-weekly",
        "--intensity",
        str(resource_policy["intensity"]),
        "--expect-plan-sha256",
        str(result["plan_sha256"]),
    ]
    if mode == "docker":
        apply_command.extend(["--image", image])
    result["apply_command"] = apply_command if action == "install" and installable else []
    return result


def schedule_plan_projection(plan: dict[str, object]) -> dict[str, object]:
    return {
        key: plan[key]
        for key in (
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
    }


def schedule_plan_fingerprint(plan: dict[str, object]) -> str:
    canonical = schedule_plan_projection(plan)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def schedule_status(
    root: Path,
    command: str = "ai-dememory",
    target_platform: str | None = None,
) -> dict[str, object]:
    config = load_config(root).get("schedule", {})
    if not isinstance(config, dict):
        config = {}
    mode = str(config.get("mode") or "installed")
    if mode not in {"installed", "docker"}:
        mode = "installed"
    image = str(config.get("image") or "ai-dememory:local")
    daily_time = str(config.get("daily_time") or "03:00")
    weekly_day = str(config.get("weekly_day") or "SUN")
    weekly_time = str(config.get("weekly_time") or "04:00")
    daily_enabled = config.get("daily_enabled", True) is True
    weekly_enabled = config.get("weekly_enabled", True) is True
    platform_value = target_platform or platform_name()
    stored_root = str(config.get("root") or str(root.expanduser().resolve()))
    stored_command = str(config.get("command") or command)
    stored_namespace = str(config.get("task_namespace") or schedule_namespace(root))
    root_moved = stored_root != str(root.expanduser().resolve())
    validation_errors: list[str] = []
    persisted_intensity = str(config.get("intensity") or "")
    if config.get("enabled", False) and persisted_intensity not in profile_names():
        validation_errors.append("enabled schedule is missing a valid intensity receipt")
    try:
        daily_time = normalize_time(daily_time, "daily_time")
        weekly_day = normalize_weekday(weekly_day)
        weekly_time = normalize_time(weekly_time, "weekly_time")
        commands = build_schedule_commands(
            root,
            "status",
            daily_time=daily_time,
            weekly_day=weekly_day,
            weekly_time=weekly_time,
            command=stored_command,
            mode=mode,
            image=image,
            target_platform=platform_value,
            daily_enabled=daily_enabled,
            weekly_enabled=weekly_enabled,
            task_namespace=stored_namespace,
        )
    except ValueError as exc:
        commands = []
        validation_errors.append(str(exc))
    expected_profiles = [
        profile
        for profile, enabled in (("daily", daily_enabled), ("weekly", weekly_enabled))
        if enabled
    ]
    installed_profiles = config.get("installed_profiles")
    plan_sha256 = str(config.get("plan_sha256") or "")
    plan_projection = decode_plan_projection(config.get("plan_projection"))
    try:
        projection_sha256 = (
            schedule_plan_fingerprint(plan_projection)
            if plan_projection
            else ""
        )
    except (KeyError, TypeError, ValueError):
        projection_sha256 = ""
    projected_schedule = (
        plan_projection.get("schedule")
        if isinstance(plan_projection.get("schedule"), dict)
        else {}
    )
    projection_matches_receipt = bool(
        plan_projection
        and hmac.compare_digest(projection_sha256, plan_sha256)
        and plan_projection.get("root") == stored_root
        and plan_projection.get("platform") == config.get("platform")
        and plan_projection.get("mode") == mode
        and plan_projection.get("command") == stored_command
        and plan_projection.get("image") == (image if mode == "docker" else "")
        and plan_projection.get("task_namespace") == stored_namespace
        and plan_projection.get("intensity") == persisted_intensity
        and projected_schedule
        == {
            "daily_enabled": daily_enabled,
            "weekly_enabled": weekly_enabled,
            "daily_time": daily_time,
            "weekly_day": weekly_day,
            "weekly_time": weekly_time,
        }
    )
    definition_digests = decode_definition_digests(config.get("definition_digests"))
    digest_receipt_valid = bool(definition_digests)
    receipt_valid = bool(
        config.get("enabled", False)
        and (mode != "docker" or immutable_docker_image(image))
        and config.get("platform") == platform_value
        and SHA256_PATTERN.fullmatch(plan_sha256)
        and projection_matches_receipt
        and digest_receipt_valid
        and stored_namespace == config.get("task_namespace")
        and isinstance(installed_profiles, list)
        and sorted(str(item) for item in installed_profiles) == sorted(expected_profiles)
        and str(config.get("installed_at") or "").strip()
    )
    if config.get("enabled", False) and not receipt_valid:
        validation_errors.append("enabled schedule is missing an exact install receipt")
    verified_at = str(config.get("verified_at") or "")
    is_verification_fresh = verification_fresh(verified_at)
    return {
        "configured": bool(config.get("enabled", False)),
        "install_receipt_valid": receipt_valid,
        "host_state_verified": bool(receipt_valid and is_verification_fresh),
        "verification_fresh": is_verification_fresh,
        "verification_ttl_seconds": SCHEDULE_VERIFICATION_TTL_SECONDS,
        "last_verified_at": verified_at,
        "valid": not validation_errors,
        "validation_errors": validation_errors,
        "platform": platform_value,
        "mode": mode,
        "image": image if mode == "docker" else "",
        "schedule": {
            "daily_enabled": daily_enabled,
            "weekly_enabled": weekly_enabled,
            "daily_time": daily_time,
            "weekly_day": weekly_day,
            "weekly_time": weekly_time,
            "intensity": persisted_intensity,
            "platform": str(config.get("platform") or ""),
            "plan_sha256": plan_sha256,
            "plan_projection_valid": projection_matches_receipt,
            "definition_digest_count": len(definition_digests),
            "task_namespace": stored_namespace,
            "current_task_namespace": schedule_namespace(root),
            "configured_root": stored_root,
            "current_root": str(root.expanduser().resolve()),
            "root_moved": root_moved,
            "command": stored_command,
            "installed_profiles": installed_profiles if isinstance(installed_profiles, list) else [],
            "installed_at": str(config.get("installed_at") or ""),
            "verified_at": verified_at,
        },
        "review_due": review_due_summary(root),
        "status_commands": [asdict(item) for item in commands],
        "mutates_system": False,
    }


def active_schedule_receipt_source(
    root: Path,
    status: dict[str, object],
) -> Path | None:
    """Return the original vault when a copied enabled receipt still owns the jobs."""

    schedule = status.get("schedule")
    if not isinstance(schedule, dict) or not schedule.get("root_moved", False):
        return None
    configured_root_text = str(schedule.get("configured_root") or "").strip()
    if not configured_root_text:
        return None
    configured_root = Path(configured_root_text).expanduser()
    source_config_path = configured_root / ".ai-dememory.toml"
    try:
        if path_is_link_like(configured_root):
            return configured_root
        if not configured_root.exists():
            return None
        if path_is_link_like(source_config_path):
            return configured_root
        if not source_config_path.exists():
            return None
    except OSError:
        # An unreadable or otherwise ambiguous source must fail closed instead
        # of authorizing deletion of jobs owned by another vault path.
        return configured_root
    try:
        source_config = load_config(configured_root).get("schedule", {})
    except (OSError, UnicodeError, ValueError):
        return configured_root
    if not isinstance(source_config, dict) or not source_config.get("enabled", False):
        return None

    same_namespace = hmac.compare_digest(
        str(source_config.get("task_namespace") or ""),
        str(schedule.get("task_namespace") or ""),
    )
    same_plan = hmac.compare_digest(
        str(source_config.get("plan_sha256") or ""),
        str(schedule.get("plan_sha256") or ""),
    )
    return configured_root if same_namespace and same_plan else None


def run_commands(commands: list[ScheduleCommand]) -> int:
    exit_code = 0
    for command in commands:
        try:
            returncode, _, _ = run_schedule_command(command)
        except OSError:
            returncode = 1
        if returncode != 0:
            exit_code = returncode
    return exit_code


def observe_schedule_definitions(
    commands: list[ScheduleCommand],
    definition_paths: list[Path],
    captured_windows_definitions: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Read back exact scheduler definitions and confirm every job is active."""

    digests: dict[str, str] = {}
    errors: list[str] = []
    for path in definition_paths:
        try:
            if path_is_link_like(path):
                raise ValueError("definition path is a symlink or junction")
            if not path.is_file():
                raise ValueError("definition file is missing or not regular")
            digests[f"file:{path.name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")

    for command in commands:
        try:
            completed = run_owned_capture(
                command.command,
                timeout_seconds=SCHEDULER_COMMAND_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{command.name}: host query failed: {exc}")
            continue
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit {completed.returncode}"
            errors.append(f"{command.name}: host query failed: {detail}")
            continue
        if command.platform == "windows":
            if captured_windows_definitions is not None:
                captured_windows_definitions[command.name] = completed.stdout
            normalized = completed.stdout.replace("\r\n", "\n").strip().encode("utf-8")
            if not normalized:
                errors.append(f"{command.name}: host query returned an empty task definition")
                continue
            digests[f"task:{command.name}"] = hashlib.sha256(normalized).hexdigest()
    return dict(sorted(digests.items())), errors


def windows_restore_commands(
    definitions: dict[str, str],
) -> list[ScheduleCommand]:
    """Build rollback commands carrying exact pre-remove Task Scheduler XML."""

    return [
        ScheduleCommand(
            name=name,
            platform="windows",
            action="restore",
            command=[
                "schtasks",
                "/Create",
                "/TN",
                name,
                "/XML",
                "<captured-task-xml>",
                "/F",
            ],
            definition_text=definition,
        )
        for name, definition in sorted(definitions.items())
    ]


def run_schedule_command(
    command: ScheduleCommand,
) -> tuple[int, bool, int]:
    if command.platform != "windows" or command.definition_text is None:
        return run_owned_process(
            command.command,
            SCHEDULER_COMMAND_TIMEOUT_SECONDS,
        )
    with tempfile.TemporaryDirectory(prefix="ai-dememory-task-restore-") as tmp:
        root = Path(tmp)
        xml_path = root / "task.xml"
        safe_write_text(
            xml_path,
            command.definition_text,
            root=root,
            overwrite=False,
            encoding="utf-16",
        )
        runtime_command = [
            str(xml_path) if item == "<captured-task-xml>" else item
            for item in command.command
        ]
        runtime = ScheduleCommand(
            name=command.name,
            platform=command.platform,
            action=command.action,
            command=runtime_command,
        )
        return run_owned_process(
            runtime.command,
            SCHEDULER_COMMAND_TIMEOUT_SECONDS,
        )


def run_install_commands(
    commands: list[ScheduleCommand],
    rollback_commands: list[ScheduleCommand],
) -> tuple[int, bool]:
    """Run install commands and remove newly completed profile jobs on failure."""
    completed_names: set[str] = set()
    for command in commands:
        try:
            returncode, _, _ = run_schedule_command(command)
        except OSError:
            returncode = 1
        if returncode == 0:
            completed_names.add(command.name)
            continue
        rollback_complete = True
        rollback_by_name = {item.name: item for item in rollback_commands}
        for name in reversed([item.name for item in commands if item.name in completed_names]):
            rollback = rollback_by_name.get(name)
            if rollback is None:
                continue
            try:
                rollback_returncode, _, _ = run_schedule_command(rollback)
            except OSError:
                rollback_returncode = 1
            rollback_complete = rollback_complete and rollback_returncode == 0
        return returncode, rollback_complete
    return 0, True


def run_remove_commands(
    commands: list[ScheduleCommand],
    rollback_commands: list[ScheduleCommand],
) -> tuple[int, bool]:
    """Remove all jobs or restore the complete pre-remove enabled state."""

    completed_names: set[str] = set()
    for command in commands:
        try:
            returncode, _, _ = run_schedule_command(command)
        except OSError:
            returncode = 1
        if returncode == 0:
            completed_names.add(command.name)
            continue
        rollback_complete = True
        rollback_by_name = {item.name: item for item in rollback_commands}
        for name in [item.name for item in commands if item.name in completed_names]:
            rollback = rollback_by_name.get(name)
            if rollback is None:
                rollback_complete = False
                continue
            try:
                rollback_returncode, _, _ = run_schedule_command(rollback)
            except OSError:
                rollback_returncode = 1
            rollback_complete = rollback_complete and rollback_returncode == 0
        return returncode, rollback_complete
    return 0, True


def platform_schedule_paths(
    root: Path,
    target_platform: str,
    daily_enabled: bool,
    weekly_enabled: bool,
    task_namespace: str | None = None,
) -> list[Path]:
    profiles = [
        profile
        for profile, enabled in (("daily", daily_enabled), ("weekly", weekly_enabled))
        if enabled
    ]
    if target_platform == "linux":
        base = Path.home() / ".config" / "systemd" / "user"
        return [
            base / f"{schedule_task_name(root, profile, task_namespace)}.{suffix}"
            for profile in profiles
            for suffix in ("service", "timer")
        ]
    if target_platform == "macos":
        base = Path.home() / "Library" / "LaunchAgents"
        return [
            base / f"{schedule_task_name(root, profile, task_namespace)}.plist"
            for profile in profiles
        ]
    return []


def snapshot_schedule_files(paths: list[Path]) -> dict[Path, bytes | None]:
    snapshot: dict[Path, bytes | None] = {}
    for path in paths:
        if path_is_link_like(path):
            raise ValueError(f"schedule definition path must not be a symlink or junction: {path}")
        snapshot[path] = path.read_bytes() if path.exists() else None
    return snapshot


def restore_schedule_files(snapshot: dict[Path, bytes | None]) -> bool:
    restored = True
    for path, content in snapshot.items():
        try:
            if path_is_link_like(path):
                restored = False
                continue
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        except OSError:
            restored = False
    return restored


def write_platform_schedule_files(
    root: Path,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    command: str,
    mode: str,
    image: str,
    target_platform: str,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    intensity: str | None = None,
) -> list[Path]:
    if target_platform == "linux":
        return write_systemd_user_units(
            root,
            daily_time,
            weekly_day,
            weekly_time,
            command,
            mode,
            image,
            daily_enabled,
            weekly_enabled,
            intensity,
        )
    if target_platform == "macos":
        return write_launchd_plists(
            root,
            daily_time,
            weekly_day,
            weekly_time,
            command,
            mode,
            image,
            daily_enabled,
            weekly_enabled,
            intensity,
        )
    return []


def remove_platform_schedule_files(
    root: Path,
    target_platform: str,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    task_namespace: str | None = None,
) -> list[Path]:
    profiles = [
        profile
        for profile, enabled in (("daily", daily_enabled), ("weekly", weekly_enabled))
        if enabled
    ]
    if target_platform == "linux":
        base = Path.home() / ".config" / "systemd" / "user"
        paths = [
            base / f"{schedule_task_name(root, profile, task_namespace)}.{suffix}"
            for profile in profiles
            for suffix in ("service", "timer")
        ]
    elif target_platform == "macos":
        base = Path.home() / "Library" / "LaunchAgents"
        paths = [
            base / f"{schedule_task_name(root, profile, task_namespace)}.plist"
            for profile in profiles
        ]
    else:
        return []
    removed: list[Path] = []
    for path in paths:
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def write_new_schedule_file(path: Path, text: str) -> None:
    """Create a scheduler definition without replacing pre-existing state."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_systemd_user_units(
    root: Path,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    command: str,
    mode: str,
    image: str,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    intensity: str | None = None,
) -> list[Path]:
    base = Path.home() / ".config" / "systemd" / "user"
    base.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    timeout_seconds = int(
        resolved_resource_policy(root, intensity=intensity)["resources"]["maintenance_timeout_seconds"]
    )
    for profile, enabled in (("daily", daily_enabled), ("weekly", weekly_enabled)):
        if not enabled:
            continue
        name = schedule_task_name(root, profile)
        service = base / f"{name}.service"
        timer = base / f"{name}.timer"
        write_new_schedule_file(
            service,
            systemd_service(
                profile,
                maintenance_run_args(root, profile, command, mode, image, intensity),
                timeout_seconds=timeout_seconds,
            ),
        )
        on_calendar = (
            f"*-*-* {daily_time}:00"
            if profile == "daily"
            else f"{weekly_day} *-*-* {weekly_time}:00"
        )
        write_new_schedule_file(timer, systemd_timer(profile.title(), on_calendar))
        written.extend([service, timer])
    return written


def systemd_service(profile: str, run_args: list[str], timeout_seconds: int = 300) -> str:
    exec_start = command_line(run_args).replace("%", "%%")
    return f"""[Unit]
Description=ai-dememory {profile} maintenance

[Service]
Type=oneshot
ExecStart={exec_start}
RuntimeMaxSec={timeout_seconds}
"""


def systemd_timer(label: str, on_calendar: str) -> str:
    return f"""[Unit]
Description=Run ai-dememory {label.lower()} maintenance

[Timer]
OnCalendar={on_calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""


def write_launchd_plists(
    root: Path,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    command: str,
    mode: str,
    image: str,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
    intensity: str | None = None,
) -> list[Path]:
    base = Path.home() / "Library" / "LaunchAgents"
    base.mkdir(parents=True, exist_ok=True)
    daily_path = base / f"{schedule_task_name(root, 'daily')}.plist"
    weekly_path = base / f"{schedule_task_name(root, 'weekly')}.plist"
    daily_hour, daily_minute = parse_time(daily_time)
    weekly_hour, weekly_minute = parse_time(weekly_time)
    weekday = launchd_weekday(weekly_day)
    written: list[Path] = []
    if daily_enabled:
        write_new_schedule_file(
            daily_path,
            launchd_plist(
                schedule_task_name(root, "daily"),
                maintenance_run_args(root, "daily", command, mode, image, intensity),
                daily_hour,
                daily_minute,
            ),
        )
        written.append(daily_path)
    if weekly_enabled:
        write_new_schedule_file(
            weekly_path,
            launchd_plist(
                schedule_task_name(root, "weekly"),
                maintenance_run_args(root, "weekly", command, mode, image, intensity),
                weekly_hour,
                weekly_minute,
                weekday,
            ),
        )
        written.append(weekly_path)
    return written


def launchd_weekday(value: str) -> int:
    mapping = {"SUN": 1, "MON": 2, "TUE": 3, "WED": 4, "THU": 5, "FRI": 6, "SAT": 7}
    return mapping[normalize_weekday(value)]


def launchd_plist(
    label: str,
    run_args: list[str],
    hour: int,
    minute: int,
    weekday: int | None = None,
) -> str:
    weekday_line = f"<key>Weekday</key><integer>{weekday}</integer>" if weekday else ""
    args = "\n".join(f"    <string>{escape(arg)}</string>" for arg in run_args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
{args}
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    {weekday_line}
    <key>Hour</key><integer>{hour}</integer>
    <key>Minute</key><integer>{minute}</integer>
  </dict>
</dict>
</plist>
"""


def schedule_cli_values(root: Path, args: argparse.Namespace) -> dict[str, object]:
    config = load_config(root).get("schedule", {})
    config = config if isinstance(config, dict) else {}
    explicit_intensity = getattr(args, "intensity", None)
    command_name = str(getattr(args, "command_name", "") or "")
    plan_action = str(getattr(args, "action", "") or "")
    receipt_authoritative = bool(
        config.get("enabled", False)
        and (
            command_name in {"status", "remove"}
            or (command_name == "plan" and plan_action in {"status", "remove"})
        )
    )
    receipt_intensity = (
        str(config.get("intensity") or "")
        if receipt_authoritative and str(config.get("intensity") or "") in profile_names()
        else None
    )
    policy = resolved_resource_policy(
        root,
        intensity=explicit_intensity or receipt_intensity,
    )
    intensity_profile = get_resource_profile(explicit_intensity) if explicit_intensity else None
    return {
        "daily_time": getattr(args, "daily_time", None) or str(config.get("daily_time") or "03:00"),
        "weekly_day": getattr(args, "weekly_day", None) or str(config.get("weekly_day") or "SUN"),
        "weekly_time": getattr(args, "weekly_time", None) or str(config.get("weekly_time") or "04:00"),
        "daily_enabled": (
            bool(args.daily_enabled)
            if getattr(args, "daily_enabled", None) is not None
            else (
                config.get("daily_enabled", True) is True
                if receipt_authoritative
                else (
                    intensity_profile.daily_enabled
                    if intensity_profile is not None
                    else bool(policy["daily_enabled"])
                )
            )
        ),
        "weekly_enabled": (
            bool(args.weekly_enabled)
            if getattr(args, "weekly_enabled", None) is not None
            else (
                config.get("weekly_enabled", True) is True
                if receipt_authoritative
                else (
                    intensity_profile.weekly_enabled
                    if intensity_profile is not None
                    else bool(policy["weekly_enabled"])
                )
            )
        ),
        "mode": getattr(args, "mode", None) or str(config.get("mode") or "installed"),
        "image": getattr(args, "image", None) or str(config.get("image") or "ai-dememory:local"),
        "intensity": str(policy["intensity"]),
    }


def add_schedule_options(
    parser: argparse.ArgumentParser,
    *,
    include_platform: bool = True,
    include_fingerprint: bool = False,
) -> None:
    parser.add_argument("--daily-time", default=None)
    parser.add_argument("--weekly-day", default=None)
    parser.add_argument("--weekly-time", default=None)
    parser.add_argument("--daily", dest="daily_enabled", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--weekly", dest="weekly_enabled", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--intensity", choices=profile_names(), default=None)
    if include_platform:
        parser.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
    parser.add_argument(
        "--mode",
        choices=("installed", "docker"),
        default=None,
        help="Run maintenance with the installed CLI or a local Docker image.",
    )
    parser.add_argument("--image", default=None, help="Docker image for --mode docker.")
    if include_fingerprint:
        parser.add_argument(
            "--expect-plan-sha256",
            default=None,
            help="Fingerprint from the exact reviewed `schedule plan` output.",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--command", default="ai-dememory", help="Installed CLI command used by the scheduler.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    plan = subparsers.add_parser("plan", help="Print a read-only scheduler setup plan.")
    plan.add_argument("--action", choices=("install", "status", "remove"), default="install")
    add_schedule_options(plan)
    plan.add_argument("--json", action="store_true")
    for name in ("setup", "install", "status", "remove"):
        sub = subparsers.add_parser(name)
        add_schedule_options(sub, include_fingerprint=name in {"setup", "install"})
        sub.add_argument("--dry-run", action="store_true")
        sub.add_argument("--json", action="store_true")
    doctor = subparsers.add_parser("doctor", help="Check scheduler command availability without running commands.")
    doctor.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
    doctor.add_argument("--mode", choices=("installed", "docker"), default="installed")
    doctor.add_argument("--json", action="store_true")
    cron = subparsers.add_parser("cron", help="Print crontab lines without installing them.")
    add_schedule_options(cron, include_platform=False)
    cron.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    root = repo_root(args.root)
    if args.command_name == "plan":
        values = schedule_cli_values(root, args)
        try:
            result = schedule_plan(
                root,
                action=args.action,
                daily_time=str(values["daily_time"]),
                weekly_day=str(values["weekly_day"]),
                weekly_time=str(values["weekly_time"]),
                command=args.command,
                mode=str(values["mode"]),
                image=str(values["image"]),
                target_platform=args.platform,
                daily_enabled=bool(values["daily_enabled"]),
                weekly_enabled=bool(values["weekly_enabled"]),
                intensity=str(values["intensity"]),
            )
        except ValueError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"ai-dememory schedule plan ({result['platform']}, {result['mode']}, {result['action']})")
            print("mutates_system: false")
            for command_item in result["commands"]:
                print(f"- {command_item['name']}: {command_line(command_item['command'])}")
            if result["cron_entries"]:
                print("cron_entries:")
                for entry in result["cron_entries"]:
                    print(f"- {entry['name']}: {entry['line']}")
        return 0
    if args.command_name == "doctor":
        result = schedule_environment(target_platform=args.platform, mode=args.mode)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"ai-dememory schedule doctor ({result['platform']}, {result['mode']})")
            print(f"ready: {str(result['ready']).lower()}")
            for check in result["checks"]:
                status = "ok" if check["available"] else ("missing" if check["required"] else "optional-missing")
                print(f"- {status}: {check['name']} command `{check['command']}`")
        return 0
    if args.command_name == "cron":
        values = schedule_cli_values(root, args)
        try:
            entries = build_cron_entries(
                root,
                daily_time=str(values["daily_time"]),
                weekly_day=str(values["weekly_day"]),
                weekly_time=str(values["weekly_time"]),
                command=args.command,
                mode=str(values["mode"]),
                image=str(values["image"]),
                daily_enabled=bool(values["daily_enabled"]),
                weekly_enabled=bool(values["weekly_enabled"]),
                intensity=str(values["intensity"]),
            )
        except ValueError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps([asdict(entry) for entry in entries], indent=2))
        else:
            print(render_cron_entries(entries), end="")
        return 0

    action = "install" if args.command_name == "setup" else args.command_name
    values = schedule_cli_values(root, args)
    stored_schedule = load_config(root).get("schedule", {})
    receipt_namespace = (
        str(stored_schedule.get("task_namespace") or "")
        if action in {"status", "remove"}
        and isinstance(stored_schedule, dict)
        and stored_schedule.get("enabled", False)
        else ""
    )
    try:
        commands = build_schedule_commands(
            root,
            action,
            daily_time=str(values["daily_time"]),
            weekly_day=str(values["weekly_day"]),
            weekly_time=str(values["weekly_time"]),
            command=args.command,
            mode=str(values["mode"]),
            image=str(values["image"]),
            target_platform=args.platform,
            daily_enabled=bool(values["daily_enabled"]),
            weekly_enabled=bool(values["weekly_enabled"]),
            intensity=str(values["intensity"]),
            task_namespace=receipt_namespace or None,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if (
        args.dry_run
        and action == "install"
        and str(values["mode"]) == "docker"
        and not immutable_docker_image(str(values["image"]))
    ):
        print("scheduled Docker images must use an immutable sha256 digest", file=sys.stderr)
        return 2
    if args.json or args.dry_run:
        print(json.dumps([asdict(command) for command in commands], indent=2))
    if args.dry_run:
        return 0
    target_platform = args.platform or platform_name()
    if action == "remove":
        persisted_schedule = load_config(root).get("schedule", {})
        if isinstance(persisted_schedule, dict) and persisted_schedule.get("enabled", False):
            installed_profiles = {
                str(item)
                for item in persisted_schedule.get("installed_profiles", [])
                if str(item) in {"daily", "weekly"}
            }
            selected_profiles = {
                profile
                for profile, enabled in (
                    ("daily", bool(values["daily_enabled"])),
                    ("weekly", bool(values["weekly_enabled"])),
                )
                if enabled
            }
            if installed_profiles and selected_profiles != installed_profiles:
                print(
                    "partial schedule removal is refused; remove the complete installed receipt",
                    file=sys.stderr,
                )
                return 2
    if action == "install":
        reviewed_plan = schedule_plan(
            root,
            action="install",
            daily_time=str(values["daily_time"]),
            weekly_day=str(values["weekly_day"]),
            weekly_time=str(values["weekly_time"]),
            command=args.command,
            mode=str(values["mode"]),
            image=str(values["image"]),
            target_platform=target_platform,
            daily_enabled=bool(values["daily_enabled"]),
            weekly_enabled=bool(values["weekly_enabled"]),
            intensity=str(values["intensity"]),
        )
        if not reviewed_plan["installable"]:
            print(
                "scheduled Docker images must use an immutable repo@sha256:<digest> reference",
                file=sys.stderr,
            )
            return 2
        expected = getattr(args, "expect_plan_sha256", None)
        if not expected:
            print(
                "schedule install requires --expect-plan-sha256 from the exact reviewed `schedule plan` output",
                file=sys.stderr,
            )
            return 2
        if not hmac.compare_digest(str(expected), str(reviewed_plan["plan_sha256"])):
            print("schedule plan changed after review; inspect a fresh plan before install", file=sys.stderr)
            return 2
        persisted = load_config(root).get("schedule", {})
        if isinstance(persisted, dict) and persisted.get("enabled", False):
            print("an enabled schedule already exists; remove its exact receipt before reinstalling", file=sys.stderr)
            return 2
        paths = platform_schedule_paths(
            root,
            target_platform,
            bool(values["daily_enabled"]),
            bool(values["weekly_enabled"]),
            receipt_namespace or None,
        )
        try:
            snapshot = snapshot_schedule_files(paths)
        except (OSError, ValueError) as exc:
            print(f"schedule definition preflight failed: {exc}", file=sys.stderr)
            return 1
        try:
            written = write_platform_schedule_files(
                root,
                str(values["daily_time"]),
                str(values["weekly_day"]),
                str(values["weekly_time"]),
                args.command,
                str(values["mode"]),
                str(values["image"]),
                target_platform,
                bool(values["daily_enabled"]),
                bool(values["weekly_enabled"]),
                str(values["intensity"]),
            )
        except OSError as exc:
            rollback_complete = restore_schedule_files(snapshot)
            print(
                json.dumps(
                    {
                        "installed": False,
                        "rollback_complete": rollback_complete,
                        "error": f"schedule definition write failed: {exc}",
                    }
                ),
                file=sys.stderr,
            )
            return 1
        for path in written:
            print(f"Wrote {path}")
        rollback_commands = build_schedule_commands(
            root,
            "remove",
            daily_time=str(values["daily_time"]),
            weekly_day=str(values["weekly_day"]),
            weekly_time=str(values["weekly_time"]),
            command=args.command,
            mode=str(values["mode"]),
            image=str(values["image"]),
            target_platform=target_platform,
            daily_enabled=bool(values["daily_enabled"]),
            weekly_enabled=bool(values["weekly_enabled"]),
            intensity=str(values["intensity"]),
        )
        exit_code, host_rollback_complete = run_install_commands(commands, rollback_commands)
        if exit_code != 0:
            files_rollback_complete = restore_schedule_files(snapshot)
            print(
                json.dumps(
                    {
                        "installed": False,
                        "rollback_complete": host_rollback_complete and files_rollback_complete,
                    }
                ),
                file=sys.stderr,
            )
            return exit_code
        status_commands = build_schedule_commands(
            root,
            "status",
            daily_time=str(values["daily_time"]),
            weekly_day=str(values["weekly_day"]),
            weekly_time=str(values["weekly_time"]),
            command=args.command,
            mode=str(values["mode"]),
            image=str(values["image"]),
            target_platform=target_platform,
            daily_enabled=bool(values["daily_enabled"]),
            weekly_enabled=bool(values["weekly_enabled"]),
            intensity=str(values["intensity"]),
        )
        observed_digests, verification_errors = observe_schedule_definitions(
            status_commands,
            paths,
        )
        if verification_errors:
            host_cleanup_complete = run_commands(rollback_commands) == 0
            files_rollback_complete = restore_schedule_files(snapshot)
            print(
                json.dumps(
                    {
                        "installed": False,
                        "rollback_complete": host_cleanup_complete and files_rollback_complete,
                        "verification_errors": verification_errors,
                    }
                ),
                file=sys.stderr,
            )
            return 1
        try:
            configure_schedule(
                root,
                str(values["daily_time"]),
                str(values["weekly_day"]),
                str(values["weekly_time"]),
                str(values["mode"]),
                str(values["image"]),
                bool(values["daily_enabled"]),
                bool(values["weekly_enabled"]),
                str(values["intensity"]),
                target_platform=target_platform,
                plan_sha256=str(reviewed_plan["plan_sha256"]),
                definition_digests=observed_digests,
                command=args.command,
            )
        except (OSError, ValueError) as exc:
            host_cleanup_complete = run_commands(rollback_commands) == 0
            files_rollback_complete = restore_schedule_files(snapshot)
            print(
                json.dumps(
                    {
                        "installed": False,
                        "rollback_complete": host_cleanup_complete and files_rollback_complete,
                        "error": f"schedule receipt write failed: {exc}",
                    }
                ),
                file=sys.stderr,
            )
            return 1
        return 0
    if action == "status":
        persisted = load_config(root).get("schedule", {})
        if not isinstance(persisted, dict) or not persisted.get("enabled", False):
            print("no enabled schedule receipt is available to verify", file=sys.stderr)
            return 2
        paths = platform_schedule_paths(
            root,
            target_platform,
            bool(values["daily_enabled"]),
            bool(values["weekly_enabled"]),
            receipt_namespace or None,
        )
        observed_digests, verification_errors = observe_schedule_definitions(commands, paths)
        if verification_errors:
            clear_schedule_verification(root)
            print(json.dumps({"verified": False, "errors": verification_errors}), file=sys.stderr)
            return 1
        try:
            mark_schedule_verified(root, observed_digests)
        except (OSError, ValueError) as exc:
            clear_schedule_verification(root)
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    if action == "remove":
        current_status = schedule_status(root, command=args.command, target_platform=target_platform)
        if not current_status["install_receipt_valid"]:
            print("schedule removal requires an exact valid install receipt", file=sys.stderr)
            return 2
        receipt_source = active_schedule_receipt_source(root, current_status)
        if receipt_source is not None:
            print(
                (
                    "schedule removal refused: this vault is a copy of an enabled "
                    f"schedule receipt still owned by {receipt_source}; remove the "
                    "schedule from the original vault or perform an explicit transfer"
                ),
                file=sys.stderr,
            )
            return 2
        paths = platform_schedule_paths(
            root,
            target_platform,
            bool(values["daily_enabled"]),
            bool(values["weekly_enabled"]),
            receipt_namespace or None,
        )
        status_commands = build_schedule_commands(
            root,
            "status",
            daily_time=str(values["daily_time"]),
            weekly_day=str(values["weekly_day"]),
            weekly_time=str(values["weekly_time"]),
            command=args.command,
            mode=str(values["mode"]),
            image=str(values["image"]),
            target_platform=target_platform,
            daily_enabled=bool(values["daily_enabled"]),
            weekly_enabled=bool(values["weekly_enabled"]),
            intensity=str(values["intensity"]),
            task_namespace=receipt_namespace or None,
        )
        captured_windows_definitions: dict[str, str] = {}
        observed_digests, verification_errors = observe_schedule_definitions(
            status_commands,
            paths,
            captured_windows_definitions=(
                captured_windows_definitions
                if target_platform == "windows"
                else None
            ),
        )
        if verification_errors:
            clear_schedule_verification(root)
            print(
                json.dumps(
                    {
                        "removed": False,
                        "error": "host schedule could not be matched to the install receipt",
                        "verification_errors": verification_errors,
                    }
                ),
                file=sys.stderr,
            )
            return 2
        try:
            mark_schedule_verified(root, observed_digests)
        except (OSError, ValueError) as exc:
            clear_schedule_verification(root)
            print(f"schedule removal refused: {exc}", file=sys.stderr)
            return 2
        try:
            snapshot = snapshot_schedule_files(paths)
        except (OSError, ValueError) as exc:
            print(f"schedule definition preflight failed: {exc}", file=sys.stderr)
            return 1
        rollback_commands = (
            windows_restore_commands(captured_windows_definitions)
            if target_platform == "windows"
            else build_schedule_commands(
                root,
                "install",
                daily_time=str(values["daily_time"]),
                weekly_day=str(values["weekly_day"]),
                weekly_time=str(values["weekly_time"]),
                command=args.command,
                mode=str(values["mode"]),
                image=str(values["image"]),
                target_platform=target_platform,
                daily_enabled=bool(values["daily_enabled"]),
                weekly_enabled=bool(values["weekly_enabled"]),
                intensity=str(values["intensity"]),
                task_namespace=receipt_namespace or None,
            )
        )
        exit_code, rollback_complete = run_remove_commands(commands, rollback_commands)
        if exit_code != 0:
            print(
                json.dumps({"removed": False, "rollback_complete": rollback_complete}),
                file=sys.stderr,
            )
            return exit_code
        try:
            removed = remove_platform_schedule_files(
                root,
                target_platform,
                bool(values["daily_enabled"]),
                bool(values["weekly_enabled"]),
                receipt_namespace or None,
            )
            for path in removed:
                print(f"Removed {path}")
            if target_platform == "linux":
                reload_returncode, _, _ = run_owned_process(
                    ["systemctl", "--user", "daemon-reload"],
                    SCHEDULER_COMMAND_TIMEOUT_SECONDS,
                )
                if reload_returncode != 0:
                    raise RuntimeError(f"systemd daemon-reload failed with exit {reload_returncode}")
            disable_schedule(root)
        except (OSError, RuntimeError, ValueError) as exc:
            files_rollback_complete = restore_schedule_files(snapshot)
            host_rollback_complete = run_commands(rollback_commands) == 0
            print(
                json.dumps(
                    {
                        "removed": False,
                        "rollback_complete": files_rollback_complete and host_rollback_complete,
                        "error": str(exc),
                    }
                ),
                file=sys.stderr,
            )
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
