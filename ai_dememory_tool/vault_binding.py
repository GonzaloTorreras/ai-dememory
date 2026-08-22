"""Pure runtime vault-binding selection for public entry points.

This module deliberately selects a vault without discovering one.  Runtime
commands must receive an explicit ``--root`` or ``AI_DEMEMORY_ROOT`` binding;
checkout and current-working-directory resolution belong to separate tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal, Mapping


class VaultBindingError(ValueError):
    """Raised when a runtime command has no usable vault binding."""


@dataclass(frozen=True)
class VaultBinding:
    """A normalized runtime vault path and the binding that selected it."""

    root: Path
    source: Literal["argument", "environment"]


def _resolved_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def resolve_runtime_vault(
    explicit_root: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> VaultBinding:
    """Select a runtime vault without CWD, package, or mutable-global fallback.

    A supplied argument always wins over the environment, including when the
    environment is malformed. Empty environment values mean no binding, while
    whitespace-only values are rejected so they cannot resolve to CWD.
    """

    if explicit_root is not None:
        if not explicit_root.strip():
            raise VaultBindingError("--root requires a non-empty vault path")
        return VaultBinding(_resolved_path(explicit_root), "argument")

    environment = os.environ if environ is None else environ
    configured_root = environment.get("AI_DEMEMORY_ROOT")
    if configured_root is None or configured_root == "":
        raise VaultBindingError(
            "runtime vault binding requires --root <vault-path> or AI_DEMEMORY_ROOT"
        )
    if not configured_root.strip():
        raise VaultBindingError("AI_DEMEMORY_ROOT requires a non-empty vault path")
    return VaultBinding(_resolved_path(configured_root), "environment")
