import copy
from dataclasses import replace
from unittest.mock import patch

from ai_dememory.config import set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.judgments import JudgmentEngine
from ai_dememory.jev_skills import arm, assess, process_new, config_key, confirmation_key, database, record
from ai_dememory.providers import BudgetExceeded
from contextlib import closing
from ai_dememory.settings import DEFAULT_SETTINGS, save_settings, load_settings
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class JevSkillTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.vault = Vault.create(self.root / "vault")
        self.services = CoreServices(self.vault)
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.settings["providers"] = {"jev":{"kind":"plugin:jev", "base_url":"https://api.typesafe.ai/v1",
            "model":"jev-1.13.0", "api_key_env":"", "auth":"session"}}
        self.settings["judgment"] = {"primary":"jev", "fallback":[], "scopes":["project:alpha"], "operations":["support"]}
        self.settings["module_settings"] = {"jev":{"language":True, "usefulness":True, "recall_tags":True}}
        set_module_enabled("jev", True)
        self.settings = save_settings(self.vault, self.settings)
        self.memory = self.vault.remember("The project keeps backups nightly.", "Backups", scope="project:alpha")
        self.calls = []

    def transport(self, url, payload, headers, timeout):
        self.calls.append(payload)
        answers = {}
        for name, question in payload["questions"].items():
            answers[name] = ({"type":"noul", "noul":.9} if question["type"] == "noul" else
                {"type":"choice", "choice":"en", "confidence":1.,
                 "probabilities":{code:float(code == "en") for code in question["criteria"]}})
        return {"model":"jev-1.13.0", "answers":answers, "usage":{"input_tokens":50,"output_tokens":10}}

    def engine(self):
        return JudgmentEngine(self.vault, load_settings(self.vault), self.transport, lambda *args:"synthetic-key")

    def test_batched_skills_work_without_excerpt_and_do_not_change_memory(self):
        before = self.memory.path.read_bytes()
        result = assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        self.assertEqual(result["status"], "assessed")
        self.assertEqual(set(self.calls[0]["questions"]), {"language", "usefulness"})
        self.assertEqual(result["result"]["usefulness"]["probability"], .9)
        self.assertEqual(self.memory.path.read_bytes(), before)
        second = assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual(len(self.calls), 1)

    def test_recall_reads_advisory_tags_without_network_and_checks_revision(self):
        assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        hit = self.services.search("backups", scope="project:alpha")[0]
        self.assertEqual(hit["details"]["jev"]["language"]["verdict"], "en")
        self.assertFalse(hit["details"]["confidence_applied"])
        self.assertIn("language: en; advisory", self.services.context("backups", scope="project:alpha")["context"])
        self.vault._write_memory(replace(self.memory, content="Backups run weekly."))
        self.assertNotIn("jev", self.services.search("backups", scope="project:alpha")[0]["details"])
        self.assertEqual(len(self.calls), 1)

    def test_presentation_toggle_reuses_existing_assessment(self):
        self.settings["module_settings"]["jev"]["recall_tags"] = False
        save_settings(self.vault, self.settings)
        assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        self.settings["module_settings"]["jev"]["recall_tags"] = True
        save_settings(self.vault, self.settings)
        self.assertIn("jev", self.services.search("backups", scope="project:alpha")[0]["details"])
        self.assertEqual(len(self.calls), 1)

    def test_disabling_one_skill_keeps_the_other_cached_without_spend(self):
        assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        self.settings["module_settings"]["jev"]["language"] = False
        save_settings(self.vault, self.settings)
        tags = self.services.search("backups", scope="project:alpha")[0]["details"]["jev"]
        self.assertNotIn("language", tags)
        self.assertIn("usefulness", tags)
        result = assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        self.assertTrue(result["cache"]["hit"])
        self.assertEqual(set(result["result"]), {"usefulness"})
        self.assertEqual(len(self.calls), 1)

    def test_reactivation_baselines_memories_from_disabled_interval(self):
        config = self.settings["module_settings"]["jev"]
        config.update({"after_save":True,"automatic_scopes":["project:alpha"]})
        save_settings(self.vault, self.settings); arm(self.services)
        config["after_save"] = False
        save_settings(self.vault, self.settings); arm(self.services)
        self.vault.remember("During disabled interval", "Paused", scope="project:alpha")
        config["after_save"] = True
        save_settings(self.vault, self.settings); arm(self.services)
        with patch("ai_dememory.builtin_modules.jev.http_transport", self.transport):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "idle")
        set_module_enabled("jev", False)
        self.vault.remember("During module disabled", "Off", scope="project:alpha")
        set_module_enabled("jev", True)
        with patch("ai_dememory.builtin_modules.jev.http_transport", self.transport):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "idle")
        self.assertEqual(self.calls, [])

    def test_oversized_memory_is_skipped_without_blocking_the_next(self):
        self.settings["module_settings"]["jev"].update({"after_save":True,"automatic_scopes":["project:alpha"]})
        save_settings(self.vault, self.settings); arm(self.services)
        large = self.vault.remember("x"*9000, "Large", scope="project:alpha")
        self.assertEqual(process_new(self.services)["reason"], "input_too_large")
        self.vault.remember("New reusable preference", "Small", scope="project:alpha")
        with patch("ai_dememory.builtin_modules.jev.http_transport", self.transport):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "assessed")
        self.assertEqual(len(self.calls), 1)

    def test_settings_aggregate_limit_prevents_unreadable_file(self):
        before = (self.vault.root / "settings.json").read_bytes()
        self.settings["module_settings"].update({f"extra-{i}":{"text":"x"*15900} for i in range(7)})
        with self.assertRaisesRegex(ValueError, "size limit"):
            save_settings(self.vault, self.settings)
        self.assertEqual((self.vault.root / "settings.json").read_bytes(), before)

    def test_automatic_failure_has_no_infinite_retry_and_manual_retry_is_available(self):
        self.settings["module_settings"]["jev"].update({"after_save":True,"automatic_scopes":["project:alpha"]})
        save_settings(self.vault, self.settings); arm(self.services)
        fresh = self.vault.remember("New preference", "Fresh", scope="project:alpha")
        with patch("ai_dememory.builtin_modules.jev.http_transport", side_effect=ConnectionError):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["reason"], "provider_unavailable")
        with patch("ai_dememory.builtin_modules.jev.http_transport", self.transport):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "idle")
            self.assertEqual(assess(self.services, fresh.memory_id, "project:alpha", engine=self.engine())["status"], "assessed")

    def test_concurrent_assessment_is_fail_fast_without_duplicate_billing(self):
        from ai_dememory.vault import _exclusive_write_lock
        with _exclusive_write_lock(self.vault.root / ".jev-skills.lock"):
            self.assertEqual(assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())["reason"], "busy")
        self.assertEqual(self.calls, [])

    def test_confirmation_binds_enabled_questions_without_invalidating_cached_answers(self):
        config = self.settings["module_settings"]["jev"]
        config["usefulness"] = False
        first = save_settings(self.vault, self.settings)
        from ai_dememory.jev_skills import configuration
        semantic = config_key(first, configuration(first))
        confirmed = confirmation_key(first, configuration(first))
        config["usefulness"] = True
        second = save_settings(self.vault, self.settings)
        self.assertEqual(semantic, config_key(second, configuration(second)))
        result = assess(self.services, self.memory.memory_id, "project:alpha",
                        expected_config=confirmed, engine=self.engine())
        self.assertEqual(result["reason"], "preview_stale")
        self.assertEqual(self.calls, [])

    def test_failed_primary_then_missing_credentials_or_budget_is_not_automatically_retried(self):
        self.settings["providers"]["backup"] = copy.deepcopy(self.settings["providers"]["jev"])
        self.settings["judgment"]["fallback"] = ["backup"]
        self.settings["module_settings"]["jev"].update({"after_save":True,"automatic_scopes":["project:alpha"]})
        save_settings(self.vault, self.settings); arm(self.services)
        fresh = self.vault.remember("A new fact", "New", scope="project:alpha")
        calls = []
        def failed(*args):
            calls.append(1)
            raise ConnectionError
        with patch("ai_dememory.builtin_modules.jev.http_transport", failed):
            resolver = lambda name, profile: "synthetic-key" if name == "jev" else ""
            self.assertEqual(process_new(self.services, resolver)["reason"], "provider_unavailable")
            self.assertEqual(process_new(self.services, resolver)["status"], "idle")
        self.assertEqual(len(calls), 1)
        with closing(database(self.vault)) as db, db:
            db.execute("DELETE FROM jev_skill_receipts WHERE memory_id=?", (fresh.memory_id,))
        original = JudgmentEngine._request_many
        def request(engine, provider_engine, profile, name, *args):
            if name == "backup":
                raise BudgetExceeded("synthetic budget")
            return original(engine, provider_engine, profile, name, *args)
        with patch("ai_dememory.builtin_modules.jev.http_transport", failed), patch.object(JudgmentEngine, "_request_many", request):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["reason"], "provider_unavailable")
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "idle")
        self.assertEqual(len(calls), 2)

    def test_revoked_automation_stops_fallback_before_egress(self):
        self.settings["providers"]["backup"] = copy.deepcopy(self.settings["providers"]["jev"])
        self.settings["judgment"]["fallback"] = ["backup"]
        self.settings["module_settings"]["jev"].update({"after_save":True,"automatic_scopes":["project:alpha"]})
        save_settings(self.vault, self.settings); arm(self.services)
        self.vault.remember("A new fact", "New", scope="project:alpha")
        calls = []
        def revoke(*args):
            calls.append(1)
            self.settings["module_settings"]["jev"].update({"after_save":False,"automatic_scopes":[]})
            save_settings(self.vault, self.settings)
            raise ConnectionError
        with patch("ai_dememory.builtin_modules.jev.http_transport", revoke):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["reason"], "preview_stale")
        self.assertEqual(len(calls), 1)

    def test_automatic_selection_rechecks_receipt_after_waiting_for_lock(self):
        self.settings["module_settings"]["jev"].update({"after_save":True,"automatic_scopes":["project:alpha"]})
        saved = save_settings(self.vault, self.settings); arm(self.services)
        fresh = self.vault.remember("A new fact", "New", scope="project:alpha")
        from ai_dememory.jev_skills import configuration
        real_assess = assess
        def intervening_worker(*args, **kwargs):
            # Another worker completed after this sweep read its initial seen set.
            record(self.vault, fresh, config_key(saved, configuration(saved)),
                   {"status":"unassessed","reason":"provider_unavailable","result":{}})
            return real_assess(*args, **kwargs)
        with patch("ai_dememory.jev_skills.assess", intervening_worker), patch("ai_dememory.builtin_modules.jev.http_transport", self.transport):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["reason"], "already_processed")
        self.assertEqual(self.calls, [])

    def test_public_pilot_measures_mock_answers_without_disclosing_canonical_memory(self):
        from ai_dememory.jev_evaluation import CASES, preview, run
        seen = []
        def response(url, payload, headers, timeout):
            seen.append(payload)
            answers = {}
            for qid, question in payload["questions"].items():
                index = int(qid.rsplit('_',1)[1])
                if question["type"] == "noul":
                    answers[qid] = {"type":"noul", "noul":float(CASES[index][3])}
                else:
                    expected = CASES[index][2]
                    selected = expected if expected in question["criteria"] else "other"
                    answers[qid] = {"type":"choice", "choice":selected,"confidence":1.,
                                    "probabilities":{c:float(c==selected) for c in question["criteria"]}}
            return {"model":"jev-1.13.0", "answers":answers, "usage":{"input_tokens":800,"output_tokens":160}}
        engine = JudgmentEngine(self.vault, self.settings, response, lambda *args:"synthetic-key")
        info = preview(self.vault)
        result = run(self.vault, info["config_key"], engine=engine)
        self.assertEqual(result["measured"]["usefulness_correct"], 8)
        self.assertEqual(result["measured"]["language_correct"], 8)
        self.assertNotIn(self.memory.content, str(seen))
        self.assertNotIn("expected_useful", str(seen))
        self.assertTrue(run(self.vault, info["config_key"], engine=engine)["cached"])
        self.assertEqual(len(seen), 1)

    def test_independent_toggles_and_configurable_languages(self):
        config = self.settings["module_settings"]["jev"]
        config.update({"usefulness":False, "languages":{"en":"English", "fr":"French"}})
        save_settings(self.vault, self.settings)
        assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())
        self.assertEqual(set(self.calls[0]["questions"]), {"language"})
        self.assertEqual(set(self.calls[0]["questions"]["language"]["criteria"]), {"en","fr","mixed","other","undetermined"})
        config["language"] = False
        save_settings(self.vault, self.settings)
        self.assertEqual(assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())["reason"], "skills_disabled")

    def test_disabled_module_retains_config_without_calls_or_tags(self):
        set_module_enabled("jev", False)
        with patch("ai_dememory.modules.load_enabled_module", side_effect=AssertionError("disabled import")):
            self.assertTrue(load_settings(self.vault)["module_settings"]["jev"]["language"])
        self.assertEqual(assess(self.services, self.memory.memory_id, "project:alpha", engine=self.engine())["reason"], "skills_disabled")
        self.assertEqual(self.calls, [])
        self.assertFalse((self.vault.root / "runtime.sqlite").exists())

    def test_automatic_sweep_skips_baseline_and_handles_same_second_and_restart(self):
        self.settings["module_settings"]["jev"].update({"after_save":True, "automatic_scopes":["project:alpha"]})
        save_settings(self.vault, self.settings)
        self.assertTrue(arm(self.services))
        with patch("ai_dememory.vault.utc_now", return_value="2026-11-10T12:00:00Z"):
            self.vault.remember("First new fact.", "First", scope="project:alpha", memory_id="f"*32)
            self.vault.remember("Second new fact.", "Second", scope="project:alpha", memory_id="a"*32)
        self.vault.remember("Other scope.", "Other", scope="project:beta")
        with patch("ai_dememory.builtin_modules.jev.http_transport", self.transport):
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "assessed")
            self.assertEqual(process_new(CoreServices(self.vault), lambda *args:"synthetic-key")["status"], "assessed")
            self.assertEqual(process_new(self.services, lambda *args:"synthetic-key")["status"], "idle")
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn("The project keeps backups", str(self.calls))

    def test_no_automatic_consent_no_processing_and_invalid_noul_fail_open(self):
        self.assertEqual(process_new(self.services)["status"], "idle")
        self.assertEqual(self.calls, [])
        bad = lambda *args: {"model":"jev-1.13.0", "answers":{
            "language":{"type":"choice","choice":"en","confidence":1,
                        "probabilities":{"en":1,"es":0,"mixed":0,"other":0,"undetermined":0}},
            "usefulness":{"type":"noul","noul":True}}}
        engine = JudgmentEngine(self.vault, self.settings, bad, lambda *args:"synthetic-key")
        self.assertEqual(assess(self.services, self.memory.memory_id, "project:alpha", engine=engine)["reason"], "invalid_response")
        self.assertEqual(self.memory.path.read_bytes(), self.vault.get(self.memory.memory_id).path.read_bytes())
