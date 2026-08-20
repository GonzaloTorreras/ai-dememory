"""Fail-closed validation for security-sensitive command-line arguments."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence


def duplicate_options(argv: Sequence[str], options: Iterable[str]) -> tuple[str, ...]:
    """Return singleton long options that occur more than once in *argv*."""
    allowed = frozenset(option.casefold() for option in options)
    counts: dict[str, int] = {}
    for argument in argv:
        option = str(argument).partition("=")[0].casefold()
        if option in allowed:
            counts[option] = counts.get(option, 0) + 1
    return tuple(sorted(option for option, count in counts.items() if count > 1))


def reject_duplicate_options(
    parser: argparse.ArgumentParser,
    argv: Sequence[str],
    options: Iterable[str],
) -> None:
    """Stop argparse before last-value-wins can replace a security control."""
    duplicates = duplicate_options(argv, options)
    if duplicates:
        parser.error(
            "security-sensitive options may be specified at most once: "
            + ", ".join(duplicates)
        )


def validate_docker_image_argument(image: str) -> str:
    """Return a Docker image argv value that cannot be parsed as an option."""
    if not image or image != image.strip():
        raise ValueError("Docker image must be a non-empty value without surrounding whitespace")
    if image.startswith("-"):
        raise ValueError("Docker image must not begin with '-'")
    if any(character.isspace() or ord(character) < 32 for character in image):
        raise ValueError("Docker image must not contain whitespace or control characters")
    return image
