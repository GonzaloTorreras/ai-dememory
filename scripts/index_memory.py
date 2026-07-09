#!/usr/bin/env python3
"""Rebuild the generated SQLite FTS memory index."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

from memorylib import (
    MemoryDocument,
    content_hash,
    discover_memory_files,
    extract_summary,
    list_text,
    repo_root,
    repo_relative_path,
    validate_memories,
)
from secret_scan import scan_paths


DEFAULT_DB = Path("indexes/memory.sqlite")


SCHEMA = """
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  scope TEXT,
  project TEXT,
  tags TEXT NOT NULL DEFAULT '',
  aliases TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  review_after TEXT NOT NULL,
  last_seen_at TEXT,
  expires_at TEXT,
  confidence REAL NOT NULL DEFAULT 0.7,
  sensitivity TEXT NOT NULL DEFAULT 'internal',
  source_kind TEXT NOT NULL,
  source_ref TEXT,
  pin INTEGER NOT NULL DEFAULT 0,
  decay TEXT NOT NULL DEFAULT 'normal',
  content_hash TEXT NOT NULL,
  summary TEXT,
  raw_content TEXT NOT NULL
);

CREATE VIRTUAL TABLE memory_fts USING fts5(
  title,
  tags,
  aliases,
  summary,
  raw_content,
  content='memories',
  content_rowid='rowid'
);

CREATE TABLE memory_tags (
  memory_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (memory_id, tag)
);

CREATE TABLE memory_aliases (
  memory_id TEXT NOT NULL,
  alias TEXT NOT NULL,
  PRIMARY KEY (memory_id, alias)
);

CREATE TABLE retrieval_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL,
  selected_memory_id TEXT,
  score REAL,
  used_by TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE consolidation_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  memory_id TEXT,
  details TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE memory_lifecycle (
  memory_id TEXT PRIMARY KEY,
  retrieval_count INTEGER NOT NULL DEFAULT 0,
  last_retrieved_at TEXT,
  strength REAL NOT NULL DEFAULT 0.0,
  positive_outcomes INTEGER NOT NULL DEFAULT 0,
  negative_outcomes INTEGER NOT NULL DEFAULT 0,
  reward_factor REAL NOT NULL DEFAULT 1.0,
  updated_at TEXT NOT NULL
);

