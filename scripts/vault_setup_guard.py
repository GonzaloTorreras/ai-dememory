#!/usr/bin/env python3
"""Validate private vault setup docs keep generated artifacts out of commits."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import shlex
import sys

from memorylib import repo_root


DOC_PATH = Path("docs/create-memory-repo.md")
VAULT_GITIGNORE = Path("vault-template/.gitignore")
PACKAGED_GITIGNORE = Path("ai_dememory_tool/templates/vault/.gitignore")
GENERATED_DIRS = ("indexes", "distilled", "reports")
REQUIRED_PLACEHOLDERS = tuple(f"{directory}/README.md" for directory in GENERATED_DIRS)
REQUIRED_IGNORES = (
    "indexes/*.sqlite",
    "indexes/*.sqlite-wal",
    "indexes/*.sqlite-shm",
    "indexes/embeddings/",
    "distilled/*.md",
    "!distilled/README.md",
    "reports/*.json",
    "reports/*.md",
    "!reports/README.md",
)
REQUIRED_DOC_SNIPPETS = (
    "ai-dememory vault-template export",
    "does not create a GitHub repository",
)


@dataclass(frozen=True)
class VaultSetupIssue:
    target: str
    message: str


def normalize_token(token: str) -> str:
    return token.strip().replace("\\", "/").strip("'\"")


def git_add_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith("git add ")]


def split_git_add(line: str) -> list[str]:
    try:
        return [normalize_token(token) for token in shlex.split(line)]
    except ValueError:
        return [normalize_token(token) for token in line.split()]


def validate_create_memory_repo_text(text: str) -> list[VaultSetupIssue]:
    issues: list[VaultSetupIssue] = []
    add_lines = git_add_lines(text)
    if not add_lines:
        issues.append(VaultSetupIssue(str(DOC_PATH), "missing explicit `git add` setup command"))
        return issues

    for line in add_lines:
        tokens = split_git_add(line)
        for directory in GENERATED_DIRS:
            forbidden = {directory, f"{directory}/", f"./{directory}", f"./{directory}/"}
            if any(token in forbidden for token in tokens):
                issues.append(
                    VaultSetupIssue(
                        str(DOC_PATH),
                        f"`git add` must not stage whole generated directory `{directory}/`",
                    )
                )

    for placeholder in REQUIRED_PLACEHOLDERS:
        if placeholder not in text:
            issues.append(VaultSetupIssue(str(DOC_PATH), f"missing placeholder path `{placeholder}`"))

    for snippet in REQUIRED_DOC_SNIPPETS:
        if snippet not in text:
            issues.append(VaultSetupIssue(str(DOC_PATH), f"missing GitHub template export guidance `{snippet}`"))

    normalized = re.sub(r"\s+", " ", text)
    for directory in GENERATED_DIRS:
        if f"Generated" not in text or directory not in normalized:
            issues.append(VaultSetupIssue(str(DOC_PATH), f"missing generated-artifact warning for `{directory}/`"))

    return issues


def validate_gitignore_text(relpath: str, text: str) -> list[VaultSetupIssue]:
    issues: list[VaultSetupIssue] = []
    lines = {line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    for pattern in REQUIRED_IGNORES:
        if pattern not in lines:
            issues.append(VaultSetupIssue(relpath, f"missing gitignore pattern `{pattern}`"))
    return issues


def validate_vault_setup(root: Path) -> list[VaultSetupIssue]:
    issues: list[VaultSetupIssue] = []

    try:
        docs_text = (root / DOC_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        issues.append(VaultSetupIssue(str(DOC_PATH), "missing private vault setup guide"))
    else:
        issues.extend(validate_create_memory_repo_text(docs_text))

    for relpath in (VAULT_GITIGNORE, PACKAGED_GITIGNORE):
        try:
            text = (root / relpath).read_text(encoding="utf-8")
        except FileNotFoundError:
            issues.append(VaultSetupIssue(str(relpath), "missing vault gitignore"))
            continue
        issues.extend(validate_gitignore_text(relpath.as_posix(), text))

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    issues = validate_vault_setup(root)
    if args.json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif issues:
        print(f"Vault setup guard found {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"{issue.target}: {issue.message}", file=sys.stderr)
    else:
        print("Vault setup guard passed.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
