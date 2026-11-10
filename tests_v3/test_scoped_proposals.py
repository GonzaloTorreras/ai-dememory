from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from ai_dememory.core import CoreServices
from ai_dememory.proposals import ProposalError, ProposalStore
from ai_dememory.quality import evidence_revision
from ai_dememory.vault import Vault


class ScopedProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Vault.create(Path(self.temp.name) / "vault")
        self.services = CoreServices(self.vault)
        self.scope = "project:one"

    def source(self, content="Source statement.", *, expires_at=None):
        return self.vault.remember(content, "Source", scope=self.scope, expires_at=expires_at)

    def proposal_for(self, memory):
        revision = evidence_revision(memory.title, memory.content, memory.source)
        return ProposalStore(self.vault).propose(
            "Scoped summary", "A reviewed summary.", scope=self.scope,
            source_revisions={memory.memory_id: revision},
        )

    def test_acceptance_writes_only_to_the_proposal_scope(self):
        source = self.source()
        proposal = self.proposal_for(source)
        accepted, memory = ProposalStore(self.vault).decide(proposal.proposal_id, accept=True)
        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(memory.scope, self.scope)
        self.assertEqual(len(self.services.list_memories("global")), 0)
        self.assertEqual(len(self.services.list_memories(self.scope)), 2)

    def test_correction_after_proposal_creation_rejects_stale_acceptance(self):
        source = self.services.learn(
            "Endpoint", "Use the old endpoint.", self.scope,
            {"provider": "test", "session": "session", "turn": "one",
             "evidence_kind": "user_statement", "excerpt": "Use the old endpoint."},
            "source-one", key="endpoint",
        )
        proposal = self.proposal_for(self.vault.get(source["memory_id"]))
        self.services.learn(
            "Endpoint", "Use the new endpoint.", self.scope,
            {"provider": "test", "session": "session", "turn": "two",
             "evidence_kind": "user_statement", "excerpt": "Use the new endpoint."},
            "source-two", key="endpoint",
        )
        with self.assertRaisesRegex(ProposalError, "stale"):
            ProposalStore(self.vault).decide(proposal.proposal_id, accept=True)
        self.assertEqual(len(self.services.list_memories(self.scope)), 1)
        self.assertEqual(ProposalStore(self.vault).get(proposal.proposal_id).status, "pending")

    def test_forgotten_or_expired_source_rejects_stale_acceptance(self):
        forgotten = self.source("Forget this source.")
        forgotten_proposal = self.proposal_for(forgotten)
        self.services.forget(forgotten.memory_id, self.scope)
        with self.assertRaisesRegex(ProposalError, "stale"):
            ProposalStore(self.vault).decide(forgotten_proposal.proposal_id, accept=True)

        expired = self.source("Expired source.", expires_at="2020-01-01T00:00:00Z")
        expired_proposal = self.proposal_for(expired)
        with self.assertRaisesRegex(ProposalError, "stale"):
            ProposalStore(self.vault).decide(expired_proposal.proposal_id, accept=True)

    def test_source_scope_mismatch_rejects_stale_acceptance(self):
        source = self.source("Scope-bound source.")
        proposal = self.proposal_for(source)
        self.vault._write_memory(replace(source, scope="project:other"))
        with self.assertRaisesRegex(ProposalError, "stale"):
            ProposalStore(self.vault).decide(proposal.proposal_id, accept=True)


if __name__ == "__main__":
    unittest.main()
