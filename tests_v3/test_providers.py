from __future__ import annotations

import copy
import io
import json
import tempfile
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from ai_dememory.providers import (
    MAX_RESPONSE_BYTES, BudgetExceeded, ProviderEngine, ProviderError,
    _NoRedirect, activity, http_transport, usage_summary,
)
from ai_dememory.settings import DEFAULT_SETTINGS, load_settings, resolve_route, save_settings
from ai_dememory.vault import Vault


def configuration():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["providers"] = {
        "cloud": {"kind": "responses", "base_url": "https://api.example.test/v1",
                  "api_key_env": "TEST_MEMORY_API_KEY", "model": "test-cloud"},
        "local": {"kind": "openai_compatible", "base_url": "http://127.0.0.1:11434/v1",
                  "api_key_env": "", "model": "test-local"},
    }
    settings["routes"]["extract"] = {"primary": "cloud", "fallback": ["local"], "max_output_tokens": 128}
    settings["routes"]["consolidate"] = {"primary": "local", "fallback": [], "max_output_tokens": 256}
    return settings


def chat_response():
    return {"choices": [{"message": {"content": "Learning summary"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3}}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.vault = Vault.create(Path(self.temporary.name) / "vault")
        self.settings = configuration()
        self.environment = patch.dict("os.environ", {"TEST_MEMORY_API_KEY": "unit-test-only"})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def test_configuration_roundtrip_and_per_operation_overrides(self):
        self.assertEqual(load_settings(self.vault), DEFAULT_SETTINGS)
        self.settings["routes"]["hook:codex"] = {"primary": "local", "fallback": [], "max_output_tokens": 64}
        save_settings(self.vault, self.settings)
        self.assertEqual(load_settings(self.vault), self.settings)
        self.assertEqual(resolve_route(self.settings, "extract", "hook:codex")["primary"], "local")
        self.assertEqual(resolve_route(self.settings, "extract", "skill:unknown")["primary"], "cloud")
        self.assertEqual(resolve_route(self.settings, "consolidate")["max_output_tokens"], 256)

    def test_bad_or_secret_configuration_is_rejected_atomically(self):
        save_settings(self.vault, self.settings)
        bad_values = ["http://192.168.1.2/v1", "https://user:password@example.test/v1",
                      "https://example.test/v1?api_key=secret", "https://example.test/v1#secret"]
        for value in bad_values:
            settings = copy.deepcopy(self.settings)
            settings["providers"]["cloud"]["base_url"] = value
            with self.assertRaises(ValueError):
                save_settings(self.vault, settings)
        settings = copy.deepcopy(self.settings)
        settings["providers"]["cloud"]["api_key"] = "never-save-me"
        with self.assertRaises(ValueError):
            save_settings(self.vault, settings)
        settings = copy.deepcopy(self.settings)
        settings["providers"]["cloud"]["model"] = "sk-" + "a" * 30
        with self.assertRaises(ValueError):
            save_settings(self.vault, settings)
        settings = copy.deepcopy(self.settings)
        settings["budgets"]["daily_calls"] = True
        with self.assertRaises(ValueError):
            save_settings(self.vault, settings)
        self.assertEqual(load_settings(self.vault), self.settings)

    def test_quota_falls_back_to_local_without_forwarding_cloud_credentials(self):
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append((url, payload, headers, timeout))
            if len(calls) == 1:
                raise urllib.error.HTTPError(url, 429, "private error", {}, io.BytesIO(b"private"))
            return chat_response()
        result = ProviderEngine(self.vault, self.settings, transport).run("extract", "private conversation")
        self.assertEqual(result["provider"], "local")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["max_output_tokens"], 128)
        self.assertFalse(calls[0][1]["store"])
        self.assertEqual(calls[0][2]["Authorization"], "Bearer unit-test-only")
        self.assertNotIn("Authorization", calls[1][2])
        logged = json.dumps(activity(self.vault))
        for canary in ("private conversation", "Learning summary", "private error", "unit-test-only"):
            self.assertNotIn(canary, logged)
        usage = usage_summary(self.vault)
        self.assertEqual(usage["calls"], 2)
        self.assertEqual(usage["estimated_attempts"], 1)

    def test_responses_shape_and_usage(self):
        def transport(url, payload, headers, timeout):
            self.assertTrue(url.endswith("/responses"))
            return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "OK"}]}],
                    "usage": {"input_tokens": 4, "output_tokens": 2}}
        result = ProviderEngine(self.vault, self.settings, transport).run("extract", "test")
        self.assertEqual(result["text"], "OK")
        self.assertFalse(result["usage"]["estimated"])
        self.assertEqual(usage_summary(self.vault)["tokens"], 6)

    def test_missing_usage_preserves_conservative_reservation(self):
        response = chat_response()
        response.pop("usage")
        engine = ProviderEngine(self.vault, self.settings, lambda *args: response)
        result = engine.run("consolidate", "test")
        self.assertTrue(result["usage"]["estimated"])
        self.assertEqual(usage_summary(self.vault)["tokens"], 4 + 256 + 256)

    def test_application_budget_cannot_be_bypassed_by_fallback(self):
        self.settings["budgets"]["daily_calls"] = 1
        calls = []
        def transport(*args):
            calls.append(args)
            raise TimeoutError("private timeout")
        engine = ProviderEngine(self.vault, self.settings, transport)
        with self.assertRaises(BudgetExceeded):
            engine.run("extract", "test")
        self.assertEqual(len(calls), 1)
        with self.assertRaises(BudgetExceeded):
            ProviderEngine(self.vault, self.settings, transport).run("extract", "test")
        self.assertEqual(len(calls), 1)

    def test_currency_budget_needs_prices_and_reserves_before_call(self):
        self.settings["budgets"]["daily_usd"] = 0.01
        with self.assertRaisesRegex(BudgetExceeded, "pricing_required"):
            ProviderEngine(self.vault, self.settings, lambda *args: self.fail("network called")).run("extract", "test")
        self.settings["providers"]["cloud"].update(input_cost_per_million=100, output_cost_per_million=100)
        with self.assertRaisesRegex(BudgetExceeded, "daily_usd"):
            ProviderEngine(self.vault, self.settings, lambda *args: self.fail("network called")).run("extract", "test")
        self.assertEqual(usage_summary(self.vault)["calls"], 0)

    def test_concurrent_calls_share_one_durable_budget(self):
        self.settings["budgets"]["daily_calls"] = 1
        barrier = threading.Barrier(2)
        def run():
            barrier.wait(timeout=5)
            try:
                ProviderEngine(self.vault, self.settings, lambda *args: chat_response()).run("consolidate", "test")
                return "success"
            except BudgetExceeded:
                return "limited"
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run(), range(2)))
        self.assertCountEqual(results, ["success", "limited"])
        self.assertEqual(usage_summary(self.vault)["calls"], 1)

    def test_invalid_output_can_fallback_but_http_configuration_errors_stop(self):
        calls = []
        def transport(*args):
            calls.append(args)
            return {} if len(calls) == 1 else chat_response()
        self.assertEqual(ProviderEngine(self.vault, self.settings, transport).run("extract", "test")["provider"], "local")
        def rejected(url, *args):
            raise urllib.error.HTTPError(url, 400, "secret details", {}, io.BytesIO())
        with self.assertRaisesRegex(ProviderError, "provider_http_error"):
            ProviderEngine(self.vault, self.settings, rejected).run("extract", "test")
        self.assertEqual(usage_summary(self.vault)["calls"], 3)

    def test_transport_bounds_response_and_disables_redirects(self):
        with patch("ai_dememory.providers.urllib.request.build_opener") as factory:
            factory.return_value.open.return_value = io.BytesIO(b"x" * (MAX_RESPONSE_BYTES + 1))
            with self.assertRaisesRegex(ProviderError, "response_too_large"):
                http_transport("https://example.test/v1/responses", {}, {}, 30)
            handlers = factory.call_args.args
            redirect_handler = next(handler for handler in handlers if isinstance(handler, _NoRedirect))
            self.assertIsNone(redirect_handler.redirect_request(None, None, 302, "", {}, "https://other.test"))
        with patch("ai_dememory.providers.urllib.request.build_opener") as factory:
            factory.return_value.open.return_value = io.BytesIO(b"not-json")
            with self.assertRaisesRegex(ProviderError, "invalid_response"):
                http_transport("https://example.test/v1/responses", {}, {}, 30)


if __name__ == "__main__":
    unittest.main()
