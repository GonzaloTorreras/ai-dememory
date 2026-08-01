from __future__ import annotations

from collections.abc import Callable
import io
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts", ROOT / "mcp" / "server"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from ai_dememory_tool.cli import build_mcp_config  # noqa: E402
import process_control  # noqa: E402
from ai_dememory_tool.mcp_profiles import (  # noqa: E402
    DEFAULT_MCP_IDLE_TIMEOUT_SECONDS,
    MAX_MCP_IDLE_TIMEOUT_SECONDS,
    MIN_MCP_IDLE_TIMEOUT_SECONDS,
    normalize_mcp_idle_timeout_seconds,
)
from memory_mcp import MAX_MCP_FRAME_CHARS, MCP_STDIN_QUEUE_DEPTH, stdio_lines  # noqa: E402
from mcp_runtime_smoke import SmokeError, response_line, rpc_response  # noqa: E402
from process_control import run_owned_capture, run_owned_process  # noqa: E402


class ControlledBlockingEof:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.exited = threading.Event()
        self.reader_thread: threading.Thread | None = None

    def readline(self, _size: int = -1) -> str:
        self.reader_thread = threading.current_thread()
        self.entered.set()
        self.release.wait()
        self.exited.set()
        return ""


class ObservedQueue(queue.Queue[tuple[str, object]]):
    def __init__(self) -> None:
        super().__init__(maxsize=MCP_STDIN_QUEUE_DEPTH)
        self.get_timeouts: list[float | None] = []

    def get(self, block: bool = True, timeout: float | None = None) -> tuple[str, object]:
        self.get_timeouts.append(timeout)
        return super().get(block=block, timeout=timeout)


class UnresponsiveMcpProcess:
    def __init__(self) -> None:
        self.stdin = io.StringIO()
        self.stdout = ControlledBlockingEof()
        self.stderr = io.StringIO()


