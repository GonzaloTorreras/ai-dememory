from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from ai_dememory.config import load_config, set_module_enabled
from ai_dememory.scheduled import manage_task, receipt_status, run_due, _task_xml
from ai_dememory.settings import load_settings, save_settings
from ai_dememory.setup_options import install_extras
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class ScheduledTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.vault = Vault.create(self.root / "vault with spaces")
        self.xml = None
        self.calls = []
        self.fake_python = self.root / "runtime with spaces" / "python.exe"
        self.fake_python.parent.mkdir()
        self.fake_python.with_name("pythonw.exe").touch()
        self.runtime = patch("ai_dememory.scheduled.sys.executable", str(self.fake_python))
        self.runtime.start()
        self.addCleanup(self.runtime.stop)

    def task_call(self, action, name, expected=None, xml=None):
        self.calls.append(action)
        if action != "status":
            self.assertEqual(self.xml, expected)
            self.xml = xml if action == "install" else None
            if self.xml:
                root = ET.fromstring(self.xml)
                ET.indent(root)
                self.xml = ET.tostring(root, encoding="unicode")
        return {"xml": self.xml, "user": "S-1-5-21-1234", "enabled": bool(self.xml),
                "state": 3 if self.xml else 0, "last_result": 0, "next_run": "test"}

    def test_install_repeat_status_and_remove_owned_task(self):
        with patch("ai_dememory.scheduled._task_call", side_effect=self.task_call):
            result = manage_task(self.vault, "install")
            self.assertTrue(result["changed"])
            self.assertFalse(manage_task(self.vault, "install")["changed"])
            self.assertTrue(manage_task(self.vault, "status")["owned"])
            self.assertTrue(receipt_status(self.vault)["installed_receipt"])
            self.assertFalse(receipt_status(self.vault)["verified_live"])
            self.assertFalse(manage_task(self.vault, "remove")["installed"])
            self.assertFalse(manage_task(self.vault, "remove")["changed"])
        self.assertIsNone(self.xml)
        self.assertEqual(self.calls.count("install"), 1)
        self.assertFalse(receipt_status(self.vault)["installed_receipt"])

    def test_task_xml_is_windowless_bounded_current_user_and_quoted(self):
        xml = _task_xml(self.vault, "S-1-5-21-1234")
        root = ET.fromstring(xml)
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        def value(path):
            return root.find(path, ns).text
        self.assertEqual(value("t:Settings/t:MultipleInstancesPolicy"), "IgnoreNew")
        self.assertEqual(value("t:Settings/t:ExecutionTimeLimit"), "PT5M")
        self.assertEqual(value("t:Settings/t:WakeToRun"), "false")
        self.assertEqual(value("t:Principals/t:Principal/t:RunLevel"), "LeastPrivilege")
        self.assertEqual(value("t:Principals/t:Principal/t:LogonType"), "InteractiveToken")
        self.assertTrue(value("t:Actions/t:Exec/t:Command").endswith("pythonw.exe"))
        self.assertIn('"' + str(self.vault.root) + '"', value("t:Actions/t:Exec/t:Arguments"))
        self.assertNotIn("powershell", xml)
        self.assertNotIn("password", xml.lower())

    def test_changed_or_unowned_task_is_never_overwritten(self):
        with patch("ai_dememory.scheduled._task_call", side_effect=self.task_call):
            self.xml = "user-owned"
            with self.assertRaisesRegex(ValueError, "not owned"):
                manage_task(self.vault, "install")
            self.xml = None
            manage_task(self.vault, "install")
            self.xml += "<!-- user edit -->"
            for action in ("install", "remove"):
                with self.assertRaisesRegex(ValueError, "not owned"):
                    manage_task(self.vault, action)
            self.assertFalse(manage_task(self.vault, "status")["owned"])

    def test_receipt_write_failure_rolls_back_only_our_task(self):
        with patch("ai_dememory.scheduled._task_call", side_effect=self.task_call):
            with patch("ai_dememory.scheduled._atomic_write", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    manage_task(self.vault, "install")
        self.assertIsNone(self.xml)
        self.assertFalse(receipt_status(self.vault)["installed_receipt"])

    def test_disabled_and_not_due_runner_do_not_load_history_or_make_calls(self):
        with patch("ai_dememory.jobs.LearningJobs") as jobs:
            self.assertEqual(run_due(self.vault), {"skipped": "workbench_disabled"})
            jobs.assert_not_called()
        set_module_enabled("workbench", True)
        with patch("ai_dememory.providers.ProviderEngine.run") as model:
            self.assertEqual(run_due(self.vault), {"skipped": "not_due_or_busy"})
            model.assert_not_called()
        self.assertEqual(self.vault.memory_count(), 0)

    def test_setup_schedule_preserves_settings_and_rolls_back_on_task_failure(self):
        settings = load_settings(self.vault)
        settings["schedule"] = {"enabled": False, "interval_hours": 24, "scope": "project:chosen"}
        settings["budgets"]["daily_calls"] = 3
        save_settings(self.vault, settings)
        from ai_dememory.core import CoreServices
        from ai_dememory.jobs import LearningJobs
        jobs = LearningJobs(CoreServices(self.vault))
        jobs.schedule_status()
        before_jobs = (self.vault.root / "jobs.json").read_bytes()
        config = load_config()
        with patch("ai_dememory.scheduled._task_call", side_effect=ValueError("denied")):
            with self.assertRaises(ValueError):
                install_extras(self.vault, schedule=True, scope="project:other")
        self.assertEqual(load_config(), config)
        self.assertEqual(load_settings(self.vault), settings)
        self.assertEqual((self.vault.root / "jobs.json").read_bytes(), before_jobs)
        with patch("ai_dememory.scheduled._task_call", side_effect=self.task_call):
            result = install_extras(self.vault, schedule=True)
        self.assertTrue(result["consolidation"]["installed"])
        current = load_settings(self.vault)
        self.assertEqual(current["schedule"], {**settings["schedule"], "enabled": True})
        self.assertEqual(current["budgets"], settings["budgets"])

    def test_cli_default_is_core_only_and_codex_opt_in_is_installed(self):
        home = self.root / "codex-home"
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
            code, _, error = self.run_cli("setup", str(self.vault.root), "--yes")
            self.assertEqual(code, 0, error)
            self.assertFalse(home.exists())
            code, output, error = self.run_cli("setup", "--yes", "--with-codex", "--json")
            self.assertEqual(code, 0, error)
            self.assertTrue(json.loads(output)["integrations"]["codex"]["trust_required"])
            hooks = json.loads((home / "hooks.json").read_text())["hooks"]
            self.assertEqual(set(hooks), {"UserPromptSubmit", "SessionStart"})
            self.assertNotIn("Stop", hooks)
            self.assertEqual(set(load_config().enabled_modules), {"mcp", "harness-codex", "workbench"})

    def test_cli_schedule_options_need_explicit_opt_in(self):
        for flags in (("--schedule-hours", "24"), ("--with-schedule", "--schedule-hours", "0")):
            code, _, error = self.run_cli("setup", str(self.vault.root), "--yes", *flags)
            self.assertEqual(code, 2, error)
