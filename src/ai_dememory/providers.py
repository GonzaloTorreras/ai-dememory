"""Bounded provider calls with durable reservations and metadata-only activity."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import closing
from datetime import datetime, timezone

from .settings import is_local_url, load_settings, local_file, resolve_route, validate_settings
from .vault import Vault

MAX_PROMPT_BYTES = 64_000
MAX_RESPONSE_BYTES = 1_000_000
TIMEOUT_SECONDS = 30


class ProviderError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Provider operation failed: {reason}")


class BudgetExceeded(ProviderError):
    pass


def _database(vault):
    path = local_file(vault, "runtime.sqlite")
    for suffix in ("-journal", "-wal", "-shm"):
        local_file(vault, "runtime.sqlite" + suffix)
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS provider_attempts (
        id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, day TEXT NOT NULL,
        operation TEXT NOT NULL, route TEXT NOT NULL, provider TEXT NOT NULL,
        model TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '',
        input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
        cost_usd REAL NOT NULL, estimated INTEGER NOT NULL, duration_ms INTEGER NOT NULL DEFAULT 0
    )""")
    return db


def _day():
    return datetime.now(timezone.utc).date().isoformat()


def _totals(db):
    return dict(db.execute("""SELECT COUNT(*) AS calls,
        COALESCE(SUM(input_tokens + output_tokens),0) AS tokens,
        COALESCE(SUM(cost_usd),0) AS cost_usd,
        COALESCE(SUM(estimated),0) AS estimated_attempts
        FROM provider_attempts WHERE day = ?""", (_day(),)).fetchone())


def usage_summary(vault: Vault) -> dict:
    with closing(_database(vault)) as db:
        return {"day": _day(), **_totals(db), "limits": load_settings(vault)["budgets"]}


