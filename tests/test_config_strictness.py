from __future__ import annotations

import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from config_file import (  # noqa: E402
    CONFIG_NAME,
    CONFIG_WRITE_LOCK_NAME,
    ConfigError,
    config_write_lock,
    load_config_path,
    parse_config_text,
    read_config_bytes,
    set_section,
    set_section_path,
    vault_operation_lock,
)
import review_memory  # noqa: E402
from review_memory import ReviewError  # noqa: E402


class StrictMainConfigTests(unittest.TestCase):
    def test_checked_in_template_parses_to_flat_sections(self) -> None:
        parsed = parse_config_text(
            (ROOT / "vault-template" / CONFIG_NAME).read_text(encoding="utf-8")
        )

        self.assertEqual(parsed["memory"]["schema_version"], "2.0")
        self.assertEqual(parsed["recall"]["clients"], ["codex", "claude"])
        self.assertEqual(parsed["providers.codex"]["capture_raw"], False)
        self.assertNotIn("providers", parsed)

    def test_missing_empty_and_partial_configs_are_supported(self) -> None:
        self.assertEqual(parse_config_text(""), {})
        self.assertEqual(parse_config_text("# intentionally empty\n"), {})
        self.assertEqual(parse_config_text("[recall]\n"), {"recall": {}})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(load_config_path(root / "missing.toml", root=root), {})

    def test_all_current_provider_names_are_allowed_but_unknown_names_are_not(self) -> None:
        text = "".join(
            f"[providers.{name}]\nenabled = false\n"
            for name in ("codex", "claude", "chatgpt", "cursor", "windsurf")
        )
        parsed = parse_config_text(text)
        self.assertEqual(len(parsed), 5)

        with self.assertRaises(ConfigError) as raised:
            parse_config_text("[providers.unlisted]\nenabled = false\n")
        self.assertEqual(raised.exception.code, "unknown_provider")
        self.assertEqual(raised.exception.field, "providers.<unknown>")

    def test_top_level_keys_unknown_sections_subsections_and_keys_are_rejected(self) -> None:
        cases = (
            ("version = 1\n", "top_level_key", "<unknown>"),
            ("[unknown]\nenabled = true\n", "unknown_section", "<unknown>"),
            ("[recall.extra]\nenabled = true\n", "unknown_subsection", "recall.<unknown>"),
            ("[recall]\nunexpected = true\n", "unknown_key", "recall.<unknown>"),
        )
        for text, code, field in cases:
            with self.subTest(code=code):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.field, field)
                self.assertIsNotNone(raised.exception.line)
                self.assertIsNotNone(raised.exception.column)

    def test_unknown_diagnostic_fields_never_reflect_quoted_or_multiline_keys(self) -> None:
        key_canary = "DO_NOT_ECHO_UNKNOWN_CONFIG_KEY"
        forged_line = "FORGED_CONFIG_DIAGNOSTIC_LINE"
        cases = (
            (
                f'[review]\n"{key_canary}\\n{forged_line}" = true\n',
                "main",
                "review.<unknown>",
            ),
            (
                f'[providers."{key_canary}\\n{forged_line}"]\nenabled = true\n',
                "main",
                "providers.<unknown>",
            ),
            (
                f'[false_positives."{key_canary}\\n{forged_line}"]\nignored = true\n',
                "review_state",
                "false_positives.<unsafe-id>",
            ),
        )
        for text, config_kind, expected_field in cases:
            with self.subTest(config_kind=config_kind, expected_field=expected_field):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text, config_kind=config_kind)
                self.assertEqual(raised.exception.field, expected_field)
                self.assertNotIn(key_canary, str(raised.exception))
                self.assertNotIn(forged_line, str(raised.exception))
                self.assertNotIn("\n", str(raised.exception))

    def test_structural_types_are_exact_and_arrays_contain_only_strings(self) -> None:
        cases = (
            ("[recall]\nenabled = 1\n", "recall.enabled"),
            ("[recall]\ndefault_budget_tokens = true\n", "recall.default_budget_tokens"),
            ("[recall]\nclients = [\"codex\", 1]\n", "recall.clients"),
            ("[review]\nupdated_at = 2026-08-26\n", "review.updated_at"),
        )
        for text, field in cases:
            with self.subTest(field=field):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text)
                self.assertEqual(raised.exception.code, "invalid_type")
                self.assertEqual(raised.exception.field, field)

    def test_finite_numbers_are_accepted_and_non_finite_numbers_are_rejected(self) -> None:
        parsed = parse_config_text("[recall]\nmin_relevance_score = 0.25\n")
        self.assertEqual(parsed["recall"]["min_relevance_score"], 0.25)

        for value in ("inf", "+inf", "-inf", "nan"):
            with self.subTest(value=value):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(f"[recall]\nmin_relevance_score = {value}\n")
                self.assertEqual(raised.exception.code, "non_finite_number")
                self.assertTrue(math.isfinite(0.0))

    def test_syntax_and_duplicate_diagnostics_redact_raw_values(self) -> None:
        redaction_canary = "do-not-echo-this-value"
        with self.assertRaises(ConfigError) as syntax:
            parse_config_text(
                f"[review]\nreviewer = {redaction_canary}\n",
                source="fixture.toml",
            )
        self.assertEqual(syntax.exception.code, "toml_syntax")
        self.assertEqual(syntax.exception.source, "fixture.toml")
        self.assertNotIn(redaction_canary, str(syntax.exception))

        with self.assertRaises(ConfigError) as duplicate:
            parse_config_text("[recall]\nenabled = true\nenabled = false\n")
        self.assertEqual(duplicate.exception.code, "duplicate_definition")
        self.assertIsNotNone(duplicate.exception.line)
        self.assertNotIn("true", str(duplicate.exception))
        self.assertNotIn("false", str(duplicate.exception))


