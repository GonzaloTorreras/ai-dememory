"""A bounded, foreground-only MCP stdio bridge."""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from typing import Any, BinaryIO, TextIO

from ai_dememory import __version__
from ai_dememory.core import CoreServices
from ai_dememory.models import ModuleManifest


MAX_REQUEST_BYTES = 1_048_576


def get_manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="mcp",
        version="1",
        summary="Local stdio MCP bridge with five bounded tools.",
        capabilities=("search", "get", "context", "propose", "status"),
        resource_budget={"network": False, "child_processes": 0, "persistent": False},
    )


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "memory.search",
            "description": "Search canonical local memories.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory.get",
            "description": "Read one canonical memory by id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 256, "maximum": 50000, "default": 20000},
                },
                "required": ["memory_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory.context",
            "description": "Build bounded context from relevant canonical memories.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    "max_chars": {"type": "integer", "minimum": 256, "maximum": 20000, "default": 4000},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory.propose",
            "description": "Create a proposal for human review; never writes canonical memory.",
            "inputSchema": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
                "required": ["title", "content"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory.status",
            "description": "Report vault, index, proposal and resource state.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]


def call_tool(services: CoreServices, name: str, arguments: dict[str, Any]) -> Any:
    if name == "memory.search":
        return services.search(str(arguments.get("query", "")), int(arguments.get("limit", 5)))
    if name == "memory.get":
        return services.get(
            str(arguments.get("memory_id", "")), int(arguments.get("max_chars", 20_000))
        )
    if name == "memory.context":
        return services.context(
            str(arguments.get("query", "")),
            int(arguments.get("limit", 5)),
            int(arguments.get("max_chars", 4000)),
        )
    if name == "memory.propose":
        return services.propose(str(arguments.get("title", "")), str(arguments.get("content", "")))
    if name == "memory.status":
        return services.status()
    raise ValueError(f"Unknown MCP tool: {name}")


def _response(request_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def handle_request(services: CoreServices, request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    if request_id is None:
        return None
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "ai-dememory", "version": __version__},
            },
        )
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": tool_definitions()})
    if method == "tools/call":
        params = request.get("params") or {}
        if not isinstance(params, dict):
            return _response(
                request_id, error={"code": -32602, "message": "params must be an object"}
            )
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _response(
                request_id, error={"code": -32602, "message": "arguments must be an object"}
            )
        try:
            value = call_tool(services, str(params.get("name", "")), arguments)
            return _response(
                request_id,
                {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]},
            )
        except (TypeError, ValueError, OverflowError, OSError, sqlite3.Error) as exc:
            return _response(request_id, error={"code": -32602, "message": str(exc)})
    return _response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})


def serve(
    services: CoreServices,
    argv: list[str] | None = None,
    input_stream: TextIO | BinaryIO | None = None,
    output_stream: TextIO | BinaryIO | None = None,
) -> int:
    if argv:
        raise ValueError("The mcp module does not accept runtime arguments")
    source = input_stream or getattr(sys.stdin, "buffer", sys.stdin)
    output = output_stream or getattr(sys.stdout, "buffer", sys.stdout)
    while True:
        raw = source.readline(MAX_REQUEST_BYTES + 1)
        if not raw:
            break
        raw_bytes = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        complete = raw.endswith(b"\n") if isinstance(raw, bytes) else raw.endswith("\n")
        if len(raw_bytes) > MAX_REQUEST_BYTES or (not complete and len(raw) > MAX_REQUEST_BYTES):
            if not complete:
                while True:
                    remainder = source.readline(MAX_REQUEST_BYTES + 1)
                    if not remainder:
                        break
                    if remainder.endswith(b"\n") if isinstance(remainder, bytes) else remainder.endswith("\n"):
                        break
            response = _response(None, error={"code": -32600, "message": "Request exceeds size limit"})
        else:
            try:
                line = raw_bytes.decode("utf-8")
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Request must be a JSON object")
                response = handle_request(services, request)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
                response = _response(None, error={"code": -32700, "message": str(exc)})
        if response is not None:
            serialized = json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n"
            if isinstance(output, io.TextIOBase):
                output.write(serialized)
            else:
                output.write(serialized.encode("utf-8"))
            output.flush()
    return 0
