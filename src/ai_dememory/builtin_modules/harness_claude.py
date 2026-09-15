"""Independently enabled Claude Code integration."""
from ai_dememory.builtin_modules.harness import serve as install
from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest("harness-claude", "1", "Claude Code project MCP and recall hooks", ("install", "recall-hook"), {"network":False,"child_processes":0,"persistent":False})


def serve(services, argv=None):
    return install(services, [*(argv or []), "--client", "claude"])
