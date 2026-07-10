#!/usr/bin/env python3
"""Install and execute the exact wheel and sdist selected for publication."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def executable(venv_root: Path, name: str) -> Path:
    directory = "Scripts" if sys.platform == "win32" else "bin"
    suffix = ".exe" if sys.platform == "win32" else ""
    return venv_root / directory / f"{name}{suffix}"


def smoke(artifact: Path, expected_version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="ai-dememory-release-smoke-") as tmp:
        root = Path(tmp)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = executable(environment, "python")
        subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(artifact)], check=True)
        subprocess.run([str(executable(environment, "ai-dememory")), "--help"], check=True)
        observed = subprocess.check_output(
            [str(python), "-c", "from importlib.metadata import version; print(version('ai-dememory'))"],
            text=True,
        ).strip()
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
    for artifact in (wheels[0], sdists[0]):
        smoke(artifact.resolve(), args.version)
        print(f"OK installed artifact: {artifact.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
