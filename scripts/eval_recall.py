#!/usr/bin/env python3
"""Evaluate memory search against curated recall fixtures."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any

from memorylib import repo_root
from search_memory import search


DEFAULT_FIXTURES = Path("quality/recall-fixtures.json")


@dataclass(frozen=True)
class FixtureResult:
    id: str
    query: str
    expected_ids: list[str]
    returned_ids: list[str]
    min_rank: int
    passed: bool
    missing_ids: list[str]


def load_fixtures(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("recall fixture file must contain a JSON array")
    fixtures: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"fixture #{index} must be an object")
        fixture_id = item.get("id")
        query = item.get("query")
        expected_ids = item.get("expected_ids")
        min_rank = item.get("min_rank", 5)
        include_sensitive = item.get("include_sensitive", False)
        for label, value in (("id", fixture_id), ("query", query)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"fixture #{index} missing non-empty {label}")
        if not isinstance(expected_ids, list) or not expected_ids or not all(
            isinstance(value, str) and value.strip() for value in expected_ids
        ):
            raise ValueError(f"fixture {fixture_id} expected_ids must be a non-empty string array")
        if not isinstance(min_rank, int) or min_rank < 1:
            raise ValueError(f"fixture {fixture_id} min_rank must be an integer >= 1")
        if not isinstance(include_sensitive, bool):
            raise ValueError(f"fixture {fixture_id} include_sensitive must be boolean")
        fixtures.append(item)
    return fixtures


def evaluate(root: Path, fixtures_path: Path, limit: int | None = None) -> list[FixtureResult]:
    fixtures = load_fixtures(fixtures_path)
    results: list[FixtureResult] = []
    for fixture in fixtures:
        min_rank = int(fixture.get("min_rank", 5))
        search_limit = max(limit or min_rank, min_rank)
        returned = search(
            str(fixture["query"]),
            root,
            limit=search_limit,
            include_sensitive=bool(fixture.get("include_sensitive", False)),
        )
        returned_ids = [result.id for result in returned]
        top_ids = returned_ids[:min_rank]
        expected_ids = list(fixture["expected_ids"])
        missing_ids = [memory_id for memory_id in expected_ids if memory_id not in top_ids]
        results.append(
            FixtureResult(
                id=str(fixture["id"]),
                query=str(fixture["query"]),
                expected_ids=expected_ids,
                returned_ids=returned_ids,
                min_rank=min_rank,
                passed=not missing_ids,
                missing_ids=missing_ids,
            )
        )
    return results


def summary(results: list[FixtureResult]) -> dict[str, Any]:
    total_expected = sum(len(result.expected_ids) for result in results)
    found_expected = sum(len(result.expected_ids) - len(result.missing_ids) for result in results)
    passed = [result for result in results if result.passed]
    return {
        "status": "evaluated" if total_expected else "insufficient_evidence",
        "total_cases": len(results),
        "passed_cases": len(passed),
        "failed_cases": len(results) - len(passed),
        "total_expected": total_expected,
        "found_expected": found_expected,
        "recall": round(found_expected / total_expected, 4) if total_expected else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Recall fixture JSON path.")
    parser.add_argument("--limit", type=int, default=None, help="Search limit override.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    fixtures_path = Path(args.fixtures)
    if not fixtures_path.is_absolute():
        fixtures_path = root / fixtures_path
    try:
        results = evaluate(root, fixtures_path, args.limit)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    data = {"summary": summary(results), "results": [asdict(result) for result in results]}
    failed = [result for result in results if not result.passed]
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        stats = data["summary"]
        if stats["recall"] is None:
            print("Recall fixtures: insufficient evidence (no expected retrievals)")
        else:
            print(
                "Recall fixtures: "
                f"{stats['passed_cases']}/{stats['total_cases']} passed, "
                f"recall={stats['recall']:.4f}"
            )
        for result in failed:
            print(
                f"FAIL {result.id}: missing {', '.join(result.missing_ids)} "
                f"within top {result.min_rank} for query `{result.query}`"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
