#!/usr/bin/env python3
"""Validate the AI-operated release and manual recovery workflows."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


# Kept for the compatibility publish-plan API, which now describes recovery.
WORKFLOW_PATH = Path(".github/workflows/publish.yml")
RELEASE_WORKFLOW_PATH = Path(".github/workflows/release.yml")
TAGGER_WORKFLOW_PATH = Path(".github/workflows/tag-release.yml")
REQUIRED_PREFLIGHT_COMMANDS = (
    "python -m compileall -q scripts mcp/server ai_dememory_tool",
    "python scripts/ai_dememory.py publish-guard",
    "python scripts/ai_dememory.py artifact-guard",
    "python scripts/ai_dememory.py validate",
    "python scripts/ai_dememory.py secret-scan",
    "python scripts/ai_dememory.py verify-mcp",
    "python scripts/ai_dememory.py release-check",
    "python scripts/ai_dememory.py install-smoke",
    "python scripts/ai_dememory.py package-build-smoke --check-clean",
    "python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:publish",
    'python scripts/ai_dememory.py publish-plan --repository "$PUBLISH_REPOSITORY" --pr-url "$AI_DEMEMORY_PR_URL" --strict',
)


@dataclass(frozen=True)
class PublishGuardIssue:
    target: str
    message: str


def validate_publish_workflow(root: Path) -> list[PublishGuardIssue]:
    issues: list[PublishGuardIssue] = []
    try:
        release_text = (root / RELEASE_WORKFLOW_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        return [PublishGuardIssue(str(RELEASE_WORKFLOW_PATH), "canonical release workflow is missing")]
    issues.extend(validate_publish_workflow_text(release_text))

    try:
        tagger_text = (root / TAGGER_WORKFLOW_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        issues.append(PublishGuardIssue(str(TAGGER_WORKFLOW_PATH), "green-CI tagger workflow is missing"))
    else:
        if "workflow_run:" not in tagger_text or 'workflows: ["CI"]' not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:on", "tagger must run only after the canonical CI workflow"))
        if "github.event.workflow_run.conclusion == 'success'" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:ci", "tagger must require successful CI"))
        if "github.event.workflow_run.event == 'push'" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:event", "tagger must accept only CI runs triggered by a push"))
        if "github.event.workflow_run.head_repository.full_name == github.repository" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:repository", "tagger must reject CI runs from forks"))
        if "vars.AI_RELEASE_ENABLED == 'true'" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:migration", "tagger must retain the one-time migration enable switch"))
        if "python scripts/ai_release_guard.py --version-only" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:identity", "tagger must validate version and changelog before tagging"))
        if "git push origin \"$RELEASE_TAG\"" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:tag", "tagger must push only the resolved release tag"))
        if 'test "$(git rev-parse "$RELEASE_TAG^{commit}")" = "$(git rev-parse HEAD)"' not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:collision", "an existing tag must resolve to the verified commit"))

    try:
        recovery_text = (root / WORKFLOW_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        issues.append(PublishGuardIssue(str(WORKFLOW_PATH), "manual recovery workflow is missing"))
    else:
        if "workflow_dispatch:" not in recovery_text:
            issues.append(PublishGuardIssue("publish.yml:on", "recovery workflow must be manually dispatched"))
        if re.search(r"(?m)^\s+(push|pull_request|pull_request_target|schedule):\s*$", recovery_text):
            issues.append(PublishGuardIssue("publish.yml:on", "recovery workflow must not run automatically"))
        if re.search(r"(?im)^\s*(password|api[_-]?token|pypi[_-]?token)\s*:", recovery_text):
            issues.append(PublishGuardIssue("publish.yml:secrets", "recovery workflow must not configure stored PyPI tokens"))
    return issues


def validate_publish_workflow_text(text: str) -> list[PublishGuardIssue]:
    """Validate canonical release workflow text without parsing untrusted YAML."""
    issues: list[PublishGuardIssue] = []
    required_fragments = {
        "release.yml:on": ("tags:", '"v*"'),
        "release.yml:concurrency": ("concurrency:", "cancel-in-progress: false"),
        "release.yml:identity": ("python scripts/ai_release_guard.py --tag", "fetch-depth: 0"),
        "release.yml:tests": ("python -m unittest discover -s tests", "release_artifact_smoke.py"),
        "release.yml:build-once": ("python -m build --no-isolation", "python -m twine check dist/*"),
        "release.yml:checksums": ("SHA256SUMS", "sha256sum dist/*"),
        "release.yml:attestation": ("actions/attest@f6bf1532d7d6793fce74eac584813a8eee607999", "attestations: write"),
        "release.yml:oidc": ("environment:\n      name: pypi", "id-token: write"),
        "release.yml:testpypi": ("environment:\n      name: testpypi", "https://test.pypi.org/legacy/"),
        "release.yml:publisher": ("pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b", "packages-dir:"),
        "release.yml:postpublish": (
            "Verify the published package from its index",
            "GH_REPO: ${{ github.repository }}",
            "gh release create",
        ),
    }
    for target, fragments in required_fragments.items():
        for fragment in fragments:
            if fragment not in text:
                issues.append(PublishGuardIssue(target, f"canonical release workflow is missing: {fragment}"))
    if "workflow_dispatch:" not in text or "recover-$RELEASE_TAG" not in text:
        issues.append(PublishGuardIssue("release.yml:recovery", "recovery must require confirm=recover-<immutable-tag>"))
    if "pull_request_target:" in text or re.search(r"(?m)^\s+schedule:\s*$", text):
        issues.append(PublishGuardIssue("release.yml:on", "release workflow must not use pull_request_target or schedule"))
    if re.search(r"(?im)^\s*(password|api[_-]?token|pypi[_-]?token)\s*:", text):
        issues.append(PublishGuardIssue("release.yml:secrets", "release workflow must not configure stored PyPI tokens"))
    if text.count("python -m build --no-isolation") != 1:
        issues.append(PublishGuardIssue("release.yml:build-once", "release distributions must be built exactly once"))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)
    issues = validate_publish_workflow(repo_root(args.root))
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"Publish workflow guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("AI-operated release workflow guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
