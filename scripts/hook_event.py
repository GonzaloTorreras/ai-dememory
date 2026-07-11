#!/usr/bin/env python3
"""Capture small provider hook event metadata into the memory inbox."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

from memorylib import (
    FrontmatterError,
    SOURCE_KINDS,
    contained_relative_path,
    parse_frontmatter_text,
    repo_relative_path,
    repo_root,
    slugify,
)
from secret_scan import scan_text
from harness_hooks import dispatch_hook_event, hook_metadata_enabled


MAX_STDIN_BYTES = 64 * 1024
MAX_HOOK_FRONTMATTER_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 15
HOOK_EVENTS: dict[str, tuple[str, ...]] = {
    "codex": ("UserPromptSubmit", "PreCompact", "PostCompact", "Stop"),
    "claude": ("UserPromptSubmit", "SessionStart", "PreCompact", "Stop", "SubagentStop", "Notification"),
}
DEFAULT_CAPTURE_REPORT = Path("reports/hook-captures.md")
DEFAULT_CAPTURE_ARCHIVE = Path("archive/session-events")
HOOK_CAPTURE_REVIEW_STATUSES = {"reviewed", "rejected", "dismissed"}
HOOK_CAPTURE_REVIEW_FILTERS = {*HOOK_CAPTURE_REVIEW_STATUSES, "pending", "resolved"}
MATCHED_EVENTS = {"PreCompact", "PostCompact"}
CLIENT_INSTRUCTION_FILES = {
    "codex": "AGENTS.md",
    "claude": "CLAUDE.md",
}
CLIENT_TITLES = {
    "codex": "Codex",
    "claude": "Claude Code",
}


@dataclass(frozen=True)
class HookInstallResult:
    client: str
    path: str
    installed: bool
    changed: bool
    dry_run: bool
    events: list[str]


@dataclass(frozen=True)
class HookCaptureReviewResult:
    path: str
    review_status: str
    reviewed_by: str
    reviewed_at: str
    reason: str
    canonical_memory_updated: bool


@dataclass(frozen=True)
class HookCaptureArchiveResult:
    dry_run: bool
    archive_root: str
    filters: dict[str, str]
    min_reviewed_days: int
    unfiltered_total_count: int
    eligible_count: int
    archived_count: int
    skipped_count: int
    candidates: list[dict[str, str]]
    archived: list[dict[str, str]]
    skipped: list[dict[str, str]]
    malformed_count: int
    malformed: list[dict[str, str]]
    reads_raw_payloads: bool
    writes_files: bool
    canonical_memory_updated: bool


class HookEventError(Exception):
    """Raised when hook capture review artifacts cannot be generated."""


def normalize_provider(provider: str) -> str:
    value = provider.lower().strip()
    if value not in HOOK_EVENTS:
        raise ValueError(f"unsupported hook provider: {provider}")
    return value


def hook_events(provider: str | None = None) -> dict[str, list[str]]:
    if provider is None:
        return {name: list(events) for name, events in HOOK_EVENTS.items()}
    provider = normalize_provider(provider)
    return {provider: list(HOOK_EVENTS[provider])}


def validate_event(provider: str, event: str) -> None:
    if event not in HOOK_EVENTS[provider]:
        supported = ", ".join(HOOK_EVENTS[provider])
        raise ValueError(f"unsupported {provider} hook event: {event}. Supported events: {supported}")


def capture_hook_event(
    root: Path,
    event: str,
    payload: str,
    capture_raw: bool = False,
    provider: str = "codex",
) -> Path | None:
    provider = normalize_provider(provider)
    validate_event(provider, event)
    digest, fingerprint_mode = hook_payload_fingerprint(payload)
    existing = existing_hook_event(root, provider, event, digest)
    if existing is not None:
        return existing
    now = datetime.now(timezone.utc)
    created = now.date().isoformat()
    review_after = (now.date() + timedelta(days=7)).isoformat()
    provider_title = provider.title()
    source_kind = provider if provider in SOURCE_KINDS else "automation"
    body = [
        f"Provider: `{provider}`",
        "",
        f"Event: `{event}`",
        "",
        f"Payload fingerprint: `{digest}`",
        "",
        f"Fingerprint mode: `{fingerprint_mode}`",
        "",
        "This is hook metadata for review. Hooks do not promote durable memory.",
    ]
    if capture_raw and payload.strip():
        body.extend(["", "## Raw Payload", "", "```json", payload[:8000], "```"])
    text = f"""---
id: hook_{slugify(provider)}_{slugify(event)}_{now.strftime('%Y%m%d_%H%M%S')}_{digest}
title: "{provider_title} hook event {event}"
type: session
status: proposed
scope: session
project: null
tags: [{slugify(provider)}, hook, session-event]
aliases: []
created_at: {created}
updated_at: {created}
confidence: 0.3
sensitivity: internal
source:
  kind: {source_kind}
  ref: "hook:{provider}:{event}"
  fingerprint: "{digest}"
  fingerprint_mode: "{fingerprint_mode}"
pin: false
decay: fast
review_after: {review_after}
---

# {provider_title} hook event {event}

