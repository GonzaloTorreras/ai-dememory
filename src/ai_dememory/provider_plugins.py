"""Providers use the existing explicitly enabled, trusted Python modules."""

from .modules import discover_modules, load_enabled_module
from .policy import reject_high_confidence_secrets
from .settings import DEFAULT_SETTINGS, validate_settings


def load_provider(kind: str, capability: str | None = "generate"):
    if not isinstance(kind, str) or not kind.startswith("plugin:"):
        raise ValueError("Expected a plugin provider kind")
    module = load_enabled_module(kind.removeprefix("plugin:"))
    factory = getattr(module, "get_provider", None)
    if not callable(factory):
        raise ValueError("Enabled module does not expose a provider")
    provider = factory()
    if capability not in (None, "generate", "judge"):
        raise ValueError("Unsupported provider capability")
    methods = ("validate", "describe", "list_models") + ((capability,) if capability else ())
    if any(not callable(getattr(provider, name, None)) for name in methods):
        raise ValueError("Provider does not implement the requested capability")
    return provider


def provider_descriptions() -> list[dict]:
    descriptions = []
    for name, descriptor in discover_modules().items():
        if not descriptor.enabled or (descriptor.builtin and "judge" not in getattr(descriptor, "capabilities", ())):
            continue
        try:
            module = load_enabled_module(name)
            if not callable(getattr(module, "get_provider", None)):
                continue
            provider = module.get_provider()
            info = provider.describe()
            if not isinstance(info, dict) or set(info) != {"label", "base_url", "auth"}:
                continue
            if any(not isinstance(value, str) or not value or len(value) > 512 or any(ord(c) < 32 for c in value)
                   for value in info.values()) or info["auth"] not in ("environment", "session", "none"):
                continue
            reject_high_confidence_secrets(" ".join(info.values()))
            validate_settings({**DEFAULT_SETTINGS, "providers": {"extension": {
                "kind": "plugin:" + name, "base_url": info["base_url"], "model": "jev-1.13.0" if name == "jev" else "description",
                "auth": info["auth"], "api_key_env": "PROVIDER_API_KEY" if info["auth"] == "environment" else ""}}})
            capabilities = [value for value in ("generate", "judge") if callable(getattr(provider, value, None))]
            descriptions.append({"kind": "plugin:" + name, **info, "capabilities": capabilities})
        except Exception:
            continue  # An optional provider cannot break the whole dashboard.
        if len(descriptions) >= 32:
            break
    return descriptions
