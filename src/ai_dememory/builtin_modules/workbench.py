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
from ai_dememory.modules import discover_modules, enable_module, disable_module, load_enabled_module
from ai_dememory.providers import ProviderEngine, activity, usage_summary
from ai_dememory.settings import auth_mode, load_settings, save_settings
from ai_dememory.vault import validate_scope

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
        self._previews = {}
        self._codex_module = None
        self.jobs = jobs or LearningJobs(services, engine_factory=lambda vault: ProviderEngine(
            vault, credential_resolver=self.resolve_credential))
        self.token = secrets.token_urlsafe(32)
        self.session = uuid4().hex
        self.last_tick = 0.0
        self.last_source_tick = 0.0
        from ai_dememory.source_jobs import SourceJobs
        self.source_jobs = SourceJobs(services.vault, self.jobs)
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
                None if auth_mode(profile) == "chatgpt" else
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
        self._previews.clear()
        if self._codex_module is not None:
            self._codex_module.cancel_login()
        super().server_close()

    def codex(self):
        self._codex_module = load_enabled_module("codex-subscription")
        self._codex_module.validate_vault(self.services.vault.root)
        return self._codex_module

    def draft_models(self, data):
        from ai_dememory.providers import list_provider_models
        from ai_dememory.settings import DEFAULT_SETTINGS, validate_settings
        profile = data.get("profile")
        validated = validate_settings({**DEFAULT_SETTINGS, "providers": {"catalog": profile}})["providers"]["catalog"]
        if validated["kind"] == "codex":
            self.codex()
        mode = auth_mode(validated)
        key = data.get("api_key", "")
        if not isinstance(key, str) or len(key) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError("Invalid API key format")
        if mode == "environment":
            key = os.environ.get(validated["api_key_env"], "")
        elif mode == "session" and not key:
            name = data.get("provider", "")
            if not isinstance(name, str):
                raise ValueError("Invalid provider name")
            key = self.resolve_credential(name, validated)
        elif mode in ("none", "chatgpt"):
            key = ""
        return {"models": list_provider_models(validated, key), "generation_calls": 0}

    def source_action(self, action, data):
        reader = load_enabled_module("sources")
        if action == "list":
            return reader.list_sources(Path(data.get("root", "")), data.get("format", "generic"))
        now = time.monotonic()
        self._previews = {key: value for key, value in self._previews.items() if now - value["created"] < 900}
        if action == "validate":
            tokens = data.get("tokens")
            if not isinstance(tokens, list) or not 1 <= len(tokens) <= 10 or any(not isinstance(t,str) for t in tokens):
                raise ValueError("Select between one and ten previews")
            settings = load_settings(self.services.vault)
            if any(t not in self._previews or self._previews[t]["routing"] != [settings["routes"],settings["providers"]] for t in tokens):
                raise ValueError("A preview expired or its route changed. Use Preview selected again before extracting.")
            return {"valid":True}
        if action == "preview":
            scope = data.get("scope", "global")
            validate_scope(scope)
            preview = reader.preview_source(Path(data.get("root", "")), data.get("file", ""), data.get("format", "generic"), data.get("session_id"))
            settings = load_settings(self.services.vault)
            token = uuid4().hex
            if len(self._previews) >= 10:
                del self._previews[next(iter(self._previews))]
            self._previews[token] = {"created": now, "messages": preview["messages"], "scope": scope,
                                     "routing": [settings["routes"], settings["providers"]],
                                     "route_key":"skill:source-"+data.get("format","generic")}
            route = settings["routes"].get(self._previews[token]["route_key"], settings["routes"].get("extract", {}))
            return {**preview, "preview_token": token, "scope": scope,
                    "destinations": [route["primary"], *route["fallback"]] if route else []}
        if action == "extract":
            token = data.get("preview_token")
            if not isinstance(token, str) or token not in self._previews or data.get("confirmed") is not True:
                raise ValueError("Preview expired or not confirmed. Preview the conversation again.")
            preview = self._previews[token]
            settings = load_settings(self.services.vault)
            if preview["routing"] != [settings["routes"], settings["providers"]]:
                raise ValueError("Provider routes changed. Preview again before sending conversation text.")
            return self.jobs.extract(preview["messages"], preview["scope"], route_key=preview.get("route_key"), event_id="source-" + token)
        raise ValueError("Unknown source action")

    def scopes(self):
        from itertools import islice
        values = {"global", load_settings(self.services.vault)["schedule"]["scope"]}
        for path in islice(self.services.vault.iter_memory_paths(), 1000):
            values.add(self.services.vault.read_memory(path).scope)
        values.update(rule["scope"] for rule in self.source_jobs.public())
        return sorted(values)

    def service_actions(self):
        if time.monotonic() - self.last_tick < 1:
            return
        self.last_tick = time.monotonic()
        self._previews = {key: value for key, value in self._previews.items() if self.last_tick - value["created"] < 900}
        try:
            self.jobs.run_due()
            if self.last_tick - self.last_source_tick >= 60:
                self.last_source_tick = self.last_tick
                self.source_jobs.run()
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
                from ai_dememory.provider_plugins import provider_descriptions
                self._send(200, {
                    "status": self.server.services.status(),
                    "memories": self.server.services.list_memories(scope, 100, query.get("inactive") == ["true"]),
                    "settings": settings,
                    "credentials": self.server.credential_status(settings),
                    "schedule": self.server.jobs.schedule_status(),
                    "activity": activity(self.server.services.vault),
                    "usage": usage_summary(self.server.services.vault),
                    "modules": [item.to_dict() for item in discover_modules().values()],
                    "scopes": self.server.scopes(),
                    "source_schedules": self.server.source_jobs.public(),
                    "codex_sessions_root": str(Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex"))) / "sessions"),
                    "provider_extensions": provider_descriptions(),
                })
            else:
                self._send(404, {"error": "Not found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except (OSError, sqlite3.Error):
            self._send(500, {"error": "Local storage unavailable. Check vault access."})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                self._send(413, {"error": "Request body exceeds the limit"})
                return
            # Consume only the bounded body before rejecting a normal request.
            # Closing with unread bytes can reset the connection on Windows,
            # hiding the 403. No JSON parsing or action precedes authorization.
            raw = self.rfile.read(size)
            if not self._local_request():
                return
            if not secrets.compare_digest(self.headers.get("X-DeMemory-Token", ""), self.server.token):
                self._send(403, {"error": "Session expired. Reload the dashboard."})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self._send(415, {"error": "JSON required"})
                return
            data = json.loads(raw)
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
        if path == "/api/provider-models":
            return self.server.draft_models(data)
        if path == "/api/modules":
            name, enabled = data.get("id"), data.get("enabled")
            if not isinstance(name, str) or type(enabled) is not bool:
                raise ValueError("Choose a module and enabled state")
            if name == "workbench":
                raise ValueError("Stop the workbench process to disable this dashboard")
            if enabled:
                enable_module(name)
            else:
                if name == "codex-subscription" and self.server._codex_module is not None:
                    self.server._codex_module.cancel_login()
                if name == "sources":
                    self.server._previews.clear()
                disable_module(name)
            return {"id": name, "enabled": enabled}
        if path == "/api/codex/login":
            method = data.get("method", "device")
            if method not in ("device", "browser"):
                raise ValueError("Choose device or browser login")
            return self.server.codex().start_login(method)
        if path == "/api/codex/status":
            return self.server.codex().login_status()
        if path == "/api/codex/cancel":
            self.server.codex().cancel_login()
            return {"cancelled": True}
        if path == "/api/source-schedules/save":
            return self.server.source_jobs.save(data)
        if path == "/api/source-schedules/run":
            if data.get("confirmed") is not True:
                raise ValueError("Confirm sending this source to its configured model route")
            return self.server.source_jobs.run(data.get("id"))
        if path == "/api/source-schedules/change":
            if data.get("action") == "resume" and data.get("confirmed") is not True:
                raise ValueError("Confirm automatic extraction before resuming")
            return self.server.source_jobs.change(data.get("id"), data.get("action"))
        if path.startswith("/api/sources/"):
            return self.server.source_action(path.rsplit("/", 1)[-1], data)
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
