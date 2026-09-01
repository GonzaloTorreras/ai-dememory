from __future__ import annotations

import json
import os
from pathlib import Path

from ai_dememory.proposals import ProposalStore
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class ReviewMemoryMvpTests(V3TestCase):
    def create_vault_and_proposal(self, title: str, content: str):
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        vault = Vault.open(vault_path)
        return vault, ProposalStore(vault).propose(title, content)

    def test_list_and_show_explain_one_pending_proposal_from_any_directory(self) -> None:
        vault, proposal = self.create_vault_and_proposal(
            "Review this idea", "Only a person may approve this content."
        )
        self.assertEqual(vault.memory_count(), 0)

        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(unrelated)
            code, output, error = self.run_cli("review", "--json")
            self.assertEqual(code, 0, error)
            result = json.loads(output)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["proposals"][0]["status"], "pending")

            code, output, error = self.run_cli("review", "show", proposal.proposal_id[:8])
        finally:
            os.chdir(previous)

        self.assertEqual(code, 0, error)
        self.assertIn("Proposal: Review this idea", output)
        self.assertIn("Status: pending", output)
        self.assertIn("Only a person may approve this content.", output)

    def test_accept_creates_verified_memory_without_building_search(self) -> None:
        vault, proposal = self.create_vault_and_proposal(
            "Accepted idea", "This becomes canonical only after review."
        )
        index_path = vault.indexes_dir / "memory.sqlite"

        code, output, error = self.run_cli(
            "review", "accept", proposal.proposal_id[:8], "--json"
        )

        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(result["proposal"]["status"], "accepted")
        self.assertTrue(result["memory"]["saved"])
        self.assertTrue(result["memory"]["verified"])
        self.assertTrue(Path(result["memory"]["path"]).is_file())
        self.assertEqual(vault.memory_count(), 1)
        self.assertFalse(index_path.exists())

    def test_reject_is_clear_and_never_creates_memory(self) -> None:
        vault, proposal = self.create_vault_and_proposal(
            "Rejected idea", "This should not become canonical."
        )

        code, output, error = self.run_cli("review", "reject", proposal.proposal_id[:8])

        self.assertEqual(code, 0, error)
        self.assertIn("Rejected proposal: Rejected idea", output)
        self.assertEqual(vault.memory_count(), 0)
        code, output, error = self.run_cli("review")
        self.assertEqual(code, 0, error)
        self.assertEqual(output.strip(), "No pending proposals.")

