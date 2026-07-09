#!/usr/bin/env python3
"""Run local readiness checks for the ai-dememory toolchain."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3

from index_memory import default_db_path
from memorylib import repo_relative_path, repo_root, validate_memories
from secret_scan import scan_paths
from verify_mcp_contract import validate_contract


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def ok(name: str, detail: str) -> Check:
    return Check(name, "ok", detail)


def warn(name: str, detail: str) -> Check:
    return Check(name, "warn", detail)


def fail(name: str, detail: str) -> Check:
    return Check(name, "fail", detail)


def check_repo(root: Path) -> Check:
    if is_vault_root(root):
        required = ["README.md", "memories", "inbox", "templates"]
    else:
        required = ["README.md", "docs/schema.md", "scripts/ai_dememory.py", "mcp/server/memory_mcp.py"]
    missing = [path for path in required if not (root / path).exists()]
    if missing:
        return fail("repo", "missing " + ", ".join(missing))
    return ok("repo", repo_relative_path(root / "README.md", root))


def check_sqlite_fts() -> Check:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE smoke_fts USING fts5(content)")
    except sqlite3.Error as exc:
        return fail("sqlite_fts5", str(exc))
    finally:
        conn.close()
    return ok("sqlite_fts5", sqlite3.sqlite_version)


def check_schema(root: Path) -> Check:
    documents, errors = validate_memories(root)
    if errors:
        return fail("schema", f"{len(errors)} error(s)")
    return ok("schema", f"{len(documents)} memory file(s)")


def check_secrets(root: Path) -> Check:
    findings = scan_paths(root)
    if findings:
        return fail("secret_scan", f"{len(findings)} suspected issue(s)")
    return ok("secret_scan", "no suspected issues")


def check_index(root: Path) -> Check:
    db_path = default_db_path(root)
    if not db_path.exists():
        return warn("index", "indexes/memory.sqlite does not exist; run ai-dememory index")
    try:
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
        conn.close()
    except sqlite3.Error as exc:
        return fail("index", str(exc))
    return ok("index", f"{count} indexed memory row(s)")


def check_mcp_definitions(root: Path) -> Check:
    try:
        issues = validate_contract(root)
    except Exception as exc:
        return fail("mcp_contract", str(exc))
    if issues:
        return fail("mcp_contract", f"{len(issues)} issue(s)")
    return ok("mcp_contract", "contract definitions valid")


def is_vault_root(root: Path) -> bool:
    return (root / ".ai-dememory.toml").exists()


def is_distribution_root(root: Path) -> bool:
    return (root / "scripts" / "ai_dememory.py").exists() and (
        root / "mcp" / "server" / "memory_mcp.py"
    ).exists()


def doctor_profile(root: Path) -> str:
    if is_distribution_root(root):
        return "distribution"
    if is_vault_root(root):
        return "vault"
    return "unknown"


def summarize_checks(checks: list[Check]) -> dict[str, int]:
    return {
        "ok": sum(1 for check in checks if check.status == "ok"),
        "warn": sum(1 for check in checks if check.status == "warn"),
        "fail": sum(1 for check in checks if check.status == "fail"),
        "total": len(checks),
    }


def run_checks(root: Path) -> list[Check]:
    checks = [
        check_repo(root),
        check_sqlite_fts(),
        check_schema(root),
        check_secrets(root),
        check_index(root),
    ]
    if is_distribution_root(root):
        checks.append(check_mcp_definitions(root))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument("--summary", action="store_true", help="Include profile and status counts.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    checks = run_checks(root)
    exit_code = 1 if any(check.status == "fail" for check in checks) else 0

    if args.json:
        rows = [asdict(check) for check in checks]
        if args.summary:
            print(
                json.dumps(
                    {
                        "profile": doctor_profile(root),
                        "summary": summarize_checks(checks),
                        "checks": rows,
                    },
                    indent=2,
                )
            )
        else:
            print(json.dumps(rows, indent=2))
    else:
        if args.summary:
            summary = summarize_checks(checks)
            print(
                f"PROFILE {doctor_profile(root)}: "
                f"ok={summary['ok']} warn={summary['warn']} fail={summary['fail']} total={summary['total']}"
            )
        for check in checks:
            print(f"{check.status.upper():<4} {check.name}: {check.detail}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
