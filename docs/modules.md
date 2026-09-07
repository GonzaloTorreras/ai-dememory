# Modules

Modules keep integrations out of the default runtime.

```bash
ai-dememory module list
ai-dememory module enable mcp
ai-dememory module disable mcp
ai-dememory module create my-module
```

The human list shows state and capabilities. `module enable` prints the next
foreground `serve` command, or installation help for `harness`; `--json` keeps
the same information for clients and scripts.

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

Use `ai-dememory serve mcp --scope project:demo` for a project-bound client.
Omitted read scopes inherit that binding; different scopes are rejected.
Writes must explicitly match it. Global memories remain readable, and the
unscoped proposal store is unavailable on bound connections.

## Bundled harness module

New setups use independently enabled `harness-codex` and `harness-claude`.
For example, `ai-dememory serve harness-codex install --project <path> --scope
project:demo` always selects Codex; the Claude module always selects Claude.
The dashboard shows separate switches. Toggling one replaces a previously
enabled common switch while preserving the other client's state. The old
`harness` entrypoint remains a small installation helper, not a third provider.
Hermes/Pi/DSH currently have source readers, not installed native hook modules.

`harness` is disabled by default. It installs project-local MCP and prompt-hook
configuration for Codex or Claude Code, without changing global client settings.
It needs installation arguments, not a long-running service:

```bash
ai-dememory module enable harness
ai-dememory serve harness install --client codex --project <empty-project-path> --scope project:demo
```

See [integrations](integrations.md) for trust, synthetic acceptance scenarios,
client limitations and rollback. Hooks run only when invoked by the host.

## Bundled workbench module

`workbench` is disabled by default. Enable it and run `ai-dememory serve workbench`
for the [local dashboard](workbench.md). Its HTTP listener is loopback-only and
cannot be configured for LAN or internet access. Provider calls are optional
outbound requests to configured endpoints, not a remote memory service.

## Sources and subscription access

`sources` adds explicit local-folder preview and extraction to the workbench.
`codex-subscription` adds official Codex managed login, model listing and
subscription-backed generation. Both are disabled by default and can be toggled
in the Modules page. See [formats, account storage and limits](workbench.md).
Neither adds a default background watcher. Codex alone uses bounded owned child
processes; enabling the module does not itself start login or generation.

## Custom provider plugins

Reuse the same installed module entry-point and manifest; no second plugin
registry is needed. Add `get_provider()` returning an object with:

```python
def describe(self):
    return {"label": "My provider", "base_url": "https://example.com/v1",
            "auth": "session"}  # session, environment, or none

def validate(self, profile):
    pass  # Reject unsupported model/configuration before sending data.

def list_models(self, profile, credential):
    return ["actual-model-id"]  # Query your service; never return credentials.

def generate(self, profile, prompt, max_output_tokens, credential):
    # Implement the provider request with finite deadlines and output bounds.
    return {"text": "...", "usage": {"input_tokens": 10, "output_tokens": 5}}
```

This illustrates signatures, not a working model adapter. An enabled provider
appears in the form as a preset; profiles store `kind: "plugin:<module-id>"`.
Generation shares the existing route, fallback and budget engine. Missing usage
keeps an estimated reservation. Disabled plugins are not imported or executable,
even if a saved profile still refers to one. Removing a profile does not uninstall
the module. Disable/uninstall the package separately when appropriate.

## Custom dashboards

The bundled UI is ordinary packaged HTML/CSS/JavaScript. A community module may
provide a replacement foreground `serve(services, argv)` dashboard using the
same core, without a core fork. Injecting arbitrary scripts into the existing
dashboard or a visual dashboard editor is not implemented. Keep custom servers
loopback-only until their own remote authentication and deployment are reviewed.
