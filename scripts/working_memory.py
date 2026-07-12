#!/usr/bin/env python3
"""Capture current working memory snapshots and handoffs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from memorylib import contained_relative_path, logical_relative_path, repo_relative_path, repo_root, slugify
from secret_scan import scan_text


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def snapshot(root: Path, title: str, notes: str, task: str | None = None) -> Path:
    payload = {
        "title": title,
        "task": task,
        "notes": notes,
        "updated_at": now_iso(),
    }
    rendered = json.dumps(payload, indent=2)
    if scan_text(rendered, "<working.snapshot>"):
        raise ValueError("working snapshot rejected by secret scan")
    path = root / "working" / "current.json"
    reject_working_path_symlink_components(root, path, "working snapshot path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n", encoding="utf-8")
    recent = root / "working" / "recent-session.md"
    reject_working_path_symlink_components(root, recent, "working recent-session path")
    recent.write_text(render_recent(payload), encoding="utf-8")
    return path


def handoff(root: Path, title: str, notes: str) -> Path:
    if scan_text(f"{title}\n{notes}", "<working.handoff>"):
        raise ValueError("handoff rejected by secret scan")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = root / "working" / "handoffs" / f"{timestamp}_{slugify(title, 'handoff')}.md"
    reject_working_path_symlink_components(root, path, "working handoff path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {title}\n\nGenerated at: `{now_iso()}`\n\n{notes.strip()}\n",
        encoding="utf-8",
    )
    return path


def reject_working_path_symlink_components(root: Path, target: Path, label: str) -> None:
    root_abs = Path(os.path.abspath(root))
    try:
        rel = logical_relative_path(target, root_abs)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the memory root") from exc
    current = root_abs
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} must not contain symlinks")
    try:
        contained_relative_path(target, root_abs)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the memory root") from exc


def render_recent(payload: dict[str, Any]) -> str:
    task = payload.get("task") or "none"
    return f"""# Recent Session

- title: `{payload['title']}`
- task: `{task}`
- updated_at: `{payload['updated_at']}`

{payload['notes']}
"""


def show_current(root: Path) -> str:
    path = root / "working" / "current.json"
    if not path.exists():
        return "{}"
    reject_working_path_symlink_components(root, path, "working current path")
    return path.read_text(encoding="utf-8")


def working_status(root: Path, limit: int = 5) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    current_path = root / "working" / "current.json"
    recent_path = root / "working" / "recent-session.md"
    current: dict[str, Any] = {}
    if current_path.exists():
        try:
            reject_working_path_symlink_components(root, current_path, "working current path")
            current = json.loads(current_path.read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError):
            current = {}

    handoff_dir = root / "working" / "handoffs"
    handoff_dir_safe = False
    if handoff_dir.exists():
        try:
            reject_working_path_symlink_components(root, handoff_dir, "working handoff directory")
            handoff_dir_safe = True
        except ValueError:
            handoff_dir_safe = False
    handoff_paths = (
        [
            path
            for path in sorted(handoff_dir.glob("*.md"), reverse=True)
            if path.name.lower() != "readme.md" and working_path_is_safe(root, path)
        ]
        if handoff_dir_safe
        else []
    )
    handoffs = [handoff_summary(root, path) for path in handoff_paths[:limit]]
    return {
        "current_exists": bool(current),
        "current_path": repo_relative_path(current_path, root) if current else None,
        "current": current,
        "recent_session_exists": recent_path.exists() and working_path_is_safe(root, recent_path),
        "recent_session_path": repo_relative_path(recent_path, root)
        if recent_path.exists() and working_path_is_safe(root, recent_path)
        else None,
        "handoff_count": len(handoff_paths),
        "handoffs": handoffs,
    }


def handoff_summary(root: Path, path: Path) -> dict[str, Any]:
    try:
        reject_working_path_symlink_components(root, path, "working handoff path")
        text = path.read_text(encoding="utf-8")
    except (ValueError, OSError):
        text = ""
    title = path.stem
    generated_at = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("Generated at:"):
            generated_at = line.replace("Generated at:", "", 1).strip().strip("`")
    return {
        "path": repo_relative_path(path, root),
        "title": title,
        "generated_at": generated_at,
    }


def working_path_is_safe(root: Path, path: Path) -> bool:
    try:
        reject_working_path_symlink_components(root, path, "working path")
    except ValueError:
        return False
    return True


def read_notes(value: str | None) -> str:
    if value:
        return value
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    snap = subparsers.add_parser("snapshot", help="Write working/current.json and recent-session.md.")
    snap.add_argument("--title", required=True)
    snap.add_argument("--task", default=None)
    snap.add_argument("--notes", default=None)
    current = subparsers.add_parser("current", help="Print working/current.json.")
    current.add_argument("--json", action="store_true")
    status = subparsers.add_parser("status", help="Summarize current working state and recent handoffs.")
    status.add_argument("--limit", type=int, default=5, help="Maximum handoffs to list.")
    status.add_argument("--json", action="store_true")
    ho = subparsers.add_parser("handoff", help="Write a handoff markdown file.")
    ho.add_argument("--title", required=True)
    ho.add_argument("--notes", default=None)

    args = parser.parse_args(argv)
    root = repo_root(args.root)
    try:
        if args.command == "snapshot":
            path = snapshot(root, args.title, read_notes(args.notes), task=args.task)
            print(f"Wrote {repo_relative_path(path, root)}")
            return 0
        if args.command == "current":
            print(show_current(root))
            return 0
        if args.command == "status":
            result = working_status(root, limit=args.limit)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print_status(result)
            return 0
        if args.command == "handoff":
            path = handoff(root, args.title, read_notes(args.notes))
            print(f"Wrote {repo_relative_path(path, root)}")
            return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 2


def print_status(status: dict[str, Any]) -> None:
    print(f"Current working state: {'present' if status['current_exists'] else 'missing'}")
    if status["current_path"]:
        print(f"- current: {status['current_path']}")
    print(f"Recent session: {'present' if status['recent_session_exists'] else 'missing'}")
    if status["recent_session_path"]:
        print(f"- recent: {status['recent_session_path']}")
    print(f"Handoffs: {status['handoff_count']}")
    for handoff_item in status["handoffs"]:
        generated = f" ({handoff_item['generated_at']})" if handoff_item.get("generated_at") else ""
        print(f"- {handoff_item['path']}: {handoff_item['title']}{generated}")


if __name__ == "__main__":
    raise SystemExit(main())
