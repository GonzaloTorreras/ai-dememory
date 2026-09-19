from __future__ import annotations

import copy
import json

from ai_dememory.builtin_modules.mcp import call_tool
from ai_dememory.core import CoreServices
from ai_dememory.quality import confidence_status
from ai_dememory.settings import load_settings, save_settings
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class MemoryQualityTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.vault = Vault.create(self.root / "vault")
        self.services = CoreServices(self.vault)

    def learn(self, event="one", **extra):
        return call_tool(self.services, "memory.learn", {
            "title": "Language", "content": extra.pop("content", "Prefer Python"),
            "scope": "project:a", "event_id": event,
            "source": {"provider": "test", "session": "s", "turn": event,
                       "excerpt": "Prefer Python", "evidence_kind": "user_statement"},
            **extra,
        }, "project:a")

    def test_old_markdown_defaults_without_rewrite(self):
        memory = self.vault.remember("Use Python")
        before = memory.path.read_bytes()
        self.assertNotIn(b"importance:", before)
        read = self.vault.get(memory.memory_id)
        self.assertEqual((read.importance, read.importance_origin, read.confidence), ("normal", "default", {}))
        self.assertEqual(memory.path.read_bytes(), before)

    def test_manual_metadata_edit_survives_reopen_and_index_rebuild(self):
        memory = self.vault.remember("Prefer Python", scope="project:a")
        self.services.search("Python", scope="project:a")
        result = self.vault.set_importance(memory.memory_id, "project:a", "high")
        self.assertEqual((result["importance"], result["importance_origin"]), ("high", "user"))
        self.assertEqual(Vault.open(self.vault.root).get(memory.memory_id).content, memory.content)
        self.assertEqual(self.vault.memory_count(), 1)
        self.assertEqual(self.services.context("Python", scope="project:a")["memory_ids"], [memory.memory_id])
        with self.assertRaises(ValueError):
            self.vault.set_importance(memory.memory_id, "project:b", "low")
        self.vault.set_importance(memory.memory_id, "project:a", "normal")
        self.assertEqual(self.vault.get(memory.memory_id).importance, "normal")

    def test_host_correction_preserves_manual_priority_and_undo(self):
        first = self.learn(key="language")
        self.vault.set_importance(first["memory_id"], "project:a", "high")
        corrected = self.learn("two", key="language", content="Prefer Rust", importance="low")
        self.assertEqual((corrected["importance"], corrected["importance_origin"]), ("high", "user"))
        self.services.forget(corrected["memory_id"], "project:a")
        self.assertEqual(self.vault.get(first["memory_id"]).importance, "high")

    def test_confidence_is_advisory_revision_bound_and_not_a_reward(self):
        saved = self.learn(confidence={"support": 0.99, "certainty": 0.99, "model": "synthetic", "rubric": "v1"})
        memory = self.vault.get(saved["memory_id"])
        self.assertEqual(confidence_status(memory), "advisory")
        before = memory.path.read_bytes()
        for _ in range(3):
            self.services.context("Python", scope="project:a")
        self.assertEqual(before, memory.path.read_bytes())
        memory.path.write_text(memory.path.read_text(encoding="utf-8").replace("Prefer Python\n", "Prefer Rust\n"), encoding="utf-8")
        self.assertEqual(confidence_status(self.vault.get(memory.memory_id)), "stale")
        hit = self.services.search("Rust", scope="project:a")[0]
        self.assertEqual(hit["details"]["confidence_status"], "stale")
        self.assertFalse(hit["details"]["confidence_applied"])

    def test_confidence_cannot_promote_inference(self):
        result = self.learn(provisional=True, importance="high", confidence={"support": 1, "model": "test", "rubric": "v1"})
        self.assertEqual(result["status"], "provisional")
        self.assertEqual(self.services.search("Python", scope="project:a"), [])

    def test_invalid_metadata_rejected_without_write(self):
        for priority in ("urgent", "", False, 3, {}, []):
            with self.subTest(priority=priority), self.assertRaises(ValueError):
                self.vault.remember("Synthetic", importance=priority)
        for confidence in ({"support": float("nan"), "model": "test", "rubric": "v1"},
                           {"support": True, "model": "test", "rubric": "v1"},
                           {"support": 1, "model": "test", "rubric": "v1", "method": "verified"},
                           {"support": 0.8}, []):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                self.learn(confidence=confidence)
        self.assertEqual(self.vault.memory_count(), 0)

    def test_ranking_settings_are_optional_bounded_and_confidence_locked(self):
        settings = load_settings(self.vault)
        old = copy.deepcopy(settings)
        old.pop("ranking")
        self.assertEqual(save_settings(self.vault, old)["ranking"], settings["ranking"])
        for value in (-1, 0.26, True, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                save_settings(self.vault, {**settings, "ranking": {"importance_weight": value, "confidence_weight": 0}})
        with self.assertRaisesRegex(ValueError, "assessor"):
            save_settings(self.vault, {**settings, "ranking": {"importance_weight": 0.1, "confidence_weight": 0.1}})
        save_settings(self.vault, {**settings, "ranking": {"importance_weight": 0, "confidence_weight": 0}})
        self.assertEqual(load_settings(self.vault)["ranking"]["importance_weight"], 0)

    def test_cli_priority_reaches_canonical_memory(self):
        code, output, error = self.run_cli("--vault", str(self.vault.root), "--json", "remember", "Prefer Python", "--importance", "high")
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["importance"], "high")
