from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts", ROOT / "mcp" / "server"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from ai_dememory_tool import __version__  # noqa: E402
from ai_dememory_tool.cli import build_mcp_config, main as cli_main  # noqa: E402
from ai_dememory_tool.mcp_profiles import (  # noqa: E402
    CORE_MCP_TOOLS,
    MCP_PROFILE_NAMES,
    PUBLIC_MCP_TOOLS,
    REVIEW_MCP_TOOLS,
    WORKING_MCP_TOOLS,
)
from mcp_inventory import build_inventory  # noqa: E402
from memory_mcp import handle_rpc, list_tools, main as mcp_main  # noqa: E402
from index_memory import rebuild_index  # noqa: E402


class McpProfileTests(unittest.TestCase):
    def test_profiles_are_additive_and_core_is_bounded(self) -> None:
        self.assertEqual(MCP_PROFILE_NAMES, ("public", "core", "working", "review", "admin"))
        self.assertEqual(len(PUBLIC_MCP_TOOLS), 3)
        self.assertGreaterEqual(len(CORE_MCP_TOOLS), 4)
        self.assertLessEqual(len(CORE_MCP_TOOLS), 8)
        self.assertTrue(set(PUBLIC_MCP_TOOLS) < set(CORE_MCP_TOOLS))
        self.assertTrue(set(CORE_MCP_TOOLS) < set(WORKING_MCP_TOOLS))
        self.assertTrue(set(WORKING_MCP_TOOLS) < set(REVIEW_MCP_TOOLS))

    def test_inventory_reports_schema_cost_for_every_profile(self) -> None:
        inventory = build_inventory(ROOT)

        self.assertEqual(set(inventory["profiles"]), set(MCP_PROFILE_NAMES))
        self.assertEqual(inventory["profiles"]["public"]["tool_count"], 3)
        self.assertEqual(inventory["profiles"]["core"]["tool_count"], 4)
        self.assertEqual(inventory["profiles"]["working"]["tool_count"], 11)
        self.assertEqual(inventory["profiles"]["review"]["tool_count"], 44)
        self.assertEqual(inventory["profiles"]["admin"]["tool_count"], inventory["tool_count"])
        self.assertLess(
            inventory["profiles"]["core"]["schema_bytes"],
            inventory["profiles"]["admin"]["schema_bytes"],
        )
        for profile in inventory["profiles"].values():
            self.assertFalse(profile["missing_tools"])
            self.assertEqual(
                profile["estimated_schema_tokens"],
                (profile["schema_bytes"] + 3) // 4,
            )

    def test_codex_config_defaults_to_core_allowlist(self) -> None:
        rendered = build_mcp_config("codex", "installed", Path("C:/vault"))
        config = tomllib.loads(rendered)["mcp_servers"]["ai-dememory"]

        self.assertEqual(config["enabled_tools"], list(CORE_MCP_TOOLS))

    def test_codex_admin_profile_preserves_unfiltered_server(self) -> None:
        rendered = build_mcp_config("codex", "installed", Path("C:/vault"), profile="admin")
        config = tomllib.loads(rendered)["mcp_servers"]["ai-dememory"]

        self.assertNotIn("enabled_tools", config)

    def test_clients_without_allowlists_use_server_enforced_core_profile(self) -> None:
        generic = build_mcp_config("generic", "installed", Path("C:/vault"))
        claude = build_mcp_config("claude", "installed", Path("C:/vault"))

        self.assertNotIn("enabled_tools", generic)
        self.assertNotIn("enabled_tools", claude["mcpServers"]["ai-dememory"])
        for client in ("generic", "claude"):
            with self.subTest(client=client):
                config = build_mcp_config(client, "installed", Path("C:/vault"), profile="core")
                server = config if client == "generic" else config["mcpServers"]["ai-dememory"]
                self.assertEqual(server["args"][-3:], ["--profile", "core", "--require-bound-root"])

    def test_server_filters_and_denies_tools_outside_profile(self) -> None:
        listed = list_tools(profile="core")
        names = {tool["name"] for tool in listed["tools"]}
        self.assertEqual(names, set(CORE_MCP_TOOLS))

        denied = handle_rpc(
            {
                "method": "tools/call",
                "params": {"name": "memory.maintenance_status", "arguments": {}},
            },
            ROOT,
            profile="core",
        )
        self.assertIsNotNone(denied)
        self.assertTrue(denied["isError"])
        self.assertIn("not enabled", denied["content"][0]["text"])

        initialized = handle_rpc({"method": "initialize", "params": {}}, ROOT, profile="core")
        self.assertEqual(initialized["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(initialized["serverInfo"]["profile"], "core")
        self.assertEqual(initialized["serverInfo"]["version"], __version__)

    def test_unprofiled_stdio_server_fails_closed_to_core(self) -> None:
        with (
            patch("memory_mcp.repo_root", return_value=ROOT),
            patch("memory_mcp.run_stdio", return_value=0) as run_stdio,
        ):
            exit_code = mcp_main(["--stdio"])

        self.assertEqual(exit_code, 0)
        run_stdio.assert_called_once_with(
            ROOT,
            profile="core",
            idle_timeout_seconds=600,
        )

    def test_plugin_allowlist_matches_public_ceiling(self) -> None:
        plugin = json.loads((ROOT / "plugins" / "ai-dememory" / ".mcp.json").read_text(encoding="utf-8"))
        args = plugin["mcpServers"]["ai-dememory"]["args"]
        enabled = plugin["mcpServers"]["ai-dememory"]["enabled_tools"]

        self.assertEqual(args[-3:], ["--profile", "public", "--require-bound-root"])
        self.assertEqual(enabled, list(PUBLIC_MCP_TOOLS))

    def test_public_profile_enforces_public_read_ceiling_server_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_profile_memory(root, "public", "mem_public", "public")
            write_profile_memory(root, "internal", "mem_internal", "internal")
            rebuild_index(root)

            response = handle_rpc(
                {
                    "method": "tools/call",
                    "params": {
                        "name": "memory.search",
                        "arguments": {
                            "query": "profile fixture",
                            "include_sensitive": True,
                            "public_only": False,
                        },
                    },
                },
                root,
                profile="public",
            )

        self.assertIsNotNone(response)
        self.assertFalse(response["isError"])
        payload = response["structuredContent"]["results"]
        self.assertEqual([item["id"] for item in payload], ["mem_public"])

    def test_public_profile_context_cannot_relax_public_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_profile_memory(root, "public", "mem_public", "public")
            write_profile_memory(root, "internal", "mem_internal", "internal")
            write_profile_memory(root, "private", "mem_private", "private")
            write_profile_memory(root, "sensitive", "mem_sensitive", "sensitive")
            rebuild_index(root)

            payloads = []
            for arguments in (
                {"query": "profile fixture", "limit": 10},
                {
                    "query": "profile fixture",
                    "limit": 10,
                    "include_sensitive": True,
                    "include_working_memory": True,
                    "public_only": False,
                },
            ):
                response = handle_rpc(
                    {
                        "method": "tools/call",
                        "params": {
                            "name": "memory.context",
                            "arguments": arguments,
                        },
                    },
                    root,
                    profile="public",
                )
                self.assertIsNotNone(response)
                self.assertFalse(response["isError"])
                payloads.append(response["structuredContent"])

        for payload in payloads:
            self.assertTrue(payload["public_only"])
            self.assertEqual([item["id"] for item in payload["items"]], ["mem_public"])
            serialized = json.dumps(payload)
            self.assertNotIn("mem_internal", serialized)
            self.assertNotIn("mem_private", serialized)
            self.assertNotIn("mem_sensitive", serialized)

    def test_default_help_foregrounds_one_dev_entry(self) -> None:
        output = io.StringIO()
        with patch("sys.stdout", output):
            exit_code = cli_main(["--help"])

        self.assertEqual(exit_code, 0)
        self.assertIn("dev            Advanced, CI", output.getvalue())
        self.assertNotIn("release-check  Run", output.getvalue())
        self.assertNotIn("publish-guard  Validate", output.getvalue())

    def test_dev_help_lists_maintainer_commands(self) -> None:
        output = io.StringIO()
        with patch("sys.stdout", output):
            exit_code = cli_main(["dev", "--help"])

        self.assertEqual(exit_code, 0)
        self.assertIn("release-check", output.getvalue())
        self.assertIn("publish-guard", output.getvalue())

    def test_dev_and_legacy_alias_dispatch_same_command(self) -> None:
        with patch("ai_dememory_tool.cli.run_packaged_command", return_value=0) as run:
            self.assertEqual(cli_main(["dev", "release-check", "--json"]), 0)
            run.assert_called_once_with("release-check", ["--json"])

        with patch("ai_dememory_tool.cli.run_packaged_command", return_value=0) as run:
            self.assertEqual(cli_main(["release-check", "--json"]), 0)
            run.assert_called_once_with("release-check", ["--json"])

def write_profile_memory(
    root: Path,
    name: str,
    memory_id: str,
    sensitivity: str,
) -> None:
    path = root / "memories" / "tools" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {memory_id}
title: {name.title()} Profile Fixture
type: tool
status: active
scope: tool
project: null
tags: [profile, fixture]
aliases: []
created_at: 2026-01-01
updated_at: 2026-01-01
confidence: 1.0
sensitivity: {sensitivity}
source:
  kind: manual
  ref: null
pin: false
decay: none
review_after: 2027-01-01
---

# {name.title()} Profile Fixture

Profile fixture searchable content.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
