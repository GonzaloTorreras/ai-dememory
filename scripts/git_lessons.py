#!/usr/bin/env python3
"""Capture review-first lesson candidates from recent git history."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from memorylib import repo_relative_path, repo_root, slugify
from secret_scan import scan_text


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fix": ("fix", "fixed", "bugfix", "patch"),
    "bug": ("bug", "error", "exception", "crash", "fault"),
    "revert": ("revert", "rollback", "back out"),
    "hotfix": ("hotfix", "urgent", "incident"),
    "migration": ("migration", "migrate", "schema", "database"),
    "ci": ("ci", "workflow", "actions", "pipeline"),
    "build": ("build", "compile", "packaging", "release"),
    "auth": ("auth", "login", "oauth", "permission"),
    "deploy": ("deploy", "deployment", "publish"),
    "regression": ("regression", "breaks", "broken"),
}
DEFAULT_CATEGORIES = ("fix", "bug", "revert", "hotfix", "migration", "ci", "build", "auth", "deploy", "regression")
MAX_COMMITS = 50


@dataclass(frozen=True)
class GitCommitLesson:
    repo: str
    sha: str
    subject: str
    body: str
    date: str
    categories: list[str]


def learn_git(
    root: Path,
    repos: list[Path],
    days: int = 7,
    limit: int = MAX_COMMITS,
    dry_run: bool = True,
) -> dict[str, object]:
    if days < 1:
        raise ValueError("days must be at least 1")
    lessons: list[GitCommitLesson] = []
    skipped: list[dict[str, str]] = []
    for repo in repos:
        try:
            lessons.extend(lesson_candidates_from_repo(repo, days=days, limit=limit))
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
            skipped.append({"repo": str(repo), "reason": str(exc)})

    written: list[str] = []
    candidates: list[GitCommitLesson] = []
    for lesson in lessons[:limit]:
        fingerprint = lesson_fingerprint(lesson)
        existing = existing_lesson_candidate(root, lesson, fingerprint)
        if existing is not None:
            skipped.append(
                {
                    "repo": lesson.repo,
                    "sha": lesson.sha,
                    "reason": "already captured",
                    "existing": repo_relative_path(existing, root),
                }
            )
            continue
        text = render_lesson_candidate(lesson, fingerprint=fingerprint)
        if scan_text(text, f"<git-lesson:{lesson.repo}:{lesson.sha}>"):
            skipped.append({"repo": lesson.repo, "sha": lesson.sha, "reason": f"secret-like lesson candidate {lesson.sha}"})
            continue
        candidates.append(lesson)
        if not dry_run:
            path = write_lesson_candidate(root, lesson, text, fingerprint)
            written.append(repo_relative_path(path, root))
    return {
        "days": days,
        "dry_run": dry_run,
        "examined": len(lessons),
        "written": written,
        "skipped": skipped,
        "candidates": [asdict(lesson) for lesson in candidates],
    }


def git_lesson_would_write_count(result: dict[str, object]) -> int:
    skipped_shas = {
        str(item.get("sha"))
        for item in result.get("skipped", [])
        if isinstance(item, dict) and item.get("sha")
    }
    return sum(
        1
        for candidate in result.get("candidates", [])
        if isinstance(candidate, dict) and str(candidate.get("sha")) not in skipped_shas
    )


def lesson_candidates_from_repo(repo: Path, days: int, limit: int = MAX_COMMITS) -> list[GitCommitLesson]:
    repo = repo.expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"repo does not exist: {repo}")
    if not is_git_repo(repo):
        raise ValueError(f"not a git repository: {repo}")
    output = run_git(
        repo,
        [
            "log",
            f"--since={days} days ago",
            f"-n{max(1, limit)}",
            "--date=short",
            "--pretty=format:%H%x1f%ad%x1f%s%x1f%b%x1e",
        ],
    )
    lessons: list[GitCommitLesson] = []
    for record in output.split("\x1e"):
        record = record.strip("\n\r")
        if not record:
            continue
        parts = record.split("\x1f", 3)
        if len(parts) != 4:
            continue
        sha, date, subject, body = (part.strip() for part in parts)
        categories = classify_commit(subject, body)
        if not categories:
            continue
        lessons.append(
            GitCommitLesson(
                repo=str(repo),
                sha=sha[:12],
                subject=subject,
                body=body,
                date=date,
                categories=categories,
            )
        )
    return lessons


def is_git_repo(repo: Path) -> bool:
    try:
        result = run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError:
        return False
    return result.strip().lower() == "true"


def run_git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def classify_commit(subject: str, body: str = "") -> list[str]:
    text = f"{subject}\n{body}".lower()
    categories = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword_matches(text, keyword) for keyword in keywords)
    ]
    return categories


def keyword_matches(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def lesson_fingerprint(lesson: GitCommitLesson) -> str:
    return hashlib.sha256((lesson.repo + lesson.sha + lesson.subject).encode("utf-8")).hexdigest()[:12]


def lesson_slug(lesson: GitCommitLesson) -> str:
    return slugify(f"{Path(lesson.repo).name}-{lesson.sha}", "git-lesson")


def existing_lesson_candidate(root: Path, lesson: GitCommitLesson, fingerprint: str) -> Path | None:
    inbox = root / "inbox" / "git-lessons"
    if not inbox.exists():
        return None
    matches = sorted(inbox.glob(f"*_{lesson_slug(lesson)}_{fingerprint}.md"))
    return matches[0] if matches else None


def safe_git_lessons_dir(root: Path) -> Path:
    root = root.resolve()
    inbox = root / "inbox"
    capture_dir = inbox / "git-lessons"
    for component in (inbox, capture_dir):
        if component.is_symlink():
            raise ValueError("git lesson path must not contain symlinks")
        if component.exists():
            try:
                component.resolve().relative_to(root)
            except ValueError as exc:
                raise ValueError("git lesson path must stay inside the memory root") from exc

    capture_dir.mkdir(parents=True, exist_ok=True)
    for component in (inbox, capture_dir):
        if component.is_symlink():
            raise ValueError("git lesson path must not contain symlinks")
        try:
            component.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("git lesson path must stay inside the memory root") from exc
    return capture_dir


def render_lesson_candidate(lesson: GitCommitLesson, fingerprint: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    created = now.date().isoformat()
    review_after = created
    categories = ", ".join(slugify(category, "lesson") for category in lesson.categories)
    title = f"Git lesson candidate {lesson.sha}"
    digest = fingerprint or lesson_fingerprint(lesson)
    body_excerpt = lesson.body[:2000].strip()
    body_section = f"\n\nCommit body:\n\n```text\n{body_excerpt}\n```" if body_excerpt else ""
    return f"""---
