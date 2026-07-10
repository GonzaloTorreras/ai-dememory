#!/usr/bin/env python3
"""Validate deterministic tag-driven ai-dememory releases."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib


TAG_RE = re.compile(r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?)$")
EXPECTED_REPOSITORY = "GonzaloTorreras/ai-dememory"


@dataclass(frozen=True)
class ReleaseIdentity:
    tag: str
    version: str
    prerelease: bool
    changelog_heading: str
    commit: str | None = None


def project_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def changelog_heading(root: Path, version: str) -> str:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"(?m)^## \[{re.escape(version)}\] - ([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})$", text)
    if not match:
        raise ValueError(f"CHANGELOG.md has no dated [{version}] release heading")
    date.fromisoformat(match.group(1))
    return match.group(0)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def validate_identity(root: Path, tag: str, *, version_only: bool = False) -> ReleaseIdentity:
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError("release tag must match vMAJOR.MINOR.PATCH or a PEP 440 prerelease")
    version = project_version(root)
    if match.group("version") != version:
        raise ValueError(f"tag {tag} does not match project version {version}")
    heading = changelog_heading(root, version)
    prerelease = bool(re.search(r"(?:a|b|rc)[0-9]+$", version))
    if version_only:
        return ReleaseIdentity(tag=tag, version=version, prerelease=prerelease, changelog_heading=heading)

    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository and repository != EXPECTED_REPOSITORY:
        raise ValueError(f"release repository must be {EXPECTED_REPOSITORY}, got {repository}")
    commit = git(root, "rev-parse", f"{tag}^{{commit}}")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", commit, "origin/main"], check=True)
    return ReleaseIdentity(tag=tag, version=version, prerelease=prerelease, changelog_heading=heading, commit=commit)


def write_github_output(path: str, identity: ReleaseIdentity) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"tag={identity.tag}\n")
        handle.write(f"version={identity.version}\n")
        handle.write(f"prerelease={'true' if identity.prerelease else 'false'}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--tag")
    parser.add_argument("--version-only", action="store_true")
    parser.add_argument("--github-output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    tag = args.tag or f"v{project_version(root)}"
    try:
        identity = validate_identity(root, tag, version_only=args.version_only)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"release identity validation failed: {exc}", file=sys.stderr)
        return 1
    if args.github_output:
        write_github_output(args.github_output, identity)
    if args.json:
        print(json.dumps(asdict(identity), indent=2))
    else:
        print(f"Release identity valid: {identity.tag} ({'prerelease' if identity.prerelease else 'stable'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