class StrictReviewStateTests(unittest.TestCase):
    def test_review_state_accepts_known_record_and_recommendation_fields(self) -> None:
        parsed = parse_config_text(
            """
[false_positives.fp_0123456789abcdef]
ignored = true
reason = "reviewed"
reviewer = "Unit Test"
reviewed_at = "2026-08-26"
review_after = "2026-11-24"
recommendation_id = "rec_safe"
recommendation_path = "inbox/recommendation.md"
recommendation_action = "ignore_false_positive"
recommendation_policy_violation = false

[conflicts.conf_fedcba9876543210]
status = "resolved"
decision = "keep:mem_one"
proposal_path = "inbox/conflict-resolution/proposal.md"
reviewer = "Unit Test"
reviewed_at = "2026-08-26"
""",
            config_kind="review_state",
        )

        self.assertTrue(parsed["false_positives.fp_0123456789abcdef"]["ignored"])
        self.assertEqual(parsed["conflicts.conf_fedcba9876543210"]["status"], "resolved")

    def test_review_state_rejects_dotted_or_unsafe_ids(self) -> None:
        for header in (
            '[false_positives."fp.dotted"]',
            '[false_positives."../escape"]',
            "[false_positives.fp_safe]",
            '[conflicts."conf space"]',
            "[conflicts.conf_123]",
        ):
            with self.subTest(header=header):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(
                        f"{header}\nreviewer = \"Unit Test\"\n",
                        config_kind="review_state",
                    )
                self.assertEqual(raised.exception.code, "unsafe_identifier")

    def test_review_state_rejects_unknown_namespaces_fields_and_types(self) -> None:
        cases = (
            ("[other.id]\nreviewer = \"x\"\n", "unknown_section"),
            ("[false_positives.fp_0123456789abcdef]\nunexpected = \"x\"\n", "unknown_key"),
            ("[conflicts.conf_fedcba9876543210]\nstatus = false\n", "invalid_type"),
        )
        for text, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ConfigError) as raised:
                    parse_config_text(text, config_kind="review_state")
                self.assertEqual(raised.exception.code, code)


