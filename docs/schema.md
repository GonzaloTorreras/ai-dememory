# Memory Schema

This schema applies to Markdown memory documents under `memories/`. `README.md`
files and generated artifacts are not memory documents.

Every memory document must start with YAML-style frontmatter delimited by `---`.
The repository scripts intentionally support only a small, predictable YAML
subset: strings, numbers, booleans, `null`, inline lists, and the nested
`source` map.

## Required Fields

```yaml
id: mem_YYYYMMDD_slug
title: Title
type: active
status: active
scope: personal
project: null
tags: []
aliases: []
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
confidence: 0.7
sensitivity: internal
source:
  kind: manual
  ref: null
pin: false
decay: normal
review_after: YYYY-MM-DD
```

## Field Contract

- `id`: stable unique identifier, lowercase letters, numbers, `_`, `-`, or `/`.
- `title`: short human-readable title.
- `type`: one of `durable`, `active`, `project`, `tool`, `archive`, `session`.
- `status`: one of `active`, `proposed`, `stale`, `disputed`, `archived`,
  `superseded`, `expired`.
- `scope`: one of `personal`, `project`, `tool`, `session`, `global`.
- `project`: project slug or `null`.
- `tags`: inline list of lowercase search tags.
- `aliases`: inline list of alternate names or phrases.
- `created_at`: `YYYY-MM-DD`.
- `updated_at`: `YYYY-MM-DD`.
- `confidence`: number from `0.0` to `1.0`.
- `sensitivity`: one of `public`, `internal`, `private`, `sensitive`,
  `secret-prohibited`.
- `source.kind`: one of `manual`, `codex`, `claude`, `gemini`, `automation`,
  `import`, `external`, `conversation`.
- `source.ref`: short source reference or `null`.
- `pin`: boolean. Pinned memories receive ranking boost and review protection.
- `decay`: one of `none`, `slow`, `normal`, `fast`.
- `review_after`: `YYYY-MM-DD`.
- `reviewed`: required only for `type: durable`; must be `true` after human
  review before the memory is accepted as durable canonical memory.
- `reviewed_by`: required only for `type: durable`; human reviewer name or
  handle.
- `reviewed_at`: required only for `type: durable`; `YYYY-MM-DD` review date.

Run `ai-dememory provenance` to audit durable memories for missing reviewed
provenance before release or publication.

`public` and `internal` are eligible for default search, MCP results, and
generated LLM context. `private` and `sensitive` are valid canonical labels, but
tooling excludes them from default LLM-facing output unless a local user
explicitly includes sensitive memory. `sensitivity: secret-prohibited` is a
sentinel for quarantined material. It is listed so tooling can recognize it, but
canonical memory validation rejects it.

## Decay

- `none`: no freshness decay.
- `slow`: half-life of 180 days.
- `normal`: half-life of 60 days.
- `fast`: half-life of 14 days.

Expired memories are excluded from search unless explicitly requested.
Archived, stale, and disputed memories remain searchable with penalties.

## Examples

Durable memory:

```yaml
id: mem_20260614_values
title: Durable Values
type: durable
reviewed: true
reviewed_by: Gonzalo Torreras
reviewed_at: 2026-06-14
status: active
scope: personal
project: null
tags: [values, operating-principles]
aliases: [core values]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.8
sensitivity: internal
source:
  kind: manual
  ref: initial-scaffold
pin: true
decay: none
review_after: 2026-09-14
```

Active memory:

```yaml
id: mem_20260614_active_context
title: Active Working Context
type: active
status: active
scope: personal
project: ai-dememory
tags: [active, memory, implementation]
aliases: [current context]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.8
sensitivity: internal
source:
  kind: codex
  ref: planning-thread
pin: false
decay: fast
review_after: 2026-07-14
```

Project memory:

```yaml
id: mem_20260614_portfolio_tickers
title: Portfolio Tracker Ticker Pricing
type: project
status: active
scope: project
project: portfolio-tracker
tags: [pricing, tickers, market-data]
aliases: [ticker prices]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.7
sensitivity: internal
source:
  kind: codex
  ref: planning-thread
pin: false
decay: normal
review_after: 2026-08-14
```

Tool memory:

```yaml
id: mem_20260614_codex_tools
title: Codex Tool Policy
type: tool
status: active
scope: tool
project: null
tags: [codex, github, tools]
aliases: [tool policy]
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.9
sensitivity: internal
source:
  kind: codex
  ref: setup-history
pin: true
decay: none
review_after: 2026-09-14
```

Archive memory:

```yaml
id: mem_20260614_old_context
title: Superseded Setup Context
type: archive
status: archived
scope: personal
project: ai-dememory
tags: [archive, setup]
aliases: []
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.6
sensitivity: internal
source:
  kind: manual
  ref: migrated-note
pin: false
decay: slow
review_after: 2026-12-14
```

Session memory:

```yaml
id: mem_20260614_session_ai_dememory
title: ai DeMemory MVP Session
type: session
status: proposed
scope: session
project: ai-dememory
tags: [session, implementation]
aliases: []
created_at: 2026-06-14
updated_at: 2026-06-14
confidence: 0.6
sensitivity: internal
source:
  kind: codex
  ref: local-session
pin: false
decay: fast
review_after: 2026-06-21
```
