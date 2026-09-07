"""Optional single-process loopback workbench; no remote deployment surface."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from ai_dememory.jobs import LearningJobs
from ai_dememory.models import ModuleManifest
from ai_dememory.providers import ProviderEngine, activity, usage_summary
from ai_dememory.settings import auth_mode, load_settings, save_settings

MAX_BODY = 256_000
ASSETS = {"/": ("index.html", "text/html"), "/app.css": ("app.css", "text/css"),
          "/app.js": ("app.js", "text/javascript")}


def get_manifest():
    return ModuleManifest("workbench", "1", "Local memory and learning dashboard",
                          ("memory", "settings", "activity", "consolidation"),
                          {"network": "loopback UI; configured providers", "child_processes": 0,
                           "persistent": False})


class WorkbenchServer(HTTPServer):
    def __init__(self, services, port=8765, jobs=None):
        self.services = services
        self._credentials = {}
        self.jobs = jobs or LearningJobs(services, engine_factory=lambda vault: ProviderEngine(
            vault, credential_resolver=self.resolve_credential))
        self.token = secrets.token_urlsafe(32)
        self.session = uuid4().hex
        self.last_tick = 0.0
        super().__init__(("127.0.0.1", port), WorkbenchHandler)

    @staticmethod
    def _identity(profile):
        return profile["kind"], profile["base_url"], auth_mode(profile)

    def prune_credentials(self, settings):
        profiles = settings["providers"]
        for name, (identity, _key) in list(self._credentials.items()):
            if name not in profiles or identity != self._identity(profiles[name]):
                del self._credentials[name]

    def resolve_credential(self, name, profile):
        settings = load_settings(self.services.vault)
        self.prune_credentials(settings)
        entry = self._credentials.get(name)
        return entry[1] if entry and entry[0] == self._identity(profile) else ""

    def credential_status(self, settings):
        self.prune_credentials(settings)
        return {name: {"mode": auth_mode(profile), "configured":
                bool(self._credentials.get(name)) if auth_mode(profile) == "session" else
                bool(os.environ.get(profile["api_key_env"])) if auth_mode(profile) == "environment" else True}
                for name, profile in settings["providers"].items()}

    def set_credential(self, data):
        if not {"provider", "api_key"} <= data.keys() or data.keys() - {"provider", "api_key", "expected"}:
            raise ValueError("Expected provider, api_key and optional expected identity fields")
        name, key = data["provider"], data["api_key"]
        if not isinstance(name, str) or not isinstance(key, str) or len(key) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError("API key must be at most 4096 printable characters without spaces")
        settings = load_settings(self.services.vault)
        self.prune_credentials(settings)
        profile = settings["providers"].get(name)
        if profile is None or auth_mode(profile) != "session":
            raise ValueError("Save a provider with session authentication first")
        if key:
            expected = data.get("expected")
            if (not isinstance(expected, dict) or set(expected) != {"kind", "base_url", "auth"}
                    or any(not isinstance(value, str) for value in expected.values())
                    or (expected["kind"], expected["base_url"], expected["auth"]) != self._identity(profile)):
                raise ValueError("Provider configuration changed. Reload it before adding an API key.")
            self._credentials[name] = (self._identity(profile), key)
        else:
            self._credentials.pop(name, None)
        return {"provider": name, **self.credential_status(settings)[name]}

    def server_close(self):
        self._credentials.clear()
        super().server_close()

    def service_actions(self):
        if time.monotonic() - self.last_tick < 1:
            return
        self.last_tick = time.monotonic()
        try:
            self.jobs.run_due()
        except (ValueError, OSError, sqlite3.Error):
            # Job failures have their own safe status; never stop serving the UI.
            pass


class WorkbenchHandler(BaseHTTPRequestHandler):
    server: WorkbenchServer

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_args):
        pass  # Do not log memory, URLs or provider payloads to the terminal.

    def _send(self, status, data, content_type="application/json"):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def _local_request(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in hosts or (origin is not None and origin != "http://" + host):
            self._send(403, {"error": "Only same-origin loopback requests are supported."})
            return False
        return True

    def do_GET(self):
        if not self._local_request():
            return
        url = urlsplit(self.path)
        try:
            if url.path in ASSETS:
                filename, content_type = ASSETS[url.path]
                data = (Path(__file__).parent.parent / "static" / filename).read_bytes()
                if filename == "index.html":
                    data = data.replace(b"__SESSION_TOKEN__", self.server.token.encode("ascii"))
                self._send(200, data, content_type)
            elif url.path == "/api/state":
                query = parse_qs(url.query)
                scope = query.get("scope", ["global"])[0]
                settings = load_settings(self.server.services.vault)
                self._send(200, {
                    "status": self.server.services.status(),
                    "memories": self.server.services.list_memories(scope, 100, query.get("inactive") == ["true"]),
                    "settings": settings,
                    "credentials": self.server.credential_status(settings),
                    "schedule": self.server.jobs.schedule_status(),
                    "activity": activity(self.server.services.vault),
                    "usage": usage_summary(self.server.services.vault),
                })
            else:
                self._send(404, {"error": "Not found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except (OSError, sqlite3.Error):
            self._send(500, {"error": "Local storage unavailable. Check vault access."})

    def do_POST(self):
        if not self._local_request():
            return
        if not secrets.compare_digest(self.headers.get("X-DeMemory-Token", ""), self.server.token):
            self._send(403, {"error": "Session expired. Reload the dashboard."})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._send(415, {"error": "JSON required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                self._send(413, {"error": "Request body exceeds the limit"})
                return
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            self._send(200, self._action(urlsplit(self.path).path, data))
        except (ValueError, TypeError) as exc:
            self._send(400, {"error": str(exc) if isinstance(exc, ValueError) else "Invalid request fields"})
        except (OSError, sqlite3.Error):
            self._send(500, {"error": "Local operation failed. Check vault access and activity."})

    def _action(self, path, data):
        services, jobs = self.server.services, self.server.jobs
        if path == "/api/settings":
            settings = save_settings(services.vault, data)
            self.server.prune_credentials(settings)
            return settings
        if path == "/api/credentials":
            return self.server.set_credential(data)
        scope = data.get("scope", "global")
        if path == "/api/learn":
            event = uuid4().hex
            content = data.get("content")
            return services.learn(data.get("title"), content, scope,
                                  {"provider": "workbench", "session": self.server.session,
                                   "turn": event, "evidence_kind": "user_statement",
                                   "excerpt": content.encode("utf-8")[:300].decode("utf-8", errors="ignore") if isinstance(content, str) else ""},
                                  event, key=data.get("key"))
        if path == "/api/forget":
            return services.forget(data.get("memory_id"), scope)
        if path == "/api/extract":
            return jobs.extract(data.get("messages"), scope, route_key=data.get("route_key"),
                                event_id=data.get("event_id"))
        if path == "/api/consolidate":
            return jobs.run_consolidation(scope)
        raise ValueError("Unknown operation")


def serve(services, argv=None):
    parser = argparse.ArgumentParser(prog="ai-dememory serve workbench")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    with WorkbenchServer(services, args.port) as server:
        print(f"ai DeMemory: http://127.0.0.1:{server.server_port}", flush=True)
        print("Local only. Scheduled jobs run while this process is open. Ctrl+C stops it.", flush=True)
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            pass
    return 0
