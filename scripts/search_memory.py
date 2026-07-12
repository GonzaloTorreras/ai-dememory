#!/usr/bin/env python3
"""Search the generated memory index with local ranking."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

from index_memory import default_db_path
from memorylib import recency_score, repo_root, today


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

TYPE_BOOST = {
    "durable": 1.0,
    "active": 0.8,
    "project": 0.5,
    "tool": 0.4,
    "session": 0.2,
    "archive": 0.0,
}


@dataclass(frozen=True)
class SearchResult:
    score: float
    id: str
    title: str
    path: str
    type: str
    status: str
    confidence: float
    snippet: str
    why: dict[str, Any]


def tokenize(query: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(query) if token.strip()]


def fts_query(tokens: list[str]) -> str:
    safe_terms = [token.replace('"', "") for token in tokens if token]
    return " OR ".join(f"{term}*" for term in safe_terms)


def search(
    query: str,
    root: Path,
    db_path: Path | None = None,
    limit: int = 10,
    include_expired: bool = False,
    include_sensitive: bool = False,
    project_hint: str | None = None,
) -> list[SearchResult]:
    db_path = db_path or default_db_path(root)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} does not exist. Run scripts/index_memory.py first.")

    tokens = tokenize(query)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT rowid, * FROM memories").fetchall()
        fts_scores = compute_fts_scores(conn, tokens)
    finally:
        conn.close()

    results: list[SearchResult] = []
    query_lower = query.lower().strip()
    for row in rows:
        if row["sensitivity"] == "secret-prohibited":
            continue
        if row["sensitivity"] in {"private", "sensitive"} and not include_sensitive:
            continue
        if row["status"] == "expired" and not include_expired:
            continue

        tags = split_words(row["tags"])
        aliases = split_aliases(row["aliases"])
        tag_match = token_overlap(tokens, tags)
        alias_match = alias_score(tokens, aliases, query_lower)
        project_match = project_match_score(row["project"], project_hint)
        matched_fields = matched_search_fields(row, tokens)
        matched_aliases = matched_alias_values(aliases, tokens, query_lower)
        matched_tags = ordered_overlap(tokens, tags)
        fts_component = fts_scores.get(row["rowid"], 0.0)

        if tokens and fts_component == 0 and tag_match == 0 and alias_match == 0 and project_match == 0:
            continue

        recency = recency_score(row["updated_at"], row["decay"], today())
        confidence = float(row["confidence"])
        type_boost = TYPE_BOOST.get(row["type"], 0.0)
        pin_boost = 1.0 if row["pin"] else 0.0
        status = status_penalty(row["status"], row["type"])
        sensitivity = sensitivity_penalty(row["sensitivity"])
        strength = lifecycle_strength(root, row["id"])
        score = (
            0.40 * fts_component
            + 0.14 * tag_match
            + 0.09 * alias_match
            + 0.10 * recency
            + 0.10 * confidence
            + 0.05 * type_boost
            + 0.04 * pin_boost
            + 0.08 * strength
            + 0.10 * project_match
            - status
            - sensitivity
        )
        results.append(
            SearchResult(
                score=round(max(score, 0.0), 4),
                id=row["id"],
                title=row["title"],
                path=row["path"],
                type=row["type"],
                status=row["status"],
                confidence=confidence,
                snippet=snippet(row["raw_content"], tokens),
                why={
                    "fts": round(fts_component, 4),
                    "tag_overlap": round(tag_match, 4),
                    "alias_match": round(alias_match, 4),
                    "project_hint": project_hint,
                    "project_match": round(project_match, 4),
                    "recency": round(recency, 4),
                    "confidence": round(confidence, 4),
                    "type_boost": round(type_boost, 4),
                    "pin_boost": round(pin_boost, 4),
                    "lifecycle_strength": round(strength, 4),
                    "status_penalty": round(status, 4),
                    "sensitivity_penalty": round(sensitivity, 4),
                    "matched_terms": matched_terms(matched_fields),
                    "matched_fields": list(matched_fields),
                    "matched_tags": matched_tags,
                    "matched_aliases": matched_aliases,
                },
            )
        )

    return sorted(results, key=lambda result: result.score, reverse=True)[:limit]


def compute_fts_scores(conn: sqlite3.Connection, tokens: list[str]) -> dict[int, float]:
    if not tokens:
        return {}
    query = fts_query(tokens)
    if not query:
        return {}
    try:
        matches = conn.execute(
            """
            SELECT m.rowid AS rowid, bm25(memory_fts) AS rank
            FROM memory_fts
            JOIN memories m ON m.rowid = memory_fts.rowid
            WHERE memory_fts MATCH ?
            ORDER BY rank
            """,
            (query,),
        ).fetchall()
    except sqlite3.Error:
        return {}

    if not matches:
        return {}
    total = len(matches)
    return {row["rowid"]: 1.0 - (idx / max(total, 1)) for idx, row in enumerate(matches)}


def split_words(value: str | None) -> set[str]:
    if not value:
        return set()
    words: set[str] = set()
    for item in value.split():
        lowered = item.lower().strip()
        if not lowered:
            continue
        words.add(lowered)
        words.update(tokenize(lowered))
    return words


def split_aliases(value: str | None) -> list[str]:
    if not value:
        return []
    if "||" in value:
        return [item.strip().lower() for item in value.split("||") if item.strip()]
    return [item.strip().lower() for item in value.split() if item.strip()]


def token_overlap(tokens: list[str], words: set[str]) -> float:
    if not tokens or not words:
        return 0.0
    return len(set(tokens) & words) / len(set(tokens))


def ordered_overlap(tokens: list[str], words: set[str]) -> list[str]:
    if not tokens or not words:
        return []
    seen: set[str] = set()
    output: list[str] = []
    for token in tokens:
        if token in words and token not in seen:
            output.append(token)
            seen.add(token)
    return output


def alias_score(tokens: list[str], aliases: list[str], query_lower: str) -> float:
    if not tokens or not aliases:
        return 0.0
    for alias in aliases:
        if alias and (alias in query_lower or query_lower in alias):
            return 1.0
    alias_words = set(word for alias in aliases for word in tokenize(alias))
    return token_overlap(tokens, alias_words)


def project_match_score(project: str | None, project_hint: str | None) -> float:
    """Return an explainable exact project match without fuzzy cross-project leakage."""
    if not project or not project_hint:
        return 0.0
    project_tokens = tokenize(project)
    hint_tokens = tokenize(project_hint)
    if not project_tokens or not hint_tokens:
        return 0.0
    return 1.0 if project_tokens == hint_tokens else 0.0


def matched_alias_values(aliases: list[str], tokens: list[str], query_lower: str) -> list[str]:
    matches: list[str] = []
    for alias in aliases:
        alias_tokens = tokenize(alias)
        if alias and (alias in query_lower or query_lower in alias):
            matches.append(alias)
        elif any(token in alias_tokens for token in tokens):
            matches.append(alias)
    return unique_ordered(matches)


def matched_search_fields(row: sqlite3.Row, tokens: list[str]) -> dict[str, list[str]]:
    fields = {
        "title": row["title"],
        "tags": row["tags"],
        "aliases": row["aliases"],
        "summary": row["summary"] or "",
        "raw_content": row["raw_content"],
    }
    matches: dict[str, list[str]] = {}
    for field, value in fields.items():
        field_terms = matched_query_terms(tokens, str(value or ""))
        if field_terms:
            matches[field] = field_terms
    return matches


def matched_query_terms(tokens: list[str], text: str) -> list[str]:
    if not tokens or not text:
        return []
    words = tokenize(text)
    output: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        if any(word.startswith(token) for word in words):
            output.append(token)
            seen.add(token)
    return output


def matched_terms(field_matches: dict[str, list[str]]) -> list[str]:
    terms: list[str] = []
    for values in field_matches.values():
        terms.extend(values)
    return unique_ordered(terms)


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


def status_penalty(status: str, memory_type: str) -> float:
    penalty = 0.0
    if status == "stale":
        penalty += 0.10
    if status == "disputed":
        penalty += 0.25
    if status in {"archived", "superseded"} or memory_type == "archive":
        penalty += 0.15
    return penalty


def sensitivity_penalty(sensitivity: str) -> float:
    if sensitivity == "sensitive":
        return 0.10
    if sensitivity == "private":
        return 0.05
    return 0.0


def lifecycle_strength(root: Path, memory_id: str) -> float:
    db_path = default_db_path(root)
    if not db_path.exists():
        return 0.0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT strength FROM memory_lifecycle WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
    except sqlite3.Error:
        return 0.0
    finally:
        conn.close()
    if not row:
        return 0.0
    try:
        return max(0.0, min(float(row[0]), 1.0))
    except (TypeError, ValueError):
        return 0.0


def snippet(content: str, tokens: list[str], max_len: int = 220) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if not compact:
        return ""
    lower = compact.lower()
    start = 0
    for token in tokens:
        idx = lower.find(token.lower())
        if idx >= 0:
            start = max(0, idx - 60)
            break
    excerpt = compact[start : start + max_len].strip()
    if start > 0:
        excerpt = "..." + excerpt
    if start + max_len < len(compact):
        excerpt += "..."
    return excerpt


def result_to_dict(result: SearchResult) -> dict[str, Any]:
    return asdict(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+", help="Search query.")
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--db", default=None, help="SQLite database path.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum results.")
    parser.add_argument("--include-expired", action="store_true", help="Include expired memories.")
    parser.add_argument("--include-sensitive", action="store_true", help="Include private/sensitive memories.")
    parser.add_argument("--why", action="store_true", help="Print explainable ranking components.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    db_path = Path(args.db) if args.db else default_db_path(root)
    if not db_path.is_absolute():
        db_path = root / db_path

    try:
        results = search(
            " ".join(args.query),
            root,
            db_path=db_path,
            limit=args.limit,
            include_expired=args.include_expired,
            include_sensitive=args.include_sensitive,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([result_to_dict(result) for result in results], indent=2))
    else:
        for result in results:
            print(
                f"{result.score:.4f} {result.id} [{result.type}/{result.status}] "
                f"{result.path} confidence={result.confidence:.2f}"
            )
            print(f"  {result.title}")
            if result.snippet:
                print(f"  {result.snippet}")
            if args.why:
                why = ", ".join(f"{key}={value}" for key, value in result.why.items())
                print(f"  why: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
