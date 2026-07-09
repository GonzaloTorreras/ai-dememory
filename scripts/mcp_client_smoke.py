#!/usr/bin/env python3
"""Launch an MCP server from client config and verify initialize/ping."""

from __future__ import annotations

import argparse
import queue
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_dememory_tool.cli import build_mcp_config
from install_smoke import MCP_INIT, MCP_PING
from memorylib import repo_root

MCP_TOOLS_LIST_ID = 3
MCP_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
MAX_TOOLS_LIST_PAGES = 20


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


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ClientSmokeError("MCP client config must be a JSON object")
    return data


def select_server_config(config: dict[str, Any], server_name: str = "ai-dememory") -> tuple[dict[str, Any], str | None]:
    servers = config.get("mcpServers")
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


def run_client_config_smoke(config: dict[str, Any], cwd: Path, server_name: str = "ai-dememory") -> ClientSmokeResult:
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

    launch_env = {**dict_env(), **env}
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
        completed = subprocess.run(
            [command, *args],
            cwd=launch_cwd,
            env=env,
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
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


def start_mcp_process(
    command: str,
    args: list[str],
    launch_cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    try:
        return subprocess.Popen(
            [command, *args],
            cwd=launch_cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ClientSmokeError(f"MCP client config command not found: {command}") from exc


def stop_mcp_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    for pipe in (process.stdout, process.stderr):
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass


def read_response_line(process: subprocess.Popen[str], timeout: int = 30) -> str:
    if process.stdout is None:
        raise ClientSmokeError("MCP client config command did not expose stdout")
    lines: queue.Queue[str] = queue.Queue(maxsize=1)

    def read_line() -> None:
        lines.put(process.stdout.readline())

    thread = threading.Thread(target=read_line, daemon=True)
    thread.start()
    try:
        line = lines.get(timeout=timeout)
    except queue.Empty as exc:
        stop_mcp_process(process)
        raise ClientSmokeError("MCP client config command timed out waiting for response") from exc
    if not line:
        stderr = process.stderr.read() if process.stderr and process.poll() is not None else ""
        raise ClientSmokeError(f"MCP client config command returned no response. stderr={stderr}")
    return line


def rpc_response(process: subprocess.Popen[str], request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if process.stdin is None:
        raise ClientSmokeError("MCP client config command did not expose stdin")
    request_id = request.get("id")
    if not isinstance(request_id, int):
        raise ClientSmokeError("MCP client smoke requests must use integer ids")
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    while True:
        line = read_response_line(process)
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


def send_notification(process: subprocess.Popen[str], notification: dict[str, Any]) -> None:
    if process.stdin is None:
        raise ClientSmokeError("MCP client config command did not expose stdin")
    process.stdin.write(json.dumps(notification) + "\n")
    process.stdin.flush()


def rpc_result(process: subprocess.Popen[str], request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    response, line = rpc_response(process, request)
    result = response.get("result")
    if not isinstance(result, dict):
        raise ClientSmokeError(f"{request.get('method')} returned a non-object result")
    return result, line


def run_tools_list_pages(command: str, args: list[str], launch_cwd: Path, env: dict[str, str]) -> str:
    stdout_parts: list[str] = []
    cursor: str | None = None
    process = start_mcp_process(command, args, launch_cwd, env)
    try:
        init, init_line = rpc_result(process, MCP_INIT)
        if init.get("protocolVersion") != "2025-11-25":
            raise ClientSmokeError("MCP client config initialize negotiated the wrong protocol")
        stdout_parts.append(init_line)
        send_notification(process, MCP_INITIALIZED)
        ping, ping_line = rpc_result(process, MCP_PING)
        if ping != {}:
            raise ClientSmokeError("MCP client config ping did not return an empty result")
        stdout_parts.append(ping_line)
        page = 0
        while True:
            if page >= MAX_TOOLS_LIST_PAGES:
                raise ClientSmokeError("MCP tools/list pagination exceeded safety limit")
            request = tools_list_request(MCP_TOOLS_LIST_ID + page, cursor)
            result, line = rpc_result(process, request)
            stdout_parts.append(line)
            cursor = result.get("nextCursor")
            if cursor is None:
                return "".join(stdout_parts)
            if not isinstance(cursor, str) or not cursor:
                raise ClientSmokeError("MCP tools/list response returned invalid nextCursor")
            page += 1
    finally:
        stop_mcp_process(process)


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Vault or checkout root. Defaults to this repo.")
    parser.add_argument("--config", default=None, help="Existing MCP client config JSON to launch.")
    parser.add_argument("--server-name", default="ai-dememory", help="Server name inside mcpServers.")
    parser.add_argument("--client", choices=("generic", "codex", "claude"), default="codex")
    parser.add_argument("--mode", choices=("installed", "docker"), default="installed")
    parser.add_argument("--command", default=None, help="Override the command clients should launch.")
    parser.add_argument("--command-arg", action="append", default=[], help="Extra argument before `mcp --stdio`; repeatable.")
    parser.add_argument("--image", default="ai-dememory:local", help="Docker image for generated Docker config.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        if args.config:
            config = override_launch(
                load_config(Path(args.config)),
                command=args.command,
                command_args=args.command_arg,
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
