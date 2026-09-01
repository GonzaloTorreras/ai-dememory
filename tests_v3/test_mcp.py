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

    def test_surface_is_exactly_five_tools(self) -> None:
        names = [tool["name"] for tool in mcp.tool_definitions()]
        self.assertEqual(
            names,
            ["memory.search", "memory.get", "memory.context", "memory.propose", "memory.status"],
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
        self.assertEqual(len(responses[1]["result"]["tools"]), 5)

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
