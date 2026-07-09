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
import sys
from typing import Any

from config_file import CONFIG_NAME, load_config, set_section
from memorylib import repo_relative_path, repo_root, slugify
from secret_scan import scan_text


CHAT_SUFFIXES = {".jsonl", ".json", ".md", ".txt", ".log"}
SKIP_PARTS = {"Cache", "Code Cache", "GPUCache", "__pycache__", "node_modules", ".git"}
MAX_FILE_BYTES = 64 * 1024
MAX_EXPORT_BYTES = 2 * 1024 * 1024
MAX_FILES = 20
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
    providers: list[dict[str, Any]] = []
    for candidate in detect_providers(root):
        reason, next_action = provider_plan_reason(candidate)
        configure_command = [command, "providers", "configure", candidate.name, "--path", candidate.path]
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
                "import_dry_run_command": [command, "import-chats", candidate.name, "--dry-run", "--json"],
                "import_command": [command, "import-chats", candidate.name],
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
        "configure_command": ["ai-dememory", "providers", "configure", name, "--path", str(normalized)]
        + ([] if enabled else ["--disable"]),
        "next_action": "Run configure without --dry-run after reviewing the provider path.",
    }


def configured_import_path(root: Path, provider: str, source_path: Path | None) -> Path:
    if source_path is not None:
        return source_path.expanduser().resolve()
    config = provider_config(root).get(provider)
    if not config:
        raise ValueError(f"provider {provider} is not configured")
    if not config.get("enabled", False):
        raise ValueError(f"provider {provider} is disabled")
    path = str(config.get("path") or "").strip()
    if not path:
        raise ValueError(f"provider {provider} has no path")
    return Path(path).expanduser().resolve()


def import_chats(
    root: Path,
    provider: str,
    source_path: Path | None = None,
    limit: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
    dry_run: bool = False,
) -> dict[str, Any]:
    if provider not in default_provider_paths():
        raise ValueError(f"unknown provider: {provider}")
    source_root = configured_import_path(root, provider, source_path)
    if not source_root.exists():
        raise FileNotFoundError(f"provider path does not exist: {source_root}")

    files = discover_chat_files(source_root, limit)
    written: list[str] = []
    would_write: list[str] = []
    skipped: list[dict[str, str]] = []
    for source_file in files:
        try:
            raw = source_file.read_bytes()[:max_file_bytes]
        except OSError as exc:
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
    return {
        "provider": provider,
        "source_path": str(source_root),
        "dry_run": dry_run,
        "reads_provider_files": True,
        "writes_import_candidates": not dry_run and bool(written),
        "examined": len(files),
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
        source_root = source_path.expanduser().resolve()
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


def discover_chat_files(source_root: Path, limit: int) -> list[Path]:
    if source_root.is_file():
        return [source_root]
    files = [
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in CHAT_SUFFIXES
        and not any(part in SKIP_PARTS for part in path.parts)
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[: max(1, limit)]


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
            raw = source_file.read_bytes()[:max_file_bytes]
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue
        text = raw.decode("utf-8", errors="replace").strip()
        title = f"{kind} capture {source_file.stem}"
        items.append(CaptureItem(title, str(source_file), text))
    return items


def extract_chatgpt_export(source_file: Path, limit: int = MAX_FILES) -> list[CaptureItem]:
    raw = source_file.read_bytes()
    if len(raw) > MAX_EXPORT_BYTES:
        raw = raw[:MAX_EXPORT_BYTES]
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
    return f"""---
id: import_{provider}_{now.strftime('%Y%m%d_%H%M%S')}_{digest}
title: "{title}"
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
  ref: "{source_ref.replace('"', "'")}"
  fingerprint: "{digest}"
pin: false
decay: fast
review_after: {review_after}
---

# {title}

Provider: `{provider}`

Source file: `{source_file}`

This is an imported review candidate. Promote only durable, non-secret facts after human review.

## Excerpt

```text
{excerpt}
```
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
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect", help="Detect known provider directories.")
    detect.add_argument("--json", action="store_true", help="Emit JSON output.")

    plan = subparsers.add_parser("plan", help="Show reviewed provider setup commands without mutating config.")
    plan.add_argument(
        "--command",
        dest="cli_command",
        default="ai-dememory",
        help="CLI command to include in generated command arrays.",
    )
    plan.add_argument("--json", action="store_true", help="Emit JSON output.")

    configure = subparsers.add_parser("configure", help="Configure a provider import source.")
    configure.add_argument("provider", choices=sorted(default_provider_paths()))
    configure.add_argument("--path", required=True, help="Provider chat/session directory.")
    configure.add_argument("--disable", action="store_true", help="Store the provider as disabled.")
    configure.add_argument("--dry-run", action="store_true", help="Preview config without writing .ai-dememory.toml.")
    configure.add_argument("--json", action="store_true", help="Emit JSON output.")

    import_cmd = subparsers.add_parser("import", help="Import provider files into inbox/imports/.")
    import_cmd.add_argument("provider", choices=sorted(default_provider_paths()))
    import_cmd.add_argument("--path", default=None, help="Override provider path for this run.")
    import_cmd.add_argument("--limit", type=int, default=MAX_FILES)
    import_cmd.add_argument("--dry-run", action="store_true", help="Preview import candidates without writing inbox files.")
    import_cmd.add_argument("--json", action="store_true", help="Emit JSON output.")

    capture_cmd = subparsers.add_parser("capture", help="Capture explicit files or text into inbox/imports/.")
    capture_cmd.add_argument("kind", choices=sorted(CAPTURE_KINDS))
    capture_source_group = capture_cmd.add_mutually_exclusive_group(required=True)
    capture_source_group.add_argument("--path", help="File or directory to capture.")
    capture_source_group.add_argument("--text", help="Text to capture.")
    capture_source_group.add_argument("--stdin", action="store_true", help="Read capture text from stdin.")
    capture_cmd.add_argument("--title", default=None, help="Title for text/stdin captures.")
    capture_cmd.add_argument("--limit", type=int, default=MAX_FILES)
    capture_cmd.add_argument("--json", action="store_true", help="Emit JSON output.")

    args = parser.parse_args(argv)
    root = repo_root(args.root)

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
                print(f"  preview: {' '.join(provider['configure_dry_run_command'])}")
                print(f"  configure: {' '.join(provider['configure_command'])}")
                if provider["import_ready"]:
                    print(f"  import: {' '.join(provider['import_command'])}")
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
