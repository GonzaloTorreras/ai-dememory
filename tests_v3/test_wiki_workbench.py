"""HTTP boundary for the optional project-wiki dashboard, using synthetic data."""
from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ai_dememory.builtin_modules.workbench import WorkbenchServer
from ai_dememory.core import CoreServices
from ai_dememory.vault import Vault
from ai_dememory.config import set_module_enabled


class WikiWorkbenchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {"AI_DEMEMORY_CONFIG_DIR": str(Path(temporary.name) / "config")})
        environment.start(); self.addCleanup(environment.stop)
        self.server = WorkbenchServer(CoreServices(Vault.create(Path(temporary.name) / "vault")), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start(); self.addCleanup(self.stop)

    def test_real_service_project_save_recall_correction_and_scope_isolation(self):
        set_module_enabled("wiki", True)
        project = self.server.services.vault.root.parent / "renovation"
        project.mkdir()
        code, body = self.request("/api/wiki/attach", {"root":str(project), "confirmed":True})
        self.assertEqual(code, 200, body)
        project_id = json.loads(body)["project"]["id"]
        content = "# Restore tests\n\nCheck attachments, not only records. A completed upload is not a verified restore."
        code, body = self.request("/api/wiki/save", {"project_id":project_id, "path":"lessons.md", "content":content})
        self.assertEqual(code, 200, body)
        revision = json.loads(body)["page"]["revision"]
        code, body = self.request("/api/wiki/recall", {"project_id":project_id, "query":"restore attachments"})
        self.assertEqual(code, 200, body)
        result = json.loads(body)
        self.assertIn("not a verified restore", result["context"])
        self.assertEqual(result["model_calls"], 0)
        edit = {"project_id":project_id,"path":"lessons.md", "content":content + "\n\nRetain original filenames.", "expected_revision":revision}
        self.assertEqual(self.request("/api/wiki/save", edit)[0], 200)
        self.assertEqual(self.request("/api/wiki/save", edit)[0], 400)
        other = project.parent / "research"; other.mkdir()
        code, body = self.request("/api/wiki/attach", {"root":str(other), "confirmed":True})
        self.assertEqual(code, 200, body)
        other_id = json.loads(body)["project"]["id"]
        code, body = self.request("/api/wiki/recall", {"project_id":other_id, "query":"restore attachments"})
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["sources"], [])

    def stop(self):
        self.server.shutdown(); self.thread.join(2); self.server.server_close()
        self.assertFalse(self.thread.is_alive())

    def request(self, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        base = {"Content-Type": "application/json", "X-DeMemory-Token": self.server.token}
        base.update(headers or {})
        try:
            connection.request("GET" if data is None else "POST", path,
                               body=None if data is None else json.dumps(data), headers=base)
            result = connection.getresponse()
            return result.status, result.read()
        finally:
            connection.close()

    def test_disabled_wiki_never_loads_its_service(self):
        with patch("ai_dememory.builtin_modules.workbench.load_enabled_module", side_effect=AssertionError("module import")):
            code, body = self.request("/api/wiki/list", {})
        self.assertEqual(code, 400, body)
        self.assertIn("Enable the optional wiki", body.decode())
        self.assertIsNone(self.server._wiki_service)
        code, body = self.request("/api/state")
        self.assertEqual(code, 200, body)
        self.assertFalse(json.loads(body)["wiki_enabled"])

    def test_denied_requests_never_enter_the_wiki_dispatcher(self):
        service = Mock()
        with patch.object(self.server, "wiki", return_value=service) as loader:
            for headers in ({"X-DeMemory-Token": "invalid"}, {"Origin": "https://unrelated.example"}):
                self.assertEqual(self.request("/api/wiki/save", {"path": "lessons.md"}, headers)[0], 403)
            loader.assert_not_called()
            service.action.assert_not_called()

    def test_only_known_actions_are_dispatched_without_rewriting_confirmation(self):
        service = Mock(); service.action.return_value = {"context": "Synthetic source", "model_calls": 0}
        payload = {"project_id": "synthetic", "query": "restoration", "mode": "assisted", "confirmed": True,
                   "expected_config": "a" * 64}
        with patch.object(self.server, "wiki", return_value=service):
            code, body = self.request("/api/wiki/recall", payload)
            self.assertEqual(code, 200, body)
            service.action.assert_called_once_with("recall", payload)
            self.assertEqual(self.request("/api/wiki/arbitrary-code", {})[0], 400)
        self.assertEqual(service.action.call_count, 1)

    def test_validation_errors_from_service_are_not_successful_writes(self):
        service = Mock(); service.action.side_effect = ValueError("Page changed; reload its revision")
        payload = {"project_id": "synthetic", "path": "lessons.md", "content": "# Changed", "expected_revision": "0" * 64}
        with patch.object(self.server, "wiki", return_value=service):
            code, body = self.request("/api/wiki/save", payload)
        self.assertEqual(code, 400)
        self.assertIn("reload its revision", body.decode())

    def test_assets_explain_confirmed_assisted_recall_and_local_schedule(self):
        code, html = self.request("/")
        self.assertEqual(code, 200)
        text = html.decode()
        for expected in ('id="wiki"', 'id="wiki-recall-dialog"', 'id="wiki-page-revision"',
                         'id="wiki-schedule-hours"', 'No historical conversation ingestion'):
            self.assertIn(expected, text)
        self.assertIn('id="wiki-recall-confirm"', text)
        self.assertIn('id="wiki-automatic-recall" type="checkbox"', text)
        self.assertIn('session-key profiles are rejected', text)
        code, script = self.request("/app.js")
        self.assertEqual(code, 200)
        self.assertIn(b"expected_revision: wikiState.page?.revision || null", script)
        self.assertIn(b"report.broken_links || []", script)
        self.assertIn(b"...warnings, ...brokenLinks", script)
        self.assertIn(b"page: wikiState.dirty ? undefined : result.page", script)


if __name__ == "__main__":
    unittest.main()
