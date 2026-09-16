"""Display metadata must never become a project identity or learning input."""
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ai_dememory.projects import configure_project, remember_project_name, resolve_project, scope_labels
from ai_dememory.vault import Vault


class ProjectNameTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.env = patch.dict(os.environ, {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "config")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.vault = Vault.create(self.root / "vault")

    def project(self, relative):
        path = self.root / relative
        path.mkdir(parents=True)
        return resolve_project(path)

    def test_names_persist_without_paths_or_rewriting_old_memories(self):
        project = self.project("Projects/Readable name")
        scope = project["scope"]
        memory = self.vault.remember("Synthetic lesson", "Lesson", scope=scope)
        before = {path: path.read_bytes() for path in self.vault.iter_memory_paths()}
        self.assertTrue(remember_project_name(self.vault, project))
        self.assertTrue(remember_project_name(self.vault, project))
        self.assertEqual(scope_labels(Vault.open(self.vault.root), [scope]), {scope: "Readable name"})
        self.assertEqual(before, {path: path.read_bytes() for path in self.vault.iter_memory_paths()})
        self.assertEqual(memory.scope, scope)
        with closing(sqlite3.connect(self.vault.root / "runtime.sqlite")) as db:
            self.assertEqual(db.execute("SELECT * FROM project_names").fetchall(), [(scope, "Readable name")])
        self.assertFalse((self.root / "config" / "projects.json").exists())

    def test_worktrees_use_main_project_name_and_identity(self):
        main = self.root / "Main project"
        metadata = main / ".git" / "worktrees" / "feature"
        metadata.mkdir(parents=True)
        (metadata / "commondir").write_text("../..", encoding="utf-8")
        worktree = self.root / "unrecognizable-worktree-id"
        worktree.mkdir()
        (worktree / ".git").write_text("gitdir: " + str(metadata), encoding="utf-8")
        first, second = resolve_project(main), resolve_project(worktree)
        self.assertEqual(first["scope"], second["scope"])
        self.assertEqual(first["name"], second["name"])
        self.assertEqual(second["name"], "Main project")

    def test_same_name_projects_are_distinct_and_labels_disambiguate(self):
        a, b = self.project("one/Same"), self.project("two/Same")
        for project in (a, b):
            remember_project_name(self.vault, project)
        self.assertNotEqual(a["scope"], b["scope"])
        labels = scope_labels(self.vault, [a["scope"], b["scope"]])
        self.assertNotEqual(labels[a["scope"]], labels[b["scope"]])
        self.assertTrue(all(name.startswith("Same · ") for name in labels.values()))

    def test_unknown_and_explicit_bindings_are_read_only(self):
        scope = "project:" + "a" * 32
        self.assertEqual(scope_labels(self.vault, [scope, "global"])[scope], "Unnamed project")
        project = self.project("Configured project")
        configure_project(project["root"], scope=scope)
        self.assertEqual(scope_labels(self.vault, [scope])[scope], os.path.normcase("Configured project"))
        self.assertFalse((self.vault.root / "runtime.sqlite").exists())

    def test_locked_display_database_fails_open_quickly(self):
        project = self.project("Normal project")
        self.assertTrue(remember_project_name(self.vault, project))
        with closing(sqlite3.connect(self.vault.root / "runtime.sqlite")) as db, db:
            db.execute("BEGIN EXCLUSIVE")
            start = time.monotonic()
            self.assertFalse(remember_project_name(self.vault, {**project, "name": "New name"}))
            labels = scope_labels(self.vault, [project["scope"]])
            self.assertLess(time.monotonic() - start, 1)
            self.assertEqual(labels[project["scope"]], "Unnamed project")

    def test_invalid_storage_never_breaks_label_read_or_capture(self):
        project = self.project("Project")
        (self.vault.root / "runtime.sqlite").mkdir()
        self.assertFalse(remember_project_name(self.vault, project))
        self.assertEqual(scope_labels(self.vault, [project["scope"]])[project["scope"]], "Unnamed project")

    def test_name_updates_do_not_rebind_and_are_bounded(self):
        project = self.project("Project")
        original = resolve_project(project["root"])["scope"]
        remember_project_name(self.vault, {**project, "name": "New display name"})
        self.assertEqual(resolve_project(project["root"])["scope"], original)
        remember_project_name(self.vault, {**project, "name": "é" * 300})
        self.assertEqual(len(scope_labels(self.vault, [original])[original]), 120)
        with closing(sqlite3.connect(self.vault.root / "runtime.sqlite")) as db, db:
            db.executemany("INSERT INTO project_names VALUES (?,?)", [(f"project:fixture-{i}", "Fixture") for i in range(1000)])
        remember_project_name(self.vault, {"scope": "project:last", "name": "Last"})
        with closing(sqlite3.connect(self.vault.root / "runtime.sqlite")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM project_names").fetchone()[0], 1000)

    def test_sensitive_names_are_omitted_and_html_remains_plain_data(self):
        project = self.project("Project")
        self.assertFalse(remember_project_name(self.vault, {**project, "name": "ghp_" + "a" * 36}))
        html = "<img src=x onerror=alert(1)>"
        self.assertTrue(remember_project_name(self.vault, {**project, "name": html}))
        self.assertEqual(scope_labels(self.vault, [project["scope"]])[project["scope"]], html)
