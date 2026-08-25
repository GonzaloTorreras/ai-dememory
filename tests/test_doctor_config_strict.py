from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from config_file import CONFIG_NAME  # noqa: E402
from doctor import check_config, main, run_checks  # noqa: E402


REDACTION_CANARY = "doctor-config-value-must-not-escape"


class StrictDoctorConfigTests(unittest.TestCase):
    def _vault(self, temporary: str, content: bytes | None) -> Path:
        root = Path(temporary) / "vault"
        root.mkdir()
        (root / "README.md").write_text("# Test vault\n", encoding="utf-8")
        for directory in ("memories", "inbox", "templates"):
            (root / directory).mkdir()
        if content is not None:
            (root / CONFIG_NAME).write_bytes(content)
        return root

    @staticmethod
    def _snapshot(root: Path) -> dict[str, bytes | None]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
            for path in sorted(root.rglob("*"))
        }

    def test_missing_empty_and_valid_partial_configs_pass(self) -> None:
        cases = (
            ("missing", None),
            ("empty", b"# defaults only\n"),
            ("partial", b"[recall]\nenabled = true\n"),
        )
        for name, content in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = self._vault(temporary, content)

                result = check_config(root)

                self.assertEqual(result.name, "config")
                self.assertEqual(result.status, "ok")
                self.assertNotIn(REDACTION_CANARY, result.detail)

    def test_invalid_configs_are_structured_redacted_and_read_only(self) -> None:
        cases = (
            (
                "syntax",
                f"[review]\nreviewer = {REDACTION_CANARY}\n".encode(),
                "toml_syntax",
                None,
            ),
            (
                "unknown",
                (
                    "[review]\n"
                    f'unexpected = "{REDACTION_CANARY}"\n'
                ).encode(),
                "unknown_key",
                "review.<unknown>",
            ),
            (
                "wrong_type",
                (
                    "[recall]\n"
                    f'enabled = "{REDACTION_CANARY}"\n'
                ).encode(),
                "invalid_type",
                "recall.enabled",
            ),
            (
                "utf8",
                b"\xff" + REDACTION_CANARY.encode(),
                "config_read_error",
                None,
            ),
        )
        for name, content, expected_code, expected_field in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = self._vault(temporary, content)
                before = self._snapshot(root)
                stdout = io.StringIO()
                stderr = io.StringIO()

                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = main(["--root", str(root), "--json", "--summary"])

                payload = json.loads(stdout.getvalue())
                config = next(check for check in payload["checks"] if check["name"] == "config")
                self.assertEqual(exit_code, 1)
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(config["status"], "fail")
                self.assertEqual(config["code"], expected_code)
                self.assertEqual(config["source"], CONFIG_NAME)
                self.assertEqual(config["field"], expected_field)
                self.assertIn("line", config)
                self.assertIn("column", config)
                self.assertNotIn(REDACTION_CANARY, stdout.getvalue())
                self.assertNotIn("Traceback", stdout.getvalue())
                self.assertEqual(self._snapshot(root), before)

    def test_human_failure_remains_one_redacted_check_without_traceback(self) -> None:
        content = (
            "[review]\n"
            f'unexpected = "{REDACTION_CANARY}"\n'
        ).encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = self._vault(temporary, content)
            before = self._snapshot(root)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["--root", str(root)])

            self.assertEqual(exit_code, 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("FAIL config:", stdout.getvalue())
            self.assertIn("config error [unknown_key]", stdout.getvalue())
            self.assertNotIn(REDACTION_CANARY, stdout.getvalue())
            self.assertNotIn("Traceback", stdout.getvalue())
            self.assertEqual(self._snapshot(root), before)

    def test_json_without_summary_remains_a_row_list(self) -> None:
        content = (
            "[review]\n"
            f'unexpected = "{REDACTION_CANARY}"\n'
        ).encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = self._vault(temporary, content)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["--root", str(root), "--json"])

        rows = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertIsInstance(rows, list)
        config = next(check for check in rows if check["name"] == "config")
        self.assertEqual(config["code"], "unknown_key")
        self.assertNotIn(REDACTION_CANARY, stdout.getvalue())

    def test_run_checks_preserves_general_failure_exit_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._vault(temporary, b"[recall]\nenabled = 1\n")

            checks = run_checks(root)

        config = next(check for check in checks if check.name == "config")
        self.assertEqual(config.status, "fail")
        self.assertTrue(any(check.status == "fail" for check in checks))


if __name__ == "__main__":
    unittest.main()
