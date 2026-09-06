"""Non-secret, per-vault learning configuration shared by UI and adapters."""

from __future__ import annotations

import copy
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit

from .policy import reject_high_confidence_secrets
from .vault import Vault, _atomic_write

DEFAULT_SETTINGS = {
    "schema_version": 1, "providers": {}, "routes": {},
    "schedule": {"enabled": False, "interval_hours": 168},
    "budgets": {"daily_calls": 20, "daily_tokens": 50_000, "daily_usd": 0},
}
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}")


def local_file(vault: Vault, name: str):
    path = vault.root / name
    if path.is_symlink() or path.resolve().parent != vault.root.resolve():
        raise ValueError("Runtime files must remain inside the vault")
    if path.exists() and not path.is_file():
        raise ValueError("Runtime path must be a regular file")
    return path


def _shape(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("Configuration contains missing or unsupported fields")


def _number(value, minimum, maximum, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"Expected {'integer' if integer else 'number'} between {minimum} and {maximum}")


def is_local_url(url: str) -> bool:
    host = urlsplit(url).hostname
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def validate_settings(data: dict) -> dict:
    _shape(data, DEFAULT_SETTINGS)
    reject_high_confidence_secrets(json.dumps(data))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported settings schema")
    providers, routes = data["providers"], data["routes"]
    if not isinstance(providers, dict) or len(providers) > 32 or not isinstance(routes, dict) or len(routes) > 128:
        raise ValueError("Too many providers or routes")
    for name, provider in providers.items():
        if not isinstance(name, str) or not _ID.fullmatch(name):
            raise ValueError("Invalid provider id")
        _shape(provider, {"kind", "base_url", "api_key_env", "model"},
               {"reasoning_effort", "input_cost_per_million", "output_cost_per_million"})
        if provider["kind"] not in ("openai_compatible", "responses"):
            raise ValueError("Unsupported provider kind")
        for field in ("base_url", "api_key_env", "model"):
            if not isinstance(provider[field], str) or len(provider[field]) > 512 or any(ord(c) < 32 for c in provider[field]):
                raise ValueError("Provider fields must be bounded plain strings")
        if not provider["model"].strip():
            raise ValueError("Provider model is required")
        if provider["api_key_env"] and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", provider["api_key_env"]):
            raise ValueError("Use an environment variable name, never a raw API key")
        url = urlsplit(provider["base_url"])
        try:
            url.port
        except ValueError as exc:
            raise ValueError("Invalid provider URL port") from exc
        if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment or "\\" in provider["base_url"]
                or (url.scheme == "http" and not is_local_url(provider["base_url"]))):
            raise ValueError("Provider URL needs HTTPS or loopback HTTP, without credentials, query or fragment")
        if "reasoning_effort" in provider and provider["reasoning_effort"] not in ("none", "minimal", "low", "medium", "high", "xhigh"):
            raise ValueError("Unsupported reasoning effort")
        for field in ("input_cost_per_million", "output_cost_per_million"):
            if field in provider:
                _number(provider[field], 0, 100_000)
    for name, route in routes.items():
        if not isinstance(name, str) or (name not in ("extract", "consolidate") and not re.fullmatch(r"(?:hook|skill):[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name)):
            raise ValueError("Invalid operation or override route")
        _shape(route, {"primary", "fallback", "max_output_tokens"})
        if not isinstance(route["primary"], str) or not isinstance(route["fallback"], list):
            raise ValueError("Invalid provider route")
        chain = [route["primary"], *route["fallback"]]
        if len(chain) > 8 or any(not isinstance(item, str) or item not in providers for item in chain) or len(set(chain)) != len(chain):
            raise ValueError("Routes require distinct configured providers (maximum eight)")
        _number(route["max_output_tokens"], 16, 16_384, True)
    _shape(data["schedule"], {"enabled", "interval_hours"})
    if type(data["schedule"]["enabled"]) is not bool:
        raise ValueError("Schedule enabled must be boolean")
    _number(data["schedule"]["interval_hours"], 1, 8760, True)
    _shape(data["budgets"], {"daily_calls", "daily_tokens", "daily_usd"})
    _number(data["budgets"]["daily_calls"], 1, 100_000, True)
    _number(data["budgets"]["daily_tokens"], 1, 100_000_000, True)
    _number(data["budgets"]["daily_usd"], 0, 100_000)
    return copy.deepcopy(data)


def load_settings(vault: Vault) -> dict:
    path = local_file(vault, "settings.json")
    if not path.exists():
        return copy.deepcopy(DEFAULT_SETTINGS)
    if path.stat().st_size > 100_000:
        raise ValueError("Settings file exceeds size limit")
    return validate_settings(json.loads(path.read_text(encoding="utf-8")))


def save_settings(vault: Vault, data: dict) -> dict:
    validated = validate_settings(data)
    _atomic_write(local_file(vault, "settings.json"), json.dumps(validated, indent=2) + "\n")
    return validated


def resolve_route(settings: dict, operation: str, route_key: str | None = None) -> dict:
    if operation not in ("extract", "consolidate"):
        raise ValueError("Operation must be extract or consolidate")
    if route_key is not None and not re.fullmatch(r"(?:hook|skill):[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", route_key):
        raise ValueError("Invalid hook or skill override")
    route = settings["routes"].get(route_key) or settings["routes"].get(operation)
    if route is None:
        raise ValueError(f"No provider route configured for {operation}")
    return route