class StrictConfigWriterTests(unittest.TestCase):
    def test_writer_validates_existing_and_candidate_before_atomic_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            original = "[recall]\nunexpected = true\n"
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ConfigError) as existing_error:
                set_section(root, "review", {"mode": "strict"})
            self.assertEqual(existing_error.exception.code, "unknown_key")
            self.assertEqual(path.read_text(encoding="utf-8"), original)

            path.write_text("[review]\nmode = \"strict\"\n", encoding="utf-8")
            before_candidate = path.read_text(encoding="utf-8")
            with self.assertRaises(ConfigError) as candidate_error:
                set_section(root, "review", {"unknown": "value"})
            self.assertEqual(candidate_error.exception.code, "unknown_key")
            self.assertEqual(path.read_text(encoding="utf-8"), before_candidate)

    def test_writer_escapes_strings_and_reparses_the_candidate(self) -> None:
        reviewer = 'line one\nline two with "quotes" and \\slashes'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            set_section(root, "review", {"reviewer": reviewer, "mode": "strict"})
            loaded = load_config_path(root / CONFIG_NAME, root=root)

        self.assertEqual(loaded["review"]["reviewer"], reviewer)

    def test_writer_rejects_unencodable_strings_without_creating_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME

            with self.assertRaises(ConfigError) as raised:
                set_section(
                    root,
                    "review",
                    {"reviewer": "\ud800private-canary", "mode": "strict"},
                )

            self.assertEqual(raised.exception.code, "config_encoding_error")
            self.assertNotIn("private-canary", str(raised.exception))
            self.assertFalse(path.exists())

    def test_writer_preserves_multiline_string_with_header_like_line(self) -> None:
        original = (
            '[review]\nreviewer = """Line one\n[recall]\nLine three"""\n'
            'mode = "strict"\n'
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ConfigError):
                set_section(root, "review", {"reviewer": "Unit Test", "mode": "strict"})

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_writer_refuses_equivalent_header_spelling_it_cannot_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            original = '["review"]\nmode = "strict"\n'
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(ConfigError) as raised:
                set_section(root, "review", {"mode": "advisory"})

            self.assertEqual(raised.exception.code, "unsupported_header_spelling")
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_writer_stops_at_any_valid_following_table_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / CONFIG_NAME
            path.write_text(
                '[review]\nmode = "strict"\n\n["recall"] # preserved\nenabled = true\n',
                encoding="utf-8",
            )

            set_section(root, "review", {"mode": "advisory"})
            updated = path.read_text(encoding="utf-8")

        self.assertIn('["recall"] # preserved\nenabled = true', updated)
        self.assertEqual(parse_config_text(updated)["review"]["mode"], "advisory")

    def test_review_state_writer_requires_its_explicit_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".ai-dememory-ignore.toml"
            set_section_path(
                path,
                "false_positives.fp_0123456789abcdef",
                {"ignored": True, "reviewer": "Unit Test"},
                root=root,
                config_kind="review_state",
            )
            loaded = load_config_path(path, root=root, config_kind="review_state")

        self.assertTrue(loaded["false_positives.fp_0123456789abcdef"]["ignored"])

    def test_concurrent_product_writers_preserve_updates_to_different_sections(self) -> None:
        import config_file

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_entered = threading.Event()
            release_first = threading.Event()
            failures: list[BaseException] = []
            real_write = config_file.safe_write_text

            def delayed_first_write(*args: object, **kwargs: object) -> Path:
                if not first_entered.is_set():
                    first_entered.set()
                    if not release_first.wait(timeout=5):
                        raise TimeoutError("test writer release timed out")
                return real_write(*args, **kwargs)  # type: ignore[arg-type]

            def write_section(section: str, values: dict[str, object]) -> None:
                try:
                    set_section(root, section, values)
                except BaseException as exc:  # pragma: no cover - asserted below
                    failures.append(exc)

            with patch("config_file.safe_write_text", side_effect=delayed_first_write):
                first = threading.Thread(
                    target=write_section,
                    args=("review", {"mode": "strict"}),
                    daemon=True,
                )
                second = threading.Thread(
                    target=write_section,
                    args=("recall", {"enabled": False}),
                    daemon=True,
                )
                first.start()
                self.assertTrue(first_entered.wait(timeout=5))
                second.start()
                time.sleep(0.05)
                self.assertTrue(second.is_alive())
                release_first.set()
                first.join(timeout=5)
                second.join(timeout=5)

            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(failures, [])
            loaded = load_config_path(root / CONFIG_NAME, root=root)
            self.assertEqual(loaded["review"]["mode"], "strict")
            self.assertIs(loaded["recall"]["enabled"], False)

    def test_first_config_creation_never_exposes_partial_authoritative_bytes(self) -> None:
        import config_file

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / CONFIG_NAME
            staged_partial = threading.Event()
            release_stage = threading.Event()
            failures: list[BaseException] = []
            real_write = config_file.safe_write_text

            def paused_temp_write(
                path: Path,
                text: str,
                **kwargs: object,
            ) -> Path:
                if ".ai-dememory-config-" in path.name:
                    path.write_bytes(text.encode("utf-8")[:8])
                    staged_partial.set()
                    if not release_stage.wait(timeout=5):
                        raise TimeoutError("test config stage release timed out")
                    path.write_text(text, encoding="utf-8", newline="\n")
                    return path
                return real_write(path, text, **kwargs)  # type: ignore[arg-type]

            def create_config() -> None:
                try:
                    set_section(root, "review", {"mode": "strict"})
                except BaseException as exc:  # pragma: no cover - asserted below
                    failures.append(exc)

            with patch("config_file.safe_write_text", side_effect=paused_temp_write):
                writer = threading.Thread(target=create_config, daemon=True)
                writer.start()
                self.assertTrue(staged_partial.wait(timeout=5))
                self.assertIsNone(read_config_bytes(target, root=root))
                self.assertFalse(target.exists())
                release_stage.set()
                writer.join(timeout=5)

            self.assertFalse(writer.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(
                load_config_path(target, root=root)["review"]["mode"],
                "strict",
            )

    def test_keyboard_interrupt_after_real_replace_is_committed_success(self) -> None:
        import config_file

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / CONFIG_NAME
            set_section(root, "review", {"mode": "strict"})
            real_replace = config_file.os.replace
            interrupted = False

            def replace_then_interrupt(source: object, destination: object) -> None:
                nonlocal interrupted
                real_replace(source, destination)  # type: ignore[arg-type]
                if Path(destination) == target and not interrupted:
                    interrupted = True
                    raise KeyboardInterrupt

            with patch("config_file.os.replace", side_effect=replace_then_interrupt):
                result = set_section(root, "review", {"mode": "advisory"})

            self.assertTrue(interrupted)
            self.assertEqual(result, target)
            self.assertEqual(
                load_config_path(target, root=root)["review"]["mode"],
                "advisory",
            )
            self.assertEqual(list(root.glob(".*.ai-dememory-config-*.tmp")), [])

            set_section(root, "recall", {"enabled": False})
            self.assertIs(load_config_path(target, root=root)["recall"]["enabled"], False)

    def test_keyboard_interrupt_before_replace_preserves_exact_previous_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / CONFIG_NAME
            set_section(root, "review", {"mode": "strict"})
            previous_bytes = target.read_bytes()

            with patch("config_file.os.replace", side_effect=KeyboardInterrupt), self.assertRaises(
                KeyboardInterrupt
            ):
                set_section(root, "review", {"mode": "advisory"})

            self.assertEqual(target.read_bytes(), previous_bytes)
            self.assertEqual(list(root.glob(".*.ai-dememory-config-*.tmp")), [])
            set_section(root, "recall", {"enabled": False})
            self.assertIs(load_config_path(target, root=root)["recall"]["enabled"], False)

    def test_signal_during_lock_cleanup_releases_every_resource_and_commits(self) -> None:
        import config_file

        for phase in ("unlock", "close", "release", "registry"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / CONFIG_NAME
                set_section(root, "review", {"mode": "strict"})
                previous_handler = signal.getsignal(signal.SIGINT)
                real_unlock = config_file._unlock_config_fd
                real_close = config_file.os.close
                real_release = config_file._release_config_thread_lock
                real_return = config_file._return_config_thread_lock
                lock_fd: int | None = None
                signalled = False

                def invoke_installed_handler() -> None:
                    nonlocal signalled
                    handler = signal.getsignal(signal.SIGINT)
                    self.assertTrue(callable(handler))
                    signalled = True
                    handler(signal.SIGINT, None)  # type: ignore[operator]

                def unlock(fd: int) -> None:
                    nonlocal lock_fd
                    lock_fd = fd
                    real_unlock(fd)
                    if phase == "unlock" and not signalled:
                        invoke_installed_handler()

                def close(fd: int) -> None:
                    real_close(fd)
                    if phase == "close" and fd == lock_fd and not signalled:
                        invoke_installed_handler()

                def release(lock: object) -> None:
                    real_release(lock)
                    if phase == "release" and not signalled:
                        invoke_installed_handler()

                def return_lock(key: str, lock: object) -> None:
                    real_return(key, lock)
                    if phase == "registry" and not signalled:
                        invoke_installed_handler()

                with patch("config_file._unlock_config_fd", side_effect=unlock), patch(
                    "config_file.os.close",
                    side_effect=close,
                ), patch(
                    "config_file._release_config_thread_lock",
                    side_effect=release,
                ), patch(
                    "config_file._return_config_thread_lock",
                    side_effect=return_lock,
                ):
                    result = set_section(root, "review", {"mode": "advisory"})

                self.assertTrue(signalled)
                self.assertEqual(signal.getsignal(signal.SIGINT), previous_handler)
                self.assertEqual(result, target)
                self.assertEqual(
                    load_config_path(target, root=root)["review"]["mode"],
                    "advisory",
                )
                failures: list[BaseException] = []

                def next_writer() -> None:
                    try:
                        set_section(root, "recall", {"enabled": False})
                    except BaseException as exc:  # pragma: no cover - asserted below
                        failures.append(exc)

                writer = threading.Thread(target=next_writer, daemon=True)
                writer.start()
                writer.join(timeout=5)
                self.assertFalse(writer.is_alive())
                self.assertEqual(failures, [])
                self.assertIs(
                    load_config_path(target, root=root)["recall"]["enabled"],
                    False,
                )

    def test_signal_during_lock_acquisition_records_ownership_before_replay(self) -> None:
        import config_file

        for phase in ("borrow", "open"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / CONFIG_NAME
                previous_handler = signal.getsignal(signal.SIGINT)
                real_borrow = config_file._borrow_config_thread_lock
                real_open = config_file.os.open
                signalled = False

                def invoke_installed_handler() -> None:
                    nonlocal signalled
                    handler = signal.getsignal(signal.SIGINT)
                    self.assertTrue(callable(handler))
                    signalled = True
                    handler(signal.SIGINT, None)  # type: ignore[operator]

                def borrow(key: str) -> object:
                    lock = real_borrow(key)
                    if phase == "borrow" and not signalled:
                        invoke_installed_handler()
                    return lock

                def open_file(path: object, flags: int, mode: int = 0o777) -> int:
                    fd = real_open(path, flags, mode)  # type: ignore[arg-type]
                    if (
                        phase == "open"
                        and Path(path).name == CONFIG_WRITE_LOCK_NAME
                        and not signalled
                    ):
                        invoke_installed_handler()
                    return fd

                with patch(
                    "config_file._borrow_config_thread_lock",
                    side_effect=borrow,
                ), patch("config_file.os.open", side_effect=open_file):
                    result = set_section(root, "review", {"mode": "strict"})

                self.assertTrue(signalled)
                self.assertEqual(signal.getsignal(signal.SIGINT), previous_handler)
                self.assertEqual(result, target)
                set_section(root, "recall", {"enabled": False})
                self.assertIs(
                    load_config_path(target, root=root)["recall"]["enabled"],
                    False,
                )

    def test_signal_at_lock_exit_boundary_cleans_before_replay(self) -> None:
        import config_file

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous_handler = signal.getsignal(signal.SIGINT)
            checkpoint_called = False

            def interrupt_at_exit() -> None:
                nonlocal checkpoint_called
                checkpoint_called = True
                handler = signal.getsignal(signal.SIGINT)
                self.assertTrue(callable(handler))
                handler(signal.SIGINT, None)  # type: ignore[operator]

            with patch(
                "config_file._config_lock_exit_checkpoint",
                side_effect=interrupt_at_exit,
            ), self.assertRaises(KeyboardInterrupt):
                with config_write_lock(root):
                    pass

            self.assertTrue(checkpoint_called)
            self.assertEqual(signal.getsignal(signal.SIGINT), previous_handler)
            lock_key = os.path.normcase(
                str((root / CONFIG_WRITE_LOCK_NAME).resolve(strict=False))
            )
            self.assertNotIn(lock_key, config_file._CONFIG_WRITE_THREAD_LOCKS)

            acquired = threading.Event()
            failures: list[BaseException] = []

            def next_owner() -> None:
                try:
                    with config_write_lock(root, timeout_seconds=1):
                        acquired.set()
                except BaseException as exc:  # pragma: no cover - asserted below
                    failures.append(exc)

            owner = threading.Thread(target=next_owner, daemon=True)
            owner.start()
            owner.join(timeout=5)
            self.assertFalse(owner.is_alive())
            self.assertTrue(acquired.is_set())
            self.assertEqual(failures, [])
            self.assertNotIn(lock_key, config_file._CONFIG_WRITE_THREAD_LOCKS)

    @unittest.skipUnless(hasattr(signal, "SIGBREAK"), "SIGBREAK is Windows-only")
    def test_default_sigbreak_replays_as_safe_cancellation(self) -> None:
        import config_file

        sigbreak = signal.SIGBREAK
        previous_handler = signal.getsignal(sigbreak)
        signal.signal(sigbreak, signal.SIG_DFL)
        try:
            for phase in ("precommit", "postcommit"):
                with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    target = root / CONFIG_NAME
                    real_atomic = config_file._atomic_replace_config_text
                    invoked = False

                    def atomic_with_sigbreak(*args: object, **kwargs: object) -> Path:
                        nonlocal invoked
                        if phase == "precommit":
                            handler = signal.getsignal(sigbreak)
                            self.assertTrue(callable(handler))
                            invoked = True
                            handler(sigbreak, None)  # type: ignore[operator]
                        result = real_atomic(*args, **kwargs)  # type: ignore[arg-type]
                        if phase == "postcommit":
                            handler = signal.getsignal(sigbreak)
                            self.assertTrue(callable(handler))
                            invoked = True
                            handler(sigbreak, None)  # type: ignore[operator]
                        return result

                    with patch(
                        "config_file._atomic_replace_config_text",
                        side_effect=atomic_with_sigbreak,
                    ), patch("config_file.signal.raise_signal") as raise_signal:
                        result = set_section(root, "review", {"mode": "strict"})

                    self.assertTrue(invoked)
                    self.assertEqual(result, target)
                    self.assertEqual(signal.getsignal(sigbreak), signal.SIG_DFL)
                    raise_signal.assert_not_called()

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)

                def interrupt_at_exit() -> None:
                    handler = signal.getsignal(sigbreak)
                    self.assertTrue(callable(handler))
                    handler(sigbreak, None)  # type: ignore[operator]

                with patch(
                    "config_file._config_lock_exit_checkpoint",
                    side_effect=interrupt_at_exit,
                ), patch("config_file.signal.raise_signal") as raise_signal, self.assertRaises(
                    KeyboardInterrupt
                ):
                    with config_write_lock(root):
                        pass
                raise_signal.assert_not_called()
                self.assertEqual(signal.getsignal(sigbreak), signal.SIG_DFL)
        finally:
            signal.signal(sigbreak, previous_handler)

    def test_stale_merge_snapshot_fails_without_erasing_newer_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            set_section(root, "review", {"reviewer": "first", "mode": "strict"})
            observed = dict(load_config_path(root / CONFIG_NAME, root=root)["review"])
            set_section(root, "review", {"reviewer": "newer", "mode": "strict"})
            newer_bytes = (root / CONFIG_NAME).read_bytes()

            with self.assertRaises(ConfigError) as raised:
                set_section(
                    root,
                    "review",
                    {"reviewer": "first", "mode": "advisory"},
                    expected_section=observed,
                )

            self.assertEqual(raised.exception.code, "config_changed")
            self.assertEqual((root / CONFIG_NAME).read_bytes(), newer_bytes)

    def test_cross_process_writer_waits_for_kernel_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "child-ready"
            code = (
                "from pathlib import Path; import sys; "
                "sys.path.insert(0, str(Path.cwd() / 'scripts')); "
                "from config_file import set_section; "
                "root=Path(sys.argv[1]); Path(sys.argv[2]).write_text('ready'); "
                "set_section(root, 'recall', {'enabled': False})"
            )
            with config_write_lock(root):
                child = subprocess.Popen(
                    [sys.executable, "-c", code, str(root), str(marker)],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=os.environ.copy(),
                )
                for _ in range(200):
                    if marker.exists():
                        break
                    time.sleep(0.01)
                self.assertTrue(marker.exists())
                time.sleep(0.05)
                self.assertIsNone(child.poll())

            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, msg=f"stdout={stdout}\nstderr={stderr}")
            self.assertTrue((root / CONFIG_WRITE_LOCK_NAME).exists())
            self.assertIs(
                load_config_path(root / CONFIG_NAME, root=root)["recall"]["enabled"],
                False,
            )

    def test_crashed_lock_owner_leaves_no_blocking_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            code = (
                "from pathlib import Path; import os, sys; "
                "sys.path.insert(0, str(Path.cwd() / 'scripts')); "
                "from config_file import config_write_lock; "
                "root=Path(sys.argv[1]); "
                "lock=config_write_lock(root); lock.__enter__(); os._exit(0)"
            )
            completed = subprocess.run(
                [sys.executable, "-c", code, str(root)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                env=os.environ.copy(),
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue((root / CONFIG_WRITE_LOCK_NAME).exists())

            set_section(root, "review", {"mode": "strict"})
            self.assertEqual(
                load_config_path(root / CONFIG_NAME, root=root)["review"]["mode"],
                "strict",
            )

    def test_lock_contention_is_bounded_and_does_not_change_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with config_write_lock(root):
                with self.assertRaises(ConfigError) as raised:
                    with config_write_lock(root, timeout_seconds=0.02):
                        self.fail("contended lock unexpectedly acquired")

            self.assertEqual(raised.exception.code, "config_busy")
            self.assertFalse((root / CONFIG_NAME).exists())
            set_section(root, "review", {"mode": "strict"})
            self.assertEqual(
                load_config_path(root / CONFIG_NAME, root=root)["review"]["mode"],
                "strict",
            )

    def test_interrupted_thread_lock_acquire_releases_registry_and_owned_lock(self) -> None:
        import config_file

        class InterruptedLock:
            def __init__(self, *, acquired_before_interrupt: bool) -> None:
                self.acquired_before_interrupt = acquired_before_interrupt
                self.owned = False
                self.release_calls = 0

            def acquire(self, *, timeout: float) -> bool:
                del timeout
                self.owned = self.acquired_before_interrupt
                raise KeyboardInterrupt

            def release(self) -> None:
                self.release_calls += 1
                if not self.owned:
                    raise RuntimeError("lock is not owned by this thread")
                self.owned = False

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for acquired_before_interrupt in (False, True):
                with self.subTest(acquired_before_interrupt=acquired_before_interrupt):
                    fake = InterruptedLock(
                        acquired_before_interrupt=acquired_before_interrupt
                    )
                    borrowed_key = ""

                    def borrow(key: str) -> InterruptedLock:
                        nonlocal borrowed_key
                        borrowed_key = key
                        with config_file._CONFIG_WRITE_THREAD_GUARD:
                            config_file._CONFIG_WRITE_THREAD_LOCKS[key] = (fake, 1)
                        return fake

                    with patch(
                        "config_file._borrow_config_thread_lock",
                        side_effect=borrow,
                    ), self.assertRaises(KeyboardInterrupt):
                        with config_write_lock(root):
                            self.fail("interrupted lock unexpectedly entered")

                    self.assertFalse(fake.owned)
                    self.assertEqual(fake.release_calls, 1)
                    self.assertNotIn(
                        borrowed_key,
                        config_file._CONFIG_WRITE_THREAD_LOCKS,
                    )

            with config_write_lock(root):
                pass

    def test_interrupted_waiter_cannot_release_another_thread_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner_entered = threading.Event()
            release_owner = threading.Event()
            third_entered = threading.Event()
            failures: list[BaseException] = []

            def owner() -> None:
                try:
                    with config_write_lock(root):
                        owner_entered.set()
                        if not release_owner.wait(timeout=5):
                            raise TimeoutError("owner release timed out")
                except BaseException as exc:  # pragma: no cover - asserted below
                    failures.append(exc)

            def timed_waiter() -> None:
                try:
                    with config_write_lock(root, timeout_seconds=0.02):
                        failures.append(AssertionError("waiter unexpectedly acquired lock"))
                except ConfigError as exc:
                    if exc.code != "config_busy":
                        failures.append(exc)

            def third_writer() -> None:
                try:
                    with config_write_lock(root, timeout_seconds=2):
                        third_entered.set()
                except BaseException as exc:  # pragma: no cover - asserted below
                    failures.append(exc)

            with patch("config_file._try_lock_config_fd", return_value=True), patch(
                "config_file._unlock_config_fd",
                return_value=None,
            ):
                owner_thread = threading.Thread(target=owner, daemon=True)
                owner_thread.start()
                self.assertTrue(owner_entered.wait(timeout=5))
                waiter_thread = threading.Thread(target=timed_waiter, daemon=True)
                waiter_thread.start()
                waiter_thread.join(timeout=5)
                self.assertFalse(waiter_thread.is_alive())

                third_thread = threading.Thread(target=third_writer, daemon=True)
                third_thread.start()
                time.sleep(0.05)
                self.assertFalse(third_entered.is_set())
                release_owner.set()
                owner_thread.join(timeout=5)
                third_thread.join(timeout=5)

            self.assertFalse(owner_thread.is_alive())
            self.assertFalse(third_thread.is_alive())
            self.assertTrue(third_entered.is_set())
            self.assertEqual(failures, [])

    @unittest.skipIf(os.name == "nt", "Windows refuses replacement of an open locked sentinel")
    def test_lock_validator_detects_replaced_sentinel_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / ".ai-dememory-schedule.lock"
            replacement = root / ".replacement.lock"

            with vault_operation_lock(
                root,
                lock_name=lock_path.name,
                source="schedule",
            ) as validate:
                replacement.write_bytes(b"\0")
                os.replace(replacement, lock_path)
                with self.assertRaises(ConfigError) as raised:
                    validate()

            self.assertEqual(raised.exception.code, "config_lock_error")
            self.assertEqual(raised.exception.source, "schedule")

    def test_review_state_write_rejects_a_concurrent_routing_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            set_section(
                root,
                "false_positives",
                {"allow_ignore_file": True, "ignore_file": "old-review.toml"},
            )
            real_set_section_path = review_memory.set_section_path

            def change_route_before_write(*args: object, **kwargs: object) -> Path:
                set_section(
                    root,
                    "false_positives",
                    {"allow_ignore_file": True, "ignore_file": "new-review.toml"},
                )
                return real_set_section_path(*args, **kwargs)  # type: ignore[arg-type]

            with patch(
                "review_memory.set_section_path",
                side_effect=change_route_before_write,
            ), self.assertRaises(ReviewError) as raised:
                review_memory._set_review_state_section(
                    root,
                    "false_positives.fp_0123456789abcdef",
                    {"ignored": True, "reviewer": "Unit Test"},
                )

            self.assertIn("config error [config_changed]", str(raised.exception))
            self.assertFalse((root / "old-review.toml").exists())
            self.assertFalse((root / "new-review.toml").exists())


if __name__ == "__main__":
    unittest.main()
