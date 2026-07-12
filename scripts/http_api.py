#!/usr/bin/env python3
"""Run a dependency-free local REST API for ai-dememory."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "mcp" / "server"
if str(MCP_SERVER) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER))

from graph_memory import build_graph
from index_memory import default_db_path, rebuild_index
from ai_dememory_tool.mcp_server.memory_mcp import get_memory, write_proposal
from memorylib import repo_root
from search_memory import result_to_dict, search
from secret_scan import scan_paths


MAX_BODY_BYTES = 64 * 1024
MAX_SEARCH_LIMIT = 50
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def make_handler(root: Path, api_key: str | None = None, log_requests: bool = True):
    class CodexMemoryHandler(BaseHTTPRequestHandler):
        server_version = "ai-dememory-api/1"

        def do_GET(self) -> None:  # noqa: N802
            self.handle_request("GET")

        def do_POST(self) -> None:  # noqa: N802
            self.handle_request("POST")

        def log_message(self, format: str, *args: Any) -> None:
            if not log_requests:
                return
            print(f"{self.address_string()} - {format % args}", file=sys.stderr)

        def handle_request(self, method: str) -> None:
            try:
                if api_key:
                    require_api_key(self.headers.get("X-API-Key"), self.headers.get("Authorization"), api_key)
                parsed = urlparse(self.path)
                if method == "GET":
                    result = route_get(root, parsed.path, parse_qs(parsed.query))
                elif method == "POST":
                    result = route_post(root, parsed.path, read_json_body(self))
                else:
                    raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")
                self.write_json(HTTPStatus.OK, result)
            except ApiError as exc:
                self.write_json(exc.status, {"error": exc.message})
            except FileNotFoundError as exc:
                self.write_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except PermissionError as exc:
                self.write_json(HTTPStatus.FORBIDDEN, {"error": str(exc)})
            except ValueError as exc:
                self.write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:
                self.write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"internal error: {type(exc).__name__}"})

        def write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return CodexMemoryHandler


def require_api_key(header_value: str | None, auth_value: str | None, expected: str) -> None:
    bearer = ""
    if auth_value and auth_value.lower().startswith("bearer "):
        bearer = auth_value[7:].strip()
    if header_value == expected or bearer == expected:
        return
    raise ApiError(HTTPStatus.UNAUTHORIZED, "valid X-API-Key or Bearer token required")


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    raw_length = handler.headers.get("Content-Length")
    try:
        length = int(raw_length or "0")
    except ValueError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid Content-Length") from exc
    if length > MAX_BODY_BYTES:
        raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, f"request body exceeds {MAX_BODY_BYTES} bytes")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, "request body must be JSON") from exc
    if not isinstance(parsed, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "request body must be a JSON object")
    return parsed


def route_get(root: Path, path: str, query: dict[str, list[str]]) -> dict[str, Any]:
    if path in {"/health", "/api/health"}:
        return {"status": "ok", "root": str(root), "index_exists": default_db_path(root).exists()}
    if path in {"/search", "/api/search"}:
        text = first(query, "query") or first(query, "q")
        if not text:
            raise ApiError(HTTPStatus.BAD_REQUEST, "query is required")
        limit = normalize_limit(first(query, "limit"))
        include_sensitive = parse_bool(first(query, "include_sensitive"))
        results = search(text, root, limit=limit, include_sensitive=include_sensitive)
        return {"results": [result_to_dict(result) for result in results]}
    if path in {"/graph", "/api/graph"}:
        return build_graph(root, include_sensitive=parse_bool(first(query, "include_sensitive")))
    if path.startswith("/memories/") or path.startswith("/api/memories/"):
        memory_id = unquote(path.rsplit("/", 1)[-1])
        return get_memory(root, memory_id, None, include_sensitive=parse_bool(first(query, "include_sensitive")))
    raise ApiError(HTTPStatus.NOT_FOUND, "unknown endpoint")


def route_post(root: Path, path: str, body: dict[str, Any]) -> dict[str, Any]:
    if path in {"/reindex", "/api/reindex"}:
        findings = scan_paths(root)
        if findings:
            raise ApiError(HTTPStatus.BAD_REQUEST, "secret scan failed before reindex")
        db_path, count = rebuild_index(root)
        return {"path": db_path.relative_to(root).as_posix(), "count": count}
    if path in {"/proposals", "/api/proposals"}:
        return write_proposal(
            root,
            title=str(body.get("title") or ""),
            content=str(body.get("content") or ""),
            project=body.get("project"),
            tags=body.get("tags") or [],
            source_kind=str(body.get("source_kind") or "codex"),
            source_ref=body.get("source_ref"),
        )
    raise ApiError(HTTPStatus.NOT_FOUND, "unknown endpoint")


def first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def normalize_limit(value: str | None) -> int:
    try:
        parsed = int(value or "10")
    except ValueError:
        return 10
    return max(1, min(parsed, MAX_SEARCH_LIMIT))


def parse_bool(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


def serve(
    root: Path,
    host: str,
    port: int,
    api_key: str | None = None,
    log_requests: bool = True,
) -> ThreadingHTTPServer:
    handler = make_handler(root, api_key, log_requests=log_requests)
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to loopback only.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    parser.add_argument("--api-key", default=None, help="Optional API key. Defaults to AI_DEMEMORY_API_KEY.")
    parser.add_argument(
        "--allow-unauthenticated-network",
        action="store_true",
        help="Allow non-loopback bind without an API key. Not recommended.",
    )
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    api_key = args.api_key or os.environ.get("AI_DEMEMORY_API_KEY")
    if not is_loopback_host(args.host) and not api_key and not args.allow_unauthenticated_network:
        print(
            "Refusing unauthenticated non-loopback API bind. "
            "Set AI_DEMEMORY_API_KEY or pass --allow-unauthenticated-network.",
            file=sys.stderr,
        )
        return 2

    httpd = serve(root, args.host, args.port, api_key=api_key)
    print(f"ai-dememory API listening on http://{args.host}:{httpd.server_address[1]}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ai-dememory API.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
