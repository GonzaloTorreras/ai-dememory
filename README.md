# ai DeMemory

ai DeMemory gives people and AI tools a small, local memory that remains easy
to inspect and edit. Markdown is the source of truth. SQLite is only a generated
search index.

The current `main` line is being rebuilt as V3. The source version is
`3.0.0a1`; it is not published yet. V3 deliberately does not migrate or emulate
2.x because there are no known production vaults to preserve.

## Start in under five minutes

Use Python 3.11 or newer from a source checkout:

```bash
python -m pip install .
ai-dememory setup
ai-dememory remember "Markdown is the canonical memory." --title "Storage rule"
```

`setup` explains one concrete action: where the vault will live, what it will
create, and what it will not do. It creates no daemon, starts no child process,
calls no model, and uses no network. The selected vault is saved in the user's
local configuration, so normal commands work from any directory.

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

Use `--vault <path>` only when deliberately overriding the saved default.

## Human writes, AI proposes

`remember` is a direct human action and writes canonical Markdown. Optional AI
integrations can only create proposals through the public module API. A person
then decides. `review` shows a readable pending list; accepting reports the
verified Markdown path without building SQLite, while rejecting creates no
memory:

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

The bundled MCP module runs in the foreground over stdio and exposes exactly
five tools: search, get, context, propose and status. It opens no network port
and starts no subprocess. Disable it with `ai-dememory module disable mcp`.

Create a community module without copying this repository:

```bash
ai-dememory module create my-module
```

See [modules](docs/modules.md) for the trust and resource contract.

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
- [Now / Next / Later](docs/roadmap.md)
- [Development](DEVELOPMENT.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

Unlinked 2.x design documents and ADRs are historical source material only and
will be removed before the first V3 package release. They do not define current
behavior or priorities.
