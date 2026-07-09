#!/usr/bin/env python3
"""Plan a manual TestPyPI or PyPI publish without uploading packages."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tomllib
from typing import Any
from urllib.parse import urlparse

from memorylib import repo_root
from manual_acceptance import ACCEPTANCE_ITEMS
from publish_guard import REQUIRED_PREFLIGHT_COMMANDS, WORKFLOW_PATH, validate_publish_workflow
from release_evidence import build_release_evidence, markdown_code_span


REPOSITORIES = ("testpypi", "pypi")
WORKFLOW_URL_PLACEHOLDER = "https://github.com/<owner>/<repo>/actions/workflows/publish.yml"
TESTPYPI_DEFERRED_ACCEPTANCE_ITEMS = {ACCEPTANCE_ITEMS["testpypi-publish"]}


def publish_plan(
    root: Path,
    repository: str = "testpypi",
    pr_url: str | None = None,
    command: str = "ai-dememory",
) -> dict[str, Any]:
    if repository not in REPOSITORIES:
        raise ValueError("repository must be testpypi or pypi")
    guard_issues = validate_publish_workflow(root)
    expected_pr_repo = publish_owner_repo(root)
    release_error: str | None = None
    try:
        evidence = build_release_evidence(root, pr_url=pr_url)
        release_available = True
        release_ready = evidence.release_ready
        release_blockers = list(evidence.release_blockers)
        publish_blockers = publish_readiness_blockers(
            repository,
            guard_issues,
            release_blockers,
            pr_url=pr_url,
            expected_owner_repo=expected_pr_repo,
        )
        blocker_ids = [str(blocker.get("id")) for blocker in release_blockers]
        publish_blocker_ids = [str(blocker.get("id")) for blocker in publish_blockers]
        blocker_count = len(release_blockers)
        publish_blocker_count = len(publish_blockers)
        manual_remaining = len(evidence.manual_acceptance_remaining)
        recall_status = evidence.recall_fixture_freshness.get("status")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        release_available = False
        release_ready = False
        release_error = str(exc)
        release_blockers = [
            {
                "id": "release_evidence_unavailable",
                "kind": "repository",
                "summary": "Release evidence is unavailable.",
                "count": 1,
                "items": [release_error],
            }
        ]
        publish_blockers = publish_readiness_blockers(
            repository,
            guard_issues,
            release_blockers,
            pr_url=pr_url,
            expected_owner_repo=expected_pr_repo,
        )
        blocker_ids = ["release_evidence_unavailable"]
        publish_blocker_ids = [str(blocker.get("id")) for blocker in publish_blockers]
        blocker_count = 1
        publish_blocker_count = len(publish_blockers)
        manual_remaining = None
        recall_status = "unavailable"
    publish_ready = release_available and publish_blocker_count == 0
    dispatch_inputs = {"repository": repository, "confirm": "publish", "pr_url": pr_url or "<pr-url>"}
    preflight_base = shlex.split(command)
    preflight_commands = [
        preflight_base + shlex.split(required)[2:]
        if required.startswith("python scripts/ai_dememory.py ")
        else shlex.split(required)
        for required in REQUIRED_PREFLIGHT_COMMANDS
    ]
    return {
        "root": str(root),
        "workflow": WORKFLOW_PATH.as_posix(),
        "repository": repository,
        "target_environment": repository,
        "dispatch_inputs": dispatch_inputs,
        "mutates_system": False,
        "runs_commands": True,
        "runs_publish_commands": False,
        "runs_preflight_commands": False,
        "writes_files": False,
        "publishes_package": False,
        "local_inspection_commands": [
            "git status/branch/head through release evidence",
            "pyproject Repository URL, then git remote get-url origin for workflow_url and PR URL repository validation",
        ],
        "requires_manual_dispatch": True,
        "requires_confirmation": True,
        "requires_pr_url": True,
        "uses_trusted_publishing": True,
        "guard_issue_count": len(guard_issues),
        "guard_issues": [asdict(issue) for issue in guard_issues],
        "release_evidence_available": release_available,
        "release_evidence_error": release_error,
        "release_ready": release_ready,
        "publish_ready": publish_ready,
        "release_blocker_count": blocker_count,
        "release_blocker_ids": blocker_ids,
        "publish_blocker_count": publish_blocker_count,
        "publish_blocker_ids": publish_blocker_ids,
        "publish_blockers": publish_blockers,
        "deferred_manual_acceptance_items": sorted(TESTPYPI_DEFERRED_ACCEPTANCE_ITEMS)
        if repository == "testpypi"
        else [],
        "manual_acceptance_remaining_count": manual_remaining,
        "recall_fixture_status": recall_status,
        "preflight_commands": preflight_commands,
        "workflow_url": publish_workflow_url(root),
        "next_actions": publish_plan_next_actions(
            repository,
            guard_issues,
            release_available,
            release_ready,
            blocker_ids,
            publish_ready,
            publish_blocker_ids,
        ),
    }


def publish_readiness_blockers(
    repository: str,
    guard_issues: list[Any],
    release_blockers: list[dict[str, Any]],
    *,
    pr_url: str | None = None,
    expected_owner_repo: str | None = None,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if guard_issues:
        blockers.append(
            {
                "id": "publish_guard_issues",
                "kind": "publish_workflow",
                "summary": "Publish workflow guard issues must be fixed before dispatch.",
                "count": len(guard_issues),
                "items": [asdict(issue) for issue in guard_issues],
            }
        )
    pr_url_issue = publish_pr_url_issue(pr_url, expected_owner_repo=expected_owner_repo)
    if pr_url_issue is not None:
        blockers.append(pr_url_issue)

    for blocker in release_blockers:
        blocker_id = str(blocker.get("id"))
        if repository == "testpypi" and blocker_id == "manual_acceptance_remaining":
            remaining = [
                item
                for item in list(blocker.get("items") or [])
                if item not in TESTPYPI_DEFERRED_ACCEPTANCE_ITEMS
            ]
            if remaining:
                filtered = dict(blocker)
                filtered["count"] = len(remaining)
                filtered["items"] = remaining
                blockers.append(filtered)
            continue
        blockers.append(blocker)
    return blockers


def github_pr_url_parts(pr_url: str) -> tuple[str, int] | None:
    if any(character.isspace() for character in pr_url):
        return None
    parsed = urlparse(pr_url)
    parts = parsed.path.split("/")
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return None
    if parsed.query or parsed.fragment:
        return None
    if len(parts) != 5 or parts[0] != "" or parts[3] != "pull" or not parts[4].isdigit():
        return None
    pr_number = int(parts[4])
    if pr_number <= 0:
        return None
    return f"{parts[1]}/{parts[2]}", pr_number


def publish_pr_url_issue(pr_url: str | None, *, expected_owner_repo: str | None = None) -> dict[str, Any] | None:
    clean = pr_url.strip() if isinstance(pr_url, str) else ""
    if not clean or clean == "<pr-url>":
        return {
            "id": "pr_url_required",
            "kind": "publish_review",
            "summary": "A GitHub PR URL is required before publish workflow dispatch.",
            "count": 1,
            "items": ["Set AI_DEMEMORY_PR_URL or pass --pr-url with the release PR URL."],
        }
    parts = github_pr_url_parts(clean)
    if parts is None:
        return {
            "id": "pr_url_required",
            "kind": "publish_review",
            "summary": "Publish PR URL must be a canonical GitHub HTTPS pull request URL.",
            "count": 1,
            "items": [clean],
        }
    actual_owner_repo, pr_number = parts
    if expected_owner_repo and actual_owner_repo.lower() != expected_owner_repo.lower():
        return {
            "id": "pr_url_required",
            "kind": "publish_review",
            "summary": "Publish PR URL must belong to this repository.",
            "count": 1,
            "items": [f"expected {expected_owner_repo}; got {actual_owner_repo}/pull/{pr_number}"],
        }
    return None


def publish_workflow_url(root: Path) -> str:
    owner_repo = publish_owner_repo(root)
    if owner_repo is None:
        return WORKFLOW_URL_PLACEHOLDER
    return f"https://github.com/{owner_repo}/actions/workflows/{WORKFLOW_PATH.name}"


def publish_owner_repo(root: Path) -> str | None:
    owner_repo = owner_repo_from_project_metadata(root)
    if owner_repo is not None:
        return owner_repo
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return github_owner_repo_from_remote(completed.stdout.strip())


def owner_repo_from_project_metadata(root: Path) -> str | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    urls = data.get("project", {}).get("urls", {})
    if not isinstance(urls, dict):
        return None
    repository = urls.get("Repository") or urls.get("Homepage")
    if not isinstance(repository, str):
        return None
    return github_owner_repo_from_remote(repository)


def github_owner_repo_from_remote(remote_url: str) -> str | None:
    normalized = remote_url.strip()
    if not normalized:
        return None
    if normalized.startswith("git@github.com:"):
        path = normalized.split(":", 1)[1]
    else:
        parsed = urlparse(normalized)
        if parsed.hostname != "github.com":
            return None
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return "/".join(parts)


def publish_plan_next_actions(
    repository: str,
    guard_issues: list[Any],
    release_available: bool,
    release_ready: bool,
    blocker_ids: list[str],
    publish_ready: bool | None = None,
    publish_blocker_ids: list[str] | None = None,
) -> list[str]:
    actions: list[str] = []
    effective_publish_ready = release_ready if publish_ready is None else publish_ready
    effective_blocker_ids = blocker_ids if publish_blocker_ids is None else publish_blocker_ids
    if guard_issues:
        actions.append("Fix publish workflow guard issues before dispatching the publish workflow.")
    if not release_available:
        actions.append("Run publish planning from a git distribution checkout with release evidence available.")
    if not effective_publish_ready:
        actions.append("Resolve target publish readiness blockers before dispatching the publish workflow.")
    if "manual_acceptance_remaining" in effective_blocker_ids:
        actions.append("Record reviewed passing manual acceptance evidence before publishing.")
    if "recall_fixture_review" in effective_blocker_ids:
        actions.append("Promote or reject reviewed recall misses before publishing.")
    if repository == "testpypi" and not release_ready:
        actions.append("TestPyPI may defer only the TestPyPI publish acceptance record; all other release blockers still apply.")
    if repository == "pypi":
        actions.append("Publish to TestPyPI and verify install evidence before publishing to PyPI.")
    actions.append("Dispatch the publish workflow manually only after explicit human approval.")
    return actions


def render_text(plan: dict[str, Any]) -> str:
    lines = [
        "# Publish Plan",
        "",
        f"- repository: `{plan['repository']}`",
        f"- workflow: `{plan['workflow']}`",
        f"- target_environment: `{plan['target_environment']}`",
        f"- publishes_package: `{str(plan['publishes_package']).lower()}`",
        f"- release_ready: `{str(plan['release_ready']).lower()}`",
        f"- publish_ready: `{str(plan['publish_ready']).lower()}`",
        f"- guard_issue_count: `{plan['guard_issue_count']}`",
        f"- release_blocker_count: `{plan['release_blocker_count']}`",
        f"- publish_blocker_count: `{plan['publish_blocker_count']}`",
        "",
        "## Dispatch Inputs",
        "",
    ]
    for name, value in plan["dispatch_inputs"].items():
        lines.append(f"- {name}: {markdown_code_span(str(value))}")
    lines.extend(["", "## Preflight Commands", ""])
    for command in plan["preflight_commands"]:
        lines.append(f"- `{shlex.join(command)}`")
    lines.extend(["", "## Next Actions", ""])
    for action in plan["next_actions"]:
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--repository", choices=REPOSITORIES, default="testpypi")
    parser.add_argument("--pr-url", default=None, help="PR URL to include in release evidence.")
    parser.add_argument("--command", default="ai-dememory", help="Command name for preflight command arrays.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero unless the target publish plan is ready.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        plan = publish_plan(
            root,
            repository=args.repository,
            pr_url=args.pr_url or os.environ.get("AI_DEMEMORY_PR_URL") or None,
            command=args.command,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(render_text(plan), end="")
    return 0 if not args.strict or plan["publish_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
