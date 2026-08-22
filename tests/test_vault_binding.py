from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ai_dememory_tool.vault_binding import VaultBindingError, resolve_runtime_vault


class RuntimeVaultBindingTests(unittest.TestCase):
    def test_explicit_root_wins_over_the_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            explicit_root = base / "explicit-vault"

            binding = resolve_runtime_vault(
                str(explicit_root),
                environ={"AI_DEMEMORY_ROOT": " \t"},
            )

        self.assertEqual(binding.root, explicit_root.resolve())
        self.assertEqual(binding.source, "argument")

    def test_environment_root_binds_when_no_argument_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            binding = resolve_runtime_vault(environ={"AI_DEMEMORY_ROOT": str(root)})

        self.assertEqual(binding.root, root.resolve())
        self.assertEqual(binding.source, "environment")

    def test_missing_or_blank_bindings_are_rejected_without_discovery(self) -> None:
        cases = (
            (None, {}, "runtime vault binding requires"),
            (None, {"AI_DEMEMORY_ROOT": ""}, "runtime vault binding requires"),
            (None, {"AI_DEMEMORY_ROOT": " \t"}, "AI_DEMEMORY_ROOT requires"),
            ("", {"AI_DEMEMORY_ROOT": "C:/vault"}, "--root requires"),
            (" \t", {"AI_DEMEMORY_ROOT": "C:/vault"}, "--root requires"),
        )
        for explicit_root, environment, message in cases:
            with self.subTest(explicit_root=explicit_root, environment=environment):
                with self.assertRaisesRegex(VaultBindingError, message):
                    resolve_runtime_vault(explicit_root, environ=environment)

