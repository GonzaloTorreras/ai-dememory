"""Read explicit local conversation exports without importing or changing them."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import time
from collections import deque
from itertools import islice
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .policy import UnsafeContentError, reject_high_confidence_secrets

FORMATS = ("codex", "claude", "pi", "dsh", "hermes", "generic")
MAX_FILES = 100
MAX_DEPTH = 4
MAX_ENTRIES = 5_000
MAX_FILE_BYTES = 2_000_000
MAX_DATABASE_BYTES = 256_000_000
MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 24_000
_DSH_GENERATION = re.compile(r"session\.v(\d+)\.jsonl(?:\.zstd)?$")


def _format(value: str) -> str:
    if value not in FORMATS:
        raise ValueError("format must be codex, claude, pi, dsh, hermes or generic")
    return value


def _is_link(path: Path, info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _root(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Choose an explicit absolute conversation directory")
    try:
        for component in (*reversed(path.parents), path):
            if _is_link(component, component.lstat()):
                raise ValueError("Conversation paths cannot contain symbolic links or junctions")
        if not path.is_dir():
            raise ValueError("Conversation root must be an existing directory")
        return path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Cannot access the selected conversation directory") from exc


def _suffixes(format: str) -> set[str]:
    return {".db", ".sqlite", ".sqlite3"} if format == "hermes" else {".json", ".jsonl"}


def _file(root: Path, relative: str, format: str) -> tuple[Path, os.stat_result]:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Select a relative conversation filename")
    path = Path(relative)
    if path.is_absolute() or path.drive or ".." in path.parts or len(path.parts) > MAX_DEPTH + 1:
        raise ValueError("Conversation file must remain inside the selected root and depth limit")
    if path.suffix.lower() not in _suffixes(format):
        raise ValueError("Choose a Hermes SQLite snapshot or a supported plain JSON/JSONL export")
    candidate = root
    try:
        for part in path.parts:
            candidate /= part
            info = candidate.lstat()
            if _is_link(candidate, info):
                raise ValueError("Conversation paths cannot contain symbolic links or junctions")
        candidate.resolve(strict=True).relative_to(root)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Conversation source must be a regular file")
        limit = MAX_DATABASE_BYTES if format in ("hermes", "codex") else MAX_FILE_BYTES
        if info.st_size > limit:
            raise ValueError(f"Conversation file exceeds the {limit // 1_000_000} MB preview limit; export a smaller selection")
        return candidate, info
    except OSError as exc:
        raise ValueError("Cannot access the selected conversation file") from exc


def list_sources(root: Path, format: str, *, after: str | None = None) -> dict[str, Any]:
    """List at most 100 eligible files under an explicitly selected directory."""
    selected_format = _format(format)
    if after is not None and (selected_format != "codex" or not isinstance(after, str)):
        raise ValueError("History pages are available for Codex only")
    root = _root(root)
    files: list[dict[str, Any]] = []
    pending = deque([(root, 0)])
    scanned = 0
    discarded = 0
    truncated = False
    exhausted = False
    generations: dict[str, int] = {}
    notices: set[str] = set()
    while pending and not exhausted:
        directory, depth = pending.popleft()
        try:
            _root(directory).relative_to(root)
            with os.scandir(directory) as entries:
                ordered = sorted(islice(entries, MAX_ENTRIES + 1), key=lambda entry: entry.name, reverse=True)
                for entry in ordered:
                    scanned += 1
                    if scanned > MAX_ENTRIES:
                        truncated = True
                        exhausted = True
                        break
                    info = entry.stat(follow_symlinks=False)
                    path = Path(entry.path)
                    if _is_link(path, info):
                        discarded += 1
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        if depth < MAX_DEPTH:
                            pending.append((path, depth + 1))
                        else:
                            truncated = True
                        continue
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    if selected_format == "dsh" and (generation := _DSH_GENERATION.fullmatch(path.name)):
                        directory_key = path.parent.relative_to(root).as_posix()
                        generations[directory_key] = max(generations.get(directory_key, -1), int(generation[1]))
                        if path.suffix == ".zstd":
                            notices.add("DSH .zstd sessions need a plain JSONL export; compressed sessions are not supported.")
                    if path.suffix.lower() not in _suffixes(selected_format):
                        continue
                    limit = MAX_DATABASE_BYTES if selected_format in ("hermes", "codex") else MAX_FILE_BYTES
                    if info.st_size > limit:
                        discarded += 1
                        continue
                    relative = path.relative_to(root).as_posix()
                    try:
                        reject_high_confidence_secrets(relative)
                    except UnsafeContentError:
                        discarded += 1
                        continue
                    item = {"path": relative, "bytes": info.st_size, "modified_at": info.st_mtime}
                    if selected_format == "hermes":
                        try:
                            sessions, limited = _hermes_sessions(path)
                            truncated = truncated or limited
                        except ValueError as exc:
                            discarded += 1
                            notices.add(str(exc))
                            continue
                        for session in sessions:
                            if len(files) >= MAX_FILES:
                                truncated = exhausted = True
                                break
                            files.append({**item, **session})
                    else:
                        files.append(item)
        except (OSError, ValueError):
            discarded += 1
    if selected_format == "dsh":
        files = [item for item in files if not (generation := _DSH_GENERATION.fullmatch(Path(item["path"]).name))
                 or int(generation[1]) == generations[Path(item["path"]).parent.as_posix()]]
    files.sort(key=lambda item: (-item["modified_at"], item["path"], -item.get("latest_message_id", 0)))
    scan_limited = truncated
    if after is not None:
        files = sorted((item for item in files if item["path"] > after and item["path"].endswith(".jsonl")),
                       key=lambda item: item["path"])
    if selected_format == "codex":
        titles = _codex_titles(root)
        visible = []
        for item in files:
            metadata = _codex_metadata(root / item["path"])
            if metadata.pop("internal", False):
                discarded += 1
                continue
            item.update(metadata)
            if item.get("conversation_id") in titles:
                item["title"] = titles[item["conversation_id"]]
            visible.append(item)
            if len(visible) >= MAX_FILES:
                break
        truncated = truncated or (len(visible) >= MAX_FILES and len(files) > MAX_FILES)
        files = visible
        notices.add("Codex internal/subagent sessions are excluded. Titles use the local index when available; otherwise a bounded first-message excerpt. Large logs preview only their latest window.")
    truncated = truncated or len(files) > MAX_FILES
    files = files[:MAX_FILES]
    return {"format": selected_format, "files": files, "truncated": truncated,
            "scan_limited": scan_limited,
            "scanned_entries": min(scanned, MAX_ENTRIES), "discarded_files": discarded,
            "notices": sorted(notices)}


def _safe_label(value, limit=160):
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    try:
        reject_high_confidence_secrets(text)
    except UnsafeContentError:
        return ""
    return text[:limit]


def _codex_metadata(path):
    result = {}
    try:
        with path.open("rb") as stream:
            first = stream.readline(524_289)
            if len(first) > 524_288:
                return {"internal":True}  # Cannot verify provenance within the metadata budget.
            head = (first + stream.read(65_536)).decode("utf-8", errors="replace")
        try:
            json.loads(first)
        except ValueError:
            return {"internal":True}
        for line in head.splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            payload = record.get("payload", {}) if isinstance(record, dict) else {}
            if record.get("type") == "session_meta" and isinstance(payload, dict):
                source = payload.get("source", "")
                result["internal"] = (isinstance(source, dict) and "subagent" in source) or str(source).lower().startswith("subagent")
                result["conversation_id"] = _safe_label(payload.get("id") or payload.get("session_id"), 128)
                result["workspace"] = _safe_label(payload.get("cwd"), 512)
                result["origin"] = _safe_label(source)
            found = _user_message(record, "codex")
            if found and not _synthetic(found[0]) and not result.get("title"):
                result["title"] = _safe_label(found[0])
    except OSError:
        pass
    return result


def _codex_titles(root):
    # Explicit sessions-root selection authorizes its adjacent title index only.
    if root.name != "sessions":
        return {}
    index = root.parent / "session_index.jsonl"
    if not index.is_file() or _is_link(index, index.lstat()):
        return {}
    titles = {}
    try:
        with index.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(max(0, size - MAX_FILE_BYTES))
            if size > MAX_FILE_BYTES:
                stream.readline()
            lines = stream.read(MAX_FILE_BYTES).decode("utf-8", errors="replace").splitlines()
        for line in lines:
            try:
                row = json.loads(line)
                title = _safe_label(row.get("thread_name"))
                if isinstance(row.get("id"), str) and title:
                    titles[row["id"]] = title
            except (ValueError, AttributeError):
                continue
    except OSError:
        pass
    return titles


def _synthetic(text):
    return text.lstrip().startswith(("The following is the Codex agent history", "# AGENTS.md instructions",
                                    "<environment_context>", "<permissions instructions>", "<subagent_notification>",
                                    "You are a reviewer", "You are reviewing a proposed"))


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(block["text"].strip() for block in content
                         if isinstance(block, dict) and block.get("type") in {"text", "input_text"}
                         and isinstance(block.get("text"), str) and block["text"].strip())
    return ""


def _user_message(record: Any, format: str) -> tuple[str, str] | None:
    if not isinstance(record, dict):
        return None
    kind = "message"
    message = record
    if format == "codex":
        payload = record.get("payload")
        if not isinstance(payload, dict):
            return None
        kind = record.get("type", "")
        if kind == "event_msg" and payload.get("type") == "user_message":
            return _text(payload.get("message")), kind
        if kind != "response_item" or payload.get("type") != "message":
            return None
        message = payload
    elif format == "claude":
        if record.get("type") != "user":
            return None
        message = record.get("message")
    elif format == "pi":
        if record.get("type") != "message":
            return None
        message = record.get("message")
    elif format == "dsh":
        message = record.get("data")
        if (record.get("type") != "user/message" or not isinstance(message, dict)
                or not isinstance(message.get("source"), dict) or message["source"].get("kind") != "user"):
            return None
    if not isinstance(message, dict) or message.get("role") != "user":
        return None
    return _text(message.get("content")), kind


def _records(text: str, suffix: str) -> tuple[list[Any], int]:
    if suffix == ".jsonl":
        records = []
        malformed = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except (ValueError, RecursionError):
                malformed += 1
        return records, malformed
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Conversation export is not valid JSON") from exc
    if isinstance(data, list):
        return data, 0
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"], 0
    return [data], 0


@contextmanager
def _hermes_connection(path: Path):
    """Read-only official Hermes schema; never create SQLite sidecars."""
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("Hermes has an active WAL. Select a checkpointed database snapshot or a generic JSON export; live WAL reading is not supported")
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=0)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        if hasattr(connection, "enable_load_extension"):
            connection.enable_load_extension(False)
        deadline = time.monotonic() + 0.25
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_FILE_BYTES)
        table = connection.execute("SELECT type FROM sqlite_master WHERE name='messages'").fetchone()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
        if table != ("table",) or not {"id", "session_id", "role", "content", "timestamp"} <= columns:
            raise ValueError("Selected database does not have the supported Hermes messages schema")
        filters = ["role='user'", "length(CAST(session_id AS BLOB)) BETWEEN 1 AND 256"]
        if "active" in columns:
            filters.append("active=1")
        if "_compressed_summary" in columns:
            filters.append("_compressed_summary=0")
        yield connection, " AND ".join(filters)
        if wal.exists() and wal.stat().st_size:
            raise ValueError("Hermes changed during preview. Select a checkpointed database snapshot or a generic JSON export")
    except (sqlite3.Error, OSError) as exc:
        raise ValueError("Cannot preview this Hermes snapshot within the read-only query limits") from exc
    finally:
        if connection is not None:
            connection.close()


def _hermes_sessions(path: Path) -> tuple[list[dict[str, Any]], bool]:
    with _hermes_connection(path) as (connection, filters):
        rows = connection.execute(
            "SELECT session_id, id FROM messages WHERE " + filters + " ORDER BY id DESC LIMIT 1001"
        ).fetchall()
    sessions = []
    seen = set()
    limited = len(rows) > 1000
    for session_id, latest in rows[:1000]:
        if not isinstance(session_id, str) or session_id in seen:
            continue
        try:
            reject_high_confidence_secrets(session_id)
        except UnsafeContentError:
            continue
        seen.add(session_id)
        if len(sessions) >= MAX_FILES:
            limited = True
            break
        sessions.append({"session_id": session_id, "latest_message_id": latest})
    return sessions, limited


def _hermes_snapshot(path: Path, session_id: str | None) -> tuple[list[Any], int, bool, str | None]:
    records = []
    malformed = 0
    with _hermes_connection(path) as (connection, filters):
        if session_id is None:
            latest = connection.execute("SELECT session_id FROM messages WHERE " + filters + " ORDER BY id DESC LIMIT 1").fetchone()
            session_id = latest[0] if latest else None
        if session_id is not None:
            if not isinstance(session_id, str) or not 1 <= len(session_id.encode("utf-8")) <= 256:
                raise ValueError("Choose a valid Hermes session id")
            reject_high_confidence_secrets(session_id)
        query = ("SELECT CASE WHEN length(CAST(content AS BLOB)) <= ? THEN content ELSE NULL END "
                 "FROM messages WHERE " + filters + " AND session_id=? ORDER BY id DESC LIMIT 101")
        rows = connection.execute(query, (MAX_MESSAGE_CHARS, session_id)).fetchall()
        for row in reversed(rows[:100]):
            content = row[0]
            if content is None:
                records.append({"_source_oversize": True})
                continue
            if isinstance(content, str) and content.startswith("\x00json:"):
                try:
                    content = json.loads(content[6:])
                except (ValueError, RecursionError):
                    malformed += 1
                    continue
            records.append({"role": "user", "content": content})
    return records, malformed, len(rows) > 100, session_id


def _pi_branch(records: list[Any]) -> list[Any]:
    entries = {}
    leaf = None
    for record in records:
        if isinstance(record, dict) and record.get("type") == "session":
            continue
        if (not isinstance(record, dict) or not isinstance(record.get("id"), str)
                or not record["id"] or "parentId" not in record
                or (record["parentId"] is not None and not isinstance(record["parentId"], str))
                or record["id"] in entries):
            raise ValueError("Pi export has malformed or duplicate branch entries")
        entries[record["id"]] = record
        leaf = record["id"]
    branch = []
    visited = set()
    while leaf is not None:
        if leaf in visited or leaf not in entries:
            raise ValueError("Pi export has an unresolved or cyclic active branch")
        visited.add(leaf)
        branch.append(entries[leaf])
        leaf = entries[leaf]["parentId"]
    return list(reversed(branch))


def _check_dsh_generation(path: Path) -> None:
    generation = _DSH_GENERATION.fullmatch(path.name)
    if not generation:
        return
    with os.scandir(path.parent) as entries:
        for index, entry in enumerate(entries):
            if index >= MAX_ENTRIES:
                raise ValueError("DSH generation check reached its directory limit")
            other = _DSH_GENERATION.fullmatch(entry.name)
            if other and int(other[1]) > int(generation[1]):
                raise ValueError("Select the latest DSH session generation; export it as plain JSONL if compressed")


def preview_source(root: Path, relative: str, format: str, session_id: str | None = None) -> dict[str, Any]:
    """Return bounded user text only. No model calls, imports or file writes occur."""
    selected_format = _format(format)
    root = _root(root)
    path, expected = _file(root, relative, selected_format)
    if selected_format == "codex" and _codex_metadata(path).get("internal"):
        raise ValueError("Internal Codex/subagent sessions are not human conversation sources")
    window_limited = False
    discarded_branch = 0
    if selected_format == "hermes":
        records, malformed, window_limited, session_id = _hermes_snapshot(path, session_id)
    else:
        if session_id is not None:
            raise ValueError("session_id applies only to Hermes snapshots")
        if selected_format == "dsh":
            _check_dsh_generation(path)
        records, malformed = _read_json(path, expected, tail=selected_format == "codex")
        window_limited = selected_format == "codex" and expected.st_size > MAX_FILE_BYTES
        if selected_format == "pi":
            if malformed:
                raise ValueError("Pi export has malformed records; active branch cannot be verified")
            branch = _pi_branch(records)
            discarded_branch = sum(1 for record in records if isinstance(record, dict) and record.get("type") != "session") - len(branch)
            records = branch
    result = _preview_messages(path.relative_to(root).as_posix(), selected_format, records,
                               malformed, window_limited)
    if selected_format == "hermes":
        result["session_id"] = session_id
    if selected_format == "pi":
        result["counts"]["discarded_branch"] = discarded_branch
    return result


def _read_json(path: Path, expected: os.stat_result, tail=False) -> tuple[list[Any], int]:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            actual = os.fstat(handle.fileno())
            if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                raise ValueError("Conversation file changed during selection; select it again")
            if tail and actual.st_size > MAX_FILE_BYTES:
                handle.seek(actual.st_size - MAX_FILE_BYTES)
                handle.readline(MAX_FILE_BYTES)
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Conversation file exceeds the 2 MB preview limit; export a smaller selection")
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ValueError("Cannot read conversation export as UTF-8") from exc
    return _records(text, path.suffix.lower())


def _preview_messages(relative: str, selected_format: str, records: list[Any], malformed: int,
                      window_limited: bool) -> dict[str, Any]:
    counts = {"records": len(records) + malformed, "malformed_records": malformed,
              "discarded_non_user": 0, "discarded_empty": 0, "discarded_sensitive": 0,
              "discarded_duplicate": 0, "discarded_limit": 0, "discarded_internal": 0}
    candidates: list[tuple[str, str, int]] = []
    native_events = selected_format == "codex" and any(
        isinstance(row, dict) and row.get("type") == "event_msg" and isinstance(row.get("payload"), dict)
        and row["payload"].get("type") == "user_message" for row in records)
    for index, record in enumerate(records):
        if isinstance(record, dict) and record.get("_source_oversize") is True:
            counts["discarded_limit"] += 1
            continue
        found = _user_message(record, selected_format)
        if found is None:
            counts["discarded_non_user"] += 1
            continue
        content, kind = found
        if native_events and kind == "response_item":
            counts["discarded_duplicate"] += 1
            continue
        if selected_format == "codex" and _synthetic(content):
            counts["discarded_internal"] += 1
            continue
        if not content:
            counts["discarded_empty"] += 1
            continue
        try:
            reject_high_confidence_secrets(content)
        except UnsafeContentError:
            counts["discarded_sensitive"] += 1
            continue
        if (selected_format == "codex" and candidates and candidates[-1][0] == content
                and candidates[-1][2] == index - 1
                and {candidates[-1][1], kind} == {"response_item", "event_msg"}):
            counts["discarded_duplicate"] += 1
            candidates.pop()
            candidates.append((content, "paired", index))
            continue
        candidates.append((content, kind, index))
    messages = []
    characters = 0
    for content, _, _ in reversed(candidates):
        if len(messages) >= MAX_MESSAGES or characters + len(content) > MAX_MESSAGE_CHARS:
            counts["discarded_limit"] += 1
            continue
        messages.append({"role": "user", "content": content})
        characters += len(content)
    messages.reverse()
    counts.update({"returned_messages": len(messages), "returned_characters": characters})
    result = {"path": relative, "format": selected_format,
              "messages": messages, "counts": counts, "truncated": window_limited or bool(counts["discarded_limit"])}
    if selected_format == "hermes":
        result["notice"] = "Checkpointed Hermes snapshot: latest 100 active user rows only; live WAL databases and compressed summaries are excluded."
    if selected_format == "dsh":
        result["notice"] = "Plain DSH JSONL export only; compressed .zstd sessions are not supported."
    return result
