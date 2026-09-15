from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from ai_dememory.config import harness_enabled, load_config, set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.harness import install_project
from ai_dememory.integration_install import install_user, _replace_block, _transaction, BEGIN, END
from ai_dememory.projects import configure_project, resolve_project
from ai_dememory.builtin_modules.mcp import ClientBinding, serve
from ai_dememory.vault import Vault


class GlobalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home, self.config = self.root / "codex-home", self.root / "config"
        self.home.mkdir()
        self.env = patch.dict(os.environ, {"CODEX_HOME": str(self.home), "AI_DEMEMORY_CONFIG_DIR": str(self.config)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.vault = Vault.create(self.root / "vault")
        self.a, self.b = self.root / "a" / "same", self.root / "b" / "same"
        self.a.mkdir(parents=True)
        self.b.mkdir(parents=True)
        set_module_enabled("harness", True)
        set_module_enabled("mcp", True)

    def test_distinct_names_and_configured_worktree_sharing(self):
        (self.a / ".git" / "worktrees" / "test").mkdir(parents=True)
        (self.a / ".git" / "worktrees" / "test" / "commondir").write_text("../..")
        (self.b / ".git").write_text("gitdir: " + str(self.a / ".git" / "worktrees" / "test"))
        self.assertEqual(resolve_project(self.a)["scope"], resolve_project(self.b)["scope"])
        configure_project(self.a, scope="project:chosen")
        self.assertEqual(resolve_project(self.b)["scope"], "project:chosen")
        isolated = self.root / "unrelated" / "same"
        isolated.mkdir(parents=True)
        self.assertNotEqual(resolve_project(isolated)["scope"], resolve_project(self.a)["scope"])

    def test_projectless_isolated_and_home_not_global_fallback(self):
        self.assertNotEqual(resolve_project(self.a)["scope"], resolve_project(self.b)["scope"])
        with patch("ai_dememory.projects.Path.home", return_value=self.a):
            with self.assertRaisesRegex(ValueError, "No project binding"):
                resolve_project(self.a)
        with self.assertRaises(ValueError):
            resolve_project("relative")

    def test_exclusion_applies_to_all_aliases_of_one_project(self):
        configure_project(self.a, scope="project:shared")
        configure_project(self.b, scope="project:shared")
        configure_project(self.a, client="codex", enabled=False)
        self.assertIn("codex", resolve_project(self.b)["excluded_clients"])
        configure_project(self.b, client="codex", enabled=True)
        self.assertNotIn("codex", resolve_project(self.a)["excluded_clients"])

    def test_generic_toggle_preserves_sibling_without_import(self):
        with patch("importlib.import_module", side_effect=AssertionError("no module import")):
            set_module_enabled("harness-codex", False)
        self.assertFalse(harness_enabled("codex"))
        self.assertTrue(harness_enabled("claude"))
        self.assertNotIn("harness", load_config().enabled_modules)

    def request(self, thread="t1", name="memory.context", arguments=None):
        return {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": arguments or {"query": "synthetic window"},
            "_meta": {"threadId": thread, "x-codex-turn-metadata": json.dumps({"thread_id": thread, "turn_id": "turn1"})}}}

    def test_binding_rejects_thread_reuse_missing_metadata_and_live_disable(self):
        binding = ClientBinding(self.a)
        binding.check(self.request())
        with self.assertRaisesRegex(ValueError, "shared across"):
            binding.check(self.request("t2"))
        request = self.request()
        request["params"].pop("_meta")
        with self.assertRaisesRegex(ValueError, "thread binding"):
            binding.check(request)
        configure_project(self.a, client="codex", enabled=False)
        with self.assertRaisesRegex(ValueError, "disabled"):
            binding.check(self.request())
        ClientBinding(self.b).check(self.request())
        set_module_enabled("harness-codex", False)
        with self.assertRaisesRegex(ValueError, "disabled"):
            ClientBinding(self.b).check(self.request())

    def test_native_learning_uses_transport_identity_and_is_scoped(self):
        scope = resolve_project(self.a)["scope"]
        args = {"title": "Window", "content": "The synthetic window is Tuesday.", "scope": scope,
                "event_id": "window", "source": {"provider": "invented", "session": "current", "turn": "current",
                "excerpt": "The synthetic window is Tuesday.", "evidence_kind": "user_statement"}}
        request = self.request(name="memory.learn", arguments=args)
        output = io.StringIO()
        with patch("ai_dememory.builtin_modules.mcp.Path.cwd", return_value=self.a):
            serve(CoreServices(self.vault), ["--auto-scope"], io.StringIO(json.dumps(request) + "\n"), output)
        response = json.loads(output.getvalue())
        self.assertNotIn("error", response)
        rows = CoreServices(self.vault).list_memories(scope)
        self.assertEqual(rows[0]["source"]["session"], "t1")
        self.assertEqual(rows[0]["source"]["provider"], "codex")
        self.assertEqual(args["source"]["session"], "current")
        self.assertEqual(CoreServices(self.vault).context("synthetic window", scope=resolve_project(self.b)["scope"])["memory_ids"], [])

    def test_binding_rejection_keeps_request_id(self):
        request = self.request()
        request["params"].pop("_meta")
        output = io.StringIO()
        with patch("ai_dememory.builtin_modules.mcp.Path.cwd", return_value=self.a):
            serve(CoreServices(self.vault), ["--auto-scope"], io.StringIO(json.dumps(request) + "\n"), output)
        result = json.loads(output.getvalue())
        self.assertEqual(result["id"], request["id"])
        self.assertEqual(result["error"]["code"], -32602)

    def test_global_merge_repeat_uninstall_preserves_unrelated_changes(self):
        config = self.home / "config.toml"
        hooks = self.home / "hooks.json"
        config.write_text('model = "user-selected"\n[mcp_servers.other]\ncommand="other"\n')
        hooks.write_text(json.dumps({"user_setting": 1, "hooks": {"Stop": [{"hooks": [{"type":"command", "command":"other"}]}]}}))
        self.assertTrue(install_user(self.vault)["changed"])
        self.assertFalse(install_user(self.vault)["changed"])
        before = tomllib.loads(config.read_text())
        self.assertNotIn("cwd", before["mcp_servers"]["dememory_v3"])
        self.assertIn("--auto-scope", before["mcp_servers"]["dememory_v3"]["args"])
        config.write_text(config.read_text() + '\n[mcp_servers.later]\ncommand="keep"\n')
        install_user(self.vault, remove=True)
        after = tomllib.loads(config.read_text())
        self.assertEqual(after["mcp_servers"]["later"]["command"], "keep")
        self.assertEqual(after["model"], "user-selected")
        self.assertNotIn("dememory_v3", after["mcp_servers"])
        self.assertEqual(json.loads(hooks.read_text())["hooks"]["Stop"][0]["hooks"][0]["command"], "other")

    def test_malformed_hook_causes_zero_changes(self):
        config, hooks = self.home / "config.toml", self.home / "hooks.json"
        config.write_text("# user config\n")
        hooks.write_text("invalid")
        with self.assertRaises(ValueError):
            install_user(self.vault)
        self.assertEqual(config.read_text(), "# user config\n")
        self.assertFalse((self.config / "integrations" / "codex-global.json").exists())

    def test_unowned_project_style_global_hook_is_not_duplicated(self):
        path = self.home / "hooks.json"
        original = json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "python -m ai_dememory.harness --scope project:old"}]}]}})
        path.write_text(original)
        with self.assertRaisesRegex(ValueError, "Unowned DeMemory hook"):
            install_user(self.vault)
        self.assertEqual(path.read_text(), original)
        self.assertFalse((self.home / "config.toml").exists())

    def test_unowned_and_modified_definitions_are_not_adopted(self):
        path = self.home / "config.toml"
        path.write_text('[mcp_servers."dememory_v3"]\ncommand="user-owned"\n')
        with self.assertRaisesRegex(ValueError, "unowned"):
            install_user(self.vault)
        path.unlink()
        install_user(self.vault)
        before = path.read_text().replace("tool_timeout_sec = 8", "tool_timeout_sec = 9")
        path.write_text(before)
        with self.assertRaisesRegex(ValueError, "edited"):
            install_user(self.vault, remove=True)
        self.assertEqual(path.read_text(), before)

    def test_marker_in_multiline_toml_cannot_erase_other_settings(self):
        block = BEGIN + '[mcp_servers.dememory_v3]\ncommand="test"\n' + END
        text = "example = '''\n" + block + "'''\n" + block
        with self.assertRaises(ValueError):
            _replace_block(text, block, "")

    def test_owned_project_retirement_preserves_scope_and_undoes_exact_files(self):
        files = install_project(self.vault, self.a, "codex", "project:old")
        originals = {p:p.read_text() for p in files}
        install_user(self.vault, projects=[self.a])
        self.assertEqual(resolve_project(self.a)["scope"], "project:old")
        self.assertNotIn("dememory_v3", tomllib.loads(files[0].read_text()).get("mcp_servers", {}))
        self.assertEqual(json.loads(files[1].read_text()), {})
        files[0].write_text('# later user edit\n')
        install_user(self.vault, remove=True)
        self.assertEqual(files[0].read_text(), '# later user edit\n')
        self.assertEqual(files[1].read_text(), originals[files[1]])

    def test_partial_write_rolls_back_without_overwriting_concurrent_edit(self):
        first, second = self.root / "one", self.root / "two"
        first.write_text("before")
        from ai_dememory.vault import _atomic_write
        def write(path, text):
            if path == second:
                raise OSError("synthetic failure")
            _atomic_write(path, text)
        with patch("ai_dememory.integration_install._atomic_write", side_effect=write):
            with self.assertRaises(OSError):
                _transaction([(first, "before", "after"), (second, None, "new")])
        self.assertEqual(first.read_text(), "before")
        self.assertFalse(second.exists())

    def test_selector_failure_rolls_back_global_install(self):
        set_module_enabled("mcp", False)
        selector = self.config / "config.toml"
        before = selector.read_text()
        from ai_dememory.vault import _atomic_write
        def write(path, text):
            if path == selector:
                raise OSError("synthetic selector failure")
            _atomic_write(path, text)
        with patch("ai_dememory.integration_install._atomic_write", side_effect=write):
            with self.assertRaises(OSError):
                install_user(self.vault)
        self.assertEqual(selector.read_text(), before)
        self.assertFalse((self.home / "config.toml").exists())
        self.assertFalse((self.home / "hooks.json").exists())


if __name__ == "__main__":
    unittest.main()