class McpLifecycleTests(unittest.TestCase):
    def bounded_blocking_call(
        self,
        stream: ControlledBlockingEof,
        call: Callable[[], object],
    ) -> tuple[str, object]:
        outcome: list[tuple[str, object]] = []

        def invoke() -> None:
            try:
                result = call()
            except BaseException as exc:
                outcome.append(("error", exc))
            else:
                outcome.append(("return", result))

        worker = threading.Thread(target=invoke, name="ai-dememory-test-bounded-call", daemon=True)
        worker.start()
        try:
            entered = stream.entered.wait(timeout=1)
            worker.join(timeout=1)
            completed_before_release = not worker.is_alive()
        finally:
            stream.release.set()
            worker.join(timeout=1)
            reader = stream.reader_thread
            if reader is not None:
                reader.join(timeout=1)

        self.assertTrue(entered, "blocking reader was never entered")
        self.assertTrue(completed_before_release, "deadline did not release the blocked caller")
        self.assertFalse(worker.is_alive(), "bounded test worker did not terminate")
        self.assertTrue(stream.exited.is_set(), "blocking read did not return after release")
        self.assertIsNotNone(stream.reader_thread)
        self.assertFalse(stream.reader_thread.is_alive(), "blocking reader thread did not terminate")
        self.assertEqual(len(outcome), 1)
        return outcome[0]

    def test_owned_capture_check_preserves_child_diagnostics(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            run_owned_capture(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('stdout marker'); print('stderr marker', file=sys.stderr); raise SystemExit(7)",
                ],
                timeout_seconds=10,
                check=True,
            )

        self.assertEqual(caught.exception.returncode, 7)
        self.assertEqual(caught.exception.output, "stdout marker\n")
        self.assertEqual(caught.exception.stderr, "stderr marker\n")

    @unittest.skipUnless(os.name == "nt", "Windows Job Object ordering is Windows-specific")
    def test_windows_child_is_suspended_until_job_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "child-started.txt"
            original_assign = process_control._assign_windows_job
            marker_state_during_assignment: list[bool] = []

            def assign_and_observe(process: subprocess.Popen[object], job: int) -> None:
                marker_state_during_assignment.append(marker.exists())
                original_assign(process, job)

            with patch(
                "process_control._assign_windows_job",
                side_effect=assign_and_observe,
            ):
                returncode, timed_out, _pid = run_owned_process(
                    [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; "
                            f"Path({str(marker)!r}).write_text('started', encoding='utf-8')"
                        ),
                    ],
                    10,
                )
            marker_exists_after_run = marker.exists()

        self.assertEqual(marker_state_during_assignment, [False])
        self.assertEqual(returncode, 0)
        self.assertFalse(timed_out)
        self.assertTrue(marker_exists_after_run)

    def test_idle_timeout_bounds_and_explicit_disable(self) -> None:
        self.assertEqual(normalize_mcp_idle_timeout_seconds(0), 0)
        self.assertEqual(
            normalize_mcp_idle_timeout_seconds(MIN_MCP_IDLE_TIMEOUT_SECONDS),
            MIN_MCP_IDLE_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            normalize_mcp_idle_timeout_seconds(MAX_MCP_IDLE_TIMEOUT_SECONDS),
            MAX_MCP_IDLE_TIMEOUT_SECONDS,
        )
        for invalid in (-1, MIN_MCP_IDLE_TIMEOUT_SECONDS - 1, MAX_MCP_IDLE_TIMEOUT_SECONDS + 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_mcp_idle_timeout_seconds(invalid)
        with self.assertRaises(ValueError):
            normalize_mcp_idle_timeout_seconds(True)

    def test_stdio_lines_preserves_messages_and_eof(self) -> None:
        with patch("memory_mcp.sys.stdin", io.StringIO("first\nsecond\n")):
            self.assertEqual(
                list(stdio_lines(DEFAULT_MCP_IDLE_TIMEOUT_SECONDS)),
                ["first\n", "second\n"],
            )

    def test_stdio_lines_bounds_queue_and_request_frames(self) -> None:
        self.assertEqual(MCP_STDIN_QUEUE_DEPTH, 8)
        oversized = ("x" * (MAX_MCP_FRAME_CHARS + 1)) + "\n"
        with (
            patch("memory_mcp.sys.stdin", io.StringIO(oversized)),
            self.assertRaisesRegex(OSError, "MCP stdin reader failed"),
        ):
            list(stdio_lines(0))

    def test_stdio_lines_releases_abandoned_blocking_pipe(self) -> None:
        stream = ControlledBlockingEof()
        inbox = ObservedQueue()
        with (
            patch("memory_mcp.sys.stdin", stream),
            patch("memory_mcp.queue.Queue", return_value=inbox),
            patch("memory_mcp.normalize_mcp_idle_timeout_seconds", return_value=0.02),
        ):
            outcome = self.bounded_blocking_call(stream, lambda: list(stdio_lines(30)))
        self.assertEqual(outcome, ("return", []))
        self.assertEqual(inbox.get_timeouts, [0.02])

    def test_runtime_smoke_has_a_per_request_response_deadline(self) -> None:
        process = UnresponsiveMcpProcess()
        response_timeouts: list[float] = []

        def observed_response_line(process: object, timeout_seconds: float) -> str:
            response_timeouts.append(timeout_seconds)
            return response_line(process, timeout_seconds)  # type: ignore[arg-type]

        with (
            patch("mcp_runtime_smoke.MCP_RESPONSE_TIMEOUT_SECONDS", 0.02),
            patch("mcp_runtime_smoke.response_line", side_effect=observed_response_line),
        ):
            outcome_kind, outcome_value = self.bounded_blocking_call(
                process.stdout,
                lambda: rpc_response(  # type: ignore[arg-type]
                    process,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "memory.search", "arguments": {}},
                    },
                ),
            )
        self.assertEqual(outcome_kind, "error")
        self.assertIsInstance(outcome_value, SmokeError)
        self.assertRegex(str(outcome_value), "tools/call memory.search")
        self.assertEqual(len(response_timeouts), 1)
        self.assertGreater(response_timeouts[0], 0)
        self.assertLessEqual(response_timeouts[0], 0.020001)

    def test_generated_config_binds_profile_specific_idle_lease(self) -> None:
        rendered = build_mcp_config(
            "codex",
            "installed",
            Path("C:/vault"),
            idle_timeout_seconds=120,
        )
        args = tomllib.loads(rendered)["mcp_servers"]["ai-dememory"]["args"]

        self.assertIn(
            ["--idle-timeout-seconds", "120"],
            [args[index : index + 2] for index in range(len(args) - 1)],
        )
        self.assertEqual(args[-3:], ["--profile", "core", "--require-bound-root"])


if __name__ == "__main__":
    unittest.main()
