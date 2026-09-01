# Architecture

ai DeMemory has one small core and optional modules.

```text
Human CLI ──remember──► atomic write ──► read-back ──► canonical Markdown
Human CLI ──recall/status──► SQLite FTS ◄───────────────┘
                                 ▲
AI or optional module ───────────┼─search/get/context/status
             │                   │
             └─propose──► Markdown proposals ──human review──► canonical Markdown
```

## Core

The Python core owns:

- selecting one default vault in machine-local configuration;
- safe, atomic Markdown writes;
- exact read-back verification before a save is reported;
- a minimal `id` and `title` memory contract;
- incremental Unicode FTS indexing and local recall;
- proposal review; and
- module discovery and activation.

The vault contains only three product directories:

```text
vault/
  .ai-dememory.toml
  .ai-dememory.write.lock # generated coordination file; contains no memory
  memories/             # canonical Markdown
  proposals/            # pending and decided proposals
  indexes/memory.sqlite # generated, disposable
```

Proposals are capped at 64 KB each and 1,000 files total. `review list` returns
at most 20 by default (100 when requested); reviewed proposal files can be
removed directly when their audit value is no longer needed.

The app selector stores only the chosen absolute vault path. Commands resolve
`--vault` first and then the saved default; they never infer a vault from the
current source checkout. `remember` does not touch SQLite; `recall` synchronizes
the disposable index on demand from canonical Markdown.

## Modules

Modules are disabled by default and loaded only after activation. The stable
`CoreServices` object offers search, get, bounded context, propose and status;
it deliberately has no canonical-write method.

This is an API boundary, not a sandbox. Installing a Python module gives that
package the same local-code trust as any other dependency. Manifests make
capabilities and resource intentions visible, but the operating system does not
enforce them.

## Runtime choice

Python remains the correct core runtime because Markdown, SQLite, packaging,
CLI and stdio MCP all work with the standard library. Node would add a second
runtime without improving the current data path. A future web UI may use
TypeScript inside an optional module after the headless product is proven.
