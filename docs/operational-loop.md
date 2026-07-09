# Operational Memory Loop

`ai-dememory` supports the first daily agentic development loop:

```text
context at session start
working memory during task
capture lessons as proposals
record usefulness outcomes
review false positives and conflicts
prepare sleep consolidation packets
handoff at session end
```

## Session Start Context

Build token-budgeted context:

```bash
ai-dememory context "ai-dememory scheduler" --budget 2000
ai-dememory context --auto --budget 2000
ai-dememory context "ai-dememory scheduler" --why
```

The context command uses SQLite FTS ranking, excludes private/sensitive memories
by default, and includes `working/current.json` plus `working/recent-session.md`
unless `--no-working-memory` is set.

Vaults can set context defaults in `.ai-dememory.toml`:

```toml
[context]
default_budget_tokens = 2000
include_working_memory = true
explain_results = false
```

CLI flags override these defaults. For example, `--budget`,
`--include-working-memory`, `--no-working-memory`, `--why`, and `--no-why`
apply only to the current command. When `explain_results` or `--why` is enabled,
the rendered context includes the same matched fields and scoring components
already returned in JSON item metadata.

MCP clients can call `memory.context` with `query`, `budget_tokens`, `limit`,
`include_sensitive`, `include_working_memory`, and `explain_results`.
Omitted MCP arguments use the vault `[context]` defaults. Clients can also call
it with `auto: true` and no query to derive the search query from generated
working memory; the response includes `query_source` so clients can tell
explicit and working-memory context apart.

## Explainable Search

Explain ranking components:

```bash
ai-dememory search "ai-dememory scheduler" --why
```

The explanation includes FTS match, tag overlap, alias match, recency,
confidence, type boost, pin boost, lifecycle strength, and penalties. It also
includes `matched_terms`, `matched_fields`, `matched_tags`, and
`matched_aliases` so reviewers can see which indexed evidence caused a memory
to rank.

## Working Memory

Capture current state:

```bash
ai-dememory working snapshot \
  --title "Scheduler hardening" \
  --task ai-dememory \
  --notes "Need to verify plugin release-check and package smoke."
```

Write a handoff:

```bash
ai-dememory working handoff \
  --title "Scheduler PR handoff" \
  --notes "Next: review CI and make PR ready."
```

Inspect resumable working state and recent handoffs:

```bash
ai-dememory working status --json
```

Files are written under:

- `working/current.json`
- `working/recent-session.md`
- `working/handoffs/`

Working files are operational state, not canonical durable memory.

MCP clients can use `memory.working_current`, `memory.working_status`,
`memory.working_snapshot`, and `memory.working_handoff` for the same generated
state. Snapshot and handoff writes are secret-scanned and stay under
`working/`.

## Lifecycle And Outcomes

Record retrieval:

```bash
ai-dememory mark-seen --id mem_example --query "scheduler"
ai-dememory mark-seen --id mem_example --query "scheduler" --json
```

The JSON form returns a feedback receipt with the memory id, query, score,
caller, timestamp, and whether lifecycle state was updated.

Record usefulness:

```bash
ai-dememory outcome --id mem_example --good --json
ai-dememory outcome --last --bad --note "Irrelevant result." --json
```

The JSON form returns a feedback receipt with the selected memory id, whether
the target came from an explicit id or the last retrieval, the updated positive
and negative counters, strength, reward factor, timestamp, and whether lifecycle
state was updated. Notes are stored after secret scanning but are not echoed in
the receipt.

Lifecycle state is stored in the generated SQLite index. Good outcomes increase
strength; bad outcomes reduce it. Search ranking uses lifecycle strength as a
small explainable component.

Inspect lifecycle scores:

```bash
ai-dememory lifecycle scores --json
ai-dememory lifecycle report
```

Index rebuilds preserve generated lifecycle tables for current memories, so
retrieval and outcome feedback survive daily maintenance. Lifecycle reports are
generated review artifacts, not canonical memory.

## Review Feedback

Generate review reports:

```bash
ai-dememory review false-positives
ai-dememory review conflicts
ai-dememory review plan --kind conflict
```

False-positive suppressions and conflict decisions are stored in
`.ai-dememory-ignore.toml`. Conflict merge proposals are written to
`inbox/conflict-resolution/` and still require human promotion into canonical
memory. Review modes define whether LLMs may only gather evidence or may also
draft review notes and merge proposals.

See [review-workflows.md](review-workflows.md).

## Sleep Consolidation

Generate a safe overnight-style review plan:

```bash
ai-dememory sleep plan
ai-dememory sleep apply-reviewed --id sleep_...
```

Sleep consolidation writes only generated reports and review packets under
`inbox/sleep-consolidation/`. It never edits canonical memory.

See [sleep-consolidation.md](sleep-consolidation.md).

## Scheduled Maintenance And Plugin Use

Recurring daily and weekly maintenance is opt-in and host-scheduler owned. The
Codex plugin can show setup, hook, provider, and scheduler plans through MCP,
but package and plugin installation do not create jobs or import provider data.

See [scheduler-plugin-blueprint.md](scheduler-plugin-blueprint.md).

## Safety Boundaries

- Context excludes restricted memory by default.
- Working snapshots and handoffs are secret-scanned.
- Outcomes update generated lifecycle state, not Markdown canonical memory.
- Review suppressions and merge proposals do not mutate canonical memory.
- Sleep consolidation packets do not mutate canonical memory.
- Durable/project/tool memory changes still go through proposal and human review.
