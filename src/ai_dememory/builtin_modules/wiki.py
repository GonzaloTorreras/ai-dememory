"""Optional project wiki. Plain Markdown remains usable without the module."""
from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest(module_id="wiki", version="1",
        summary="Portable project Markdown wiki, bounded recall and local maintenance.",
        capabilities=("project-wiki", "recall", "maintenance"),
        resource_budget={"network":"explicit assisted recall only", "child_processes":"configured native provider only", "persistent":False})


def validate_config(value):
    if value:
        raise ValueError("Configure each project in the Wiki dashboard; no global wiki options are defined")
    return {}


def serve(services, argv=None):
    import argparse
    import json
    from ai_dememory.wiki_runtime import WikiService
    parser = argparse.ArgumentParser(prog="ai-dememory serve wiki")
    parser.add_argument("--run-due", action="store_true", help="Check local wiki maintenance once and exit; no model or history ingestion")
    args = parser.parse_args(argv)
    service = WikiService(services.vault)
    print(json.dumps(service.tick() if args.run_due else service.action("list", {})))
    return 0
