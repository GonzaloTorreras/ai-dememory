from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_dememory.builtin_modules.workbench import MAX_BODY, WorkbenchServer
from ai_dememory.core import CoreServices
from ai_dememory.jobs import LearningJobs
from ai_dememory.vault import Vault


class WorkbenchTests(unittest.TestCase):
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
        self.assertTrue(state["schedule"]["foreground_only"])
        self.assertEqual(state["usage"]["calls"], 0)
        self.assertEqual(self.request("/api/consolidate", {"scope": "global"})[0], 200)
        self.assertIsNotNone(self.state()["schedule"]["last_run_at"])

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
        self.assertEqual(self.request("/api/learn", {}, {"Content-Length": str(MAX_BODY + 1)})[0], 413)
        self.assertEqual(self.request("/api/learn", {}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.state()["memories"], [])


if __name__ == "__main__":
    unittest.main()
