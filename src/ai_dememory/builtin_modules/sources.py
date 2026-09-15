"""Optional bounded reader for explicitly selected local conversation exports."""

import argparse

from ai_dememory.models import ModuleManifest
from ai_dememory.sources import list_sources, preview_source


def get_manifest():
    return ModuleManifest("sources", "1", "Preview user text from selected local conversation exports",
                          ("list", "preview"),
                          {"network": False, "child_processes": 0, "persistent": False})


def serve(services, argv=None):
    parser = argparse.ArgumentParser(
        prog="ai-dememory serve sources",
        description="Use the Workbench conversation reader to select an explicit local folder and preview "
                    "Codex, Claude, Pi, DSH plain JSONL, generic JSON/JSONL exports, or Hermes "
                    "SQLite databases. Live Hermes needs existing WAL/SHM files on the same host. "
                    "DSH .zstd sessions are not supported. "
                    "Preview reads user text only; extraction is a separate action. "
                    "This module does not scan your home directory, start a daemon, or call a model.",
    )
    parser.parse_args(argv or [])
    parser.print_help()
    return 0
