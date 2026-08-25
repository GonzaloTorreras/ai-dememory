from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import traceback
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MCP_SERVER = ROOT / "mcp" / "server"
for import_root in (SCRIPTS, MCP_SERVER):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from config_file import CONFIG_NAME  # noqa: E402
from memory_mcp import handle_rpc  # noqa: E402
from review_memory import (  # noqa: E402
    ReviewError,
    _set_review_state_section,
    active_review_mode,
    configure_review_mode,
    load_review_config,
    main as review_main,
    review_policy_config,
)


class ReviewConfigDiagnosticRedactionTests(unittest.TestCase):
    @staticmethod
    def tree_snapshot(root: Path) -> dict[str, tuple[str, bytes]]:
        snapshot: dict[str, tuple[str, bytes]] = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                snapshot[relative] = ("directory", b"")
            elif path.is_file():
                snapshot[relative] = ("file", path.read_bytes())
        return snapshot

    @staticmethod
    def mcp_error_text(root: Path, tool_name: str) -> str:
        result = handle_rpc(
            {
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": {}},
            },
            root,
        )
        if result is None:
            raise AssertionError("expected an MCP tool result")
        if result.get("isError") is not True:
            raise AssertionError(f"expected an MCP error result, got {result!r}")
        return str(result["content"][0]["text"])

    def test_custom_review_state_path_is_never_used_as_a_diagnostic_source(self) -> None:
        path_canary = "DO_NOT_ECHO_CUSTOM_REVIEW_PATH"
        field_canary = "DO_NOT_ECHO_CUSTOM_REVIEW_FIELD"
        forged_line = "FORGED_REVIEW_STATE_DIAGNOSTIC_LINE"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            state = root / "state" / f"{path_canary}.toml"
            state.parent.mkdir(parents=True)
            (root / CONFIG_NAME).write_text(
                "\n".join(
                    (
                        "[false_positives]",
                        "allow_ignore_file = true",
                        f'ignore_file = "state/{path_canary}.toml"',
                        "",
                    )
                ),
                encoding="utf-8",
            )
            original_state = (
                "[false_positives.fp_0123456789abcdef]\n"
                f'"{field_canary}\\n{forged_line}" = true\n'
            ).encode("utf-8")
            state.write_bytes(original_state)
            before = self.tree_snapshot(root)

            with self.assertRaises(ReviewError) as direct_error:
                load_review_config(root)
            with self.assertRaises(ReviewError) as writer_error:
                _set_review_state_section(
                    root,
                    "false_positives.fp_0123456789abcdef",
                    {"ignored": True},
                )

            stderr = io.StringIO()
            stdout = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(stdout):
                exit_code = review_main(
                    ["--root", str(root), "review", "false-positives", "--json"]
                )
            mcp_error = self.mcp_error_text(root, "memory.review_false_positives")

            diagnostics = (
                str(direct_error.exception),
                str(writer_error.exception),
                stderr.getvalue(),
                stdout.getvalue(),
                mcp_error,
            )
            for diagnostic in diagnostics:
                self.assertNotIn(path_canary, diagnostic)
                self.assertNotIn(field_canary, diagnostic)
                self.assertNotIn(forged_line, diagnostic)
            self.assertIn("review-state-config", str(direct_error.exception))
            self.assertNotIn("\n", str(direct_error.exception))
            direct_traceback = "".join(traceback.format_exception(direct_error.exception))
            self.assertNotIn(path_canary, direct_traceback)
            self.assertNotIn(field_canary, direct_traceback)
            self.assertNotIn(forged_line, direct_traceback)
            self.assertIsNone(direct_error.exception.__cause__)
            self.assertIn("review-state-config", str(writer_error.exception))
            self.assertIsNone(writer_error.exception.__cause__)
            self.assertIn("review-state-config", stderr.getvalue())
            self.assertIn("review-state-config", mcp_error)
            self.assertEqual(exit_code, 1)
            self.assertEqual(self.tree_snapshot(root), before)
            self.assertEqual(state.read_bytes(), original_state)

    def test_external_review_state_path_is_absent_from_messages_and_tracebacks(self) -> None:
        path_canary = "DO_NOT_ECHO_EXTERNAL_REVIEW_PATH"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "vault"
            root.mkdir()
            outside = base / f"{path_canary}.toml"
            (root / CONFIG_NAME).write_text(
                "[false_positives]\n"
                f"ignore_file = {json.dumps(str(outside))}\n",
                encoding="utf-8",
            )
            before = self.tree_snapshot(root)

            with self.assertRaises(ReviewError) as direct_error:
                load_review_config(root)
            stderr = io.StringIO()
            stdout = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(stdout):
                exit_code = review_main(
                    ["--root", str(root), "review", "false-positives", "--json"]
                )
            mcp_error = self.mcp_error_text(root, "memory.review_false_positives")

            formatted = "".join(traceback.format_exception(direct_error.exception))
            for diagnostic in (
                str(direct_error.exception),
                formatted,
                stderr.getvalue(),
                stdout.getvalue(),
                mcp_error,
            ):
                self.assertNotIn(path_canary, diagnostic)
                self.assertNotIn(str(outside), diagnostic)
            self.assertIsNone(direct_error.exception.__cause__)
            self.assertIn("review state path must stay inside", str(direct_error.exception))
            self.assertEqual(exit_code, 1)
            self.assertEqual(self.tree_snapshot(root), before)

    def test_semantic_review_values_are_redacted_across_api_cli_and_mcp(self) -> None:
        cases = (
            ("review", "mode", active_review_mode, "unknown review mode"),
            (
                "false_positives",
                "triage_policy",
                review_policy_config,
                "unknown false-positive triage policy",
            ),
            (
                "conflicts",
                "resolution_policy",
                review_policy_config,
                "unknown conflict resolution policy",
            ),
        )
        for section, key, direct_call, expected_message in cases:
            with self.subTest(field=f"{section}.{key}"):
                value_canary = f"DO_NOT_ECHO_{section.upper()}_{key.upper()}"
                forged_line = f"FORGED_DIAGNOSTIC_LINE_{section.upper()}_{key.upper()}"
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary) / "vault"
                    root.mkdir()
                    (root / CONFIG_NAME).write_text(
                        f'[{section}]\n{key} = """{value_canary}\n{forged_line}"""\n',
                        encoding="utf-8",
                    )
                    before = self.tree_snapshot(root)

                    with self.assertRaises(ReviewError) as direct_error:
                        direct_call(root)

                    stderr = io.StringIO()
                    stdout = io.StringIO()
                    with redirect_stderr(stderr), redirect_stdout(stdout):
                        exit_code = review_main(
                            ["--root", str(root), "review", "modes", "--json"]
                        )
                    mcp_error = self.mcp_error_text(root, "memory.review_modes")

                    diagnostics = (
                        str(direct_error.exception),
                        stderr.getvalue(),
                        stdout.getvalue(),
                        mcp_error,
                    )
                    for diagnostic in diagnostics:
                        self.assertNotIn(value_canary, diagnostic)
                        self.assertNotIn(forged_line, diagnostic)
                    self.assertNotIn("\n", str(direct_error.exception))
                    self.assertIn(expected_message, str(direct_error.exception))
                    self.assertIn(expected_message, stderr.getvalue())
                    self.assertIn(expected_message, mcp_error)
                    self.assertEqual(exit_code, 1)
                    self.assertEqual(self.tree_snapshot(root), before)

    def test_review_state_write_errors_redact_the_custom_path(self) -> None:
        path_canary = "DO_NOT_ECHO_REVIEW_WRITE_PATH"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            state = root / "state" / f"{path_canary}.toml"
            state.parent.mkdir(parents=True)
            (root / CONFIG_NAME).write_text(
                "[false_positives]\n"
                "allow_ignore_file = true\n"
                f'ignore_file = "state/{path_canary}.toml"\n',
                encoding="utf-8",
            )
            before = self.tree_snapshot(root)
            os_error = PermissionError(13, "permission denied", str(state))

            with patch("config_file.safe_write_text", side_effect=os_error):
                with self.assertRaises(ReviewError) as raised:
                    _set_review_state_section(
                        root,
                        "false_positives.fp_0123456789abcdef",
                        {"ignored": True},
                    )

            diagnostic = str(raised.exception)
            self.assertEqual(
                diagnostic,
                "review-state-config: config error [config_write_error]",
            )
            self.assertNotIn(path_canary, diagnostic)
            self.assertNotIn(str(root), diagnostic)
            formatted = "".join(traceback.format_exception(raised.exception))
            self.assertNotIn(path_canary, formatted)
            self.assertNotIn(str(root), formatted)
            self.assertIsNone(raised.exception.__cause__)
            self.assertEqual(self.tree_snapshot(root), before)

    def test_requested_review_mode_is_redacted_in_direct_and_mcp_errors(self) -> None:
        value_canary = "DO_NOT_ECHO_REQUESTED_REVIEW_MODE"
        forged_line = "FORGED_REQUESTED_MODE_DIAGNOSTIC_LINE"
        requested_mode = f"{value_canary}\n{forged_line}"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            root.mkdir()
            before = self.tree_snapshot(root)

            with self.assertRaises(ReviewError) as direct_error:
                configure_review_mode(root, requested_mode)
            cli_stderr = io.StringIO()
            cli_stdout = io.StringIO()
            with redirect_stderr(cli_stderr), redirect_stdout(cli_stdout):
                with self.assertRaises(SystemExit) as cli_exit:
                    review_main(
                        [
                            "--root",
                            str(root),
                            "review",
                            "configure-mode",
                            "--mode",
                            requested_mode,
                        ]
                    )
            result = handle_rpc(
                {
                    "method": "tools/call",
                    "params": {
                        "name": "memory.review_configure_mode",
                        "arguments": {"mode": requested_mode},
                    },
                },
                root,
            )

            if result is None:
                self.fail("expected an MCP tool result")
            self.assertIs(result.get("isError"), True)
            mcp_error = str(result["content"][0]["text"])
            for diagnostic in (
                str(direct_error.exception),
                cli_stderr.getvalue(),
                cli_stdout.getvalue(),
                mcp_error,
            ):
                self.assertNotIn(value_canary, diagnostic)
                self.assertNotIn(forged_line, diagnostic)
            for diagnostic in (
                str(direct_error.exception),
                cli_stderr.getvalue(),
                mcp_error,
            ):
                self.assertIn("unknown review mode", diagnostic)
            self.assertNotIn("\n", str(direct_error.exception))
            self.assertNotIn("\n", mcp_error)
            self.assertEqual(cli_exit.exception.code, 2)
            self.assertEqual(self.tree_snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
