#!/usr/bin/env python3
"""Evaluate whether vector search is justified by recall fixtures."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from eval_recall import DEFAULT_FIXTURES, evaluate, summary
from memorylib import repo_relative_path, repo_root
from secret_scan import scan_text


DEFAULT_RECALL_THRESHOLD = 0.85
DEFAULT_MIN_FAILED_CASES = 2
DEFAULT_VECTOR_REPORT = Path("reports/vector-readiness.md")


@dataclass(frozen=True)
class VectorReadiness:
    decision: str
    rationale: str
    recall_threshold: float
    min_failed_cases: int
    recall: dict[str, Any]
    failed_case_ids: list[str]
    generated_at: str


def evaluate_vector_readiness(
    root: Path,
    fixtures_path: Path | None = None,
    recall_threshold: float = DEFAULT_RECALL_THRESHOLD,
    min_failed_cases: int = DEFAULT_MIN_FAILED_CASES,
) -> VectorReadiness:
    if not 0.0 <= recall_threshold <= 1.0:
        raise ValueError("recall threshold must be between 0.0 and 1.0")
    if min_failed_cases < 1:
        raise ValueError("min failed cases must be at least 1")
    fixtures = fixtures_path or root / DEFAULT_FIXTURES
    if not fixtures.is_absolute():
        fixtures = root / fixtures
    results = evaluate(root, fixtures)
    stats = summary(results)
    failed_ids = [result.id for result in results if not result.passed]
    recall_value = float(stats["recall"])
    failed_count = int(stats["failed_cases"])

    if recall_value < recall_threshold and failed_count >= min_failed_cases:
        decision = "eligible_for_vector_experiment"
        rationale = "Recall fixtures are below threshold and enough cases fail to justify a measured vector experiment."
    elif failed_count:
        decision = "investigate_fts_first"
        rationale = "Some recall fixtures fail, but the configured threshold is not met; improve metadata, aliases, or fixtures first."
    else:
        decision = "not_justified"
        rationale = "All recall fixtures pass; keep SQLite FTS as the default retrieval layer."

    return VectorReadiness(
        decision=decision,
        rationale=rationale,
        recall_threshold=recall_threshold,
        min_failed_cases=min_failed_cases,
        recall=stats,
        failed_case_ids=failed_ids,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )


def resolve_repo_path(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def write_vector_report(
    root: Path,
    readiness: VectorReadiness,
    report_path: str | Path = DEFAULT_VECTOR_REPORT,
) -> Path:
    target = resolve_repo_path(root, report_path)
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("report path must stay inside the memory root") from exc
    text = f"""# Vector Readiness

Generated: `{readiness.generated_at}`

Decision: `{readiness.decision}`

{readiness.rationale}

## Thresholds

- recall threshold: `{readiness.recall_threshold}`
- minimum failed cases: `{readiness.min_failed_cases}`

## Recall Summary

```json
{json.dumps(readiness.recall, indent=2)}
```

## Failed Cases

{failed_cases_markdown(readiness.failed_case_ids)}

## Rule

Do not implement or enable vector search until this report shows
`eligible_for_vector_experiment` and the user explicitly approves the added
dependency and privacy model.
"""
    if scan_text(text, "<vector-readiness-report>"):
        raise ValueError("vector readiness report rejected by secret scan")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def failed_cases_markdown(case_ids: list[str]) -> str:
    if not case_ids:
        return "No failed recall fixtures."
    return "\n".join(f"- `{case_id}`" for case_id in case_ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Evaluate vector readiness.")
    status.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Recall fixture JSON path.")
    status.add_argument("--recall-threshold", type=float, default=DEFAULT_RECALL_THRESHOLD)
    status.add_argument("--min-failed-cases", type=int, default=DEFAULT_MIN_FAILED_CASES)
    status.add_argument("--write-report", action="store_true", help="Write reports/vector-readiness.md.")
    status.add_argument("--report-path", default=str(DEFAULT_VECTOR_REPORT), help="Report path inside the memory root.")
    status.add_argument("--json", action="store_true", help="Emit JSON output.")

    args = parser.parse_args(argv)
    root = repo_root(args.root)

    try:
        readiness = evaluate_vector_readiness(
            root,
            Path(args.fixtures),
            recall_threshold=args.recall_threshold,
            min_failed_cases=args.min_failed_cases,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        report_path = write_vector_report(root, readiness, args.report_path) if args.write_report else None
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    output = asdict(readiness)
    if report_path:
        output["report_path"] = repo_relative_path(report_path, root)

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"Vector readiness: {readiness.decision}")
        print(readiness.rationale)
        if report_path:
            print(f"Wrote {repo_relative_path(report_path, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
