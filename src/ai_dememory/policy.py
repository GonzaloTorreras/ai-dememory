"""Small high-confidence safety checks at the canonical write boundary."""

from __future__ import annotations

import re


class UnsafeContentError(ValueError):
    pass


_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def reject_high_confidence_secrets(text: str) -> None:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise UnsafeContentError(
                "The text looks like secret material. Store secrets in a credential manager, not memory."
            )
