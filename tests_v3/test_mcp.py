from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_dememory.builtin_modules import mcp
from ai_dememory.config import select_vault, set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.modules import load_enabled_module
from ai_dememory.proposals import ProposalStore
from ai_dememory.vault import Vault


class McpModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "config")},
            clear=False,
        )
        self.environment.start()
        self.vault = Vault.create(self.root / "vault")
        self.services = CoreServices(self.vault)

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def test_surface_is_exactly_seven_tools(self) -> None:
        names = [tool["name"] for tool in mcp.tool_definitions()]
        self.assertEqual(
            names,
            ["memory.search", "memory.get", "memory.context", "memory.propose", "memory.learn", "memory.forget", "memory.status"],
        )

    def test_mcp_proposal_never_writes_canonical_memory(self) -> None:
        result = mcp.call_tool(
            self.services,
            "memory.propose",
            {"title": "Candidate", "content": "This needs human review."},
        )
        self.assertEqual(self.vault.memory_count(), 0)
        self.assertEqual(len(ProposalStore(self.vault).list()), 1)
        self.assertEqual(result["status"], "pending")

    def test_get_output_is_bounded(self) -> None:
        memory = self.vault.remember("needle " + ("x" * 1000), "Bounded")
        result = mcp.call_tool(
            self.services, "memory.get", {"memory_id": memory.memory_id, "max_chars": 256}
        )
        self.assertEqual(len(result["content"]), 256)
        self.assertTrue(result["truncated"])

    def test_stdio_initialize_and_list(self) -> None:
        requests = "\n".join(
            (
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
                "",
            )
        )
        output = io.StringIO()
        self.assertEqual(mcp.serve(self.services, input_stream=io.StringIO(requests), output_stream=output), 0)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "ai-dememory")
        self.assertEqual(len(responses[1]["result"]["tools"]), 7)
        guidance = responses[0]["result"]["instructions"]
        for expected in ("memory.context", "memory.learn", "event_id", "provenance", "provisional", "explicit correction"):
            self.assertIn(expected, guidance)

    def learning_arguments(self, scope="project:alpha", event="one"):
        return {"title": "Runtime decision", "content": "Use Python", "scope": scope, "event_id": event,
                "source": {"provider": "codex", "session": "session", "turn": event,
                           "evidence_kind": "user_statement", "excerpt": "Use Python"}}

    def test_scope_bound_stdio_defaults_retrieval_and_forget(self) -> None:
        memory = mcp.call_tool(self.services, "memory.learn", self.learning_arguments())
        other = mcp.call_tool(self.services, "memory.learn", self.learning_arguments("project:beta"))
        shared = self.vault.remember("Shared Python guidance", "Shared")
        methods = [
            {"method": "initialize"},
            {"method": "tools/list"},
            {"method": "tools/call", "params": {"name": "memory.context", "arguments": {"query": "Python"}}},
            {"method": "tools/call", "params": {"name": "memory.get", "arguments": {"memory_id": other["memory_id"]}}},
            {"method": "tools/call", "params": {"name": "memory.forget", "arguments": {"memory_id": memory["memory_id"]}}},
        ]
        requests = "".join(json.dumps({"jsonrpc": "2.0", "id": index + 1, **request}) + "\n"
                           for index, request in enumerate(methods))
        output = io.StringIO()
        self.assertEqual(mcp.serve(self.services, ["--scope", "project:alpha"],
                                   input_stream=io.StringIO(requests), output_stream=output), 0)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertIn("bound to scope project:alpha", responses[0]["result"]["instructions"])
        tools = responses[1]["result"]["tools"]
        self.assertEqual(len(tools), 7)
        for tool in tools:
            schema = tool["inputSchema"]["properties"].get("scope")
            if schema:
                self.assertEqual(schema["default"], "project:alpha")
                self.assertEqual(schema["enum"], ["project:alpha"])
        context = json.loads(responses[2]["result"]["content"][0]["text"])
        self.assertEqual(set(context["memory_ids"]), {memory["memory_id"], shared.memory_id})
        self.assertIsNone(json.loads(responses[3]["result"]["content"][0]["text"]))
        forgotten = json.loads(responses[4]["result"]["content"][0]["text"])
        self.assertEqual(forgotten["status"], "forgotten")
        self.assertEqual(self.vault.get(other["memory_id"]).status, "active")

    def test_bound_server_rejects_cross_scope_operations_and_unscoped_proposals(self) -> None:
        bound = "project:alpha"
        memory = mcp.call_tool(self.services, "memory.learn", self.learning_arguments(), bound)
        for scope in ("project:beta", "global"):
            calls = [
                ("memory.search", {"query": "Python", "scope": scope}),
                ("memory.context", {"query": "Python", "scope": scope}),
                ("memory.get", {"memory_id": memory["memory_id"], "scope": scope}),
                ("memory.forget", {"memory_id": memory["memory_id"], "scope": scope}),
                ("memory.learn", self.learning_arguments(scope, "two")),
            ]
            for name, arguments in calls:
                with self.subTest(name=name, scope=scope):
                    response = mcp.handle_request(self.services, {
                        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    }, bound)
                    self.assertEqual(response["error"]["code"], -32602)
        with self.assertRaisesRegex(ValueError, "unscoped proposals"):
            mcp.call_tool(self.services, "memory.propose", {"title": "Bypass", "content": "No"}, bound)
        self.assertEqual(ProposalStore(self.vault).count(), 0)
        self.assertEqual(self.vault.memory_count(), 1)
        self.assertEqual(self.vault.get(memory["memory_id"]).status, "active")

    def test_bound_learning_requires_explicit_scope_and_arguments_are_not_mutated(self) -> None:
        arguments = self.learning_arguments()
        arguments.pop("scope")
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            mcp.call_tool(self.services, "memory.learn", arguments, "project:alpha")
        retrieval = {"query": "Python"}
        self.assertEqual(mcp.call_tool(self.services, "memory.search", retrieval, "project:alpha"), [])
        self.assertEqual(retrieval, {"query": "Python"})

    def test_invalid_mcp_runtime_arguments_fail_before_reading_input(self) -> None:
        for argv in (["--scope"], ["--scope", "../private"], ["--unknown"], ["extra"]):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                mcp.serve(self.services, argv, input_stream=io.StringIO(""), output_stream=io.StringIO())

    def test_malformed_tool_call_does_not_stop_stdio_server(self) -> None:
        requests = "\n".join(
            (
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": ["bad"]}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
                "",
            )
        )
        output = io.StringIO()
        self.assertEqual(mcp.serve(self.services, input_stream=io.StringIO(requests), output_stream=output), 0)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertEqual(responses[1]["result"], {})

    def test_request_limit_counts_utf8_bytes_and_server_continues(self) -> None:
        oversized = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "memory.propose",
                    "arguments": {
                        "title": "😀" * ((mcp.MAX_REQUEST_BYTES // 4) + 1),
                        "content": "x",
                    },
                },
            },
            ensure_ascii=False,
        )
        self.assertLess(len(oversized), mcp.MAX_REQUEST_BYTES)
        self.assertGreater(len(oversized.encode("utf-8")), mcp.MAX_REQUEST_BYTES)
        requests = (
            oversized
            + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"})
            + "\n"
        )
        output = io.StringIO()
        self.assertEqual(
            mcp.serve(self.services, input_stream=io.StringIO(requests), output_stream=output),
            0,
        )
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32600)
        self.assertEqual(responses[1]["result"], {})
        self.assertEqual(ProposalStore(self.vault).list(), [])

    def test_numeric_overflow_and_extreme_nesting_are_controlled(self) -> None:
        overflow = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "memory.search",
                    "arguments": {"query": "x", "limit": 1e309},
                },
            }
        )
        nested = "[" * 1_100 + "]" * 1_100
        requests = "\n".join(
            (overflow, nested, json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}), "")
        )
        output = io.StringIO()
        self.assertEqual(
            mcp.serve(self.services, input_stream=io.StringIO(requests), output_stream=output),
            0,
        )
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertEqual(responses[1]["error"]["code"], -32700)
        self.assertEqual(responses[2]["result"], {})

    def test_lone_surrogate_error_does_not_stop_binary_stdio(self) -> None:
        requests = (
            b'{"jsonrpc":"2.0","id":1,"method":"\\ud800"}\n'
            b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
        )
        output = io.BytesIO()
        self.assertEqual(
            mcp.serve(self.services, input_stream=io.BytesIO(requests), output_stream=output),
            0,
        )
        responses = [json.loads(line) for line in output.getvalue().decode("ascii").splitlines()]
        self.assertEqual(responses[0]["error"]["code"], -32601)
        self.assertEqual(responses[1]["result"], {})

    def test_real_stdio_transport_preserves_utf8_bytes(self) -> None:
        select_vault(self.vault.root)
        set_module_enabled("mcp", True)
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "memory.propose",
                "arguments": {"title": "España 😀", "content": "recuerdo útil"},
            },
        }
        environment = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-m", "ai_dememory", "serve", "mcp"],
            input=(json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.root,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
        response = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(response["id"], 1)
        proposals = ProposalStore(self.vault).list()
        self.assertEqual([(item.title, item.content) for item in proposals], [("España 😀", "recuerdo útil")])

    def test_module_must_be_enabled_before_loading(self) -> None:
        with self.assertRaisesRegex(ValueError, "disabled"):
            load_enabled_module("mcp")
        set_module_enabled("mcp", True)
        self.assertEqual(load_enabled_module("mcp").get_manifest().module_id, "mcp")


if __name__ == "__main__":
    unittest.main()
