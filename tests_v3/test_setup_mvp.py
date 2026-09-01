from __future__ import annotations

import json

from tests_v3.test_core import V3TestCase


class SetupMvpTests(V3TestCase):
    def test_noninteractive_human_setup_ends_with_one_clear_next_action(self) -> None:
        vault_path = self.root / "my vault"

        code, output, error = self.run_cli("setup", str(vault_path), "--yes")

        self.assertEqual(code, 0, error)
        self.assertIn("Vault ready: my vault", output)
        self.assertIn(f"Location: {vault_path.resolve()}", output)
        self.assertIn("Saved as default: yes", output)
        self.assertIn("Search index: not built (recall builds it when needed)", output)
        self.assertIn("Background processes: 0", output)
        self.assertIn("Model calls: 0", output)
        self.assertIn("Network: off", output)
        self.assertIn('Next: ai-dememory remember "Something worth remembering"', output)
        self.assertFalse(output.lstrip().startswith("{"))

    def test_setup_json_contract_remains_machine_readable(self) -> None:
        vault_path = self.root / "vault"

        code, output, error = self.run_cli("setup", str(vault_path), "--yes", "--json")

        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["vault"], str(vault_path.resolve()))
        self.assertTrue(result["select_as_default"])
        self.assertEqual(result["search_index"]["state"], "not_built")
        self.assertEqual(result["next"], ['ai-dememory remember "Something worth remembering"'])

    def test_no_select_does_not_suggest_a_command_that_needs_a_default(self) -> None:
        vault_path = self.root / "unselected"

        code, output, error = self.run_cli(
            "setup", str(vault_path), "--yes", "--no-select"
        )

        self.assertEqual(code, 0, error)
        self.assertIn("Saved as default: no", output)
        self.assertIn(
            "Next: Use --vault with the location above when running remember.",
            output,
        )
