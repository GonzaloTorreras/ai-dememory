from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ai_dememory_tool.cli import main as cli_main
from ai_dememory_tool.cli import run_packaged_command
import ai_dememory_tool.vault_binding as vault_binding
from ai_dememory_tool.vault_binding import (
    MAX_DEFAULT_VAULT_SELECTOR_BYTES,
    MAX_VAULT_CONFIG_BYTES,
    VaultBindingError,
    clear_default_vault,
    default_vault_selector_path,
    load_default_vault,
    resolve_runtime_vault,
    save_default_vault,
)
from config_file import ConfigError, MAX_CONFIG_BYTES, load_config


def make_vault(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".ai-dememory.toml").write_text('[memory]\nschema_version = "2.0"\n', encoding="utf-8")
    return path


def isolated_env(config_home: Path, **extra: str) -> dict[str, str]:
    return {"AI_DEMEMORY_CONFIG_HOME": str(config_home), "AI_DEMEMORY_ROOT": "", **extra}


class RuntimeVaultBindingTests(unittest.TestCase):
    def test_structural_and_schema_config_limits_stay_aligned(self) -> None:
        self.assertEqual(MAX_VAULT_CONFIG_BYTES, MAX_CONFIG_BYTES)

    def test_precedence_is_argument_then_environment_then_saved_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            default = make_vault(base / "default")
            environment_root = make_vault(base / "environment")
            explicit = make_vault(base / "explicit")
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

    def test_relative_bindings_fail_before_any_filesystem_probe(self) -> None:
        with patch("pathlib.Path.lstat", side_effect=AssertionError("unexpected probe")):
            with self.assertRaisesRegex(VaultBindingError, "--root requires an absolute"):
                resolve_runtime_vault("relative-vault", environ={})
            with self.assertRaisesRegex(VaultBindingError, "AI_DEMEMORY_ROOT requires an absolute"):
                resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": "relative-vault"})

    def test_selected_source_fails_closed_without_falling_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            default = make_vault(base / "default")
            environment_root = make_vault(base / "environment")
            environment = isolated_env(
                base / "config",
                AI_DEMEMORY_ROOT=str(environment_root),
            )
            save_default_vault(default, environ=environment)

            missing_explicit = base / "missing-explicit"
            with self.assertRaisesRegex(VaultBindingError, "--root vault directory does not exist"):
                resolve_runtime_vault(str(missing_explicit), environ=environment)

            missing_environment = base / "missing-environment"
            default_only = isolated_env(
                base / "config",
                AI_DEMEMORY_ROOT=str(missing_environment),
            )
            with self.assertRaisesRegex(
                VaultBindingError,
                "AI_DEMEMORY_ROOT vault directory does not exist",
            ):
                resolve_runtime_vault(environ=default_only)

    def test_every_source_requires_an_existing_initialized_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            config_home = base / "config"
            file_root = base / "file-root"
            file_root.write_text("not a directory", encoding="utf-8")
            uninitialized = base / "uninitialized"
            uninitialized.mkdir()
            default_environment = isolated_env(config_home)
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            selector.write_text(
                json.dumps({"schema_version": 1, "root": str(uninitialized)}),
                encoding="utf-8",
            )

            cases = (
                (
                    "explicit-file",
                    lambda: resolve_runtime_vault(str(file_root), environ={}),
                    "--root vault must be a real directory",
                ),
                (
                    "explicit-uninitialized",
                    lambda: resolve_runtime_vault(str(uninitialized), environ={}),
                    "--root vault is missing .ai-dememory.toml",
                ),
                (
                    "environment-file",
                    lambda: resolve_runtime_vault(
                        environ={"AI_DEMEMORY_ROOT": str(file_root)}
                    ),
                    "AI_DEMEMORY_ROOT vault must be a real directory",
                ),
                (
                    "environment-uninitialized",
                    lambda: resolve_runtime_vault(
                        environ={"AI_DEMEMORY_ROOT": str(uninitialized)}
                    ),
                    "AI_DEMEMORY_ROOT vault is missing .ai-dememory.toml",
                ),
                (
                    "default-uninitialized",
                    lambda: resolve_runtime_vault(environ=default_environment),
                    "default vault is missing .ai-dememory.toml",
                ),
            )
            for label, invoke, message in cases:
                with self.subTest(label=label):
                    with self.assertRaisesRegex(VaultBindingError, message):
                        invoke()

    def test_saved_default_rejects_missing_and_nondirectory_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            default_environment = isolated_env(base / "config")
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            file_root = base / "file-root"
            file_root.write_text("not a directory", encoding="utf-8")
            for label, selected_root, message in (
                ("missing", base / "missing", "default vault directory does not exist"),
                ("file", file_root, "default vault must be a real directory"),
            ):
                with self.subTest(label=label):
                    selector.write_text(
                        json.dumps({"schema_version": 1, "root": str(selected_root)}),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(VaultBindingError, message):
                        resolve_runtime_vault(environ=default_environment)

    def test_explicit_and_environment_bindings_do_not_consult_the_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            explicit = make_vault(base / "explicit")
            environment_root = make_vault(base / "environment")
            with patch(
                "ai_dememory_tool.vault_binding._selector_path",
                side_effect=AssertionError("selector lookup must not occur"),
            ):
                explicit_binding = resolve_runtime_vault(
                    str(explicit),
                    environ={"AI_DEMEMORY_ROOT": str(environment_root)},
                )
                environment_binding = resolve_runtime_vault(
                    environ={"AI_DEMEMORY_ROOT": str(environment_root)}
                )

            self.assertEqual(explicit_binding.source, "argument")
            self.assertEqual(explicit_binding.root, explicit.resolve())
            self.assertEqual(environment_binding.source, "environment")
            self.assertEqual(environment_binding.root, environment_root.resolve())

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

    def test_selector_is_parser_agnostic_but_downstream_config_load_can_fail(self) -> None:
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
            with self.assertRaises(ConfigError) as raised:
                load_config(root)

        self.assertEqual(raised.exception.code, "toml_syntax")
        self.assertNotIn("plain text", str(raised.exception))

    def test_canonical_ancestor_alias_is_accepted_for_every_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            real_parent = base / "real-parent"
            root = make_vault(real_parent / "vault")
            alias = base / "alias"
            try:
                alias.symlink_to(real_parent, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlink creation unavailable: {exc}")
            aliased_root = alias / "vault"
            environment = isolated_env(
                base / "config",
                AI_DEMEMORY_ROOT=str(aliased_root),
            )

            explicit = resolve_runtime_vault(str(aliased_root), environ=environment)
            selected = save_default_vault(aliased_root, environ=environment)
            environment_binding = resolve_runtime_vault(environ=environment)
            default_binding = resolve_runtime_vault(environ=isolated_env(base / "config"))

            self.assertEqual(explicit.root, root.resolve())
            self.assertEqual(environment_binding.root, root.resolve())
            self.assertEqual(selected.root, root.resolve())
            self.assertEqual(default_binding.root, root.resolve())

    def test_linked_final_root_is_rejected_for_every_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = make_vault(base / "target")
            linked_root = base / "linked-vault"
            try:
                linked_root.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlink creation unavailable: {exc}")
            default_environment = isolated_env(base / "config")
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            selector.write_text(
                json.dumps({"schema_version": 1, "root": str(linked_root)}),
                encoding="utf-8",
            )

            cases = (
                ("explicit", lambda: resolve_runtime_vault(str(linked_root), environ={})),
                (
                    "environment",
                    lambda: resolve_runtime_vault(
                        environ={"AI_DEMEMORY_ROOT": str(linked_root)}
                    ),
                ),
                ("default", lambda: resolve_runtime_vault(environ=default_environment)),
            )
            for label, invoke in cases:
                with self.subTest(label=label):
                    with self.assertRaisesRegex(VaultBindingError, "must be a real directory"):
                        invoke()

    def test_junction_like_final_root_metadata_is_rejected_portably(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_vault(Path(temporary) / "vault")
            actual = root.lstat()
            junction_like = SimpleNamespace(
                st_mode=actual.st_mode,
                st_ino=actual.st_ino,
                st_dev=actual.st_dev,
                st_nlink=actual.st_nlink,
                st_size=actual.st_size,
                st_mtime_ns=actual.st_mtime_ns,
                st_ctime_ns=actual.st_ctime_ns,
                st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
            )
            original_lstat = Path.lstat

            def lstat_as_junction(path: Path) -> os.stat_result:
                if path == root:
                    return junction_like  # type: ignore[return-value]
                return original_lstat(path)

            with patch("pathlib.Path.lstat", new=lstat_as_junction):
                with self.assertRaisesRegex(VaultBindingError, "must be a real directory"):
                    resolve_runtime_vault(str(root), environ={})

    def test_linked_config_is_rejected_for_every_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            config = root / ".ai-dememory.toml"
            config.unlink()
            target = base / "target.toml"
            target.write_text('[memory]\nschema_version = "2.0"\n', encoding="utf-8")
            try:
                config.symlink_to(target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"file symlink creation unavailable: {exc}")
            default_environment = isolated_env(base / "config")
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            selector.write_text(
                json.dumps({"schema_version": 1, "root": str(root)}),
                encoding="utf-8",
            )

            cases = (
                ("explicit", lambda: resolve_runtime_vault(str(root), environ={})),
                (
                    "environment",
                    lambda: resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": str(root)}),
                ),
                ("default", lambda: resolve_runtime_vault(environ=default_environment)),
            )
            for label, invoke in cases:
                with self.subTest(label=label):
                    with self.assertRaisesRegex(VaultBindingError, "must be a regular file"):
                        invoke()

    def test_directory_without_stable_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_vault(Path(temporary) / "vault")
            actual = root.lstat()
            no_identity = os.stat_result(
                (
                    actual.st_mode,
                    0,
                    actual.st_dev,
                    actual.st_nlink,
                    actual.st_uid,
                    actual.st_gid,
                    actual.st_size,
                    actual.st_atime,
                    actual.st_mtime,
                    actual.st_ctime,
                )
            )
            original_lstat = Path.lstat

            def lstat_without_identity(path: Path) -> os.stat_result:
                if path == root:
                    return no_identity
                return original_lstat(path)

            with patch("pathlib.Path.lstat", new=lstat_without_identity):
                with self.assertRaisesRegex(VaultBindingError, "no stable directory identity"):
                    resolve_runtime_vault(str(root), environ={})

    def test_config_without_stable_identity_is_rejected_for_every_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            config = root / ".ai-dememory.toml"
            actual = config.lstat()
            no_identity = os.stat_result(
                (
                    actual.st_mode,
                    0,
                    actual.st_dev,
                    actual.st_nlink,
                    actual.st_uid,
                    actual.st_gid,
                    actual.st_size,
                    actual.st_atime,
                    actual.st_mtime,
                    actual.st_ctime,
                )
            )
            default_environment = isolated_env(base / "config")
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            selector.write_text(
                json.dumps({"schema_version": 1, "root": str(root)}),
                encoding="utf-8",
            )
            original_lstat = Path.lstat

            def lstat_without_identity(path: Path) -> os.stat_result:
                if path == config:
                    return no_identity
                return original_lstat(path)

            cases = (
                ("explicit", lambda: resolve_runtime_vault(str(root), environ={})),
                (
                    "environment",
                    lambda: resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": str(root)}),
                ),
                ("default", lambda: resolve_runtime_vault(environ=default_environment)),
            )
            with patch("pathlib.Path.lstat", new=lstat_without_identity):
                for label, invoke in cases:
                    with self.subTest(label=label):
                        with self.assertRaisesRegex(VaultBindingError, "no stable file identity"):
                            invoke()

    def test_oversized_config_is_rejected_for_every_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            (root / ".ai-dememory.toml").write_bytes(b"x" * (MAX_VAULT_CONFIG_BYTES + 1))
            default_environment = isolated_env(base / "config")
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            selector.write_text(
                json.dumps({"schema_version": 1, "root": str(root)}),
                encoding="utf-8",
            )
            cases = (
                ("explicit", lambda: resolve_runtime_vault(str(root), environ={})),
                (
                    "environment",
                    lambda: resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": str(root)}),
                ),
                ("default", lambda: resolve_runtime_vault(environ=default_environment)),
            )
            for label, invoke in cases:
                with self.subTest(label=label):
                    with self.assertRaisesRegex(VaultBindingError, "exceeds its byte limit"):
                        invoke()

    def test_root_swap_during_config_read_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            displaced = base / "displaced-vault"
            original_read_regular = vault_binding._read_regular

            def read_then_swap(path: Path, *, limit: int, label: str) -> bytes:
                body = original_read_regular(path, limit=limit, label=label)
                root.rename(displaced)
                make_vault(root)
                return body

            with patch(
                "ai_dememory_tool.vault_binding._read_regular",
                side_effect=read_then_swap,
            ):
                with self.assertRaisesRegex(VaultBindingError, "changed during validation"):
                    resolve_runtime_vault(str(root), environ={})

    def test_same_inode_same_size_config_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_vault(Path(temporary) / "vault")
            config = root / ".ai-dememory.toml"
            original_body = config.read_bytes()
            replacement_body = original_body.replace(b'"2.0"', b'"9.9"')
            self.assertEqual(len(original_body), len(replacement_body))
            original_read = os.read
            changed = False

            def read_then_mutate(descriptor: int, size: int) -> bytes:
                nonlocal changed
                chunk = original_read(descriptor, size)
                if chunk and not changed:
                    changed = True
                    before = config.stat()
                    config.write_bytes(replacement_body)
                    os.utime(
                        config,
                        ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000),
                    )
                return chunk

            with patch("ai_dememory_tool.vault_binding.os.read", side_effect=read_then_mutate):
                with self.assertRaisesRegex(VaultBindingError, "changed during access"):
                    resolve_runtime_vault(str(root), environ={})

    def test_descriptor_substitution_for_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = make_vault(base / "vault")
            config = root / ".ai-dememory.toml"
            outside = base / "outside.toml"
            outside.write_bytes(config.read_bytes())
            original_open = os.open

            def open_outside(
                path: str | bytes | os.PathLike[str],
                flags: int,
                *args: object,
            ) -> int:
                if Path(path) == config:
                    return original_open(outside, flags, *args)
                return original_open(path, flags, *args)

            with patch("ai_dememory_tool.vault_binding.os.open", side_effect=open_outside):
                with self.assertRaisesRegex(VaultBindingError, "changed during access"):
                    resolve_runtime_vault(str(root), environ={})

    def test_structural_errors_do_not_disclose_selected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path_canary = "vault-path-canary-48291"
            missing = base / path_canary
            default_environment = isolated_env(base / "config")
            selector = default_vault_selector_path(default_environment)
            selector.parent.mkdir(parents=True)
            selector.write_text(
                json.dumps({"schema_version": 1, "root": str(missing)}),
                encoding="utf-8",
            )
            for label, invoke in (
                ("explicit", lambda: resolve_runtime_vault(str(missing), environ={})),
                (
                    "environment",
                    lambda: resolve_runtime_vault(
                        environ={"AI_DEMEMORY_ROOT": str(missing)}
                    ),
                ),
                ("default", lambda: resolve_runtime_vault(environ=default_environment)),
            ):
                with self.subTest(label=label):
                    with self.assertRaises(VaultBindingError) as raised:
                        invoke()
                    self.assertNotIn(path_canary, str(raised.exception))
                    self.assertNotIn(str(base), str(raised.exception))

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
            with self.assertRaisesRegex(VaultBindingError, "multiple hard links"):
                resolve_runtime_vault(str(root), environ={})
            with self.assertRaisesRegex(VaultBindingError, "multiple hard links"):
                resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": str(root)})

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
                    self.assertEqual(run_packaged_command("search", ["fixture"]), 0)
                    clear_default_vault(environ=environment)
                    os.chdir(cwd_vault)
                    self.assertEqual(run_packaged_command("search", ["fixture"]), 0)
                    os.chdir(unrelated)
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(cli_main(["vault", "use", str(replacement)]), 0)
                    self.assertEqual(run_packaged_command("search", ["fixture"]), 0)
            finally:
                os.chdir(previous)

            self.assertEqual(observed[0][:2], ["--root", str(default.resolve())])
            self.assertEqual(observed[1][:2], ["--root", str(cwd_vault.resolve())])
            self.assertEqual(observed[2][:2], ["--root", str(replacement.resolve())])
