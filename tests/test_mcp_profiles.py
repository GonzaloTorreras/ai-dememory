from __future__ import annotations

import io
import json
import os
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
from ai_dememory_tool.cli import build_mcp_config, find_memory_root, main as cli_main  # noqa: E402
from ai_dememory_tool.vault_binding import save_default_vault  # noqa: E402
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
    def setUp(self) -> None:
        # Root-binding tests must not read a selector from the developer host.
        self._default_selector_home = tempfile.TemporaryDirectory()
        self._default_selector_patch = patch.dict(
            os.environ,
            {"AI_DEMEMORY_CONFIG_HOME": self._default_selector_home.name},
            clear=False,
        )
        self._default_selector_patch.start()
        self.addCleanup(self._default_selector_home.cleanup)
        self.addCleanup(self._default_selector_patch.stop)

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
                self.assertNotIn("--require-version", server["args"])

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
        with patch("memory_mcp.run_stdio", return_value=0) as run_stdio:
            exit_code = mcp_main(["--stdio", "--root", str(ROOT)])

        self.assertEqual(exit_code, 0)
        run_stdio.assert_called_once_with(
            ROOT,
            profile="core",
            idle_timeout_seconds=600,
        )

    def test_mcp_server_accepts_legacy_version_arguments_after_an_upgrade(self) -> None:
        with patch("memory_mcp.run_stdio", return_value=0) as run_stdio:
            self.assertEqual(
                mcp_main(["--stdio", "--root", str(ROOT), "--require-version", "0.0.0"]),
                0,
            )
        run_stdio.assert_called_once_with(
            ROOT,
            profile="core",
            idle_timeout_seconds=600,
        )

    def test_mcp_runtime_accepts_an_explicitly_saved_local_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            vault = Path(temporary) / "vault"
            vault.mkdir()
            (vault / ".ai-dememory.toml").write_text(
                '[memory]\nschema_version = "2.0"\n',
                encoding="utf-8",
            )
            save_default_vault(vault)

            with (
                patch.dict(os.environ, {"AI_DEMEMORY_ROOT": ""}, clear=False),
                patch("memory_mcp.run_stdio", return_value=0) as run_stdio,
            ):
                self.assertEqual(mcp_main(["--stdio", "--require-bound-root"]), 0)

        run_stdio.assert_called_once_with(
            vault.resolve(),
            profile="core",
            idle_timeout_seconds=600,
        )

    def test_mcp_help_explains_the_explicit_saved_default_selector(self) -> None:
        output = io.StringIO()
        with patch("sys.stdout", output), self.assertRaises(SystemExit) as raised:
            mcp_main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = " ".join(output.getvalue().split()).replace("ai- dememory", "ai-dememory")
        self.assertIn("saved local default", help_text)
        self.assertIn("ai-dememory vault use <absolute-vault-path>", help_text)
        self.assertIn("explicitly saved local default", help_text)

    def test_mcp_readme_keeps_the_runtime_selector_contract(self) -> None:
        readme = (ROOT / "mcp" / "README.md").read_text(encoding="utf-8")

        self.assertIn("ai-dememory vault use <absolute-vault-path>", readme)
        self.assertIn("`--require-bound-root` requires one usable binding", readme)
        self.assertIn("never discover a vault from the current directory", readme)

    def test_public_cli_route_accepts_a_legacy_mcp_version_argument(self) -> None:
        output = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(os.environ, {}, clear=True),
            patch("sys.stdout", output),
        ):
            exit_code = cli_main(
                [
                    "--root",
                    temporary,
                    "mcp",
                    "--list-tools",
                    "--require-bound-root",
                    "--require-version",
                    "0.0.0",
                ]
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("tools", payload)
        self.assertTrue(payload["tools"])

    def test_mcp_server_rejects_whitespace_root_bindings_before_start(self) -> None:
        invalid_bindings = (
            (
                "explicit root separated",
                ["--stdio", "--require-bound-root", "--root", " \t"],
                str(ROOT),
                "--root requires a non-empty vault path",
            ),
            (
                "explicit root equals",
                ["--stdio", "--require-bound-root", "--root= \t"],
                str(ROOT),
                "--root requires a non-empty vault path",
            ),
            (
                "environment root",
                ["--stdio", "--require-bound-root"],
                " \t",
                "AI_DEMEMORY_ROOT requires a non-empty vault path",
            ),
        )
        for label, argv, environment_root, message in invalid_bindings:
            with self.subTest(binding=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                    patch("memory_mcp.run_stdio") as run_stdio,
                    patch("sys.stderr", error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    mcp_main(argv)
                self.assertEqual(raised.exception.code, 2)
                run_stdio.assert_not_called()
                self.assertIn(message, error.getvalue())

        valid_bindings = (
            ("explicit root", ["--stdio", "--require-bound-root", "--root", str(ROOT)], " \t"),
            ("environment root", ["--stdio", "--require-bound-root"], str(ROOT)),
        )
        for label, argv, environment_root in valid_bindings:
            with self.subTest(binding=f"valid {label}"):
                with (
                    patch.dict(os.environ, {"AI_DEMEMORY_ROOT": environment_root}),
                    patch("memory_mcp.run_stdio", return_value=0) as run_stdio,
                ):
                    self.assertEqual(mcp_main(argv), 0)
                run_stdio.assert_called_once_with(
                    ROOT,
                    profile="core",
                    idle_timeout_seconds=600,
                )

    def test_mcp_runtime_requires_a_binding_before_server_or_tool_call(self) -> None:
        invocations = (
            ("stdio", ["--stdio"], "memory_mcp.run_stdio"),
            (
                "call",
                ["--call", "memory.search", "--args", '{"query":"codex"}'],
                "memory_mcp.call_tool",
            ),
        )
        for label, argv, runtime_target in invocations:
            with self.subTest(entrypoint=label):
                error = io.StringIO()
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch(runtime_target) as runtime_call,
                    patch("sys.stderr", error),
                    self.assertRaises(SystemExit) as raised,
                ):
                    mcp_main(argv)

                self.assertEqual(raised.exception.code, 2)
                runtime_call.assert_not_called()
                self.assertIn("runtime vault binding requires", error.getvalue())

    def test_mcp_list_tools_stays_rootless_static_metadata(self) -> None:
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"AI_DEMEMORY_ROOT": " \t"}),
            patch("memory_mcp.resolve_runtime_vault") as resolver,
            patch("sys.stdout", output),
        ):
            self.assertEqual(mcp_main(["--list-tools"]), 0)

        resolver.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())["tools"])

    def test_mcp_metadata_respects_the_legacy_binding_flag(self) -> None:
        error = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.stderr", error),
            self.assertRaises(SystemExit) as raised,
        ):
            mcp_main(["--list-tools", "--require-bound-root"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("runtime vault binding requires", error.getvalue())

    def test_mcp_rejects_a_blank_direct_tool_name_before_binding(self) -> None:
        error = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("memory_mcp.resolve_runtime_vault") as resolver,
            patch("memory_mcp.call_tool") as tool_call,
            patch("sys.stderr", error),
            self.assertRaises(SystemExit) as raised,
        ):
            mcp_main(["--call", ""])

        self.assertEqual(raised.exception.code, 2)
        resolver.assert_not_called()
        tool_call.assert_not_called()
        self.assertIn("--call requires a non-empty tool name", error.getvalue())

    def test_public_cli_mcp_metadata_never_discovers_a_vault(self) -> None:
        output = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("ai_dememory_tool.cli.find_memory_root") as root_resolver,
            patch("sys.stdout", output),
        ):
            self.assertEqual(cli_main(["mcp", "--list-tools"]), 0)

        root_resolver.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())["tools"])

    def test_plugin_allowlist_matches_public_ceiling(self) -> None:
        plugin = json.loads((ROOT / "plugins" / "ai-dememory" / ".mcp.json").read_text(encoding="utf-8"))
        args = plugin["mcpServers"]["ai-dememory"]["args"]
        enabled = plugin["mcpServers"]["ai-dememory"]["enabled_tools"]

        self.assertEqual(args[-3:], ["--profile", "public", "--require-bound-root"])
        self.assertNotIn("--require-version", args)
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

    def test_version_check_fails_closed_on_an_unexpected_installed_release(self) -> None:
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(cli_main(["version-check", __version__]), 0)
        self.assertEqual(output.getvalue().strip(), f"ai-dememory {__version__}")

        error = io.StringIO()
        with patch("sys.stderr", error):
            self.assertEqual(cli_main(["version-check", "0.0.0"]), 1)
        self.assertIn(f"expected 0.0.0, found {__version__}", error.getvalue())

    def test_bare_legacy_version_option_explains_the_supported_diagnostics(self) -> None:
        error = io.StringIO()
        with patch("sys.stderr", error):
            self.assertEqual(cli_main(["--require-version", "2.1.0"]), 2)
        self.assertIn("legacy subcommand option", error.getvalue())
        self.assertIn("ai-dememory --version", error.getvalue())

    def test_mcp_config_accepts_legacy_version_arguments_without_emitting_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.StringIO()
            with patch("sys.stdout", output):
                self.assertEqual(
                    cli_main(
                        [
                            "mcp-config",
                            "--root",
                            str(root),
                            "--client",
                            "codex",
                            "--require-version",
                            "0.0.0",
                        ]
                    ),
                    0,
                )
            self.assertIn("[mcp_servers.ai-dememory]", output.getvalue())
        self.assertNotIn("--require-version", output.getvalue())

    def test_mcp_config_rejects_command_args_that_override_security_controls(self) -> None:
        rejected = (
            ["--root", "C:/evil"],
            ["--root=C:/evil"],
            ["--profile", "admin"],
            ["--require-version=0.0.0"],
            ["mcp"],
        )
        for command_args in rejected:
            with self.subTest(command_args=command_args):
                with self.assertRaisesRegex(ValueError, "cannot override reserved MCP argument"):
                    build_mcp_config(
                        "generic",
                        "installed",
                        Path("C:/safe"),
                        command="py",
                        command_args=command_args,
                    )

        rendered = build_mcp_config(
            "generic",
            "installed",
            Path("C:/safe"),
            command="py",
            command_args=["-3", "scripts/ai_dememory.py"],
        )
        self.assertEqual(rendered["args"][:2], ["-3", "scripts/ai_dememory.py"])

    def test_cli_and_mcp_reject_abbreviated_or_duplicate_security_controls(self) -> None:
        error = io.StringIO()
        with patch("sys.stderr", error), patch(
            "ai_dememory_tool.cli.run_packaged_command"
        ) as run:
            self.assertEqual(
                cli_main(["--root", "C:/safe", "mcp", "--root", "C:/evil"]),
                2,
            )
            run.assert_not_called()
        self.assertIn("--root may be specified at most once", error.getvalue())

        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
            cli_main(
                [
                    "mcp-config",
                    "--client",
                    "generic",
                    "--require-version",
                    __version__,
                    "--ro",
                    "C:/evil",
                ]
            )
        self.assertEqual(raised.exception.code, 2)

        for argv in (
            ["--stdio", "--require-v", __version__],
            ["--stdio", "--profile", "public", "--profile", "admin"],
            ["--stdio", "--idle-timeout-seconds", "600", "--idle-timeout-seconds", "0"],
        ):
            with self.subTest(argv=argv), patch("sys.stderr", io.StringIO()), self.assertRaises(
                SystemExit
            ) as raised:
                mcp_main(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_root_resolution_expands_home_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {"AI_DEMEMORY_ROOT": "~/vault", "USERPROFILE": temporary, "HOME": temporary},
            clear=False,
        ):
            self.assertEqual(find_memory_root(), (Path(temporary) / "vault").resolve())

    def test_legacy_version_argument_preserves_root_profile_and_idle_controls(self) -> None:
        with patch("memory_mcp.run_stdio", return_value=0) as run_stdio:
            self.assertEqual(
                mcp_main(
                    [
                        "--stdio",
                        "--root",
                        str(ROOT),
                        "--require-bound-root",
                        "--require-version",
                        "0.0.0",
                        "--profile",
                        "public",
                        "--idle-timeout-seconds",
                        "120",
                    ]
                ),
                0,
            )
        run_stdio.assert_called_once_with(
            ROOT,
            profile="public",
            idle_timeout_seconds=120,
        )

    def test_docker_mcp_config_rejects_option_shaped_image(self) -> None:
        for image in ("--privileged", "--volume=/:/host", " ai-dememory:local"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                build_mcp_config("generic", "docker", Path("C:/safe"), image=image)

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
