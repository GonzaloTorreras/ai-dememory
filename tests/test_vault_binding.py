from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ai_dememory_tool.cli import main as cli_main
from ai_dememory_tool.cli import run_packaged_command
from ai_dememory_tool.vault_binding import (
    MAX_DEFAULT_VAULT_SELECTOR_BYTES,
    VaultBindingError,
    clear_default_vault,
    default_vault_selector_path,
    load_default_vault,
    resolve_runtime_vault,
    save_default_vault,
)


def make_vault(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".ai-dememory.toml").write_text('[memory]\nschema_version = "2.0"\n', encoding="utf-8")
    return path


def isolated_env(config_home: Path, **extra: str) -> dict[str, str]:
    return {"AI_DEMEMORY_CONFIG_HOME": str(config_home), "AI_DEMEMORY_ROOT": "", **extra}


class RuntimeVaultBindingTests(unittest.TestCase):
    def test_precedence_is_argument_then_environment_then_saved_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            default = make_vault(base / "default")
            environment_root = base / "environment"
            explicit = base / "explicit"
            environment = isolated_env(base / "config", AI_DEMEMORY_ROOT=str(environment_root))
            save_default_vault(default, environ=environment)

            self.assertEqual(
                resolve_runtime_vault(str(explicit), environ=environment).root,
                explicit.resolve(),
            )
            environment_binding = resolve_runtime_vault(environ=environment)
            self.assertEqual(environment_binding.root, environment_root.resolve())
            self.assertEqual(environment_binding.source, "environment")

            default_binding = resolve_runtime_vault(
                environ=isolated_env(base / "config"),
            )
            self.assertEqual(default_binding.root, default.resolve())
            self.assertEqual(default_binding.source, "default")

    def test_save_writes_only_a_small_selector_and_loads_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")

            saved = save_default_vault(root, environ=environment)
            selector = default_vault_selector_path(environment)
            payload = json.loads(selector.read_text(encoding="utf-8"))

            self.assertEqual(saved.root, root.resolve())
            self.assertEqual(set(payload), {"schema_version", "root"})
            self.assertEqual(payload["root"], str(root.resolve()))
            self.assertFalse(list(selector.parent.glob(".default-vault-*.tmp")))
            self.assertEqual(load_default_vault(environ=environment), saved)
            self.assertNotIn("AI_DEMEMORY_ROOT", payload)

    def test_injected_environment_does_not_read_a_real_host_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            profile_environment = isolated_env(base / "profile-config")
            save_default_vault(root, environ=profile_environment)
            with patch.dict(os.environ, profile_environment, clear=False):
                with self.assertRaisesRegex(VaultBindingError, "runtime vault binding requires"):
                    resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": ""})

    def test_missing_blank_and_relative_bindings_fail_without_cwd_discovery(self) -> None:
        cases = (
            (None, {}, "runtime vault binding requires"),
            (None, {"AI_DEMEMORY_ROOT": ""}, "runtime vault binding requires"),
            (None, {"AI_DEMEMORY_ROOT": " \t"}, "AI_DEMEMORY_ROOT requires"),
            ("", {"AI_DEMEMORY_ROOT": "C:/vault"}, "--root requires"),
            ("./vault", {}, "--root requires an absolute"),
            (None, {"AI_DEMEMORY_ROOT": "relative-vault"}, "AI_DEMEMORY_ROOT requires an absolute"),
        )
        for explicit_root, environment, message in cases:
            with self.subTest(explicit_root=explicit_root, environment=environment):
                with self.assertRaisesRegex(VaultBindingError, message):
                    resolve_runtime_vault(explicit_root, environ=environment)

    def test_empty_process_environment_treats_the_default_as_unavailable(self) -> None:
        with patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}, clear=True):
            with self.assertRaisesRegex(VaultBindingError, "runtime vault binding requires"):
                resolve_runtime_vault()

    @unittest.skipUnless(os.name == "nt", "UNC paths are a Windows-only concern")
    def test_saved_default_and_selector_home_reject_unc_paths(self) -> None:
        with self.assertRaisesRegex(VaultBindingError, "local vault path"):
            save_default_vault(r"\\server\share\vault")
        with self.assertRaisesRegex(VaultBindingError, "local path"):
            default_vault_selector_path(
                {"AI_DEMEMORY_CONFIG_HOME": r"\\server\share\ai-dememory"}
            )

    def test_malformed_non_utf8_and_oversized_selectors_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")
            selector = default_vault_selector_path(environment)
            selector.parent.mkdir()
            cases = {
                "malformed": b"{}",
                "invalid_utf8": b"\xff",
                "oversized": b"x" * (MAX_DEFAULT_VAULT_SELECTOR_BYTES + 1),
                "relative_root": b'{"schema_version":1,"root":"relative"}',
            }
            for label, body in cases.items():
                with self.subTest(label=label):
                    selector.write_bytes(body)
                    with self.assertRaises(VaultBindingError):
                        load_default_vault(environ=environment)
            self.assertTrue(root.exists())

    def test_missing_selected_vault_config_fails_closed_but_clear_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")
            save_default_vault(root, environ=environment)
            (root / ".ai-dememory.toml").unlink()

            with self.assertRaisesRegex(VaultBindingError, "missing .ai-dememory.toml"):
                resolve_runtime_vault(environ=environment)
            self.assertTrue(clear_default_vault(environ=environment))
            self.assertIsNone(load_default_vault(environ=environment))

    def test_legacy_permissive_config_text_remains_a_valid_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")
            (root / ".ai-dememory.toml").write_text(
                "[memory]\nlabel = plain text\n",
                encoding="utf-8",
            )

            save_default_vault(root, environ=environment)
            self.assertEqual(resolve_runtime_vault(environ=environment).root, root.resolve())

    def test_nonregular_selector_is_never_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            environment = isolated_env(base / "config")
            selector = default_vault_selector_path(environment)
            selector.parent.mkdir()
            selector.mkdir()
            with self.assertRaisesRegex(VaultBindingError, "regular file"):
                load_default_vault(environ=environment)

    def test_hard_linked_selector_or_vault_config_is_never_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")
            selector = default_vault_selector_path(environment)
            selector.parent.mkdir()
            selector_source = base / "selector-source.json"
            selector_source.write_text(
                json.dumps({"schema_version": 1, "root": str(root.resolve())}),
                encoding="utf-8",
            )
            try:
                os.link(selector_source, selector)
            except OSError as exc:
                self.skipTest(f"hard-link creation unavailable: {exc}")
            with self.assertRaisesRegex(VaultBindingError, "multiple hard links"):
                load_default_vault(environ=environment)

            selector.unlink()
            config_link = base / "vault-config-link.toml"
            os.link(root / ".ai-dememory.toml", config_link)
            with self.assertRaisesRegex(VaultBindingError, "multiple hard links"):
                save_default_vault(root, environ=environment)

    def test_link_selector_is_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            environment = isolated_env(base / "config")
            selector = default_vault_selector_path(environment)
            selector.parent.mkdir()
            target = base / "target.json"
            target.write_text('{"schema_version":1,"root":"/tmp"}', encoding="utf-8")
            try:
                selector.symlink_to(target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(VaultBindingError, "regular file"):
                load_default_vault(environ=environment)

    def test_vault_cli_use_current_and_clear_are_explicit_and_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")
            with patch.dict(os.environ, environment, clear=False):
                use_output = io.StringIO()
                with redirect_stdout(use_output):
                    self.assertEqual(cli_main(["vault", "use", str(root), "--json"]), 0)
                current_output = io.StringIO()
                with redirect_stdout(current_output):
                    self.assertEqual(cli_main(["vault", "current", "--json"]), 0)
                clear_output = io.StringIO()
                with redirect_stdout(clear_output):
                    self.assertEqual(cli_main(["vault", "clear", "--json"]), 0)

            self.assertEqual(json.loads(use_output.getvalue())["root"], str(root.resolve()))
            self.assertTrue(json.loads(current_output.getvalue())["configured"])
            self.assertTrue(json.loads(clear_output.getvalue())["cleared"])
            self.assertFalse(default_vault_selector_path(environment).exists())

    def test_setup_wizard_uses_the_saved_default_without_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            environment = isolated_env(base / "config")
            save_default_vault(root, environ=environment)
            output = io.StringIO()
            answers = {
                "automation": {"intensity": "balanced", "model_policy": "off"},
                "learning": {"session_proposals": False},
            }
            with patch.dict(os.environ, environment, clear=False), redirect_stdout(output):
                self.assertEqual(
                    cli_main(
                        [
                            "setup",
                            "wizard",
                            "--input-json",
                            json.dumps(answers),
                            "--json",
                        ]
                    ),
                    0,
                )

        self.assertEqual(Path(json.loads(output.getvalue())["root"]), root.resolve())

    def test_global_root_argument_does_not_leak_from_an_in_process_cli_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=False), redirect_stdout(output):
                os.environ.pop("AI_DEMEMORY_ROOT", None)
                self.assertEqual(
                    cli_main(["--root", temporary, "version-check", "2.1.2"]),
                    0,
                )
                self.assertNotIn("AI_DEMEMORY_ROOT", os.environ)

        self.assertIn("ai-dememory 2.1.2", output.getvalue())

    def test_generic_commands_use_the_explicit_default_before_cwd_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            default = make_vault(base / "default")
            cwd_vault = make_vault(base / "cwd-vault")
            replacement = make_vault(base / "replacement")
            unrelated = base / "unrelated"
            unrelated.mkdir()
            (unrelated / "memories").mkdir()
            environment = isolated_env(base / "config")
            save_default_vault(default, environ=environment)
            observed: list[list[str]] = []
            fake_module = SimpleNamespace(main=lambda argv: observed.append(argv) or 0)
            previous = Path.cwd()
            try:
                with (
                    patch.dict(os.environ, environment, clear=False),
                    patch("ai_dememory_tool.cli.configure_imports"),
                    patch("ai_dememory_tool.cli.importlib.import_module", return_value=fake_module),
                ):
                    os.chdir(unrelated)
                    self.assertEqual(run_packaged_command("schedule", ["plan"]), 0)
                    clear_default_vault(environ=environment)
                    os.chdir(cwd_vault)
                    self.assertEqual(run_packaged_command("schedule", ["plan"]), 0)
                    os.chdir(unrelated)
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(cli_main(["vault", "use", str(replacement)]), 0)
                    self.assertEqual(run_packaged_command("schedule", ["plan"]), 0)
            finally:
                os.chdir(previous)

            self.assertEqual(observed[0][:2], ["--root", str(default.resolve())])
            self.assertEqual(observed[1][:2], ["--root", str(cwd_vault.resolve())])
            self.assertEqual(observed[2][:2], ["--root", str(replacement.resolve())])