id: git_lesson_{slugify(Path(lesson.repo).name, 'repo')}_{lesson.sha}
title: "{title}"
type: project
status: proposed
scope: project
project: "{Path(lesson.repo).name}"
tags: [git, lesson, {categories}]
aliases: []
created_at: {created}
updated_at: {created}
confidence: 0.45
sensitivity: internal
source:
  kind: external
  ref: "git:{lesson.repo}:{lesson.sha}"
  fingerprint: "{digest}"
pin: false
decay: normal
review_after: {review_after}
---

# {title}

Repository: `{lesson.repo}`

Commit: `{lesson.sha}`

Date: `{lesson.date}`

Categories: `{", ".join(lesson.categories)}`

Subject: {lesson.subject}
{body_section}

Review this candidate before promoting a stable project memory.
"""


def write_lesson_candidate(root: Path, lesson: GitCommitLesson, text: str, fingerprint: str | None = None) -> Path:
    digest = fingerprint or lesson_fingerprint(lesson)
    slug = lesson_slug(lesson)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    inbox = safe_git_lessons_dir(root)
    path = inbox / f"{timestamp}_{slug}_{digest}.md"
    if path.exists() or path.is_symlink():
        raise ValueError("git lesson candidate path already exists")
    path.write_text(text, encoding="utf-8")
    return path


def parse_repos(repo: str | None, repos: str | None) -> list[Path]:
    values: list[str] = []
    if repo:
        values.append(repo)
    if repos:
        values.extend(item.strip() for item in repos.split(",") if item.strip())
    return [Path(value) for value in values] or [Path.cwd()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Memory repository root. Defaults to this repo.")
    parser.add_argument("--git", action="store_true", help="Learn from git commit history.")
    parser.add_argument("--days", type=int, default=7, help="Look back this many days.")
    parser.add_argument("--repo", default=None, help="One git repository to inspect.")
    parser.add_argument("--repos", default=None, help="Comma-separated git repositories to inspect.")
    parser.add_argument("--limit", type=int, default=MAX_COMMITS, help="Maximum lesson candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Preview candidates without writing files. This is the default.")
    parser.add_argument("--write", action="store_true", help="Write reviewed lesson candidates to inbox/git-lessons/.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    if not args.git:
        print("learn currently requires --git", file=sys.stderr)
        return 2
    if args.write and args.dry_run:
        parser.error("--write cannot be combined with --dry-run")
    root = repo_root(args.root)
    try:
        result = learn_git(root, parse_repos(args.repo, args.repos), days=args.days, limit=args.limit, dry_run=not args.write)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["dry_run"]:
            print(f"Would write {git_lesson_would_write_count(result)} git lesson candidate(s).")
        else:
            print(f"Wrote {len(result['written'])} git lesson candidate(s) to inbox/git-lessons/.")
        if result["skipped"]:
            print(f"Skipped {len(result['skipped'])} repo/item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
