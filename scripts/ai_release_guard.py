#!/usr/bin/env python3
"""Validate deterministic exact-tag ai-dememory releases."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

from memorylib import path_is_link_like, safe_write_text
from process_control import noninteractive_git_environment, run_owned_capture


TAG_RE = re.compile(r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?)$")
EXPECTED_REPOSITORY = "GonzaloTorreras/ai-dememory"
# CommonMark treats zero to three leading spaces as an ATX heading. Every such
# rendered H2 is therefore a release-section boundary; four spaces remain an
# indented code block. Canonical target headings are still required at column
# zero by ``changelog_release_notes`` below.
ATX_LEVEL_TWO_RE = re.compile(r"^ {0,3}##(?:[ \t]+|$)")
ATX_LEVEL_ONE_RE = re.compile(r"^ {0,3}#(?:[ \t]+|$)")
LIST_ITEM_RE = re.compile(
    r"^(?P<indent> {0,3})(?P<marker>[-+*]|[0-9]{1,9}[.)])(?P<spacing> {1,4}|\t)"
)
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
BLOCK_QUOTE_RE = re.compile(r"^ {0,3}>")
THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})$"
)
SETEXT_H2_UNDERLINE_RE = re.compile(r"^ {0,3}-+[ \t]*$")
SETEXT_H1_UNDERLINE_RE = re.compile(r"^ {0,3}=+[ \t]*$")
HTML_COMMENT_OPEN_RE = re.compile(r"^ {0,3}<!--")
RAW_HTML_BLOCK_START_RE = re.compile(
    r"^ {0,3}(?:</?[A-Za-z]|<\?|<![A-Z]|<!\[CDATA\[)",
    re.IGNORECASE,
)
MARKDOWN_AUTOLINK_RE = re.compile(
    r"^ {0,3}<(?:[A-Za-z][A-Za-z0-9+.-]{1,31}:[^<>\s]+|[^<>\s@]+@[^<>\s@]+)>(?:[ \t]+.*)?$"
)
UNSUPPORTED_LINE_SEPARATOR_RE = re.compile(r"[\x0b\x0c\x1c-\x1e\x85\u2028\u2029]")
RELEASE_NOTES_RESERVED_COMPONENTS = frozenset({".git", ".github"})
WINDOWS_RESERVED_DEVICE_RE = re.compile(
    r"^(?:con|prn|aux|nul|clock\$|conin\$|conout\$|com[1-9]|lpt[1-9])(?:\..*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReleaseIdentity:
    tag: str
    version: str
    prerelease: bool
    changelog_heading: str
    commit: str | None = None


def project_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _consume_block_comments(raw_line: str, in_comment: bool) -> tuple[bool, str]:
    """Remove every block-comment transition while preserving visible text."""
    cursor = 0
    visible: list[str] = []
    if not in_comment:
        opening = HTML_COMMENT_OPEN_RE.match(raw_line.rstrip("\r\n"))
        if opening is None:
            return False, raw_line
        visible.append(raw_line[: opening.start()])
        cursor = opening.end()
        in_comment = True

    while cursor < len(raw_line):
        if in_comment:
            close = raw_line.find("-->", cursor)
            if close < 0:
                return True, "".join(visible)
            cursor = close + 3
            in_comment = False
            continue
        opening_at = raw_line.find("<!--", cursor)
        if opening_at < 0:
            visible.append(raw_line[cursor:])
            return False, "".join(visible)
        visible.append(raw_line[cursor:opening_at])
        cursor = opening_at + 4
        in_comment = True
    return in_comment, "".join(visible)


def _structural_level_two_headings(text: str) -> list[tuple[int, int, str]]:
    """Return canonical release boundaries under a strict Markdown grammar.

    Release changelogs deliberately reject constructs whose CommonMark block
    interpretation depends on surrounding list/paragraph state. This keeps the
    extracted byte range auditable without embedding a second Markdown parser.
    """
    headings: list[tuple[int, int, str]] = []
    offset = 0
    saw_nonblank_line = False
    if UNSUPPORTED_LINE_SEPARATOR_RE.search(text):
        raise ValueError(
            "CHANGELOG.md contains a non-CommonMark line separator; use LF or CRLF"
        )

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if "<!--" in line or "-->" in line:
            raise ValueError(
                "CHANGELOG.md HTML comments are unsupported in release notes; "
                "use visible Markdown text"
            )
        if re.search(r"`{3,}|~{3,}", line):
            raise ValueError(
                "CHANGELOG.md fenced code blocks are unsupported in release notes; "
                "use inline code or link to maintained documentation"
            )
        if SETEXT_H2_UNDERLINE_RE.fullmatch(line):
            raise ValueError(
                "CHANGELOG.md Setext H2/thematic dash boundaries are unsupported; "
                "use canonical ATX ## release headings"
            )
        if SETEXT_H1_UNDERLINE_RE.fullmatch(line):
            raise ValueError(
                "CHANGELOG.md Setext H1 boundaries are unsupported; "
                "keep a single leading # Changelog title and use canonical ATX ## release headings"
            )
        if ATX_LEVEL_ONE_RE.match(line):
            if saw_nonblank_line or line != "# Changelog":
                raise ValueError(
                    "CHANGELOG.md top-level H1 boundaries are unsupported; "
                    "keep a single leading # Changelog title and use canonical ATX ## release headings"
                )

        if RAW_HTML_BLOCK_START_RE.match(line) and not MARKDOWN_AUTOLINK_RE.fullmatch(line):
            raise ValueError(
                "CHANGELOG.md raw HTML blocks are unsupported in release notes; "
                "use fenced code for literal HTML"
            )

        if ATX_LEVEL_TWO_RE.match(line):
            leading_spaces = len(line) - len(line.lstrip(" "))
            if leading_spaces:
                raise ValueError(
                    "CHANGELOG.md indented ATX H2 headings are unsupported; "
                    "use H3 for nested content and column-zero ## for release boundaries"
                )
            headings.append((offset, offset + len(line), line))
        if line.strip():
            saw_nonblank_line = True
        offset += len(raw_line)
    return headings


def _visible_markdown(text: str) -> str:
    """Remove HTML comments outside fences for the non-empty-section check."""
    visible: list[str] = []
    in_comment = False
    fence_character = ""
    fence_length = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if fence_character:
            visible.append(raw_line)
            if re.fullmatch(
                rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                line,
            ):
                fence_character = ""
                fence_length = 0
            continue

        if not in_comment:
            fence = FENCE_OPEN_RE.fullmatch(line)
            if fence and not (fence.group("marker").startswith("`") and "`" in fence.group("info")):
                marker = fence.group("marker")
                fence_character = marker[0]
                fence_length = len(marker)
                visible.append(raw_line)
                continue

        if in_comment:
            in_comment, remainder = _consume_block_comments(raw_line, True)
            visible.append(remainder)
            continue

        if HTML_COMMENT_OPEN_RE.match(line):
            in_comment, remainder = _consume_block_comments(raw_line, False)
            visible.append(remainder)
            continue
        visible.append(raw_line)
    return "".join(visible)


def _trim_surrounding_blank_lines(text: str) -> str:
    """Trim only blank edge lines so indented Markdown remains semantic."""
    lines = text.splitlines()
    first = 0
    last = len(lines)
    while first < last and not lines[first].strip():
        first += 1
    while last > first and not lines[last - 1].strip():
        last -= 1
    return "\n".join(lines[first:last])


def changelog_release_notes(root: Path, version: str) -> str:
    """Return the exact, non-empty changelog section for ``version``.

    Newlines and surrounding blank lines are normalized so the same immutable
    source produces the same release-note bytes on every runner. Content inside
    the section, including an explicit comparison link, is otherwise preserved.
    """
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = _structural_level_two_headings(text)
    target_re = re.compile(rf"^## \[{re.escape(version)}\] - (?P<date>[^\r\n]+)$")
    matches = []
    for start, end, line in headings:
        match = target_re.fullmatch(line)
        if match is not None:
            matches.append((start, end, match))
    if not matches:
        raise ValueError(f"CHANGELOG.md has no dated [{version}] release heading")
    if len(matches) != 1:
        raise ValueError(f"CHANGELOG.md has multiple [{version}] release headings")
    start, match_end, match = matches[0]
    assert match is not None
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", match.group("date")):
        raise ValueError(f"CHANGELOG.md has no dated [{version}] release heading")
    date.fromisoformat(match.group("date"))
    next_headings = [heading_start for heading_start, _, _ in headings if heading_start > match_end]
    end = next_headings[0] if next_headings else len(text)
    body = _trim_surrounding_blank_lines(text[match_end:end])
    visible_body = _visible_markdown(body).strip()
    if not visible_body:
        raise ValueError(f"CHANGELOG.md [{version}] release section is empty")
    return f"{text[start:match_end]}\n\n{body}\n"


def changelog_heading(root: Path, version: str) -> str:
    return changelog_release_notes(root, version).splitlines()[0]


def _release_notes_output_target(root: Path, output: Path) -> Path:
    """Return a new regular output path without traversing repository links."""
    logical_root = Path(os.path.abspath(root))
    resolved_root = logical_root.resolve()
    candidate = output if output.is_absolute() else logical_root / output
    try:
        relative = candidate.relative_to(logical_root)
    except ValueError:
        try:
            relative = candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("release notes output must stay inside the repository root") from exc

    if not relative.parts or any(
        part in {".", ".."}
        or part.rstrip(" .") != part
        or ":" in part
        or WINDOWS_RESERVED_DEVICE_RE.fullmatch(part) is not None
        for part in relative.parts
    ):
        raise ValueError("release notes output must name a file without special path components")
    if any(part.casefold() in RELEASE_NOTES_RESERVED_COMPONENTS for part in relative.parts):
        raise ValueError("release notes output must not use reserved repository components")

    parent = resolved_root
    for part in relative.parts[:-1]:
        parent = parent / part
        if path_is_link_like(parent):
            raise ValueError("release notes output must not contain symlinks or junctions")
        if not parent.exists():
            try:
                parent.mkdir()
            except FileExistsError:
                pass
        if path_is_link_like(parent):
            raise ValueError("release notes output must not contain symlinks or junctions")
        if not parent.is_dir():
            raise ValueError(f"release notes output parent is not a directory: {parent}")
        try:
            canonical_relative = parent.resolve(strict=True).relative_to(resolved_root)
        except (OSError, ValueError) as exc:
            raise ValueError("release notes output must stay inside the repository root") from exc
        if any(part.casefold() in RELEASE_NOTES_RESERVED_COMPONENTS for part in canonical_relative.parts):
            raise ValueError("release notes output must not use reserved repository components")

    target = parent / relative.name
    if target.exists() or path_is_link_like(target):
        raise ValueError(f"release notes output already exists: {target}")

    return target


def write_release_notes(root: Path, version: str, output: Path) -> Path:
    notes = changelog_release_notes(root, version)
    target = _release_notes_output_target(root, output)
    return safe_write_text(target, notes, root=root, overwrite=False)


def git(root: Path, *args: str) -> str:
    return run_owned_capture(
        ["git", "-C", str(root), *args],
        timeout_seconds=30,
        env=noninteractive_git_environment(),
        check=True,
    ).stdout.strip()


def validate_identity(root: Path, tag: str, *, version_only: bool = False) -> ReleaseIdentity:
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError("release tag must match vMAJOR.MINOR.PATCH or a PEP 440 prerelease")
    version = project_version(root)
    if match.group("version") != version:
        raise ValueError(f"tag {tag} does not match project version {version}")
    heading = changelog_heading(root, version)
    prerelease = bool(re.search(r"(?:a|b|rc)[0-9]+$", version))
    if version_only:
        return ReleaseIdentity(tag=tag, version=version, prerelease=prerelease, changelog_heading=heading)

    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository and repository != EXPECTED_REPOSITORY:
        raise ValueError(f"release repository must be {EXPECTED_REPOSITORY}, got {repository}")
    commit = git(root, "rev-parse", f"{tag}^{{commit}}")
    run_owned_capture(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, "origin/main"],
        timeout_seconds=30,
        env=noninteractive_git_environment(),
        check=True,
    )
    return ReleaseIdentity(tag=tag, version=version, prerelease=prerelease, changelog_heading=heading, commit=commit)


def write_github_output(path: str, identity: ReleaseIdentity) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"tag={identity.tag}\n")
        handle.write(f"version={identity.version}\n")
        handle.write(f"prerelease={'true' if identity.prerelease else 'false'}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--tag")
    parser.add_argument("--version-only", action="store_true")
    parser.add_argument("--github-output")
    parser.add_argument(
        "--release-notes",
        metavar="PATH",
        help="Write the exact, deterministic CHANGELOG section to PATH.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    tag = args.tag or f"v{project_version(root)}"
    try:
        identity = validate_identity(root, tag, version_only=args.version_only)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"release identity validation failed: {exc}", file=sys.stderr)
        return 1
    if args.github_output:
        write_github_output(args.github_output, identity)
    if args.release_notes:
        output = Path(args.release_notes)
        if not output.is_absolute():
            output = root / output
        try:
            write_release_notes(root, identity.version, output)
        except (OSError, ValueError) as exc:
            print(f"release notes generation failed: {exc}", file=sys.stderr)
            return 1
    if args.json:
        print(json.dumps(asdict(identity), indent=2))
    else:
        print(f"Release identity valid: {identity.tag} ({'prerelease' if identity.prerelease else 'stable'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
