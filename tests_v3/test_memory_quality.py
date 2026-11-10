from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

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

    def test_correction_inherits_lifecycle_until_explicit_editor_reset(self):
        first = self.learn(key="runtime", memory_kind="episode", expires_at="2030-01-01T00:00:00Z")
        corrected = self.learn("two", key="runtime", content="Prefer Rust")
        self.assertEqual((corrected["memory_kind"], corrected["expires_at"]),
                         ("episode", "2030-01-01T00:00:00Z"))
        reset = self.vault.update_quality(corrected["memory_id"], "project:a",
                                          {"memory_kind": "durable", "expires_at": None})
        self.assertEqual((reset["memory_kind"], reset["expires_at"]), ("durable", None))

    def test_new_assertion_renews_expired_memory_but_retry_does_not(self):
        for keyed in (False, True):
            with self.subTest(keyed=keyed):
                extra = {"key": "expired"} if keyed else {}
                first = self.learn("expired-" + str(keyed), memory_kind="episode", expires_at="2000-01-01T00:00:00Z", **extra)
                retry = self.learn("expired-" + str(keyed), **extra)
                self.assertEqual(retry["memory_id"], first["memory_id"])
                fresh = self.learn("renewed-" + str(keyed), **extra)
                self.assertNotEqual(fresh["memory_id"], first["memory_id"])
                self.assertIsNone(fresh["expires_at"])
                self.assertIn(fresh["memory_id"], self.services.context("Python", scope="project:a")["memory_ids"])

    def test_new_assertion_renews_aged_episode_and_accepts_explicit_expiry(self):
        first = self.learn("old", key="episode", memory_kind="episode")
        old = self.vault.get(first["memory_id"])
        self.vault._write_memory(replace(old, created_at="2000-01-01T00:00:00Z"))
        settings = load_settings(self.vault); settings["lifecycle"]["episode_recall_days"] = 7
        save_settings(self.vault, settings)
        self.assertEqual(self.services.context("Python", scope="project:a")["memory_ids"], [])
        fresh = self.learn("new", key="episode", expires_at="2030-01-01T00:00:00Z")
        self.assertEqual(fresh["memory_kind"], "episode")
        self.assertIn(fresh["memory_id"], self.services.context("Python", scope="project:a")["memory_ids"])
        extended = self.learn("extended", key="episode", expires_at="2031-01-01T00:00:00Z")
        self.assertEqual(extended["expires_at"], "2031-01-01T00:00:00Z")

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

    def test_expiry_and_episode_window_hide_not_delete(self):
        old = self.vault.remember("Old deployment result", memory_kind="episode", scope="project:a")
        self.vault._write_memory(replace(old, created_at=(datetime.now(timezone.utc) - timedelta(days=40)).isoformat()))
        expired = self.vault.remember("Expired deployment result", expires_at="2000-01-01T00:00:00Z", scope="project:a")
        self.assertIsNone(self.services.get(expired.memory_id, scope="project:a"))
        self.assertEqual(len(self.services.list_memories("project:a")), 1)
        settings = load_settings(self.vault)
        settings["lifecycle"]["episode_recall_days"] = 30
        save_settings(self.vault, settings)
        self.assertEqual(self.services.context("deployment", scope="project:a")["memory_ids"], [])
        self.assertEqual(self.services.list_memories("project:a"), [])
        history = self.services.list_memories("project:a", include_inactive=True)
        self.assertEqual(len(history), 2)
        self.assertTrue(all(not row["recall_eligible"] for row in history))
        self.assertEqual(self.vault.memory_count(), 2)
        self.vault.update_quality(expired.memory_id, "project:a", {"expires_at": None, "memory_kind": "durable"})
        self.assertIsNotNone(self.services.get(expired.memory_id, scope="project:a"))

    def test_lifecycle_validation_is_explicit_and_timezone_aware(self):
        for expiry in ("next week", "2026-10-02", "2026-10-02T00:00:00", True, ""):
            with self.subTest(expiry=expiry), self.assertRaises(ValueError):
                self.vault.remember("Synthetic", expires_at=expiry)
        memory = self.vault.remember("Synthetic", memory_kind="durable", expires_at="2026-10-02T02:00:00+02:00")
        self.assertEqual(memory.expires_at, "2026-10-02T00:00:00Z")
        self.assertEqual(self.vault.get(memory.memory_id).memory_kind, "durable")

    def test_thirty_synthetic_recall_episodes(self):
        # Reusable lexical baseline, not a claim of multilingual semantic accuracy.
        cases = [
            ("Python", "Prefer Python for data scripts."), ("PostgreSQL", "Use PostgreSQL for transactional storage."),
            ("RaspberryPi", "The deployment target is RaspberryPi."), ("Redis", "Redis is a disposable cache."),
            ("SQLite", "SQLite stays on local disk."), ("Firefox", "Test the interface in Firefox."),
            ("Tuesday", "Run the maintenance on Tuesday."), ("parquet", "Export the dataset as parquet."),
            ("Celsius", "Store temperatures in Celsius."), ("invoices", "Keep invoices outside the source repository."),
            ("backups", "Verify backups before replacing the disk."), ("accessibility", "Include accessibility in UI reviews."),
            ("Svelte", "Build this interface with Svelte."), ("pagination", "Use cursor pagination for results."),
            ("timeouts", "Bound network requests with timeouts."),
            ("presupuesto", "El presupuesto mensual es limitado."), ("caducidad", "La caducidad debe ser explícita."),
            ("jardín", "El jardín utiliza riego por goteo."), ("escalera", "La escalera de entrada tiene seis peldaños."),
            ("azulejos", "Los azulejos del baño son blancos."), ("fachada", "La fachada tiene orientación norte."),
            ("viernes", "La revisión semanal se realiza el viernes."), ("recibos", "Los recibos son historial operativo."),
            ("contraseñas", "Las contraseñas no deben guardarse en recuerdos."), ("ventilación", "Priorizar la ventilación natural."),
            ("proveedor", "El proveedor alternativo es local."), ("consolidación", "La consolidación mantiene proyectos separados."),
            ("aprendizajes", "Guardar aprendizajes estables y concisos."), ("madera", "La mesa del comedor es de madera."),
            ("calendario", "El calendario usa la zona horaria local."),
        ]
        for i, (term, content) in enumerate(cases):
            with self.subTest(term=term):
                scope = f"project:case-{i}"
                saved = self.vault.remember(content, scope=scope, importance="high")
                query = f"please tell me about the {term}" if i < 15 else f"por favor dime sobre {term}"
                result = self.services.context(query, scope=scope)
                self.assertEqual(result["memory_ids"], [saved.memory_id])
                self.assertEqual(self.services.context(term, scope="project:unrelated")["memory_ids"], [])
