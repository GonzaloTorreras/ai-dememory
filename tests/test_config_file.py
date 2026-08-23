from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import config_file  # noqa: E402
from config_file import CONFIG_NAME, MAX_CONFIG_BYTES, load_config, load_config_path  # noqa: E402
import onboarding  # noqa: E402
from onboarding import operational_setup_plan  # noqa: E402
from review_memory import (  # noqa: E402
    ReviewError,
    configure_review_mode,
    load_review_config,
    main as review_main,
)


def make_symlink_or_skip(test_case: unittest.TestCase, target: Path, link: Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:
        test_case.skipTest(f"symlink creation unavailable: {exc}")


class RootBoundConfigReadTests(unittest.TestCase):
    def test_regular_and_missing_configs_remain_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            (root / CONFIG_NAME).write_text(
                "[recall]\nenabled = true\ndefault_budget_tokens = 640\n",
                encoding="utf-8",
            )

            loaded = load_config(root)
            missing = load_config_path(root / "missing.toml", root=root)

        self.assertEqual(loaded["recall"]["enabled"], True)
        self.assertEqual(loaded["recall"]["default_budget_tokens"], 640)
        self.assertEqual(missing, {})

    def test_main_config_rejects_external_and_broken_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            outside = base / "outside.toml"
            outside.write_text("[recall]\nenabled = false\n", encoding="utf-8")
            config = root / CONFIG_NAME
            make_symlink_or_skip(self, outside, config)

            with self.assertRaisesRegex(ValueError, "config path must not contain symlinks"):
                load_config(root)

            config.unlink()
            make_symlink_or_skip(self, base / "missing.toml", config)
            with self.assertRaisesRegex(ValueError, "config path must not contain symlinks"):
                load_config(root)

    def test_direct_loader_rejects_an_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            outside = base / "outside.toml"
            outside.write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "config path must stay inside"):
                load_config_path(outside, root=root)

    def test_reader_rejects_an_oversized_or_invalid_utf8_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            config.write_bytes(b"#" * (MAX_CONFIG_BYTES + 1))

            with self.assertRaisesRegex(ValueError, "exceeds"):
                load_config(root)

            config.write_bytes(b"[recall]\nlabel = \xff\n")
            with self.assertRaisesRegex(ValueError, "valid UTF-8"):
                load_config(root)

    def test_reader_rejects_a_multiple_hard_link_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            outside = base / "outside.toml"
            outside.write_text("[recall]\nenabled = false\n", encoding="utf-8")
            config = root / CONFIG_NAME
            try:
                os.link(outside, config)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"hard-link creation unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "multiple hard links"):
                load_config(root)

    def test_reader_rejects_descriptor_substitution_portably(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            config.write_text("[recall]\nenabled = true\n", encoding="utf-8")
            outside = base / "outside.toml"
            outside.write_text("[recall]\nenabled = false\n", encoding="utf-8")
            original_open = os.open

            def open_outside(path: str | bytes | os.PathLike[str], flags: int, *args: object) -> int:
                if Path(path) == config:
                    return original_open(outside, flags, *args)
                return original_open(path, flags, *args)

            with patch("config_file.os.open", side_effect=open_outside):
                with self.assertRaisesRegex(ValueError, "changed while reading"):
                    load_config(root)

    def test_reader_rejects_a_file_without_stable_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            config.write_text("[recall]\nenabled = true\n", encoding="utf-8")
            zero_identity = os.stat_result((stat.S_IFREG | 0o600, 0, 1, 1, 0, 0, 0, 0, 0, 0))
            original_lstat = Path.lstat

            def lstat_without_identity(path: Path) -> os.stat_result:
                if path == config:
                    return zero_identity
                return original_lstat(path)

            with (
                patch("config_file.path_is_link_like", return_value=False),
                patch("pathlib.Path.lstat", new=lstat_without_identity),
            ):
                with self.assertRaisesRegex(ValueError, "no stable file identity"):
                    load_config(root)

    def test_reader_rejects_an_unknown_hard_link_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            config.write_text("[recall]\nenabled = true\n", encoding="utf-8")
            unknown_link_count = os.stat_result((stat.S_IFREG | 0o600, 1, 1, 0, 0, 0, 0, 0, 0, 0))
            original_lstat = Path.lstat

            def lstat_without_link_count(path: Path) -> os.stat_result:
                if path == config:
                    return unknown_link_count
                return original_lstat(path)

            with (
                patch("config_file.path_is_link_like", return_value=False),
                patch("pathlib.Path.lstat", new=lstat_without_link_count),
            ):
                with self.assertRaisesRegex(ValueError, "no stable hard-link count"):
                    load_config(root)

    def test_reader_reports_open_system_errors_as_invalid_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            (root / CONFIG_NAME).write_text("[recall]\nenabled = true\n", encoding="utf-8")

            with patch("config_file.os.open", side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(ValueError, "could not be opened safely"):
                    load_config(root)

    def test_review_state_config_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            state = root / "state" / "review.toml"
            state.parent.mkdir(parents=True)
            (root / CONFIG_NAME).write_text(
                "[false_positives]\nignore_file = \"state/review.toml\"\n",
                encoding="utf-8",
            )
            state.write_text("[false_positives.fp_safe]\nignored = true\n", encoding="utf-8")

            loaded = load_review_config(root)

        self.assertEqual(loaded["false_positives.fp_safe"]["ignored"], True)

    def test_review_state_rejects_an_external_configured_path_before_load(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            outside = base / "outside.toml"
            outside.write_text("[false_positives.fp_external]\nignored = true\n", encoding="utf-8")
            (root / CONFIG_NAME).write_text(
                f'[false_positives]\nignore_file = "{outside}"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReviewError, "review state path must stay inside"):
                load_review_config(root)

    def test_review_state_swap_after_open_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            state = root / "state" / "review.toml"
            state.parent.mkdir(parents=True)
            (root / CONFIG_NAME).write_text(
                "[false_positives]\nignore_file = \"state/review.toml\"\n",
                encoding="utf-8",
            )
            state.write_text("[false_positives.fp_safe]\nignored = true\n", encoding="utf-8")
            outside = base / "outside.toml"
            outside.write_text("[false_positives.fp_external]\nignored = false\n", encoding="utf-8")
            held_state = state.with_name("held-review.toml")
            original_open = os.open

            def swap_after_open(path: str | bytes | os.PathLike[str], flags: int, *args: object) -> int:
                descriptor = original_open(path, flags, *args)
                if Path(path) == state:
                    try:
                        state.replace(held_state)
                        os.symlink(outside, state)
                    except (OSError, NotImplementedError) as exc:
                        os.close(descriptor)
                        raise unittest.SkipTest(f"safe swap unavailable: {exc}") from exc
                return descriptor

            with patch("config_file.os.open", side_effect=swap_after_open):
                with self.assertRaisesRegex(ReviewError, "config path must not contain symlinks"):
                    load_review_config(root)

    def test_review_cli_reports_an_unsafe_main_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            outside = base / "outside.toml"
            outside.write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")
            make_symlink_or_skip(self, outside, root / CONFIG_NAME)
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = review_main(["--root", str(root), "review", "modes", "--json"])

        self.assertEqual(exit_code, 1)
        self.assertIn("config path must not contain symlinks", stderr.getvalue())

    def test_review_cli_reports_a_safe_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            (root / CONFIG_NAME).write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")
            stderr = io.StringIO()

            with (
                patch("review_memory.set_section", side_effect=ValueError("config path changed while reading")),
                redirect_stderr(stderr),
            ):
                exit_code = review_main(["--root", str(root), "review", "configure-mode", "--mode", "strict"])

        self.assertEqual(exit_code, 1)
        self.assertIn("config path changed while reading", stderr.getvalue())

    def test_review_cli_normalizes_a_safe_config_read_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            stderr = io.StringIO()

            with (
                patch("review_memory.load_config", side_effect=ValueError("config path must not contain symlinks")),
                redirect_stderr(stderr),
            ):
                exit_code = review_main(["--root", str(root), "review", "configure-mode", "--mode", "strict"])

        self.assertEqual(exit_code, 1)
        self.assertIn("config path must not contain symlinks", stderr.getvalue())

    def test_configure_review_mode_preserves_safe_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            (root / CONFIG_NAME).write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")

            with patch(
                "review_memory.set_section",
                side_effect=ValueError("config path changed while reading"),
            ):
                with self.assertRaisesRegex(ValueError, "config path changed while reading"):
                    configure_review_mode(root, "strict")

    def test_setup_plan_keeps_the_validated_config_fingerprint_after_a_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            original = b"[automation]\nintensity = \"minimal\"\n"
            config.write_bytes(original)
            outside = base / "outside.toml"
            outside.write_bytes(b"[automation]\nintensity = \"active\"\n")
            real_reader = config_file.read_config_bytes
            switched = False

            def read_then_swap(path: Path, *, root: Path) -> bytes | None:
                nonlocal switched
                content = real_reader(path, root=root)
                if Path(path) == config and not switched:
                    switched = True
                    try:
                        config.unlink()
                        os.symlink(outside, config)
                    except (OSError, NotImplementedError) as exc:
                        raise unittest.SkipTest(f"safe swap unavailable: {exc}") from exc
                return content

            with patch("onboarding.read_config_bytes", side_effect=read_then_swap):
                plan = operational_setup_plan(
                    root,
                    {
                        "clients": ["codex"],
                        "automation": {"intensity": "balanced", "model_policy": "off"},
                        "learning": {"session_proposals": False},
                    },
                )

        config_write = next(item for item in plan["writes"] if item["kind"] == "config")
        self.assertTrue(switched)
        self.assertEqual(config_write["current_sha256"], hashlib.sha256(original).hexdigest())

    def test_setup_apply_rejects_a_config_swap_after_target_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            config.write_text("[automation]\nintensity = \"minimal\"\n", encoding="utf-8")
            outside = base / "outside.toml"
            outside.write_text("[automation]\nintensity = \"active\"\n", encoding="utf-8")
            plan = operational_setup_plan(
                root,
                {
                    "clients": ["codex"],
                    "automation": {"intensity": "balanced", "model_policy": "off"},
                    "learning": {"session_proposals": False},
                },
                _include_payloads=True,
            )
            real_safe_target = onboarding.safe_target
            switched = False

            def target_then_swap(root_value: Path, relative_path: str) -> Path:
                nonlocal switched
                target = real_safe_target(root_value, relative_path)
                if relative_path == CONFIG_NAME and not switched:
                    switched = True
                    try:
                        config.unlink()
                        os.symlink(outside, config)
                    except (OSError, NotImplementedError) as exc:
                        raise unittest.SkipTest(f"safe swap unavailable: {exc}") from exc
                return target

            with patch("onboarding.safe_target", side_effect=target_then_swap):
                with self.assertRaisesRegex(ValueError, "config path must not contain symlinks"):
                    onboarding._apply_setup_plan(root, plan, str(plan["plan_sha256"]))

        self.assertTrue(switched)


if __name__ == "__main__":
    unittest.main()
