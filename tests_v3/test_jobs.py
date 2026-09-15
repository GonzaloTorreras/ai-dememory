from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from ai_dememory.core import CoreServices
from ai_dememory.jobs import LearningJobs
from ai_dememory.proposals import ProposalStore
from ai_dememory.settings import load_settings, save_settings
from ai_dememory.vault import Vault


class LearningJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Vault.create(Path(self.temp.name) / "vault")
        self.services = CoreServices(self.vault)
        self.engine = Mock()
        self.factory = Mock(return_value=self.engine)
        self.jobs = LearningJobs(self.services, self.factory)
        self.now = datetime(2026, 9, 6, tzinfo=timezone.utc)

    def output(self, data):
        self.engine.run.return_value = {"text": json.dumps(data), "provider": "local",
                                        "model": "test-model", "usage": {}, "attempts": []}

    def route(self):
        settings = load_settings(self.vault)
        settings["providers"] = {"local": {"kind": "openai_compatible",
            "base_url": "http://127.0.0.1:11434/v1", "api_key_env": "", "model": "test"}}
        settings["routes"]["consolidate"] = {
            "primary": "local", "fallback": [], "max_output_tokens": 1000}
        save_settings(self.vault, settings)

    def schedule(self, enabled=True, hours=168, scope="global"):
        settings = load_settings(self.vault)
        settings["schedule"] = {"enabled": enabled, "interval_hours": hours, "scope": scope}
        save_settings(self.vault, settings)

    def remember(self, text, scope="global", key=None, supersedes=None):
        source = {"provider": "test", "session": "session", "turn": text[:20],
                  "evidence_kind": "user_statement", "excerpt": text}
        return self.services.learn(text[:30], text, scope, source, text + scope + str(key),
                                   key=key, supersedes=supersedes)

    def test_user_quote_active_assistant_and_paraphrase_provisional(self):
        messages = [{"role": "user", "content": "Use Python. Keep functions short."},
                    {"role": "assistant", "content": "The issue is fixed."}]
        self.output({"memories": [
            {"title": "Language", "content": "Use Python.", "evidence": "Use Python.", "message_index": 0},
            {"title": "Fix", "content": "The issue is fixed.", "evidence": "The issue is fixed.", "message_index": 1},
            {"title": "Unsupported", "content": "Python never fails.", "evidence": "Use Python.", "message_index": 0},
        ]})
        result = self.jobs.extract(messages, "project:one", event_id="turn-1")
        self.assertEqual([m["status"] for m in result["learned"]], ["active", "provisional", "provisional"])
        self.assertEqual(len(self.services.list_memories("project:one")), 1)
        self.assertEqual(self.services.list_memories("global"), [])
        retry = self.jobs.extract(messages, "project:one", event_id="turn-1")
        self.assertEqual([m["memory_id"] for m in result["learned"]],
                         [m["memory_id"] for m in retry["learned"]])
        self.assertEqual(len(self.services.list_memories("project:one", include_inactive=True)), 3)

    def test_fabricated_quote_and_model_controlled_policy_rejected(self):
        self.output({"memories": [
            {"title": "Wrong", "content": "Use Python", "evidence": "not present", "message_index": 0},
            {"title": "Wrong", "content": "Use Python", "evidence": "Use Python", "message_index": 0,
             "evidence_kind": "verified_outcome"},
            {"title": "Wrong", "content": "Use Python", "evidence": "Use Python", "message_index": True},
        ]})
        result = self.jobs.extract([{"role": "user", "content": "Use Python"}], "global")
        self.assertEqual(result["rejected"], 3)
        self.assertEqual(result["learned"], [])

    def test_completed_receipt_replays_despite_changed_output_order_and_count(self):
        messages = [{"role": "user", "content": "Use Python. Keep functions short."}]
        self.output({"memories": [{"title": "Language", "content": "Use Python.",
            "evidence": "Use Python.", "message_index": 0}]})
        first = self.jobs.extract(messages, "project:one", event_id="stable-event")
        self.output({"memories": [
            {"title": "Style", "content": "Keep functions short.",
             "evidence": "Keep functions short.", "message_index": 0},
            {"title": "Other title", "content": "Use Python.",
             "evidence": "Use Python.", "message_index": 0}]})
        restarted = LearningJobs(self.services, self.factory)
        replay = restarted.extract(messages, "project:one", event_id="stable-event")
        self.assertEqual(first, replay)
        self.assertEqual(self.engine.run.call_count, 1)
        with closing(sqlite3.connect(self.vault.root / "runtime.sqlite")) as db:
            receipt = db.execute("SELECT event_key, result FROM extraction_receipts").fetchone()
        self.assertNotIn("stable-event", receipt[0])
        for text in ("Use Python", "Keep functions short", "Language", "source", "excerpt"):
            self.assertNotIn(text, receipt[1])

    def test_cross_event_content_duplicate_has_its_own_durable_receipt(self):
        messages = [{"role": "user", "content": "Use Python."}]
        self.output({"memories": [{"title": "Language", "content": "Use Python.",
            "evidence": "Use Python.", "message_index": 0}]})
        first = self.jobs.extract(messages, "global", event_id="event-one")
        duplicate = self.jobs.extract(messages, "global", event_id="event-two")
        self.assertEqual(duplicate["learned"][0]["memory_id"], first["learned"][0]["memory_id"])
        self.assertEqual(duplicate["learned"][0]["admission"], "duplicate")
        self.output({"memories": []})
        replay = LearningJobs(self.services, self.factory).extract(messages, "global", event_id="event-two")
        self.assertEqual(replay, duplicate)
        self.assertEqual(self.engine.run.call_count, 2)

    def test_failed_provider_can_retry_and_partial_admissions_survive_retry(self):
        messages = [{"role": "user", "content": "Use Python. Keep functions short."}]
        self.engine.run.side_effect = ValueError("provider unavailable")
        with self.assertRaises(ValueError):
            self.jobs.extract(messages, "global", event_id="retry-event")
        self.engine.run.side_effect = None
        self.output({"memories": [
            {"title": "Language", "content": "Use Python.",
             "evidence": "Use Python.", "message_index": 0},
            {"title": "Style", "content": "Keep functions short.",
             "evidence": "Keep functions short.", "message_index": 0}]})
        original = self.services.learn
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("temporary write failure")
            return original(*args, **kwargs)

        with patch.object(self.services, "learn", side_effect=fail_second):
            with self.assertRaises(ValueError):
                self.jobs.extract(messages, "global", event_id="retry-event")
        first_id = self.services.list_memories()[0]["memory_id"]
        result = LearningJobs(self.services, self.factory).extract(messages, "global", event_id="retry-event")
        self.assertEqual(result["learned"][0]["memory_id"], first_id)
        self.assertEqual(len(result["learned"]), 2)
        self.assertEqual(len(self.services.list_memories()), 2)
        self.assertEqual(self.engine.run.call_count, 3)

    def test_concurrent_same_occurrence_fails_fast_then_replays_without_call(self):
        entered, release = threading.Event(), threading.Event()
        messages = [{"role": "user", "content": "Use Python."}]
        self.output({"memories": [{"title": "Language", "content": "Use Python.",
            "evidence": "Use Python.", "message_index": 0}]})
        response = self.engine.run.return_value

        def held_provider(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test provider was not released")
            return response

        self.engine.run.side_effect = held_provider
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(self.jobs.extract, messages, "global", event_id="concurrent")
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(ValueError):
                    LearningJobs(self.services, self.factory).extract(messages, "global", event_id="concurrent")
            finally:
                release.set()
            first = future.result(timeout=5)
        replay = LearningJobs(self.services, self.factory).extract(messages, "global", event_id="concurrent")
        self.assertEqual(first, replay)
        self.assertEqual(self.engine.run.call_count, 1)

    def test_completed_empty_receipt_and_forgotten_memory_do_not_relearn(self):
        messages = [{"role": "user", "content": "Use Python."}]
        self.output({"memories": []})
        empty = self.jobs.extract(messages, "global", event_id="empty-event")
        self.output({"memories": [{"title": "Language", "content": "Use Python.",
            "evidence": "Use Python.", "message_index": 0}]})
        self.assertEqual(self.jobs.extract(messages, "global", event_id="empty-event"), empty)
        created = self.jobs.extract(messages, "global", event_id="memory-event")
        self.services.forget(created["learned"][0]["memory_id"])
        replay = self.jobs.extract(messages, "global", event_id="memory-event")
        self.assertEqual(replay["learned"][0]["status"], "forgotten")
        self.assertEqual(self.services.list_memories(), [])
        self.assertEqual(self.engine.run.call_count, 2)

    def test_secret_or_oversized_input_never_reaches_provider(self):
        for content in ("ghp_" + "A" * 30, "x" * 24001):
            with self.assertRaises(ValueError):
                self.jobs.extract([{"role": "user", "content": content}], "global")
        with self.assertRaises(ValueError):
            self.jobs.extract([{"role": "system", "content": "hello"}], "global")
        self.factory.assert_not_called()
        self.assertFalse((self.vault.root / "jobs.json").exists())

    def test_generated_key_cannot_replace_an_existing_memory(self):
        existing = self.remember("Use Python for the backend.", key="backend.language")
        self.output({"memories": [{"title": "Unrelated statement", "content": "Use Node here.",
            "evidence": "Use Node here.", "message_index": 0, "key": "backend.language"}]})
        result = self.jobs.extract([{"role": "user", "content": "Use Node here."}], "global")
        self.assertEqual(result["learned"], [])
        self.assertEqual(result["rejected"], 1)
        active = self.services.list_memories()
        self.assertEqual([row["memory_id"] for row in active], [existing["memory_id"]])
        self.assertEqual(active[0]["content"], "Use Python for the backend.")

    def test_deterministic_cleanup_stays_in_exact_scope_without_provider(self):
        self.vault.remember("Same content", "One")
        self.vault.remember("Same content", "Two")
        self.remember("Same content", "project:other")
        result = self.jobs.consolidate()
        self.assertEqual(result, {"cleaned": 1, "proposals": 0, "no_op": False})
        self.assertEqual(len(self.services.list_memories()), 1)
        self.assertEqual(len(self.services.list_memories("project:other")), 1)
        self.factory.assert_not_called()
        self.assertTrue(self.jobs.consolidate()["no_op"])

    def test_summary_is_proposal_with_valid_sources_and_deduplicated(self):
        a = self.remember("This project uses Python for the command line interface.")
        b = self.remember("This project uses Python for the HTTP workbench server.")
        self.route()
        self.output({"summary": {"title": "Python runtime", "content": "Python powers CLI and HTTP.",
                                 "memory_ids": [a["memory_id"], b["memory_id"]]}})
        self.assertEqual(self.jobs.consolidate()["proposals"], 1)
        self.assertTrue(self.jobs.consolidate()["no_op"])
        self.assertEqual(len(self.services.list_memories()), 2)
        proposals = ProposalStore(self.vault).list()
        self.assertEqual(len(proposals), 1)
        self.assertIn(a["memory_id"], proposals[0].content)

    def test_same_content_with_distinct_keys_is_preserved(self):
        first = self.remember("Use Python.", key="backend.language")
        second = self.remember("Use Python.", key="cli.language")
        self.assertTrue(self.jobs.consolidate()["no_op"])
        self.assertEqual({row["memory_id"] for row in self.services.list_memories()},
                         {first["memory_id"], second["memory_id"]})

    def test_duplicate_cleanup_does_not_undo_unkeyed_correction(self):
        prior = self.remember("Use the old endpoint.")
        current = self.remember("Use the new endpoint.", supersedes=prior["memory_id"])
        duplicate = self.vault.remember("Use the new endpoint.", "Another copy").to_dict()
        # Force the duplicate ahead of the correction so content-only cleanup
        # would incorrectly forget the correction and restore its predecessor.
        duplicate["created_at"] = "2020-01-01T00:00:00Z"
        current["created_at"] = "2021-01-01T00:00:00Z"
        with patch.object(self.services, "list_memories", return_value=[duplicate, current]):
            self.assertTrue(self.jobs.consolidate()["no_op"])
        self.assertEqual(self.vault.get(prior["memory_id"]).status, "superseded")
        self.assertEqual(self.vault.get(current["memory_id"]).status, "active")

    def test_unknown_summary_reference_rejected_without_proposal(self):
        a = self.remember("First durable statement.")
        self.remember("Second durable statement.")
        self.route()
        self.output({"summary": {"title": "Invented", "content": "Invented.",
                                 "memory_ids": [a["memory_id"], "unknown"]}})
        with self.assertRaises(ValueError):
            self.jobs.consolidate()
        self.assertEqual(ProposalStore(self.vault).count(), 0)

    def test_project_content_never_enters_unscoped_review_proposals(self):
        self.remember("Project private first statement.", "project:one")
        self.remember("Project private second statement.", "project:one")
        self.route()
        self.assertTrue(self.jobs.consolidate("project:one")["no_op"])
        self.factory.assert_not_called()
        self.assertEqual(ProposalStore(self.vault).count(), 0)

    def test_schedule_survives_restart_and_reschedules_interval(self):
        self.schedule()
        status = self.jobs.schedule_status(self.now)
        next_run = self.now + timedelta(hours=168)
        self.assertEqual(status["next_run_at"], next_run.isoformat().replace("+00:00", "Z"))
        restarted = LearningJobs(self.services, self.factory)
        self.assertIsNone(restarted.run_due(self.now + timedelta(hours=1)))
        self.assertTrue(restarted.run_due(next_run)["no_op"])
        self.assertIsNone(restarted.run_due(next_run))
        self.schedule(hours=24)
        changed = restarted.schedule_status(next_run)
        self.assertEqual(changed["next_run_at"], (next_run + timedelta(hours=24)).isoformat().replace("+00:00", "Z"))
        self.schedule(enabled=False)
        self.assertIsNone(restarted.run_due(next_run + timedelta(days=50)))

    def test_failed_schedule_records_safe_error_and_does_not_retry_storm(self):
        self.schedule(hours=1)
        self.jobs.schedule_status(self.now)
        due = self.now + timedelta(hours=1)
        with patch.object(self.jobs, "consolidate", side_effect=ValueError("PRIVATE RAW CONTENT")) as work:
            self.assertEqual(self.jobs.run_due(due), {"error": "consolidation_failed"})
            self.assertIsNone(self.jobs.run_due(due + timedelta(seconds=1)))
            self.assertEqual(work.call_count, 1)
        state = (self.vault.root / "jobs.json").read_text()
        self.assertNotIn("PRIVATE", state)
        self.assertIn("consolidation_failed", state)
        self.assertTrue(self.jobs.run_consolidation(now=due)["no_op"])
        self.assertIsNone(self.jobs.schedule_status(due)["last_error"])

    def test_scheduled_project_cleanup_is_isolated_and_survives_restart(self):
        # Simulate manually copied Markdown records; ordinary learn deduplicates.
        for scope in ("global", "project:one", "project:two"):
            for title in ("Original", "Manual copy"):
                memory = self.vault.remember("Same synthetic recipe", title)
                self.vault._write_memory(replace(memory, scope=scope))
        self.route()
        self.schedule(hours=1, scope="project:one")
        due = self.jobs.schedule_status(self.now)["next_run_at"]
        restarted = LearningJobs(self.services, self.factory)
        result = restarted.run_due(due)
        self.assertEqual(result, {"cleaned": 1, "proposals": 0, "no_op": False, "scope": "project:one"})
        self.assertEqual(len(self.services.list_memories("project:one")), 1)
        for scope in ("global", "project:two"):
            self.assertEqual(len(self.services.list_memories(scope)), 2)
        self.assertEqual(len(self.services.list_memories("project:one", include_inactive=True)), 2)
        self.factory.assert_not_called()
        self.assertEqual(ProposalStore(self.vault).count(), 0)
        self.assertIsNone(restarted.run_due(due))
        status = restarted.schedule_status(due)
        self.assertEqual(status["scope"], "project:one")
        self.assertEqual(status["last_run_scope"], "project:one")
        self.assertTrue(restarted.run_due(status["next_run_at"])["no_op"])

    def test_other_scope_manual_success_and_failure_preserve_schedule_anchor(self):
        self.schedule(hours=24, scope="project:scheduled")
        due = self.jobs.schedule_status(self.now)["next_run_at"]
        later = self.now + timedelta(hours=3)
        self.jobs.run_consolidation("project:manual", now=later)
        self.assertEqual(self.jobs.schedule_status(later)["next_run_at"], due)
        with patch.object(self.jobs, "consolidate", side_effect=ValueError("PRIVATE")):
            with self.assertRaises(ValueError):
                self.jobs.run_consolidation("project:manual", now=later + timedelta(hours=1))
        restarted = LearningJobs(self.services, self.factory)
        status = restarted.schedule_status(later)
        self.assertEqual(status["next_run_at"], due)
        self.assertEqual(status["last_run_scope"], "project:manual")
        self.assertEqual(status["last_error"], "consolidation_failed")
        self.schedule(hours=12, scope="project:scheduled")
        self.assertEqual(restarted.schedule_status(later)["next_run_at"],
                         (self.now + timedelta(hours=12)).isoformat().replace("+00:00", "Z"))
        self.assertNotIn("PRIVATE", (self.vault.root / "jobs.json").read_text())

    def test_scope_change_and_reenable_start_fresh_interval(self):
        self.schedule(hours=24, scope="project:one")
        self.jobs.schedule_status(self.now)
        later = self.now + timedelta(hours=20)
        self.schedule(hours=24, scope="project:two")
        status = self.jobs.schedule_status(later)
        self.assertEqual(status["next_run_at"], (later + timedelta(hours=24)).isoformat().replace("+00:00", "Z"))
        self.assertIsNone(self.jobs.run_due(later + timedelta(hours=4)))
        self.schedule(enabled=False, hours=24, scope="project:two")
        self.assertIsNone(self.jobs.schedule_status(later)["next_run_at"])
        resumed = later + timedelta(days=2)
        self.schedule(hours=24, scope="project:two")
        self.assertEqual(self.jobs.schedule_status(resumed)["next_run_at"],
                         (resumed + timedelta(hours=24)).isoformat().replace("+00:00", "Z"))

    def test_schedule_scope_validation_is_atomic_and_absence_means_global(self):
        settings = load_settings(self.vault)
        settings["schedule"].pop("scope")
        saved = save_settings(self.vault, settings)
        self.assertEqual(saved["schedule"]["scope"], "global")
        self.assertNotIn("scope", settings["schedule"])
        for value in (None, False, "", "has space", "x" * 129):
            settings["schedule"]["scope"] = value
            with self.assertRaises(ValueError):
                save_settings(self.vault, settings)
            self.assertEqual(load_settings(self.vault), saved)

    def test_overlap_and_naive_time_rejected(self):
        self.jobs._running = True
        with self.assertRaises(ValueError):
            self.jobs.run_consolidation()
        with self.assertRaises(ValueError):
            self.jobs.schedule_status(datetime(2026, 9, 6))


if __name__ == "__main__":
    unittest.main()
