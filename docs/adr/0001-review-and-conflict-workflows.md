# ADR 0001: Review Suppressions And Conflict Proposals

Status: Accepted

Date: 2026-06-19

## Context

The memory vault needs a way to handle secret-scan false positives and duplicate
or conflicting memories without letting automation rewrite durable memory. The
same workflow must be usable from CLI, MCP, package installs, and generated vault
templates.

## Decision

Review state is stored in `.ai-dememory-ignore.toml` using deterministic
finding ids:

- `false_positives.fp_<hash>` for reviewed secret-scan false positives.
- `conflicts.conf_<hash>` for reviewed memory conflict candidates.

Generated reports live under `reports/`. False-positive, conflict, and
consolidation reports can use `--report-path` for another generated path, but
report paths must resolve inside the memory root and rendered output is
secret-scanned before writing. Conflict merge proposals live under
`inbox/conflict-resolution/`. CLI and MCP write operations may update only
those review artifacts; canonical memory changes remain manual.

## Consequences

- Review decisions are auditable and versionable without editing canonical
  memory documents.
- Reports can be regenerated from Markdown and the ignore file.
- Conflict resolution stays conservative: the tool can propose a merge but does
  not decide which durable facts should survive.
- Finding ids can change if the underlying redacted finding or conflict
  membership changes, so old suppressions should be periodically reviewed.
- Secret scanning can reject generated review reports if future rendered fields
  contain secret-like text.

## Deferred

Semantic contradiction detection, LLM-assisted merge drafting, and vector-based
near-duplicate discovery are deferred until recall and conflict fixtures show
they are needed.

## Future Risks

- If review reports become release artifacts, they may need timestamped paths for
  immutable review history.
