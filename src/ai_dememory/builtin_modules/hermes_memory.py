"""Opt-in native Hermes integration; importing this module does not import Hermes."""

import argparse
from pathlib import Path

from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest("hermes-memory", "1", "Native Hermes provider for a scoped local vault",
                          ("install", "memory-provider"),
                          {"network": False, "child_processes": 0, "persistent": False})


def serve(services, argv=None):
    parser = argparse.ArgumentParser(prog="ai-dememory serve hermes-memory",
        description="Prepare a new isolated Hermes home. Install ai-dememory in Hermes's Python environment first. No Hermes process or model is started.")
    parser.add_argument("action", choices=["install"])
    parser.add_argument("--home", required=True, type=Path, help="New empty Hermes home; never an existing personal profile")
    parser.add_argument("--scope", required=True, help="Fixed memory scope, e.g. project:demo")
    args = parser.parse_args(argv)
    from ai_dememory.hermes_provider import install_home
    install_home(services.vault, args.home, args.scope)
    print("Prepared an isolated Hermes home. Start Hermes with HERMES_HOME pointing to it.")
    print("DeMemory replaces built-in MEMORY.md/USER.md in this new profile only.")
    print("Hermes still owns its conversation history. No credentials, transcripts or existing settings were copied.")
    return 0
