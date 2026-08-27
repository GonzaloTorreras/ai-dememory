#!/usr/bin/env python3
"""Launch an MCP server from client config and verify initialize/ping."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import queue
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import tomllib
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_dememory_tool.cli import build_mcp_config
from ai_dememory_tool.argument_safety import reject_duplicate_options
from install_smoke import MCP_INIT, MCP_PING
from memorylib import repo_root
from process_control import (
    attach_bounded_stderr_drain,
    bounded_stderr_tail,
    close_stdin_and_reap,
    join_bounded_stderr_drain,
    run_owned_capture,
    start_owned_process,
    terminate_process_tree,
)

MCP_TOOLS_LIST_ID = 3
MCP_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
MAX_TOOLS_LIST_PAGES = 20
ROOT_ENVIRONMENT_KEY = "AI_DEMEMORY_ROOT"
MCP_INTERACTIVE_TIMEOUT_SECONDS = 30.0
MAX_MCP_RESPONSE_LINE_CHARS = 1024 * 1024
MAX_MCP_INTERACTIVE_OUTPUT_CHARS = 4 * 1024 * 1024
MAX_MCP_REQUEST_CHARS = 64 * 1024
MCP_WRITER_SHUTDOWN_GRACE_SECONDS = 2.0


class ClientSmokeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClientSmokeResult:
    command: str
    args: list[str]
    cwd: str
    server_name: str | None
    initialized: bool
    pinged: bool
    enabled_tools_verified: bool
    enabled_tool_count: int


@dataclass
class _InteractiveMcpBudget:
    """One wall-clock and retained-output budget for an interactive session."""

    deadline: float
    output_chars: int = 0

    def remaining_seconds(self) -> float:
        return self.deadline - time.monotonic()

    def record_line(self, line: str) -> None:
        self.output_chars += len(line)
        if self.output_chars > MAX_MCP_INTERACTIVE_OUTPUT_CHARS:
            raise ClientSmokeError(
                "MCP client config interactive output exceeded its resource limit"
            )


@dataclass
class _StdinWriterState:
    """Coordinate a timed-out writer without closing its stream cross-thread."""

    stream: Any
    detach_requested: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)
    close_lock: threading.Lock = field(default_factory=threading.Lock)
    thread: threading.Thread | None = None
    closed: bool = False


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ClientSmokeError("MCP client config must be a JSON object")
    return data


def select_server_config(
    config: dict[str, Any] | str, server_name: str = "ai-dememory"
) -> tuple[dict[str, Any], str | None]:
    if isinstance(config, str):
        config = tomllib.loads(config)
    servers = config.get("mcpServers") or config.get("mcp_servers")
    if isinstance(servers, dict):
        server = servers.get(server_name)
        if not isinstance(server, dict):
            raise ClientSmokeError(f"mcpServers does not contain `{server_name}`")
        return server, server_name
    return config, None


def override_launch(
    config: dict[str, Any],
    command: str | None = None,
    command_args: list[str] | None = None,
    server_name: str = "ai-dememory",
) -> dict[str, Any]:
    if command is None and not command_args:
        return config
    data = json.loads(json.dumps(config))
    server, _ = select_server_config(data, server_name)
    if command is not None:
        server["command"] = command
    if command_args:
        server["args"] = [*command_args, "mcp", "--stdio"]
    return data


def bind_config_runtime_root(
    config: dict[str, Any],
    root: Path,
    server_name: str = "ai-dememory",
) -> dict[str, Any]:
    """Bind a supported loaded client fixture to the selected smoke vault."""
    data = json.loads(json.dumps(config))
    server, _ = select_server_config(data, server_name)
    command = server.get("command")
    if not isinstance(command, str) or not command:
        raise ClientSmokeError("MCP client config command must be a non-empty string")
    launcher = command.replace("\\", "/").rsplit("/", 1)[-1].casefold().rstrip(" .")
    if launcher in {"docker", "docker.exe"}:
        raise ClientSmokeError(
            "Loaded Docker MCP configs cannot be rebound safely; omit --config and "
            "use --mode docker so the selected --root generates the /memory mount"
        )
    args = server.get("args")
    if args is None:
        args = []
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ClientSmokeError("MCP client config args must be an array of strings")
    if any(
        argument.casefold() == "--root" or argument.casefold().startswith("--root=")
        for argument in args
    ):
        raise ClientSmokeError(
            "Loaded MCP client config must not contain --root; select the smoke vault "
            "with mcp-client-smoke --root"
        )
    env = server.get("env")
    if env is None:
        env = {}
    if not isinstance(env, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in env.items()
    ):
        raise ClientSmokeError("MCP client config env must be an object of strings")
    normalized_env = _without_root_environment_aliases(env)
    server["env"] = {**normalized_env, ROOT_ENVIRONMENT_KEY: str(root)}
    return data


def _without_root_environment_aliases(env: dict[str, str]) -> dict[str, str]:
    """Remove spellings that Windows aliases to the canonical root key."""

    return {
        key: value
        for key, value in env.items()
        # Windows folds the dotless-i spelling ``aı_dememory_root`` onto
        # the canonical variable when it builds a child environment. Unicode
        # uppercasing matches that boundary; casefolding does not.
        if key.upper() != ROOT_ENVIRONMENT_KEY
    }


def merge_launch_environment(configured_env: dict[str, str]) -> dict[str, str]:
    """Merge host/config environments without reintroducing a root alias."""

    configured_roots = {
        value
        for key, value in configured_env.items()
        if key.upper() == ROOT_ENVIRONMENT_KEY
    }
    if len(configured_roots) > 1:
        raise ClientSmokeError(
            "MCP client config contains conflicting AI_DEMEMORY_ROOT environment aliases"
        )
    selected_root = next(iter(configured_roots), None)
    merged = {**dict_env(), **configured_env}
    if selected_root is None:
        return merged
    launch_env = _without_root_environment_aliases(merged)
    launch_env[ROOT_ENVIRONMENT_KEY] = selected_root
    return launch_env


def run_client_config_smoke(config: dict[str, Any] | str, cwd: Path, server_name: str = "ai-dememory") -> ClientSmokeResult:
    server, selected_name = select_server_config(config, server_name)
    command = server.get("command")
    args = server.get("args") or []
    env = server.get("env") or {}
    configured_cwd = server.get("cwd")
    if not isinstance(command, str) or not command:
        raise ClientSmokeError("MCP client config command must be a non-empty string")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ClientSmokeError("MCP client config args must be an array of strings")
    if not isinstance(env, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items()):
        raise ClientSmokeError("MCP client config env must be an object of strings")
    if configured_cwd is not None and not isinstance(configured_cwd, str):
        raise ClientSmokeError("MCP client config cwd must be a string when present")
    enabled_tools = server.get("enabled_tools")
    if enabled_tools is not None and (
        not isinstance(enabled_tools, list) or not all(isinstance(tool, str) for tool in enabled_tools)
    ):
        raise ClientSmokeError("MCP client config enabled_tools must be an array of strings when present")
    launch_cwd = Path(configured_cwd) if configured_cwd else cwd

    launch_env = merge_launch_environment(env)
    stdout = run_mcp_batch(command, args, launch_cwd, launch_env, [MCP_INIT, MCP_INITIALIZED, MCP_PING])
    assert_mcp_initialize_and_ping(stdout)
    enabled_tools_verified = False
    enabled_tool_count = 0
    if enabled_tools:
        tools_stdout = run_tools_list_pages(command, args, launch_cwd, launch_env)
        verify_enabled_tools(tools_stdout, enabled_tools)
        enabled_tools_verified = True
        enabled_tool_count = len(enabled_tools)
    return ClientSmokeResult(
        command=command,
        args=args,
        cwd=str(launch_cwd),
        server_name=selected_name,
        initialized=True,
        pinged=True,
        enabled_tools_verified=enabled_tools_verified,
        enabled_tool_count=enabled_tool_count,
    )


def run_mcp_batch(
    command: str,
    args: list[str],
    launch_cwd: Path,
    env: dict[str, str],
    requests: list[dict[str, Any]],
) -> str:
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    try:
        completed = run_owned_capture(
            [command, *args],
            cwd=launch_cwd,
            env=env,
            input_text=payload,
            timeout_seconds=30,
        )
    except FileNotFoundError as exc:
        raise ClientSmokeError(f"MCP client config command not found: {command}") from exc
    if completed.returncode != 0:
        raise ClientSmokeError(
            f"MCP client config command failed with exit {completed.returncode}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def json_rpc_results_by_id(stdout: str) -> dict[int, dict[str, Any]]:
    results: dict[int, dict[str, Any]] = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        response = json.loads(line)
        if not isinstance(response, dict):
            raise ClientSmokeError("MCP client config command returned a non-object JSON-RPC message")
        response_id = response.get("id")
        if response_id is None:
            continue
        if not isinstance(response_id, int):
            raise ClientSmokeError("MCP client config command returned a response with non-integer id")
        if "error" in response:
            raise ClientSmokeError(f"MCP request {response_id} failed: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ClientSmokeError(f"MCP request {response_id} returned a non-object result")
        results[response_id] = result
    return results


def assert_mcp_initialize_and_ping(stdout: str) -> None:
    results = json_rpc_results_by_id(stdout)
    init = results.get(1) or {}
    ping = results.get(2)
    if init.get("protocolVersion") != "2025-11-25":
        raise ClientSmokeError("MCP initialize did not negotiate 2025-11-25")
    if ping != {}:
        raise ClientSmokeError("MCP ping did not return an empty result")


@contextmanager
def start_mcp_process(
    command: str,
    args: list[str],
    launch_cwd: Path,
    env: dict[str, str],
) -> Iterator[subprocess.Popen[str]]:
    process_scope = start_owned_process(
        [command, *args],
        cwd=launch_cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    entered = False
    try:
        with process_scope as process:
            entered = True
            attach_bounded_stderr_drain(process)
            try:
                yield process
            finally:
                stop_mcp_process(process)
    except FileNotFoundError as exc:
        if entered:
            raise
        # The child is created on context entry, not when process_scope is
        # constructed, so translate the error around the complete `with`.
        raise ClientSmokeError(f"MCP client config command not found: {command}") from exc


def stop_mcp_process(process: subprocess.Popen[str]) -> None:
    # A writer that outlived its bounded termination attempt may still own the
    # TextIOWrapper lock. Detach it before the generic cleanup tries stdin.close;
    # the writer closes its captured stream itself if it ever returns.
    _detach_live_stdin_writer(process)
    cleanup_complete = False
    drain_complete = False
    try:
        cleanup_complete = close_stdin_and_reap(process, grace_seconds=2)
    finally:
        drain_complete = join_bounded_stderr_drain(process, timeout=2)
    if not cleanup_complete:
        # The child may still own the pipe endpoints. Closing a buffered stream
        # while its drain holds the stream lock can block forever, so fail
        # promptly and leave final reclamation to the OS/supervisor boundary.
        raise ClientSmokeError("MCP client process tree did not terminate cleanly")
    if not drain_complete:
        raise ClientSmokeError("MCP client stderr drain did not terminate cleanly")
    for pipe in (process.stdout, process.stderr):
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass


def _close_detached_writer_stream(state: _StdinWriterState) -> None:
    """Close a detached stream exactly once, but only after its writer exits."""

    if not state.detach_requested.is_set() or not state.finished.is_set():
        return
    with state.close_lock:
        if state.closed:
            return
        state.closed = True
        try:
            state.stream.close()
        except (OSError, ValueError):
            pass


def _detach_live_stdin_writer(process: subprocess.Popen[str]) -> bool:
    """Make generic cleanup skip stdin while a bounded writer still owns it."""

    state = getattr(process, "_ai_dememory_stdin_writer_state", None)
    if not isinstance(state, _StdinWriterState):
        return False
    writer = state.thread
    if writer is None or not writer.is_alive():
        return False
    state.detach_requested.set()
    if process.stdin is state.stream:
        process.stdin = None
    # Covers the race where the writer finished between is_alive() and detach.
    _close_detached_writer_stream(state)
    return True


def read_response_line(
    process: subprocess.Popen[str],
    timeout_seconds: float,
    *,
    max_chars: int = MAX_MCP_RESPONSE_LINE_CHARS,
) -> str:
    if process.stdout is None:
        raise ClientSmokeError("MCP client config command did not expose stdout")
    if timeout_seconds <= 0:
        raise ClientSmokeError("MCP client config interactive session timed out")
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    lines: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def read_line() -> None:
        try:
            lines.put(("line", process.stdout.readline(max_chars + 1)))
        except BaseException as exc:  # pragma: no cover - platform pipe failure
            lines.put(("error", exc))

    thread = threading.Thread(
        target=read_line,
        name="ai-dememory-mcp-client-smoke-stdout",
        daemon=True,
    )
    thread.start()
    try:
        kind, value = lines.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise ClientSmokeError(
            "MCP client config interactive session timed out waiting for response"
        ) from exc
    if kind == "error":
        raise ClientSmokeError("MCP client config stdout reader failed") from value
    line = str(value)
    if not line:
        stderr = bounded_stderr_tail(process)
        raise ClientSmokeError(f"MCP client config command returned no response. stderr={stderr}")
    if len(line) > max_chars:
        raise ClientSmokeError(
            "MCP client config response line exceeded its resource limit"
        )
    return line


def _write_mcp_message(
    process: subprocess.Popen[str],
    message: dict[str, Any],
    budget: _InteractiveMcpBudget,
) -> None:
    """Write one bounded message without letting a full pipe defeat the deadline."""

    if process.stdin is None:
        raise ClientSmokeError("MCP client config command did not expose stdin")
    stdin = process.stdin
    payload = json.dumps(message) + "\n"
    if len(payload) > MAX_MCP_REQUEST_CHARS:
        raise ClientSmokeError("MCP client config request exceeded its resource limit")
    remaining = budget.remaining_seconds()
    if remaining <= 0:
        raise ClientSmokeError(
            "MCP client config interactive session exceeded its total deadline"
        )
    result: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)
    state = _StdinWriterState(stream=stdin)

    def write_message() -> None:
        try:
            stdin.write(payload)
            stdin.flush()
            result.put(("ok", None))
        except BaseException as exc:  # pragma: no cover - platform pipe failure
            result.put(("error", exc))
        finally:
            state.finished.set()
            _close_detached_writer_stream(state)

    writer = threading.Thread(
        target=write_message,
        name="ai-dememory-mcp-client-smoke-stdin",
        daemon=True,
    )
    state.thread = writer
    setattr(process, "_ai_dememory_stdin_writer_state", state)
    writer.start()
    try:
        kind, value = result.get(timeout=remaining)
    except queue.Empty as exc:
        reaped = terminate_process_tree(
            process,
            grace_seconds=MCP_WRITER_SHUTDOWN_GRACE_SECONDS,
        )
        writer.join(timeout=MCP_WRITER_SHUTDOWN_GRACE_SECONDS)
        writer_alive = writer.is_alive()
        if writer_alive:
            _detach_live_stdin_writer(process)
        if not reaped or writer_alive:
            raise ClientSmokeError(
                "MCP client config timed-out writer could not be reclaimed"
            ) from exc
        raise ClientSmokeError(
            "MCP client config interactive session timed out writing a request"
        ) from exc
    if kind == "error":
        raise ClientSmokeError("MCP client config stdin writer failed") from value
    if budget.remaining_seconds() <= 0:
        raise ClientSmokeError(
            "MCP client config interactive session exceeded its total deadline"
        )


def rpc_response(
    process: subprocess.Popen[str],
    request: dict[str, Any],
    budget: _InteractiveMcpBudget,
) -> tuple[dict[str, Any], str]:
    request_id = request.get("id")
    if not isinstance(request_id, int):
        raise ClientSmokeError("MCP client smoke requests must use integer ids")
    _write_mcp_message(process, request, budget)
    while True:
        remaining = budget.remaining_seconds()
        if remaining <= 0:
            raise ClientSmokeError(
                "MCP client config interactive session exceeded its total deadline"
            )
        line = read_response_line(process, remaining)
        budget.record_line(line)
        response = json.loads(line)
        if not isinstance(response, dict):
            raise ClientSmokeError("MCP client config command returned a non-object JSON-RPC message")
        response_id = response.get("id")
        if response_id is None:
            continue
        if response_id != request_id:
            continue
        if "error" in response:
            raise ClientSmokeError(f"{request.get('method')} failed: {response['error']}")
        return response, line


def send_notification(
    process: subprocess.Popen[str],
    notification: dict[str, Any],
    budget: _InteractiveMcpBudget,
) -> None:
    _write_mcp_message(process, notification, budget)


def rpc_result(
    process: subprocess.Popen[str],
    request: dict[str, Any],
    budget: _InteractiveMcpBudget,
) -> tuple[dict[str, Any], str]:
    response, line = rpc_response(process, request, budget)
    result = response.get("result")
    if not isinstance(result, dict):
        raise ClientSmokeError(f"{request.get('method')} returned a non-object result")
    return result, line


def run_tools_list_pages(command: str, args: list[str], launch_cwd: Path, env: dict[str, str]) -> str:
    stdout_parts: list[str] = []
    cursor: str | None = None
    budget = _InteractiveMcpBudget(
        deadline=time.monotonic() + MCP_INTERACTIVE_TIMEOUT_SECONDS
    )

    def exercise_process(process: subprocess.Popen[str]) -> str:
        nonlocal cursor
        init, init_line = rpc_result(process, MCP_INIT, budget)
        if init.get("protocolVersion") != "2025-11-25":
            raise ClientSmokeError("MCP client config initialize negotiated the wrong protocol")
        stdout_parts.append(init_line)
        send_notification(process, MCP_INITIALIZED, budget)
        ping, ping_line = rpc_result(process, MCP_PING, budget)
        if ping != {}:
            raise ClientSmokeError("MCP client config ping did not return an empty result")
        stdout_parts.append(ping_line)
        page = 0
        while True:
            if page >= MAX_TOOLS_LIST_PAGES:
                raise ClientSmokeError("MCP tools/list pagination exceeded safety limit")
            request = tools_list_request(MCP_TOOLS_LIST_ID + page, cursor)
            result, line = rpc_result(process, request, budget)
            stdout_parts.append(line)
            cursor = result.get("nextCursor")
            if cursor is None:
                return "".join(stdout_parts)
            if not isinstance(cursor, str) or not cursor:
                raise ClientSmokeError("MCP tools/list response returned invalid nextCursor")
            page += 1
    with start_mcp_process(command, args, launch_cwd, env) as process:
        return exercise_process(process)


def tools_list_request(request_id: int, cursor: str | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": "tools/list"}
    if cursor is not None:
        request["params"] = {"cursor": cursor}
    return request


def tools_list_results(stdout: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        response = json.loads(line)
        result = response.get("result") if isinstance(response, dict) else None
        if isinstance(result, dict) and "tools" in result:
            results.append(result)
    return results


def next_tools_cursor(stdout: str) -> str | None:
    results = tools_list_results(stdout)
    if not results:
        raise ClientSmokeError("MCP client config enabled_tools could not be verified: missing tools/list response")
    cursor = results[-1].get("nextCursor")
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not cursor:
        raise ClientSmokeError("MCP tools/list response returned invalid nextCursor")
    return cursor


def verify_enabled_tools(stdout: str, enabled_tools: list[str]) -> None:
    results = tools_list_results(stdout)
    if not results:
        raise ClientSmokeError("MCP client config enabled_tools could not be verified: missing tools/list response")
    if results[-1].get("nextCursor") is not None:
        raise ClientSmokeError("MCP tools/list pagination did not reach the final page")
    tool_names: set[str] = set()
    for result in results:
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise ClientSmokeError("MCP tools/list response missing tools array")
        tool_names.update(tool.get("name") for tool in tools if isinstance(tool, dict) and isinstance(tool.get("name"), str))
    missing = sorted(set(enabled_tools) - tool_names)
    if missing:
        raise ClientSmokeError("MCP client config enabled_tools missing from server tools/list: " + ", ".join(missing))


def dict_env() -> dict[str, str]:
    import os

    return dict(os.environ)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", default=None, help="Initialized vault root used by the launched MCP server.")
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Existing reviewed non-Docker MCP client config JSON to launch. It must not "
            "contain --root; this command binds the selected smoke vault."
        ),
    )
    parser.add_argument("--server-name", default="ai-dememory", help="Server name inside mcpServers.")
    parser.add_argument("--client", choices=("generic", "codex", "claude"), default="codex")
    parser.add_argument("--mode", choices=("installed", "docker"), default="installed")
    parser.add_argument("--command", default=None, help="Override the command clients should launch.")
    parser.add_argument("--command-arg", action="append", default=[], help="Extra argument before `mcp --stdio`; repeatable.")
    parser.add_argument("--image", default="ai-dememory:local", help="Docker image for generated Docker config.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    raw_argv = list(argv if argv is not None else sys.argv[1:])
    reject_duplicate_options(
        parser,
        raw_argv,
        ("--root", "--config", "--server-name", "--client", "--mode", "--command", "--image", "--json"),
    )
    args = parser.parse_args(raw_argv)

    root = repo_root(args.root)
    try:
        if args.config:
            config = bind_config_runtime_root(
                override_launch(
                    load_config(Path(args.config)),
                    command=args.command,
                    command_args=args.command_arg,
                    server_name=args.server_name,
                ),
                root,
                server_name=args.server_name,
            )
        else:
            config = build_mcp_config(
                args.client,
                args.mode,
                root,
                command=args.command or "ai-dememory",
                command_args=args.command_arg,
                image=args.image,
            )
        result = run_client_config_smoke(config, root, server_name=args.server_name)
    except (ClientSmokeError, json.JSONDecodeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        name = f" `{result.server_name}`" if result.server_name else ""
        print(f"MCP client config{name} initialized and pinged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
