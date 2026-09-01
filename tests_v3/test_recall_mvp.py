from __future__ import annotations

import json
import os
from pathlib import Path

from tests_v3.test_core import V3TestCase


class RecallMemoryMvpTests(V3TestCase):
    def test_recall_from_any_directory_builds_search_only_when_needed(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        code, _, error = self.run_cli(
            "remember",
            "Canonical Markdown can be found later.",
            "--title",
            "Recall contract",
            "--json",
        )
        self.assertEqual(code, 0, error)
        index_path = vault_path / "indexes" / "memory.sqlite"
        self.assertFalse(index_path.exists())

        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(unrelated)
            code, output, error = self.run_cli("recall", "canonical later", "--json")
        finally:
            os.chdir(previous)

        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["query"], "canonical later")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["title"], "Recall contract")
        self.assertTrue(Path(result["results"][0]["path"]).is_file())
        self.assertTrue(index_path.is_file())

    def test_human_recall_explains_matches_and_empty_results(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        code, _, error = self.run_cli(
            "remember", "A searchable memory body.", "--title", "Searchable"
        )
        self.assertEqual(code, 0, error)

        code, output, error = self.run_cli("recall", "searchable")
        self.assertEqual(code, 0, error)
        self.assertIn("Found 1 matching memory.", output)
        self.assertIn("Searchable", output)
        self.assertIn(str(vault_path.resolve() / "memories"), output)

        code, output, error = self.run_cli("recall", "absent-term")
        self.assertEqual(code, 0, error)
        self.assertEqual(output.strip(), "No matching memories.")

