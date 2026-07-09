#!/usr/bin/env python3
"""Install, inspect, and remove opt-in ai-dememory maintenance schedules."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

from config_file import load_config
from config_file import set_section
from maintenance import review_due_summary
from memorylib import repo_root


WEEKDAYS = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}


@dataclass(frozen=True)
class ScheduleCommand:
    name: str
    platform: str
    action: str
    command: list[str]
    run_command: list[str] | None = None


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


def configure_schedule(root: Path, daily_time: str, weekly_day: str, weekly_time: str, mode: str, image: str) -> Path:
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    return set_section(
        root,
        "schedule",
        {
            "enabled": True,
            "daily_time": daily_time,
            "weekly_day": weekly_day,
            "weekly_time": weekly_time,
            "mode": mode,
            "image": image if mode == "docker" else "",
        },
    )


def maintenance_run_args(root: Path, profile: str, command: str, mode: str, image: str) -> list[str]:
    if mode == "docker":
        return [
            "docker",
            "run",
            "--rm",
            "-e",
            "AI_DEMEMORY_ROOT=/memory",
            "-v",
            f"{root}:/memory",
            image,
            "maintenance",
            "run",
            "--profile",
            profile,
            "--root",
            "/memory",
        ]
    return [command, "maintenance", "run", "--profile", profile, "--root", str(root)]


def command_line(args: list[str]) -> str:
    return shlex.join(args)


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
) -> list[CronEntry]:
    if mode not in {"installed", "docker"}:
        raise ValueError("mode must be installed or docker")
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    daily_hour, daily_minute = parse_time(daily_time)
    weekly_hour, weekly_minute = parse_time(weekly_time)
    weekly_day_number = cron_weekday(weekly_day)
    entries = [
        (
            "ai-dememory-daily",
            "daily",
            f"{daily_minute} {daily_hour} * * *",
            maintenance_run_args(root, "daily", command, mode, image),
        ),
        (
            "ai-dememory-weekly",
            "weekly",
            f"{weekly_minute} {weekly_hour} * * {weekly_day_number}",
            maintenance_run_args(root, "weekly", command, mode, image),
        ),
    ]
    return [
        CronEntry(name=name, profile=profile, schedule=schedule, command=args, line=f"{schedule} {command_line(args)}")
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
) -> list[ScheduleCommand]:
    if mode not in {"installed", "docker"}:
        raise ValueError("mode must be installed or docker")
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    system = target_platform or platform_name()
    daily_args = maintenance_run_args(root, "daily", command, mode, image)
    weekly_args = maintenance_run_args(root, "weekly", command, mode, image)
    if system == "windows":
        daily_run = windows_command_line(daily_args)
        weekly_run = windows_command_line(weekly_args)
        if action in {"install", "setup"}:
            return [
                ScheduleCommand(
                    "ai-dememory-daily",
                    system,
                    action,
                    ["schtasks", "/Create", "/TN", "ai-dememory-daily", "/SC", "DAILY", "/ST", daily_time, "/TR", daily_run, "/F"],
                    daily_args,
                ),
                ScheduleCommand(
                    "ai-dememory-weekly",
                    system,
                    action,
                    ["schtasks", "/Create", "/TN", "ai-dememory-weekly", "/SC", "WEEKLY", "/D", weekly_day, "/ST", weekly_time, "/TR", weekly_run, "/F"],
                    weekly_args,
                ),
            ]
        if action == "remove":
            return [
                ScheduleCommand("ai-dememory-daily", system, action, ["schtasks", "/Delete", "/TN", "ai-dememory-daily", "/F"]),
                ScheduleCommand("ai-dememory-weekly", system, action, ["schtasks", "/Delete", "/TN", "ai-dememory-weekly", "/F"]),
            ]
        return [
            ScheduleCommand("ai-dememory-daily", system, action, ["schtasks", "/Query", "/TN", "ai-dememory-daily"]),
            ScheduleCommand("ai-dememory-weekly", system, action, ["schtasks", "/Query", "/TN", "ai-dememory-weekly"]),
        ]

    if system == "macos":
        daily_plist = str(Path.home() / "Library" / "LaunchAgents" / "ai-dememory-daily.plist")
        weekly_plist = str(Path.home() / "Library" / "LaunchAgents" / "ai-dememory-weekly.plist")
        if action in {"install", "setup"}:
            return [
                ScheduleCommand("ai-dememory-daily", system, action, ["launchctl", "load", "-w", daily_plist], daily_args),
                ScheduleCommand("ai-dememory-weekly", system, action, ["launchctl", "load", "-w", weekly_plist], weekly_args),
            ]
        if action == "remove":
            return [
                ScheduleCommand("ai-dememory-daily", system, action, ["launchctl", "unload", "-w", daily_plist]),
                ScheduleCommand("ai-dememory-weekly", system, action, ["launchctl", "unload", "-w", weekly_plist]),
            ]
        return [
            ScheduleCommand("ai-dememory-daily", system, action, ["launchctl", "list", "ai-dememory-daily"]),
            ScheduleCommand("ai-dememory-weekly", system, action, ["launchctl", "list", "ai-dememory-weekly"]),
        ]

    if action in {"install", "setup"}:
        return [
            ScheduleCommand("ai-dememory-daemon-reload", system, action, ["systemctl", "--user", "daemon-reload"]),
            ScheduleCommand("ai-dememory-daily", system, action, ["systemctl", "--user", "enable", "--now", "ai-dememory-daily.timer"], daily_args),
            ScheduleCommand("ai-dememory-weekly", system, action, ["systemctl", "--user", "enable", "--now", "ai-dememory-weekly.timer"], weekly_args),
        ]
    if action == "remove":
        return [
            ScheduleCommand("ai-dememory-daily", system, action, ["systemctl", "--user", "disable", "--now", "ai-dememory-daily.timer"]),
            ScheduleCommand("ai-dememory-weekly", system, action, ["systemctl", "--user", "disable", "--now", "ai-dememory-weekly.timer"]),
        ]
    return [
        ScheduleCommand("ai-dememory-daily", system, action, ["systemctl", "--user", "status", "ai-dememory-daily.timer"]),
        ScheduleCommand("ai-dememory-weekly", system, action, ["systemctl", "--user", "status", "ai-dememory-weekly.timer"]),
    ]


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
) -> dict[str, object]:
    if action == "setup":
        action = "install"
    if action not in {"install", "status", "remove"}:
        raise ValueError("action must be install, status, or remove")
    daily_time = normalize_time(daily_time, "daily_time")
    weekly_day = normalize_weekday(weekly_day)
    weekly_time = normalize_time(weekly_time, "weekly_time")
    platform_value = target_platform or platform_name()
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
        )
        if action == "install"
        else []
    )
    return {
        "root": str(root),
        "action": action,
        "platform": platform_value,
        "mode": mode,
        "image": image if mode == "docker" else "",
        "schedule": {
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
            "Review the platform scheduler commands before running `ai-dememory schedule setup`.",
            "Use the cron entries only on hosts where reviewed crontab installation is appropriate.",
            "Run `ai-dememory schedule doctor --json` to check local scheduler command availability.",
        ],
    }


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
    platform_value = target_platform or platform_name()
    validation_errors: list[str] = []
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
            command=command,
            mode=mode,
            image=image,
            target_platform=platform_value,
        )
    except ValueError as exc:
        commands = []
        validation_errors.append(str(exc))
    return {
        "configured": bool(config.get("enabled", False)),
        "valid": not validation_errors,
        "validation_errors": validation_errors,
        "platform": platform_value,
        "mode": mode,
        "image": image if mode == "docker" else "",
        "schedule": {
            "daily_time": daily_time,
            "weekly_day": weekly_day,
            "weekly_time": weekly_time,
        },
        "review_due": review_due_summary(root),
        "status_commands": [asdict(item) for item in commands],
        "mutates_system": False,
    }


def run_commands(commands: list[ScheduleCommand]) -> int:
    exit_code = 0
    for command in commands:
        result = subprocess.run(command.command, check=False)
        if result.returncode != 0:
            exit_code = result.returncode
    return exit_code


def write_platform_schedule_files(
    root: Path,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    command: str,
    mode: str,
    image: str,
    target_platform: str,
) -> list[Path]:
    if target_platform == "linux":
        return write_systemd_user_units(root, daily_time, weekly_day, weekly_time, command, mode, image)
    if target_platform == "macos":
        return write_launchd_plists(root, daily_time, weekly_day, weekly_time, command, mode, image)
    return []


def remove_platform_schedule_files(target_platform: str) -> list[Path]:
    if target_platform == "linux":
        base = Path.home() / ".config" / "systemd" / "user"
        paths = [
            base / "ai-dememory-daily.service",
            base / "ai-dememory-daily.timer",
            base / "ai-dememory-weekly.service",
            base / "ai-dememory-weekly.timer",
        ]
    elif target_platform == "macos":
        base = Path.home() / "Library" / "LaunchAgents"
        paths = [
            base / "ai-dememory-daily.plist",
            base / "ai-dememory-weekly.plist",
        ]
    else:
        return []
    removed: list[Path] = []
    for path in paths:
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def write_systemd_user_units(
    root: Path,
    daily_time: str,
    weekly_day: str,
    weekly_time: str,
    command: str,
    mode: str,
    image: str,
) -> list[Path]:
    base = Path.home() / ".config" / "systemd" / "user"
    base.mkdir(parents=True, exist_ok=True)
    daily_service = base / "ai-dememory-daily.service"
    weekly_service = base / "ai-dememory-weekly.service"
    daily_timer = base / "ai-dememory-daily.timer"
    weekly_timer = base / "ai-dememory-weekly.timer"
    daily_service.write_text(systemd_service("daily", maintenance_run_args(root, "daily", command, mode, image)), encoding="utf-8")
    weekly_service.write_text(systemd_service("weekly", maintenance_run_args(root, "weekly", command, mode, image)), encoding="utf-8")
    daily_timer.write_text(systemd_timer("Daily", f"*-*-* {daily_time}:00"), encoding="utf-8")
    weekly_timer.write_text(systemd_timer("Weekly", f"{weekly_day} *-*-* {weekly_time}:00"), encoding="utf-8")
    return [daily_service, daily_timer, weekly_service, weekly_timer]


def systemd_service(profile: str, run_args: list[str]) -> str:
    return f"""[Unit]
