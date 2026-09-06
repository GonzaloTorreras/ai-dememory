"""Optional project-local harness integration installer."""

from ai_dememory.harness import install_parser, install_project
from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest("harness", "1", "Project-local MCP and recall hook",
                          ("install", "recall-hook"),
                          {"network": False, "child_processes": 0, "persistent": False})


def serve(services, argv=None):
    args = install_parser().parse_args(argv)
    paths = install_project(services.vault, args.project, args.client, args.scope)
    print("Installed project-local integration:")
    for path in paths:
        print(f"  {path}")
    print("Restart the client in this project. Codex: review and trust the hook in /hooks.")
    print("No transcript import, extra model or background process is enabled.")
    return 0
