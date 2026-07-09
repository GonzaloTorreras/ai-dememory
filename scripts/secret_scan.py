#!/usr/bin/env python3
"""Local secret scanner for memory files and repo text artifacts."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Iterable

from memorylib import repo_relative_path, repo_root


SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".svelte-kit",
    "dist",
    "build",
}
SKIP_SUFFIXES = {
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".db",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".zip",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    redacted_line: str


PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key-block", PRIVATE_KEY_RE),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("stripe-secret-key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("github-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws-temp-access-key", re.compile(r"\bASIA[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("jwt-token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "database-url",
        re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:\s/@]+:[^@\s]+@"),
    ),
    ("authorization-bearer", re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("service-account-json", re.compile(r'"type"\s*:\s*"service_account"')),
    ("service-account-json", re.compile(r'"private_key_id"\s*:')),
    ("service-account-json", re.compile(r'"private_key"\s*:')),
    (
        "cookie-or-session",
        re.compile(r"(?i)\b(?:cookie|session(?:id)?|set-cookie)\b\s*[:=]\s*['\"]?[^'\"\s;]{20,}"),
    ),
)

SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?"
    r"(?P<name>[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|COOKIE|SESSION|PRIVATE_KEY|API_KEY|ACCESS_KEY|CLIENT_SECRET|DATABASE_URL|DB_URL|REDIS_URL)[A-Z0-9_]*)"
    r"\s*=\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

STRUCTURED_SECRET_RE = re.compile(
    r"(?i)^\s*(?:[-*]\s*)?"
    r"(?P<name>api[_-]?key|password|passwd|token|secret|client[_-]?secret|private[_-]?key|session[_-]?token|cookie)"
    r"\s*:\s*(?P<value>.+?)\s*$"
)

ENV_ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.+?)\s*$")

SAFE_PLACEHOLDERS = {
    "",
    "null",
    "none",
    "changeme",
    "change-me",
    "example",
    "placeholder",
    "redacted",
    "<redacted>",
    "<secret>",
    "your-token",
    "your-token-here",
    "your-api-key",
}


def discover_files(root: Path, targets: Iterable[str] | None = None) -> list[Path]:
    if targets:
        paths = [Path(target) for target in targets]
        resolved = [(path if path.is_absolute() else root / path) for path in paths]
    else:
        resolved = [root]

    files: list[Path] = []
    for path in resolved:
        if path.is_file() and should_scan(path, root):
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in path.rglob("*") if p.is_file() and should_scan(p, root))
    return sorted(set(files))


def should_scan(path: Path, root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root.resolve())
        parts = set(rel.parts)
    except ValueError:
        parts = set(path.parts)
    if parts & SKIP_DIRS:
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if path.name.endswith((".pyc", ".pyo")):
        return False
    return True


def scan_file(path: Path, root: Path) -> list[Finding]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [Finding(display_path(path, root), 0, "read-error", f"<redacted:read-error> {exc}")]

    if b"\x00" in raw[:4096]:
        return []

    text = raw.decode("utf-8", errors="replace")
    return scan_text(text, display_path(path, root), env_file=is_env_file(path))


def scan_text(text: str, display_name: str = "<text>", env_file: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line_findings: list[str] = []
        if env_file:
            env_match = ENV_ASSIGNMENT_RE.match(line)
            if env_match and should_flag_assignment(env_match.group("name"), env_match.group("value"), True):
                line_findings.append(".env-content")

        assignment_match = SENSITIVE_ASSIGNMENT_RE.match(line)
        if assignment_match and should_flag_assignment(
            assignment_match.group("name"),
            assignment_match.group("value"),
            False,
        ):
            line_findings.append("sensitive-assignment")

        structured_match = STRUCTURED_SECRET_RE.match(line)
        if structured_match and should_flag_assignment(
            structured_match.group("name"),
            structured_match.group("value"),
            False,
        ):
            line_findings.append("structured-secret")

        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                line_findings.append(kind)

        if line_findings:
            redacted_line = redact_line(line, line_findings)
            for kind in sorted(set(line_findings)):
                findings.append(Finding(display_name, line_no, kind, redacted_line))
    return findings


def is_safe_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'\"").lower()
    return normalized in SAFE_PLACEHOLDERS or normalized.startswith("<") and normalized.endswith(">")


def should_flag_assignment(name: str, value: str, env_file: bool) -> bool:
    if is_safe_placeholder(value):
        return False
    if env_file:
        return True

    normalized = value.strip().strip("'\"")
    if looks_like_code_expression(normalized):
        return False
    if any(pattern.search(normalized) for _, pattern in SECRET_PATTERNS):
        return True
    minimum = 6 if name.lower() in {"password", "passwd"} else 8
    return len(normalized) >= minimum and not any(char.isspace() for char in normalized)


def looks_like_code_expression(value: str) -> bool:
    if value.startswith(("re.compile(", "Path(", "set(", "dict(", "list(", "tuple(")):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*\(.*\)", value):
        return True
    return False


def redact_assignment(match: re.Match[str], kind: str, separator: str) -> str:
    return f"{match.group('name')}{separator}<redacted:{kind}>"


def redact_line(line: str, kinds: Iterable[str]) -> str:
    kind_set = set(kinds)
    if kind_set & {"private-key-block", "service-account-json"}:
        return "<redacted:secret-line>"

    redacted = SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: redact_assignment(match, "sensitive-assignment", "="),
        line,
    )
    redacted = ENV_ASSIGNMENT_RE.sub(
        lambda match: redact_assignment(match, ".env-content", "=")
        if ".env-content" in kind_set
        else match.group(0),
        redacted,
    )
    redacted = STRUCTURED_SECRET_RE.sub(
        lambda match: redact_assignment(match, "structured-secret", ":"),
        redacted,
    )
    for kind, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(f"<redacted:{kind}>", redacted)
    if len(redacted) > 240:
        return redacted[:237].rstrip() + "..."
    return redacted


def is_env_file(path: Path) -> bool:
    return path.name == ".env" or path.name.startswith(".env.")


def display_path(path: Path, root: Path) -> str:
    try:
        return repo_relative_path(path, root)
    except ValueError:
        return str(path)


def scan_paths(root: Path, targets: Iterable[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for path in discover_files(root, targets):
        findings.extend(scan_file(path, root))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Optional files or directories to scan.")
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    findings = scan_paths(root, args.paths or None)

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    elif findings:
        print(f"Secret scan found {len(findings)} suspected issue(s):", file=sys.stderr)
        for finding in findings:
            print(
                f"{finding.path}:{finding.line}: {finding.kind}: {finding.redacted_line}",
                file=sys.stderr,
            )
    else:
        print("Secret scan passed.")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
