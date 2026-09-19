"""Optional TypeSafe Jev System One judgment provider."""

from __future__ import annotations

from ai_dememory.models import ModuleManifest
from ai_dememory.providers import ProviderError, _headers, http_transport


BASE_URL = "https://api.typesafe.ai/v1"
MODEL = "jev-1.13.0"


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
        module_id="jev", version="1", summary="Optional TypeSafe Jev shadow-only evidence judgments.",
        capabilities=("provider", "judge"),
        resource_budget={"network": True, "child_processes": 0, "persistent": "metadata-only cache"},
    )


def get_provider() -> JevProvider:
    return JevProvider()
