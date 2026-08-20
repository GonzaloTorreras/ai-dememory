"""Resolve the active ai-dememory package identity without import-path assumptions."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
import tomllib


def current_package_version() -> str:
    """Return the source checkout version or installed distribution version."""
    source_pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if source_pyproject.is_file():
        metadata = tomllib.loads(source_pyproject.read_text(encoding="utf-8"))
        return str(metadata["project"]["version"])
    try:
        return distribution_version("ai-dememory")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "cannot resolve ai-dememory version from a source checkout or installed distribution"
        ) from exc
