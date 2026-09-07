from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ai_dememory.provider_plugins import load_provider, provider_descriptions
from ai_dememory.providers import ProviderEngine, ProviderError, activity, list_provider_models, usage_summary
from ai_dememory.settings import DEFAULT_SETTINGS, validate_settings
from ai_dememory.vault import Vault


def profile(kind="plugin:example"):
    return {"kind": kind, "base_url": "http://127.0.0.1:11434/v1", "model": "test", "api_key_env": "", "auth": "none"}


class ProviderPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = Vault.create(Path(self.temp.name) / "vault")
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)

    def configure(self, profiles, chain):
        self.settings["providers"] = profiles
        self.settings["routes"]["extract"] = {"primary": chain[0], "fallback": chain[1:], "max_output_tokens": 32}
        return self.settings

    def test_disabled_provider_configuration_does_not_import_plugin(self):
        settings = self.configure({"custom": profile()}, ["custom"])
        with patch("ai_dememory.modules.discover_modules", return_value={"example": SimpleNamespace(enabled=False)}), \
                patch("ai_dememory.modules._load_entrypoint") as loader:
            validate_settings(settings)
            with self.assertRaises(ValueError):
                load_provider("plugin:example")
            with self.assertRaises(ProviderError):
                list_provider_models(profile())
            with self.assertRaises(ProviderError):
                ProviderEngine(self.vault, settings).run("extract", "test")
            loader.assert_not_called()

    def test_enabled_plugin_uses_existing_budget_and_bounded_results(self):
        plugin = SimpleNamespace(validate=Mock(), describe=Mock(), list_models=lambda p, k: ["one", "one", "two"],
                                 generate=lambda p, text, maximum, key: {"text": "answer", "usage": {"input_tokens": 2, "output_tokens": 3}})
        with patch("ai_dememory.provider_plugins.load_enabled_module", return_value=SimpleNamespace(get_provider=lambda: plugin)):
            self.assertEqual(list_provider_models(profile()), ["one", "two"])
            settings = self.configure({"custom": profile()}, ["custom"])
            result = ProviderEngine(self.vault, settings).run("extract", "test")
            self.assertEqual(result["text"], "answer")
            self.assertEqual(usage_summary(self.vault)["tokens"], 5)
            plugin.generate = lambda *args: {"text": "x" * 1_000_001}
            with self.assertRaises(ProviderError):
                ProviderEngine(self.vault, settings).run("extract", "test")

    def test_descriptions_only_load_enabled_community_modules(self):
        descriptors = {"off": SimpleNamespace(enabled=False, builtin=False),
                       "builtin": SimpleNamespace(enabled=True, builtin=True),
                       "custom": SimpleNamespace(enabled=True, builtin=False),
                       "broken": SimpleNamespace(enabled=True, builtin=False)}
        def module(name):
            if name == "broken":
                raise RuntimeError("private-exception")
            return SimpleNamespace(get_provider=lambda: SimpleNamespace(describe=lambda: {"label": "Custom", "base_url": "https://example.test/v1", "auth": "session"}))
        with patch("ai_dememory.provider_plugins.discover_modules", return_value=descriptors), \
                patch("ai_dememory.provider_plugins.load_enabled_module", side_effect=module) as loader:
            self.assertEqual(provider_descriptions(), [{"kind": "plugin:custom", "label": "Custom", "base_url": "https://example.test/v1", "auth": "session"}])
            self.assertEqual([call.args[0] for call in loader.call_args_list], ["custom", "broken"])

    def test_codex_counts_budget_without_paid_api_fallback(self):
        codex = {"kind": "codex", "base_url": "", "api_key_env": "", "auth": "chatgpt", "model": "available-model"}
        remote = {**profile("responses"), "base_url": "https://example.test/v1"}
        settings = self.configure({"subscription": codex, "remote": remote}, ["subscription", "remote"])
        settings["budgets"]["daily_usd"] = 1
        module = SimpleNamespace(validate_vault=Mock(), generate=Mock(side_effect=RuntimeError("private subscription error")), list_models=lambda: ["real-model"])
        with patch("ai_dememory.providers.load_enabled_module", return_value=module), \
                patch("ai_dememory.providers.http_transport") as transport:
            self.assertEqual(list_provider_models(codex), ["real-model"])
            with self.assertRaisesRegex(ProviderError, "paid_fallback_disabled"):
                ProviderEngine(self.vault, settings).run("extract", "test")
            transport.assert_not_called()
            self.assertEqual(usage_summary(self.vault)["calls"], 1)
            self.assertEqual(usage_summary(self.vault)["cost_usd"], 0)
            self.assertNotIn("private subscription error", str(activity(self.vault)))
            module.validate_vault.assert_called_once_with(self.vault.root)

    def test_codex_active_vault_checked_before_generation(self):
        codex = {"kind": "codex", "base_url": "", "api_key_env": "", "auth": "chatgpt", "model": "available-model"}
        settings = self.configure({"subscription": codex}, ["subscription"])
        failure = ValueError("private path must not escape")
        failure.reason = "account_directory_inside_vault"
        module = SimpleNamespace(validate_vault=Mock(side_effect=failure), generate=Mock())
        with patch("ai_dememory.providers.load_enabled_module", return_value=module):
            with self.assertRaisesRegex(ProviderError, "account_directory_inside_vault"):
                ProviderEngine(self.vault, settings).run("extract", "test")
        module.validate_vault.assert_called_once_with(self.vault.root)
        module.generate.assert_not_called()
        self.assertNotIn("private path", str(activity(self.vault)))

    def test_codex_can_fallback_to_local_and_rejects_api_auth(self):
        codex = {"kind": "codex", "base_url": "", "api_key_env": "", "auth": "chatgpt", "model": "available-model"}
        settings = self.configure({"subscription": codex, "local": profile("openai_compatible")}, ["subscription", "local"])
        with patch("ai_dememory.providers.load_enabled_module", side_effect=ValueError("disabled")):
            result = ProviderEngine(self.vault, settings, lambda *args: {"choices": [{"message": {"content": "local answer"}}]}).run("extract", "test")
            self.assertEqual(result["provider"], "local")
        codex["auth"] = "session"
        with self.assertRaises(ValueError):
            validate_settings(settings)

    def test_remote_catalog_uses_get_headers_and_rejects_malformed_ids(self):
        candidate = {**profile("anthropic"), "auth": "session", "base_url": "https://api.anthropic.com/v1"}
        def transport(url, payload, headers, timeout):
            self.assertEqual(url, "https://api.anthropic.com/v1/models")
            self.assertIsNone(payload)
            self.assertEqual(headers["x-api-key"], "catalog-canary")
            self.assertEqual(headers["anthropic-version"], "2023-06-01")
            return {"data": [{"id": "actual-one"}, {"id": "actual-one"}, {"id": "actual-two"}]}
        self.assertEqual(list_provider_models(candidate, "catalog-canary", transport), ["actual-one", "actual-two"])
        for data in ({}, {"data": [{}]}, {"data": [{"id": "catalog-canary"}]}, {"data": [{"id": None}]}):
            with self.assertRaisesRegex(ProviderError, "model_catalog_unavailable") as error:
                list_provider_models(candidate, "catalog-canary", lambda *args: data)
            self.assertNotIn("catalog-canary", str(error.exception))


if __name__ == "__main__":
    unittest.main()
