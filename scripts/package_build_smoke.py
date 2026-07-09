#!/usr/bin/env python3
"""Build package distributions in a temp directory and run twine check."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
import tempfile

from build_artifacts import cleanup_created_build_paths, generated_build_paths
from install_smoke import InstallSmokeError, SmokeStep, run_step, venv_paths
from memorylib import repo_root


def assert_no_stale_build_paths(root: Path) -> None:
    existing = [path for path in generated_build_paths(root) if path.exists()]
    if existing:
        names = ", ".join(path.name for path in existing)
        raise InstallSmokeError(
            f"stale generated package build artifact(s) present: {names}. "
            "Remove generated build/, dist/, and *.egg-info paths before running package-build-smoke."
        )


def assert_dist_artifacts(dist: Path) -> list[Path]:
    files = sorted(path for path in dist.iterdir() if path.is_file()) if dist.exists() else []
    wheels = [path for path in files if path.suffix == ".whl"]
    sdists = [path for path in files if path.name.endswith(".tar.gz")]
    if len(wheels) != 1:
        raise InstallSmokeError(f"expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        raise InstallSmokeError(f"expected exactly one source distribution, found {len(sdists)}")
    return [*wheels, *sdists]


def run_package_build_smoke(root: Path, keep_temp: bool = False) -> list[SmokeStep]:
    steps: list[SmokeStep] = []
    assert_no_stale_build_paths(root)
    existing_generated: set[Path] = set()
    temp_path = Path(tempfile.mkdtemp(prefix="ai-dememory-build-smoke-"))
    try:
        venv = temp_path / "venv"
        dist = temp_path / "dist"
        run_step(steps, "create build venv", [sys.executable, "-m", "venv", str(venv)])
        python, pip, _ = venv_paths(venv)
        run_step(steps, "upgrade build tooling", [str(python), "-m", "pip", "install", "--upgrade", "pip", "build", "twine"])
        run_step(steps, "build distributions", [str(python), "-m", "build", "--outdir", str(dist), str(root)], cwd=root)
        artifacts = assert_dist_artifacts(dist)
        run_step(steps, "twine check", [str(python), "-m", "twine", "check", *[str(path) for path in artifacts]])
        return steps
    finally:
        try:
            cleanup_created_build_paths(root, existing_generated)
        except RuntimeError as exc:
            raise InstallSmokeError(str(exc)) from exc
        if keep_temp:
            print(f"Kept package build smoke temp directory: {temp_path}", file=sys.stderr)
        else:
            shutil.rmtree(temp_path, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary build smoke directory.")
    parser.add_argument(
        "--check-clean",
        action="store_true",
        help="Only verify that generated package build artifact paths are absent.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        if args.check_clean:
            assert_no_stale_build_paths(root)
            if args.json:
                print(json.dumps({"clean": True, "checked": [path.name for path in generated_build_paths(root)]}, indent=2))
            else:
                print("No stale generated package build artifacts found.")
            return 0
        steps = run_package_build_smoke(root, keep_temp=args.keep_temp)
    except InstallSmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([asdict(step) for step in steps], indent=2))
    else:
        for step in steps:
            print(f"OK {step.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