{chr(10).join(body)}
"""
    if scan_text(text, f"<hook:{provider}:{event}>"):
        return None
    inbox = resolve_hook_capture_inbox_root(root)
    inbox.mkdir(parents=True, exist_ok=True)
    inbox = resolve_hook_capture_inbox_root(root)
    path = inbox / f"{now.strftime('%Y%m%dT%H%M%SZ')}_{slugify(provider)}_{slugify(event)}_{digest}.md"
    path.write_text(text, encoding="utf-8")
    return path


def hook_payload_fingerprint(payload: str) -> tuple[str, str]:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        normalized = payload
        mode = "raw-text"
    else:
        normalized = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        mode = "canonical-json"
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:12]
    return digest, mode


def existing_hook_event(root: Path, provider: str, event: str, digest: str) -> Path | None:
    inbox = resolve_hook_capture_inbox_root(root)
    if not inbox.exists():
        return None
    slug_provider = slugify(provider)
    slug_event = slugify(event)
    matches = sorted(inbox.glob(f"*_{slug_provider}_{slug_event}_{digest}.md"))
    return matches[0] if matches else None


def hook_config(client: str, command: str = "ai-dememory", root: Path | str | None = None) -> dict[str, object]:
    provider = normalize_provider(client)
    root_path = Path(root) if root is not None else None
    hooks: dict[str, list[dict[str, object]]] = {}
    for event in HOOK_EVENTS[provider]:
        item: dict[str, object] = {
            "hooks": [
                hook_command_definition(
                    provider,
                    event,
                    command=command,
                    root=root_path,
                    include_windows_command=provider == "codex",
                )
            ]
        }
        if event in MATCHED_EVENTS:
            item["matcher"] = "manual|auto"
        hooks[event] = [item]
    return {"hooks": hooks}


def hook_status(root: Path, clients: list[str] | None = None) -> list[HookInstallResult]:
    selected = normalize_clients(clients)
    results: list[HookInstallResult] = []
    for client in selected:
        path = root / CLIENT_INSTRUCTION_FILES[client]
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        results.append(
            HookInstallResult(
                client=client,
                path=repo_relative_path(path, root),
                installed=managed_block_present(text, client),
                changed=False,
                dry_run=False,
                events=list(HOOK_EVENTS[client]),
            )
        )
    return results


def hook_status_summary(
    root: Path,
    clients: list[str] | None = None,
    capture_provider: str | None = None,
    capture_event: str | None = None,
    capture_review_status: str | None = None,
    capture_created_from: str | None = None,
    capture_created_to: str | None = None,
    capture_review_after_from: str | None = None,
    capture_review_after_to: str | None = None,
) -> dict[str, object]:
    results = hook_status(root, clients)
    installed_count = sum(1 for result in results if result.installed)
    return {
        "mutates_system": False,
        "runs_commands": False,
        "writes_files": False,
        "supported_clients": list(HOOK_EVENTS),
        "installed_count": installed_count,
        "all_installed": installed_count == len(results),
        "hooks": results_as_dicts(results),
        "captures": hook_capture_summary(
            root,
            provider=capture_provider,
            event=capture_event,
            review_status=capture_review_status,
            created_from=capture_created_from,
            created_to=capture_created_to,
            review_after_from=capture_review_after_from,
            review_after_to=capture_review_after_to,
        ),
    }


def normalize_filter_date(value: str | None, name: str) -> str | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise HookEventError(f"{name} must be an ISO date in YYYY-MM-DD format") from exc
    return text


def normalize_date_window(filters: dict[str, str], start_name: str, start: str | None, end_name: str, end: str | None) -> None:
    start_value = normalize_filter_date(start, start_name)
    end_value = normalize_filter_date(end, end_name)
    if start_value and end_value and date.fromisoformat(start_value) > date.fromisoformat(end_value):
        raise HookEventError(f"{start_name} must be on or before {end_name}")
    if start_value:
        filters[start_name] = start_value
    if end_value:
        filters[end_name] = end_value


def normalize_hook_capture_filters(
    provider: str | None = None,
    event: str | None = None,
    review_status: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    review_after_from: str | None = None,
    review_after_to: str | None = None,
) -> dict[str, str]:
    filters: dict[str, str] = {}
    if provider is not None and str(provider).strip():
        try:
            filters["provider"] = normalize_provider(str(provider))
        except ValueError as exc:
            raise HookEventError(str(exc)) from exc
    if event is not None and str(event).strip():
        event_value = str(event).strip()
        if filters.get("provider"):
            try:
                validate_event(filters["provider"], event_value)
            except ValueError as exc:
                raise HookEventError(str(exc)) from exc
        elif not any(event_value in events for events in HOOK_EVENTS.values()):
            supported = sorted({item for events in HOOK_EVENTS.values() for item in events})
            raise HookEventError(f"unsupported hook event filter: {event_value}. Supported events: {', '.join(supported)}")
        filters["event"] = event_value
    if review_status is not None and str(review_status).strip():
        status_value = str(review_status).strip().lower()
        if status_value not in HOOK_CAPTURE_REVIEW_FILTERS:
            supported = ", ".join(sorted(HOOK_CAPTURE_REVIEW_FILTERS))
            raise HookEventError(f"unsupported hook review status filter: {status_value}. Supported statuses: {supported}")
        filters["review_status"] = status_value
    normalize_date_window(filters, "created_from", created_from, "created_to", created_to)
    normalize_date_window(filters, "review_after_from", review_after_from, "review_after_to", review_after_to)
    return filters


def frontmatter_date_value(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def date_window_matches(value: object, filters: dict[str, str], start_name: str, end_name: str) -> bool:
    if start_name not in filters and end_name not in filters:
        return True
    parsed = frontmatter_date_value(value)
    if parsed is None:
        return False
    if start_name in filters and parsed < date.fromisoformat(filters[start_name]):
        return False
    if end_name in filters and parsed > date.fromisoformat(filters[end_name]):
        return False
    return True


def hook_capture_matches_filters(
    provider: str,
    event: str,
    review_status: str,
    created_at: object,
    review_after: object,
    filters: dict[str, str],
) -> bool:
    if filters.get("provider") and provider != filters["provider"]:
        return False
    if filters.get("event") and event != filters["event"]:
        return False
    status_filter = filters.get("review_status")
    if status_filter == "resolved":
        return review_status in HOOK_CAPTURE_REVIEW_STATUSES
    if status_filter and review_status != status_filter:
        return False
    if not date_window_matches(created_at, filters, "created_from", "created_to"):
        return False
    if not date_window_matches(review_after, filters, "review_after_from", "review_after_to"):
        return False
    return True


def hook_capture_summary(
    root: Path,
    limit: int = 5,
    provider: str | None = None,
    event: str | None = None,
    review_status: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    review_after_from: str | None = None,
    review_after_to: str | None = None,
) -> dict[str, object]:
    filters = normalize_hook_capture_filters(
        provider,
        event,
        review_status,
        created_from,
        created_to,
        review_after_from,
        review_after_to,
    )
    root_abs = Path(os.path.abspath(root))
    inbox = resolve_hook_capture_inbox_root(root)
    files = hook_capture_files(inbox)
    captures: list[dict[str, object]] = []
    malformed: list[dict[str, str]] = []
    by_provider: dict[str, int] = {}
    by_event: dict[str, int] = {}
    review_after_status_counts: dict[str, int] = {}
    review_status_counts: dict[str, int] = {}
    due_paths: list[str] = []
    unfiltered_total_count = 0
    for path in files:
        relpath = contained_relative_path(path, root_abs).as_posix()
        if path.is_symlink():
            malformed.append({"path": relpath, "error": "symlink capture entry"})
            continue
        try:
            contained_relative_path(path, inbox)
        except ValueError:
            malformed.append({"path": relpath, "error": "capture entry outside inbox"})
            continue
        try:
            frontmatter = read_hook_frontmatter(path)
            provider, event = hook_provider_event(frontmatter)
        except (FrontmatterError, ValueError) as exc:
            malformed.append({"path": relpath, "error": sanitize_hook_error(exc, root)})
            continue
        created_at = str(frontmatter.get("created_at") or "")
        review_after = str(frontmatter.get("review_after") or "")
        review_status = hook_capture_review_status(frontmatter)
        unfiltered_total_count += 1
        if not hook_capture_matches_filters(provider, event, review_status, created_at, review_after, filters):
            continue
        reviewed_by = str(frontmatter.get("reviewed_by") or "")
        reviewed_at = str(frontmatter.get("reviewed_at") or "")
        review_reason = str(frontmatter.get("review_reason") or "")
        pending_review = review_status == "pending"
        review_due, review_after_status = hook_review_after_state(review_after)
        if not pending_review:
            review_due = False
        review_after_status_counts[review_after_status] = review_after_status_counts.get(review_after_status, 0) + 1
        review_status_counts[review_status] = review_status_counts.get(review_status, 0) + 1
        if review_due:
            due_paths.append(relpath)
        by_provider[provider] = by_provider.get(provider, 0) + 1
        by_event[event] = by_event.get(event, 0) + 1
        captures.append(
            {
                "path": relpath,
                "provider": provider,
                "event": event,
                "created_at": created_at,
                "review_after": review_after,
                "review_due": review_due,
                "review_after_status": review_after_status,
                "review_status": review_status,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "review_reason": review_reason,
                "fingerprint": str((frontmatter.get("source") or {}).get("fingerprint") or ""),
                "fingerprint_mode": str((frontmatter.get("source") or {}).get("fingerprint_mode") or ""),
            }
        )
    latest = sorted(captures, key=lambda item: str(item["path"]), reverse=True)[:limit]
    resolved_count = sum(count for status, count in review_status_counts.items() if status in HOOK_CAPTURE_REVIEW_STATUSES)
    return {
        "inbox_path": repo_relative_path(inbox, root),
        "filters": filters,
        "unfiltered_total_count": unfiltered_total_count,
        "total_count": len(captures),
        "malformed_count": len(malformed),
        "by_provider": dict(sorted(by_provider.items())),
        "by_event": dict(sorted(by_event.items())),
        "pending_count": review_status_counts.get("pending", 0),
        "resolved_count": resolved_count,
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "review_due_count": len(due_paths),
        "review_due_paths": due_paths[:limit],
        "review_after_status_counts": dict(sorted(review_after_status_counts.items())),
        "latest": latest,
        "malformed": malformed[:limit],
        "limit": limit,
        "reads_raw_payloads": False,
        "writes_files": False,
    }


def hook_capture_files(inbox: Path) -> list[Path]:
    """Return candidate capture files while excluding inbox documentation."""
    if not inbox.exists():
        return []
    return sorted(path for path in inbox.glob("*.md") if path.name.casefold() != "readme.md")


def resolve_hook_report_path(root: Path, output: str | Path) -> Path:
    root_abs = Path(os.path.abspath(root))
    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = root_abs / candidate
    target = Path(os.path.abspath(candidate))
    reports_root = Path(os.path.abspath(root_abs / "reports"))
    try:
        target.relative_to(root_abs)
    except ValueError as exc:
        raise HookEventError("hook capture report path must stay inside the memory root") from exc
    try:
        target.relative_to(reports_root)
    except ValueError as exc:
        raise HookEventError("hook capture report path must stay under reports") from exc
    reject_hook_path_symlink_components(root_abs, target, "hook capture report path")
    return target


def resolve_hook_archive_root(root: Path, output: str | Path) -> Path:
    root_abs = Path(os.path.abspath(root))
    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = root_abs / candidate
    target = Path(os.path.abspath(candidate))
    archive_root = Path(os.path.abspath(root_abs / "archive" / "session-events"))
    try:
        target.relative_to(root_abs)
    except ValueError as exc:
        raise HookEventError("hook capture archive path must stay inside the memory root") from exc
    try:
        target.relative_to(archive_root)
    except ValueError as exc:
        raise HookEventError("hook capture archive path must stay under archive/session-events") from exc
    reject_hook_path_symlink_components(root_abs, target, "hook capture archive path")
    return target


def resolve_hook_capture_inbox_root(root: Path) -> Path:
    root_abs = Path(os.path.abspath(root))
    target = Path(os.path.abspath(root_abs / "inbox" / "session-events"))
    reject_hook_path_symlink_components(root_abs, target, "hook capture inbox path")
    return target


def reject_hook_path_symlink_components(root_abs: Path, target: Path, label: str) -> None:
    current = root_abs
    for part in target.relative_to(root_abs).parts:
        current = current / part
        if current.is_symlink():
            raise HookEventError(f"{label} must not contain symlinks")


def render_hook_capture_report(summary: dict[str, object]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Hook Capture Review",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "This report reads hook capture frontmatter only. It does not read raw payload bodies or promote memory.",
        "",
        "## Summary",
        "",
        f"- inbox_path: `{summary.get('inbox_path', '')}`",
        f"- filters: `{json.dumps(summary.get('filters', {}), sort_keys=True)}`",
        f"- unfiltered_total_count: `{summary.get('unfiltered_total_count', 0)}`",
        f"- total_count: `{summary.get('total_count', 0)}`",
        f"- malformed_count: `{summary.get('malformed_count', 0)}`",
        f"- pending_count: `{summary.get('pending_count', 0)}`",
        f"- resolved_count: `{summary.get('resolved_count', 0)}`",
        f"- review_due_count: `{summary.get('review_due_count', 0)}`",
        f"- reads_raw_payloads: `{str(bool(summary.get('reads_raw_payloads'))).lower()}`",
        f"- writes_files: `{str(bool(summary.get('writes_files'))).lower()}`",
        "",
    ]
    lines.extend(render_count_section("Counts By Provider", summary.get("by_provider", {})))
    lines.extend(render_count_section("Counts By Event", summary.get("by_event", {})))
    lines.extend(render_count_section("Review Status", summary.get("review_status_counts", {})))
    lines.extend(render_count_section("Review After Status", summary.get("review_after_status_counts", {})))
    lines.extend(render_path_section("Due Captures", summary.get("review_due_paths", [])))
    lines.extend(render_capture_section("Latest Captures", summary.get("latest", [])))
    lines.extend(render_malformed_section(summary.get("malformed", [])))
    return "\n".join(lines).rstrip() + "\n"


def render_count_section(title: str, counts: object) -> list[str]:
    lines = [f"## {title}", ""]
    if not isinstance(counts, dict) or not counts:
        return [*lines, "- none", ""]
    for key, value in sorted(counts.items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return lines


def render_path_section(title: str, paths: object) -> list[str]:
    lines = [f"## {title}", ""]
    if not isinstance(paths, list) or not paths:
        return [*lines, "- none", ""]
    for path in paths:
        lines.append(f"- `{path}`")
    lines.append("")
    return lines


def render_capture_section(title: str, captures: object) -> list[str]:
    lines = [f"## {title}", ""]
    if not isinstance(captures, list) or not captures:
        return [*lines, "- none", ""]
    for item in captures:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### `{item.get('path', '')}`",
                "",
                f"- provider: `{item.get('provider', '')}`",
                f"- event: `{item.get('event', '')}`",
                f"- created_at: `{item.get('created_at', '')}`",
                f"- review_after: `{item.get('review_after', '')}`",
                f"- review_after_status: `{item.get('review_after_status', '')}`",
                f"- review_due: `{str(bool(item.get('review_due'))).lower()}`",
                f"- review_status: `{item.get('review_status', '')}`",
                f"- reviewed_by: `{item.get('reviewed_by', '')}`",
                f"- reviewed_at: `{item.get('reviewed_at', '')}`",
                f"- review_reason: {item.get('review_reason', '')}",
                f"- fingerprint_mode: `{item.get('fingerprint_mode', '')}`",
                f"- fingerprint: `{item.get('fingerprint', '')}`",
                "",
            ]
        )
    return lines


def render_malformed_section(malformed: object) -> list[str]:
    lines = ["## Malformed Candidates", ""]
    if not isinstance(malformed, list) or not malformed:
        return [*lines, "- none", ""]
    for item in malformed:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"### `{item.get('path', '')}`",
                "",
                f"- error: {item.get('error', '')}",
                "",
            ]
        )
    return lines


def write_hook_capture_report(
    root: Path,
    output: str | Path = DEFAULT_CAPTURE_REPORT,
    limit: int = 20,
    provider: str | None = None,
    event: str | None = None,
    review_status: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    review_after_from: str | None = None,
    review_after_to: str | None = None,
) -> tuple[Path, dict[str, object]]:
    summary = hook_capture_summary(
        root,
        limit=limit,
        provider=provider,
        event=event,
        review_status=review_status,
        created_from=created_from,
        created_to=created_to,
        review_after_from=review_after_from,
        review_after_to=review_after_to,
    )
    target = resolve_hook_report_path(root, output)
    text = render_hook_capture_report(summary)
    if scan_text(text, "<hook-capture-report>"):
        raise HookEventError("hook capture report rejected by secret scan")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target, summary


def hook_reviewed_age_days(reviewed_at: str) -> int | None:
    value = reviewed_at.strip()
    if not value:
        return None
    try:
        reviewed_date = date.fromisoformat(value[:10])
    except ValueError:
        return None
    return (today() - reviewed_date).days


def archive_reviewed_hook_captures(
    root: Path,
    apply: bool = False,
    archive_root: str | Path = DEFAULT_CAPTURE_ARCHIVE,
    provider: str | None = None,
    event: str | None = None,
    review_status: str | None = "resolved",
    min_reviewed_days: int = 0,
    limit: int = 20,
) -> HookCaptureArchiveResult:
    if min_reviewed_days < 0:
        raise HookEventError("minimum reviewed age must be zero or greater")
    if limit < 1:
        raise HookEventError("limit must be at least 1")
    filters = normalize_hook_capture_filters(provider, event, review_status or "resolved")
    status_filter = filters.get("review_status", "resolved")
    if status_filter == "pending":
        raise HookEventError("hook capture archive only supports resolved review statuses")

    archive_target = resolve_hook_archive_root(root, archive_root)

    root_abs = Path(os.path.abspath(root))
    inbox = resolve_hook_capture_inbox_root(root)
    files = hook_capture_files(inbox)
    candidates: list[dict[str, str]] = []
    archived: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    malformed: list[dict[str, str]] = []
    unfiltered_total_count = 0

    for path in files:
        relpath = contained_relative_path(path, root_abs).as_posix()
        if path.is_symlink():
            skipped.append({"path": relpath, "reason": "symlink_capture_entry"})
            continue
        try:
            contained_relative_path(path, inbox)
        except ValueError:
            skipped.append({"path": relpath, "reason": "outside_inbox"})
            continue
        try:
            frontmatter = read_hook_frontmatter(path)
            capture_provider, capture_event = hook_provider_event(frontmatter)
        except (FrontmatterError, ValueError) as exc:
            malformed.append({"path": relpath, "reason": sanitize_hook_error(exc, root)})
            continue
        created_at = str(frontmatter.get("created_at") or "")
        review_after = str(frontmatter.get("review_after") or "")
        review_status_value = hook_capture_review_status(frontmatter)
        unfiltered_total_count += 1
        if not hook_capture_matches_filters(capture_provider, capture_event, review_status_value, created_at, review_after, filters):
            continue
        if review_status_value not in HOOK_CAPTURE_REVIEW_STATUSES:
            skipped.append({"path": relpath, "reason": "not_resolved"})
            continue
        reviewed_at = str(frontmatter.get("reviewed_at") or "")
        age_days = hook_reviewed_age_days(reviewed_at)
        if age_days is None:
            skipped.append({"path": relpath, "reason": "invalid_reviewed_at"})
            continue
        if age_days < min_reviewed_days:
            skipped.append({"path": relpath, "reason": "reviewed_too_recent"})
            continue
        destination = archive_target / path.name
        destination_relpath = repo_relative_path(destination, root)
        item = {
            "path": relpath,
            "archive_path": destination_relpath,
            "provider": capture_provider,
            "event": capture_event,
            "review_status": review_status_value,
            "reviewed_at": reviewed_at,
        }
        if destination.exists():
            skipped.append({**item, "reason": "archive_path_exists"})
            continue
        candidates.append(item)
        if apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.replace(destination)
            archived.append(item)

    return HookCaptureArchiveResult(
        dry_run=not apply,
        archive_root=repo_relative_path(archive_target, root),
        filters=filters,
        min_reviewed_days=min_reviewed_days,
        unfiltered_total_count=unfiltered_total_count,
        eligible_count=len(candidates),
        archived_count=len(archived),
        skipped_count=len(skipped),
        candidates=candidates[:limit],
        archived=archived[:limit],
        skipped=skipped[:limit],
        malformed_count=len(malformed),
        malformed=malformed[:limit],
        reads_raw_payloads=False,
        writes_files=apply,
        canonical_memory_updated=False,
    )


def hook_capture_review_status(frontmatter: dict[str, object]) -> str:
    value = str(frontmatter.get("review_status") or "").strip().lower()
    if value in HOOK_CAPTURE_REVIEW_STATUSES:
        return value
    if frontmatter.get("reviewed") is True:
        return "reviewed"
    return "pending"


def reviewed_today() -> str:
    return today().isoformat()


def ensure_hook_capture_path(root: Path, capture_path: str | Path) -> Path:
    candidate = Path(capture_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    inbox = resolve_hook_capture_inbox_root(root)
    target = Path(os.path.abspath(candidate))
    try:
        relative_target = contained_relative_path(target, inbox)
    except ValueError as exc:
        raise HookEventError("hook capture review path must stay under inbox/session-events") from exc
    current = inbox
    for part in relative_target.parts:
        current = current / part
        if current.is_symlink():
            raise HookEventError("hook capture review path must not contain symlinks")
    if target.suffix.lower() != ".md":
        raise HookEventError("hook capture review path must be a Markdown file")
    if not target.exists():
        raise HookEventError("hook capture review path does not exist")
    try:
        frontmatter = read_hook_frontmatter(target)
        hook_provider_event(frontmatter)
    except (FrontmatterError, ValueError) as exc:
        raise HookEventError(f"invalid hook capture review candidate: {sanitize_hook_error(exc, root)}") from exc
    return target


def render_frontmatter_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(" ".join(str(value).splitlines()).strip())


def read_hook_frontmatter_block(path: Path) -> tuple[list[str], int]:
    lines: list[bytes] = []
    total_bytes = 0
    with path.open("rb") as handle:
        first = handle.readline(MAX_HOOK_FRONTMATTER_BYTES + 1)
        if not first:
            raise FrontmatterError(f"{path}: missing opening frontmatter delimiter")
        if len(first) > MAX_HOOK_FRONTMATTER_BYTES:
            raise FrontmatterError(f"{path}: frontmatter exceeds maximum size")
        lines.append(first)
        total_bytes += len(first)
        if first.strip() != b"---":
            raise FrontmatterError(f"{path}: missing opening frontmatter delimiter")
        while True:
            remaining = MAX_HOOK_FRONTMATTER_BYTES - total_bytes
            if remaining <= 0:
                raise FrontmatterError(f"{path}: frontmatter exceeds maximum size")
            line = handle.readline(remaining + 1)
            if not line:
                break
            if len(line) > remaining:
                raise FrontmatterError(f"{path}: frontmatter exceeds maximum size")
            stripped = line.strip()
            if len(lines) > 1 and (stripped == b"" or stripped.startswith(b"#")):
                raise FrontmatterError(f"{path}: missing closing frontmatter delimiter")
            lines.append(line)
            total_bytes += len(line)
            if len(lines) > 1 and stripped == b"---":
                try:
                    decoded = [item.decode("utf-8").rstrip("\r\n") for item in lines]
                except UnicodeDecodeError as exc:
                    raise FrontmatterError(f"{path}: frontmatter must be UTF-8") from exc
                return decoded, handle.tell()
    raise FrontmatterError(f"{path}: missing closing frontmatter delimiter")


def update_frontmatter_fields(path: Path, updates: dict[str, object]) -> None:
    lines, body_offset = read_hook_frontmatter_block(path)
    if not lines or lines[0].strip() != "---":
        raise HookEventError("hook capture is missing opening frontmatter delimiter")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise HookEventError("hook capture is missing closing frontmatter delimiter")

    rendered_updates = {key: f"{key}: {render_frontmatter_scalar(value)}" for key, value in updates.items()}
    seen: set[str] = set()
    new_lines = list(lines)
    for index in range(1, closing_index):
        line = new_lines[index]
        if ":" not in line or line.startswith(" "):
            continue
        key = line.split(":", 1)[0].strip()
        if key in rendered_updates:
            new_lines[index] = rendered_updates[key]
            seen.add(key)
    insert_at = closing_index
    for key, line in rendered_updates.items():
        if key not in seen:
            new_lines.insert(insert_at, line)
            insert_at += 1
    updated_frontmatter = ("\n".join(new_lines) + "\n").encode("utf-8")
    temp_handle = tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(temp_handle.name)
    try:
        with path.open("rb") as source, temp_handle as target:
            source.seek(body_offset)
            target.write(updated_frontmatter)
            shutil.copyfileobj(source, target)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def review_hook_capture(
    root: Path,
    capture_path: str | Path,
    review_status: str,
    reviewed_by: str,
    reason: str,
) -> HookCaptureReviewResult:
    review_status = review_status.strip().lower()
    if review_status not in HOOK_CAPTURE_REVIEW_STATUSES:
        raise HookEventError("review status must be reviewed, rejected, or dismissed")
    reviewed_by = reviewed_by.strip()
    if not reviewed_by:
        raise HookEventError("reviewed_by is required")
    reason = " ".join(reason.split()).strip()
    if not reason:
        raise HookEventError("reason is required")

    capture_file = ensure_hook_capture_path(root, capture_path)
    frontmatter = read_hook_frontmatter(capture_file)
    current_status = hook_capture_review_status(frontmatter)
    if current_status != "pending":
        raise HookEventError(f"hook capture is already resolved with review_status: {current_status}")

    relpath = repo_relative_path(capture_file, root)
    scan_target = json.dumps(
        {
            "path": relpath,
            "review_status": review_status,
            "reviewed_by": reviewed_by,
            "reason": reason,
        },
        sort_keys=True,
    )
    if scan_text(scan_target, "<hook-capture-review>"):
        raise HookEventError("hook capture review rejected by secret scan")

    reviewed_at = reviewed_today()
    update_frontmatter_fields(
        capture_file,
        {
            "reviewed": True,
            "review_status": review_status,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "review_reason": reason,
        },
    )
    return HookCaptureReviewResult(
        path=relpath,
        review_status=review_status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        reason=reason,
        canonical_memory_updated=False,
    )


def read_hook_frontmatter(path: Path) -> dict[str, object]:
    lines, _ = read_hook_frontmatter_block(path)
    frontmatter, _ = parse_frontmatter_text("\n".join(lines), path)
    return frontmatter


def hook_review_after_state(review_after: str) -> tuple[bool, str]:
    if not review_after:
        return False, "missing"
    try:
        due_date = datetime.fromisoformat(review_after).date()
    except ValueError:
        return True, "invalid"
    if due_date <= today():
        return True, "due"
    return False, "scheduled"


def today() -> date:
    return date.today()


def sanitize_hook_error(error: Exception, root: Path) -> str:
    text = str(error)
    return text.replace(str(root.resolve()), "<root>")


def hook_provider_event(frontmatter: dict[str, object]) -> tuple[str, str]:
    source = frontmatter.get("source")
    if not isinstance(source, dict):
        raise ValueError("missing source metadata")
    ref = str(source.get("ref") or "")
    parts = ref.split(":", 2)
    if len(parts) != 3 or parts[0] != "hook":
        raise ValueError("source ref is not a hook event")
    provider = normalize_provider(parts[1])
    event = parts[2]
    validate_event(provider, event)
    return provider, event


def install_hook_instructions(
    root: Path,
    clients: list[str] | None = None,
    dry_run: bool = False,
) -> list[HookInstallResult]:
    selected = normalize_clients(clients)
    results: list[HookInstallResult] = []
    for client in selected:
        path = safe_instruction_file(root, client)
        original = path.read_text(encoding="utf-8") if path.exists() else default_instruction_text(client)
        updated = upsert_managed_block(original, client, instruction_block(client))
        changed = updated != original
        if changed and not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(updated, encoding="utf-8")
        results.append(
            HookInstallResult(
                client=client,
                path=repo_relative_path(path, root),
                installed=True,
                changed=changed,
                dry_run=dry_run,
                events=list(HOOK_EVENTS[client]),
            )
        )
    return results


def uninstall_hook_instructions(
    root: Path,
    clients: list[str] | None = None,
    dry_run: bool = False,
) -> list[HookInstallResult]:
    selected = normalize_clients(clients)
    results: list[HookInstallResult] = []
    for client in selected:
        path = safe_instruction_file(root, client)
        original = path.read_text(encoding="utf-8") if path.exists() else ""
        updated = remove_managed_block(original, client)
        changed = updated != original
        if changed and not dry_run:
            path.write_text(updated, encoding="utf-8")
        results.append(
            HookInstallResult(
                client=client,
                path=repo_relative_path(path, root),
                installed=managed_block_present(updated, client),
                changed=changed,
                dry_run=dry_run,
                events=list(HOOK_EVENTS[client]),
            )
        )
    return results


def safe_instruction_file(root: Path, client: str) -> Path:
    root = root.resolve()
    path = root / CLIENT_INSTRUCTION_FILES[client]
    if path.is_symlink():
        raise ValueError("hook instruction file must not be a symlink")
    if path.exists():
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("hook instruction file must stay inside the memory root") from exc
    return path


def normalize_clients(clients: list[str] | None) -> list[str]:
    if not clients:
        return list(HOOK_EVENTS)
    selected: list[str] = []
    for client in clients:
        if client == "all":
            return list(HOOK_EVENTS)
        selected.append(normalize_provider(client))
    return selected


def managed_markers(client: str) -> tuple[str, str]:
    return (
        f"<!-- BEGIN AI-DEMEMORY HOOKS:{client} -->",
        f"<!-- END AI-DEMEMORY HOOKS:{client} -->",
    )


def managed_block_present(text: str, client: str) -> bool:
    begin, end = managed_markers(client)
    return begin in text and end in text


def upsert_managed_block(text: str, client: str, block: str) -> str:
    begin, end = managed_markers(client)
    if begin in text and end in text:
        start = text.index(begin)
        finish = text.index(end, start) + len(end)
        updated = text[:start].rstrip() + "\n\n" + block.rstrip() + "\n" + text[finish:].lstrip()
        return updated.rstrip() + "\n"
    return text.rstrip() + "\n\n" + block.rstrip() + "\n"


def remove_managed_block(text: str, client: str) -> str:
    begin, end = managed_markers(client)
    if begin not in text or end not in text:
        return text
    start = text.index(begin)
    finish = text.index(end, start) + len(end)
    updated = text[:start].rstrip() + "\n\n" + text[finish:].lstrip()
    return updated.rstrip() + ("\n" if updated.strip() else "")


def instruction_block(client: str) -> str:
    begin, end = managed_markers(client)
    title = CLIENT_TITLES[client]
    events = ", ".join(HOOK_EVENTS[client])
    return f"""{begin}
