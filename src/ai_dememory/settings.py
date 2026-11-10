"""Non-secret, per-vault learning configuration shared by UI and adapters."""

from __future__ import annotations

import copy
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit

from .policy import reject_high_confidence_secrets
from .vault import Vault, _atomic_write, validate_scope

DEFAULT_SETTINGS = {
    "schema_version": 1, "providers": {}, "routes": {},
    "schedule": {"enabled": False, "interval_hours": 168, "scope": "global"},
    "consolidation": {"project_summaries": False},
    "budgets": {"daily_calls": 20, "daily_tokens": 50_000, "daily_usd": 0},
    "ranking": {"importance_weight": 0.15, "confidence_weight": 0},
    "lifecycle": {"episode_recall_days": 0},
    "judgment": {"primary": "", "fallback": [], "scopes": [], "operations": ["support"]},
    "retrieval": {"source_excerpt": True},
    "module_settings": {},
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


def auth_mode(provider: dict) -> str:
    return provider.get("auth", "environment" if provider["api_key_env"] else "none")


def validate_settings(data: dict) -> dict:
    optional = {"ranking", "lifecycle", "consolidation", "judgment", "retrieval", "module_settings"}
    _shape(data, set(DEFAULT_SETTINGS) - optional, optional)
    reject_high_confidence_secrets(json.dumps(data, allow_nan=False))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported settings schema")
    providers, routes = data["providers"], data["routes"]
    if not isinstance(providers, dict) or len(providers) > 32 or not isinstance(routes, dict) or len(routes) > 128:
        raise ValueError("Too many providers or routes")
    for name, provider in providers.items():
        if not isinstance(name, str) or not _ID.fullmatch(name):
            raise ValueError("Invalid provider id")
        _shape(provider, {"kind", "base_url", "api_key_env", "model"},
               {"auth", "reasoning_effort", "input_cost_per_million", "output_cost_per_million"})
        kind = provider["kind"]
        if not isinstance(kind, str) or (kind not in ("openai_compatible", "responses", "anthropic", "codex")
                and not re.fullmatch(r"plugin:[a-z][a-z0-9-]{1,48}", kind)):
            raise ValueError("Unsupported provider kind")
        for field in ("base_url", "api_key_env", "model"):
            if not isinstance(provider[field], str) or len(provider[field]) > 512 or any(ord(c) < 32 for c in provider[field]):
                raise ValueError("Provider fields must be bounded plain strings")
        if not provider["model"].strip():
            raise ValueError("Provider model is required")
        if provider["api_key_env"] and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", provider["api_key_env"]):
            raise ValueError("Use an environment variable name, never a raw API key")
        mode = auth_mode(provider)
        if kind == "codex" and (mode != "chatgpt" or provider["base_url"] or provider["api_key_env"]):
            raise ValueError("Codex requires ChatGPT authentication and empty URL/environment fields")
        if mode not in (("chatgpt",) if kind == "codex" else ("environment", "session", "none")):
            raise ValueError("Authentication must be environment, session or none")
        if bool(provider["api_key_env"]) != (mode == "environment"):
            raise ValueError("Only environment authentication requires an environment variable name")
        url = urlsplit(provider["base_url"])
        try:
            url.port
        except ValueError as exc:
            raise ValueError("Invalid provider URL port") from exc
        if kind != "codex" and (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment or "\\" in provider["base_url"]
                or (url.scheme == "http" and not is_local_url(provider["base_url"]))):
            raise ValueError("Provider URL needs HTTPS or loopback HTTP, without credentials, query or fragment")
        if "reasoning_effort" in provider and provider["reasoning_effort"] not in ("none", "minimal", "low", "medium", "high", "xhigh"):
            raise ValueError("Unsupported reasoning effort")
        if provider["kind"] == "anthropic" and "reasoning_effort" in provider:
            raise ValueError("Reasoning effort is not configured for Anthropic providers yet")
        for field in ("input_cost_per_million", "output_cost_per_million"):
            if field in provider:
                _number(provider[field], 0, 100_000)
        if kind == "plugin:jev" and (provider["base_url"].rstrip("/") != "https://api.typesafe.ai/v1"
                or provider["model"] != "jev-1.13.0"
                or mode not in ("environment", "session") or "reasoning_effort" in provider):
            raise ValueError("Jev requires its pinned System One endpoint/model and API-key authentication")
    for name, route in routes.items():
        if not isinstance(name, str) or (name not in ("extract", "consolidate") and not re.fullmatch(r"(?:hook|skill):[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name)):
            raise ValueError("Invalid operation or override route")
        _shape(route, {"primary", "fallback", "max_output_tokens"})
        if not isinstance(route["primary"], str) or not isinstance(route["fallback"], list):
            raise ValueError("Invalid provider route")
        chain = [route["primary"], *route["fallback"]]
        if len(chain) > 8 or any(not isinstance(item, str) or item not in providers for item in chain) or len(set(chain)) != len(chain):
            raise ValueError("Routes require distinct configured providers (maximum eight)")
        if any(providers[item]["kind"] == "plugin:jev" for item in chain):
            raise ValueError("Jev judges evidence; it cannot generate extraction or consolidation text")
        _number(route["max_output_tokens"], 16, 16_384, True)
    _shape(data["schedule"], {"enabled", "interval_hours"},
           {"scope", "target_mode", "scopes", "include_global"})
    if type(data["schedule"]["enabled"]) is not bool:
        raise ValueError("Schedule enabled must be boolean")
    _number(data["schedule"]["interval_hours"], 1, 8760, True)
    schedule = data["schedule"]
    validate_scope(schedule.get("scope", "global"))
    target_mode = schedule.get("target_mode")
    if target_mode is not None:
        if target_mode not in ("selected_projects", "all_project_scopes"):
            raise ValueError("Schedule target mode must select projects or all project scopes")
        if type(schedule.get("include_global", False)) is not bool:
            raise ValueError("Schedule include_global must be boolean")
        scopes = schedule.get("scopes", [])
        if not isinstance(scopes, list) or len(scopes) > 100:
            raise ValueError("Schedule scopes must contain at most 100 project scopes")
        if target_mode == "selected_projects" and not scopes:
            raise ValueError("Selected-project schedules need at least one project scope")
        if target_mode == "all_project_scopes" and scopes:
            raise ValueError("All-project schedules cannot also select project scopes")
        if any(not isinstance(scope, str) or not scope.startswith("project:") for scope in scopes):
            raise ValueError("Schedule targets must be project scopes")
        for scope in scopes:
            validate_scope(scope)
        if len(set(scopes)) != len(scopes):
            raise ValueError("Schedule project scopes must be distinct")
    elif "scopes" in schedule or "include_global" in schedule:
        raise ValueError("Schedule targets require a target mode")
    _shape(data["budgets"], {"daily_calls", "daily_tokens", "daily_usd"})
    _number(data["budgets"]["daily_calls"], 1, 100_000, True)
    _number(data["budgets"]["daily_tokens"], 1, 100_000_000, True)
    _number(data["budgets"]["daily_usd"], 0, 100_000)
    validated = copy.deepcopy(data)
    validated["schedule"].setdefault("scope", "global")
    consolidation = validated.setdefault("consolidation", copy.deepcopy(DEFAULT_SETTINGS["consolidation"]))
    _shape(consolidation, {"project_summaries"})
    if type(consolidation["project_summaries"]) is not bool:
        raise ValueError("Project summaries must be explicitly enabled or disabled")
    ranking = validated.setdefault("ranking", copy.deepcopy(DEFAULT_SETTINGS["ranking"]))
    _shape(ranking, {"importance_weight", "confidence_weight"})
    _number(ranking["importance_weight"], 0, 0.25)
    _number(ranking["confidence_weight"], 0, 0.25)
    if ranking["importance_weight"] + ranking["confidence_weight"] > 0.25:
        raise ValueError("Combined ranking weights cannot exceed 0.25")
    if ranking["confidence_weight"] != 0:
        raise ValueError("Confidence weighting is unavailable until an assessor is evaluated; use zero")
    lifecycle = validated.setdefault("lifecycle", copy.deepcopy(DEFAULT_SETTINGS["lifecycle"]))
    _shape(lifecycle, {"episode_recall_days"})
    _number(lifecycle["episode_recall_days"], 0, 36500, True)
    judgment = validated.setdefault("judgment", copy.deepcopy(DEFAULT_SETTINGS["judgment"]))
    _shape(judgment, {"primary", "fallback", "scopes", "operations"})
    if not isinstance(judgment["primary"], str) or not isinstance(judgment["fallback"], list):
        raise ValueError("Invalid judgment provider chain")
    chain = ([judgment["primary"]] if judgment["primary"] else []) + judgment["fallback"]
    if (len(chain) > 3 or any(not isinstance(item, str) or item not in providers
            or not providers[item]["kind"].startswith("plugin:") for item in chain)
            or len(chain) != len(set(chain)) or (not judgment["primary"] and chain)):
        raise ValueError("Judgment needs up to three distinct plugin profiles, not generative API fallbacks")
    scopes = judgment["scopes"]
    if (not isinstance(scopes, list) or len(scopes) > 100
            or any(not isinstance(scope, str) for scope in scopes) or len(scopes) != len(set(scopes))):
        raise ValueError("Select up to 100 distinct scopes for external judgment")
    for scope in scopes:
        validate_scope(scope)
    operations = judgment["operations"]
    if (not isinstance(operations, list) or not operations or len(operations) > 2
            or any(value not in ("support", "compare") for value in operations)
            or "support" not in operations or len(operations) != len(set(operations))):
        raise ValueError("Judgment operations require support with optional compare")
    retrieval = validated.setdefault("retrieval", copy.deepcopy(DEFAULT_SETTINGS["retrieval"]))
    _shape(retrieval, {"source_excerpt"})
    if type(retrieval["source_excerpt"]) is not bool:
        raise ValueError("Original-source retrieval must be enabled or disabled")
    configs = validated.setdefault("module_settings", {})
    if not isinstance(configs, dict) or len(configs) > 32:
        raise ValueError("Select at most 32 module configurations")
    for name, config in configs.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,48}", name)
                or not isinstance(config, dict) or len(json.dumps(config)) > 16_000):
            raise ValueError("Module settings require a bounded object keyed by module ID")
    return validated


def load_settings(vault: Vault) -> dict:
    path = local_file(vault, "settings.json")
    if not path.exists():
        return copy.deepcopy(DEFAULT_SETTINGS)
    if path.stat().st_size > 100_000:
        raise ValueError("Settings file exceeds size limit")
    return validate_settings(json.loads(path.read_text(encoding="utf-8")))


def save_settings(vault: Vault, data: dict) -> dict:
    validated = validate_settings(data)
    # Modules own detailed validation. Reading disabled module configuration
    # preserves it without importing optional code.
    from .config import load_config
    from .modules import load_enabled_module
    for name in set(validated["module_settings"]) & set(load_config().enabled_modules):
        validator = getattr(load_enabled_module(name), "validate_config", None)
        if callable(validator):
            validated["module_settings"][name] = validator(validated["module_settings"][name])
    validated = validate_settings(validated)
    encoded = json.dumps(validated, indent=2) + "\n"
    if len(encoded.encode("utf-8")) > 100_000:
        raise ValueError("Settings file exceeds size limit")
    _atomic_write(local_file(vault, "settings.json"), encoded)
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
