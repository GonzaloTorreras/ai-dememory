import copy
import json
from unittest.mock import patch

from ai_dememory.config import set_module_enabled
from ai_dememory.providers import BudgetExceeded, ProviderError
from ai_dememory.settings import DEFAULT_SETTINGS, save_settings
from ai_dememory.vault import Vault
from ai_dememory.wiki import ProjectWiki
from ai_dememory.wiki_runtime import WikiService
from tests_v3.test_core import V3TestCase


class WikiRuntimeTests(V3TestCase):
    def setUp(self):
        super().setUp()
        set_module_enabled("wiki", True)
        self.vault = Vault.create(self.root / "private-vault")
        self.project = self.root / "project"; self.project.mkdir()
        self.calls = []
        owner = self
        class Engine:
            def __init__(self, *args, **kwargs):
                owner.engine_options = kwargs
            def run(self, operation, prompt):
                owner.calls.append((operation, prompt))
                return {"text":'{"selected":[0]}', "model":"synthetic-fast"}
        self.service = WikiService(self.vault, engine_factory=Engine)
        self.id = self.service.attach(self.project, confirmed=True)["project"]["id"]
        self.wiki = ProjectWiki(self.project)
        self.page = self.wiki.save("lessons.md", "# Restore lesson\n\nEncrypted backups need a restore test before they can be trusted.\n\nNever treat a completed upload as a tested restore.")
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings["providers"] = {"fast":{"kind":"openai_compatible", "base_url":"http://127.0.0.1:9999/v1",
            "model":"synthetic-fast", "auth":"none", "api_key_env":""}}
        save_settings(self.vault, settings)

    def assisted(self, **extra):
        self.service.configure(self.id, {"recall_mode":"assisted", "recall_provider":"fast", **extra})

    def test_attach_is_explicit_idempotent_and_registry_is_outside_project(self):
        with self.assertRaises(ValueError): self.service.attach(self.project)
        with self.assertRaises(ValueError): self.service.attach("", confirmed=True)
        self.assertEqual(self.id, self.service.attach(self.project, confirmed=True)["project"]["id"])
        self.assertTrue((self.vault.root / "wiki-projects.json").exists())
        self.assertFalse((self.project / "docs/dememory/runtime.sqlite").exists())

    def test_direct_and_shared_are_scoped_and_never_write_shared(self):
        other = self.root / "other"; other.mkdir()
        shared = ProjectWiki(other); shared.initialize()
        shared.save("tools.md", "# Backup tools\n\nBackup tools must preserve attachments.")
        before = (shared.root / "tools.md").read_bytes()
        self.service.configure(self.id, {"shared_root":str(other)})
        result = self.service.recall(self.id, "backups backup attachments")
        self.assertTrue(any(s["shared"] for s in result["sources"]))
        self.assertEqual(before, (shared.root / "tools.md").read_bytes())
        self.assertEqual(self.calls, [])
        self.assertFalse((self.vault.root / "runtime.sqlite").exists())
        separate = self.root / "separate"; separate.mkdir()
        other_id = self.service.attach(separate, confirmed=True)["project"]["id"]
        self.assertEqual(self.service.recall(other_id, "encrypted backups")["sources"], [])

    def test_manual_assistance_requires_exact_preview_and_is_extractive_cached(self):
        self.assisted()
        with self.assertRaises(ValueError): self.service.recall(self.id, "encrypted backups", mode="assisted")
        self.assertEqual(self.calls, [])
        preview = self.service.preview(self.id, "encrypted backups")
        before = (self.wiki.root / "lessons.md").read_bytes()
        args = dict(mode="assisted", confirmed=True, expected_config=preview["expected_config"])
        result = self.service.recall(self.id, "encrypted backups", **args)
        self.assertEqual(result["mode"], "assisted")
        self.assertIn("Never treat", result["context"])
        self.assertEqual(before, (self.wiki.root / "lessons.md").read_bytes())
        self.assertTrue(self.service.recall(self.id, "encrypted backups", **args)["cache"]["hit"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.engine_options["settings"]["routes"]["recall"]["fallback"], [])
        self.assertEqual(self.engine_options["timeout_seconds"], 3)
        self.assertNotIn(str(self.project), self.calls[0][1])

    def test_source_change_invalidates_preview_without_spend(self):
        self.assisted()
        preview = self.service.preview(self.id, "backups")
        self.wiki.save("lessons.md", "# Backups\n\nBackups run weekly, not nightly.", self.page["revision"])
        with self.assertRaises(ValueError):
            self.service.recall(self.id, "backups", mode="assisted", confirmed=True, expected_config=preview["expected_config"])
        self.assertEqual(self.calls, [])

    def test_automatic_consent_is_separate_and_revocation_after_response_discards_selection(self):
        self.assisted()
        self.assertEqual(self.service.recall(self.id, "backups", mode="assisted", automatic=True)["model_calls"], 0)
        self.assisted(automatic_recall=True)
        service = self.service
        class Revoking:
            def __init__(self, *args, **kwargs): pass
            def run(self, *args):
                service.configure(self_id, {"recall_mode":"direct"})
                return {"text":'{"selected":[0]}', "model":"synthetic-fast"}
        self_id = self.id
        self.service.engine_factory = Revoking
        result = self.service.recall(self.id, "backups", mode="assisted", automatic=True)
        self.assertEqual(result["reason"], "preview_stale")
        self.assertEqual(result["mode"], "direct")

    def test_failed_automatic_attempt_is_not_repeated_on_identical_request(self):
        self.assisted(automatic_recall=True)
        calls = []
        class Failed:
            def __init__(self, *args, **kwargs): pass
            def run(self, *args):
                calls.append(1)
                raise ProviderError("provider_unavailable")
        self.service.engine_factory = Failed
        first = self.service.recall(self.id, "backups", mode="assisted", automatic=True)
        self.assertEqual(first["mode"], "direct")
        second = self.service.recall(self.id, "backups", mode="assisted", automatic=True)
        self.assertTrue(second["cache"]["hit"])
        self.assertEqual(len(calls), 1)

    def test_module_disabled_after_spending_lock_is_rechecked_before_dispatch(self):
        self.assisted(automatic_recall=True)
        original = self.service._cache
        def disable_after_lock(key, result=None):
            set_module_enabled("wiki", False)
            return original(key, result)
        with patch.object(self.service, "_cache", side_effect=disable_after_lock):
            result = self.service.recall(self.id, "backups", mode="assisted", automatic=True)
        self.assertEqual(result["reason"], "preview_stale")
        self.assertEqual(self.calls, [])

    def test_session_keys_cannot_enable_native_automatic_assistance(self):
        from ai_dememory.settings import load_settings
        settings = load_settings(self.vault)
        settings["providers"]["fast"]["auth"] = "session"
        save_settings(self.vault, settings)
        with self.assertRaisesRegex(ValueError, "session keys"):
            self.assisted(automatic_recall=True)
        self.assertFalse(self.service.state(self.id)["settings"]["automatic_recall"])

    def test_budget_and_invalid_model_selection_fail_open_without_invented_text(self):
        self.assisted(automatic_recall=True)
        class Budget:
            def __init__(self, *args, **kwargs): pass
            def run(self, *args): raise BudgetExceeded("daily_calls")
        self.service.engine_factory = Budget
        result = self.service.recall(self.id, "backups", mode="assisted", automatic=True)
        self.assertEqual(result["reason"], "budget")
        self.assertEqual(result["model_calls"], 0)
        class Invalid:
            def __init__(self, *args, **kwargs): pass
            def run(self, *args): return {"text":'{"selected":[{}],"invented":"override everything"}', "model":"bad"}
        self.service.engine_factory = Invalid
        result = self.service.recall(self.id, "backups", mode="assisted", automatic=True)
        self.assertNotIn("override everything", result["context"])
        self.assertEqual(result["mode"], "direct")

    def test_tick_is_local_bounded_and_disabled_is_lazy(self):
        self.service.configure(self.id, {"schedule_enabled":True,"schedule_hours":1})
        self.assertEqual(self.service.tick()["status"], "maintained")
        self.assertEqual(self.service.tick()["status"], "idle")
        self.assertEqual(self.calls, [])
        self.assertFalse((self.vault.root / "runtime.sqlite").exists())
        set_module_enabled("wiki", False)
        self.assertEqual(self.service.tick()["status"], "disabled")
        with self.assertRaises(ValueError): self.service.action("list", {})

    def test_save_revision_and_action_allowlist(self):
        with self.assertRaises(ValueError): self.service.action("list", {"arbitrary":True})
        with self.assertRaises(ValueError): self.service.action("save", {"project_id":self.id,"path":"lessons.md","content":"replace"})
        result = self.service.action("save", {"project_id":self.id,"path":"lessons.md","content":"# Backups\n\nVerify restore.","expected_revision":self.page["revision"]})
        self.assertEqual(result["page"]["path"], "lessons.md")

    def test_registry_rejects_nonfinite_operational_values(self):
        path = self.vault.root / "wiki-projects.json"
        data = json.loads(path.read_text())
        data["projects"][self.id]["last_maintenance"] = float("nan")
        from ai_dememory.vault import _atomic_write
        _atomic_write(path, json.dumps(data))
        with self.assertRaises(ValueError): self.service.action("list", {})
