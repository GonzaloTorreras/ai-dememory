"""Optional TypeSafe Jev System One judgment provider."""

from __future__ import annotations

import re

from ai_dememory.models import ModuleManifest
from ai_dememory.providers import ProviderError, _headers, http_transport


BASE_URL = "https://api.typesafe.ai/v1"
MODEL = "jev-1.13.0"

DEFAULT_CONFIG = {"language": False, "usefulness": False, "recall_tags": False,
                  "after_save": False, "automatic_scopes": [],
                  "languages": {"es": "Spanish", "en": "English"}, "purpose": ""}


def validate_config(value: dict) -> dict:
    from ai_dememory.vault import validate_scope
    if not isinstance(value, dict) or value.keys() - DEFAULT_CONFIG.keys():
        raise ValueError("Unsupported Jev skill settings")
    result = {**DEFAULT_CONFIG, **value}
    for name in ("language", "usefulness", "recall_tags", "after_save"):
        if type(result[name]) is not bool:
            raise ValueError("Jev skill switches must be boolean")
    languages = result["languages"]
    if not isinstance(languages, dict) or not 1 <= len(languages) <= 12:
        raise ValueError("Configure between one and twelve language codes and names")
    for code, name in languages.items():
        if (not isinstance(code, str) or not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", code)
                or not isinstance(name, str) or not name.strip() or len(name) > 64
                or any(ord(c) < 32 for c in name)):
            raise ValueError("Use language codes such as es/en and short readable language names")
    scopes = result["automatic_scopes"]
    if not isinstance(scopes, list) or len(scopes) > 100 or any(not isinstance(s, str) for s in scopes):
        raise ValueError("Select up to 100 scopes for automatic external assessment")
    for scope in scopes:
        validate_scope(scope)
    if len(scopes) != len(set(scopes)):
        raise ValueError("Automatic scopes must be distinct")
    if result["after_save"] and (not scopes or not (result["language"] or result["usefulness"])):
        raise ValueError("Automatic assessment needs a selected skill and explicit scopes")
    if not isinstance(result["purpose"], str) or len(result["purpose"]) > 500:
        raise ValueError("Jev memory purpose must be at most 500 characters")
    return result


class JevProvider:
    def validate(self, profile: dict) -> None:
        if not isinstance(profile, dict) or profile.get("kind") != "plugin:jev":
            raise ValueError("Jev requires the plugin:jev provider kind")
        if profile.get("base_url", "").rstrip("/") != BASE_URL or profile.get("model") != MODEL:
            raise ValueError("Jev requires its pinned System One endpoint and model")

    def describe(self) -> dict:
        return {"label": "TypeSafe Jev judgments", "base_url": BASE_URL, "auth": "environment"}

    def list_models(self, profile: dict, credential: str = "") -> list[str]:
        self.validate(profile)
        return [MODEL]

    def judge(self, profile: dict, payload: dict, credential: str, transport=None, timeout: float = 10) -> dict:
        self.validate(profile)
        if not isinstance(payload, dict) or type(timeout) not in (int, float) or not 0 < timeout <= 10:
            raise ProviderError("invalid_request")
        return (transport or http_transport)(
            BASE_URL + "/systemone", payload, _headers(profile, credential), timeout
        )


def get_manifest() -> ModuleManifest:
    return ModuleManifest(
        module_id="jev", version="2", summary="Optional TypeSafe Jev evidence, language and usefulness judgments.",
        capabilities=("provider", "judge"),
        resource_budget={"network": True, "child_processes": 0, "persistent": "metadata-only cache"},
    )


def get_provider() -> JevProvider:
    return JevProvider()
