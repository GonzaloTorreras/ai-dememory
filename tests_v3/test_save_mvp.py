from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ai_dememory.cli import main
from ai_dememory.config import load_config
from ai_dememory.vault import Vault, VaultError, _exclusive_write_lock


class SaveMemoryMvpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "config")},
            clear=False,
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    @staticmethod
    def run_cli(*arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(arguments))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_setup_then_save_and_verify_one_memory_from_any_directory(self) -> None:
        vault_path = self.root / "vault"
        code, output, error = self.run_cli("setup", str(vault_path), "--yes", "--json")
        self.assertEqual(code, 0, error)
        setup = json.loads(output)
        self.assertEqual(setup["next"], ['ai-dememory remember "Something worth remembering"'])
        self.assertEqual(setup["search_index"]["state"], "not_built")
        self.assertEqual(setup["search_index"]["built_by"], "recall")
        self.assertEqual(Path(load_config().default_vault), vault_path.resolve())

        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(unrelated)
            code, output, error = self.run_cli(
                "remember",
                "El Markdown es la memoria canónica.",
                "--title",
                "Regla de almacenamiento",
                "--json",
            )
        finally:
            os.chdir(previous)

        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertTrue(result["saved"])
        self.assertTrue(result["verified"])

        saved_path = Path(result["path"])
        self.assertTrue(saved_path.is_file())
        memory = Vault.open(vault_path).read_memory(saved_path)
        self.assertEqual(memory.memory_id, result["memory_id"])
        self.assertEqual(memory.title, "Regla de almacenamiento")
        self.assertEqual(memory.content, "El Markdown es la memoria canónica.")
        self.assertFalse((vault_path / "indexes" / "memory.sqlite").exists())

    def test_readback_failure_never_reports_a_successful_save(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)

        with patch.object(Vault, "read_memory", side_effect=VaultError("read-back unavailable")):
            code, output, error = self.run_cli("remember", "Do not claim unverified writes", "--json")

        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("read-back unavailable", error)
        self.assertEqual(list((vault_path / "memories").glob("*.md")), [])

    def test_human_output_explains_the_result_and_location(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)

        code, output, error = self.run_cli(
            "remember", "A useful result is understandable.", "--title", "Clear result"
        )

        self.assertEqual(code, 0, error)
        self.assertIn("Saved and verified: Clear result", output)
        self.assertIn(str(vault_path / "memories"), output)

    def test_unrelated_malformed_markdown_does_not_block_a_new_save(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        (vault_path / "memories" / "broken.md").write_text(
            "not canonical Markdown", encoding="utf-8"
        )

        code, output, error = self.run_cli("remember", "A new independent memory", "--json")

        self.assertEqual(code, 0, error)
        self.assertTrue(json.loads(output)["verified"])

    def test_file_limit_is_enforced_before_a_save_can_exceed_it(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)

        with patch("ai_dememory.vault.MAX_MEMORY_FILES", 1):
            code, _, error = self.run_cli("remember", "First memory", "--json")
            self.assertEqual(code, 0, error)
            code, output, error = self.run_cli("remember", "Second memory", "--json")

        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("1-memory limit", error)
        self.assertEqual(len(list((vault_path / "memories").glob("*.md"))), 1)

    def test_concurrent_writer_fails_fast_and_can_retry_after_release(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)

        with _exclusive_write_lock(vault_path / ".ai-dememory.write.lock"):
            code, output, error = self.run_cli("remember", "Concurrent save", "--json")

        self.assertEqual(code, 2)
        self.assertEqual(output, "")
        self.assertIn("already in progress", error)
        code, output, error = self.run_cli("remember", "Retry succeeds", "--json")
        self.assertEqual(code, 0, error)
        self.assertTrue(json.loads(output)["verified"])

    def test_supplied_memory_id_cannot_escape_the_vault(self) -> None:
        vault_path = self.root / "vault"
        vault = Vault.create(vault_path)
        escaped = self.root / "escaped.md"

        with self.assertRaisesRegex(VaultError, "32 lowercase hexadecimal"):
            vault.remember(
                "Never escape the vault",
                "Contained",
                memory_id="x/../../../../escaped",
            )

        self.assertFalse(escaped.exists())
        self.assertEqual(list((vault_path / "memories").glob("*.md")), [])


if __name__ == "__main__":
    unittest.main()
