from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests_v3.test_core import V3TestCase


class CommunityModuleMvpTests(V3TestCase):
    def test_create_install_enable_and_run_foreground_module(self) -> None:
        module_path = self.root / "sample module"
        code, output, error = self.run_cli(
            "module", "create", "sample", "--path", str(module_path)
        )
        self.assertEqual(code, 0, error)
        self.assertIn("Created module: sample", output)
        self.assertIn(f"Location: {module_path.resolve()}", output)
        self.assertIn("python -m pip install -e", output)
        self.assertIn("ai-dememory module enable sample", output)

        environment_path = self.root / "module-venv"
        subprocess.run(
            [sys.executable, "-m", "venv", "--system-site-packages", str(environment_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        python = environment_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        installed = subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--no-build-isolation",
                "-e",
                str(module_path),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(
            installed.returncode,
            0,
            installed.stderr.decode("utf-8", errors="replace"),
        )

        environment = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        environment["AI_DEMEMORY_CONFIG_DIR"] = str(self.root / "installed-config")
        vault_path = self.root / "installed-vault"

        def run(*arguments: str) -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [str(python), "-m", "ai_dememory", *arguments],
                cwd=self.root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )

        setup = run("setup", str(vault_path), "--yes")
        self.assertEqual(setup.returncode, 0, setup.stderr.decode(errors="replace"))
        listed = run("module", "list")
        self.assertEqual(listed.returncode, 0, listed.stderr.decode(errors="replace"))
        self.assertIn("sample [disabled]", listed.stdout.decode("utf-8"))
        enabled = run("module", "enable", "sample")
        self.assertEqual(enabled.returncode, 0, enabled.stderr.decode(errors="replace"))
        self.assertIn("Next: ai-dememory serve sample", enabled.stdout.decode("utf-8"))

        served = run("serve", "sample")
        self.assertEqual(served.returncode, 0, served.stderr.decode(errors="replace"))
        result = json.loads(served.stdout.decode("utf-8"))
        self.assertEqual(result["module"], "sample")
        self.assertEqual(result["core"]["background_processes"], 0)
        self.assertEqual(result["core"]["model_calls"], 0)

        disabled = run("module", "disable", "sample")
        self.assertEqual(disabled.returncode, 0, disabled.stderr.decode(errors="replace"))
        self.assertIn("Disabled module: sample", disabled.stdout.decode("utf-8"))
