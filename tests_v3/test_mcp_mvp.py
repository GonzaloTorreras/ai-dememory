from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ai_dememory.proposals import ProposalStore
from ai_dememory.vault import Vault
from tests_v3.test_core import V3TestCase


class McpVerticalMvpTests(V3TestCase):
    def test_enable_read_propose_and_stop_on_eof(self) -> None:
        vault_path = self.root / "vault"
        code, _, error = self.run_cli("setup", str(vault_path), "--yes")
        self.assertEqual(code, 0, error)
        code, _, error = self.run_cli(
            "remember", "MCP can retrieve this canonical memory.", "--title", "MCP memory"
        )
        self.assertEqual(code, 0, error)

        code, output, error = self.run_cli("module", "list")
        self.assertEqual(code, 0, error)
        self.assertIn("mcp [disabled]", output)
        code, output, error = self.run_cli("module", "enable", "mcp")
        self.assertEqual(code, 0, error)
        self.assertIn("Enabled module: mcp", output)
        self.assertIn("Next: ai-dememory serve mcp", output)

        requests = "\n".join(
            (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "memory.search",
                            "arguments": {"query": "canonical"},
                        },
                    }
                ),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "memory.propose",
                            "arguments": {
                                "title": "MCP candidate",
                                "content": "This remains pending review.",
                            },
                        },
                    }
                ),
                "",
            )
        )
        environment = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-m", "ai_dememory", "serve", "mcp"],
            input=requests.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.root,
            env=environment,
            timeout=10,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
        responses = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines()]
        search = json.loads(responses[0]["result"]["content"][0]["text"])
        proposal = json.loads(responses[1]["result"]["content"][0]["text"])
        self.assertEqual(search[0]["title"], "MCP memory")
        self.assertEqual(proposal["status"], "pending")
        vault = Vault.open(vault_path)
        self.assertEqual(vault.memory_count(), 1)
        self.assertEqual(ProposalStore(vault).count(), 1)

        code, output, error = self.run_cli("module", "disable", "mcp")
        self.assertEqual(code, 0, error)
        self.assertIn("Disabled module: mcp", output)

