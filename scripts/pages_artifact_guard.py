#!/usr/bin/env python3
"""Fail closed unless ``site/`` is an exact, clean Pages artifact."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_PATH = Path("site")
REGULAR_FILE_MODE = "100644"


def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def parse_git_manifest(raw: bytes) -> tuple[dict[str, str], list[str]]:
    """Parse ``git ls-files --stage -z`` output for ``site/``."""

    entries: dict[str, str] = {}
    errors: list[str] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
            path = encoded_path.decode("utf-8", "surrogateescape").replace("\\", "/")
        except (ValueError, UnicodeError):
            errors.append("git manifest contains an invalid record")
            continue
        if not path.startswith("site/"):
            errors.append(f"tracked artifact entry escapes site/: {path!r}")
            continue
        relative = path.removeprefix("site/")
        if not relative or relative.startswith("/") or "/../" in f"/{relative}/":
            errors.append(f"tracked artifact entry has an invalid path: {path!r}")
            continue
        if stage != "0":
            errors.append(f"tracked artifact entry is unmerged at stage {stage}: {path}")
        if mode != REGULAR_FILE_MODE:
            errors.append(
                f"tracked artifact entry must be a regular 100644 file, found {mode}: {path}"
            )
        if len(object_id) != 40 or any(character not in "0123456789abcdef" for character in object_id):
            errors.append(f"tracked artifact entry has an invalid object id: {path}")
        if relative in entries:
            errors.append(f"tracked artifact entry is duplicated: {path}")
        entries[relative] = mode
    return entries, errors


def _git_bytes(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail or f"git {' '.join(arguments)} failed")
    return completed.stdout


def audit_artifact_tree(site_root: Path, tracked: dict[str, str]) -> list[str]:
    """Compare the filesystem tree with the tracked regular-file manifest."""

    errors: list[str] = []
    if not site_root.exists():
        return ["site/: artifact directory is missing"]
    if _is_link_like(site_root) or not site_root.is_dir():
        return ["site/: artifact root must be a real directory, not a link or junction"]

    actual_files: set[str] = set()
    actual_directories: set[str] = set()

    def walk(directory: Path) -> None:
        with os.scandir(directory) as children:
            for child in children:
                path = Path(child.path)
                relative = path.relative_to(site_root).as_posix()
                if _is_link_like(path):
                    errors.append(f"site/{relative}: links and junctions are forbidden")
                    continue
                if child.is_dir(follow_symlinks=False):
                    actual_directories.add(relative)
                    walk(path)
                    continue
                if not child.is_file(follow_symlinks=False):
                    errors.append(f"site/{relative}: only regular files are allowed")
                    continue
                # Path.stat uses the Windows handle path that reports the real
                # link count; DirEntry.stat may report zero on some runtimes.
                metadata = path.stat(follow_symlinks=False)
                if not stat.S_ISREG(metadata.st_mode):
                    errors.append(f"site/{relative}: only regular files are allowed")
                    continue
                if metadata.st_nlink > 1:
                    errors.append(f"site/{relative}: hard-linked files are forbidden")
                actual_files.add(relative)

    walk(site_root)
    tracked_files = set(tracked)
    for relative in sorted(tracked_files - actual_files):
        errors.append(f"site/{relative}: tracked file is missing from the artifact")
    for relative in sorted(actual_files - tracked_files):
        errors.append(f"site/{relative}: artifact file is not tracked by Git")

    expected_directories = {
        parent.as_posix()
        for relative in tracked_files
        for parent in Path(relative).parents
        if parent != Path(".")
    }
    for relative in sorted(actual_directories - expected_directories):
        errors.append(f"site/{relative}: artifact directory is not implied by tracked files")
    return sorted(set(errors))


def audit_pages_artifact(
    repo_root: Path = REPO_ROOT,
    *,
    require_clean: bool = True,
) -> list[str]:
    """Return deterministic errors for the exact checked-in Pages artifact."""

    root = repo_root.resolve()
    errors: list[str] = []
    try:
        tracked, manifest_errors = parse_git_manifest(
            _git_bytes(root, "ls-files", "--stage", "-z", "--", SITE_PATH.as_posix())
        )
    except RuntimeError as exc:
        return [f"site/: cannot read tracked artifact manifest: {exc}"]
    errors.extend(manifest_errors)
    if not tracked:
        errors.append("site/: tracked artifact manifest is empty")

    if require_clean:
        try:
            dirty = _git_bytes(
                root,
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--",
                SITE_PATH.as_posix(),
            )
        except RuntimeError as exc:
            errors.append(f"site/: cannot verify clean artifact state: {exc}")
        else:
            if dirty:
                errors.append("site/: artifact has modified, staged, or untracked content")

    errors.extend(audit_artifact_tree(root / SITE_PATH, tracked))
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors = audit_pages_artifact(args.root)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        print("Pages artifact guard failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        print("Pages artifact guard passed: site/ is clean, tracked, and link-free.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