CREATE TABLE memory_outcomes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
"""


class IndexBuildError(Exception):
    pass


def default_db_path(root: Path) -> Path:
    return root / DEFAULT_DB


def memory_targets(root: Path) -> list[str]:
    return [repo_relative_path(path, root) for path in discover_memory_files(root)]


def rebuild_index(root: Path, db_path: Path | None = None) -> tuple[Path, int]:
    db_path = db_path or default_db_path(root)
    targets = memory_targets(root)
    findings = scan_paths(root, targets)
    if findings:
        formatted = "\n".join(
            f"{finding.path}:{finding.line}: {finding.kind}: {finding.redacted_line}"
            for finding in findings
        )
        raise IndexBuildError(f"secret scan failed before indexing:\n{formatted}")

    documents, errors = validate_memories(root)
    if errors:
        raise IndexBuildError("memory validation failed:\n" + "\n".join(errors))
    current_ids = {str(document.frontmatter["id"]) for document in documents}
    generated_state = dump_generated_state(db_path, current_ids)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(SCHEMA)
        assert_fts_available(conn)
        for document in documents:
            insert_document(conn, root, document)
        restore_generated_state(conn, generated_state)
        conn.commit()
    except Exception:
        conn.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    else:
        conn.close()

    if db_path.exists():
        db_path.unlink()
    tmp_path.replace(db_path)
    cleanup_sidecars(tmp_path)
    cleanup_sidecars(db_path)
    return db_path, len(documents)


def dump_generated_state(db_path: Path, current_ids: set[str]) -> dict[str, list[dict[str, object]]]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            "retrieval_log": filtered_rows(
                conn,
                "retrieval_log",
                "selected_memory_id",
                current_ids,
            ),
            "memory_lifecycle": filtered_rows(conn, "memory_lifecycle", "memory_id", current_ids),
            "memory_outcomes": filtered_rows(conn, "memory_outcomes", "memory_id", current_ids),
            "consolidation_log": read_rows(conn, "consolidation_log"),
        }
    finally:
        conn.close()


def read_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, object]]:
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def filtered_rows(
    conn: sqlite3.Connection,
    table: str,
    memory_column: str,
    current_ids: set[str],
) -> list[dict[str, object]]:
    rows = read_rows(conn, table)
    output: list[dict[str, object]] = []
    for row in rows:
        memory_id = row.get(memory_column)
        if memory_id is None or str(memory_id) in current_ids:
            output.append(row)
    return output


def restore_generated_state(conn: sqlite3.Connection, state: dict[str, list[dict[str, object]]]) -> None:
    for table in ("retrieval_log", "consolidation_log", "memory_lifecycle", "memory_outcomes"):
        for row in state.get(table, []):
            insert_row(conn, table, row)


def insert_row(conn: sqlite3.Connection, table: str, row: dict[str, object]) -> None:
    if not row:
        return
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    quoted_columns = ", ".join(columns)
    conn.execute(
        f"INSERT OR IGNORE INTO {table} ({quoted_columns}) VALUES ({placeholders})",
        [row[column] for column in columns],
    )


def assert_fts_available(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("SELECT count(*) FROM memory_fts").fetchone()
    except sqlite3.Error as exc:
        raise IndexBuildError(f"SQLite FTS5 is not available: {exc}") from exc


def cleanup_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


def insert_document(conn: sqlite3.Connection, root: Path, document: MemoryDocument) -> None:
    data = document.frontmatter
    if data.get("sensitivity") == "secret-prohibited":
        return

    source = data["source"]
    tags = [str(tag) for tag in data.get("tags", [])]
    aliases = [str(alias) for alias in data.get("aliases", [])]
    summary = extract_summary(document.content)
    relpath = repo_relative_path(document.path, root)

    cursor = conn.execute(
        """
        INSERT INTO memories (
          id, path, title, type, status, scope, project, tags, aliases,
          created_at, updated_at, review_after, last_seen_at, expires_at, confidence,
          sensitivity, source_kind, source_ref, pin, decay, content_hash,
          summary, raw_content
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["id"],
            relpath,
            data["title"],
            data["type"],
            data["status"],
            data["scope"],
            data.get("project"),
            " ".join(tags),
            " || ".join(aliases),
            data["created_at"],
            data["updated_at"],
            data["review_after"],
            data.get("last_seen_at"),
            data.get("expires_at"),
            float(data["confidence"]),
            data["sensitivity"],
            source["kind"],
            source.get("ref"),
            1 if data["pin"] else 0,
            data["decay"],
            content_hash(data, document.content),
            summary,
            document.content,
        ),
    )
    rowid = cursor.lastrowid

    for tag in tags:
        conn.execute("INSERT INTO memory_tags (memory_id, tag) VALUES (?, ?)", (data["id"], tag))
    for alias in aliases:
        conn.execute(
            "INSERT INTO memory_aliases (memory_id, alias) VALUES (?, ?)",
            (data["id"], alias),
        )

    conn.execute(
        """
        INSERT INTO memory_fts (rowid, title, tags, aliases, summary, raw_content)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (rowid, data["title"], " ".join(tags), " ".join(aliases), summary, document.content),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--db", default=None, help="Output SQLite database path.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    db_path = Path(args.db) if args.db else default_db_path(root)
    if not db_path.is_absolute():
        db_path = root / db_path

    try:
        path, count = rebuild_index(root, db_path)
    except IndexBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    print(f"Indexed {count} memory file(s) into {repo_relative_path(path, root)} at {timestamp}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