def activity(vault: Vault, limit: int = 50) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Activity limit must be between 1 and 200")
    with closing(_database(vault)) as db:
        return [dict(row) for row in db.execute("SELECT * FROM provider_attempts ORDER BY id DESC LIMIT ?", (limit,))]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_transport(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    encoded = json.dumps(payload).encode("utf-8")
    if len(encoded) > MAX_PROMPT_BYTES * 8:
        raise ProviderError("request_too_large")
    request = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    # Ignore proxy environment variables; a local fallback must stay local.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    deadline = time.monotonic() + timeout
    with opener.open(request, timeout=timeout) as response:
        chunks, size = [], 0
        while True:
            if time.monotonic() >= deadline:
                raise ProviderError("provider_timeout")
            chunk = response.read1(min(65_536, MAX_RESPONSE_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ProviderError("response_too_large")
        raw = b"".join(chunks)
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ProviderError("invalid_response") from exc
    if not isinstance(data, dict):
        raise ProviderError("invalid_response")
    return data


def _cost(provider, inputs, outputs):
    return (inputs * provider.get("input_cost_per_million", 0)
            + outputs * provider.get("output_cost_per_million", 0)) / 1_000_000


class ProviderEngine:
    def __init__(self, vault: Vault, settings: dict | None = None, transport=None):
        self.vault = vault
        self.settings = validate_settings(settings) if settings is not None else load_settings(vault)
        self.transport = transport or http_transport

    def _reserve(self, operation, route_key, name, provider, inputs, outputs):
        budgets = self.settings["budgets"]
        if budgets["daily_usd"] and not is_local_url(provider["base_url"]) and any(
            key not in provider for key in ("input_cost_per_million", "output_cost_per_million")
        ):
            raise BudgetExceeded("pricing_required")
        cost = _cost(provider, inputs, outputs)
        with closing(_database(self.vault)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            totals = _totals(db)
            if totals["calls"] + 1 > budgets["daily_calls"]:
                raise BudgetExceeded("daily_calls")
            if totals["tokens"] + inputs + outputs > budgets["daily_tokens"]:
                raise BudgetExceeded("daily_tokens")
            if budgets["daily_usd"] and totals["cost_usd"] + cost > budgets["daily_usd"]:
                raise BudgetExceeded("daily_usd")
            cursor = db.execute("""INSERT INTO provider_attempts
                (created_at,day,operation,route,provider,model,status,input_tokens,output_tokens,cost_usd,estimated)
                VALUES (?,?,?,?,?,?,'pending',?,?,?,1)""",
                (datetime.now(timezone.utc).isoformat(), _day(), operation, route_key or operation,
                 name, provider["model"], inputs, outputs, cost))
            return cursor.lastrowid

    def _finish(self, attempt, status, reason, started, usage=None, provider=None):
        with closing(_database(self.vault)) as db, db:
            db.execute("UPDATE provider_attempts SET status=?,reason=?,duration_ms=? WHERE id=?",
                       (status, reason, round((time.monotonic() - started) * 1000), attempt))
            if usage is not None:
                db.execute("UPDATE provider_attempts SET input_tokens=?,output_tokens=?,cost_usd=?,estimated=0 WHERE id=?",
                           (usage["input_tokens"], usage["output_tokens"],
                            _cost(provider, usage["input_tokens"], usage["output_tokens"]), attempt))

    def run(self, operation: str, prompt: str, route_key: str | None = None) -> dict:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise ValueError("Prompt must contain 1 to 64000 UTF-8 bytes")
        route = resolve_route(self.settings, operation, route_key)
        attempts = []
        for name in [route["primary"], *route["fallback"]]:
            provider = self.settings["providers"][name]
            # Byte count is conservative across tokenizers; include message framing.
            inputs, outputs = len(prompt.encode("utf-8")) + 256, route["max_output_tokens"]
            attempt = self._reserve(operation, route_key, name, provider, inputs, outputs)
            started = time.monotonic()
            try:
                headers = {"Content-Type": "application/json"}
                if provider["api_key_env"]:
                    key = os.environ.get(provider["api_key_env"], "")
                    if not key:
                        raise ProviderError("missing_credentials")
                    if any(ord(c) < 32 for c in key):
                        raise ProviderError("invalid_credentials")
                    headers["Authorization"] = "Bearer " + key
                response_api = provider["kind"] == "responses"
                payload = {"model": provider["model"], "stream": False}
                if response_api:
                    payload.update(input=prompt, max_output_tokens=outputs, store=False)
                    if "reasoning_effort" in provider:
                        payload["reasoning"] = {"effort": provider["reasoning_effort"]}
                else:
                    payload.update(messages=[{"role": "user", "content": prompt}], max_tokens=outputs)
                    if "reasoning_effort" in provider:
                        payload["reasoning_effort"] = provider["reasoning_effort"]
                url = provider["base_url"].rstrip("/") + ("/responses" if response_api else "/chat/completions")
                data = self.transport(url, payload, headers, TIMEOUT_SECONDS)
                if response_api:
                    text = "".join(part["text"] for item in data.get("output", []) if item.get("type") == "message"
                                   for part in item.get("content", []) if part.get("type") == "output_text")
                else:
                    text = data["choices"][0]["message"]["content"]
                if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
                    raise ProviderError("invalid_response")
                raw_usage = data.get("usage") or {}
                in_count = raw_usage.get("input_tokens" if response_api else "prompt_tokens")
                out_count = raw_usage.get("output_tokens" if response_api else "completion_tokens")
                usage = None
                if type(in_count) is int and type(out_count) is int and in_count >= 0 and out_count >= 0:
                    usage = {"input_tokens": in_count, "output_tokens": out_count}
                self._finish(attempt, "success", "", started, usage, provider)
                attempts.append({"provider": name, "status": "success"})
                return {"text": text, "provider": name, "model": provider["model"],
                        "usage": {**(usage or {"input_tokens": inputs, "output_tokens": outputs}), "estimated": usage is None},
                        "attempts": attempts}
            except urllib.error.HTTPError as exc:
                reason = "provider_quota" if exc.code == 429 else "provider_unavailable" if exc.code >= 500 else "provider_http_error"
                retryable = exc.code in (408, 429) or exc.code >= 500
                exc.close()
            except (TimeoutError, urllib.error.URLError, ConnectionError, OSError):
                reason, retryable = "provider_unavailable", True
            except ProviderError as exc:
                reason, retryable = exc.reason, True
            except (KeyError, IndexError, TypeError, AttributeError, ValueError):
                reason, retryable = "invalid_response", True
            self._finish(attempt, "failed", reason, started)
            attempts.append({"provider": name, "status": "failed", "reason": reason})
            if not retryable:
                raise ProviderError(reason)
        raise ProviderError(attempts[-1]["reason"])
