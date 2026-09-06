# Modules

Modules keep integrations out of the default runtime.

```bash
ai-dememory module list
ai-dememory module enable mcp
ai-dememory module disable mcp
ai-dememory module create my-module
```

The human list shows state and capabilities. `module enable` prints the exact
foreground `serve` command to run next; `--json` keeps the same information for
clients and scripts.

`module create` writes one tiny editable Python package and prints the exact
install, enable and foreground-run commands. It does not install or execute the
new code automatically.

## Contract

An installed module registers the `ai_dememory.modules` Python entry-point and
exposes `get_manifest()` returning `ModuleManifest`:

- `module_id` and `version` identify it;
- `capabilities` explains what it adds;
- `resource_budget` declares network, process and persistence intentions.

Discovery reads package metadata without importing disabled modules. Enabling a
module imports it once to validate the manifest. `serve` loads only the named,
enabled module and runs it in the foreground.

Modules should accept `CoreServices`, which permits scoped reads, bounded
context, evidenced `learn`, reversible `forget`, listing, proposals and status.
Inference is provisional; explicit sourced statements may be admitted directly.
A person promotes a generated summary with `ai-dememory review accept`.

This is the supported interface, not a security boundary. Enabled Python code
can still import other package objects or access process-local state; review it
as carefully as any installed dependency.

The generated package includes a working foreground entrypoint with this
contract:

```python
def serve(services, argv) -> int:
    print(services.status())
    return 0
```

`services` is the narrow `CoreServices` surface and `argv` contains arguments
after the module id. A module must stay in the foreground and return a process
exit code; it should not create a daemon or child process unless its reviewed
manifest and documentation explicitly declare that behavior.

Use `--` before module arguments that collide with ai DeMemory globals, for
example `ai-dememory serve my-module -- --json`.

## Trust

Python plugins are local trusted code. The API and manifest encourage least
privilege but cannot prevent malicious code from opening files or processes.
Install only reviewed packages. Resource budgets are descriptive until a real
need justifies an external sandbox or supervisor.

Disabling prevents future module starts/imports; stop an already-running foreground
service separately with Ctrl+C. It does not uninstall the third-party package or
its dependencies. A stale enabled id can still be
disabled after its package has been removed.

## Bundled MCP module

`mcp` is installed with the package but disabled by default. When enabled,
`ai-dememory serve mcp` runs a synchronous stdio server with no socket or child
process and exactly seven tools:

- `memory.search`
- `memory.get`
- `memory.context`
- `memory.propose`
- `memory.learn`
- `memory.forget`
- `memory.status`

Point an MCP client at command `ai-dememory` with arguments `serve`, `mcp`.
The saved default vault removes the need to embed a private path in client
configuration.

## Bundled workbench module

`workbench` is disabled by default. Enable it and run `ai-dememory serve workbench`
for the [local dashboard](workbench.md). Its HTTP listener is loopback-only and
cannot be configured for LAN or internet access. Provider calls are optional
outbound requests to configured endpoints, not a remote memory service.
