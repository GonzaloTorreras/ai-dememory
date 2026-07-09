# ADR 0003: Lifecycle Scoring And Generated State Preservation

Status: Accepted

Date: 2026-06-19

## Context

`ai-dememory` uses Markdown as canonical memory and SQLite as a generated index.
The v2 operational loop records retrievals and usefulness outcomes in SQLite so
search can learn from real use. A full index rebuild previously replaced the
SQLite database and lost that generated feedback.

## Decision

Index rebuild now preserves generated lifecycle tables for current memories:

- `retrieval_log`
- `memory_lifecycle`
- `memory_outcomes`
- `consolidation_log`

`ai-dememory lifecycle scores` computes deterministic lifecycle scores from
retrieval count, positive/negative outcomes, reward factor, confidence, recency,
pin state, and review-due status. `ai-dememory lifecycle report` writes a human
review report. `--report-path` can choose a generated report path, but the path
must resolve inside the memory root and the final rendered Markdown is
secret-scanned before writing. `memory.lifecycle_scores` exposes the same data
as a read-only MCP tool.

## Consequences

- Daily and weekly maintenance can rebuild the index without erasing outcome
  feedback.
- `indexes/memory-weights.json` can include lifecycle score and recommendation
  fields.
- SQLite remains generated and disposable, but lifecycle state now has a
  preservation path across normal rebuilds.

## Caveats

- Lifecycle state is still not canonical Markdown. Deleting `indexes/` deletes
  lifecycle history.
- State for memories removed from Markdown is filtered out during rebuild.
- The score formula is intentionally simple and explainable; it is not a
  statistical relevance model.
- Secret scanning can reject a generated lifecycle report if future rendered
  fields contain secret-like text.

## Future Work

- Export lifecycle snapshots to a reviewable Markdown or JSON backup if users
  want stronger durability.
- Calibrate score weights against recall fixtures and real negative outcomes.
- Add lifecycle trends to weekly maintenance reports.
- If lifecycle reports become release artifacts, consider timestamped report
  paths for immutable history.
