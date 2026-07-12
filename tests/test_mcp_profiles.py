from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tomllib
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts", ROOT / "mcp" / "server"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from ai_dememory_tool.cli import build_mcp_config, main as cli_main  # noqa: E402
from ai_dememory_tool.mcp_profiles import (  # noqa: E402
    CORE_MCP_TOOLS,
    MCP_PROFILE_NAMES,
    REVIEW_MCP_TOOLS,
    WORKING_MCP_TOOLS,
)
from mcp_inventory import build_inventory  # noqa: E402


class McpProfileTests(unittest.TestCase):
    def test_profiles_are_additive_and_core_is_bounded(self) -> None:
        self.assertEqual(MCP_PROFILE_NAMES, ("core", "working", "review", "admin"))
        self.assertGreaterEqual(len(CORE_MCP_TOOLS), 5)
        self.assertLessEqual(len(CORE_MCP_TOOLS), 8)
        self.assertTrue(set(CORE_MCP_TOOLS) < set(WORKING_MCP_TOOLS))
        self.assertTrue(set(WORKING_MCP_TOOLS) < set(REVIEW_MCP_TOOLS))

    def test_inventory_reports_schema_cost_for_every_profile(self) -> None:
        inventory = build_inventory(ROOT)

        self.assertEqual(set(inventory["profiles"]), set(MCP_PROFILE_NAMES))
        self.assertEqual(inventory["profiles"]["core"]["tool_count"], 7)
        self.assertEqual(inventory["profiles"]["working"]["tool_count"], 12)
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

    def test_clients_without_allowlists_default_admin_and_reject_narrow_profiles(self) -> None:
        generic = build_mcp_config("generic", "installed", Path("C:/vault"))
        claude = build_mcp_config("claude", "installed", Path("C:/vault"))

        self.assertNotIn("enabled_tools", generic)
        self.assertNotIn("enabled_tools", claude["mcpServers"]["ai-dememory"])
        for client in ("generic", "claude"):
            with self.subTest(client=client), self.assertRaisesRegex(ValueError, "not enforceable"):
                build_mcp_config(client, "installed", Path("C:/vault"), profile="core")

    def test_plugin_allowlist_matches_core(self) -> None:
        plugin = json.loads((ROOT / "plugins" / "ai-dememory" / ".mcp.json").read_text(encoding="utf-8"))
        enabled = plugin["mcpServers"]["ai-dememory"]["enabled_tools"]

        self.assertEqual(enabled, list(CORE_MCP_TOOLS))

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


if __name__ == "__main__":
    unittest.main()
