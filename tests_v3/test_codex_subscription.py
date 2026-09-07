from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_dememory import codex_subscription as codex


# Real subprocess protocol fixture: never starts Codex, opens a browser, or calls a model.
_SERVER = r'''
import json, os, sys, time
from pathlib import Path
mode, logfile = sys.argv[1:]
logged_in = False
def emit(value):
    print(json.dumps(value), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    with open(logfile, 'a', encoding='utf-8') as log:
        log.write(json.dumps(request) + '\n')
    method, rid = request.get('method'), request.get('id')
    if method == 'initialized':
        continue
    if method == 'initialize':
        if mode == 'hang':
            time.sleep(30)
        if mode == 'exit':
            sys.exit(0)
        if mode == 'oversize':
            print('x' * 1000001, flush=True)
            continue
        result = {}
    elif method == 'account/read':
        kind = 'apiKey' if mode == 'apikey' else 'chatgpt'
        result = {'account': {'type': kind}}
        if mode in ('login', 'pending') and not logged_in:
            result = {'account': None}
    elif method == 'account/login/start':
        result = {'type':request['params']['type'], 'loginId':'test-login',
                  'verificationUrl':'https://auth.openai.com/codex/device',
                  'authUrl':'https://auth.openai.com/oauth/authorize', 'userCode':'TEST-1234'}
        logged_in = mode == 'login'
    elif method == 'account/login/cancel':
        result = {}
    elif method == 'model/list':
        result = {'data':[{'model':'test-model', 'supportedReasoningEfforts':[{'reasoningEffort':'low'}]},
                          {'model':'test-model'}], 'nextCursor':None}
    elif method == 'config/read':
        result = {'config':{'mcp_servers':{}, 'plugins':{}, 'model_provider':'openai', 'forced_login_method':'chatgpt'}}
    elif method == 'experimentalFeature/list':
        names = ['shell_tool','code_mode','code_mode_host','js_repl','plugins','hooks','multi_agent_v2']
        result = {'data':[{'name': name, 'enabled':mode == 'unsafe'} for name in names]}
        result['data'].append({'name':'skip_host_skill_discovery','enabled':True})
    elif method == 'thread/start':
        result = {'thread':{'id':'thread-test','ephemeral':True}, 'sandbox':{'type':'readOnly'}}
    elif method == 'turn/start':
        emit({'id':rid,'result':{'turn':{'id':'turn-test'}}})
        if mode == 'tool':
            emit({'id':900,'method':'item/commandExecution/requestApproval','params':{}})
            continue
        delta = 'x' * 1000 if mode == 'long' else 'A useful learning.'
        for method, params in [
            ('thread/tokenUsage/updated',{'tokenUsage':{'last':{'inputTokens':20,'outputTokens':4}}}),
            ('item/agentMessage/delta',{'delta':delta}),
            ('turn/completed',{'turn':{'status':'completed'}}),
        ]:
            emit({'method':method,'params':{'threadId':'thread-test', **params}})
        continue
    else:
        continue
    emit({'id':rid,'result':result})
'''


class CodexSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.script = self.root / "server.py"
        self.script.write_text(_SERVER, encoding="utf-8")
        self.log = self.root / "protocol.jsonl"
        self.env = patch.dict(os.environ, {"AI_DEMEMORY_CONFIG_DIR": str(self.root / "config")})
        self.env.start()

    def tearDown(self):
        codex.cancel_login()
        self.env.stop()
        self.temporary.cleanup()

    def server(self, mode="normal"):
        return patch.object(codex, "_command", return_value=[sys.executable, "-u", str(self.script), mode, str(self.log)])

    def requests(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_account_state_and_models_reap_children(self):
        with self.server():
            self.assertEqual(codex.login_status(), {"authenticated": True, "pending": False})
            self.assertEqual(codex.list_models(), ["test-model"])
        self.assertFalse(any(t.name == "dememory-codex-reader" and t.is_alive() for t in threading.enumerate()))
        self.assertEqual(list((self.root / "config" / "codex-account").glob("request-*")), [])

    def test_api_key_accounts_are_never_used(self):
        with self.server("apikey"):
            self.assertEqual(codex.login_status()["error"], "chatgpt_account_required")
            with self.assertRaisesRegex(codex.CodexSubscriptionError, "chatgpt_account_required"):
                codex.generate({"model": "test-model"}, "Summarize this", 128)
        self.assertFalse(any(r.get("method") == "turn/start" for r in self.requests()))

    def test_device_and_browser_login_only_return_public_flow_fields(self):
        for method in ("device", "browser"):
            with self.server("login"):
                flow = codex.start_login(method)
                self.assertEqual(set(flow), {"verification_url", "user_code", "login_id"})
                self.assertTrue(flow["verification_url"].startswith("https://auth.openai.com/"))
                self.assertEqual(codex.login_status(), {"authenticated": True, "pending": False})
                self.assertIsNone(codex._pending)

    def test_pending_login_cancel_closes_process_and_reader(self):
        with self.server("pending"):
            codex.start_login()
            child, _ = codex._pending
            self.assertTrue(codex.login_status()["pending"])
            codex.cancel_login()
            self.assertIsNotNone(child.process.poll())
            self.assertFalse(child.reader.is_alive())
            self.assertTrue(child.process.stdout.closed)
            self.assertFalse(Path(child.scratch.name).exists())

    def test_expiry_reaps_without_any_ui_poll(self):
        with self.server("pending"):
            child = codex._AppServer(lifetime=0.15)
            child.watchdog.join(timeout=5)
            self.assertIsNotNone(child.process.poll())
            self.assertFalse(child.reader.is_alive())
            self.assertTrue(child.process.stdout.closed)
            self.assertFalse(Path(child.scratch.name).exists())

    def test_hang_eof_and_oversized_protocol_are_bounded(self):
        for mode, reason in (("hang", "codex_timeout"), ("exit", "codex_process_exited"),
                             ("oversize", "codex_response_too_large")):
            with self.server(mode), self.assertRaisesRegex(codex.CodexSubscriptionError, reason):
                codex._AppServer(lifetime=0.2)

    def test_generation_is_ephemeral_and_has_no_execution_environment(self):
        with self.server():
            value = codex.generate({"model": "test-model"}, "Summarize this", 128)
        self.assertEqual(value, {"text": "A useful learning.", "usage": {"input_tokens": 20, "output_tokens": 4}})
        thread = next(r["params"] for r in self.requests() if r.get("method") == "thread/start")
        self.assertTrue(thread["ephemeral"])
        self.assertEqual(thread["environments"], [])
        self.assertEqual(thread["dynamicTools"], [])
        self.assertEqual(thread["sandbox"], "read-only")
        turn = next(r["params"] for r in self.requests() if r.get("method") == "turn/start")
        self.assertNotIn("max_output_tokens", turn)  # No invented server cap.
        self.assertEqual(turn["sandboxPolicy"]["access"]["readableRoots"], [thread["cwd"]])

    def test_unsupported_isolation_aborts_before_model_request(self):
        with self.server("unsafe"), self.assertRaisesRegex(codex.CodexSubscriptionError, "unsupported_tools_isolation"):
            codex.generate({"model": "test-model"}, "Summarize this", 128)
        self.assertFalse(any(r.get("method") == "turn/start" for r in self.requests()))

    def test_reasoning_effort_is_validated_against_catalog_and_forwarded(self):
        with self.server():
            codex.generate({"model": "test-model", "reasoning_effort": "low"}, "Summarize this", 128)
            with self.assertRaisesRegex(codex.CodexSubscriptionError, "unsupported_reasoning_effort"):
                codex.generate({"model": "test-model", "reasoning_effort": "high"}, "Summarize this", 128)
        turns = [r for r in self.requests() if r.get("method") == "turn/start"]
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["params"]["effort"], "low")

    def test_tool_request_and_output_overflow_abort_owned_process(self):
        for mode, reason in (("tool", "codex_tool_request_rejected"), ("long", "codex_response_too_large")):
            with self.server(mode), self.assertRaisesRegex(codex.CodexSubscriptionError, reason):
                codex.generate({"model": "test-model"}, "Summarize this", 32)
        self.assertFalse(any(t.name == "dememory-codex-reader" and t.is_alive() for t in threading.enumerate()))

    def test_environment_does_not_pass_credentials_or_existing_codex_home(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret", "CODEX_ACCESS_TOKEN": "secret",
                                     "CODEX_HOME": "old-home", "ANTHROPIC_API_KEY": "secret"}):
            env = codex._environment(self.root)
        self.assertEqual(env["CODEX_HOME"], str(self.root))
        self.assertFalse(any("KEY" in key or "TOKEN" in key for key in env))

    def test_explicit_active_vault_rejected_before_directory_creation(self):
        with self.assertRaisesRegex(codex.CodexSubscriptionError, "account_directory_inside_vault"):
            codex.validate_vault(self.root)
        self.assertFalse((self.root / "config").exists())

    def test_command_uses_only_owned_account_and_documented_flags(self):
        with patch.dict(os.environ, {"AI_DEMEMORY_CODEX_BIN": sys.executable}):
            args = codex._command()
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn('cli_auth_credentials_store="file"', args)
        self.assertIn("features.shell_tool=false", args)
        self.assertIn("features.skip_host_skill_discovery=true", args)


if __name__ == "__main__":
    unittest.main()
