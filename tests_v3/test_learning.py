from __future__ import annotations

from unittest.mock import patch

from ai_dememory.builtin_modules.mcp import call_tool, handle_request
from ai_dememory.core import CoreServices
from ai_dememory.proposals import ProposalStore
from ai_dememory.vault import Vault, _exclusive_write_lock
from tests_v3.test_core import V3TestCase


class LearningTests(V3TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.vault = Vault.create(self.root / "vault")
        self.services = CoreServices(self.vault)

    def learn(self, content="Use Python for this project", scope="project:a", event="one", **kwargs):
        source = kwargs.pop("source", {
            "provider": "test", "session": "session-a", "turn": event,
            "evidence_kind": "user_statement", "excerpt": content,
        })
        return self.services.learn("Project decision", content, scope, source, event, **kwargs)

    def test_explicit_learning_is_retrieved_in_scope_with_provenance(self):
        saved = self.learn()
        self.assertEqual(saved["admission"], "created")
        self.assertEqual(self.services.search("Python"), [])
        self.assertEqual(self.services.search("Python", scope="project:b"), [])
        result = self.services.context("Python", scope="project:a")
        self.assertEqual(result["memory_ids"], [saved["memory_id"]])
        self.assertEqual(result["sources"][0]["source"]["provider"], "test")
        self.assertIsNone(self.services.get(saved["memory_id"], scope="project:b"))
        reread = Vault.open(self.vault.root).get(saved["memory_id"])
        self.assertEqual(reread.source, saved["source"])
        self.vault.remember("Global Python preference", "Global")
        self.assertEqual(len(self.services.search("Python", scope="project:a")), 2)
        self.assertEqual(len(self.services.search("Python", scope="project:b")), 1)
        self.assertEqual(len(self.services.list_memories(scope="project:a")), 1)

    def test_retry_and_duplicate_content_do_not_add_memories(self):
        first = self.learn()
        retry = self.learn()
        duplicate = self.learn(event="another-turn")
        self.assertEqual(retry["admission"], "duplicate")
        self.assertEqual(duplicate["memory_id"], first["memory_id"])
        self.assertEqual(self.vault.memory_count(), 1)

    def test_inference_is_provisional_and_cannot_replace_decision(self):
        active = self.learn(key="runtime")
        source = {**active["source"], "evidence_kind": "inference", "excerpt": "Perhaps Rust"}
        provisional = self.learn("Perhaps Rust", event="two", key="runtime", source=source)
        self.assertEqual(provisional["status"], "provisional")
        self.assertEqual(self.services.search("Rust", scope="project:a"), [])
        self.assertIsNone(self.services.get(provisional["memory_id"], scope="project:a"))
        self.assertEqual(len(self.services.list_memories(scope="project:a", include_inactive=True)), 2)
        self.assertEqual(self.vault.get(active["memory_id"]).status, "active")
        with self.assertRaisesRegex(ValueError, "Provisional"):
            self.learn("Maybe Go", source=source, supersedes=active["memory_id"])

    def test_retry_with_changed_model_output_keeps_original_occurrence(self):
        first = self.learn(key="runtime")
        changed_source = {**first["source"], "evidence_kind": "inference", "excerpt": "Maybe use Rust instead"}
        retry = self.services.learn("Different title", "Maybe use Rust instead", "project:a",
                                    changed_source, "one", key="other-key")
        self.assertEqual(retry["admission"], "duplicate")
        self.assertEqual(retry["memory_id"], first["memory_id"])
        self.assertEqual(retry["content"], first["content"])
        self.assertEqual(retry["status"], "active")
        self.assertEqual(self.vault.memory_count(), 1)
        self.services.forget(first["memory_id"], "project:a")
        retried_after_forget = self.services.learn("Yet another title", "Try Go", "project:a",
                                                   changed_source, "one")
        self.assertEqual(retried_after_forget["memory_id"], first["memory_id"])
        self.assertEqual(retried_after_forget["status"], "forgotten")
        self.assertEqual(self.vault.memory_count(), 1)

    def test_status_distinguishes_core_policy_from_process_telemetry(self):
        self.assertEqual(self.services.status()["resource_scope"], "core policy, not process telemetry")

    def test_correction_and_undo_preserve_history_without_cross_scope_writes(self):
        old = self.learn(key="runtime")
        other = self.learn(scope="project:b", key="runtime")
        new = self.learn("Use Rust for this project", event="two", key="runtime")
        self.assertEqual(new["supersedes"], old["memory_id"])
        self.assertEqual(self.services.search("Python", scope="project:a"), [])
        self.assertEqual(self.vault.get(old["memory_id"]).status, "superseded")
        self.assertEqual(self.vault.get(other["memory_id"]).status, "active")
        with self.assertRaisesRegex(ValueError, "requested scope"):
            self.services.forget(new["memory_id"], scope="project:b")
        undone = self.services.forget(new["memory_id"], scope="project:a")
        self.assertEqual(undone["restored_memory_id"], old["memory_id"])
        self.assertEqual(self.services.search("Rust", scope="project:a"), [])
        self.assertEqual(len(self.services.search("Python", scope="project:a")), 1)
        retry = self.learn("Use Rust for this project", event="two", key="runtime")
        self.assertEqual(retry["status"], "forgotten")
        self.assertEqual(self.vault.memory_count(), 3)

    def test_learning_rejects_invalid_inputs_before_writing(self):
        for changes in ({"scope": "../other"}, {"source": {}}, {"provisional": "false"},
                        {"content": None}, {"event": None}, {"key": "../x"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.learn(**changes)
        with self.assertRaisesRegex(ValueError, "secret material"):
            self.learn(source={"provider": "test", "session": "s", "turn": "t",
                               "evidence_kind": "user_statement", "excerpt": "-----BEGIN PRIVATE KEY-----"})
        self.assertEqual(self.vault.memory_count(), 0)

    def test_provisional_duplicates_and_explicit_confirmation(self):
        source = {"provider": "test", "session": "s", "turn": "t",
                  "evidence_kind": "inference", "excerpt": "Python is appropriate"}
        first = self.learn(source=source)
        duplicate = self.learn(source=source, event="again")
        self.assertEqual(first["memory_id"], duplicate["memory_id"])
        confirmed = self.learn(source={**source, "evidence_kind": "user_statement"}, event="confirmed")
        self.assertEqual(confirmed["status"], "active")
        self.assertEqual(len(self.services.search("Python", scope="project:a")), 1)

    def test_context_keeps_match_near_end_of_long_memory(self):
        memory = self.vault.remember("Unrelated filler. " * 400 + "The deployment target is RaspberryPi.", "Deployment")
        result = self.services.context("RaspberryPi", max_chars=256)
        self.assertIn("RaspberryPi", result["context"])
        self.assertEqual(result["memory_ids"], [memory.memory_id])
        self.assertLessEqual(len(result["context"]), 256)

    def test_mcp_rejects_null_and_coerced_types_without_writing(self):
        for arguments in ({"title": None, "content": None}, {"title": 123, "content": "body"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                call_tool(self.services, "memory.propose", arguments)
        for arguments in ({"query": None}, {"query": "test", "limit": True},
                          {"query": "test", "limit": "2"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                call_tool(self.services, "memory.search", arguments)
        result = handle_request(self.services, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                               "params": {"name": "memory.propose", "arguments": None}})
        self.assertIn("error", result)
        self.assertEqual(ProposalStore(self.vault).count(), 0)

    def test_mcp_learning_and_forgetting_flow(self):
        args = {"title": "Decision", "content": "Use Python", "scope": "project:a", "event_id": "turn-1",
                "source": {"provider": "test", "session": "s", "turn": "1",
                           "evidence_kind": "user_statement", "excerpt": "Use Python"}}
        memory = call_tool(self.services, "memory.learn", args)
        self.assertEqual(memory["status"], "active")
        result = call_tool(self.services, "memory.forget", {"memory_id": memory["memory_id"], "scope": "project:a"})
        self.assertEqual(result["status"], "forgotten")

    def test_correction_failure_rolls_back_new_memory(self):
        previous = self.learn(key="runtime")
        original_write = Vault._write_memory

        def write(vault, memory):
            if memory.status == "superseded":
                raise OSError("simulated write failure")
            return original_write(vault, memory)

        with patch.object(Vault, "_write_memory", write), self.assertRaises(OSError):
            self.learn("Use Rust", event="two", key="runtime")
        self.assertEqual(self.vault.memory_count(), 1)
        self.assertEqual(self.vault.get(previous["memory_id"]).status, "active")

    def test_proposal_decision_lock_prevents_competing_accept_or_reject(self):
        store = ProposalStore(self.vault)
        proposal = store.propose("Decision", "Use Python")
        with _exclusive_write_lock(self.vault.root / ".ai-dememory.proposals.lock"):
            with self.assertRaisesRegex(ValueError, "write is already in progress"):
                store.decide(proposal.proposal_id, True)
            with self.assertRaisesRegex(ValueError, "write is already in progress"):
                store.decide(proposal.proposal_id, False)
        self.assertEqual(store.get(proposal.proposal_id).status, "pending")
        self.assertEqual(self.vault.memory_count(), 0)
