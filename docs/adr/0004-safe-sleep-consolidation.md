# ADR 0004: Safe Sleep Consolidation

Status: Accepted

Date: 2026-06-19

## Context

The v2 plan calls for sleep consolidation, but automatic consolidation can be
dangerous in a personal memory system. Inbox captures, stale facts, conflicts,
and lifecycle repair signals need review, but an unattended agent must not
rewrite durable memory or silently suppress warnings.

## Decision

Sleep consolidation is implemented as a plan-and-review-packet workflow:

- `ai-dememory sleep plan` writes or prints a generated candidate plan.
- `ai-dememory sleep plan --report-path` and
  `ai-dememory sleep plan --json-report-path` can choose generated output
  paths, but paths must resolve inside the memory root and rendered output is
  secret-scanned before writing.
- `ai-dememory sleep apply-reviewed` writes selected candidates to
  `inbox/sleep-consolidation/`.
- MCP exposes `memory.sleep_plan` and `memory.sleep_apply_reviewed`.

The workflow may write generated reports and inbox review packets only. It does
not mutate canonical memory, archive files, change frontmatter, or suppress
secret-scan findings.

## Consequences

- Maintenance can prepare a useful review queue without risking canonical data.
- Humans still decide promotion, rewrite, archive, supersede, or rejection.
- Sleep packets provide stable candidate ids and evidence summaries for later
  review.

## Caveats

- Sleep packets may duplicate information already visible in other reports.
- Secret-like content blocks sleep planning rather than being copied into a
  packet.
- Secret scanning can reject generated sleep plan reports if future rendered
  fields contain secret-like text.
- This phase does not implement semantic compaction or automatic memory merges.

## Future Work

- Add mode-aware sleep planning thresholds.
- Add explicit `reviewed_by` metadata to sleep packets after human review.
- Add optional semantic clustering once recall and conflict fixtures justify it.
- If sleep plans become release artifacts, consider timestamped report paths for
  immutable review history.
