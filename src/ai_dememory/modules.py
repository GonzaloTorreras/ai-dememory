"""Lazy discovery and activation of optional ai DeMemory modules."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .config import load_config, set_module_enabled
from .models import ModuleManifest


class ModuleError(ValueError):
    pass


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    version: str
    summary: str
    entrypoint: str
    capabilities: tuple[str, ...]
    resource_budget: dict[str, int | bool | str]
    builtin: bool
    enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_BUILTINS = {
    "mcp": ModuleDescriptor(
        module_id="mcp",
        version="1",
        summary="Local stdio MCP bridge with five bounded tools.",
        entrypoint="ai_dememory.builtin_modules.mcp",
        capabilities=("search", "get", "context", "propose", "status"),
        resource_budget={"network": False, "child_processes": 0, "persistent": False},
        builtin=True,
        enabled=False,
    )
}


def _valid_id(module_id: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9-]{1,48}", module_id))


def discover_modules() -> dict[str, ModuleDescriptor]:
    enabled = set(load_config().enabled_modules)
    modules = {
        key: ModuleDescriptor(**{**asdict(value), "enabled": key in enabled})
        for key, value in _BUILTINS.items()
    }
    try:
        entrypoints = importlib.metadata.entry_points(group="ai_dememory.modules")
    except TypeError:
        entrypoints = importlib.metadata.entry_points().select(group="ai_dememory.modules")
    for entrypoint in entrypoints:
        if not _valid_id(entrypoint.name) or entrypoint.name in modules:
            continue
        distribution = getattr(entrypoint, "dist", None)
        modules[entrypoint.name] = ModuleDescriptor(
            module_id=entrypoint.name,
            version=getattr(distribution, "version", "unknown"),
            summary="Installed community module; load it only after enabling it.",
            entrypoint=entrypoint.value,
            capabilities=(),
            resource_budget={"declared_on_load": True},
            builtin=False,
            enabled=entrypoint.name in enabled,
        )
    return modules


def _load_entrypoint(descriptor: ModuleDescriptor) -> ModuleType | Any:
    if descriptor.builtin:
        return importlib.import_module(descriptor.entrypoint)
    for entrypoint in importlib.metadata.entry_points(group="ai_dememory.modules"):
        if entrypoint.name == descriptor.module_id:
            return entrypoint.load()
    raise ModuleError(f"Module is no longer installed: {descriptor.module_id}")


def _manifest(loaded: ModuleType | Any) -> ModuleManifest:
    value = loaded.get_manifest() if hasattr(loaded, "get_manifest") else getattr(loaded, "manifest", None)
    if not isinstance(value, ModuleManifest):
        raise ModuleError("Module must expose get_manifest() returning ModuleManifest")
    if not _valid_id(value.module_id):
        raise ModuleError(f"Invalid module id: {value.module_id}")
    return value


def enable_module(module_id: str) -> ModuleManifest:
    descriptor = discover_modules().get(module_id)
    if descriptor is None:
        raise ModuleError(f"Unknown module: {module_id}")
    loaded = _load_entrypoint(descriptor)
    manifest = _manifest(loaded)
    if manifest.module_id != module_id:
        raise ModuleError(f"Module id mismatch: expected {module_id}, got {manifest.module_id}")
    set_module_enabled(module_id, True)
    return manifest


def disable_module(module_id: str) -> None:
    if module_id not in discover_modules() and module_id not in load_config().enabled_modules:
        raise ModuleError(f"Unknown module: {module_id}")
    set_module_enabled(module_id, False)


def load_enabled_module(module_id: str) -> ModuleType | Any:
    descriptor = discover_modules().get(module_id)
    if descriptor is None:
        raise ModuleError(f"Unknown module: {module_id}")
    if not descriptor.enabled:
        raise ModuleError(f"Module {module_id} is disabled. Run `ai-dememory module enable {module_id}`.")
    loaded = _load_entrypoint(descriptor)
    _manifest(loaded)
    return loaded


def create_module(module_id: str, target: Path | None = None) -> Path:
    if not _valid_id(module_id):
        raise ModuleError("Module id must use lowercase letters, numbers and hyphens")
    package_name = module_id.replace("-", "_")
    root = (target or Path.cwd() / f"ai-dememory-module-{module_id}").expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ModuleError(f"Target directory is not empty: {root}")
    package = root / "src" / package_name
    tests = root / "tests"
    package.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "\n".join(
            (
                "[build-system]",
                'requires = ["setuptools>=77"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[project]",
                f'name = "ai-dememory-module-{module_id}"',
                'version = "0.1.0"',
                f'dependencies = ["ai-dememory>=3.0.0a1,<4"]',
                "",
                '[project.entry-points."ai_dememory.modules"]',
                f'{module_id} = "{package_name}"',
                "",
                "[tool.setuptools]",
                'package-dir = {"" = "src"}',
                "",
                "[tool.setuptools.packages.find]",
                'where = ["src"]',
                "",
            )
        ),
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        "\n".join(
            (
                '"""An optional ai DeMemory module."""',
                "",
                "import json",
                "",
                "from ai_dememory.models import ModuleManifest",
                "",
                "",
                "def get_manifest() -> ModuleManifest:",
                "    return ModuleManifest(",
                f'        module_id={json.dumps(module_id)},',
                '        version="0.1.0",',
                '        summary="Describe what this module adds.",',
                '        capabilities=("status",),',
                '        resource_budget={"network": False, "child_processes": 0, "persistent": False},',
                "    )",
                "",
                "",
                "def serve(services, argv) -> int:",
                '    """Run in the foreground using only the narrow CoreServices API."""',
                "    if argv:",
                '        raise ValueError("This example module does not accept arguments")',
                f'    print(json.dumps({{"module": {json.dumps(module_id)}, "core": services.status()}}, indent=2))',
                "    return 0",
                "",
            )
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"# ai DeMemory module: {module_id}\n\nGenerated by `ai-dememory module create {module_id}`.\n",
        encoding="utf-8",
    )
    (tests / "test_manifest.py").write_text(
        "\n".join(
            (
                "import unittest",
                f"from {package_name} import get_manifest",
                "",
                "",
                "class ManifestTest(unittest.TestCase):",
                "    def test_manifest(self):",
                f"        self.assertEqual(get_manifest().module_id, {json.dumps(module_id)})",
                "",
                "",
                'if __name__ == "__main__":',
                "    unittest.main()",
                "",
            )
        ),
        encoding="utf-8",
    )
    return root
