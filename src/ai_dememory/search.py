"""Disposable SQLite FTS index built from canonical Markdown."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from types import SimpleNamespace

from .models import SearchHit
from .quality import recall_eligible
from .vault import Vault, VaultError, utc_now, validate_scope


class SearchError(ValueError):
    pass


_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _term_key(token: str) -> str:
    # Keep Latin accent-insensitive snippets/details consistent with unicode61.
    return "".join(char for char in unicodedata.normalize("NFD", token.casefold())
                   if not unicodedata.combining(char))

# These terms add little retrieval signal by themselves.  They are intentionally
# small and conservative: identifiers, negations, numbers, and ordinary short
# questions must remain searchable.  This is lexical filtering, not translation
# or stemming.
_FILLER_TERMS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "de", "del", "do", "el",
    "en", "for", "from", "how", "i", "in", "is", "it", "la", "las", "los", "me",
    "gracias", "hello", "hi", "hola", "my", "of", "ok", "okay", "or", "please", "por",
    "que", "thanks", "thank", "the", "to", "un", "una", "what", "with", "y", "yo",
})


def _query_tokens(query: str) -> list[str]:
    """Return bounded, unique whole-word terms with retrieval value.

    Terms are case/accent-folded for deduplication but their spelling is kept
    for FTS.  Filtering happens before the twenty-term bound so a useful word
    after conversational filler is not silently discarded.
    """
    selected: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN.findall(query):
        key = _term_key(token)
        if key in seen or key in _FILLER_TERMS:
            continue
        seen.add(key)
        selected.append(token)
        if len(selected) == 20:
            break
    return selected


def _canonical_snippet(content: str, tokens: list[str], max_chars: int = 240) -> str:
    wanted = {_term_key(token) for token in tokens}
    positions = [match.start() for match in _TOKEN.finditer(content) if _term_key(match.group()) in wanted]
    start = max(0, (min(positions) if positions else 0) - min(60, max_chars // 4))
    snippet = " ".join(content[start : start + max_chars].split())
    if start:
        snippet = "… " + snippet
    if start + max_chars < len(content):
        snippet += " …"
    return snippet


def _matching_terms(title: str, content: str, tokens: list[str]) -> list[str]:
    present = {_term_key(match.group()) for match in _TOKEN.finditer(f"{title} {content}")}
    return [token.casefold() for token in tokens if _term_key(token) in present]


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
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(memory_files)")}
            if "scope" not in columns:
                connection.execute("ALTER TABLE memory_files ADD COLUMN scope TEXT NOT NULL DEFAULT 'global'")
                connection.execute("ALTER TABLE memory_files ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
                connection.execute("DELETE FROM memory_files")
                connection.execute("DELETE FROM memory_fts")
                connection.commit()
                columns.update({"scope", "status"})
            # The index is disposable, but adding projected metadata lets ranking
            # stay bounded and avoids rereading every Markdown file per query.
            for name, declaration in (
                ("importance", "TEXT NOT NULL DEFAULT 'normal'"),
                ("importance_origin", "TEXT NOT NULL DEFAULT 'default'"),
                ("memory_kind", "TEXT NOT NULL DEFAULT 'unspecified'"),
                ("expires_at", "TEXT"),
            ):
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE memory_files ADD COLUMN {name} {declaration}"
                    )
                    columns.add(name)
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
                        INSERT INTO memory_files(
                            memory_id, path, title, created_at, mtime_ns, size, scope, status,
                            importance, importance_origin, memory_kind, expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            memory.memory_id,
                            relative,
                            memory.title,
                            memory.created_at,
                            stat.st_mtime_ns,
                            stat.st_size,
                            memory.scope,
                            memory.status,
                            getattr(memory, "importance", "normal"),
                            getattr(memory, "importance_origin", "default"),
                            getattr(memory, "memory_kind", "unspecified"),
                            getattr(memory, "expires_at", None),
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

    def search(
        self, query: str, limit: int = 5, scope: str = "global", *, importance_weight: float = 0.15,
        episode_days: int = 0,
    ) -> list[SearchHit]:
        validate_scope(scope)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise SearchError("limit must be between 1 and 50")
        if not isinstance(query, str):
            raise SearchError("query must be a string")
        if type(importance_weight) not in {int, float} or not isfinite(importance_weight) or not 0 <= importance_weight <= 0.25:
            raise SearchError("importance_weight must be a finite number between 0 and 0.25")
        if type(episode_days) is not int or not 0 <= episode_days <= 36500:
            raise SearchError("episode_days must be an integer between 0 and 36500")
        tokens = _query_tokens(query)
        if not _TOKEN.findall(query):
            raise SearchError("Search query must contain at least one word or number")
        if not tokens:
            return []
        self.sync()
        expression = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:20])
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT f.memory_id, m.path, m.created_at, m.importance, m.importance_origin,
                       m.memory_kind, m.expires_at,
                       bm25(memory_fts, 0.0, 4.0, 1.0) AS rank
                FROM memory_fts AS f
                JOIN memory_files AS m ON m.memory_id = f.memory_id
                WHERE memory_fts MATCH ? AND m.scope IN ('global', ?) AND m.status = 'active'
                ORDER BY rank, m.created_at DESC
                """,
                (expression, scope),
            ).fetchall()
        except sqlite3.Error as exc:
            raise SearchError(f"Search failed: {exc}") from exc
        finally:
            connection.close()
        now = datetime.now(timezone.utc)
        ranked_rows: list[tuple[float, str, sqlite3.Row]] = []
        for row in rows:
            indexed_memory = SimpleNamespace(
                status="active",
                created_at=row["created_at"],
                memory_kind=row["memory_kind"] or "unspecified",
                expires_at=row["expires_at"],
            )
            if not recall_eligible(indexed_memory, episode_days=episode_days, now=now):
                continue
            importance = row["importance"] or "normal"
            if importance not in {"low", "normal", "high"}:
                importance = "normal"
            importance_applied = row["importance_origin"] != "host"
            # Host-provided importance is advisory until a user enables such a
            # policy.  It remains visible in details but cannot affect recall.
            effective_importance = importance if importance_applied else "normal"
            importance_value = {"low": 0.0, "normal": 0.5, "high": 1.0}[effective_importance]
            base_score = float(-row["rank"])
            score = base_score * (1 + importance_weight * (2 * importance_value - 1))
            ranked_rows.append((score, row["created_at"], row))
        ranked_rows.sort(key=lambda value: (value[0], value[1]), reverse=True)

        hits: list[SearchHit] = []
        for score, _, row in ranked_rows[:limit]:
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
            if memory.scope not in {"global", scope} or not recall_eligible(
                memory, episode_days=episode_days, now=now
            ):
                continue
            importance = getattr(memory, "importance", row["importance"] or "normal")
            if importance not in {"low", "normal", "high"}:
                importance = "normal"
            importance_origin = getattr(memory, "importance_origin", row["importance_origin"] or "default")
            if not isinstance(importance_origin, str) or not importance_origin:
                importance_origin = "default"
            importance_applied = importance_origin != "host"
            from .quality import confidence_status
            details = {
                "matching_terms": _matching_terms(memory.title, memory.content, tokens),
                "importance": importance,
                "importance_origin": importance_origin,
                "importance_applied": importance_applied,
                "importance_weight": float(importance_weight),
                "confidence_status": confidence_status(memory),
                "confidence_applied": False,
            }
            hits.append(
                SearchHit(
                    memory_id=memory.memory_id,
                    title=memory.title,
                    snippet=_canonical_snippet(memory.content, tokens),
                    score=score,
                    path=canonical,
                    details=details,
                )
            )
        return hits

    def status(self) -> dict[str, int | str | None]:
        self._validate_storage_paths()
        if not self.path.exists():
            return {"state": "not_built", "rows": 0, "bytes": 0, "last_synced_at": None}
        size = self.path.stat().st_size
        try:
            uri = f"{self.path.resolve().as_uri()}?mode=ro&immutable=1"
            connection = sqlite3.connect(uri, uri=True)
        except sqlite3.Error:
            return {"state": "invalid", "rows": 0, "bytes": size, "last_synced_at": None}
        try:
            rows = connection.execute("SELECT COUNT(*) FROM memory_files").fetchone()[0]
            synced = connection.execute(
                "SELECT value FROM index_meta WHERE key = 'last_synced_at'"
            ).fetchone()
        except sqlite3.Error:
            return {"state": "invalid", "rows": 0, "bytes": size, "last_synced_at": None}
        finally:
            connection.close()
        return {
            "state": "ready",
            "rows": int(rows),
            "bytes": size,
            "last_synced_at": synced[0] if synced else None,
        }
