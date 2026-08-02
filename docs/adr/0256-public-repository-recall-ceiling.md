# ADR 0256: Public-Repository Recall Ceiling

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-26.

## Context

The historical recall default excluded `private` and `sensitive` memories but
still returned `internal` memory and generated working state. That default is
appropriate for a locally authorized private vault, not for work whose output
will be committed to a public repository.

Sensitivity labels in rendered context make review possible, but labels alone
do not prevent non-public titles, snippets, identifiers, or auto-generated
queries from influencing public artifacts. Filtering after a ranked result
limit also lets internal hits hide otherwise valid public results.

## Decision

Add an explicit, fail-closed `public_only` ceiling:

- search filters every sensitivity other than `public` before ranking results
  are limited, derives text scores only from revalidated canonical public
  Markdown, and excludes generated lifecycle strength;
- context uses that pre-limited search, does not read generated working memory,
  preserves a structured working-memory exclusion status, and never reports
  rejected memory identifiers;
- public-only context requires an explicit query and rejects `auto` before
  generated working state is read;
- MCP `memory.search`, `memory.context`, and `memory.get` expose the same
  `public_only` control;
- CLI `search --public-only` and `context --public-only` expose the equivalent
  boundary;
- generated public-repository instructions require
  `memory.context(public_only=true, include_working_memory=false)` or
  `memory.search(public_only=true)`, and require `memory.get(public_only=true)`
  for a selected item;
- public-repository agents must not use working-memory tools, graph, resources,
  prompts, auto context, or any recall surface without a public-only ceiling.

Non-public content injected by an already-running native hook remains tainted
context. It cannot be quoted, paraphrased, transformed, or committed without
explicit disclosure authorization and a separate review.

## Consequences

Public recall is enforceable by the retrieval surface instead of depending on
an agent to inspect content after exposure. Internal results cannot consume the
public result limit, and public output no longer reveals filtered identifiers
or working-query text.

Hidden index rows, global FTS corpus statistics, and generated lifecycle events
cannot change public-only scores, ordering, or ranking explanations. The
returned `why.text_score_source` is `canonical_public` and
`why.lifecycle_strength` is deliberately zero.

Private-vault behavior remains backward compatible unless callers opt into the
new ceiling. The default still excludes `private` and `sensitive` while
allowing `internal`, so documentation must not describe the default as
public-safe.

## Limitations

The hook adapter cannot reliably infer that every current working directory is
public. Repository instructions therefore remain part of the boundary for
native hook injections. Graph, resources, prompts, and working-memory tools do
not yet implement a public-only view and are explicitly unavailable to public
repository recall.

Secret scanning detects secret-like strings; it cannot prove that ordinary
proprietary prose is safe to disclose.

## Future Work

- Add an explicit repository egress policy to hook configuration only if it can
  fail closed without silently changing private-vault recall.
- Add public-only graph or resource views only with pre-limit/pre-render
  filtering and contract tests.
- Measure public recall precision separately from private-vault recall before
  changing ranking behavior.

## Dependencies

- ADR 0253 defines the public repository as the canonical source and package
  checkout while keeping private vaults separate.
- `scripts/search_memory.py` enforces pre-limit sensitivity filtering.
- `scripts/context_memory.py` enforces explicit public context and working-state
  exclusion.
- `mcp/server/memory_mcp.py` exposes the bounded MCP controls.
- `scripts/hook_event.py`, `AGENTS.md`, `CLAUDE.md`, and
  `skills/ai-dememory/SKILL.md` define repository-facing instructions.
- `plugins/ai-dememory/skills/memory-recall/SKILL.md` and
  `plugins/ai-dememory/skills/memory-working-session/SKILL.md` enforce the same
  ceiling in the packaged Codex plugin.
- `scripts/release_check.py` rejects packaged plugin skills that reintroduce
  unbounded public-repository recall.

## Rollback

Fail closed by disabling recall for public-repository work. Do not fall back to
default search, generated working memory, resources, prompts, or graph output.