Description=ai-dememory {profile} maintenance

[Service]
Type=oneshot
ExecStart={command_line(run_args)}
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
) -> list[Path]:
    base = Path.home() / "Library" / "LaunchAgents"
    base.mkdir(parents=True, exist_ok=True)
    daily_path = base / "ai-dememory-daily.plist"
    weekly_path = base / "ai-dememory-weekly.plist"
    daily_hour, daily_minute = parse_time(daily_time)
    weekly_hour, weekly_minute = parse_time(weekly_time)
    weekday = launchd_weekday(weekly_day)
    daily_path.write_text(
        launchd_plist(
            "ai-dememory-daily",
            maintenance_run_args(root, "daily", command, mode, image),
            daily_hour,
            daily_minute,
        ),
        encoding="utf-8",
    )
    weekly_path.write_text(
        launchd_plist(
            "ai-dememory-weekly",
            maintenance_run_args(root, "weekly", command, mode, image),
            weekly_hour,
            weekly_minute,
            weekday,
        ),
        encoding="utf-8",
    )
    return [daily_path, weekly_path]


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--command", default="ai-dememory", help="Installed CLI command used by the scheduler.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    plan = subparsers.add_parser("plan", help="Print a read-only scheduler setup plan.")
    plan.add_argument("--action", choices=("install", "status", "remove"), default="install")
    plan.add_argument("--daily-time", default="03:00")
    plan.add_argument("--weekly-day", default="SUN")
    plan.add_argument("--weekly-time", default="04:00")
    plan.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
    plan.add_argument("--mode", choices=("installed", "docker"), default="installed", help="Run maintenance with the installed CLI or a local Docker image.")
    plan.add_argument("--image", default="ai-dememory:local", help="Docker image for --mode docker.")
    plan.add_argument("--json", action="store_true")
    for name in ("setup", "install", "status", "remove"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--daily-time", default="03:00")
        sub.add_argument("--weekly-day", default="SUN")
        sub.add_argument("--weekly-time", default="04:00")
        sub.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
        sub.add_argument("--mode", choices=("installed", "docker"), default="installed", help="Run maintenance with the installed CLI or a local Docker image.")
        sub.add_argument("--image", default="ai-dememory:local", help="Docker image for --mode docker.")
        sub.add_argument("--dry-run", action="store_true")
        sub.add_argument("--json", action="store_true")
    doctor = subparsers.add_parser("doctor", help="Check scheduler command availability without running commands.")
    doctor.add_argument("--platform", choices=("windows", "linux", "macos"), default=None)
    doctor.add_argument("--mode", choices=("installed", "docker"), default="installed")
    doctor.add_argument("--json", action="store_true")
    cron = subparsers.add_parser("cron", help="Print crontab lines without installing them.")
    cron.add_argument("--daily-time", default="03:00")
    cron.add_argument("--weekly-day", default="SUN")
    cron.add_argument("--weekly-time", default="04:00")
    cron.add_argument("--mode", choices=("installed", "docker"), default="installed", help="Run maintenance with the installed CLI or a local Docker image.")
    cron.add_argument("--image", default="ai-dememory:local", help="Docker image for --mode docker.")
    cron.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    root = repo_root(args.root)
    if args.command_name == "plan":
        try:
            result = schedule_plan(
                root,
                action=args.action,
                daily_time=args.daily_time,
                weekly_day=args.weekly_day,
                weekly_time=args.weekly_time,
                command=args.command,
                mode=args.mode,
                image=args.image,
                target_platform=args.platform,
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
        try:
            entries = build_cron_entries(
                root,
                daily_time=args.daily_time,
                weekly_day=args.weekly_day,
                weekly_time=args.weekly_time,
                command=args.command,
                mode=args.mode,
                image=args.image,
            )
        except ValueError as exc:
            parser.error(str(exc))
        if args.json:
            print(json.dumps([asdict(entry) for entry in entries], indent=2))
        else:
            print(render_cron_entries(entries), end="")
        return 0

    action = "install" if args.command_name == "setup" else args.command_name
    try:
        commands = build_schedule_commands(
            root,
            action,
            daily_time=args.daily_time,
            weekly_day=args.weekly_day,
            weekly_time=args.weekly_time,
            command=args.command,
            mode=args.mode,
            image=args.image,
            target_platform=args.platform,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.json or args.dry_run:
        print(json.dumps([asdict(command) for command in commands], indent=2))
    if args.dry_run:
        return 0
    target_platform = args.platform or platform_name()
    if action == "install":
        configure_schedule(root, args.daily_time, args.weekly_day, args.weekly_time, args.mode, args.image)
        written = write_platform_schedule_files(
            root,
            args.daily_time,
            args.weekly_day,
            args.weekly_time,
            args.command,
            args.mode,
            args.image,
            target_platform,
        )
        for path in written:
            print(f"Wrote {path}")
    if action in {"install", "remove", "status"}:
        exit_code = run_commands(commands)
        if action == "remove":
            removed = remove_platform_schedule_files(target_platform)
            for path in removed:
                print(f"Removed {path}")
            if target_platform == "linux":
                reload_result = subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
                if reload_result.returncode != 0 and exit_code == 0:
                    exit_code = reload_result.returncode
        return exit_code
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
