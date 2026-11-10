"""Bounded, shadow-only evidence judgments using an explicitly enabled provider."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.error
from contextlib import closing
from datetime import datetime, timezone

from .modules import discover_modules
from .policy import reject_high_confidence_secrets
from .provider_plugins import load_provider
from .providers import BudgetExceeded, ProviderEngine, ProviderError, _database
from .quality import evidence_revision, recall_eligible
from .settings import auth_mode, load_settings
from .vault import Vault, validate_scope


MODEL = "jev-1.13.0"
RUBRIC = "evidence-support-v2"
MAX_INPUT_CHARS = 8_000
MAX_ATTEMPTS = 3
TOTAL_TIMEOUT_SECONDS = 10
_SUPPORT = ("supports", "contradicts", "insufficient")
_COMPARE = ("same_claim", "update", "conflict", "unrelated", "unknown")
_SAFE_REASONS = frozenset({
    "attempt_limit", "budget", "comparison_not_enabled", "comparison_not_eligible", "input_too_large",
    "invalid_response", "invalid_scope", "judgment_not_enabled", "memory_not_eligible", "missing_credentials",
    "missing_evidence", "provider_http_error", "provider_quota", "provider_timeout", "provider_unavailable",
})


def _unassessed(reason: str, *, model: str = "", cache: dict | None = None) -> dict:
    return {
        "status": "unassessed", "reason": reason, "shadow_only": True,
        "writes_canonical_memory": False, "source_authenticity": "unverified",
        "model": model, "rubric": RUBRIC, "cache": cache or {"hit": False}, "result": {},
    }


def _json_size(value: dict) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _payload(state: dict, question_id: str, instructions: str, criteria: dict[str, str]) -> dict:
    return {
        "model": MODEL,
        "state": state,
        "questions": {question_id: {"type": "choice", "instructions": instructions, "criteria": criteria}},
    }


def _bounded_payload(state: dict, question_id: str, instructions: str, criteria: dict[str, str]) -> dict:
    """Reject oversized previewed state rather than silently judging a subset."""
    payload = _payload(state, question_id, instructions, criteria)
    if _json_size(payload) > MAX_INPUT_CHARS:
        raise ValueError("input_too_large")
    reject_high_confidence_secrets(json.dumps(payload, ensure_ascii=False))
    return payload


def _usage(data: dict) -> dict | None:
    usage = data.get("usage", {})
    if not isinstance(usage, dict):
        return None
    inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
    if type(inputs) is int and type(outputs) is int and inputs >= 0 and outputs >= 0:
        return {"input_tokens": inputs, "output_tokens": outputs}
    return None


def _answer(data: dict, question_id: str, labels: tuple[str, ...] | None) -> dict:
    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise ProviderError("invalid_response")
    answer = answers.get(question_id)
    if labels is None:
        value = answer.get("noul") if isinstance(answer, dict) else None
        if (not isinstance(answer, dict) or answer.get("type") != "noul"
                or type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1):
            raise ProviderError("invalid_response")
        return {"probability": value}
    if not isinstance(answer, dict) or answer.get("type") != "choice" or answer.get("choice") not in labels:
        raise ProviderError("invalid_response")
    probabilities = answer.get("probabilities")
    certainty = answer.get("confidence")
    if not isinstance(probabilities, dict) or set(probabilities) != set(labels):
        raise ProviderError("invalid_response")
    if type(certainty) not in (int, float) or not math.isfinite(certainty):
        raise ProviderError("invalid_response")
    if not 0 <= certainty <= 1:
        raise ProviderError("invalid_response")
    values = list(probabilities.values())
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ProviderError("invalid_response")
    if abs(sum(values) - 1) > 0.001:
        raise ProviderError("invalid_response")
    if probabilities[answer["choice"]] < max(values):
        raise ProviderError("invalid_response")
    return {"verdict": answer["choice"], "probabilities": probabilities, "certainty": certainty}


def _plugin_enabled(profile: dict, descriptors: dict) -> bool:
    kind = profile.get("kind", "") if isinstance(profile, dict) else ""
    descriptor = descriptors.get(kind.removeprefix("plugin:")) if isinstance(kind, str) else None
    return bool(descriptor and descriptor.enabled)


class JudgmentEngine:
    def __init__(self, vault: Vault, settings: dict | None = None, transport=None, credential_resolver=None):
        self.vault = vault
        self.settings = settings if settings is not None else load_settings(vault)
        self.transport = transport
        self.credential_resolver = credential_resolver

    def _configuration(self, scope: str, allowed_scopes=None) -> tuple[dict, list[str]] | tuple[None, None]:
        config = self.settings.get("judgment", {}) if isinstance(self.settings, dict) else {}
        if not isinstance(config, dict) or config.get("primary", "") == "":
            return None, None
        scopes, operations = config.get("scopes", []) if allowed_scopes is None else allowed_scopes, config.get("operations", ["support"])
        if not isinstance(scopes, list) or len(scopes) > 100 or scope not in scopes:
            return None, None
        if not isinstance(operations, list) or "support" not in operations:
            return None, None
        chain = [config.get("primary"), *config.get("fallback", [])]
        if any(not isinstance(name, str) or name not in self.settings.get("providers", {}) for name in chain):
            return None, None
        return config, chain

    def _cache_key(self, memory, comparison, scope: str, chain: list[str], descriptors: dict) -> str:
        evidence = memory.source.get("excerpt", "") if isinstance(memory.source, dict) else ""
        route = [
            [name, self.settings["providers"][name].get("kind"), self.settings["providers"][name].get("base_url"),
             self.settings["providers"][name].get("model"), _plugin_enabled(self.settings["providers"][name], descriptors)]
            for name in chain
        ]
        values = [scope, memory.memory_id, comparison.memory_id if comparison else "",
                  evidence_revision(memory.title, memory.content, memory.source),
                  hashlib.sha256(evidence.encode("utf-8")).hexdigest(), route, RUBRIC]
        if comparison:
            values.append(evidence_revision(comparison.title, comparison.content, comparison.source))
        return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()

    def _cached(self, key: str) -> dict | None:
        with closing(_database(self.vault)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS judgment_cache (
                cache_key TEXT PRIMARY KEY, created_at TEXT NOT NULL, result TEXT NOT NULL)""")
            row = db.execute("SELECT result FROM judgment_cache WHERE cache_key = ?", (key,)).fetchone()
        if row is None:
            return None
        try:
            result = json.loads(row["result"])
        except (TypeError, ValueError):
            return None
        return result if isinstance(result, dict) else None

    def _cache(self, key: str, result: dict) -> None:
        encoded = json.dumps(result, ensure_ascii=True, separators=(",", ":"))
        with closing(_database(self.vault)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS judgment_cache (
                cache_key TEXT PRIMARY KEY, created_at TEXT NOT NULL, result TEXT NOT NULL)""")
            db.execute("INSERT OR REPLACE INTO judgment_cache(cache_key, created_at, result) VALUES(?,?,?)",
                       (key, datetime.now(timezone.utc).isoformat(), encoded))
            db.execute("DELETE FROM judgment_cache WHERE rowid NOT IN (SELECT rowid FROM judgment_cache ORDER BY rowid DESC LIMIT 200)")

    def _credential(self, name: str, profile: dict) -> str:
        mode = auth_mode(profile)
        if mode == "environment":
            return os.environ.get(profile.get("api_key_env", ""), "")
        if mode == "session" and self.credential_resolver:
            return self.credential_resolver(name, profile)
        return ""

    def _request(self, engine: ProviderEngine, provider, name: str, payload: dict, question_id: str,
                 labels: tuple[str, ...], deadline: float) -> tuple[dict, dict]:
        answers, meta = self._request_many(engine, provider, name, payload, {question_id: labels}, deadline)
        return answers[question_id], meta

    def _request_many(self, engine, provider, name, payload, questions, deadline):
        remaining = max(0, deadline - time.monotonic())
        if remaining <= 0:
            raise ProviderError("provider_timeout")
        credential = self._credential(name, provider)
        if auth_mode(provider) not in ("none", "chatgpt") and not credential:
            raise ProviderError("missing_credentials")
        try:
            adapter = load_provider(provider["kind"], capability="judge")
            adapter.validate(provider)
        except Exception:
            raise ProviderError("invalid_response") from None
        payload = {**payload, "model": provider["model"]}
        if _json_size(payload) > MAX_INPUT_CHARS:
            raise ProviderError("input_too_large")
        inputs = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 256
        attempt = engine._reserve("judgment", "judgment", name, provider, inputs, 256)
        started = time.monotonic()
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderError("provider_timeout")
            data = adapter.judge(provider, payload, credential, self.transport, min(10, remaining))
            if data.get("model") is not None and data["model"] != provider["model"]:
                raise ProviderError("invalid_response")
            parsed = {qid: {**_answer(data, qid, labels), "provider": name, "model": provider["model"]}
                      for qid, labels in questions.items()}
            if time.monotonic() > deadline:
                raise ProviderError("provider_timeout")
            engine._finish(attempt, "success", "", started, _usage(data), provider)
            return parsed, {"provider": name, "model": provider["model"]}
        except urllib.error.HTTPError as exc:
            reason = "provider_quota" if exc.code == 429 else "provider_http_error"
            exc.close()
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError):
            reason = "provider_unavailable"
        except ProviderError as exc:
            reason = exc.reason if exc.reason in _SAFE_REASONS else "invalid_response"
        except Exception:
            reason = "invalid_response"
        engine._finish(attempt, "failed", reason, started)
        raise ProviderError(reason)

    def evaluate(self, memory_id: str, scope: str, comparison_id: str | None = None, *,
                 expected_revision: str | None = None, comparison_revision: str | None = None) -> dict:
        try:
            validate_scope(scope)
        except ValueError:
            return _unassessed("invalid_scope")
        memory = self.vault.get(memory_id) if isinstance(memory_id, str) else None
        if memory is None or memory.scope != scope or not recall_eligible(memory):
            return _unassessed("memory_not_eligible")
        if expected_revision is not None and (
                not isinstance(expected_revision, str)
                or expected_revision != evidence_revision(memory.title, memory.content, memory.source)):
            return _unassessed("preview_stale")
        excerpt = memory.source.get("excerpt", "") if isinstance(memory.source, dict) else ""
        if not isinstance(excerpt, str) or not excerpt.strip():
            return _unassessed("missing_evidence")
        config, chain = self._configuration(scope)
        if config is None:
            return _unassessed("judgment_not_enabled")
        comparison = None
        if comparison_id is not None:
            if "compare" not in config.get("operations", []):
                return _unassessed("comparison_not_enabled")
            comparison = self.vault.get(comparison_id) if isinstance(comparison_id, str) else None
            if (comparison is None or comparison.memory_id == memory.memory_id or comparison.scope != scope
                    or not recall_eligible(comparison)):
                return _unassessed("comparison_not_eligible")
            if comparison_revision is not None and (
                    not isinstance(comparison_revision, str)
                    or comparison_revision != evidence_revision(
                        comparison.title, comparison.content, comparison.source
                    )):
                return _unassessed("preview_stale")
        primary = self.settings["providers"][chain[0]]
        # Check enabled state without importing the optional adapter or opening the cache database.
        descriptors = discover_modules()
        descriptor = descriptors.get("jev")
        if descriptor is None or not descriptor.enabled:
            return _unassessed("judgment_not_enabled", model=primary.get("model", ""))
        if not any(auth_mode(self.settings["providers"][name]) in ("none", "chatgpt")
                   or self._credential(name, self.settings["providers"][name]) for name in chain):
            return _unassessed("missing_credentials", model=primary.get("model", ""))
        key = self._cache_key(memory, comparison, scope, chain, descriptors)
        cached = self._cached(key)
        if cached is not None:
            return {**cached, "cache": {"hit": True}}

        try:
            engine = ProviderEngine(self.vault, self.settings, self.transport, self.credential_resolver)
        except Exception:
            return _unassessed("judgment_not_enabled", model=primary.get("model", ""))
        deadline, attempts = time.monotonic() + TOTAL_TIMEOUT_SECONDS, 0
        results, provider_meta = {}, {"provider": "", "model": primary["model"]}
        try:
            requests = [("support", _bounded_payload(
                {"title": memory.title, "content": memory.content, "excerpt": excerpt}, "support",
                "Using only the provided `excerpt` as evidence, classify whether the claim in `title` and `content` is supported.",
                {"supports": "The excerpt supports the claim.", "contradicts": "The excerpt contradicts the claim.",
                 "insufficient": "The excerpt does not establish the claim."}), _SUPPORT)]
            if comparison:
                requests.append(("comparison", _bounded_payload(
                    {"title": memory.title, "content": memory.content, "candidate_title": comparison.title,
                     "candidate_content": comparison.content}, "comparison",
                    "Using only `title`, `content`, `candidate_title`, and `candidate_content`, classify the claim relationship.",
                    {"same_claim": "They state the same claim.", "update": "Candidate updates the claim.",
                     "conflict": "They conflict.", "unrelated": "They are unrelated.", "unknown": "Relationship is unclear."}), _COMPARE))
        except Exception:
            return _unassessed("input_too_large", model=primary["model"])
        for question_id, payload, labels in requests:
            last_reason = "provider_unavailable"
            for name in chain:
                if attempts >= MAX_ATTEMPTS:
                    return _unassessed("attempt_limit", model=primary["model"])
                attempts += 1
                try:
                    results[question_id], provider_meta = self._request(
                        engine, self.settings["providers"][name], name, payload, question_id, labels, deadline
                    )
                    break
                except BudgetExceeded:
                    return _unassessed("budget", model=primary["model"])
                except ProviderError as exc:
                    last_reason = getattr(exc, "reason", "provider_unavailable")
            else:
                return _unassessed(last_reason, model=primary["model"])
        result = {
            "status": "assessed", "shadow_only": True, "writes_canonical_memory": False,
            "source_authenticity": "unverified", "model": provider_meta["model"], "rubric": RUBRIC,
            "cache": {"hit": False}, "result": results,
        }
        self._cache(key, result)
        return result
