#!/usr/bin/env python3
"""Install and execute the exact wheel and sdist selected for publication."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile

from process_control import run_owned_capture


EXPECTED_WHEEL_PACKAGES = {"ai_dememory_tool"}


def validate_wheel_namespaces(wheel: Path) -> set[str]:
    """Reject public or accidental top-level packages in the built wheel."""
    with zipfile.ZipFile(wheel) as archive:
        packages: set[str] = set()
        for name in archive.namelist():
            if not name or name.startswith((".", "/")):
                continue
            parts = name.split("/")
            top = parts[0]
            if top.endswith(".dist-info"):
                continue
            if top.endswith(".data"):
                if len(parts) < 3 or parts[1] not in {"purelib", "platlib"}:
                    continue
                top = parts[2]
            packages.add(Path(top).stem if "/" not in name and top.endswith(".py") else top)
    if packages != EXPECTED_WHEEL_PACKAGES:
        raise RuntimeError(
            f"{wheel.name}: unsafe top-level packages {sorted(packages)}; "
            f"expected {sorted(EXPECTED_WHEEL_PACKAGES)}"
        )
    return packages


def executable(venv_root: Path, name: str) -> Path:
    directory = "Scripts" if sys.platform == "win32" else "bin"
    suffix = ".exe" if sys.platform == "win32" else ""
    return venv_root / directory / f"{name}{suffix}"


def run_checked(command: list[str], timeout_seconds: int = 180) -> subprocess.CompletedProcess[str]:
    completed = run_owned_capture(command, timeout_seconds=timeout_seconds)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


def smoke(artifact: Path, expected_version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="ai-dememory-release-smoke-") as tmp:
        root = Path(tmp)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = executable(environment, "python")
        run_checked([str(python), "-m", "pip", "install", "--no-deps", str(artifact)])
        run_checked([str(executable(environment, "ai-dememory")), "--help"])
        vault = root / "vault"
        run_checked([str(executable(environment, "ai-dememory")), "init", str(vault)])
        run_checked([str(executable(environment, "ai-dememory")), "--root", str(vault), "doctor"])
        run_checked(
            [str(executable(environment, "ai-dememory")), "--root", str(vault), "mcp", "--help"],
        )
        observed = run_checked(
            [str(python), "-c", "from importlib.metadata import version; print(version('ai-dememory'))"],
        ).stdout.strip()
        if observed != expected_version:
            raise RuntimeError(f"{artifact.name}: installed {observed}, expected {expected_version}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    wheels = sorted(args.dist.glob("*.whl"))
    sdists = sorted(args.dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("expected exactly one wheel and one sdist")
    validate_wheel_namespaces(wheels[0])
    print(f"OK wheel namespace: {', '.join(sorted(EXPECTED_WHEEL_PACKAGES))}")
    for artifact in (wheels[0], sdists[0]):
        smoke(artifact.resolve(), args.version)
        print(f"OK installed artifact: {artifact.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
