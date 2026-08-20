#!/usr/bin/env python3
"""Detect and import local LLM chat files into the review inbox."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (SOURCE_ROOT / "pyproject.toml").is_file() and str(SOURCE_ROOT) not in sys.path:
    # Direct source-checkout commands must use the matching local package.
    sys.path.insert(0, str(SOURCE_ROOT))

from ai_dememory_tool.argument_safety import reject_duplicate_options  # noqa: E402
from command_render import render_copy_command
from config_file import CONFIG_NAME, load_config, set_section
from memorylib import (
    path_is_link_like,
    repo_relative_path,
    repo_root,
    safe_write_text,
    slugify,
)
from resource_policy import HARD_LIMITS, resolved_resource_policy
from secret_scan import scan_text


CHAT_SUFFIXES = {".jsonl", ".json", ".md", ".txt", ".log"}
SKIP_PARTS = {"Cache", "Code Cache", "GPUCache", "__pycache__", "node_modules", ".git"}
MAX_FILE_BYTES = 64 * 1024
MAX_EXPORT_BYTES = 2 * 1024 * 1024
MAX_FILES = 20
MAX_SCAN_ENTRIES = 2500
CAPTURE_KINDS = {"chatgpt", "claude", "codex", "cursor", "windsurf", "markdown", "text", "conversation"}


@dataclass(frozen=True)
class ProviderCandidate:
    name: str
    path: str
    exists: bool
    configured: bool
    enabled: bool


@dataclass(frozen=True)
class CaptureItem:
    title: str
    source_label: str
    text: str


@dataclass(frozen=True)
class ChatFileScan:
    files: list[Path]
    scanned_entries: int
    truncated: bool


def default_provider_paths() -> dict[str, list[Path]]:
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", ""))
    return {
        "codex": [home / ".codex"],
        "claude": [home / ".claude", appdata / "Claude"],
        "chatgpt": [home / "Downloads" / "conversations.json"],
        "cursor": [appdata / "Cursor" / "User"],
        "windsurf": [appdata / "Windsurf" / "User"],
    }


def provider_config(root: Path) -> dict[str, dict[str, Any]]:
    config = load_config(root)
    providers: dict[str, dict[str, Any]] = {}
    for section, values in config.items():
        if section.startswith("providers."):
            providers[section.split(".", 1)[1]] = values
    return providers


def detect_providers(root: Path) -> list[ProviderCandidate]:
    configured = provider_config(root)
    candidates: list[ProviderCandidate] = []
    for name, default_paths in default_provider_paths().items():
        values = configured.get(name, {})
        configured_path = str(values.get("path") or "")
        paths = [Path(configured_path).expanduser()] if configured_path else default_paths
        chosen = next((path for path in paths if path.exists()), paths[0])
        candidates.append(
            ProviderCandidate(
                name=name,
                path=str(chosen),
                exists=chosen.exists(),
                configured=name in configured,
                enabled=bool(values.get("enabled", False)),
            )
        )
    return candidates


def providers_status(root: Path) -> dict[str, Any]:
    providers = []
    for candidate in detect_providers(root):
        import_ready = candidate.configured and candidate.enabled and candidate.exists
        if import_ready:
            reason = "ready"
        elif not candidate.configured:
            reason = "not_configured"
        elif not candidate.enabled:
            reason = "disabled"
        else:
            reason = "path_missing"
        providers.append(
            {
                "name": candidate.name,
                "path": candidate.path,
                "exists": candidate.exists,
                "configured": candidate.configured,
                "enabled": candidate.enabled,
                "import_ready": import_ready,
                "reason": reason,
            }
        )
    return {
        "providers": providers,
        "configured_count": sum(1 for item in providers if item["configured"]),
        "enabled_count": sum(1 for item in providers if item["enabled"]),
        "import_ready_count": sum(1 for item in providers if item["import_ready"]),
        "mutates_system": False,
        "reads_provider_files": False,
        "writes_import_candidates": False,
    }


def provider_plan_reason(candidate: ProviderCandidate) -> tuple[str, str]:
    if candidate.configured and candidate.enabled and candidate.exists:
        return "ready_for_import", "Run the import command when you want review candidates."
    if candidate.configured and candidate.enabled and not candidate.exists:
        return "configured_path_missing", "Choose a new path or disable this provider."
    if candidate.configured and not candidate.enabled:
        return "configured_disabled", "Enable with a reviewed configure command before imports run."
    if candidate.exists:
        return "detected_unconfigured", "Review the path, then run the configure command if it is the right provider folder."
    return "not_detected", "Choose a provider export or local folder path before configuring."


def provider_setup_plan(root: Path, command: str = "ai-dememory") -> dict[str, Any]:
    bound_command = [command, "--root", str(root.resolve())]
    providers: list[dict[str, Any]] = []
    for candidate in detect_providers(root):
        reason, next_action = provider_plan_reason(candidate)
        configure_command = [*bound_command, "providers", "configure", candidate.name, "--path", candidate.path]
        providers.append(
            {
                "name": candidate.name,
                "path": candidate.path,
                "path_source": "configured" if candidate.configured else "detected_default",
                "exists": candidate.exists,
                "configured": candidate.configured,
                "enabled": candidate.enabled,
                "import_ready": candidate.configured and candidate.enabled and candidate.exists,
                "reason": reason,
                "next_action": next_action,
                "configure_dry_run_command": [*configure_command, "--dry-run", "--json"],
                "configure_command": configure_command,
                "disable_command": [*configure_command, "--disable"],
                "import_dry_run_command": [*bound_command, "import-chats", candidate.name, "--dry-run", "--json"],
                "import_command": [*bound_command, "import-chats", candidate.name],
            }
        )
    return {
        "providers": providers,
        "mutates_system": False,
        "reads_provider_files": False,
        "writes_import_candidates": False,
        "next_actions": [
            "Review detected paths before configuring providers.",
            "Run a configure command only for providers and paths the user chooses.",
            "Run import commands manually or through opt-in maintenance after configuration.",
        ],
    }


def configure_provider(root: Path, name: str, path: Path, enabled: bool = True) -> Path:
    values = provider_config_values(name, path, enabled)
    return set_section(root, f"providers.{name}", values)


def provider_config_values(name: str, path: Path, enabled: bool = True) -> dict[str, Any]:
    if name not in default_provider_paths():
        raise ValueError(f"unknown provider: {name}")
    return {
        "enabled": enabled,
        "path": str(path.expanduser().resolve()),
        "capture_raw": False,
    }


def configure_provider_preview(root: Path, name: str, path: Path, enabled: bool = True) -> dict[str, Any]:
    values = provider_config_values(name, path, enabled)
    normalized = Path(str(values["path"]))
    return {
        "provider": name,
        "section": f"providers.{name}",
        "config_path": repo_relative_path(root / CONFIG_NAME, root),
        "values": values,
        "path": str(normalized),
        "path_exists": normalized.exists(),
        "enabled": enabled,
        "dry_run": True,
        "mutates_config": False,
        "writes_files": False,
        "reads_provider_files": False,
        "writes_import_candidates": False,
        "configure_command": ["ai-dememory", "--root", str(root.resolve()), "providers", "configure", name, "--path", str(normalized)]
        + ([] if enabled else ["--disable"]),
        "next_action": "Run configure without --dry-run after reviewing the provider path.",
    }


def configured_import_path(root: Path, provider: str, source_path: Path | None) -> Path:
    if source_path is not None:
        path = source_path
    else:
        config = provider_config(root).get(provider)
        if not config:
            raise ValueError(f"provider {provider} is not configured")
        if not config.get("enabled", False):
            raise ValueError(f"provider {provider} is disabled")
        configured = str(config.get("path") or "").strip()
        if not configured:
            raise ValueError(f"provider {provider} has no path")
        path = Path(configured)
    lexical = Path(os.path.abspath(path.expanduser()))
    if path_is_link_like(lexical):
        raise ValueError(f"provider path must not be a symlink or junction: {lexical}")
    return lexical


def import_chats(
    root: Path,
    provider: str,
    source_path: Path | None = None,
    limit: int | None = None,
    max_file_bytes: int | None = None,
    max_scan_entries: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if provider not in default_provider_paths():
        raise ValueError(f"unknown provider: {provider}")
    source_root = configured_import_path(root, provider, source_path)
    if not source_root.exists():
        raise FileNotFoundError(f"provider path does not exist: {source_root}")

    policy = resolved_resource_policy(root)
    resources = policy["resources"]
    if not isinstance(resources, dict):
        raise ValueError("resolved resource policy is invalid")
    limit = bounded_runtime_limit(
        limit,
        int(resources["provider_file_limit"]),
        "provider_file_limit",
    )
    max_file_bytes = bounded_runtime_limit(
        max_file_bytes,
        int(resources["provider_max_file_bytes"]),
        "provider_max_file_bytes",
    )
    max_scan_entries = bounded_runtime_limit(
        max_scan_entries,
        int(resources["provider_scan_entries"]),
        "provider_scan_entries",
    )
    scan = scan_chat_files(source_root, max_scan_entries=max_scan_entries)
    written: list[str] = []
    would_write: list[str] = []
    skipped: list[dict[str, str]] = []
    examined = 0
    already_imported = 0
    for source_file in scan.files:
        if len(written) + len(would_write) >= limit:
            break
        examined += 1
        try:
            raw = read_provider_file(source_file, source_root, max_file_bytes)
        except (OSError, ValueError) as exc:
            skipped.append({"path": str(source_file), "reason": f"read failed: {exc}"})
            continue
        if b"\x00" in raw[:4096]:
            skipped.append({"path": str(source_file), "reason": "binary"})
            continue
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            skipped.append({"path": str(source_file), "reason": "empty"})
            continue
        fingerprint = import_fingerprint(source_file, text)
        existing = existing_import_candidate(root, provider, source_file, fingerprint)
        if existing is not None:
            already_imported += 1
            skipped.append(
                {
                    "path": str(source_file),
                    "reason": "already imported",
                    "existing": repo_relative_path(existing, root),
                }
            )
            continue
        rendered = render_import_candidate(provider, source_file, text, fingerprint=fingerprint)
        if scan_text(rendered, f"<import:{provider}:{source_file}>"):
            skipped.append({"path": str(source_file), "reason": "secret-like content"})
            continue
        if dry_run:
            would_write.append(repo_relative_path(import_candidate_path(root, provider, source_file, rendered, fingerprint), root))
        else:
            target = write_import_candidate(root, provider, source_file, rendered, fingerprint)
            written.append(repo_relative_path(target, root))
    new_candidates = len(written) + len(would_write)
    coverage_blocked = (
        scan.truncated
        and examined > 0
        and already_imported == examined
        and new_candidates == 0
    )
    suggested_scan_entries = (
        min(
            max_scan_entries * 2,
            int(HARD_LIMITS["provider_scan_entries"]["maximum"]),
        )
        if scan.truncated
        else None
    )
    if coverage_blocked and suggested_scan_entries == max_scan_entries:
        next_action = (
            "The configured hard scan ceiling was reached after revisiting only known files; "
            "narrow or reorganize the provider source before the next import."
        )
    elif coverage_blocked:
        next_action = (
            "The bounded scan window contains only previously imported files; review a higher "
            f"intensity or retry with --scan-limit {suggested_scan_entries}."
        )
    elif scan.truncated:
        next_action = (
            "More provider entries exist beyond this bounded scan window; later imports may "
            f"need --scan-limit {suggested_scan_entries} after this batch is reviewed."
        )
    else:
        next_action = "The configured provider source was fully enumerated within this run."
    return {
        "provider": provider,
        "source_path": str(source_root),
        "dry_run": dry_run,
        "reads_provider_files": True,
        "writes_import_candidates": not dry_run and bool(written),
        "examined": examined,
        "already_imported": already_imported,
        "new_candidates": new_candidates,
        "scanned_entries": scan.scanned_entries,
        "scan_truncated": scan.truncated,
        "coverage_complete": not scan.truncated,
        "coverage_blocked": coverage_blocked,
        "suggested_scan_entries": suggested_scan_entries,
        "remaining_estimate_lower_bound": max(
            1 if scan.truncated else 0,
            len(scan.files) - examined,
        ),
        "next_action": next_action,
        "limits": {
            "max_new_candidates": limit,
            "max_file_bytes": max_file_bytes,
            "max_scan_entries": max_scan_entries,
        },
        "written": written,
        "would_write": would_write,
        "skipped": skipped,
    }


def capture_source(
    root: Path,
    kind: str,
    source_path: Path | None = None,
    text: str | None = None,
    title: str | None = None,
    limit: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> dict[str, Any]:
    if kind not in CAPTURE_KINDS:
        raise ValueError(f"unknown capture kind: {kind}")
    if source_path is None and text is None:
        raise ValueError("capture requires --path, --text, or --stdin")
    if source_path is not None and text is not None:
        raise ValueError("capture accepts either source_path or text, not both")

    if text is not None:
        items = [CaptureItem(title or f"{kind} text capture", "<text>", text)]
        source_label = "<text>"
    else:
        source_root = Path(os.path.abspath(source_path.expanduser()))
        if path_is_link_like(source_root):
            raise ValueError(f"capture path must not be a symlink or junction: {source_root}")
        if not source_root.exists():
            raise FileNotFoundError(f"capture path does not exist: {source_root}")
        source_label = str(source_root)
        if kind == "chatgpt" and source_root.is_file() and source_root.suffix.lower() == ".json":
            items = extract_chatgpt_export(source_root, limit=limit)
        else:
            items = capture_items_from_path(source_root, kind, limit=limit, max_file_bytes=max_file_bytes)

    written: list[str] = []
    skipped: list[dict[str, str]] = []
    for item in items:
        item_text = item.text.strip()
        if not item_text:
            skipped.append({"path": item.source_label, "reason": "empty"})
            continue
        rendered = render_import_candidate(kind, Path(item.source_label), item_text, title=item.title)
        if scan_text(rendered, f"<capture:{kind}:{item.source_label}>"):
            skipped.append({"path": item.source_label, "reason": "secret-like content"})
            continue
        target = write_import_candidate(root, kind, Path(item.source_label), rendered)
        written.append(repo_relative_path(target, root))
    return {
        "kind": kind,
        "source_path": source_label,
        "examined": len(items),
        "written": written,
        "skipped": skipped,
    }


def discover_chat_files(
    source_root: Path,
    limit: int,
    max_scan_entries: int = MAX_SCAN_ENTRIES,
) -> list[Path]:
    """Return recent matching files while bounding directory enumeration."""
    scan = scan_chat_files(source_root, max_scan_entries=max_scan_entries)
    return scan.files[: max(1, limit)]


def scan_chat_files(source_root: Path, max_scan_entries: int = MAX_SCAN_ENTRIES) -> ChatFileScan:
    if max_scan_entries < 1:
        raise ValueError("max_scan_entries must be positive")
    if path_is_link_like(source_root):
        raise ValueError(f"provider path must not be a symlink or junction: {source_root}")
    if source_root.is_file():
        return ChatFileScan(files=[source_root], scanned_entries=1, truncated=False)

    files_with_mtime: list[tuple[float, Path]] = []
    stack = [source_root]
    scanned_entries = 0
    truncated = False
    while stack:
        directory = stack.pop()
        try:
            entries = os.scandir(directory)
        except OSError:
            continue
        with entries:
            for entry in entries:
                if scanned_entries >= max_scan_entries:
                    truncated = True
                    break
                scanned_entries += 1
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_PARTS and not entry.is_symlink():
                            stack.append(Path(entry.path))
                        continue
                    if (
                        entry.is_file(follow_symlinks=False)
                        and Path(entry.name).suffix.lower() in CHAT_SUFFIXES
                        and not any(part in SKIP_PARTS for part in Path(entry.path).parts)
                    ):
                        files_with_mtime.append((entry.stat(follow_symlinks=False).st_mtime, Path(entry.path)))
                except OSError:
                    continue
        if truncated:
            break
    files_with_mtime.sort(key=lambda item: (-item[0], str(item[1]).casefold()))
    return ChatFileScan(
        files=[path for _, path in files_with_mtime],
        scanned_entries=scanned_entries,
        truncated=truncated or bool(stack),
    )


def bounded_runtime_limit(value: int | None, default: int, limit_name: str) -> int:
    parsed = default if value is None else value
    if not isinstance(parsed, int) or isinstance(parsed, bool):
        raise ValueError(f"{limit_name} must be an integer")
    limits = HARD_LIMITS[limit_name]
    minimum = int(limits["minimum"])
    maximum = int(limits["maximum"])
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{limit_name} must be between {minimum} and {maximum}")
    return parsed


def capture_items_from_path(
    source_root: Path,
    kind: str,
    limit: int,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> list[CaptureItem]:
    files = discover_chat_files(source_root, limit)
    items: list[CaptureItem] = []
    for source_file in files:
        try:
            raw = read_provider_file(source_file, source_root, max_file_bytes)
        except (OSError, ValueError):
            continue
        if b"\x00" in raw[:4096]:
            continue
        text = raw.decode("utf-8", errors="replace").strip()
        title = f"{kind} capture {source_file.stem}"
        items.append(CaptureItem(title, str(source_file), text))
    return items


def extract_chatgpt_export(source_file: Path, limit: int = MAX_FILES) -> list[CaptureItem]:
    raw = read_provider_file(source_file, source_file.parent, MAX_EXPORT_BYTES)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    conversations = data if isinstance(data, list) else data.get("conversations", []) if isinstance(data, dict) else []
    if not isinstance(conversations, list):
        raise ValueError("ChatGPT export must contain a list of conversations")

    items: list[CaptureItem] = []
    for index, conversation in enumerate(conversations[: max(1, limit)]):
        if not isinstance(conversation, dict):
            continue
        title = str(conversation.get("title") or f"ChatGPT conversation {index + 1}").strip()
        body = chatgpt_conversation_text(conversation)
        if body.strip():
            items.append(CaptureItem(title, f"{source_file}#{slugify(title, 'conversation')}", body))
    return items


def read_provider_file(source_file: Path, source_root: Path, max_bytes: int) -> bytes:
    """Read one regular provider file after handle-bound no-link checks."""

    if max_bytes < 1:
        raise ValueError("provider read limit must be positive")
    path = Path(os.path.abspath(source_file))
    root = Path(os.path.abspath(source_root))
    boundary = root if root.is_dir() else root.parent
    try:
        relative = path.relative_to(boundary)
    except ValueError as exc:
        raise ValueError("provider file escaped the configured source root") from exc

    def assert_safe_components() -> None:
        current = boundary
        if path_is_link_like(current):
            raise ValueError("provider source root must not be a symlink or junction")
        for part in relative.parts:
            current = current / part
            if path_is_link_like(current):
                raise ValueError("provider file path must not contain symlinks or junctions")

    assert_safe_components()
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("provider source must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        after_open = path.lstat()
        identity = (before.st_dev, before.st_ino)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(after_open.st_mode)
            or identity != (opened.st_dev, opened.st_ino)
            or identity != (after_open.st_dev, after_open.st_ino)
        ):
            raise ValueError("provider file changed before it could be read safely")
        assert_safe_components()
        chunks: list[bytes] = []
        remaining = max_bytes
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        final = path.lstat()
        if (
            path_is_link_like(path)
            or not stat.S_ISREG(final.st_mode)
            or identity != (final.st_dev, final.st_ino)
        ):
            raise ValueError("provider file changed while it was being read")
        assert_safe_components()
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def chatgpt_conversation_text(conversation: dict[str, Any]) -> str:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        return json.dumps(conversation, indent=2)[:8000]

    messages: list[tuple[float, str]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content") if isinstance(message.get("content"), dict) else {}
        parts = content.get("parts") if isinstance(content, dict) else []
        text_parts = [part for part in parts if isinstance(part, str) and part.strip()]
        if not text_parts:
            continue
        author = message.get("author") if isinstance(message.get("author"), dict) else {}
        role = str(author.get("role") or "unknown")
        create_time = message.get("create_time")
        try:
            sort_key = float(create_time)
        except (TypeError, ValueError):
            sort_key = float(len(messages))
        messages.append((sort_key, f"{role}: {' '.join(text_parts).strip()}"))
    messages.sort(key=lambda item: item[0])
    return "\n\n".join(text for _, text in messages)


def import_fingerprint(source_file: Path, text: str) -> str:
    return hashlib.sha256((str(source_file) + "\n" + text).encode("utf-8")).hexdigest()[:12]


def existing_import_candidate(root: Path, provider: str, source_file: Path, fingerprint: str) -> Path | None:
    inbox = root / "inbox" / "imports" / provider
    if not inbox.exists():
        return None
    slug = slugify(source_file.stem, "chat")
    matches = sorted(inbox.glob(f"*_{slug}_{fingerprint}.md"))
    return matches[0] if matches else None


def render_import_candidate(
    provider: str,
    source_file: Path,
    text: str,
    title: str | None = None,
    fingerprint: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    created = now.date().isoformat()
    review_after = (now.date() + timedelta(days=7)).isoformat()
    digest = fingerprint or import_fingerprint(source_file, text)
    title = title or f"{provider} import candidate {digest}"
    excerpt = text[:8000].rstrip()
    source_ref = f"{provider}:{source_file}"
    yaml_title = json.dumps(title, ensure_ascii=False)
    yaml_source_ref = json.dumps(source_ref, ensure_ascii=False)
    display_title = re.sub(r"[\r\n]+", " ", title).strip() or f"{provider} import candidate {digest}"
    source_display = str(source_file).replace("`", "'").replace("\r", " ").replace("\n", " ")
    longest_backtick_run = max((len(match.group(0)) for match in re.finditer(r"`+", excerpt)), default=0)
    fence = "`" * max(3, longest_backtick_run + 1)
    return f"""---
