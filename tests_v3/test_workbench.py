from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch, Mock

from ai_dememory.builtin_modules.workbench import MAX_BODY, WorkbenchServer
from ai_dememory.core import CoreServices
from ai_dememory.jobs import LearningJobs
from ai_dememory.settings import load_settings, save_settings
from ai_dememory.vault import Vault


class WorkbenchTests(unittest.TestCase):
    def test_history_schedule_progress_through_confirmed_http_flow(self):
        self.request('/api/modules', {'id': 'sources', 'enabled': True})
        root = Path(self.temp.name).resolve() / 'history'; root.mkdir()
        rows = [{'type': 'session_meta', 'payload': {'id': 'http-test', 'source': 'vscode'}}]
        rows += [{'type': 'event_msg', 'payload': {'type': 'user_message', 'message': f'Synthetic preference {i}'}} for i in range(25)]
        (root / 'session.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        payload = {'root': str(root), 'format': 'codex', 'mode': 'history', 'scope': 'project:test',
                   'interval_hours': 1, 'enabled': False}
        code, body, _ = self.request('/api/source-schedules/save', payload)
        self.assertEqual(code, 200, body)
        id = json.loads(body)['saved']
        with patch.object(self.server.jobs, 'extract', return_value={'learned': []}) as extract:
            self.assertEqual(self.request('/api/source-schedules/run', {'id': id})[0], 400)
            extract.assert_not_called()
            for size in (20, 5):
                code, body, _ = self.request('/api/source-schedules/run', {'id': id, 'confirmed': True})
                self.assertEqual(code, 200, body)
                self.assertEqual(len(extract.call_args.args[0]), size)
                self.assertEqual(extract.call_args.args[1], 'project:test')
        rule = self.state()['source_schedules'][0]
        self.assertEqual(rule['mode'], 'history')
        self.assertEqual(rule['progress']['messages'], 25)
        self.assertFalse(rule['enabled'])
        self.assertNotIn('scan_after', rule)

    def test_batch_preflight_and_independent_harness_switches(self):
        self.request('/api/modules',{'id':'sources','enabled':True})
        with patch.object(self.server.jobs,'extract') as extract:
            code, _, _ = self.request('/api/sources/validate',{'tokens':['expired']})
            self.assertEqual(code,400)
            extract.assert_not_called()
        self.request('/api/modules',{'id':'harness','enabled':True})
        self.request('/api/modules',{'id':'harness-codex','enabled':False})
        modules={m['module_id']:m['enabled'] for m in self.state()['modules']}
        self.assertFalse(modules['harness'])
        self.assertFalse(modules['harness-codex'])
        self.assertTrue(modules['harness-claude'])

    def test_model_discovery_uses_draft_and_never_returns_key(self):
        profile = {"kind":"responses", "base_url":"https://api.example.test/v1", "model":"catalog", "auth":"session", "api_key_env":""}
        with patch("ai_dememory.providers.list_provider_models", return_value=["model-a", "model-b"]) as models:
            code, body, _ = self.request("/api/provider-models", {"profile":profile,"api_key":"synthetic-catalog-key"})
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["models"], ["model-a","model-b"])
        self.assertNotIn(b"synthetic-catalog-key", body)
        models.assert_called_once_with(profile, "synthetic-catalog-key")
        self.assertEqual(self.state()["settings"]["providers"], {})

    def test_sources_are_opt_in_and_preview_is_the_extraction_boundary(self):
        from ai_dememory.settings import DEFAULT_SETTINGS, save_settings
        profile = {"kind":"openai_compatible","base_url":"http://localhost:11434/v1","model":"test","auth":"none","api_key_env":""}
        save_settings(self.services.vault, {**DEFAULT_SETTINGS,"providers":{"local":profile}, "routes":{"extract":{"primary":"local","fallback":[],"max_output_tokens":100}}})
        root = Path(self.temp.name).resolve() / "conversations"
        root.mkdir()
        source = root / "session.json"
        source.write_text(json.dumps({"messages":[{"role":"user","content":"Synthetic deployment window Thursday."},{"role":"assistant","content":"Untrusted assistant prose."}]}), encoding="utf-8")
        payload = {"root":str(root),"format":"generic","file":"session.json","scope":"project:test"}
        code, _, _ = self.request("/api/sources/preview", payload)
        self.assertEqual(code, 400)
        self.assertEqual(self.request("/api/modules", {"id":"sources","enabled":True})[0], 200)
        code, body, _ = self.request("/api/sources/preview", payload)
        self.assertEqual(code, 200, body)
        preview = json.loads(body)
        self.assertEqual(preview["destinations"], ["local"])
        self.assertNotIn("Untrusted assistant", body.decode())
        source.write_text('{"messages":[{"role":"user","content":"Changed after preview"}]}', encoding="utf-8")
        request = {"preview_token":preview["preview_token"],"confirmed":True}
        with patch.object(self.server.jobs, "extract", return_value={"learned":[]}) as extract:
            self.assertEqual(self.request("/api/sources/extract", request)[0], 200)
            self.assertEqual(extract.call_args.args[0], preview["messages"])
            self.assertEqual(extract.call_args.args[1], "project:test")
        self.assertEqual(self.request("/api/sources/extract", {"preview_token":preview["preview_token"]})[0], 400)
        self.request("/api/modules", {"id":"sources","enabled":False})
        self.assertEqual(self.server._previews, {})
        self.assertEqual(self.request("/api/sources/extract", request)[0], 400)

    def test_source_preview_rejects_changed_provider_routes_and_expiry(self):
        from ai_dememory.settings import load_settings, save_settings
        token = "preview-test"
        self.server._previews[token] = {"created":0,"messages":[],"scope":"global","routing":[{},{}]}
        self.request("/api/modules", {"id":"sources","enabled":True})
        self.assertEqual(self.request("/api/sources/extract", {"preview_token":token,"confirmed":True})[0], 400)
        import time
        self.server._previews[token] = {"created":time.monotonic(),"messages":[],"scope":"global","routing":[{},{}]}
        settings = load_settings(self.services.vault)
        settings["providers"]["added"] = {"kind":"responses","base_url":"https://api.example.test/v1","model":"test","api_key_env":""}
        save_settings(self.services.vault, settings)
        with patch.object(self.server.jobs, "extract") as extract:
            self.assertEqual(self.request("/api/sources/extract", {"preview_token":token,"confirmed":True})[0], 400)
            extract.assert_not_called()

    def test_codex_login_is_explicit_and_module_gated(self):
        self.assertEqual(self.request("/api/codex/status", {})[0], 400)
        fake = Mock()
        fake.start_login.return_value = {"verification_url":"https://auth.openai.com/codex/device","user_code":"SYNTHETIC"}
        with patch("ai_dememory.builtin_modules.workbench.load_enabled_module", return_value=fake):
            code, body, _ = self.request("/api/codex/login", {"method":"device"})
            self.assertEqual(code, 200, body)
            fake.start_login.assert_called_once_with("device")
            self.assertEqual(self.request("/api/codex/cancel", {})[0], 200)
            fake.cancel_login.assert_called_once()

    def test_codex_binary_failure_has_same_guidance_in_login_and_status(self):
        from ai_dememory import codex_subscription
        error = codex_subscription.CodexSubscriptionError("codex_binary_required")
        with patch("ai_dememory.builtin_modules.workbench.load_enabled_module", return_value=codex_subscription), \
                patch.object(codex_subscription, "_AppServer", side_effect=error):
            code, body, _ = self.request("/api/codex/login", {"method": "device"})
            self.assertEqual(code, 400)
            self.assertEqual(json.loads(body)["error"], str(error))
            code, body, _ = self.request("/api/codex/status", {})
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)["error"], "codex_binary_required")
            self.assertEqual(json.loads(body)["message"], str(error))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {"AI_DEMEMORY_CONFIG_DIR": str(Path(self.temp.name) / "config")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.services = CoreServices(Vault.create(Path(self.temp.name) / "vault"))
        self.server = WorkbenchServer(self.services, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join(2)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())

    def request(self, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        base = {"Content-Type": "application/json", "X-DeMemory-Token": self.server.token}
        base.update(headers or {})
        try:
            connection.request("GET" if data is None else "POST", path,
                               body=None if data is None else json.dumps(data), headers=base)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def state(self, query=""):
        code, body, _ = self.request("/api/state" + query)
        self.assertEqual(code, 200, body)
        return json.loads(body)

    def test_assets_token_csp_and_no_remote_bind(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for path in ("/", "/app.js", "/app.css"):
            code, body, headers = self.request(path)
            self.assertEqual(code, 200)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
            self.assertEqual(headers["Cache-Control"], "no-store")
            if path == "/":
                self.assertIn(self.server.token.encode(), body)
                self.assertNotIn(b"__SESSION_TOKEN__", body)
        self.assertEqual(self.request("/../settings.json")[0], 404)

    def test_host_origin_and_token_enforced(self):
        self.assertEqual(self.request("/api/state", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("/api/learn", {}, {"X-DeMemory-Token": ""})[0], 403)
        self.assertEqual(self.services.vault.memory_count(), 0)

    def test_new_scope_is_blank_plain_text_separate_from_existing_options(self):
        class Inputs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.fields = {}

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if "id" in attributes:
                    self.fields[attributes["id"]] = (tag, attributes)

        code, body, _ = self.request("/")
        self.assertEqual(code, 200)
        parsed = Inputs()
        parsed.feed(body.decode())
        tag, field = parsed.fields["scope"]
        self.assertEqual(tag, "input")
        self.assertEqual(field["type"], "text")
        self.assertEqual(field.get("value", ""), "")
        self.assertEqual(field["autocomplete"], "off")
        self.assertNotIn("list", field)
        self.assertTrue(field["placeholder"])
        self.assertEqual(parsed.fields["scope-selector"][0], "select")
        self.assertEqual(parsed.fields["schedule-scope"][1]["list"], "scope-options")
        self.assertEqual(parsed.fields["scope-options"][0], "datalist")
        self.assertIn(b"needs no DeMemory model provider", body)

    def test_complete_scoped_save_and_forget(self):
        payload = {"title": "Preference", "content": "Use readable examples. " * 200, "scope": "project:demo"}
        code, body, _ = self.request("/api/learn", payload)
        self.assertEqual(code, 200, body)
        saved = json.loads(body)
        self.assertEqual(saved["status"], "active")
        self.assertEqual(saved["source"]["provider"], "workbench")
        self.assertEqual(self.state()["memories"], [])
        self.assertEqual(len(self.state("?scope=project:demo")["memories"]), 1)
        self.assertEqual(self.request("/api/forget", {"memory_id": saved["memory_id"], "scope": "global"})[0], 400)
        self.assertEqual(self.request("/api/forget", {"memory_id": saved["memory_id"], "scope": "project:demo"})[0], 200)
        self.assertEqual(self.state("?scope=project:demo")["memories"], [])
        self.assertEqual(self.state("?scope=project:demo&inactive=true")["memories"][0]["status"], "forgotten")

    def test_settings_schedule_and_manual_consolidation(self):
        settings = self.state()["settings"]
        settings["schedule"] = {"enabled": True, "interval_hours": 24}
        self.assertEqual(self.request("/api/settings", settings)[0], 200)
        state = self.state()
        self.assertTrue(state["schedule"]["enabled"])
        self.assertEqual(state["schedule"]["execution"], "foreground_or_one_shot")
        self.assertFalse(state["scheduled_task"]["installed_receipt"])
        self.assertEqual(state["usage"]["calls"], 0)
        self.assertEqual(self.request("/api/consolidate", {"scope": "global"})[0], 200)
        self.assertIsNotNone(self.state()["schedule"]["last_run_at"])

    def test_saved_schedule_scope_is_independent_from_browsing_and_manual_runs(self):
        settings = self.state()["settings"]
        settings["schedule"] = {"enabled": True, "interval_hours": 24, "scope": "project:empty"}
        self.assertEqual(self.request("/api/settings", settings)[0], 200)
        before = self.state("?scope=project:browsing")
        self.assertIn("project:empty", before["scopes"])
        self.assertEqual(before["schedule"]["scope"], "project:empty")
        code, body, _ = self.request("/api/consolidate", {"scope": "project:manual"})
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["scope"], "project:manual")
        after = self.state()
        self.assertEqual(after["settings"]["schedule"], settings["schedule"])
        self.assertEqual(after["schedule"]["next_run_at"], before["schedule"]["next_run_at"])
        self.assertEqual(after["schedule"]["last_run_scope"], "project:manual")
        self.assertEqual(after["usage"]["calls"], 0)

    def test_invalid_schedule_scope_cannot_replace_saved_configuration(self):
        before = self.state()["settings"]
        for scope in (None, "", "project with spaces"):
            settings = {**before, "schedule": {**before["schedule"], "scope": scope}}
            self.assertEqual(self.request("/api/settings", settings)[0], 400)
            self.assertEqual(self.state()["settings"], before)

    def test_long_unicode_and_escaped_excerpts_are_bounded(self):
        for content in ("Preferir español 🙂 " * 200, '"' * 1000):
            code, body, _ = self.request("/api/learn", {"title": "Quoted preference", "content": content})
            self.assertEqual(code, 200, body)
            self.assertLess(len(json.dumps(json.loads(body)["source"], ensure_ascii=False).encode()), 1024)

    def test_extract_real_job_mocked_provider(self):
        class Engine:
            def __init__(self, vault):
                pass

            def run(self, *args, **kwargs):
                return {"text": json.dumps({"memories": [{"title": "Preference", "content": "I prefer Python.",
                    "evidence": "I prefer Python.", "message_index": 0}]}), "provider": "fake", "model": "test"}

        self.server.jobs = LearningJobs(self.services, engine_factory=Engine)
        code, body, _ = self.request("/api/extract", {"messages": [{"role": "user", "content": "I prefer Python."}], "scope": "global"})
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["learned"][0]["status"], "active")

    def test_bad_input_is_rejected_without_stopping_server(self):
        self.assertEqual(self.request("/api/learn", {"title": None, "content": None})[0], 400)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request("POST", "/api/learn", headers={"Content-Length": str(MAX_BODY + 1)})
            self.assertEqual(connection.getresponse().status, 413)
        finally:
            connection.close()
        self.assertEqual(self.request("/api/learn", {}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.state()["memories"], [])

    def session_settings(self):
        settings = self.state()["settings"]
        settings["providers"]["cloud"] = {"kind": "responses", "base_url": "https://example.test/v1",
                                          "model": "test", "auth": "session", "api_key_env": ""}
        settings["routes"]["extract"] = {"primary": "cloud", "fallback": [], "max_output_tokens": 128}
        self.assertEqual(self.request("/api/settings", settings)[0], 200)
        return settings

    @staticmethod
    def credential_payload(settings, key):
        profile = settings["providers"]["cloud"]
        return {"provider": "cloud", "api_key": key,
                "expected": {field: profile[field] for field in ("kind", "base_url", "auth")}}

    def test_session_credentials_are_ephemeral_and_bound_to_profile(self):
        settings = self.session_settings()
        key = "ui-session-canary-123"
        payload = self.credential_payload(settings, key)
        self.assertFalse(self.state()["credentials"]["cloud"]["configured"])
        self.assertEqual(self.request("/api/credentials", payload, {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("/api/credentials", payload, {"X-DeMemory-Token": "bad"})[0], 403)
        code, body, _ = self.request("/api/credentials", payload)
        self.assertEqual(code, 200, body)
        self.assertNotIn(key, body.decode())
        self.assertTrue(self.state()["credentials"]["cloud"]["configured"])
        self.assertNotIn(key, json.dumps(self.state()))
        self.assertNotIn(key, (self.services.vault.root / "settings.json").read_text())
        profile = settings["providers"]["cloud"]
        self.assertEqual(self.server.resolve_credential("cloud", profile), key)
        profile["model"] = "different-model"
        self.assertEqual(self.request("/api/settings", settings)[0], 200)
        self.assertTrue(self.state()["credentials"]["cloud"]["configured"])
        for field, value in (("base_url", "https://other.test/v1"), ("kind", "anthropic")):
            self.assertEqual(self.request("/api/credentials", payload)[0], 200)
            profile[field] = value
            self.assertEqual(self.request("/api/settings", settings)[0], 200)
            self.assertFalse(self.state()["credentials"]["cloud"]["configured"])
            payload = self.credential_payload(settings, key)
        self.assertEqual(self.request("/api/credentials", payload)[0], 200)
        self.assertEqual(self.request("/api/credentials", {"provider": "cloud", "api_key": ""})[0], 200)
        self.assertFalse(self.state()["credentials"]["cloud"]["configured"])
        self.request("/api/credentials", payload)
        self.stop()
        self.assertEqual(self.server._credentials, {})

    def test_denied_post_consumes_bounded_body_without_parsing_or_action(self):
        with patch.object(self.server.RequestHandlerClass, "_action") as action:
            for _ in range(20):
                for headers in ({"Origin":"https://evil.example"}, {"X-DeMemory-Token":"wrong"}):
                    self.assertEqual(self.request("/api/learn", {"content":"denied synthetic text"}, headers)[0], 403)
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
            try:
                connection.request("POST", "/api/learn", body="not-json", headers={"Content-Type":"application/json", "X-DeMemory-Token":"wrong"})
                self.assertEqual(connection.getresponse().status, 403)
            finally:
                connection.close()
            action.assert_not_called()
        self.assertEqual(self.state()["memories"], [])

    def test_environment_status_removal_and_external_profile_edit(self):
        settings = self.session_settings()
        payload = self.credential_payload(settings, "ephemeral-canary")
        self.request("/api/credentials", payload)
        settings["providers"]["cloud"]["base_url"] = "https://edited.test/v1"
        save_settings(self.services.vault, settings)
        self.assertEqual(self.server.resolve_credential("cloud", settings["providers"]["cloud"]), "")
        payload = self.credential_payload(settings, "ephemeral-canary")
        self.request("/api/credentials", payload)
        settings["providers"]["cloud"].update(auth="environment", api_key_env="WORKBENCH_TEST_KEY")
        self.request("/api/settings", settings)
        with patch.dict(os.environ, {"WORKBENCH_TEST_KEY": "environment-canary"}):
            self.assertEqual(self.state()["credentials"]["cloud"], {"mode": "environment", "configured": True})
            self.assertNotIn("environment-canary", json.dumps(self.state()))
        code, body, _ = self.request("/api/credentials", payload)
        self.assertEqual(code, 400)
        self.assertNotIn("ephemeral-canary", body.decode())
        settings["providers"] = {}
        settings["routes"] = {}
        self.request("/api/settings", settings)
        self.assertEqual(self.state()["credentials"], {})
        self.assertEqual(self.server._credentials, {})

    def test_session_key_reaches_real_job_without_persisting(self):
        settings = self.session_settings()
        self.request("/api/credentials", self.credential_payload(settings, "job-session-canary"))
        result = {"memories": [{"title": "Preference", "content": "I prefer Python.",
                               "evidence": "I prefer Python.", "message_index": 0}]}
        def transport(url, payload, headers, timeout):
            self.assertEqual(headers["Authorization"], "Bearer job-session-canary")
            return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}
        with patch("ai_dememory.providers.http_transport", transport):
            code, body, _ = self.request("/api/extract", {"messages": [{"role": "user", "content": "I prefer Python."}]})
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["learned"][0]["status"], "active")
        self.assertNotIn("job-session-canary", json.dumps(self.state()))
        for path in self.services.vault.root.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"job-session-canary", path.read_bytes())

    def test_scheduled_consolidation_resolves_session_key(self):
        settings = self.session_settings()
        settings["routes"]["consolidate"] = settings["routes"]["extract"].copy()
        settings["schedule"]["enabled"] = True
        self.request("/api/settings", settings)
        self.request("/api/credentials", self.credential_payload(settings, "scheduled-canary"))
        for title, content in (("One", "Use Python for scripts."), ("Two", "Prefer readable examples.")):
            self.assertEqual(self.request("/api/learn", {"title": title, "content": content})[0], 200)
        due = self.state()["schedule"]["next_run_at"]
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append(headers)
            return {"output": [{"type": "message", "content": [{"type": "output_text", "text": '{"summary":null}'}]}]}
        with patch("ai_dememory.providers.http_transport", transport):
            result = self.server.jobs.run_due(now=due)
        self.assertTrue(result["no_op"])
        self.assertEqual(calls[0]["Authorization"], "Bearer scheduled-canary")
        self.assertNotIn("scheduled-canary", json.dumps(self.state()))

    def test_stale_tab_cannot_attach_key_to_changed_endpoint(self):
        settings = self.session_settings()
        tab_a_payload = self.credential_payload(settings, "stale-tab-key-canary")
        settings["providers"]["cloud"]["base_url"] = "https://tab-b.test/v1"
        self.assertEqual(self.request("/api/settings", settings)[0], 200)
        code, body, _ = self.request("/api/credentials", tab_a_payload)
        self.assertEqual(code, 400)
        self.assertNotIn("stale-tab-key-canary", body.decode())
        self.assertNotIn("tab-b.test", body.decode())
        self.assertFalse(self.state()["credentials"]["cloud"]["configured"])
        self.assertEqual(self.server._credentials, {})
        for expected in (None, {}, {"kind": "responses", "base_url": [], "auth": "session"}):
            self.assertEqual(self.request("/api/credentials", {**tab_a_payload, "expected": expected})[0], 400)
        self.assertEqual(self.request("/api/credentials", {"provider": "cloud", "api_key": "missing-identity"})[0], 400)
        self.assertEqual(self.request("/api/credentials", self.credential_payload(settings, "fresh-tab-key"))[0], 200)


if __name__ == "__main__":
    unittest.main()
