"""Forward-only Codex windows and durable metadata cursors; no copied transcripts."""

import hashlib
import json
import os
import stat
from contextlib import closing
from pathlib import Path

from .policy import UnsafeContentError, reject_high_confidence_secrets
from .providers import _database
from .sources import (_root, _file, _codex_metadata, _synthetic, _user_message,
                      MAX_FILE_BYTES, MAX_MESSAGES, MAX_MESSAGE_CHARS)


def read_window(root, relative, cursor=None):
    """Read complete native user events from one append-only JSONL window.

    Unlike the manual tail preview, stop BEFORE overflowing a message budget.
    The returned cursor is committed only after extraction succeeds.
    """
    root = _root(Path(root))
    path, expected = _file(root, relative, "codex")
    if path.suffix.lower() != ".jsonl":
        raise ValueError("Incremental history requires native Codex JSONL")
    metadata = _codex_metadata(path)
    if metadata.get("internal") or not metadata.get("conversation_id"):
        raise ValueError("Incremental history requires a human Codex session with an id")
    identity = f"{expected.st_dev}:{expected.st_ino}:{metadata['conversation_id']}"
    cursor = cursor or {"offset": 0, "identity": identity}
    start = cursor["offset"]
    limit = cursor.get("pending_end", expected.st_size)
    if cursor["identity"] != identity or expected.st_size < max(start, limit):
        raise ValueError("Source replaced or truncated; select a new schedule for the changed export")
    messages, characters = [], 0
    counts = {"malformed": 0, "sensitive": 0, "oversize": 0, "ignored": 0}
    partial = False
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise ValueError("Conversation changed during selection")
        stream.seek(start)
        offset = start
        while offset - start < MAX_FILE_BYTES:
            position = stream.tell()
            raw = stream.readline(min(MAX_FILE_BYTES - (position - start), limit - position))
            if not raw:
                break
            if not raw.endswith(b"\n"):
                partial = stream.tell() >= limit
                if not partial and position == start:
                    raise ValueError("A history record exceeds the 2 MB scan limit; use a smaller export")
                break  # Never consume a partially written line, even if it parses.
            try:
                record = json.loads(raw.decode("utf-8-sig"))
            except (ValueError, UnicodeError, RecursionError):
                counts["malformed"] += 1
                offset = stream.tell()
                continue
            found = _user_message(record, "codex")
            if not found or found[1] != "event_msg" or not found[0] or _synthetic(found[0]):
                counts["ignored"] += 1
            else:
                content = found[0]
                try:
                    reject_high_confidence_secrets(content)
                except UnsafeContentError:
                    counts["sensitive"] += 1
                else:
                    if len(content) > MAX_MESSAGE_CHARS:
                        counts["oversize"] += 1
                    elif len(messages) >= MAX_MESSAGES or characters + len(content) > MAX_MESSAGE_CHARS:
                        break  # This complete message belongs to the next window.
                    else:
                        messages.append({"role": "user", "content": content})
                        characters += len(content)
            offset = stream.tell()
    return {"messages": messages, "cursor": {"identity": identity, "offset": offset},
            "start": start, "bytes_remaining": max(0, expected.st_size - offset),
            "waiting_for_newline": partial, "counts": counts}


def _connect(vault):
    db = _database(vault)
    db.execute("""CREATE TABLE IF NOT EXISTS source_cursors (
        rule_id TEXT NOT NULL, file_key TEXT NOT NULL, cursor TEXT NOT NULL,
        PRIMARY KEY (rule_id, file_key))""")
    return db


def remove_cursors(vault, rule_id):
    with closing(_connect(vault)) as db, db:
        db.execute("DELETE FROM source_cursors WHERE rule_id=?", (rule_id,))


def run_history(vault, jobs, reader, rule):
    """One window per run; page through files so old histories cannot starve."""
    progress = rule.setdefault("progress", {"windows": 0, "messages": 0, "passes": 0})
    listing = reader.list_sources(Path(rule["root"]), "codex", after=rule.get("scan_after", ""))
    if not listing["files"] and rule.get("scan_after"):
        rule["scan_after"] = ""
        progress["passes"] += 1
        listing = reader.list_sources(Path(rule["root"]), "codex", after="")
    progress.update(scan_limited=listing["scan_limited"], waiting_for_newline=False)
    progress.pop("source_warning", None)
    result = {"processed": 0, "learned": 0, "skipped": 0}
    with closing(_connect(vault)) as db:
        for file in listing["files"]:
            key = hashlib.sha256(file["path"].encode()).hexdigest()
            row = db.execute("SELECT cursor FROM source_cursors WHERE rule_id=? AND file_key=?",
                             (rule["id"], key)).fetchone()
            previous = json.loads(row["cursor"]) if row else None
            try:
                window = read_window(rule["root"], file["path"], previous)
            except (ValueError, OSError):
                result["skipped"] += 1
                progress["source_warning"] = "Unreadable, replaced or unsupported source skipped; inspect/export it before starting a new schedule."
                rule["scan_after"] = file["path"]
                continue
            progress.update(bytes_remaining=window["bytes_remaining"],
                            waiting_for_newline=window["waiting_for_newline"])
            if window["messages"]:
                # Freeze this retry's byte range before any provider call. Later
                # appends cannot enlarge an interrupted occurrence on restart.
                pending = {**window["cursor"], "offset": window["start"],
                           "pending_end": window["cursor"]["offset"]}
                with db:
                    db.execute("INSERT OR REPLACE INTO source_cursors VALUES (?, ?, ?)",
                               (rule["id"], key, json.dumps(pending)))
                # Position distinguishes identical user statements in separate turns.
                occurrence = json.dumps([rule["id"], key, window["cursor"]["identity"],
                                         window["start"], window["cursor"]["offset"], window["messages"]])
                event = "source-history-" + hashlib.sha256(occurrence.encode()).hexdigest()
                extracted = jobs.extract(window["messages"], rule["scope"],
                                         route_key="skill:source-codex", event_id=event)
                result["learned"] = len(extracted.get("learned", []))
            # No transaction is held during a provider call. Its durable receipt
            # also covers a crash after extraction but before this cursor commit.
            if previous != window["cursor"]:
                with db:
                    db.execute("INSERT OR REPLACE INTO source_cursors VALUES (?, ?, ?)",
                               (rule["id"], key, json.dumps(window["cursor"])))
            # Round-robin: a long or busy first conversation must not monopolize
            # the daily window. Its own cursor retains the remaining history.
            rule["scan_after"] = file["path"]
            moved = window["cursor"]["offset"] != window["start"]
            if moved:
                result["processed"] = 1
                progress["windows"] += 1
                progress["messages"] += len(window["messages"])
                progress["last_discards"] = window["counts"]
                break
        else:
            # Another page or another pass, never an unbounded scan in one tick.
            if len(listing["files"]) < 100:
                rule["scan_after"] = ""
                progress["passes"] += 1
    progress["tracked_conversations"] = _cursor_count(vault, rule["id"])
    return result


def _cursor_count(vault, rule_id):
    with closing(_connect(vault)) as db:
        return db.execute("SELECT count(*) FROM source_cursors WHERE rule_id=?", (rule_id,)).fetchone()[0]
