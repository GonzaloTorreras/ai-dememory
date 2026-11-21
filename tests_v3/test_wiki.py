from ai_dememory.wiki import MAX_INDEX_CHARS, ProjectWiki
from ai_dememory.vault import VaultBusyError
from tests_v3.test_core import V3TestCase


class ProjectWikiTests(V3TestCase):
    def setUp(self):
        super().setUp()
        self.project = self.root / "project"
        self.wiki = ProjectWiki(self.project)

    def test_setup_is_additive_and_idempotent_with_only_one_initial_page(self):
        self.assertFalse(self.project.exists())
        self.project.mkdir()
        agents = self.project / "AGENTS.md"
        original = b"# Existing rules\r\n\r\nKeep custom instructions.\r\n"
        agents.write_bytes(original)
        result = self.wiki.initialize()
        self.assertTrue(result["initialized"])
        self.assertTrue(agents.read_bytes().startswith(original))
        before = agents.read_bytes()
        self.wiki.initialize()
        self.assertEqual(agents.read_bytes(), before)
        self.assertEqual([p.name for p in self.wiki.root.iterdir()], ["index.md"])
        self.assertEqual(self.wiki.pages(), [])
        self.assertIn("tools", {p["id"] for p in self.wiki.templates()})
        self.assertEqual(result["model_calls"], 0)

    def test_empty_navigation_never_links_to_missing_or_deleted_content(self):
        self.wiki.initialize()
        index = self.wiki.root / "index.md"
        self.assertNotIn("](catalog.md)", index.read_text())
        self.wiki.save("lessons.md", "# Lesson\n\nVerify a restore.")
        (self.wiki.root / "lessons.md").unlink()
        self.wiki.rebuild()
        self.assertNotIn("](catalog.md)", index.read_text())
        catalog = (self.wiki.root / "catalog.md").read_text()
        self.assertNotIn("](lessons.md)", catalog)
        self.assertIn("No content pages yet", catalog)

    def test_save_recall_correct_and_rebuild_ordinary_markdown(self):
        self.wiki.initialize()
        content = "# Backups\n\nKeep encrypted backups nightly.\n\nOnly staging is verified; production is NOT tested.\n"
        page = self.wiki.save("lessons/backups.md", content)
        context = self.wiki.context("encrypted backups")
        self.assertEqual(context["sources"][0]["path"], "lessons/backups.md")
        self.assertIn("production is NOT tested", context["context"])
        self.assertFalse(context["sources"][0]["partial"])
        with self.assertRaisesRegex(ValueError, "revision"):
            self.wiki.save(page["path"], "# Backups\n\nBackups changed.")
        changed = self.wiki.save(page["path"], "# Backups\n\nUse monthly encrypted backups.", page["revision"])
        with self.assertRaisesRegex(ValueError, "changed"):
            self.wiki.save(page["path"], content, page["revision"])
        self.assertNotEqual(changed["revision"], page["revision"])
        before = {p.relative_to(self.wiki.root).as_posix(): p.read_bytes() for p in self.wiki.root.rglob("*.md")}
        self.wiki.rebuild()
        self.assertEqual(before, {p.relative_to(self.wiki.root).as_posix(): p.read_bytes() for p in self.wiki.root.rglob("*.md")})
        self.assertTrue((self.wiki.root / "lessons" / "index.md").exists())
        self.assertEqual(self.wiki.status()["broken_links"], [])

    def test_manual_pages_need_no_metadata_and_status_filters_recall(self):
        self.wiki.initialize()
        (self.wiki.root / "manual.md").write_text("# Lighting\n\nWarm lighting suits this room.", encoding="utf-8")
        self.wiki.save("draft.md", "# Lighting guess\n\n<!-- dememory-status: provisional -->\n\nWarm lighting is a guess.")
        self.wiki.save("archive/lighting.md", "# Old lighting\n\nWarm lighting was replaced.")
        self.assertEqual(len(self.wiki.pages()), 3)
        result = self.wiki.context("warm lighting")
        self.assertEqual([p["path"] for p in result["sources"]], ["manual.md"])
        self.assertEqual(self.wiki.status()["provisional"], 1)
        self.assertEqual(self.wiki.status()["archived"], 1)

    def test_title_match_recovers_body_even_without_repeated_keywords(self):
        self.wiki.initialize()
        self.wiki.save("backups.md", "# Backup policy\n\nKeep copies nightly and test restoration monthly.")
        result = self.wiki.context("backup policy")
        self.assertEqual(result["sources"][0]["path"], "backups.md")
        self.assertIn("test restoration monthly", result["context"])

    def test_root_index_is_bounded_catalog_is_complete_without_moving_notes(self):
        self.wiki.initialize()
        for number in range(45):
            (self.wiki.root / f"lesson-{number:02d}.md").write_text(
                f"# A useful independent lesson number {number}\n\n" + "Useful context. " * 30, encoding="utf-8")
        self.wiki.rebuild()
        root = (self.wiki.root / "index.md").read_text(encoding="utf-8")
        catalog = (self.wiki.root / "catalog.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(root), MAX_INDEX_CHARS)
        self.assertIn("catalog.md", root)
        for number in range(45):
            self.assertIn(f"lesson-{number:02d}.md", catalog)
            self.assertTrue((self.wiki.root / f"lesson-{number:02d}.md").exists())
        self.assertFalse((self.wiki.root / "topics").exists())
        self.wiki.rebuild()

    def test_existing_human_index_and_agents_are_preserved(self):
        self.wiki.root.mkdir(parents=True)
        index = self.wiki.root / "index.md"
        human = "# My custom index\n\nKeep [our guide](../../guide.md).\n"
        index.write_text(human, encoding="utf-8")
        self.wiki.initialize()
        self.assertTrue(index.read_text(encoding="utf-8").startswith(human))
        self.wiki.save("tools.md", "# Tools\n\nThe camera uses fixed exposure.")
        self.assertTrue(index.read_text(encoding="utf-8").startswith(human))

    def test_unsafe_paths_secrets_and_link_escapes_are_rejected(self):
        self.wiki.initialize()
        for path in ("../outside.md", "/outside.md", "a\\outside.md", "index.md", "x/catalog.md", "a/b/c/d/page.md"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.wiki.save(path, "# Valid\n\nSafe text.")
        with self.assertRaises(ValueError):
            self.wiki.save("tools.md", "# Key\n\nghp_" + "A" * 30)
        with self.assertRaises(ValueError):
            self.wiki.save("ghp_" + "A" * 30 + ".md", "# No key\n\nSafe content.")
        with self.assertRaises(ValueError):
            self.wiki.save("tools.md", "# Escape\n\n[secret](../../../outside.md)")
        self.assertFalse((self.root / "outside.md").exists())
        self.assertEqual(self.wiki.pages(), [])

    def test_safe_project_reference_is_not_followed_and_broken_links_are_reported(self):
        self.wiki.initialize()
        (self.project / "guide.md").write_text("A linked project source, not another memory.", encoding="utf-8")
        self.wiki.save("references.md", "# References\n\nRead [guide](../../guide.md) and [pending](future.md).")
        self.assertEqual(self.wiki.status()["broken_links"], [{"page":"references.md","target":"docs/dememory/future.md"}])
        self.assertEqual(self.wiki.context("linked project source")["sources"], [])

    def test_oversized_content_and_partial_context_fail_without_cutting_claims(self):
        self.wiki.initialize()
        with self.assertRaises(ValueError):
            self.wiki.save("large.md", "x" * 24_001)
        self.wiki.save("large.md", "# Deep lesson\n\n## Important condition\n\nDo not use varnish outdoors.\n\n## History\n\n" + "Old observation. " * 200)
        result = self.wiki.context("varnish outdoors", max_chars=256)
        self.assertIn("Do not use varnish outdoors.", result["context"])
        self.assertTrue(result["sources"][0]["partial"])
        self.assertLessEqual(len(result["context"]), 256)

    def test_invalid_or_duplicate_status_never_becomes_current(self):
        self.wiki.initialize()
        for content in ("# Draft\n<!-- dememory-status: unknown -->\nX", "<!-- dememory-status: current -->\n<!-- dememory-status: provisional -->"):
            with self.assertRaises(ValueError):
                self.wiki.save("draft.md", content)
        (self.wiki.root / "manual.md").write_text("# Manual\n<!-- dememory-status: unknown -->\nSensitive outcome.", encoding="utf-8")
        self.assertEqual(self.wiki.pages(), [])
        self.assertTrue(self.wiki.status()["warnings"])

    def test_linked_roots_pages_and_junctions_are_rejected(self):
        self.wiki.initialize()
        outside = self.root / "outside"
        outside.mkdir()
        linked = self.wiki.root / "linked"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks requires Developer Mode or privileges on Windows")
        with self.assertRaises(ValueError):
            self.wiki.save("linked/page.md", "# Escape\n\nNot local.")
        with self.assertRaises(ValueError):
            ProjectWiki(linked)
        self.assertTrue(self.wiki.status()["warnings"])

    def test_another_writer_is_fail_fast(self):
        self.wiki.initialize()
        with self.wiki._lock():
            with self.assertRaises(VaultBusyError):
                self.wiki.save("lessons.md", "# Lessons\n\nNo overlapping writes.")
        self.assertEqual(self.wiki.pages(), [])

    def test_unsafe_navigation_never_overwrites_linked_targets(self):
        self.wiki.initialize()
        original = (self.wiki.root / "index.md").read_bytes()
        (self.wiki.root / "index.md").write_text("<!-- BEGIN AI-DEMEMORY WIKI -->\nBroken", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Malformed"):
            self.wiki.rebuild()
        self.assertNotEqual((self.wiki.root / "index.md").read_bytes(), original)
