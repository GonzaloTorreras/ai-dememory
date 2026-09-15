# ai DeMemory

ai DeMemory gives people and AI tools a small, local memory that remains easy
to inspect and edit. Markdown is the memory source of truth. Search SQLite is
disposable; optional provider budgets and job receipts are separate durable state.

The current development branch is rebuilding the product as V3. The source version is
`3.0.0a2` (alpha). See [releases](https://github.com/GonzaloTorreras/ai-dememory/releases)
for published artifacts and the target index. V3 deliberately does not migrate or emulate
2.x. Existing historical/test vaults remain separate and must not be deleted
when replacing the installed package.

## Start in under five minutes

Use Python 3.11 or newer from a source checkout:

```bash
python -m pip install .
ai-dememory setup
ai-dememory remember "Markdown is the canonical memory." --title "Storage rule"
```

`setup` explains where the vault will live and offers optional Codex integration
and a Windows consolidation task. Declining both keeps the core passive: no
daemon, child process, model call or network. Explicit extras register client/OS
configuration but do not start a model or scan conversations. The selected vault is saved in the user's
local configuration, so normal commands work from any directory. After setup it
prints the selected location, index state and one next command instead of a raw
configuration dump.

`remember` is the V3 MVP. It atomically writes one Markdown file, reads that
file back, and only then prints `Saved and verified` with its identifier and
path. It does not build SQLite, start a process or require the source checkout.
Use `--json` for a stable machine-readable result with `saved: true` and
`verified: true`.

Recall is a separate, lazy step. The disposable SQLite index is created or
updated only when it is actually needed. Human output reports how many memories
matched; `--json` returns `query`, `count` and `results`:

```bash
ai-dememory recall "canonical memory"
ai-dememory status
```

`status` is a read-only summary of the selected vault: canonical memories,
pending proposals, generated index state and enabled modules. Its zero-call and
zero-process fields describe the core only, not running optional modules. It
does not build the index or start anything. Use
`ai-dememory status --json` for scripts.

Use `--vault <path>` only when deliberately overriding the saved default.

Connect Codex across local projects with one optional user-level installation:

```bash
ai-dememory setup --with-codex --yes
```

Restart Codex and trust the generated UserPromptSubmit and SessionStart commands in `/hooks`.
Each task receives its own project scope; Git worktrees share their project.
The hook recalls relevant memory without reading transcripts or calling another
model. The host assistant can learn useful facts through the same scoped MCP.
Normal Codex tool-approval settings still apply. See [integration setup and
rollback](docs/integrations.md). Use this branch's built package or source,
not historical V2 scripts, when testing V3.

On Windows, add `--with-schedule` to that setup command for weekly consolidation
without leaving the dashboard open. Existing cadence/scope are preserved; change
them in the dashboard. This is one hourly check, not a resident service. See
[setup, hooks and scheduled work](docs/automation.md) for costs, limits and removal.

Manual `remember` and `recall` default to shared global memory. Add `--scope auto`
to use the current project, or `--scope project:NAME` for an explicit scope.
`status` shows the runtime, selected configuration and current project scope.

## Learning without approving every fact

`remember` saves your explicit input. Enabled integrations can also call
`memory.learn` with scope and provenance: explicit statements and verified
outcomes become active, while inferences remain provisional and out of recall.
Trusted clients supply that evidence; this is not automatic truth verification.
Keys allow explicit corrections and forgetting the latest correction restores
its predecessor. This is not general semantic contradiction detection.

Optional model-generated summaries still use proposals. `review` shows them;
accepting saves verified Markdown and rejecting creates no memory:

```bash
ai-dememory review
ai-dememory review show <proposal-id>
ai-dememory review accept <proposal-id>
ai-dememory review reject <proposal-id>
```

## Optional modules

Everything beyond the local core is opt-in. A disabled module contributes zero
runtime imports, tools and processes. Dependencies of an already installed
third-party package remain installed until that package is uninstalled.

```bash
ai-dememory module list
ai-dememory module enable mcp
ai-dememory serve mcp
```

`module list` shows enabled/disabled state and capabilities. Enabling a module
prints its foreground `serve` command; disabling it starts no cleanup process.

The bundled MCP module runs in the foreground over stdio and exposes seven
tools: search, get, context, propose, learn, forget and status. It opens no network port
and starts no subprocess. Disable it with `ai-dememory module disable mcp`.

The [workbench](docs/workbench.md) also provides live provider model discovery,
optional official Codex browser/device login, and manual local-conversation
previews. Its Modules page toggles these extensions. API billing and subscription
usage are distinct. [Provider plugins and replacement dashboards](docs/modules.md)
reuse the existing trusted Python module contract.

Create a community module without copying this repository:

```bash
ai-dememory module create my-module
```

The scaffold command prints its location followed by the three commands to
install, enable and run it. The generated package is deliberately small: one
manifest, one foreground function and one test.

See [modules](docs/modules.md) for the trust and resource contract.

For project-local Codex or Claude Code MCP settings and optional prompt recall,
follow [local harness integrations](docs/integrations.md). These adapters are
alpha: consult the acceptance status before assuming native client support.
Hermes has a separate opt-in [native memory provider](docs/integrations.md#native-hermes-provider-local-alpha)
using the same scoped vault. Its installed contract smoke is verified; a full
Hermes client/model episode is still pending.

## Local dashboard

```bash
ai-dememory module enable workbench
ai-dememory serve workbench
```

Open `http://127.0.0.1:8765`. Manage memory, providers, per-operation or hook/skill
routes, fallback order, budgets and a consolidation schedule in the browser.
No model is selected and no schedule is enabled by default. Choose OpenAI,
Anthropic / Claude or a local/custom endpoint. API keys can be entered for the
current workbench session or loaded from environment-variable references;
neither is saved as plaintext in the vault. An optional `codex-subscription`
module provides isolated managed login; its authenticated generation acceptance
is still pending. It is not generic OAuth for other providers.
Scheduled jobs run while the foreground service runs; an optional Windows task
can check consolidation without it. One consolidation runs at a time, and the
foreground UI waits during its own provider calls. Optional source schedules require separate explicit
opt-in; enabling the dashboard alone does not import conversations. Remote
access remains a later slice.

See [the workbench guide](docs/workbench.md) and [the V3 plan](docs/roadmap.md).

## Product boundaries

- Python is the only core runtime; Node is not required.
- Markdown is canonical; `indexes/memory.sqlite` is disposable.
- The default install has no scheduler, hooks, dashboard, graph, vectors,
  embeddings, model calls or background process.
- Modules are local trusted Python code, not sandboxes. Their declared resource
  budgets are visible metadata, not an operating-system enforcement boundary.
- The public source repository and every private vault are separate locations.
- High-confidence secret material is rejected at canonical and proposal writes;
  credentials still belong in a credential manager.

## Documentation

- [Concept and architecture](docs/architecture.md)
- [Optional modules](docs/modules.md)
- [Local harness integrations](docs/integrations.md)
- [Now / Next / Later](docs/roadmap.md)
- [Development](DEVELOPMENT.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

Unlinked 2.x design documents and ADRs are historical source material only and
will be removed before the first V3 package release. They do not define current
behavior or priorities.
