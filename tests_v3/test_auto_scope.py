from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ai_dememory.builtin_modules.mcp import ClientBinding, serve
from ai_dememory.config import set_module_enabled
from ai_dememory.core import CoreServices
from ai_dememory.projects import configure_project, resolve_project
from ai_dememory.proposals import ProposalStore
from ai_dememory.vault import Vault


class AutoScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "config"
        self.enterContext(patch.dict(os.environ, {
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "AI_DEMEMORY_CONFIG_DIR": str(self.config),
            "CODEX_HOME": str(self.root / "codex"),
        }))
        self.vault = Vault.create(self.root / "vault")
        self.services = CoreServices(self.vault)
        set_module_enabled("mcp", True)
        set_module_enabled("harness", True)
        self.shared = self.vault.remember("The synthetic window is Tuesday.", "Window")
        self.private = self.vault.remember("The synthetic window is Sunday.", "Window", scope="project:private")

    def call(self, name="memory.context", arguments=None, thread="test-thread"):
        return {"method": "tools/call", "params": {
            "name": name, "arguments": arguments if arguments is not None else {"query": "synthetic window"},
            "_meta": {"threadId": thread},
        }}

    def incoming(self, requests):
        return "".join(json.dumps({"jsonrpc": "2.0", "id": i, **request}) + "\n"
                       for i, request in enumerate(requests, 1))

    def serve_at(self, cwd, requests, args=None):
        output = io.StringIO()
        with patch("ai_dememory.builtin_modules.mcp.Path.cwd", return_value=cwd):
            self.assertEqual(serve(self.services, args or ["--auto-scope"],
                                   io.StringIO(self.incoming(requests)), output), 0)
        return [json.loads(line) for line in output.getvalue().splitlines()]

    def test_home_stdio_initializes_recalls_and_proposes_in_global_scope(self):
        requests = [{"method": "initialize"}, {"method": "tools/list"}, self.call(),
                    self.call("memory.propose", {"title": "Candidate", "content": "Review this shared preference."})]
        result = subprocess.run([sys.executable, "-m", "ai_dememory", "--vault", str(self.vault.root),
                                 "serve", "mcp", "--auto-scope"], cwd=self.home,
                                input=self.incoming(requests), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 4)
        self.assertIn("global", responses[0]["result"]["instructions"])
        tools = {tool["name"]: tool for tool in responses[1]["result"]["tools"]}
        self.assertEqual(tools["memory.context"]["inputSchema"]["properties"]["scope"]["enum"], ["global"])
        self.assertNotIn("Unavailable", tools["memory.propose"]["description"])
        context = json.loads(responses[2]["result"]["content"][0]["text"])
        self.assertEqual(context["memory_ids"], [self.shared.memory_id])
        proposal = json.loads(responses[3]["result"]["content"][0]["text"])
        self.assertEqual(proposal["status"], "pending")
        self.assertEqual(ProposalStore(self.vault).list()[0].scope, "global")
        self.assertEqual(self.vault.memory_count(), 2)

    def test_root_falls_back_but_explicit_scopes_keep_their_behavior(self):
        responses = self.serve_at(Path(self.home.anchor), [{"method": "initialize"}, self.call()])
        self.assertIn("global", responses[0]["result"]["instructions"])
        self.assertEqual(json.loads(responses[1]["result"]["content"][0]["text"])["memory_ids"],
                         [self.shared.memory_id])
        for scope in ("global", "project:private"):
            with self.subTest(scope=scope):
                responses = self.serve_at(self.home, [self.call(), self.call("memory.propose", {
                    "title": "Candidate", "content": "Review this."})], ["--scope", scope])
                ids = json.loads(responses[0]["result"]["content"][0]["text"])["memory_ids"]
                self.assertIn(self.shared.memory_id, ids)
                self.assertEqual(self.private.memory_id in ids, scope == "project:private")
                self.assertIn("error", responses[1])

    def test_global_fallback_keeps_scope_thread_and_enable_checks(self):
        missing_meta = self.call()
        missing_meta["params"].pop("_meta")
        requests = [missing_meta, self.call(arguments={"query": "window", "scope": "project:private"}),
                    self.call(), self.call(thread="another-thread")]
        responses = self.serve_at(self.home, requests)
        for index in (0, 1, 3):
            self.assertEqual(responses[index]["error"]["code"], -32602)
        self.assertIn("result", responses[2])
        binding = ClientBinding(self.home)
        binding.check(self.call())
        set_module_enabled("harness-codex", False)
        with self.assertRaisesRegex(ValueError, "disabled"):
            binding.check(self.call())
        self.assertEqual(self.serve_at(self.home, [{"method": "tools/list"}])[0]["result"]["tools"], [])

    def test_configured_home_and_rebinding_are_not_global_fallback(self):
        binding = ClientBinding(self.home)
        configure_project(self.home, scope="project:private")
        with self.assertRaisesRegex(ValueError, "rebound"):
            binding.check(self.call())
        self.assertEqual(ClientBinding(self.home).scope, "project:private")
        responses = self.serve_at(self.home, [self.call()])
        ids = json.loads(responses[0]["result"]["content"][0]["text"])["memory_ids"]
        self.assertIn(self.private.memory_id, ids)

    def test_invalid_project_config_does_not_become_global_fallback(self):
        (self.config / "projects.json").write_text("invalid", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.serve_at(self.home, [{"method": "initialize"}])

    def test_global_alias_exclusion_applies_to_mcp_and_hook(self):
        alias = self.root / "alias"
        alias.mkdir()
        configure_project(alias, scope="global", client="codex", enabled=False)
        responses = self.serve_at(self.home, [{"method": "tools/list"}, self.call()])
        self.assertEqual(responses[0]["result"]["tools"], [])
        self.assertIn("error", responses[1])
        self.assertEqual(json.loads(self.run_hook(self.home).stdout), {})

    def test_global_learning_preserves_native_source_identity(self):
        request = self.call("memory.learn", {
            "title": "Preference", "content": "Prefer concise answers.", "scope": "global", "event_id": "preference",
            "source": {"provider": "current", "session": "current", "turn": "current",
                       "excerpt": "Prefer concise answers.", "evidence_kind": "user_statement"},
        })
        request["params"]["_meta"]["x-codex-turn-metadata"] = {"thread_id": "test-thread", "turn_id": "test-turn"}
        response = self.serve_at(self.home, [request])[0]
        self.assertIn("result", response)
        memory = next(item for item in self.services.list_memories("global") if item["title"] == "Preference")
        self.assertEqual(memory["source"]["provider"], "codex")
        self.assertEqual(memory["source"]["session"], "test-thread")
        self.assertEqual(memory["source"]["turn"], "test-turn")

    def test_configured_global_home_keeps_bound_proposal_behavior(self):
        binding = ClientBinding(self.home)
        configure_project(self.home, scope="global")
        with self.assertRaisesRegex(ValueError, "rebound"):
            binding.check(self.call())
        response = self.serve_at(self.home, [self.call("memory.propose", {
            "title": "Candidate", "content": "Review this."})])[0]
        self.assertIn("error", response)

    def test_auto_hooks_recall_global_from_home_and_root(self):
        for cwd in (self.home, Path(self.home.anchor)):
            for client in ("codex", "claude"):
                with self.subTest(cwd=cwd, client=client):
                    result = self.run_hook(cwd, client)
                    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                    self.assertIn("scope: global", context)
                    self.assertIn("Tuesday", context)
                    self.assertNotIn("Sunday", context)

    def run_hook(self, cwd, client="codex", event="UserPromptSubmit", scope=None):
        payload = {"hook_event_name": event, "cwd": str(cwd), "source": "startup", "prompt": "synthetic window"}
        result = subprocess.run([sys.executable, "-m", "ai_dememory.harness", "--vault", str(self.vault.root),
                                 "--config-dir", str(self.config), "--client", client,
                                 *(["--scope", scope] if scope else ["--auto-scope"])],
                                cwd=self.home, input=json.dumps(payload), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result

    def test_home_session_start_explicit_scope_and_disabled_hook(self):
        result = self.run_hook(self.home, event="SessionStart")
        self.assertIn("scope global", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
        result = self.run_hook(self.home, scope="project:private")
        self.assertIn("Sunday", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
        set_module_enabled("harness-codex", False)
        self.assertEqual(json.loads(self.run_hook(self.home).stdout), {})

    def test_strict_project_resolution_still_rejects_unbound_home(self):
        with self.assertRaisesRegex(ValueError, "No project binding"):
            resolve_project(self.home)
