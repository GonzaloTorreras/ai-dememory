# Maintainer Script Reference

This directory is a maintainer reference for the Python implementation behind
`ai-dememory`. It is not the installation guide. Normal users should install
the `ai-dememory` command, create a separately bound private vault with the
wizard, and follow [the user documentation](../docs/install.md).

Python 3.11+ is supported. The public repository contains demo and validation
fixtures only; do not use it as a personal vault.

## User-Facing CLI

The installed command is `ai-dememory`—there is no separate `ai-memory`
executable. Bind normal commands to the intended private vault:

```bash
ai-dememory --root ~/code/my-memory doctor
ai-dememory --root ~/code/my-memory index
ai-dememory --root ~/code/my-memory search "topic or project" --limit 5
ai-dememory --root ~/code/my-memory mcp-config --client codex
ai-dememory --root ~/code/my-memory api
```

The final command starts the optional foreground loopback REST API for a local
dashboard or script; it is not an MCP server and it is not started by package
installation. See [Local REST API](../docs/local-api.md) and
[Local MCP](../docs/local-mcp.md) for the audience and safety boundary.

Use these help surfaces instead of treating this file as a copy-everything
checklist:

```bash
ai-dememory --help
ai-dememory <command> --help
ai-dememory dev --help
```

## Advanced Vault Operations

An existing vault owner may deliberately opt into imports, maintenance, review
packets, hooks, or scheduler work. Preview before applying any stateful action:

```bash
ai-dememory --root ~/code/my-memory setup plan --json
ai-dememory --root ~/code/my-memory setup health --json
ai-dememory providers detect
ai-dememory --root ~/code/my-memory schedule plan --json
ai-dememory --root ~/code/my-memory schedule setup --dry-run
ai-dememory --root ~/code/my-memory maintenance run --profile daily --dry-run --json
```

The wizard does not install hooks or schedules, import chats, start MCP/API
servers, or create durable personal memory. Those actions remain explicit and
review-first. Generated indexes, reports, and context exports are disposable;
Markdown under the private vault is canonical.

## Maintainer And CI Commands

The `dev` namespace groups advanced, CI, release, test-fixture, and source-tree
diagnostics so they do not look like first-run requirements. Direct legacy forms
remain supported for compatibility, but new documentation should prefer the
namespace:

```bash
ai-dememory dev verify-mcp
ai-dememory dev api-smoke
ai-dememory --root <initialized-vault> dev mcp-client-smoke
ai-dememory dev release-check
ai-dememory dev publish-plan --repository testpypi --json
ai-dememory dev release-evidence --json
```

These commands can read source fixtures, create temporary test vaults, or
validate a draft PR/release contract. They are not normal private-vault startup
or maintenance commands. Use `ai-dememory dev --help` for the complete list,
including package build, CI, publish, acceptance, recall-fixture, provenance,
and artifact guards.

## Source Checkout Fallback

Only contributors debugging a trusted checkout should invoke the compatibility
wrapper directly. It runs the source tree, not the installed package. Keep the
vault path explicit and separate from the checkout:

```bash
python3 -m pip install -e .
python3 scripts/ai_dememory.py --root /path/to/private-vault validate
python3 scripts/ai_dememory.py --root /path/to/private-vault api
python3 scripts/ai_dememory.py verify-mcp
python3 -m unittest discover -s tests -t .
```

On Windows, use `py -3` when `python3` is unavailable. CI, draft-PR runtime
smoke, package publication, and release commands belong to a source checkout;
they must not be copied into an end-user vault workflow.

## Direct Script Modules

The individual files remain useful for narrow debugging and are not public
wrappers to document as the primary user API.

| Area | Main modules |
| --- | --- |
| Canonical vault validation and retrieval | `validate_memory.py`, `secret_scan.py`, `index_memory.py`, `search_memory.py`, `context_memory.py`, `graph_memory.py` |
| Local integrations | `http_api.py`, `mcp_client_smoke.py`, `mcp_runtime_smoke.py`, `hook_event.py`, `provider_import.py` |
| Review and lifecycle | `recall_fixtures.py`, `capture_miss.py`, `review_memory.py`, `lifecycle.py`, `sleep_consolidation.py`, `working_memory.py` |
| Maintenance and scheduler | `maintenance.py`, `schedule_memory.py`, `resource_policy.py`, `process_control.py` |
| Release and repository guards | `install_smoke.py`, `package_build_smoke.py`, `release_check.py`, `publish_guard.py`, `ci_guard.py`, `artifact_guard.py`, `release_evidence.py` |

Each module accepts its own `--help`. When a module has a supported CLI command,
prefer that installed command in user-facing documentation; keep a direct-script
example only when testing or debugging the checkout itself.