## {title} Memory Hooks

`ai-dememory` recall hooks are optional, trust-gated, and review-first.

- Generate local hook config with `ai-dememory hooks config --client {client} --root <vault-path>`.
- Supported events: {events}.
- Before a relevant non-trivial or project task, recall by prompt keywords and working directory; skip trivial self-contained requests.
- Native hooks can inject reviewed public/internal memory. If hooks are unavailable, follow these instructions and use the memory recall skill as a weaker fallback.
- Hook metadata is deduplicated under `inbox/session-events/`; raw payload capture is off by default.
- At task end, emit only explicit stable learning signals for a review-first proposal. Never infer a durable fact from the raw transcript.
- Do not promote hook captures to durable memory without explicit human review.
- Do not store secrets, tokens, cookies, private keys, or `.env` content in memory.
{end}"""


def default_instruction_text(client: str) -> str:
    if client == "codex":
        return "# Agent Instructions\n"
    return "# Claude Instructions\n"


def hook_command_definition(
    provider: str,
    event: str,
    command: str,
    root: Path | None,
    include_windows_command: bool = False,
) -> dict[str, object]:
    args = [command, "hook-event", "dispatch", "--provider", provider, "--event", event]
    if root is not None:
        args.extend(["--root", str(root)])
    command_line = serialize_hook_command(args, windows=False)
    definition: dict[str, object] = {
        "type": "command",
        "command": command_line,
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "statusMessage": "Capturing memory hook metadata",
    }
    if include_windows_command:
        definition["commandWindows"] = serialize_hook_command(args, windows=True)
    return definition


def serialize_hook_command(args: list[str], *, windows: bool) -> str:
    """Serialize hook argv for the provider's documented shell.

    Provider configs require a command string rather than an argv array. Use
    the platform serializers instead of bespoke quoting so valid vault paths
    containing shell metacharacters remain a single inert argument.
    """
    return serialize_windows_hook_command(args) if windows else shlex.join(args)


def serialize_windows_hook_command(args: list[str]) -> str:
    """Build a cmd-safe launcher without interpolating user data into a shell."""
    # cmd.exe expands %VAR% even inside quotes, while delayed expansion can do
    # the same for !VAR!. Encode argv as data and let a fixed PowerShell script
    # invoke it as an argument array. The outer command contains no user bytes.
    argv_payload = base64.b64encode(
        json.dumps(args, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    script = (
        f"$p='{argv_payload}';"
        "$j=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p));"
        "[string[]]$a=$j|ConvertFrom-Json;"
        "$e=[string]$a[0];"
        "$r=@($a|Select-Object -Skip 1);"
        "& $e @r;"
        "if($null-ne$LASTEXITCODE){exit $LASTEXITCODE}"
    )
    encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return (
        "powershell.exe -NoLogo -NoProfile -NonInteractive "
        f"-EncodedCommand {encoded_script}"
    )


def run_capture(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--provider", default="codex", choices=tuple(HOOK_EVENTS), help="Hook provider.")
    parser.add_argument("--event", required=True, help="Provider hook event name.")
    parser.add_argument("--capture-raw", action="store_true", help="Include raw hook payload after secret scan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    payload = sys.stdin.buffer.read(MAX_STDIN_BYTES).decode("utf-8", errors="replace")
    path = capture_hook_event(root, args.event, payload, capture_raw=args.capture_raw, provider=args.provider)
    result = {"path": repo_relative_path(path, root) if path else None, "captured": path is not None}
    # hook-event may be invoked directly by a harness; stdout is always JSON.
    print(json.dumps(result, indent=2 if args.json else None))
    return 0


def run_dispatch(argv: list[str] | None = None) -> int:
    """Dispatch a generic stdin JSON hook without ever emitting free-form stdout."""
    parser = argparse.ArgumentParser(description="Inject relevant memory into a harness hook.")
    parser.add_argument("--root", default=None, help="Memory vault root. Defaults to this repo.")
    parser.add_argument("--client", "--provider", dest="client", choices=(*HOOK_EVENTS.keys(), "generic"), default="generic")
    parser.add_argument("--event", required=True, help="Harness event name.")
    parser.add_argument("--budget-tokens", type=int, default=None)
    parser.add_argument("--capture-raw", action="store_true", help="Opt in to raw metadata capture after secret scan.")
    args = parser.parse_args(argv)
    payload = sys.stdin.buffer.read(MAX_STDIN_BYTES).decode("utf-8", errors="replace")
    try:
        root = repo_root(args.root)
        if (
            args.client in HOOK_EVENTS
            and args.event in HOOK_EVENTS[args.client]
            and hook_metadata_enabled(root, args.client)
        ):
            try:
                capture_hook_event(root, args.event, payload, capture_raw=args.capture_raw, provider=args.client)
            except Exception:
                # Metadata capture is independent from the hook protocol.
                pass
        response = dispatch_hook_event(root, args.event, payload, args.client, args.budget_tokens)
    except Exception:
        response = {}
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    return 0


def results_as_dicts(results: list[HookInstallResult]) -> list[dict[str, object]]:
    return [asdict(result) for result in results]


def run_events(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="List supported hook events.")
    parser.add_argument("--client", "--provider", dest="provider", choices=tuple(HOOK_EVENTS), default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    events = hook_events(args.provider)
    if args.json:
        print(json.dumps({"providers": events}, indent=2))
        return 0
    for provider, provider_events in events.items():
        print(f"{provider}: {', '.join(provider_events)}")
    return 0


def run_list(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="List hook instruction install status.")
    parser.add_argument("--root", default=None, help="Repository or vault root. Defaults to this repo.")
    parser.add_argument("--client", choices=(*HOOK_EVENTS.keys(), "all"), default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    results = hook_status(root, [args.client])
    if args.json:
        print(json.dumps({"hooks": results_as_dicts(results)}, indent=2))
        return 0
    for result in results:
        state = "installed" if result.installed else "not installed"
        print(f"{result.client}: {state} in {result.path} ({', '.join(result.events)})")
    return 0


def run_captures(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Summarize hook capture review candidates.")
    parser.add_argument("--root", default=None, help="Repository or vault root. Defaults to this repo.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum latest, due, and malformed entries to include.")
    parser.add_argument("--provider", choices=tuple(HOOK_EVENTS), default=None, help="Filter captures by provider.")
    parser.add_argument(
        "--event",
        choices=tuple(sorted({event for events in HOOK_EVENTS.values() for event in events})),
        default=None,
        help="Filter captures by hook event.",
    )
    parser.add_argument(
        "--review-status",
        choices=tuple(sorted(HOOK_CAPTURE_REVIEW_FILTERS)),
        default=None,
        help="Filter captures by review status. Use resolved for any reviewed/rejected/dismissed capture.",
    )
    parser.add_argument("--created-from", default=None, help="Filter captures created on or after this YYYY-MM-DD date.")
    parser.add_argument("--created-to", default=None, help="Filter captures created on or before this YYYY-MM-DD date.")
    parser.add_argument("--review-after-from", default=None, help="Filter captures with review_after on or after this YYYY-MM-DD date.")
    parser.add_argument("--review-after-to", default=None, help="Filter captures with review_after on or before this YYYY-MM-DD date.")
    parser.add_argument("--write-report", action="store_true", help="Write a Markdown review report under the vault.")
    parser.add_argument("--report-path", default=str(DEFAULT_CAPTURE_REPORT), help="Report path relative to the vault.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    try:
        if args.write_report:
            path, summary = write_hook_capture_report(
                root,
                args.report_path,
                limit=args.limit,
                provider=args.provider,
                event=args.event,
                review_status=args.review_status,
                created_from=args.created_from,
                created_to=args.created_to,
                review_after_from=args.review_after_from,
                review_after_to=args.review_after_to,
            )
            result = {"report_path": repo_relative_path(path, root), "summary": summary}
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Wrote {result['report_path']}")
                print(f"Hook captures: {summary['total_count']} total, {summary['review_due_count']} due")
            return 0
        summary = hook_capture_summary(
            root,
            limit=args.limit,
            provider=args.provider,
            event=args.event,
            review_status=args.review_status,
            created_from=args.created_from,
            created_to=args.created_to,
            review_after_from=args.review_after_from,
            review_after_to=args.review_after_to,
        )
    except HookEventError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"Hook captures: {summary['total_count']} total, {summary['review_due_count']} due")
    print(f"Inbox: {summary['inbox_path']}")
    if summary["review_due_paths"]:
        print("Due:")
        for path in summary["review_due_paths"]:
            print(f"- {path}")
    return 0


def run_review(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Record a reviewed outcome on a hook capture candidate.")
    parser.add_argument("--root", default=None, help="Repository or vault root. Defaults to this repo.")
    parser.add_argument("--path", required=True, help="Hook capture path under inbox/session-events.")
    parser.add_argument("--status", required=True, choices=tuple(sorted(HOOK_CAPTURE_REVIEW_STATUSES)))
    parser.add_argument("--reviewed-by", required=True, help="Reviewer name.")
    parser.add_argument("--reason", required=True, help="Short review reason.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    try:
        result = review_hook_capture(root, args.path, args.status, args.reviewed_by, args.reason)
    except HookEventError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Reviewed {result.path}: {result.review_status} by {result.reviewed_by} on {result.reviewed_at}")
    return 0


def run_archive(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Archive reviewed hook capture candidates.")
    parser.add_argument("--root", default=None, help="Repository or vault root. Defaults to this repo.")
    parser.add_argument("--apply", action="store_true", help="Move eligible captures. Defaults to preview only.")
    parser.add_argument("--archive-root", default=str(DEFAULT_CAPTURE_ARCHIVE), help="Archive directory under archive/session-events.")
    parser.add_argument("--provider", choices=tuple(HOOK_EVENTS), default=None, help="Filter captures by provider.")
    parser.add_argument(
        "--event",
        choices=tuple(sorted({event for events in HOOK_EVENTS.values() for event in events})),
        default=None,
        help="Filter captures by hook event.",
    )
    parser.add_argument(
        "--review-status",
        choices=tuple(sorted([*HOOK_CAPTURE_REVIEW_STATUSES, "resolved"])),
        default="resolved",
        help="Filter captures by resolved review status.",
    )
    parser.add_argument("--min-reviewed-days", type=int, default=0, help="Only archive captures reviewed at least this many days ago.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum candidates, archived items, skips, and malformed entries to include.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    try:
        result = archive_reviewed_hook_captures(
            root,
            apply=args.apply,
            archive_root=args.archive_root,
            provider=args.provider,
            event=args.event,
            review_status=args.review_status,
            min_reviewed_days=args.min_reviewed_days,
            limit=args.limit,
        )
    except HookEventError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = asdict(result)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        action = "Archived" if args.apply else "Would archive"
        print(f"{action} {result.archived_count if args.apply else result.eligible_count} hook capture(s).")
        print(f"Archive: {result.archive_root}")
    return 0


def run_config(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Print provider hook configuration.")
    parser.add_argument("--client", "--provider", dest="provider", choices=tuple(HOOK_EVENTS), default="codex")
    parser.add_argument("--command", default="ai-dememory", help="Installed CLI command clients should call.")
    parser.add_argument("--root", default=None, help="Vault root to pass to hook-event commands.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve() if args.root else None
    print(json.dumps(hook_config(args.provider, command=args.command, root=root), indent=2))
    return 0


def run_install(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Install managed hook instruction blocks.")
    parser.add_argument("--root", default=None, help="Repository or vault root. Defaults to this repo.")
    parser.add_argument("--client", choices=(*HOOK_EVENTS.keys(), "all"), default="all")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    results = install_hook_instructions(root, [args.client], dry_run=args.dry_run)
    if args.json:
        print(json.dumps({"hooks": results_as_dicts(results)}, indent=2))
        return 0
    for result in results:
        action = "would update" if result.dry_run and result.changed else "updated" if result.changed else "already installed"
        print(f"{result.client}: {action} {result.path}")
    return 0


def run_uninstall(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Remove managed hook instruction blocks.")
    parser.add_argument("--root", default=None, help="Repository or vault root. Defaults to this repo.")
    parser.add_argument("--client", choices=(*HOOK_EVENTS.keys(), "all"), default="all")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    results = uninstall_hook_instructions(root, [args.client], dry_run=args.dry_run)
    if args.json:
        print(json.dumps({"hooks": results_as_dicts(results)}, indent=2))
        return 0
    for result in results:
        action = "would remove" if result.dry_run and result.changed else "removed" if result.changed else "not installed"
        print(f"{result.client}: {action} {result.path}")
    return 0


def pop_global_root(argv: list[str]) -> str | None:
    if not argv:
        return None
    if argv[0] == "--root":
        if len(argv) < 2:
            raise SystemExit("--root requires a path")
        argv.pop(0)
        return argv.pop(0)
    if argv[0].startswith("--root="):
        return argv.pop(0).split("=", 1)[1]
    return None


def has_root_arg(argv: list[str]) -> bool:
    return any(arg == "--root" or arg.startswith("--root=") for arg in argv)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    root_override = pop_global_root(args)
    if args and args[0] == "dispatch":
        dispatch_args = args[1:]
        if root_override and not has_root_arg(dispatch_args):
            dispatch_args = ["--root", root_override, *dispatch_args]
        return run_dispatch(dispatch_args)
    if args and args[0] == "events":
        return run_events(args[1:])
    if args and args[0] == "list":
        list_args = args[1:]
        if root_override and not has_root_arg(list_args):
            list_args = ["--root", root_override, *list_args]
        return run_list(list_args)
    if args and args[0] == "captures":
        capture_args = args[1:]
        if root_override and not has_root_arg(capture_args):
            capture_args = ["--root", root_override, *capture_args]
        return run_captures(capture_args)
    if args and args[0] == "review":
        review_args = args[1:]
        if root_override and not has_root_arg(review_args):
            review_args = ["--root", root_override, *review_args]
        return run_review(review_args)
    if args and args[0] == "archive":
        archive_args = args[1:]
        if root_override and not has_root_arg(archive_args):
            archive_args = ["--root", root_override, *archive_args]
        return run_archive(archive_args)
    if args and args[0] == "config":
        config_args = args[1:]
        if root_override and not has_root_arg(config_args):
            config_args = ["--root", root_override, *config_args]
        return run_config(config_args)
    if args and args[0] == "install":
        install_args = args[1:]
        if root_override and not has_root_arg(install_args):
            install_args = ["--root", root_override, *install_args]
        return run_install(install_args)
    if args and args[0] == "uninstall":
        uninstall_args = args[1:]
        if root_override and not has_root_arg(uninstall_args):
            uninstall_args = ["--root", root_override, *uninstall_args]
        return run_uninstall(uninstall_args)
    if root_override and not has_root_arg(args):
        args = ["--root", root_override, *args]
    return run_capture(args)


if __name__ == "__main__":
    raise SystemExit(main())
