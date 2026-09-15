"""Optional project-local harness integration installer."""

from ai_dememory.harness import install_parser, install_project
from ai_dememory.models import ModuleManifest


def get_manifest():
    return ModuleManifest("harness", "1", "Project-local MCP and recall hook",
                          ("install", "recall-hook"),
                          {"network": False, "child_processes": 0, "persistent": False})


def serve(services, argv=None):
    args = install_parser().parse_args(argv)
    if args.user:
        if args.client != "codex" or args.action not in {"install", "uninstall"} or args.scope:
            raise ValueError("User installation supports Codex automatic project scopes only")
        from ai_dememory.integration_install import install_user
        result = install_user(services.vault, remove=args.action == "uninstall", projects=args.retire_project)
        print("Global Codex integration installed." if result["installed"] else "Global Codex integration removed.")
        print("Restart Codex. Review and trust UserPromptSubmit and SessionStart in /hooks; trust is never bypassed."
              if result["installed"] else "Restart Codex to unload this connection; any unchanged retired project connections were restored.")
        print("No daemon, transcript scan or extra model call. Vault memories are preserved.")
        return 0
    if args.action in {"bind", "exclude", "include"}:
        from ai_dememory.projects import configure_project
        if args.action == "bind" and not args.scope:
            raise ValueError("Choose an explicit scope for this project")
        result = configure_project(args.project, scope=args.scope,
                                   client=args.client if args.action != "bind" else None,
                                   enabled=args.action == "include")
        print(f"Project scope: {result['scope']}. Excluded clients: {', '.join(result['excluded_clients']) or 'none'}")
        return 0
    if args.action != "install" or not args.scope or args.retire_project:
        raise ValueError("Project installation requires install --project PATH --scope SCOPE")
    paths = install_project(services.vault, args.project, args.client, args.scope)
    print("Installed project-local integration:")
    for path in paths:
        print(f"  {path}")
    print("Restart the client in this project. Codex: review and trust the hook in /hooks.")
    print("No transcript import, extra model or background process is enabled.")
    return 0
