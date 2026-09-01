from __future__ import annotations

import json

from tests_v3.test_core import V3TestCase


class StatusMvpTests(V3TestCase):
    def test_human_status_explains_the_current_vault_without_side_effects(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)

        code, output, error = self.run_cli("status")

        self.assertEqual(code, 0, error)
        self.assertIn("Vault: vault", output)
        self.assertIn(f"Location: {vault_path.resolve()}", output)
        self.assertIn("Memories: 0", output)
        self.assertIn("Pending proposals: 0", output)
        self.assertIn("Search index: not built", output)
        self.assertIn("Enabled modules: none", output)
        self.assertIn("Background processes: 0", output)
        self.assertIn("Model calls: 0", output)
        self.assertFalse((vault_path / "indexes" / "memory.sqlite").exists())

    def test_status_reflects_saved_memory_and_enabled_module(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        code, _, error = self.run_cli("remember", "Useful local fact.", "--title", "Fact")
        self.assertEqual(code, 0, error)
        code, _, error = self.run_cli("module", "enable", "mcp")
        self.assertEqual(code, 0, error)

        code, output, error = self.run_cli("status")
        self.assertEqual(code, 0, error)
        self.assertIn("Memories: 1", output)
        self.assertIn("Enabled modules: mcp", output)

        code, output, error = self.run_cli("status", "--json")
        self.assertEqual(code, 0, error)
        status = json.loads(output)
        self.assertEqual(status["memories"], 1)
        self.assertEqual(status["enabled_modules"], ["mcp"])
        self.assertEqual(status["index"]["state"], "not_built")
