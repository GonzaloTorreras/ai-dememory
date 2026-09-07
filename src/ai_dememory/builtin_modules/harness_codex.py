"""Independently enabled Codex integration."""
from ai_dememory.builtin_modules.harness import serve as install
from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest("harness-codex", "1", "Codex project MCP and recall hooks", ("install", "recall-hook"), {"network":False,"child_processes":0,"persistent":False})


def serve(services, argv=None):
    return install(services, [*(argv or []), "--client", "codex"])
