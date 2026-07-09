#!/usr/bin/env python3
"""Record memory retrieval and usefulness outcomes."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
import sys
from typing import Any

from index_memory import default_db_path
from memorylib import parse_date, recency_score, repo_relative_path, repo_root, today
from secret_scan import scan_text


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_lifecycle (
  memory_id TEXT PRIMARY KEY,
  retrieval_count INTEGER NOT NULL DEFAULT 0,
  last_retrieved_at TEXT,
  strength REAL NOT NULL DEFAULT 0.0,
  positive_outcomes INTEGER NOT NULL DEFAULT 0,
  negative_outcomes INTEGER NOT NULL DEFAULT 0,
  reward_factor REAL NOT NULL DEFAULT 1.0,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_outcomes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);
"""

LIFECYCLE_JSON = Path("indexes/memory-lifecycle.json")
LIFECYCLE_REPORT = Path("reports/lifecycle.md")


@dataclass(frozen=True)
class LifecycleScore:
    memory_id: str
    title: str
    path: str
    type: str
    status: str
    score: float
    strength: float
    retrieval_count: int
    positive_outcomes: int
    negative_outcomes: int
    reward_factor: float
    confidence: float
    recency: float
    review_due: bool
    last_retrieved_at: str | None
    updated_at: str
    recommendation: str


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(root: Path) -> sqlite3.Connection:
    db_path = default_db_path(root)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} does not exist. Run ai-dememory index first.")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def mark_seen(root: Path, memory_id: str, query: str = "", score: float | None = None, used_by: str | None = None) -> dict[str, Any]:
    for label, value in (("memory_id", memory_id), ("query", query), ("used_by", used_by or "")):
        if value and scan_text(value, f"<lifecycle.mark_seen.{label}>"):
            raise ValueError(f"mark-seen rejected secret-like {label}")
    timestamp = now_iso()
    conn = connect(root)
    try:
        conn.execute(
            """
            INSERT INTO retrieval_log (query, selected_memory_id, score, used_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (query or "<manual>", memory_id, score, used_by, timestamp),
        )
        conn.execute(
            """
            INSERT INTO memory_lifecycle (memory_id, retrieval_count, last_retrieved_at, strength, updated_at)
            VALUES (?, 1, ?, 0.1, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
              retrieval_count = retrieval_count + 1,
              last_retrieved_at = excluded.last_retrieved_at,
              strength = min(1.0, strength + 0.03),
              updated_at = excluded.updated_at
            """,
            (memory_id, timestamp, timestamp),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "memory_id": memory_id,
        "query": query or "<manual>",
        "score": score,
        "used_by": used_by,
        "lifecycle_updated": True,
        "created_at": timestamp,
    }


def record_outcome(root: Path, memory_id: str | None, outcome: str, note: str | None = None) -> dict[str, Any]:
    if outcome not in {"good", "bad"}:
        raise ValueError("outcome must be good or bad")
    if note and scan_text(note, "<lifecycle.outcome.note>"):
        raise ValueError("outcome note rejected by secret scan")
    target_source = "last_seen" if memory_id is None else "explicit"
    conn = connect(root)
    try:
        target_id = memory_id or last_seen_id(conn)
        if not target_id:
            raise ValueError("no memory id provided and retrieval log is empty")
        if scan_text(target_id, "<lifecycle.outcome.memory_id>"):
            raise ValueError("outcome memory id rejected by secret scan")
        timestamp = now_iso()
        conn.execute(
            "INSERT INTO memory_outcomes (memory_id, outcome, note, created_at) VALUES (?, ?, ?, ?)",
            (target_id, outcome, note, timestamp),
        )
        if outcome == "good":
            conn.execute(
                """
                INSERT INTO memory_lifecycle (memory_id, positive_outcomes, strength, reward_factor, updated_at)
                VALUES (?, 1, 0.15, 1.05, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                  positive_outcomes = positive_outcomes + 1,
                  strength = min(1.0, strength + 0.12),
                  reward_factor = min(2.0, reward_factor + 0.05),
                  updated_at = excluded.updated_at
                """,
                (target_id, timestamp),
            )
        else:
            conn.execute(
                """
                INSERT INTO memory_lifecycle (memory_id, negative_outcomes, strength, reward_factor, updated_at)
                VALUES (?, 1, 0.0, 0.95, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                  negative_outcomes = negative_outcomes + 1,
                  strength = max(0.0, strength - 0.15),
                  reward_factor = max(0.1, reward_factor - 0.10),
                  updated_at = excluded.updated_at
                """,
                (target_id, timestamp),
            )
        row = conn.execute(
            """
            SELECT positive_outcomes, negative_outcomes, strength, reward_factor
            FROM memory_lifecycle
            WHERE memory_id = ?
            """,
            (target_id,),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    positive, negative, strength, reward_factor = row if row else (0, 0, 0.0, 1.0)
    return {
        "memory_id": target_id,
        "target_source": target_source,
        "outcome": outcome,
        "note_recorded": bool(note),
        "positive_outcomes": int(positive),
        "negative_outcomes": int(negative),
        "strength": float(strength),
        "reward_factor": float(reward_factor),
        "lifecycle_updated": True,
        "created_at": timestamp,
    }


def last_seen_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
        SELECT selected_memory_id
        FROM retrieval_log
        WHERE selected_memory_id IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def lifecycle_scores(root: Path, include_sensitive: bool = False) -> list[LifecycleScore]:
    conn = connect(root)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              m.id,
              m.title,
              m.path,
              m.type,
              m.status,
              m.confidence,
              m.updated_at,
              m.decay,
              m.review_after,
              m.pin,
              COALESCE(l.retrieval_count, 0) AS retrieval_count,
              l.last_retrieved_at,
              COALESCE(l.strength, 0.0) AS strength,
              COALESCE(l.positive_outcomes, 0) AS positive_outcomes,
              COALESCE(l.negative_outcomes, 0) AS negative_outcomes,
              COALESCE(l.reward_factor, 1.0) AS reward_factor
            FROM memories m
            LEFT JOIN memory_lifecycle l ON l.memory_id = m.id
            WHERE m.sensitivity != 'secret-prohibited'
              AND (? OR COALESCE(m.sensitivity, '') NOT IN ('private', 'sensitive'))
            """,
            (1 if include_sensitive else 0,),
        ).fetchall()
    finally:
        conn.close()

    now = today()
    scores: list[LifecycleScore] = []
    for row in rows:
        retrieval_count = int(row["retrieval_count"])
        positive = int(row["positive_outcomes"])
        negative = int(row["negative_outcomes"])
        total_outcomes = positive + negative
        positive_ratio = positive / total_outcomes if total_outcomes else 0.5
        negative_pressure = negative / total_outcomes if total_outcomes else 0.0
        confidence = float(row["confidence"])
        recency = recency_score(str(row["updated_at"]), str(row["decay"]), now)
        strength = clamp(float(row["strength"]))
        reward_factor = max(0.1, min(float(row["reward_factor"]), 2.0))
        review_due = parse_date(str(row["review_after"])) <= now if row["review_after"] else False
        pin_boost = 0.05 if int(row["pin"] or 0) else 0.0
        score = clamp(
            0.30 * strength
            + 0.20 * positive_ratio
            + 0.15 * min(reward_factor / 2.0, 1.0)
            + 0.15 * confidence
            + 0.10 * recency
            + pin_boost
            - 0.15 * negative_pressure
            - (0.10 if review_due else 0.0)
        )
        scores.append(
            LifecycleScore(
                memory_id=str(row["id"]),
                title=str(row["title"]),
                path=str(row["path"]),
                type=str(row["type"]),
                status=str(row["status"]),
                score=round(score, 4),
                strength=round(strength, 4),
                retrieval_count=retrieval_count,
                positive_outcomes=positive,
                negative_outcomes=negative,
                reward_factor=round(reward_factor, 4),
                confidence=round(confidence, 4),
                recency=round(recency, 4),
                review_due=review_due,
                last_retrieved_at=row["last_retrieved_at"],
                updated_at=str(row["updated_at"]),
                recommendation=recommendation(retrieval_count, positive, negative, score, review_due),
            )
        )
    return sorted(scores, key=lambda item: (-item.score, item.memory_id))


def clamp(value: float) -> float:
    return max(0.0, min(value, 1.0))


def recommendation(
    retrieval_count: int,
    positive: int,
    negative: int,
    score: float,
    review_due: bool,
) -> str:
    if review_due:
        return "review_due"
    if negative > positive and negative > 0:
        return "needs_repair"
    if positive > 0 and score >= 0.70:
        return "reinforce"
    if retrieval_count == 0:
        return "unproven"
    return "watch"


def write_lifecycle_scores(root: Path, output: Path = LIFECYCLE_JSON, include_sensitive: bool = False) -> tuple[Path, list[LifecycleScore]]:
    scores = lifecycle_scores(root, include_sensitive=include_sensitive)
    path = resolve_repo_path(root, output)
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("lifecycle score path must stay inside the memory root") from exc
    text = json.dumps([asdict(score) for score in scores], indent=2)
    if scan_text(text, "<lifecycle-scores-json>"):
        raise ValueError("lifecycle scores JSON rejected by secret scan")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, scores


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def write_lifecycle_report(root: Path, output: Path = LIFECYCLE_REPORT) -> tuple[Path, list[LifecycleScore]]:
    scores = lifecycle_scores(root)
    target = resolve_repo_path(root, output)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("report path must stay inside the memory root") from exc

    text = render_lifecycle_report(scores)
    if scan_text(text, "<lifecycle-report>"):
        raise ValueError("lifecycle report rejected by secret scan")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target, scores


def render_lifecycle_report(scores: list[LifecycleScore]) -> str:
    generated_at = now_iso()
    by_recommendation: dict[str, int] = {}
    for score in scores:
        by_recommendation[score.recommendation] = by_recommendation.get(score.recommendation, 0) + 1
    lines = [
        "# Lifecycle Scores",
        "",
        f"Generated at: {generated_at}",
        "",
        "No canonical memory files were modified.",
        "",
        "## Summary",
        "",
        f"- memories: {len(scores)}",
    ]
    for name in sorted(by_recommendation):
        lines.append(f"- {name}: {by_recommendation[name]}")
    lines.extend(["", "## Scores", ""])
    if not scores:
        lines.extend(["_No indexed memories._", ""])
        return "\n".join(lines)
    for item in scores:
        lines.extend(
            [
                f"### {item.title}",
                "",
                f"- id: `{item.memory_id}`",
                f"- path: `{item.path}`",
                f"- score: `{item.score:.4f}`",
                f"- recommendation: `{item.recommendation}`",
                f"- retrieval_count: `{item.retrieval_count}`",
                f"- outcomes: `+{item.positive_outcomes} / -{item.negative_outcomes}`",
                f"- strength: `{item.strength:.4f}`",
                f"- reward_factor: `{item.reward_factor:.4f}`",
                f"- recency: `{item.recency:.4f}`",
                f"- review_due: `{item.review_due}`",
                "",
            ]
        )
    return "\n".join(lines)


def display_path(path: Path, root: Path) -> str:
    try:
        return repo_relative_path(path, root)
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seen = subparsers.add_parser("mark-seen")
    seen.add_argument("--id", required=True)
    seen.add_argument("--query", default="")
    seen.add_argument("--score", type=float, default=None)
    seen.add_argument("--used-by", default=None)
    seen.add_argument("--json", action="store_true")
    outcome = subparsers.add_parser("outcome")
    target = outcome.add_mutually_exclusive_group()
    target.add_argument("--id", default=None)
    target.add_argument("--last", action="store_true")
    group = outcome.add_mutually_exclusive_group(required=True)
    group.add_argument("--good", action="store_true")
    group.add_argument("--bad", action="store_true")
    outcome.add_argument("--note", default=None)
    outcome.add_argument("--json", action="store_true")
    scores = subparsers.add_parser("scores", help="Compute lifecycle scores.")
    scores.add_argument("--output", default=str(LIFECYCLE_JSON))
    scores.add_argument("--include-sensitive", action="store_true", help="Include private and sensitive memory metadata in the generated local score export.")
    scores.add_argument("--json", action="store_true")
    report = subparsers.add_parser("report", help="Write a lifecycle score report.")
    report.add_argument("--output", default=str(LIFECYCLE_REPORT))
    report.add_argument("--report-path", default=None, help="Report path inside the memory root.")
    report.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    try:
        if args.command == "mark-seen":
            result = mark_seen(root, args.id, query=args.query, score=args.score, used_by=args.used_by)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"{result['created_at']} {result['memory_id']}")
            return 0
        if args.command == "outcome":
            result = record_outcome(
                root,
                None if args.last else args.id,
                "good" if args.good else "bad",
                note=args.note,
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"{result['created_at']} {result['memory_id']}")
            return 0
        if args.command == "scores":
            path, rows = write_lifecycle_scores(root, Path(args.output), include_sensitive=args.include_sensitive)
            if args.json:
                print(json.dumps({"path": display_path(path, root), "scores": [asdict(row) for row in rows]}, indent=2))
            else:
                print(f"Wrote {display_path(path, root)} ({len(rows)} score(s))")
            return 0
        if args.command == "report":
            path, rows = write_lifecycle_report(root, Path(args.report_path or args.output))
            if args.json:
                print(json.dumps({"path": display_path(path, root), "scores": [asdict(row) for row in rows]}, indent=2))
            else:
                print(f"Wrote {display_path(path, root)} ({len(rows)} score(s))")
            return 0
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error("unhandled command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
