#!/usr/bin/env python3
"""Validate ADR structure for v2 decision records."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

from memorylib import repo_root


ADR_DIR = Path("docs/adr")
DEPENDENCIES_REQUIRED_FROM = 31
REQUIRED_CORE_SECTIONS = ("Context", "Decision")
SECTION_GROUPS = {
    "benefits": ("Benefits", "Consequences"),
    "limitations": ("Limitations", "Caveats", "Deferred"),
    "future_risks": ("Future Risks", "Future Work", "Deferred"),
}


@dataclass(frozen=True)
class AdrGuardIssue:
    target: str
    message: str


def adr_number(path: Path) -> int | None:
    match = re.match(r"^(\d{4})-", path.name)
    return int(match.group(1)) if match else None


def section_bodies(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    bodies: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        bodies[title] = text[start:end].strip()
    return bodies


def has_status(text: str, sections: dict[str, str]) -> bool:
    if sections.get("Status"):
        return True
    return bool(re.search(r"(?m)^Status:\s*\S+", text))


def has_nonempty_section(sections: dict[str, str], names: tuple[str, ...]) -> bool:
    return any(sections.get(name, "").strip() for name in names)


def validate_adr_text(relpath: str, text: str, number: int | None = None) -> list[AdrGuardIssue]:
    issues: list[AdrGuardIssue] = []
    target = relpath
    sections = section_bodies(text)

    if not re.search(r"(?m)^#\s+ADR\s+\d{4}:\s+\S+", text):
        issues.append(AdrGuardIssue(target, "missing `# ADR NNNN: Title` heading"))
    if not has_status(text, sections):
        issues.append(AdrGuardIssue(target, "missing accepted/proposed status"))
    for section in REQUIRED_CORE_SECTIONS:
        if not sections.get(section, "").strip():
            issues.append(AdrGuardIssue(target, f"missing non-empty `{section}` section"))
    for label, names in SECTION_GROUPS.items():
        if not has_nonempty_section(sections, names):
            joined = "` or `".join(names)
            issues.append(AdrGuardIssue(target, f"missing non-empty `{joined}` section for {label}"))
    if number is not None and number >= DEPENDENCIES_REQUIRED_FROM and not sections.get("Dependencies", "").strip():
        issues.append(AdrGuardIssue(target, "ADR 0031+ must include a non-empty `Dependencies` section"))
    return issues


def validate_adr_docs(root: Path) -> list[AdrGuardIssue]:
    directory = root / ADR_DIR
    if not directory.exists():
        return [AdrGuardIssue(str(ADR_DIR), "ADR directory is missing")]
    issues: list[AdrGuardIssue] = []
    paths = sorted(directory.glob("*.md"))
    if not paths:
        return [AdrGuardIssue(str(ADR_DIR), "ADR directory has no Markdown files")]
    paths_by_number: dict[int, list[Path]] = {}
    for path in paths:
        relpath = path.relative_to(root).as_posix()
        number = adr_number(path)
        if number is None:
            issues.append(AdrGuardIssue(relpath, "ADR filename must start with a zero-padded number"))
            continue
        paths_by_number.setdefault(number, []).append(path)
        issues.extend(validate_adr_text(relpath, path.read_text(encoding="utf-8"), number))
    for number, duplicate_paths in sorted(paths_by_number.items()):
        if len(duplicate_paths) < 2:
            continue
        names = ", ".join(path.name for path in duplicate_paths)
        issues.append(
            AdrGuardIssue(
                str(ADR_DIR),
                f"duplicate ADR {number:04d} filenames: {names}",
            )
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_adr_docs(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"ADR guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("ADR guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
