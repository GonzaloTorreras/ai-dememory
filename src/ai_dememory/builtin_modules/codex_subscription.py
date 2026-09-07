"""Explicitly enabled Codex subscription adapter."""

from ai_dememory.codex_subscription import (
    cancel_login, close, generate, list_models, login_status, start_login, validate_vault,
)
from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest(
        module_id="codex-subscription", version="1",
        summary="Optional Codex account login and subscription-backed extraction.",
        capabilities=("provider", "device-login"),
        resource_budget={"network": True, "child_processes": "bounded Codex app-server",
                         "persistent": "isolated Codex account"},
    )
