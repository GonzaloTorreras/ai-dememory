#!/usr/bin/env python3
"""Run a dependency-free local REST API for ai-dememory."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import threading
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "mcp" / "server"
if str(ROOT) not in sys.path:
    # Direct source-script invocation must import only the trusted checkout,
    # never a package supplied by the current working directory.
    sys.path.insert(0, str(ROOT))
if str(MCP_SERVER) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER))

from graph_memory import build_graph
from index_memory import default_db_path, rebuild_index
from ai_dememory_tool.mcp_server.memory_mcp import get_memory, write_proposal
from ai_dememory_tool.argument_safety import duplicate_options
from ai_dememory_tool.vault_binding import VaultBindingError, resolve_runtime_vault
from search_memory import result_to_dict, search
from secret_scan import scan_paths


MAX_BODY_BYTES = 64 * 1024
MAX_SEARCH_LIMIT = 50
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_REQUEST_THREADS = 8
REQUEST_TIMEOUT_SECONDS = 15
MUTATION_INTENT_HEADER = "X-AI-DeMemory-Intent"
MUTATION_INTENT_VALUE = "reviewed-local-write"
RUNTIME_VAULT_ROOT_HELP = (
    "Vault root. Resolution order: --root, AI_DEMEMORY_ROOT, then a saved local "
    "default selected with `ai-dememory vault use <absolute-vault-path>`; the command never "
    "uses the working directory to discover a vault."
)


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = MAX_REQUEST_THREADS

    def __init__(self, *args: Any, max_request_threads: int = MAX_REQUEST_THREADS, **kwargs: Any):
        self._request_slots = threading.BoundedSemaphore(max_request_threads)
        super().__init__(*args, **kwargs)

    def process_request(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        self._request_slots.acquire()
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            raise

    def process_request_thread(self, request: socket.socket, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


def make_handler(
    root: Path,
    api_key: str | None = None,
    log_requests: bool = True,
    bind_host: str = "127.0.0.1",
):
    class CodexMemoryHandler(BaseHTTPRequestHandler):
        server_version = "ai-dememory-api/1"

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)

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
                require_safe_request_context(
                    bind_host,
                    self.headers.get("Host"),
                    self.headers.get("Origin"),
                    self.headers.get("Sec-Fetch-Site"),
                )
                if api_key:
                    require_api_key(self.headers.get("X-API-Key"), self.headers.get("Authorization"), api_key)
                parsed = urlparse(self.path)
                if method == "GET":
                    result = route_get(root, parsed.path, parse_qs(parsed.query))
                elif method == "POST":
                    # Consume the bounded request body before rejecting mutation
                    # metadata. Closing a Windows socket with unread client data
                    # can reset the connection before the JSON error is received.
                    raw_body = read_request_body(self)
                    require_mutation_intent(self.headers.get(MUTATION_INTENT_HEADER))
                    result = route_post(root, parsed.path, parse_json_body(self, raw_body))
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
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass

    return CodexMemoryHandler


def require_api_key(header_value: str | None, auth_value: str | None, expected: str) -> None:
    bearer = ""
    if auth_value and auth_value.lower().startswith("bearer "):
        bearer = auth_value[7:].strip()
    if header_value == expected or bearer == expected:
        return
    raise ApiError(HTTPStatus.UNAUTHORIZED, "valid X-API-Key or Bearer token required")


def header_hostname(host_header: str | None) -> str:
    if not host_header:
        return ""
    try:
        return (urlparse(f"//{host_header}").hostname or "").casefold()
    except ValueError:
        return ""


def require_safe_request_context(
    bind_host: str,
    host_header: str | None,
    origin: str | None,
    fetch_site: str | None,
) -> None:
    request_host = header_hostname(host_header)
    if not request_host:
        raise ApiError(HTTPStatus.BAD_REQUEST, "valid Host header required")
    if is_loopback_host(bind_host) and request_host not in LOOPBACK_HOSTS:
        raise ApiError(HTTPStatus.MISDIRECTED_REQUEST, "Host header must address loopback")
    if str(fetch_site or "").casefold() == "cross-site":
        raise ApiError(HTTPStatus.FORBIDDEN, "cross-site browser requests are not allowed")
    if origin:
        try:
            origin_host = (urlparse(origin).hostname or "").casefold()
        except ValueError as exc:
            raise ApiError(HTTPStatus.FORBIDDEN, "invalid Origin header") from exc
        if not origin_host or origin_host != request_host:
            raise ApiError(HTTPStatus.FORBIDDEN, "cross-origin browser requests are not allowed")


def require_mutation_intent(value: str | None) -> None:
    if value != MUTATION_INTENT_VALUE:
        raise ApiError(
            HTTPStatus.FORBIDDEN,
            f"{MUTATION_INTENT_HEADER}: {MUTATION_INTENT_VALUE} is required for POST",
        )


def read_request_body(handler: BaseHTTPRequestHandler) -> bytes:
    transfer_encoding = str(handler.headers.get("Transfer-Encoding") or "").strip()
    if transfer_encoding and transfer_encoding.casefold() != "identity":
        raise ApiError(HTTPStatus.BAD_REQUEST, "Transfer-Encoding is not supported")
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        raise ApiError(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, "invalid Content-Length") from exc
    if length < 0:
        raise ApiError(HTTPStatus.BAD_REQUEST, "Content-Length must not be negative")
    if length > MAX_BODY_BYTES:
        raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, f"request body exceeds {MAX_BODY_BYTES} bytes")
    try:
        raw = handler.rfile.read(length)
    except (TimeoutError, socket.timeout) as exc:
        raise ApiError(HTTPStatus.REQUEST_TIMEOUT, "request body timed out") from exc
    if len(raw) != length:
        raise ApiError(HTTPStatus.BAD_REQUEST, "request body ended before Content-Length bytes")
    return raw


def parse_json_body(handler: BaseHTTPRequestHandler, raw: bytes) -> dict[str, Any]:
    content_type = str(handler.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(HTTPStatus.BAD_REQUEST, "request body must be JSON") from exc
    if not isinstance(parsed, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "request body must be a JSON object")
    return parsed


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    # Direct callers retain the no-consumption rejection for a wrong media
    # type. The live HTTP handler uses the split read/parse flow above so a
    # bounded rejected POST body is consumed before the response closes.
    content_type = str(handler.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
    return parse_json_body(handler, read_request_body(handler))


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
        return build_graph(
            root,
            include_sensitive=parse_bool(first(query, "include_sensitive")),
            limit=normalize_limit(first(query, "limit")),
            offset=normalize_offset(first(query, "offset")),
        )
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


def normalize_offset(value: str | None) -> int:
    try:
        parsed = int(value or "0")
    except ValueError:
        return 0
    return max(0, min(parsed, 10_000))


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
    tls_cert: str | Path | None = None,
    tls_key: str | Path | None = None,
) -> BoundedThreadingHTTPServer:
    if not is_loopback_host(host) and not api_key:
        raise ValueError("non-loopback API binds require an API key")
    if not is_loopback_host(host) and not (tls_cert and tls_key):
        raise ValueError("non-loopback API binds require --tls-cert and --tls-key")
    if bool(tls_cert) != bool(tls_key):
        raise ValueError("tls-cert and tls-key must be provided together")
    handler = make_handler(root, api_key, log_requests=log_requests, bind_host=host)
    server = BoundedThreadingHTTPServer((host, port), handler)
    if tls_cert and tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(tls_cert), keyfile=str(tls_key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help=RUNTIME_VAULT_ROOT_HELP)
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to loopback only.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    parser.add_argument("--api-key", default=None, help="Optional API key. Defaults to AI_DEMEMORY_API_KEY.")
    parser.add_argument("--tls-cert", default=None, help="PEM certificate required for non-loopback binds.")
    parser.add_argument("--tls-key", default=None, help="PEM private key required for non-loopback binds.")
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if duplicate_options(arguments, ("--root",)):
        parser.error("--root may be specified at most once")
    args = parser.parse_args(arguments)

    try:
        root = resolve_runtime_vault(args.root).root
    except VaultBindingError as exc:
        parser.error(str(exc))
    api_key = args.api_key or os.environ.get("AI_DEMEMORY_API_KEY")
    if not is_loopback_host(args.host) and not api_key:
        print(
            "Refusing unauthenticated non-loopback API bind. Set AI_DEMEMORY_API_KEY.",
            file=sys.stderr,
        )
        return 2
    if not is_loopback_host(args.host) and not (args.tls_cert and args.tls_key):
        print(
            "Refusing cleartext non-loopback API bind. Provide --tls-cert and --tls-key.",
            file=sys.stderr,
        )
        return 2
    if bool(args.tls_cert) != bool(args.tls_key):
        print("--tls-cert and --tls-key must be provided together.", file=sys.stderr)
        return 2

    try:
        httpd = serve(
            root,
            args.host,
            args.port,
            api_key,
            tls_cert=args.tls_cert,
            tls_key=args.tls_key,
        )
    except (OSError, ssl.SSLError, ValueError) as exc:
        print(f"API startup failed: {exc}", file=sys.stderr)
        return 2
    scheme = "https" if args.tls_cert else "http"
    print(f"ai-dememory API listening on {scheme}://{args.host}:{httpd.server_address[1]}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ai-dememory API.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
