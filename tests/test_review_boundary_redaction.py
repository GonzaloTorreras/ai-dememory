from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from schedule_memory import (  # noqa: E402
    SCHEDULE_REVIEW_STATE_ERROR_MESSAGE,
    main as schedule_main,
    schedule_status,
)
from sleep_consolidation import (  # noqa: E402
    SLEEP_REVIEW_STATE_ERROR_MESSAGE,
    SleepError,
    build_sleep_plan,
    main as sleep_main,
)


REVIEW_PATH_CANARY = "DO_NOT_ECHO_CUSTOM_REVIEW_PATH"


class ReviewBoundaryRedactionTests(unittest.TestCase):
    @staticmethod
    def _vault(temporary: str) -> Path:
        root = Path(temporary) / "vault"
        state = root / "state" / f"{REVIEW_PATH_CANARY}.toml"
        state.parent.mkdir(parents=True)
        (root / ".ai-dememory.toml").write_text(
            "[false_positives]\n"
            "enabled = true\n"
            "allow_ignore_file = true\n"
            f'ignore_file = "state/{REVIEW_PATH_CANARY}.toml"\n'
            "[conflicts]\n"
            "enabled = true\n",
            encoding="utf-8",
        )
        state.write_text(
            "[false_positives.fp_0123456789abcdef]\nignored = true\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def _tree_snapshot(root: Path) -> dict[str, tuple[str, bytes]]:
        snapshot: dict[str, tuple[str, bytes]] = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                snapshot[relative] = ("directory", b"")
            elif path.is_file():
                snapshot[relative] = ("file", path.read_bytes())
        return snapshot

    @staticmethod
    def _review_read_failure() -> ValueError:
        return ValueError(f"review state read failed at {REVIEW_PATH_CANARY}")

    def test_schedule_status_terminates_review_error_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._vault(temporary)
            before = self._tree_snapshot(root)

            with patch(
                "review_memory.load_config_path",
                side_effect=self._review_read_failure(),
            ), patch("schedule_memory.build_schedule_commands") as commands, patch(
                "schedule_memory.vault_operation_lock"
            ) as operation_lock:
                with self.assertRaises(ValueError) as direct_error:
                    schedule_status(root, target_platform="linux")

                diagnostics: list[str] = []
                error_diagnostics: list[str] = []
                for json_mode in (False, True):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    argv = ["--root", str(root), "remove", "--platform", "linux"]
                    if json_mode:
                        argv.append("--json")
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        exit_code = schedule_main(argv)
                    self.assertEqual(exit_code, 2)
                    if json_mode:
                        self.assertEqual(json.loads(stdout.getvalue()), [])
                        diagnostics.append(stdout.getvalue())
                    else:
                        self.assertEqual(stdout.getvalue(), "")
                    diagnostics.append(stderr.getvalue())
                    error_diagnostics.append(stderr.getvalue())

            self.assertEqual(str(direct_error.exception), SCHEDULE_REVIEW_STATE_ERROR_MESSAGE)
            self.assertIsNone(direct_error.exception.__cause__)
            for diagnostic in diagnostics:
                self.assertNotIn(REVIEW_PATH_CANARY, diagnostic)
                self.assertNotIn("Traceback", diagnostic)
            for diagnostic in error_diagnostics:
                self.assertIn(SCHEDULE_REVIEW_STATE_ERROR_MESSAGE, diagnostic)
            self.assertEqual(self._tree_snapshot(root), before)
            commands.assert_not_called()
            operation_lock.assert_not_called()

    def test_sleep_plan_terminates_review_error_chain_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._vault(temporary)
            before = self._tree_snapshot(root)

            with patch(
                "review_memory.load_config_path",
                side_effect=self._review_read_failure(),
            ):
                with self.assertRaises(SleepError) as direct_error:
                    build_sleep_plan(root)

                diagnostics: list[str] = []
                commands = (
                    ["--root", str(root), "--dry-run"],
                    ["--root", str(root), "plan", "--json"],
                )
                for argv in commands:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        exit_code = sleep_main(argv)
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(stdout.getvalue(), "")
                    diagnostics.append(stderr.getvalue())

            self.assertEqual(str(direct_error.exception), SLEEP_REVIEW_STATE_ERROR_MESSAGE)
            self.assertIsNone(direct_error.exception.__cause__)
            for diagnostic in diagnostics:
                self.assertIn(SLEEP_REVIEW_STATE_ERROR_MESSAGE, diagnostic)
                self.assertNotIn(REVIEW_PATH_CANARY, diagnostic)
                self.assertNotIn("Traceback", diagnostic)
            self.assertEqual(self._tree_snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
