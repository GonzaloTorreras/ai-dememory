import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from ai_dememory.config import select_vault, set_module_enabled
from ai_dememory.harness import recall_hook
from ai_dememory.vault import Vault
from ai_dememory.wiki import ProjectWiki
from ai_dememory.wiki_hook import find_project, install, recall, MAX_INPUT, _packet_context
from tests_v3.test_core import V3TestCase


class WikiHookTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.project = self.root / "project"
        self.wiki = ProjectWiki(self.project)
        self.wiki.initialize()
        self.wiki.save("lessons.md", "# Restoration\n\nVerify attachments as well as database records after restoring.")
        set_module_enabled("wiki", True)
        self.payload = {"hook_event_name":"UserPromptSubmit", "prompt":"How should we verify a restoration?",
                        "cwd":str(self.project), "transcript_path":"must-not-be-opened"}

    def test_native_hook_returns_small_evidenced_context_and_no_mcp_guidance(self):
        for client in ("codex", "claude"):
            result = recall(self.project, self.payload, client)
            context = result["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Verify attachments", context)
            self.assertIn("docs/dememory/lessons.md", context)
            self.assertLessEqual(len(context), 2400)
            self.assertNotIn("memory.learn", context)
            self.assertNotIn("must-not-be-opened", context)
        for source in ("startup", "resume", "clear", "compact", "fork"):
            context = recall(self.project, {"hook_event_name":"SessionStart", "source":source})
            self.assertIn("docs/dememory/index.md", context["hookSpecificOutput"]["additionalContext"])

    def test_context_omits_oversized_whole_excerpt_instead_of_cutting_its_conditions(self):
        excerpt = "Long condition " * 250 + "Do not apply outside this project."
        source = {"path":"conditions.md", "title":"Conditions", "excerpt":excerpt}
        text = _packet_context({"context":excerpt, "sources":[source], "warnings":[]})
        self.assertNotIn("Long condition", text)
        self.assertIn("whole excerpts were omitted", text)
        self.assertLessEqual(len(text), 2400)

    def test_context_packs_multiple_complete_excerpts_preserving_partial_and_budget_warnings(self):
        sources = [{"path":f"rule-{i}.md", "title":f"Rule {i}", "excerpt":f"Rule {i}: " + "x"*500 + "; never on Friday.",
                    "partial":i == 0} for i in range(3)]
        packet = {"sources":sources, "warnings":["Another relevant page needs a larger reading budget."]}
        text = _packet_context(packet)
        self.assertLessEqual(len(text), 2400)
        for source in sources:
            self.assertIn(source["excerpt"], text)
        self.assertIn("Partial excerpt; read the full page for conditions.", text)
        self.assertIn(packet["warnings"][0], text)
        smaller = _packet_context(packet, max_chars=1600)
        self.assertLessEqual(len(smaller), 1600)
        self.assertIn(sources[0]["excerpt"], smaller)
        self.assertIn(sources[1]["excerpt"], smaller)
        self.assertNotIn("Rule 2:", smaller)
        self.assertIn("whole excerpts were omitted", smaller)

    def test_shared_context_is_labelled_read_only_and_not_as_a_consumer_project_path(self):
        sources = [{"path":"values.md", "title":"Values", "excerpt":"Keep personal values private.", "shared":True},
                   {"path":"lessons.md", "title":"Local lesson", "excerpt":"Verify local restoration attachments."}]
        text = _packet_context({"sources":sources, "warnings":[]})
        self.assertIn("Source: shared memory (read-only): values.md", text)
        self.assertNotIn("docs/dememory/values.md", text)
        self.assertIn("Source: docs/dememory/lessons.md", text)

    def test_disabled_recursion_invalid_foreign_and_secret_requests_are_empty(self):
        for payload in (None, {**self.payload,"prompt":"sk-"+"x"*30},
                        {**self.payload,"prompt":"x"*12001}, {**self.payload,"cwd":str(self.root / "other")},
                        {"hook_event_name":"SessionStart","source":"unknown"}):
            self.assertEqual(recall(self.project, payload), {})
        with patch.dict(os.environ, {"AI_DEMEMORY_WIKI_WORKER":"1"}):
            self.assertEqual(recall(self.project, self.payload), {})
        set_module_enabled("wiki", False)
        self.assertEqual(recall(self.project, self.payload), {})

    def test_session_end_refreshes_manual_pages_without_models_transcripts_or_context(self):
        page = self.wiki.root / "manual-lesson.md"
        page.write_text("# Manual lesson\n\nKeep the verified attachment check.", encoding="utf-8")
        catalog = self.wiki.root / "catalog.md"
        self.assertNotIn("manual-lesson.md", catalog.read_text(encoding="utf-8"))
        payload = {"hook_event_name":"SessionEnd", "cwd":str(self.project),
                   "transcript_path":"must-not-be-opened"}
        with patch("ai_dememory.wiki_runtime.recall_for_project", side_effect=AssertionError("No model path")):
            self.assertEqual(recall(self.project, payload), {})
        self.assertIn("manual-lesson.md", catalog.read_text(encoding="utf-8"))
        for client in ("codex", "claude"):
            installed = install(self.project, client)
            settings = json.loads(Path(installed["path"]).read_text(encoding="utf-8"))
            self.assertEqual(settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"], 25)
            self.assertIn("--allow-assisted", settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"])
            self.assertEqual(settings["hooks"]["SessionStart"][0]["hooks"][0]["timeout"], 3)
            self.assertEqual(settings["hooks"]["SessionEnd"][0]["hooks"][0]["timeout"], 3)
            self.assertNotIn("Stop", settings["hooks"])

    def test_session_end_skips_recursive_worker_and_fails_open_when_busy(self):
        page = self.wiki.root / "worker-note.md"
        page.write_text("# Worker note\n\nDo not rebuild from recursive worker hooks.", encoding="utf-8")
        payload = {"hook_event_name":"SessionEnd", "cwd":str(self.project)}
        with patch.dict(os.environ, {"AI_DEMEMORY_WIKI_WORKER":"1"}), patch.object(ProjectWiki, "rebuild") as rebuild:
            self.assertEqual(recall(self.project, payload), {})
            rebuild.assert_not_called()
        self.assertNotIn("worker-note.md", (self.wiki.root / "catalog.md").read_text(encoding="utf-8"))
        with patch.object(ProjectWiki, "rebuild", side_effect=ValueError("Another writer is active")):
            self.assertEqual(recall(self.project, payload), {})

    def test_subprocess_fail_open_and_child_exits(self):
        for raw in (b"broken", b"null", b"x"*(MAX_INPUT+1)):
            result = subprocess.run([sys.executable,"-m","ai_dememory.wiki_hook","--project",str(self.project)],
                                    input=raw,capture_output=True,timeout=5)
            self.assertEqual((result.returncode,result.stdout.strip(),result.stderr), (0,b"{}",b""))

    def test_hook_install_preserves_unrelated_settings_is_idempotent_and_keeps_venv_path(self):
        path = self.project / ".claude/settings.json"
        path.parent.mkdir()
        original = {"permissions":{"allow":["Read"]},"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"other"}]}]}}
        path.write_text(json.dumps(original),encoding="utf-8")
        with patch("ai_dememory.wiki_hook.sys.executable", str(self.root / "venv/Scripts/python.exe")):
            first = install(self.project, "claude")
            before = path.read_bytes()
            second = install(self.project, "claude")
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(path.read_bytes(), before)
        saved = json.loads(before)
        self.assertEqual(saved["permissions"], original["permissions"])
        self.assertEqual(saved["hooks"]["UserPromptSubmit"][0], original["hooks"]["UserPromptSubmit"][0])
        self.assertIn("venv", saved["hooks"]["UserPromptSubmit"][1]["hooks"][0]["command"])
        self.assertFalse((self.project / ".mcp.json").exists())
        saved["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 99
        path.write_text(json.dumps(saved),encoding="utf-8")
        edited = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "edited|changed"):
            install(self.project, "claude")
        self.assertEqual(path.read_bytes(), edited)

    def test_global_harness_prefers_project_wiki_and_discovery_stops_at_nested_git(self):
        vault = Vault.create(self.root / "vault")
        vault.remember("Wrong old vault result", "Restoration")
        context = recall_hook(vault, self.payload, "project:test")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Verify attachments", context)
        self.assertNotIn("Wrong old vault", context)
        nested = self.project / "subproject"
        nested.mkdir()
        self.assertEqual(find_project(nested), self.project)
        (nested / ".git").mkdir()
        self.assertIsNone(find_project(nested))

    def test_old_global_hook_path_never_requests_assisted_recall(self):
        vault = Vault.create(self.root / "private")
        select_vault(vault.root)
        packet = self.wiki.context(self.payload["prompt"])
        with patch("ai_dememory.wiki_runtime.recall_for_project", return_value=packet) as broker:
            result = recall_hook(vault, self.payload, "project:test")
        self.assertIn("Verify attachments", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(broker.call_args.kwargs, {"automatic":True,"allow_assisted":False})
