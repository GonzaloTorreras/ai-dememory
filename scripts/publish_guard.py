#!/usr/bin/env python3
"""Validate the canonical release and legacy read-only preflight workflows."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


# Kept for the compatibility publish-plan API. This workflow must never publish.
WORKFLOW_PATH = Path(".github/workflows/publish.yml")
RELEASE_WORKFLOW_PATH = Path(".github/workflows/release.yml")
TAGGER_WORKFLOW_PATH = Path(".github/workflows/tag-release.yml")
WORKFLOW_DIR = Path(".github/workflows")
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


def workflow_events(text: str) -> set[str]:
    """Return direct children of a conventional top-level workflow ``on`` block."""
    match = re.search(r"(?m)^on:\s*(?:#.*)?$", text)
    if match is None:
        return set()
    remainder = text[match.end() :]
    next_top_level = re.search(r"(?m)^[A-Za-z0-9_.-]+:\s*", remainder)
    block = remainder[: next_top_level.start()] if next_top_level else remainder
    return set(re.findall(r"(?m)^ {2}([A-Za-z0-9_-]+):", block))


def validate_legacy_preflight_workflow_text(text: str) -> list[PublishGuardIssue]:
    """Require the legacy workflow to remain manual, read-only, and non-publishing."""
    issues: list[PublishGuardIssue] = []
    lowered = text.casefold()
    if workflow_events(text) != {"workflow_dispatch"}:
        issues.append(
            PublishGuardIssue(
                "publish.yml:on",
                "legacy preflight must be workflow_dispatch-only",
            )
        )
    if "inputs.confirm != 'preflight'" not in text:
        issues.append(PublishGuardIssue("publish.yml:confirmation", "legacy preflight must require confirm=preflight"))
    if "contents: read" not in text or "persist-credentials: false" not in text:
        issues.append(
            PublishGuardIssue(
                "publish.yml:permissions",
                "legacy preflight must use read-only contents permission and disable persisted checkout credentials",
            )
        )
    if re.search(r"(?m)^\s+[\w-]+:\s*write\s*$", text):
        issues.append(PublishGuardIssue("publish.yml:permissions", "legacy preflight must not grant write permissions"))
    if re.search(r"(?m)^\s+environment:\s*", text):
        issues.append(PublishGuardIssue("publish.yml:environment", "legacy preflight must not target publishing environments"))
    if re.search(r"(?im)^\s*(password|api[_-]?token|pypi[_-]?token)\s*:", text):
        issues.append(PublishGuardIssue("publish.yml:secrets", "legacy preflight must not configure stored PyPI tokens"))

    forbidden_fragments = {
        "OIDC publishing permission": "id-token: write",
        "PyPI publisher action": "pypa/gh-action-pypi-publish",
        "artifact upload": "actions/upload-artifact",
        "artifact download": "actions/download-artifact",
        "package upload command": "twine upload",
        "release creation": "gh release create",
        "Git push": "git push",
    }
    for label, fragment in forbidden_fragments.items():
        if fragment.casefold() in lowered:
            issues.append(PublishGuardIssue("publish.yml:non-publishing", f"legacy preflight must not contain {label}: {fragment}"))
    if "python scripts/ai_dememory.py publish-plan" not in text or "--strict" not in text:
        issues.append(PublishGuardIssue("publish.yml:preflight", "legacy preflight must run strict publish readiness planning"))
    return issues


def validate_publisher_inventory(workflows: dict[Path, str]) -> list[PublishGuardIssue]:
    """Reject package-publishing authority outside the canonical release workflow."""
    issues: list[PublishGuardIssue] = []
    exclusive_markers = {
        "OIDC write permission": "id-token: write",
        "PyPI publisher action": "pypa/gh-action-pypi-publish",
        "twine upload": "twine upload",
        "TestPyPI upload endpoint": "https://test.pypi.org/legacy/",
        "PyPI upload endpoint": "https://upload.pypi.org/",
        "GitHub Release creation": "gh release create",
        "uv package upload": "uv publish",
        "Poetry package upload": "poetry publish",
        "Flit package upload": "flit publish",
        "Hatch package upload": "hatch publish",
        "PDM package upload": "pdm publish",
        "npm package upload": "npm publish",
        "Cargo package upload": "cargo publish",
        "RubyGems package upload": "gem push",
        "stored GitHub secret reference": "${{ secrets.",
        "indexed GitHub secret reference": "${{ secrets[",
    }
    for path, text in workflows.items():
        normalized = Path(path).as_posix()
        if normalized == RELEASE_WORKFLOW_PATH.as_posix():
            continue
        lowered = text.casefold()
        for label, marker in exclusive_markers.items():
            if marker.casefold() in lowered:
                issues.append(
                    PublishGuardIssue(
                        f"{normalized}:publisher",
                        f"{label} is allowed only in {RELEASE_WORKFLOW_PATH.as_posix()}",
                    )
                )
        if re.search(r"(?im)^\s+name:\s*(testpypi|pypi)\s*$", text):
            issues.append(
                PublishGuardIssue(
                    f"{normalized}:environment",
                    f"package-index environments are allowed only in {RELEASE_WORKFLOW_PATH.as_posix()}",
                )
            )
        if re.search(r"(?im)^\s+packages:\s*write\s*$", text):
            issues.append(
                PublishGuardIssue(
                    f"{normalized}:permissions",
                    f"package-registry write permission is allowed only in {RELEASE_WORKFLOW_PATH.as_posix()}",
                )
            )
    return issues


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
        issues.append(PublishGuardIssue(str(TAGGER_WORKFLOW_PATH), "explicit release tagger workflow is missing"))
    else:
        if workflow_events(tagger_text) != {"workflow_dispatch"}:
            issues.append(
                PublishGuardIssue(
                    "tag-release.yml:on",
                    "tagger must be workflow_dispatch-only",
                )
            )
        if 'test "$RELEASE_CONFIRM" = "release-$RELEASE_TAG@$APPROVED_SHA"' not in tagger_text:
            issues.append(
                PublishGuardIssue(
                    "tag-release.yml:approval",
                    "tagger must require confirmation bound to the exact tag and commit",
                )
            )
        if "ref: ${{ inputs.approved_sha }}" not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:checkout", "tagger must check out the approved commit"))
        if 'gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq .sha' not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:main", "tagger must require the approved commit to be current main"))
        if (
            "actions/workflows/ci.yml/runs" not in tagger_text
            or '-f head_sha="$APPROVED_SHA"' not in tagger_text
            or 'select(.conclusion == "success")' not in tagger_text
        ):
            issues.append(PublishGuardIssue("tag-release.yml:ci", "tagger must require successful push CI for the approved commit"))
        if (
            'python scripts/ai_release_guard.py --tag "$RELEASE_TAG" --version-only'
            not in tagger_text
        ):
            issues.append(PublishGuardIssue("tag-release.yml:identity", "tagger must validate the approved tag, version, and changelog"))
        if (
            'gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs"' not in tagger_text
            or '-f ref="refs/tags/$RELEASE_TAG"' not in tagger_text
            or '-f object="$APPROVED_SHA"' not in tagger_text
        ):
            issues.append(
                PublishGuardIssue(
                    "tag-release.yml:tag",
                    "tagger must create only the resolved annotated tag through the GitHub API",
                )
            )
        if 'test "$(git rev-parse "$RELEASE_TAG^{commit}")" = "$APPROVED_SHA"' not in tagger_text:
            issues.append(PublishGuardIssue("tag-release.yml:collision", "an existing tag must resolve to the verified commit"))
        if "actions: read" not in tagger_text or "actions: write" in tagger_text:
            issues.append(
                PublishGuardIssue(
                    "tag-release.yml:permissions",
                    "tagger must keep Actions read-only so publication requires a separate owner dispatch",
                )
            )
        if "gh workflow run release.yml" in tagger_text:
            issues.append(
                PublishGuardIssue(
                    "tag-release.yml:dispatch",
                    "tagger must not dispatch the publisher automatically",
                )
            )

    try:
        legacy_text = (root / WORKFLOW_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        issues.append(PublishGuardIssue(str(WORKFLOW_PATH), "legacy read-only preflight workflow is missing"))
    else:
        issues.extend(validate_legacy_preflight_workflow_text(legacy_text))
    workflow_texts: dict[Path, str] = {}
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted((root / WORKFLOW_DIR).glob(pattern)):
            try:
                workflow_texts[path.relative_to(root)] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                issues.append(PublishGuardIssue(str(path.relative_to(root)), f"workflow cannot be inspected: {exc}"))
    issues.extend(validate_publisher_inventory(workflow_texts))
    return issues


def validate_publish_workflow_text(text: str) -> list[PublishGuardIssue]:
    """Validate canonical release workflow text without parsing untrusted YAML."""
    issues: list[PublishGuardIssue] = []
    lowered = text.casefold()
    required_fragments = {
        "release.yml:on": ("workflow_dispatch:", "intent:", "approved_sha:"),
        "release.yml:concurrency": ("concurrency:", "cancel-in-progress: false"),
        "release.yml:identity": ("python scripts/ai_release_guard.py --tag", "fetch-depth: 0"),
        "release.yml:tests": ("python -m unittest discover -s tests -t .", "release_artifact_smoke.py"),
        "release.yml:build-once": ("python -m build --no-isolation", "python -m twine check dist/*"),
        "release.yml:checksums": ("SHA256SUMS", "sha256sum dist/*"),
        "release.yml:attestation": ("actions/attest@f6bf1532d7d6793fce74eac584813a8eee607999", "attestations: write"),
        "release.yml:oidc": ("environment:\n      name: pypi", "id-token: write"),
        "release.yml:testpypi": ("environment:\n      name: testpypi", "https://test.pypi.org/legacy/"),
        "release.yml:publisher": ("pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b", "packages-dir:"),
        "release.yml:idempotence": (
            "published_artifact_guard.py",
            "steps.existing.outputs.published != 'true'",
        ),
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
    if (
        'test "$RELEASE_CONFIRM" = "$RELEASE_INTENT-$RELEASE_TAG@$APPROVED_SHA"'
        not in text
        or 'test "$(git rev-parse "$RELEASE_TAG^{commit}")" = "$APPROVED_SHA"'
        not in text
    ):
        issues.append(
            PublishGuardIssue(
                "release.yml:authorization",
                "publication and recovery must require an exact intent, tag, and commit confirmation",
            )
        )
    if workflow_events(text) != {"workflow_dispatch"}:
        issues.append(
            PublishGuardIssue(
                "release.yml:on",
                "canonical release must be workflow_dispatch-only",
            )
        )
    if re.search(r"(?im)^\s*(password|api[_-]?token|pypi[_-]?token)\s*:", text):
        issues.append(PublishGuardIssue("release.yml:secrets", "release workflow must not configure stored PyPI tokens"))
    if "${{ secrets." in lowered or "${{ secrets[" in lowered:
        issues.append(
            PublishGuardIssue(
                "release.yml:secrets",
                "canonical release must use OIDC and must not reference stored GitHub secrets",
            )
        )
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
