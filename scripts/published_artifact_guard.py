#!/usr/bin/env python3
"""Compare local release artifacts with an existing PyPI version."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


INDEXES = {
    "pypi": "https://pypi.org",
    "testpypi": "https://test.pypi.org",
}


def local_digests(dist: Path) -> dict[str, str]:
    artifacts = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise ValueError("expected exactly one wheel and one sdist")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts}


def published_digests(repository: str, version: str) -> dict[str, str] | None:
    url = f"{INDEXES[repository]}/pypi/ai-dememory/{version}/json"
    try:
        with urlopen(Request(url, headers={"User-Agent": "ai-dememory-release-guard/1"}), timeout=20) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return {item["filename"]: item["digests"]["sha256"] for item in payload.get("urls", [])}


def compare(dist: Path, repository: str, version: str) -> bool:
    local = local_digests(dist)
    remote = published_digests(repository, version)
    if remote is None:
        return False
    if local != remote:
        raise ValueError(f"published {repository} artifacts do not match local bundle: local={local}, remote={remote}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--repository", choices=sorted(INDEXES), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)
    try:
        published = compare(args.dist, args.repository, args.version)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"published artifact validation failed: {exc}", file=sys.stderr)
        return 1
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"published={'true' if published else 'false'}\n")
    print("published artifacts match" if published else "version is not published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
