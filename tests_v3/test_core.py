from __future__ import annotations

import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ai_dememory.cli import _extract_globals, _parser, main
from ai_dememory.config import load_config, select_vault, set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.modules import create_module, disable_module, discover_modules
from ai_dememory.proposals import MAX_PROPOSAL_CONTENT_BYTES, ProposalStore
from ai_dememory.search import SearchIndex
from ai_dememory.vault import MAX_MEMORY_CONTENT_BYTES, MAX_TITLE_BYTES, Vault


class V3TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "config")},
            clear=False,
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(arguments))
        return code, stdout.getvalue(), stderr.getvalue()


class CoreFlowTests(V3TestCase):
    def test_double_dash_preserves_module_arguments_that_match_global_flags(self) -> None:
        argv = ["serve", "sample", "--", "--json", "--vault", "module-local"]
        clean, vault, json_output = _extract_globals(argv)
        self.assertEqual(clean, argv)
        self.assertIsNone(vault)
        self.assertFalse(json_output)
        parsed = _parser().parse_args(clean)
        self.assertEqual(parsed.module_args, ["--json", "--vault", "module-local"])

    def test_setup_remember_recall_and_status_from_any_directory(self) -> None:
        vault_path = self.root / "vault"
        code, output, error = self.run_cli("setup", str(vault_path), "--yes", "--json")
        self.assertEqual(code, 0, error)
        setup = json.loads(output)
        self.assertEqual(setup["background_processes"], 0)
        self.assertEqual(Path(load_config().default_vault), vault_path.resolve())

        code, output, error = self.run_cli(
            "remember", "El diseño modular debe seguir siendo útil.", "--title", "Principio modular", "--json"
        )
        self.assertEqual(code, 0, error)
        memory = json.loads(output)
        self.assertTrue(memory["memory_id"])

        unrelated = self.root / "somewhere-else"
        unrelated.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(unrelated)
            code, output, error = self.run_cli("recall", "diseño útil", "--json")
            self.assertEqual(code, 0, error)
        finally:
            os.chdir(previous)
        results = json.loads(output)["results"]
        self.assertEqual(results[0]["title"], "Principio modular")

        code, output, error = self.run_cli("status", "--json")
        self.assertEqual(code, 0, error)
        status = json.loads(output)
        self.assertEqual(status["memories"], 1)
        self.assertEqual(status["background_processes"], 0)
        self.assertEqual(status["model_calls"], 0)

    def test_explicit_vault_overrides_default(self) -> None:
        default = self.root / "default"
        alternate = self.root / "alternate"
        self.run_cli("setup", str(default), "--yes")
        Vault.create(alternate).remember("Alternate-only fact", "Alternate")
        code, output, error = self.run_cli(
            "recall", "Alternate-only", "--vault", str(alternate), "--json"
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["results"][0]["title"], "Alternate")

    def test_deleted_index_is_rebuilt_from_markdown(self) -> None:
        vault = Vault.create(self.root / "vault")
        vault.remember("La recuperación reconstruye el índice local.", "Reconstrucción")
        index = SearchIndex(vault)
        self.assertEqual(len(index.search("recuperación")), 1)
        index.path.unlink()
        for suffix in ("-shm", "-wal"):
            candidate = Path(str(index.path) + suffix)
            if candidate.exists():
                candidate.unlink()
        self.assertEqual(len(index.search("índice")), 1)

    def test_corrupt_generated_index_is_rebuilt(self) -> None:
        vault = Vault.create(self.root / "vault")
        vault.remember("El índice corrupto se puede descartar.", "Recovery")
        index = SearchIndex(vault)
        index.path.write_bytes(b"this is not sqlite")
        hits = index.search("corrupto")
        self.assertEqual([hit.title for hit in hits], ["Recovery"])

    def test_secret_like_canonical_write_is_rejected(self) -> None:
        vault = Vault.create(self.root / "vault")
        with self.assertRaisesRegex(ValueError, "secret material"):
            vault.remember("-----BEGIN PRIVATE KEY-----\nnot-real")

    def test_setup_refuses_non_empty_unrelated_directory(self) -> None:
        target = self.root / "existing-project"
        target.mkdir()
        (target / "important.txt").write_text("keep", encoding="utf-8")
        code, _, error = self.run_cli("setup", str(target), "--yes")
        self.assertEqual(code, 2)
        self.assertIn("non-empty directory", error)
        self.assertFalse((target / ".ai-dememory.toml").exists())

    def test_memory_size_is_bounded(self) -> None:
        vault = Vault.create(self.root / "vault")
        with self.assertRaisesRegex(ValueError, "content limit"):
            vault.remember("x" * (MAX_MEMORY_CONTENT_BYTES + 1))

    def test_setup_repairs_invalid_machine_config(self) -> None:
        config_file = self.root / "config" / "config.toml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("not valid toml = [", encoding="utf-8")
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        self.assertEqual(Path(load_config().default_vault), vault_path.resolve())

    def test_relative_default_vault_is_rejected_instead_of_using_cwd(self) -> None:
        config_file = self.root / "config" / "config.toml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text(
            'schema_version = 1\ndefault_vault = "relative/vault"\n\n[modules]\nenabled = []\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "absolute path"):
            load_config()

    def test_real_cli_json_output_preserves_unicode_on_windows_pipes(self) -> None:
        vault = Vault.create(self.root / "vault")
        ProposalStore(vault).propose("España 😀", "recuerdo útil")
        select_vault(vault.root)
        environment = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-m", "ai_dememory", "review", "list", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.root,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
        result = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(result["proposals"][0]["title"], "España 😀")

    def test_search_snippet_is_read_back_from_canonical_markdown(self) -> None:
        import sqlite3

        vault = Vault.create(self.root / "vault")
        vault.remember("Canonical body remains authoritative.", "Canonical title")
        index = SearchIndex(vault)
        index.sync()
        connection = sqlite3.connect(index.path)
        with connection:
            connection.execute("UPDATE memory_fts SET body = 'tampered generated text'")
        connection.close()
        hits = index.search("Canonical")
        self.assertEqual(len(hits), 1)
        self.assertIn("Canonical body", hits[0].snippet)
        self.assertNotIn("tampered", hits[0].snippet)

    def test_renamed_markdown_replaces_stale_index_path(self) -> None:
        vault = Vault.create(self.root / "vault")
        memory = vault.remember("Markdown can be organized after writing.", "Movable")
        index = SearchIndex(vault)
        index.sync()
        organized = vault.memories_dir / "organized.md"
        memory.path.rename(organized)
        hits = index.search("organized")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].path, organized.resolve())

    def test_invalid_utf8_markdown_returns_controlled_error(self) -> None:
        vault = Vault.create(self.root / "vault")
        (vault.memories_dir / "invalid.md").write_bytes(b"---\nid: bad\ntitle: bad\n---\n\xff")
        with self.assertRaisesRegex(ValueError, "Cannot read memory"):
            SearchIndex(vault).search("bad")

    def test_manually_edited_oversized_title_is_rejected_on_read(self) -> None:
        vault = Vault.create(self.root / "vault")
        title = "😀" * ((MAX_TITLE_BYTES // 4) + 1)
        (vault.memories_dir / "manual.md").write_text(
            "\n".join(
                (
                    "---",
                    'id: "0123456789abcdef0123456789abcdef"',
                    f"title: {json.dumps(title, ensure_ascii=False)}",
                    'created_at: "2026-09-01T00:00:00Z"',
                    "---",
                    "",
                    "manual content",
                )
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "title exceeds"):
            SearchIndex(vault).search("manual")

    def test_managed_directory_link_is_rejected(self) -> None:
        vault = Vault.create(self.root / "vault")
        external = self.root / "external"
        external.mkdir()
        memories = vault.memories_dir
        memories.rmdir()
        try:
            memories.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "managed directory"):
            vault.remember("Must remain inside the vault.", "Boundary")

    def test_generated_index_link_is_rejected_without_touching_target(self) -> None:
        vault = Vault.create(self.root / "vault")
        external = self.root / "external.sqlite"
        external.write_text("do not modify", encoding="utf-8")
        index = SearchIndex(vault)
        try:
            index.path.symlink_to(external)
        except OSError as exc:
            self.skipTest(f"file symlinks are unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            index.status()
        self.assertEqual(external.read_text(encoding="utf-8"), "do not modify")

    def test_nested_link_under_memories_is_rejected(self) -> None:
        vault = Vault.create(self.root / "vault")
        external = self.root / "external-memories"
        external.mkdir()
        (external / "outside.md").write_text("outside", encoding="utf-8")
        linked = vault.memories_dir / "linked"
        try:
            linked.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "Linked paths"):
            vault.memory_count()

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_nested_windows_junction_under_memories_is_rejected(self) -> None:
        vault = Vault.create(self.root / "vault")
        external = self.root / "junction-target"
        external.mkdir()
        linked = vault.memories_dir / "junction"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(linked), str(external)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if created.returncode != 0:
            self.skipTest(created.stderr.decode(errors="replace"))
        try:
            with self.assertRaisesRegex(ValueError, "Linked paths|escapes the vault"):
                vault.memory_count()
        finally:
            os.rmdir(linked)


class ReviewTests(V3TestCase):
    def test_proposal_content_and_store_count_are_bounded(self) -> None:
        vault = Vault.create(self.root / "vault")
        store = ProposalStore(vault)
        with self.assertRaisesRegex(ValueError, "content limit"):
            store.propose("Too large", "x" * (MAX_PROPOSAL_CONTENT_BYTES + 1))
        with patch("ai_dememory.proposals.MAX_PROPOSAL_FILES", 2):
            store.propose("First", "one")
            store.propose("Second", "two")
            with self.assertRaisesRegex(ValueError, "file limit"):
                store.propose("Third", "three")

    def test_oversized_unicode_title_is_rejected_before_writing(self) -> None:
        vault = Vault.create(self.root / "vault")
        title = "😀" * ((MAX_TITLE_BYTES // 4) + 1)
        with self.assertRaisesRegex(ValueError, "title exceeds"):
            ProposalStore(vault).propose(title, "bounded content")
        self.assertEqual(ProposalStore(vault).list(), [])

    def test_proposal_acceptance_is_idempotent_at_memory_boundary(self) -> None:
        vault = Vault.create(self.root / "vault")
        store = ProposalStore(vault)
        proposal = store.propose("A reviewed idea", "Only a person promotes this.")
        accepted, memory = store.decide(proposal.proposal_id[:8], accept=True)
        self.assertEqual(accepted.status, "accepted")
        self.assertIsNotNone(memory)
        self.assertEqual(vault.memory_count(), 1)
        with self.assertRaisesRegex(ValueError, "already accepted"):
            store.decide(proposal.proposal_id, accept=True)
        self.assertEqual(vault.memory_count(), 1)

    def test_context_never_exceeds_budget(self) -> None:
        vault = Vault.create(self.root / "vault")
        vault.remember("budget " + ("x" * 2000), "Long memory")
        result = CoreServices(vault).context("budget", max_chars=256)
        self.assertLessEqual(len(result["context"]), 256)


class ModuleTests(V3TestCase):
    def test_stale_enabled_module_can_be_disabled_after_uninstall(self) -> None:
        set_module_enabled("removed-module", True)
        disable_module("removed-module")
        self.assertNotIn("removed-module", load_config().enabled_modules)

    def test_discovery_does_not_import_disabled_builtin(self) -> None:
        previous = sys.modules.pop("ai_dememory.builtin_modules.mcp", None)
        try:
            modules = discover_modules()
            self.assertIn("mcp", modules)
            self.assertFalse(modules["mcp"].enabled)
            self.assertNotIn("ai_dememory.builtin_modules.mcp", sys.modules)
        finally:
            if previous is not None:
                sys.modules["ai_dememory.builtin_modules.mcp"] = previous

    def test_scaffold_is_installable_shape(self) -> None:
        target = create_module("sample", self.root / "sample-module")
        self.assertTrue((target / "pyproject.toml").is_file())
        self.assertTrue((target / "src" / "sample" / "__init__.py").is_file())
        self.assertIn('sample = "sample"', (target / "pyproject.toml").read_text(encoding="utf-8"))
        sys.path.insert(0, str(target / "src"))
        try:
            generated = importlib.import_module("sample")
            output = io.StringIO()
            with redirect_stdout(output):
                services = CoreServices(Vault.create(self.root / "module-vault"))
                self.assertEqual(generated.serve(services, []), 0)
            self.assertEqual(json.loads(output.getvalue())["module"], "sample")
        finally:
            sys.path.remove(str(target / "src"))
            sys.modules.pop("sample", None)


if __name__ == "__main__":
    unittest.main()
