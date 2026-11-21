import json
from pathlib import Path
from unittest.mock import patch

from ai_dememory.config import load_config, select_vault, set_module_enabled
from ai_dememory.wiki import ProjectWiki
from tests_v3.test_core import V3TestCase


class WikiCliTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.project = self.root / "project"

    def setup_wiki(self, *extra):
        code, output, error = self.run_cli("setup", "--project", str(self.project), "--yes", "--json", *extra)
        self.assertEqual(code, 0, error)
        return json.loads(output)

    def test_setup_save_recall_correct_and_status_without_a_default_vault(self):
        self.project.mkdir()
        agents = self.project / "AGENTS.md"
        agents.write_text("# Existing rules\nKeep tests useful.\n", encoding="utf-8")
        result = self.setup_wiki()
        self.assertEqual(result["model_calls"], 0)
        self.assertIsNone(load_config().default_vault)
        self.assertIn("wiki", load_config().enabled_modules)
        self.assertIn("# Existing rules", agents.read_text(encoding="utf-8"))
        self.assertTrue((self.project / "docs/dememory/index.md").is_file())
        self.assertFalse((self.project / "docs/dememory/architecture.md").exists())
        code, output, error = self.run_cli("remember", "# Backup rule\n\nBackup nightly, not weekly.",
            "--project", str(self.project), "--page", "lessons.md", "--json")
        self.assertEqual(code, 0, error)
        saved = json.loads(output)
        code, output, error = self.run_cli("recall", "backup", "--project", str(self.project), "--json")
        self.assertEqual(code, 0, error)
        recalled = json.loads(output)
        self.assertIn("not weekly", recalled["context"])
        self.assertEqual(recalled["model_calls"], 0)
        changed = "# Backup rule\n\nBackups run weekly after an explicit correction."
        code, _, error = self.run_cli("remember", changed, "--project", str(self.project), "--page", "lessons.md")
        self.assertEqual(code, 2)
        code, output, error = self.run_cli("remember", changed, "--project", str(self.project), "--page", "lessons.md",
            "--expected-revision", saved["revision"], "--json")
        self.assertEqual(code, 0, error)
        self.assertEqual(ProjectWiki(self.project).read("lessons.md")["content"].strip(), changed)
        code, output, error = self.run_cli("status", "--project", str(self.project), "--json")
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["pages"], 1)

    def test_setup_is_idempotent_and_claude_codex_hooks_do_not_install_mcp(self):
        self.setup_wiki("--with-codex", "--with-claude")
        before = {p: p.read_bytes() for p in (self.project / "AGENTS.md", self.project / ".codex/hooks.json",
                                             self.project / ".claude/settings.json")}
        result = self.setup_wiki("--with-codex", "--with-claude")
        self.assertTrue(all(p.read_bytes() == value for p, value in before.items()))
        self.assertTrue(all(not h["changed"] for h in result["hooks"]))
        self.assertFalse((self.project / ".mcp.json").exists())
        self.assertFalse((self.project / ".codex/config.toml").exists())

    def test_invalid_mixed_modes_and_disabled_module_do_not_import_wiki(self):
        for args in (("setup", str(self.root / "vault"), "--project", str(self.project), "--yes"),
                     ("setup", "--project", str(self.project), "--with-schedule", "--yes"),
                     ("setup", "--with-claude", "--yes"),
                     ("status", "--project", str(self.project), "--vault", str(self.root / "vault")),
                     ("remember", "x", "--page", "lessons.md")):
            code, _, _ = self.run_cli(*args)
            self.assertEqual(code, 2)
        self.setup_wiki()
        set_module_enabled("wiki", False)
        with patch("ai_dememory.wiki.ProjectWiki", side_effect=AssertionError("disabled code")):
            code, _, error = self.run_cli("status", "--project", str(self.project))
        self.assertEqual(code, 2)
        self.assertIn("disabled", error)

    def test_wiki_page_is_explicit_and_cannot_escape_or_accept_vault_flags(self):
        self.setup_wiki()
        for extra in ([], ["--page", "../escape.md"], ["--page", "lessons.md", "--scope", "project:other"],
                      ["--page", "lessons.md", "--kind", "durable"]):
            code, _, _ = self.run_cli("remember", "A useful fact", "--project", str(self.project), *extra)
            self.assertEqual(code, 2)
        self.assertFalse((self.project / "docs/escape.md").exists())

    def test_noninteractive_setup_needs_confirmation(self):
        code, _, _ = self.run_cli("setup", "--project", str(self.project), "--json")
        self.assertEqual(code, 2)
        self.assertFalse(self.project.exists())

    def test_project_setup_attaches_to_selected_private_vault_without_reselecting_it(self):
        private = self.root / "private-vault"
        code, _, error = self.run_cli("setup", str(private), "--yes")
        self.assertEqual(code, 0, error)
        with patch("os.getcwd", return_value=str(self.root)):
            code, output, error = self.run_cli("setup", "--project", "project", "--yes", "--json")
        self.assertEqual(code, 0, error)
        self.assertEqual(load_config().default_vault, str(private))
        self.assertEqual(json.loads(output)["registration"]["project"]["root"], str(self.project))

    def test_stale_optional_vault_does_not_break_standalone_setup_or_reset_selection(self):
        missing = self.root / "missing-private-vault"
        select_vault(missing)
        result = self.setup_wiki()
        self.assertEqual(result["registration"], {"registered":False,"reason":"configured_vault_unavailable"})
        self.assertTrue(result["warnings"])
        self.assertEqual(load_config().default_vault, str(missing))
        self.assertFalse(missing.exists())
        self.assertTrue((self.project / "AGENTS.md").is_file())
        self.assertTrue((self.project / "docs/dememory/index.md").is_file())
        self.assertEqual(ProjectWiki(self.project).pages(), [])
