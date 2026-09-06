# Architecture

ai DeMemory has one small core and optional modules.

```text
Human CLI ──remember──► atomic write ──► read-back ──► canonical Markdown
Human CLI ──recall/status──► SQLite FTS ◄───────────────┘
                                 ▲
AI or optional module ───────────┼─search/get/context/status
             │                   │
             ├─learn(scope, source)──► active or provisional Markdown
             └─propose──► Markdown proposals ──human review──► canonical Markdown

Optional local UI ──► settings + memory management + metadata activity
                 └─► foreground jobs ──► configured provider / fallback
                                      └─► budget reservations and job receipts
```

## Core

The Python core owns:

- selecting one default vault in machine-local configuration;
- safe, atomic Markdown writes;
- exact read-back verification before a save is reported;
- a small identity, scope, provenance, status and optional correction-key contract;
- incremental Unicode FTS indexing and local recall;
- proposal review; and
- module discovery and activation.

The vault separates memory/search from optional operational state:

```text
vault/
  .ai-dememory.toml
  .ai-dememory.write.lock # generated coordination file; contains no memory
  memories/             # canonical Markdown
  proposals/            # pending and decided proposals
  indexes/memory.sqlite # generated, disposable
  settings.json         # optional non-secret provider/job configuration
  runtime.sqlite        # durable budget and metadata receipts; NOT a search index
  jobs.json             # durable schedule state
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
`CoreServices` object offers search, get, bounded context, propose, status,
list_memories, learn and forget. Explicit sourced evidence may become active;
inference remains provisional. Client-supplied evidence labels are trusted input,
not proof that an LLM's assertions are correct. Retrieval ignores inactive states.

This is an API boundary, not a sandbox. Installing a Python module gives that
package the same local-code trust as any other dependency. Manifests make
capabilities and resource intentions visible, but the operating system does not
enforce them.

## Runtime choice

Python remains the correct core runtime because Markdown, SQLite, packaging,
CLI and stdio MCP all work with the standard library. Node would add a second
runtime without improving the current data path. The optional workbench serves
plain HTML/CSS/JavaScript from the same Python process: no frontend build chain.

## Job and provider boundary

The optional [harness adapter](integrations.md) installs project-local client
settings. A short-lived prompt hook retrieves context; a scope-bound stdio MCP
process handles explicit tool calls. The host model decides what to learn,
without a second extraction model or transcript reader. Hook telemetry contains
bounded metadata only. Client trust and model behavior need separate native
acceptance; protocol tests alone cannot prove proactive learning.

Jobs call a provider protocol, never a harness-specific model class. Named
routes select an extraction/consolidation profile or a hook/skill override.
Fallbacks are ordered; each attempt reserves daily budget first. The initial
wire adapters support Responses and OpenAI-compatible JSON APIs. New protocols
belong behind this boundary, not in vault writes or retrieval.

The dashboard is loopback-only, same-origin, session-token protected for writes,
with no CORS. It is not remote MCP or a multi-user server. One synchronous job
runs at a time; the UI waits during calls. No child process or scheduler daemon
is created. Remote transport, auth, per-client scopes and nonblocking job progress
are separate later slices, described in [the plan](roadmap.md).
