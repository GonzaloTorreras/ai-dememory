#!/usr/bin/env python3
"""Local secret scanner for memory files and repo text artifacts."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import sys
from typing import Iterable

from memorylib import path_is_link_like, repo_root
from resource_limits import (
    MAX_SECRET_SCAN_ENTRIES as MAX_SCAN_ENTRIES,
    MAX_SECRET_SCAN_FILE_BYTES as MAX_SCAN_FILE_BYTES,
    MAX_SECRET_SCAN_FILES as MAX_SCAN_FILES,
    MAX_SECRET_SCAN_FINDINGS as MAX_SCAN_FINDINGS,
    MAX_SECRET_SCAN_TEXT_CHARS as MAX_SCAN_TEXT_CHARS,
    MAX_SECRET_SCAN_TOTAL_BYTES as MAX_SCAN_TOTAL_BYTES,
)


ROOT_SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".svelte-kit",
    "dist",
    "build",
    ".venv",
    "venv",
}
NESTED_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
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


class ScanLimitExceeded(ValueError):
    """Raised when a secret scan would exceed a hard resource budget."""

    def __init__(self, message: str, path: str = "<scan>") -> None:
        super().__init__(message)
        self.path = path


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


def discover_files(
    root: Path,
    targets: Iterable[str] | None = None,
    *,
    root_resolved: Path | None = None,
    max_scan_entries: int = MAX_SCAN_ENTRIES,
    max_files: int = MAX_SCAN_FILES,
    max_file_bytes: int = MAX_SCAN_FILE_BYTES,
    max_total_bytes: int = MAX_SCAN_TOTAL_BYTES,
) -> list[Path]:
    root_resolved = root_resolved or root.resolve()
    root_absolute = Path(os.path.abspath(root))
    if targets:
        paths = [Path(target) for target in targets]
        resolved = [(path if path.is_absolute() else root / path) for path in paths]
    else:
        resolved = [root]

    files: list[Path] = []
    seen_files: set[Path] = set()
    entries_seen = 0
    total_bytes = 0
    for path in resolved:
        ensure_scan_path(path, root_resolved, root_absolute)
        if path.is_file() and should_scan(path, root, root_resolved=root_resolved):
            total_bytes = add_scannable_file(
                path,
                root,
                files,
                seen_files,
                total_bytes=total_bytes,
                max_files=max_files,
                max_file_bytes=max_file_bytes,
                max_total_bytes=max_total_bytes,
            )
        elif path.is_dir():
            if should_skip_directory(path, root, root_resolved):
                continue
            for current_raw, dir_names, file_names in os.walk(
                path,
                topdown=True,
                followlinks=False,
            ):
                current = Path(current_raw)
                dir_names.sort()
                file_names.sort()
                retained_dirs: list[str] = []
                for name in dir_names:
                    entries_seen += 1
                    enforce_entry_limit(entries_seen, max_scan_entries)
                    candidate = current / name
                    if path_is_link_like(candidate):
                        continue
                    if not should_skip_directory(candidate, root, root_resolved):
                        retained_dirs.append(name)
                dir_names[:] = retained_dirs
                for name in file_names:
                    entries_seen += 1
                    enforce_entry_limit(entries_seen, max_scan_entries)
                    candidate = current / name
                    if path_is_link_like(candidate):
                        continue
                    if should_scan(candidate, root, root_resolved=root_resolved):
                        total_bytes = add_scannable_file(
                            candidate,
                            root,
                            files,
                            seen_files,
                            total_bytes=total_bytes,
                            max_files=max_files,
                            max_file_bytes=max_file_bytes,
                            max_total_bytes=max_total_bytes,
                        )
    return sorted(files)


def enforce_entry_limit(entries_seen: int, max_scan_entries: int) -> None:
    if entries_seen > max_scan_entries:
        raise ScanLimitExceeded(
            f"secret scan exceeded the {max_scan_entries} entry limit"
        )


def add_scannable_file(
    path: Path,
    root: Path,
    files: list[Path],
    seen_files: set[Path],
    *,
    total_bytes: int,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> int:
    logical_path = Path(os.path.abspath(path))
    if logical_path in seen_files:
        return total_bytes
    try:
        size = path.stat(follow_symlinks=False).st_size
    except OSError as exc:
        raise ScanLimitExceeded(
            f"secret scan could not inspect file: {display_path(path, root)}",
            display_path(path, root),
        ) from exc
    if size > max_file_bytes:
        raise ScanLimitExceeded(
            f"secret scan file exceeds the {max_file_bytes} byte limit",
            display_path(path, root),
        )
    if total_bytes + size > max_total_bytes:
        raise ScanLimitExceeded(
            f"secret scan exceeded the {max_total_bytes} total byte limit",
            display_path(path, root),
        )
    if len(files) >= max_files:
        raise ScanLimitExceeded(
            f"secret scan exceeded the {max_files} file limit",
            display_path(path, root),
        )
    files.append(path)
    seen_files.add(logical_path)
    return total_bytes + size


def ensure_scan_path(path: Path, root_resolved: Path, root_absolute: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("secret scan paths must stay inside the memory root") from exc
    logical_path = Path(os.path.abspath(path))
    try:
        relative = logical_path.relative_to(root_absolute)
    except ValueError as exc:
        raise ValueError("secret scan paths must stay inside the memory root") from exc
    current = root_absolute
    if path_is_link_like(current):
        raise ValueError("secret scan root must not be a symlink or junction")
    for part in relative.parts:
        current = current / part
        if path_is_link_like(current):
            raise ValueError("secret scan path must not contain links or junctions")


def should_skip_directory(path: Path, root: Path, root_resolved: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root_resolved)
    except (OSError, ValueError):
        return True
    parts = rel.parts
    if not parts or parts[0] == "memories":
        return False
    return parts[0] in ROOT_SKIP_DIRS or bool(set(parts) & NESTED_SKIP_DIRS)


def should_scan(path: Path, root: Path, *, root_resolved: Path | None = None) -> bool:
    try:
        rel = path.resolve().relative_to(root_resolved or root.resolve())
    except ValueError:
        return False
    parts = rel.parts
    if not parts:
        return False
    if parts[0] != "memories" and (
        parts[0] in ROOT_SKIP_DIRS or bool(set(parts) & NESTED_SKIP_DIRS)
    ):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if path.name.endswith((".pyc", ".pyo")):
        return False
    return True


def scan_file(
    path: Path,
    root: Path,
    *,
    root_absolute: Path | None = None,
    max_file_bytes: int = MAX_SCAN_FILE_BYTES,
    max_findings: int = MAX_SCAN_FINDINGS,
) -> list[Finding]:
    display_name = display_path(path, root, root_absolute=root_absolute)
    try:
        size = path.stat(follow_symlinks=False).st_size
    except OSError as exc:
        return [Finding(display_name, 0, "read-error", f"<redacted:read-error> {exc}")]
    if size > max_file_bytes:
        return [
            Finding(
                display_name,
                0,
                "scan-limit",
                f"<redacted:scan-limit> file exceeds {max_file_bytes} bytes",
            )
        ]

    findings: list[Finding] = []
    bytes_read = 0
    line_no = 0
    try:
        with path.open("rb") as stream:
            prefix = stream.read(min(4096, max_file_bytes + 1))
            if b"\x00" in prefix:
                return []
            stream.seek(0)
            while True:
                remaining = max_file_bytes - bytes_read
                raw_line = stream.readline(remaining + 1)
                if not raw_line:
                    break
                bytes_read += len(raw_line)
                if bytes_read > max_file_bytes:
                    return bounded_limit_findings(
                        findings,
                        Finding(
                            display_name,
                            line_no,
                            "scan-limit",
                            f"<redacted:scan-limit> file exceeds {max_file_bytes} bytes",
                        ),
                        max_findings,
                    )
                line_no += 1
                line_findings = scan_text(
                    raw_line.decode("utf-8", errors="replace"),
                    display_name,
                    env_file=is_env_file(path),
                    max_findings=max_findings,
                )
                for finding in line_findings:
                    findings.append(
                        Finding(
                            finding.path,
                            line_no,
                            finding.kind,
                            finding.redacted_line,
                        )
                    )
                    if len(findings) >= max_findings:
                        return bounded_limit_findings(
                            findings,
                            Finding(
                                display_name,
                                line_no,
                                "scan-limit",
                                f"<redacted:scan-limit> findings exceed {max_findings}",
                            ),
                            max_findings,
                        )
    except OSError as exc:
        return [Finding(display_name, 0, "read-error", f"<redacted:read-error> {exc}")]
    return findings


def bounded_limit_findings(
    findings: list[Finding],
    limit_finding: Finding,
    max_findings: int,
) -> list[Finding]:
    if max_findings <= 0:
        return []
    return [*findings[: max_findings - 1], limit_finding]


def scan_text(
    text: str,
    display_name: str = "<text>",
    env_file: bool = False,
    *,
    max_findings: int = MAX_SCAN_FINDINGS,
) -> list[Finding]:
    if len(text) > MAX_SCAN_TEXT_CHARS:
        return [
            Finding(
                display_name,
                0,
                "scan-limit",
                f"<redacted:scan-limit> text exceeds {MAX_SCAN_TEXT_CHARS} characters",
            )
        ]
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
                if len(findings) >= max_findings:
                    return bounded_limit_findings(
                        findings,
                        Finding(
                            display_name,
                            line_no,
                            "scan-limit",
                            f"<redacted:scan-limit> findings exceed {max_findings}",
                        ),
                        max_findings,
                    )
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


def display_path(path: Path, root: Path, *, root_absolute: Path | None = None) -> str:
    try:
        return path.absolute().relative_to(root_absolute or root.absolute()).as_posix()
    except ValueError:
        return str(path)


def scan_paths(
    root: Path,
    targets: Iterable[str] | None = None,
    *,
    max_scan_entries: int = MAX_SCAN_ENTRIES,
    max_files: int = MAX_SCAN_FILES,
    max_file_bytes: int = MAX_SCAN_FILE_BYTES,
    max_total_bytes: int = MAX_SCAN_TOTAL_BYTES,
    max_findings: int = MAX_SCAN_FINDINGS,
) -> list[Finding]:
    findings: list[Finding] = []
    root_resolved = root.resolve()
    root_absolute = root.absolute()
    try:
        files = discover_files(
            root,
            targets,
            root_resolved=root_resolved,
            max_scan_entries=max_scan_entries,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
    except ScanLimitExceeded as exc:
        return [
            Finding(
                exc.path,
                0,
                "scan-limit",
                f"<redacted:scan-limit> {exc}",
            )
        ]
    total_bytes = 0
    for path in files:
        try:
            total_bytes += path.stat(follow_symlinks=False).st_size
        except OSError as exc:
            findings.append(
                Finding(
                    display_path(path, root, root_absolute=root_absolute),
                    0,
                    "read-error",
                    f"<redacted:read-error> {exc}",
                )
            )
            continue
        if total_bytes > max_total_bytes:
            return bounded_limit_findings(
                findings,
                Finding(
                    display_path(path, root, root_absolute=root_absolute),
                    0,
                    "scan-limit",
                    f"<redacted:scan-limit> total bytes exceed {max_total_bytes}",
                ),
                max_findings,
            )
        remaining = max_findings - len(findings)
        if remaining <= 0:
            return bounded_limit_findings(
                findings,
                Finding(
                    "<scan>",
                    0,
                    "scan-limit",
                    f"<redacted:scan-limit> findings exceed {max_findings}",
                ),
                max_findings,
            )
        findings.extend(
            scan_file(
                path,
                root,
                root_absolute=root_absolute,
                max_file_bytes=max_file_bytes,
                max_findings=remaining,
            )
        )
        if len(findings) >= max_findings:
            return bounded_limit_findings(
                findings,
                Finding(
                    display_path(path, root, root_absolute=root_absolute),
                    0,
                    "scan-limit",
                    f"<redacted:scan-limit> findings exceed {max_findings}",
                ),
                max_findings,
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Optional files or directories to scan.")
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        findings = scan_paths(root, args.paths or None)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

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
