"""Disposable SQLite FTS index built from canonical Markdown."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .models import SearchHit
from .vault import Vault, VaultError, utc_now


class SearchError(ValueError):
    pass


_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _canonical_snippet(content: str, tokens: list[str], max_chars: int = 240) -> str:
    normalized = content.casefold()
    positions = [normalized.find(token.casefold()) for token in tokens]
    positions = [position for position in positions if position >= 0]
    start = max(0, (min(positions) if positions else 0) - 60)
    snippet = " ".join(content[start : start + max_chars].split())
    if start:
        snippet = "… " + snippet
    if start + max_chars < len(content):
        snippet += " …"
    return snippet


class SearchIndex:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.path = vault.indexes_dir / "memory.sqlite"

    def _storage_paths(self) -> tuple[Path, Path, Path]:
        return self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")

    def _validate_storage_paths(self) -> None:
        directory = self.vault.indexes_dir
        for path in self._storage_paths():
            if path.is_symlink():
                raise SearchError(f"Generated index path cannot be a symbolic link: {path}")
            if not path.exists():
                continue
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(directory)
            except (OSError, ValueError) as exc:
                raise SearchError(f"Generated index path escapes the vault: {path}") from exc
            if not resolved.is_file():
                raise SearchError(f"Generated index path is not a regular file: {path}")

    def _open_connection(self) -> sqlite3.Connection:
        self._validate_storage_paths()
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS index_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_files (
                    memory_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    memory_id UNINDEXED,
                    title,
                    body,
                    tokenize='unicode61'
                );
                """
            )
            return connection
        except Exception:
            connection.close()
            raise

    @staticmethod
    def _is_corruption(error: sqlite3.DatabaseError) -> bool:
        message = str(error).lower()
        return any(
            marker in message
            for marker in ("not a database", "malformed", "file is encrypted", "database disk image")
        )

    def _discard_generated_index(self) -> None:
        self._validate_storage_paths()
        try:
            for path in self._storage_paths():
                if path.exists():
                    path.unlink()
        except OSError as exc:
            raise SearchError(f"Cannot replace corrupt generated index: {exc}") from exc

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._open_connection()
        except sqlite3.DatabaseError as exc:
            if not self._is_corruption(exc):
                raise
            self._discard_generated_index()
            return self._open_connection()

    def sync(self) -> dict[str, int]:
        indexed = 0
        removed = 0
        skipped = 0
        try:
            connection = self._connect()
        except sqlite3.Error as exc:
            raise SearchError(f"Cannot open generated search index: {exc}") from exc
        try:
            with connection:
                existing = {
                    row["path"]: row
                    for row in connection.execute(
                        "SELECT memory_id, path, mtime_ns, size FROM memory_files"
                    )
                }
                memory_paths = list(self.vault.iter_memory_paths())
                current_paths = {
                    path.relative_to(self.vault.root).as_posix() for path in memory_paths
                }
                for relative, row in list(existing.items()):
                    if relative not in current_paths:
                        connection.execute(
                            "DELETE FROM memory_fts WHERE memory_id = ?", (row["memory_id"],)
                        )
                        connection.execute("DELETE FROM memory_files WHERE path = ?", (relative,))
                        existing.pop(relative)
                        removed += 1

                for path in memory_paths:
                    relative = path.relative_to(self.vault.root).as_posix()
                    stat = path.stat()
                    previous = existing.get(relative)
                    if previous and previous["mtime_ns"] == stat.st_mtime_ns and previous["size"] == stat.st_size:
                        skipped += 1
                        continue
                    try:
                        memory = self.vault.read_memory(path)
                    except VaultError as exc:
                        raise SearchError(str(exc)) from exc
                    if previous:
                        connection.execute("DELETE FROM memory_fts WHERE memory_id = ?", (previous["memory_id"],))
                        connection.execute("DELETE FROM memory_files WHERE path = ?", (relative,))
                    duplicate = connection.execute(
                        "SELECT path FROM memory_files WHERE memory_id = ?", (memory.memory_id,)
                    ).fetchone()
                    if duplicate:
                        raise SearchError(
                            f"Duplicate memory id {memory.memory_id} in {relative} and {duplicate['path']}"
                        )
                    connection.execute(
                        """
                        INSERT INTO memory_files(memory_id, path, title, created_at, mtime_ns, size)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            memory.memory_id,
                            relative,
                            memory.title,
                            memory.created_at,
                            stat.st_mtime_ns,
                            stat.st_size,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO memory_fts(memory_id, title, body) VALUES (?, ?, ?)",
                        (memory.memory_id, memory.title, memory.content),
                    )
                    indexed += 1

                connection.execute(
                    "INSERT OR REPLACE INTO index_meta(key, value) VALUES ('last_synced_at', ?)",
                    (utc_now(),),
                )
        except sqlite3.Error as exc:
            raise SearchError(f"Cannot synchronize generated search index: {exc}") from exc
        finally:
            connection.close()
        return {"indexed": indexed, "removed": removed, "unchanged": skipped}

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        if not 1 <= limit <= 50:
            raise SearchError("limit must be between 1 and 50")
        tokens = _TOKEN.findall(query)
        if not tokens:
            raise SearchError("Search query must contain at least one word or number")
        self.sync()
        expression = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:20])
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT f.memory_id, m.path,
                       bm25(memory_fts, 4.0, 1.0) AS rank
                FROM memory_fts AS f
                JOIN memory_files AS m ON m.memory_id = f.memory_id
                WHERE memory_fts MATCH ?
                ORDER BY rank, m.created_at DESC
                LIMIT ?
                """,
                (expression, limit),
            ).fetchall()
        except sqlite3.Error as exc:
            raise SearchError(f"Search failed: {exc}") from exc
        finally:
            connection.close()
        hits: list[SearchHit] = []
        for row in rows:
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise SearchError("Generated index contains an unsafe memory path; delete it to rebuild")
            path = self.vault.root / relative
            try:
                canonical = path.resolve(strict=True)
                canonical.relative_to(self.vault.root)
            except (OSError, ValueError) as exc:
                raise SearchError("Generated index points outside the selected vault") from exc
            if path.is_symlink() or not canonical.is_file():
                raise SearchError("Generated index points to a linked or non-file memory")
            try:
                memory = self.vault.read_memory(canonical)
            except VaultError as exc:
                raise SearchError(str(exc)) from exc
            if memory.memory_id != row["memory_id"]:
                raise SearchError("Generated index identity does not match canonical Markdown")
            hits.append(
                SearchHit(
                    memory_id=memory.memory_id,
                    title=memory.title,
                    snippet=_canonical_snippet(memory.content, tokens),
                    score=float(-row["rank"]),
                    path=canonical,
                )
            )
        return hits

    def status(self) -> dict[str, int | str | None]:
        self._validate_storage_paths()
        if not self.path.exists():
            return {"state": "not_built", "rows": 0, "bytes": 0, "last_synced_at": None}
        try:
            connection = self._connect()
        except sqlite3.Error as exc:
            raise SearchError(f"Cannot inspect generated search index: {exc}") from exc
        try:
            rows = connection.execute("SELECT COUNT(*) FROM memory_files").fetchone()[0]
            synced = connection.execute(
                "SELECT value FROM index_meta WHERE key = 'last_synced_at'"
            ).fetchone()
        except sqlite3.Error as exc:
            raise SearchError(f"Cannot inspect generated search index: {exc}") from exc
        finally:
            connection.close()
        return {
            "state": "ready",
            "rows": int(rows),
            "bytes": self.path.stat().st_size,
            "last_synced_at": synced[0] if synced else None,
        }
