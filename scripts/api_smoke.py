#!/usr/bin/env python3
"""Smoke test the dependency-free local REST API."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from http_api import main as api_main, serve
from index_memory import rebuild_index
from memorylib import repo_root


@dataclass(frozen=True)
class ApiSmokeStep:
    name: str
    status: str
    detail: str


class ApiSmokeError(RuntimeError):
    pass


def ok(name: str, detail: str) -> ApiSmokeStep:
    return ApiSmokeStep(name, "ok", detail)


def write_memory(root: Path, relpath: str, memory_id: str, sensitivity: str = "internal") -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {memory_id}
title: API Smoke Memory
type: tool
status: active
scope: tool
project: null
tags: [codex, api]
aliases: [api smoke]
created_at: 2026-06-19
updated_at: 2026-06-19
confidence: 0.9
sensitivity: {sensitivity}
source:
  kind: manual
  ref: api-smoke
pin: false
decay: normal
review_after: 2026-09-19
---

# API Smoke Memory

Codex local REST API smoke should find this memory.
""",
        encoding="utf-8",
    )
    return path


def request_json(
    url: str,
    api_key: str | None = None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        finally:
            exc.close()
        return exc.code, payload


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise ApiSmokeError(message)


def stop_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def run_api_smoke() -> list[ApiSmokeStep]:
    steps: list[ApiSmokeStep] = []
    with tempfile.TemporaryDirectory(prefix="ai-dememory-api-smoke-") as tmp:
        root = Path(tmp)
        write_memory(root, "memories/tools/api.md", "mem_api_smoke")
        write_memory(root, "memories/tools/sensitive.md", "mem_api_sensitive", sensitivity="sensitive")
        db_path, count = rebuild_index(root, root / "indexes" / "memory.sqlite")
        assert_condition(count == 2 and db_path.exists(), "fixture index was not created")
        steps.append(ok("fixture_index", f"{count} memories"))

        header_value = "test-key"
        server = serve(root, "127.0.0.1", 0, header_value, log_requests=False)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            status, payload = request_json(f"{base_url}/health")
            assert_condition(status == 401 and "error" in payload, "API did not require a key")
            steps.append(ok("requires_key", "unauthenticated request rejected"))

            status, health = request_json(f"{base_url}/health", header_value)
            assert_condition(status == 200 and health["status"] == "ok", "health endpoint failed")
            assert_condition(health["index_exists"] is True, "health did not report index")
            steps.append(ok("health", "loopback health returned ok"))

            status, search = request_json(f"{base_url}/search?query=codex&limit=1", header_value)
            assert_condition(status == 200, "search endpoint failed")
            assert_condition(search["results"][0]["id"] == "mem_api_smoke", "search returned wrong memory")
            steps.append(ok("search", "returned indexed memory"))

            status, graph = request_json(f"{base_url}/graph", header_value)
            assert_condition(status == 200, "graph endpoint failed")
            node_ids = {node["id"] for node in graph["nodes"]}
            assert_condition("mem_api_smoke" in node_ids, "graph missing internal memory")
            assert_condition("mem_api_sensitive" not in node_ids, "graph leaked sensitive memory")
            steps.append(ok("graph", "sensitive memory filtered by default"))

            status, memory = request_json(f"{base_url}/memories/mem_api_smoke", header_value)
            memory_id = (memory.get("frontmatter") or {}).get("id")
            assert_condition(status == 200 and memory_id == "mem_api_smoke", "memory read failed")
            steps.append(ok("memory_read", "read public/internal memory"))

            status, sensitive = request_json(f"{base_url}/memories/mem_api_sensitive", header_value)
            assert_condition(status == 403 and "error" in sensitive, "sensitive memory read was not rejected")
            steps.append(ok("sensitive_rejection", "sensitive memory rejected by default"))

            status, proposal = request_json(
                f"{base_url}/proposals",
                header_value,
                method="POST",
                body={
                    "title": "API Smoke Proposal",
                    "content": "Non-secret local API proposal.",
                    "tags": ["api", "smoke"],
                    "source_kind": "codex",
                },
            )
            assert_condition(status == 200, "proposal endpoint failed")
            proposal_path = proposal["path"]
            assert_condition(proposal_path.startswith("inbox/llm-captures/"), "proposal escaped inbox")
            assert_condition((root / proposal_path).exists(), "proposal file was not written")
            steps.append(ok("proposal", "wrote only to inbox/llm-captures"))

            status, reindex = request_json(f"{base_url}/reindex", header_value, method="POST", body={})
            assert_condition(status == 200 and reindex["count"] == 2, "reindex endpoint failed")
            steps.append(ok("reindex", "rebuilt fixture index"))
        finally:
            stop_server(server, thread)

        with patch("sys.stderr", io.StringIO()):
            exit_code = api_main(["--root", str(root), "--host", "0.0.0.0", "--port", "8765"])
        assert_condition(exit_code == 2, "non-loopback unauthenticated bind was not refused")
        steps.append(ok("network_refusal", "0.0.0.0 without API key refused"))
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Accepted for command consistency; smoke uses a temp vault.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    if args.root:
        repo_root(args.root)
    try:
        steps = run_api_smoke()
    except ApiSmokeError as exc:
        print(str(exc))
        return 1
    if args.json:
        print(json.dumps([asdict(step) for step in steps], indent=2))
    else:
        for step in steps:
            print(f"OK {step.name}: {step.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
