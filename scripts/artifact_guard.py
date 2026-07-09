#!/usr/bin/env python3
"""Fail when generated local artifacts are staged for commit."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess

from memorylib import repo_root


ROOT_GENERATED_DIRS = {
    "indexes": "generated SQLite/vector index artifact",
    "reports": "generated report artifact",
    "distilled": "generated context export",
    "working": "generated working-session artifact",
    "build": "build output",
    "dist": "distribution build output",
}

GENERATED_SEGMENTS = {
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    ".mypy_cache": "mypy cache",
}

GENERATED_SUFFIXES = {
    ".sqlite": "generated SQLite database",
    ".sqlite-shm": "generated SQLite shared-memory file",
    ".sqlite-wal": "generated SQLite write-ahead log",
    ".db": "generated database",
    ".pyc": "Python bytecode cache",
    ".pyo": "Python bytecode cache",
}


@dataclass(frozen=True)
class ArtifactIssue:
    path: str
    reason: str


def normalize_git_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def classify_generated_artifact(path: str) -> str | None:
    normalized = normalize_git_path(path)
    if not normalized:
        return None

    parts = normalized.split("/")
    root_segment = parts[0]
    if root_segment in ROOT_GENERATED_DIRS:
        return ROOT_GENERATED_DIRS[root_segment]

    for segment in parts:
        if segment in GENERATED_SEGMENTS:
            return GENERATED_SEGMENTS[segment]
        if segment.endswith(".egg-info"):
            return "Python package metadata build output"

    for suffix, reason in GENERATED_SUFFIXES.items():
        if normalized.endswith(suffix):
            return reason

    return None


def validate_artifact_paths(paths: list[str]) -> list[ArtifactIssue]:
    issues: list[ArtifactIssue] = []
    for path in paths:
        reason = classify_generated_artifact(path)
        if reason:
            issues.append(ArtifactIssue(normalize_git_path(path), reason))
    return issues


def staged_paths(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def validate_staged_artifacts(root: Path) -> list[ArtifactIssue]:
    try:
        paths = staged_paths(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [ArtifactIssue("<git>", f"could not inspect staged files: {exc}")]
    return validate_artifact_paths(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_staged_artifacts(root)

    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print("Generated artifacts are staged and must be unstaged before release:")
        for issue in issues:
            print(f"- {issue.path}: {issue.reason}")
    else:
        print("No generated artifacts are staged.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
