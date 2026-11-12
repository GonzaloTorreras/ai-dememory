from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from ai_dememory.cli import main
from ai_dememory.config import load_config, set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.harness import SERVER_NAME, recall_hook
from ai_dememory.projects import configure_project
from ai_dememory.vault import Vault, _atomic_write


class ClaudeUserInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home, self.config = self.root / "home", self.root / "config"
        self.home.mkdir()
        environment = patch.dict(os.environ, {
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"),
            "AI_DEMEMORY_CONFIG_DIR": str(self.config),
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.vault = Vault.create(self.root / "vault")
        self.server_path = self.home / ".claude.json"
        self.settings_path = self.home / ".claude" / "settings.json"
        self.receipt_path = self.config / "integrations" / "claude-global.json"

    def cli(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            try:
                code = main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue(), error.getvalue()

    def setup(self, *args):
        code, output, error = self.cli("setup", str(self.vault.root), "--with-claude", "--yes", "--json", *args)
        self.assertEqual(code, 0, error)
        return json.loads(output)["integrations"]["claude"]

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    def uninstall(self):
        code, output, error = self.cli("serve", "harness-claude", "uninstall", "--user")
        self.assertEqual(code, 0, error)
        self.assertIn("removed", output)

    def test_setup_merges_native_files_and_enables_claude(self):
        original = {"numStartups": 21, "projects": {"example": {"allowedTools": []}},
                    "mcpServers": {"other": {"command": "other"}}}
        foreign = {"matcher": "startup", "hooks": [{"type": "command", "command": "other"}]}
        self.write(self.server_path, original)
        self.write(self.settings_path, {"theme": "dark", "hooks": {
            "UserPromptSubmit": [foreign], "SessionStart": [foreign], "Stop": [foreign]}})
        self.assertTrue(self.setup()["changed"])
        server_data = self.read(self.server_path)
        server = server_data["mcpServers"].pop(SERVER_NAME)
        self.assertEqual(server_data, original)
        self.assertEqual(server["command"], str(Path(sys.executable).absolute()))
        self.assertEqual(server["args"][-2:], ["--scope", "global"])
        self.assertNotIn("--auto-scope", server["args"])
        self.assertEqual(server["env"], {"AI_DEMEMORY_CONFIG_DIR": str(self.config)})
        settings = self.read(self.settings_path)
        self.assertEqual(settings["theme"], "dark")
        for event in ("UserPromptSubmit", "SessionStart"):
            self.assertEqual(settings["hooks"][event][0], foreign)
            group = settings["hooks"][event][1]
            if event == "SessionStart":
                self.assertEqual(group["matcher"], "startup|resume|clear|compact")
            hook = group["hooks"][0]
            self.assertEqual(hook["timeout"], 3)
            self.assertIn("-m ai_dememory.harness", hook["command"])
            self.assertIn("--auto-scope", hook["command"])
            self.assertIn("--client claude", hook["command"])
        self.assertEqual(settings["hooks"]["Stop"], [foreign])
        self.assertTrue({"harness-claude", "mcp"} <= set(load_config().enabled_modules))
        self.assertNotIn("harness-codex", load_config().enabled_modules)
        self.assertTrue(self.receipt_path.is_file())

    def test_setup_combines_codex_and_claude_and_reports_both(self):
        self.setup("--with-codex")
        self.assertTrue((self.config / "integrations" / "codex-global.json").is_file())
        self.assertTrue({"harness-codex", "harness-claude"} <= set(load_config().enabled_modules))
        code, output, error = self.cli("setup", str(self.vault.root), "--with-claude", "--with-codex", "--yes")
        self.assertEqual(code, 0, error)
        self.assertIn("Claude Code", output)
        self.assertIn("Codex", output)
        self.assertIn("Claude", output.split("Next:")[1])

    def test_repeat_is_byte_for_byte_noop(self):
        self.setup()
        paths = (self.server_path, self.settings_path, self.receipt_path)
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        self.assertFalse(self.setup()["changed"])
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})

    def test_large_claude_state_is_preserved(self):
        original = {"historyState": "x" * 1_100_000}
        self.write(self.server_path, original)
        self.setup()
        self.assertEqual(self.read(self.server_path)["historyState"], original["historyState"])
        self.assertLess(self.receipt_path.stat().st_size, 10_000)

    def test_unicode_state_remains_readable_for_repeat_and_uninstall(self):
        # Escaping UTF-8 to ASCII must not push an installed file over its limit.
        for path, size in ((self.server_path, 2_700_000), (self.settings_path, 170_000)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"padding": "é" * size}, ensure_ascii=False), encoding="utf-8")
        self.setup()
        self.assertFalse(self.setup()["changed"])
        self.uninstall()
        self.assertEqual(len(self.read(self.server_path)["padding"]), 2_700_000)
        self.assertEqual(len(self.read(self.settings_path)["padding"]), 170_000)

    def test_serialized_size_limit_is_preflighted_before_any_writes(self):
        self.write(self.server_path, {"keep": True})
        self.write(self.settings_path, {"padding": [0] * 150_000})
        before = (self.server_path.read_bytes(), self.settings_path.read_bytes())
        code, _, _ = self.cli("setup", str(self.vault.root), "--with-claude", "--yes")
        self.assertEqual(code, 2)
        self.assertEqual((self.server_path.read_bytes(), self.settings_path.read_bytes()), before)
        self.assertFalse(self.receipt_path.exists())

    def test_different_same_name_server_refuses_without_client_writes(self):
        self.write(self.server_path, {"mcpServers": {SERVER_NAME: {"command": "user-owned"}}})
        before = self.server_path.read_bytes()
        code, _, _ = self.cli("setup", str(self.vault.root), "--with-claude", "--yes")
        self.assertEqual(code, 2)
        self.assertEqual(self.server_path.read_bytes(), before)
        self.assertFalse(self.settings_path.exists())
        self.assertFalse(self.receipt_path.exists())
        self.assertNotIn("harness-claude", load_config().enabled_modules)

    def test_malformed_settings_preflight_leaves_server_untouched(self):
        self.write(self.server_path, {"keep": True})
        before = self.server_path.read_bytes()
        for bad in ([], {"hooks": []}, {"hooks": {"SessionStart": {}}}):
            with self.subTest(bad=bad):
                self.write(self.settings_path, bad)
                code, _, _ = self.cli("setup", str(self.vault.root), "--with-claude", "--yes")
                self.assertEqual(code, 2)
                self.assertEqual(self.server_path.read_bytes(), before)
                self.assertEqual(self.read(self.settings_path), bad)
                self.assertFalse(self.receipt_path.exists())

    def test_unowned_differing_hook_refuses(self):
        before = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command",
                  "command": "python -m ai_dememory.harness --scope project:old"}]}]}}
        self.write(self.settings_path, before)
        code, _, _ = self.cli("setup", str(self.vault.root), "--with-claude", "--yes")
        self.assertEqual(code, 2)
        self.assertEqual(self.read(self.settings_path), before)
        self.assertFalse(self.server_path.exists())

    def test_uninstall_preserves_other_entries_and_later_hooks(self):
        self.setup()
        data = self.read(self.server_path)
        data["later"] = [1, 2, 3]
        data["mcpServers"]["other"] = {"command": "later"}
        self.write(self.server_path, data)
        settings = self.read(self.settings_path)
        later = {"type": "command", "command": "later-hook"}
        settings["hooks"]["SessionStart"][0]["hooks"].append(later)
        settings["permissions"] = {"allow": ["Read"]}
        self.write(self.settings_path, settings)
        self.uninstall()
        self.assertEqual(self.read(self.server_path), {"later": [1, 2, 3], "mcpServers": {"other": {"command": "later"}}})
        after = self.read(self.settings_path)
        self.assertEqual(after["permissions"], settings["permissions"])
        self.assertEqual(after["hooks"]["SessionStart"], [{"matcher": "startup|resume|clear|compact", "hooks": [later]}])
        self.assertFalse(after["hooks"].get("UserPromptSubmit"))
        self.assertEqual(self.read(self.receipt_path), {})
        self.uninstall()

    def test_uninstall_leaves_no_managed_matcher_group(self):
        self.setup()
        self.uninstall()
        settings = self.read(self.settings_path)
        self.assertFalse(settings.get("hooks", {}).get("SessionStart"))
        self.assertNotIn(SERVER_NAME, self.read(self.server_path).get("mcpServers", {}))
        self.assertTrue(self.vault.root.exists())

    def test_identical_preexisting_entries_remain_unowned(self):
        self.setup()
        server, settings = self.read(self.server_path), self.read(self.settings_path)
        self.uninstall()
        self.write(self.server_path, server)
        self.write(self.settings_path, settings)
        self.setup()
        self.assertEqual(self.read(self.server_path), server)
        self.assertEqual(self.read(self.settings_path), settings)
        self.uninstall()
        self.assertEqual(self.read(self.server_path), server)
        self.assertEqual(self.read(self.settings_path), settings)

    def test_edited_owned_server_or_matcher_refuses_remove_and_reinstall(self):
        self.setup()
        original_server = self.read(self.server_path)
        original_settings = self.read(self.settings_path)
        for target in ("server", "matcher", "hook"):
            with self.subTest(target=target):
                server, settings = copy.deepcopy(original_server), copy.deepcopy(original_settings)
                if target == "server":
                    server["mcpServers"][SERVER_NAME]["command"] = "edited"
                elif target == "matcher":
                    settings["hooks"]["SessionStart"][0]["matcher"] = "startup"
                else:
                    settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"] = 9
                self.write(self.server_path, server)
                self.write(self.settings_path, settings)
                for action in ("install", "uninstall"):
                    code, _, _ = self.cli("serve", "harness-claude", action, "--user")
                    self.assertEqual(code, 2)
                    self.assertEqual(self.read(self.server_path), server)
                    self.assertEqual(self.read(self.settings_path), settings)

    def test_receipt_failure_rolls_back_client_files_and_modules(self):
        self.write(self.server_path, {"keep": 42})
        before = self.server_path.read_bytes()
        def write(path, text):
            if path == self.receipt_path:
                raise OSError("synthetic receipt failure")
            _atomic_write(path, text)
        with patch("ai_dememory.integration_install._atomic_write", side_effect=write):
            code, _, _ = self.cli("setup", str(self.vault.root), "--with-claude", "--yes")
        self.assertEqual(code, 2)
        self.assertEqual(self.server_path.read_bytes(), before)
        self.assertFalse(self.settings_path.exists())
        self.assertNotIn("harness-claude", load_config().enabled_modules)

    def test_invalid_receipt_refuses_without_client_writes(self):
        self.setup()
        receipt = self.read(self.receipt_path)
        before = (self.server_path.read_bytes(), self.settings_path.read_bytes())
        for hooks in ([], None, {"SessionStart": {"owned": True}}):
            with self.subTest(hooks=hooks):
                self.write(self.receipt_path, {**receipt, "hooks": hooks})
                code, _, error = self.cli("serve", "harness-claude", "uninstall", "--user")
                self.assertEqual(code, 2, error)
                self.assertIn("receipt", error)
                self.assertEqual((self.server_path.read_bytes(), self.settings_path.read_bytes()), before)

    def test_duplicate_owned_hook_refuses_uninstall(self):
        self.setup()
        settings = self.read(self.settings_path)
        settings["hooks"]["SessionStart"].append(copy.deepcopy(settings["hooks"]["SessionStart"][0]))
        self.write(self.settings_path, settings)
        before = (self.server_path.read_bytes(), self.settings_path.read_bytes())
        code, _, error = self.cli("serve", "harness-claude", "uninstall", "--user")
        self.assertEqual(code, 2, error)
        self.assertEqual((self.server_path.read_bytes(), self.settings_path.read_bytes()), before)

    def test_direct_install_and_uninstall_without_receipt(self):
        set_module_enabled("harness-claude", True)
        code, _, error = self.cli("--vault", str(self.vault.root), "serve", "harness-claude", "uninstall", "--user")
        self.assertEqual(code, 0, error)
        self.assertFalse(self.server_path.exists())
        self.assertFalse(self.settings_path.exists())
        code, _, error = self.cli("--vault", str(self.vault.root), "serve", "harness-claude", "install", "--user")
        self.assertEqual(code, 0, error)
        self.assertTrue(self.receipt_path.is_file())

    def test_installed_mcp_recalls_global_without_codex_metadata(self):
        self.setup()
        self.learn("global", "Thursday")
        self.learn("project:other", "Sunday")
        server = self.read(self.server_path)["mcpServers"][SERVER_NAME]
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "memory.context", "arguments": {"query": "synthetic deployment window"}}}
        result = subprocess.run([server["command"], *server["args"]], env={**os.environ, **server["env"]},
                                input=json.dumps(request) + "\n", text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertNotIn("error", response)
        self.assertIn("Thursday", result.stdout)
        self.assertNotIn("Sunday", result.stdout)

    @unittest.skipIf(os.name == "nt", "POSIX symlink permissions")
    def test_linked_client_config_is_refused(self):
        target = self.root / "other-client.json"
        target.write_text('{"keep": true}', encoding="utf-8")
        self.server_path.symlink_to(target)
        code, _, _ = self.cli("setup", str(self.vault.root), "--with-claude", "--yes")
        self.assertEqual(code, 2)
        self.assertEqual(target.read_text(encoding="utf-8"), '{"keep": true}')
        self.assertFalse(self.settings_path.exists())

    @unittest.skipIf(os.name == "nt", "POSIX venv symlink and shell command")
    def test_symlinked_venv_interpreter_is_preserved(self):
        interpreter = self.root / "venv with spaces" / "bin" / "python"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(sys.executable)
        with patch("sys.executable", str(interpreter)):
            self.setup()
        self.assertEqual(self.read(self.server_path)["mcpServers"][SERVER_NAME]["command"], str(interpreter))
        for groups in self.read(self.settings_path)["hooks"].values():
            self.assertEqual(shlex.split(groups[0]["hooks"][0]["command"])[0], str(interpreter))

    def test_session_start_guidance_for_claude(self):
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                output = recall_hook(self.vault, {"hook_event_name": "SessionStart", "source": source}, "global", "claude")
                self.assertIn("hookSpecificOutput", output)
                result = output["hookSpecificOutput"]
                self.assertEqual(result["hookEventName"], "SessionStart")
                self.assertIn("memory.context", result["additionalContext"])
                self.assertLess(len(result["additionalContext"]), 1200)
        self.assertEqual(self.vault.memory_count(), 0)
        self.assertEqual(recall_hook(self.vault, {"hook_event_name": "SessionStart", "source": "unknown"}, "global", "claude"), {})

    def run_hook(self, cwd):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "What is the synthetic deployment window?"}
        if cwd is not None:
            payload["cwd"] = str(cwd)
        result = subprocess.run([sys.executable, "-m", "ai_dememory.harness", "--vault", str(self.vault.root),
                                 "--config-dir", str(self.config), "--auto-scope", "--client", "claude"],
                                input=json.dumps(payload), text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def learn(self, scope, day):
        content = f"The synthetic deployment window is {day}."
        CoreServices(self.vault).learn("Deployment window", content, scope,
            {"provider": "test", "session": "test", "turn": day, "evidence_kind": "user_statement", "excerpt": content}, day)

    def test_unbound_home_and_missing_cwd_recall_global(self):
        set_module_enabled("harness-claude", True)
        self.learn("global", "Thursday")
        self.learn("project:other", "Sunday")
        for cwd in (self.home, None):
            with self.subTest(cwd=cwd):
                output = self.run_hook(cwd)
                self.assertIn("hookSpecificOutput", output)
                context = output["hookSpecificOutput"]["additionalContext"]
                self.assertIn("DeMemory scope: global", context)
                self.assertIn("Thursday", context)
                self.assertNotIn("Sunday", context)

    def test_bound_project_and_exclusion_are_respected(self):
        set_module_enabled("harness-claude", True)
        project = self.root / "project"
        project.mkdir()
        configure_project(project, scope="project:chosen")
        self.learn("project:chosen", "Tuesday")
        self.learn("project:other", "Sunday")
        context = self.run_hook(project)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Tuesday", context)
        self.assertNotIn("Sunday", context)
        configure_project(project, client="claude", enabled=False)
        self.assertEqual(self.run_hook(project), {})
        set_module_enabled("harness-claude", False)
        self.assertEqual(self.run_hook(self.home), {})


if __name__ == "__main__":
    unittest.main()
