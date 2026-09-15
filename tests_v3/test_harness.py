from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ai_dememory.config import load_config, set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.harness import MAX_INPUT, install_project, project_files, recall_hook
from ai_dememory.vault import Vault


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "config")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.vault = Vault.create(self.root / "vault")
        set_module_enabled("harness", True)

    def payload(self, prompt="What are the deployment window instructions?"):
        return {"hook_event_name": "UserPromptSubmit", "session_id": "session-test",
                "turn_id": "turn-test", "prompt": prompt, "transcript_path": "must-not-open"}

    def run_hook(self, raw, vault=None):
        return subprocess.run([sys.executable, "-m", "ai_dememory.harness", "--vault", str(vault or self.vault.root),
                               "--config-dir", str(self.root / "config"), "--scope", "project:alpha"],
                              input=raw, capture_output=True, timeout=5)

    def test_real_hook_recall_scopes_and_does_not_read_transcript(self):
        services = CoreServices(self.vault)
        source = {"provider": "test", "session": "s", "turn": "t", "evidence_kind": "user_statement", "excerpt": "Window Thursday"}
        services.learn("Deployment window", "Deployment window is Thursday at 16:00.", "project:alpha", source, "a")
        services.learn("Deployment window", "Deployment window is Sunday at 02:00.", "project:beta", source, "b")
        result = self.run_hook(json.dumps(self.payload()).encode())
        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Thursday", context)
        self.assertNotIn("Sunday", context)
        self.assertIn("session=session-test", context)
        self.assertNotIn("must-not-open", context)
        self.assertEqual(self.vault.memory_count(), 2)

    def test_fail_open_invalid_missing_disabled_and_oversized(self):
        for raw in (b"broken json", b"null", b"x" * (MAX_INPUT + 1)):
            result = self.run_hook(raw)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, b"{}"))
            self.assertEqual(result.stderr, b"")
        result = self.run_hook(json.dumps(self.payload()).encode(), self.root / "absent")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, b"{}"))
        set_module_enabled("harness", False)
        result = self.run_hook(json.dumps(self.payload()).encode())
        self.assertEqual(result.stdout.strip(), b"{}")

    def test_empty_and_trivial_do_not_create_memory(self):
        self.assertEqual(recall_hook(self.vault, self.payload("Hi"), "project:alpha"), {})
        self.assertEqual(recall_hook(self.vault, self.payload(""), "project:alpha"), {})
        self.assertEqual(self.vault.memory_count(), 0)

    def test_session_start_guidance_is_bounded_and_never_reads_or_writes_memory(self):
        for source in ("startup", "resume", "clear", "compact"):
            payload = {**self.payload(), "hook_event_name": "SessionStart", "source": source}
            with patch("ai_dememory.harness.CoreServices") as services:
                result = recall_hook(self.vault, payload, "project:alpha", "codex")
                services.assert_not_called()
            context = result["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn("project:alpha", context)
            self.assertIn("memory.context", context)
            self.assertLess(len(context), 1200)
            self.assertNotIn("must-not-open", context)
        self.assertEqual(self.vault.memory_count(), 0)
        for source in (None, "unknown"):
            self.assertEqual(recall_hook(self.vault, {"hook_event_name": "SessionStart", "source": source}, "global"), {})

    def test_secret_input_does_not_reach_hook_logs(self):
        secret = "sk-" + "x" * 30
        result = self.run_hook(json.dumps(self.payload("Please remember this token " + secret)).encode())
        self.assertEqual(result.stdout.strip(), b"{}")
        self.assertEqual(result.stderr, b"")
        self.assertFalse((self.vault.root / "runtime.sqlite").exists())

    def test_logs_are_metadata_only_and_occurrence_deduped(self):
        for _ in range(2):
            recall_hook(self.vault, self.payload("synthetic-canary Please explain deployment schedules"), "project:alpha")
        with closing(sqlite3.connect(self.vault.root / "runtime.sqlite")) as db:
            rows = db.execute("SELECT * FROM hook_calls").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("synthetic-canary", repr(rows))

    def test_install_codex_is_repeatable_and_uses_absolute_paths(self):
        project = self.root / "project with spaces"
        paths = install_project(self.vault, project, "codex", "project:alpha")
        config = tomllib.loads(paths[0].read_text())
        server = config["mcp_servers"]["dememory_v3"]
        self.assertTrue(Path(server["command"]).is_absolute())
        self.assertIn(str(self.vault.root), server["args"])
        self.assertEqual(server["args"][-2:], ["--scope", "project:alpha"])
        hooks = json.loads(paths[1].read_text())["hooks"]
        self.assertEqual(set(hooks), {"UserPromptSubmit"})
        self.assertEqual(hooks["UserPromptSubmit"][0]["hooks"][0]["timeout"], 3)
        self.assertEqual(install_project(self.vault, project, "codex", "project:alpha"), paths)
        self.assertIn("mcp", load_config().enabled_modules)

    def test_existing_client_config_is_not_overwritten(self):
        project = self.root / "occupied"
        target = project / ".codex" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text("user_owned = true\n")
        with self.assertRaisesRegex(ValueError, "Existing client config"):
            install_project(self.vault, project, "codex", "project:alpha")
        self.assertEqual(target.read_text(), "user_owned = true\n")
        self.assertFalse((target.parent / "hooks.json").exists())

    def test_claude_configuration_uses_its_native_locations(self):
        files = project_files(self.vault, self.root / "claude", "claude", "project:alpha")
        parsed = {path.name: json.loads(text) for path, text in files.items()}
        self.assertIn("dememory_v3", parsed[".mcp.json"]["mcpServers"])
        self.assertIn("UserPromptSubmit", parsed["settings.json"]["hooks"])
        hook = parsed["settings.json"]["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertNotIn("additionalContextLimit", hook)

    @unittest.skipUnless(os.name == "nt", "Windows shell encoding")
    def test_windows_hook_rejects_shell_metacharacters(self):
        with patch.dict(os.environ, {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "bad&path")}):
            with self.assertRaisesRegex(ValueError, "shell metacharacters"):
                project_files(self.vault, self.root / "project", "codex", "project:alpha")


if __name__ == "__main__":
    unittest.main()
