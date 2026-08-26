from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
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

from config_file import CONFIG_NAME, ConfigError  # noqa: E402
from setup_plan import main, setup_health, setup_plan  # noqa: E402


REDACTION_CANARY = "strict-config-value-must-not-escape"
INVALID_CONFIG = (
    "[review]\n"
    'mode = "strict"\n'
    f'unexpected = "{REDACTION_CANARY}"\n'
)


class StrictSetupBoundaryTests(unittest.TestCase):
    def _invalid_vault(self, temporary: str) -> tuple[Path, Path]:
        root = Path(temporary) / "vault"
        root.mkdir()
        config = root / CONFIG_NAME
        config.write_text(INVALID_CONFIG, encoding="utf-8")
        return root, config

    def test_plan_and_health_validate_config_before_collectors(self) -> None:
        cases = (
            (
                "plan",
                setup_plan,
                (
                    "setup_plan.resolved_resource_policy",
                    "setup_plan.provider_setup_plan",
                ),
            ),
            (
                "health",
                setup_health,
                (
                    "setup_plan.schedule_status",
                    "setup_plan.maintenance_status",
                    "setup_plan.hook_status_summary",
                    "setup_plan.validate_repo_result",
                ),
            ),
        )
        for name, function, collector_names in cases:
            with self.subTest(command=name), tempfile.TemporaryDirectory() as temporary:
                root, config = self._invalid_vault(temporary)
                original = config.read_bytes()
                with ExitStack() as stack:
                    collectors = [stack.enter_context(patch(target)) for target in collector_names]
                    with self.assertRaises(ConfigError) as raised:
                        function(root)

                self.assertEqual(raised.exception.code, "unknown_key")
                self.assertEqual(raised.exception.field, "review.<unknown>")
                self.assertNotIn(REDACTION_CANARY, str(raised.exception))
                self.assertEqual(config.read_bytes(), original)
                for collector in collectors:
                    collector.assert_not_called()

    def test_json_failures_are_structured_redacted_and_traceback_free(self) -> None:
        for command in ("plan", "health"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as temporary:
                root, config = self._invalid_vault(temporary)
                original = config.read_bytes()
                stdout = io.StringIO()
                stderr = io.StringIO()

                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = main(["--root", str(root), command, "--json"])

                output = stdout.getvalue()
                payload = json.loads(output)
                self.assertEqual(exit_code, 2)
                self.assertEqual(stderr.getvalue(), "")
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["type"], "configuration_error")
                self.assertEqual(payload["error"]["code"], "unknown_key")
                self.assertEqual(payload["error"]["source"], CONFIG_NAME)
                self.assertEqual(payload["error"]["field"], "review.<unknown>")
                self.assertIsInstance(payload["error"]["line"], int)
                self.assertIsInstance(payload["error"]["column"], int)
                self.assertNotIn(REDACTION_CANARY, output)
                self.assertNotIn("Traceback", output)
                self.assertEqual(config.read_bytes(), original)

    def test_human_failure_is_redacted_and_traceback_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, config = self._invalid_vault(temporary)
            original = config.read_bytes()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["--root", str(root), "health"])

            self.assertEqual(exit_code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("config error [unknown_key]", stderr.getvalue())
            self.assertNotIn(REDACTION_CANARY, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(config.read_bytes(), original)

    def test_safe_reader_value_error_uses_the_same_json_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            config = root / CONFIG_NAME
            original = b"\xffprivate-bytes-must-not-escape"
            config.write_bytes(original)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(["--root", str(root), "plan", "--json"])

            output = stdout.getvalue()
            payload = json.loads(output)
            self.assertEqual(exit_code, 2)
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "configuration_error")
            self.assertEqual(payload["error"]["code"], "config_read_error")
            self.assertEqual(payload["error"]["message"], "config file must be valid UTF-8")
            self.assertNotIn("private-bytes", output)
            self.assertNotIn("Traceback", output)
            self.assertEqual(config.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
