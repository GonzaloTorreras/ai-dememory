"""Render reviewable argv arrays without interpolating untrusted shell text."""

from __future__ import annotations

import os
import shlex
from collections.abc import Sequence


POWERSHELL_SINGLE_QUOTE_DELIMITERS = (
    "'",
    "\u2018",
    "\u2019",
    "\u201a",
    "\u201b",
)


def _powershell_single_quoted(argument: str) -> str:
    for delimiter in POWERSHELL_SINGLE_QUOTE_DELIMITERS:
        argument = argument.replace(delimiter, delimiter * 2)
    return "'" + argument + "'"


def render_copy_command(argv: Sequence[str], *, windows: bool | None = None) -> str:
    """Render argv for POSIX shells or PowerShell using inert arguments."""
    values = [str(argument) for argument in argv]
    if not values:
        raise ValueError("command argv must not be empty")
    if any("\x00" in argument for argument in values):
        raise ValueError("command arguments must not contain NUL")
    use_windows = os.name == "nt" if windows is None else windows
    if not use_windows:
        return shlex.join(values)
    quoted = [_powershell_single_quoted(argument) for argument in values]
    return "& " + " ".join(quoted)