id: import_{provider}_{now.strftime('%Y%m%d_%H%M%S')}_{digest}
title: {yaml_title}
type: session
status: proposed
scope: session
project: null
tags: [import, {provider}]
aliases: []
created_at: {created}
updated_at: {created}
confidence: 0.4
sensitivity: internal
source:
  kind: import
  ref: {yaml_source_ref}
  fingerprint: "{digest}"
pin: false
decay: fast
review_after: {review_after}
---

# {display_title}

Provider: `{provider}`

Source file: `{source_display}`

This is an imported review candidate. Promote only durable, non-secret facts after human review.

## Excerpt

{fence}text
{excerpt}
{fence}
"""


def import_candidate_path(root: Path, provider: str, source_file: Path, text: str, fingerprint: str | None = None) -> Path:
    digest = fingerprint or hashlib.sha256((str(source_file) + "\n" + text).encode("utf-8")).hexdigest()[:12]
    slug = slugify(source_file.stem, "chat")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    inbox = root / "inbox" / "imports" / provider
    return inbox / f"{timestamp}_{slug}_{digest}.md"


def safe_import_dir(root: Path, provider: str) -> Path:
    root = root.resolve()
    inbox = root / "inbox"
    imports = inbox / "imports"
    capture_dir = imports / provider
    for component in (inbox, imports, capture_dir):
        if component.is_symlink():
            raise ValueError("import path must not contain symlinks")
        if component.exists():
            try:
                component.resolve().relative_to(root)
            except ValueError as exc:
                raise ValueError("import path must stay inside the memory root") from exc

    capture_dir.mkdir(parents=True, exist_ok=True)
    for component in (inbox, imports, capture_dir):
        if component.is_symlink():
            raise ValueError("import path must not contain symlinks")
        try:
            component.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("import path must stay inside the memory root") from exc
    return capture_dir


def write_import_candidate(root: Path, provider: str, source_file: Path, text: str, fingerprint: str | None = None) -> Path:
    path = safe_import_dir(root, provider) / import_candidate_path(root, provider, source_file, text, fingerprint).name
    if path.exists() or path.is_symlink():
        raise ValueError("import candidate path already exists")
    safe_write_text(path, text, root=root, overwrite=False)
    return path


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect", help="Detect known provider directories.", allow_abbrev=False)
    detect.add_argument("--json", action="store_true", help="Emit JSON output.")

    plan = subparsers.add_parser(
        "plan",
        help="Show reviewed provider setup commands without mutating config.",
        allow_abbrev=False,
    )
    plan.add_argument(
        "--command",
        dest="cli_command",
        default="ai-dememory",
        help="CLI command to include in generated command arrays.",
    )
    plan.add_argument("--json", action="store_true", help="Emit JSON output.")

    configure = subparsers.add_parser(
        "configure", help="Configure a provider import source.", allow_abbrev=False
    )
    configure.add_argument("provider", choices=sorted(default_provider_paths()))
    configure.add_argument("--path", required=True, help="Provider chat/session directory.")
    configure.add_argument("--disable", action="store_true", help="Store the provider as disabled.")
    configure.add_argument("--dry-run", action="store_true", help="Preview config without writing .ai-dememory.toml.")
    configure.add_argument("--json", action="store_true", help="Emit JSON output.")

    import_cmd = subparsers.add_parser(
        "import", help="Import provider files into inbox/imports/.", allow_abbrev=False
    )
    import_cmd.add_argument("provider", choices=sorted(default_provider_paths()))
    import_cmd.add_argument("--path", default=None, help="Override provider path for this run.")
    import_cmd.add_argument("--limit", type=int, default=None, help="Maximum new candidates; defaults to the intensity profile.")
    import_cmd.add_argument(
        "--scan-limit",
        type=int,
        default=None,
        help="Maximum filesystem entries to inspect; defaults to the intensity profile.",
    )
    import_cmd.add_argument("--dry-run", action="store_true", help="Preview import candidates without writing inbox files.")
    import_cmd.add_argument("--json", action="store_true", help="Emit JSON output.")

    capture_cmd = subparsers.add_parser(
        "capture", help="Capture explicit files or text into inbox/imports/.", allow_abbrev=False
    )
    capture_cmd.add_argument("kind", choices=sorted(CAPTURE_KINDS))
    capture_source_group = capture_cmd.add_mutually_exclusive_group(required=True)
    capture_source_group.add_argument("--path", help="File or directory to capture.")
    capture_source_group.add_argument("--text", help="Text to capture.")
    capture_source_group.add_argument("--stdin", action="store_true", help="Read capture text from stdin.")
    capture_cmd.add_argument("--title", default=None, help="Title for text/stdin captures.")
    capture_cmd.add_argument("--limit", type=int, default=MAX_FILES)
    capture_cmd.add_argument("--json", action="store_true", help="Emit JSON output.")

    reject_duplicate_options(parser, argv, ("--root",))
    args = parser.parse_args(argv)
    root_was_supplied = any(argument == "--root" or argument.startswith("--root=") for argument in argv)
    if root_was_supplied and (not args.root or not args.root.strip()):
        parser.error("--root requires a non-empty vault path")
    explicit_root = args.root if args.root and args.root.strip() else None
    configured_root = os.environ.get("AI_DEMEMORY_ROOT")
    configured_root = configured_root if configured_root and configured_root.strip() else None
    mutates_vault = args.command == "capture" or (
        args.command in {"configure", "import"} and not args.dry_run
    )
    emits_bound_command = args.command == "plan" or (
        args.command == "configure" and args.dry_run
    )
    if (
        (mutates_vault or emits_bound_command)
        and not explicit_root
        and not configured_root
    ):
        parser.error(
            f"provider {args.command} requires an explicit vault binding; "
            "pass --root <vault-path> or set AI_DEMEMORY_ROOT"
        )
    root = repo_root(explicit_root)

    if args.command == "detect":
        candidates = detect_providers(root)
        if args.json:
            print(json.dumps([asdict(candidate) for candidate in candidates], indent=2))
        else:
            for candidate in candidates:
                marker = "enabled" if candidate.enabled else "disabled"
                exists = "exists" if candidate.exists else "missing"
                print(f"{candidate.name:<10} {marker:<8} {exists:<7} {candidate.path}")
        return 0

    if args.command == "plan":
        plan_result = provider_setup_plan(root, command=args.cli_command)
        if args.json:
            print(json.dumps(plan_result, indent=2))
        else:
            print("Provider setup plan")
            print("Package install does not configure providers or import chats.")
            for provider in plan_result["providers"]:
                marker = provider["reason"]
                print(f"- {provider['name']}: {marker} ({provider['path']})")
                print(
                    "  preview: "
                    + render_copy_command(provider["configure_dry_run_command"])
                )
                print(
                    "  configure: "
                    + render_copy_command(provider["configure_command"])
                )
                if provider["import_ready"]:
                    print("  import: " + render_copy_command(provider["import_command"]))
            print("Next: review paths, configure chosen providers, then import manually or through opt-in maintenance.")
        return 0

    if args.command == "configure":
        if args.dry_run:
            preview = configure_provider_preview(root, args.provider, Path(args.path), enabled=not args.disable)
            if args.json:
                print(json.dumps(preview, indent=2))
            else:
                state = "disabled" if args.disable else "enabled"
                print(f"Would configure {args.provider} as {state}.")
                print(f"Path: {preview['path']}")
                print(f"Path exists: {str(preview['path_exists']).lower()}")
                print(f"Config: {preview['config_path']} [{preview['section']}]")
            return 0
        configure_provider(root, args.provider, Path(args.path), enabled=not args.disable)
        state = "disabled" if args.disable else "enabled"
        print(f"Configured {args.provider} as {state}.")
        return 0

    if args.command == "import":
        try:
            result = import_chats(
                root,
                args.provider,
                source_path=Path(args.path) if args.path else None,
                limit=args.limit,
                max_scan_entries=args.scan_limit,
                dry_run=args.dry_run,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["dry_run"]:
                print(
                    f"Would import {len(result['would_write'])} candidate(s) from {result['provider']} "
                    f"into inbox/imports/{result['provider']}/."
                )
                return 0
            print(
                f"Imported {len(result['written'])} candidate(s) from {result['provider']} "
                f"into inbox/imports/{result['provider']}/."
            )
            if result["skipped"]:
                print(f"Skipped {len(result['skipped'])} file(s).")
        return 0

    if args.command == "capture":
        try:
            capture_text = sys.stdin.read() if args.stdin else args.text
            result = capture_source(
                root,
                args.kind,
                source_path=Path(args.path) if args.path else None,
                text=capture_text,
                title=args.title,
                limit=args.limit,
            )
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(
                f"Captured {len(result['written'])} candidate(s) from {result['kind']} "
                f"into inbox/imports/{result['kind']}/."
            )
            if result["skipped"]:
                print(f"Skipped {len(result['skipped'])} item(s).")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
