"""Helpers for package build artifacts created by local smoke commands."""

from __future__ import annotations

from pathlib import Path
import shutil


GENERATED_BUILD_NAMES = ("build", "dist", "ai_dememory.egg-info")


def generated_build_paths(root: Path) -> list[Path]:
    return [root / name for name in GENERATED_BUILD_NAMES]


def snapshot_generated_build_paths(root: Path) -> set[Path]:
    return {path.resolve() for path in generated_build_paths(root) if path.exists()}


def cleanup_created_build_paths(root: Path, existing: set[Path]) -> None:
    resolved_root = root.resolve()
    for path in generated_build_paths(root):
        resolved = path.resolve() if path.exists() else path
        if not path.exists() or resolved in existing:
            continue
        if not resolved.is_relative_to(resolved_root):
            raise RuntimeError(f"refusing to clean generated path outside root: {resolved}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
