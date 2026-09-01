from __future__ import annotations

import importlib
import json
import sys

from tests_v3.test_core import V3TestCase


class CommunityModuleMvpTests(V3TestCase):
    def test_create_json_returns_argv_and_cwd_without_a_shell_command(self) -> None:
        module_path = self.root / "module$(not-a-command)"
        code, output, error = self.run_cli(
            "module", "create", "structured", "--path", str(module_path), "--json"
        )

        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["created"], str(module_path.resolve()))
        self.assertEqual(
            result["next"][0],
            {
                "command": "python",
                "args": ["-m", "pip", "install", "-e", "."],
                "cwd": str(module_path.resolve()),
            },
        )

    def test_create_discover_enable_and_run_foreground_module(self) -> None:
        module_path = self.root / "sample module"
        code, output, error = self.run_cli(
            "module", "create", "sample", "--path", str(module_path)
        )
        self.assertEqual(code, 0, error)
        self.assertIn("Created module: sample", output)
        self.assertIn(f"Location: {module_path.resolve()}", output)
        self.assertIn("Next, from that directory:", output)
        self.assertIn("python -m pip install -e .", output)
        self.assertIn("ai-dememory module enable sample", output)

        metadata_root = self.root / "entrypoint-fixture"
        distribution = metadata_root / "ai_dememory_module_sample-0.1.0.dist-info"
        distribution.mkdir(parents=True)
        (distribution / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: ai-dememory-module-sample\nVersion: 0.1.0\n",
            encoding="utf-8",
        )
        (distribution / "entry_points.txt").write_text(
            "[ai_dememory.modules]\nsample = sample\n",
            encoding="utf-8",
        )
        module_source = str(module_path / "src")
        sys.path[:0] = [str(metadata_root), module_source]
        importlib.invalidate_caches()
        try:
            vault_path = self.root / "module-vault"
            code, _, error = self.run_cli("setup", str(vault_path), "--yes")
            self.assertEqual(code, 0, error)

            code, output, error = self.run_cli("module", "list")
            self.assertEqual(code, 0, error)
            self.assertIn("sample [disabled]", output)
            self.assertNotIn("sample", sys.modules)

            code, output, error = self.run_cli("module", "enable", "sample")
            self.assertEqual(code, 0, error)
            self.assertIn("Next: ai-dememory serve sample", output)

            code, output, error = self.run_cli("serve", "sample")
            self.assertEqual(code, 0, error)
            result = json.loads(output)
            self.assertEqual(result["module"], "sample")
            self.assertEqual(result["core"]["background_processes"], 0)
            self.assertEqual(result["core"]["model_calls"], 0)

            code, output, error = self.run_cli("module", "disable", "sample")
            self.assertEqual(code, 0, error)
            self.assertIn("Disabled module: sample", output)
        finally:
            sys.path.remove(str(metadata_root))
            sys.path.remove(module_source)
            sys.modules.pop("sample", None)
            importlib.invalidate_caches()
