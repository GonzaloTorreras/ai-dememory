# ADR 0016: Manual Acceptance Evidence

## Status

Accepted for v2 draft.

## Context

The v2 release evidence command reports automated checks and lists manual
acceptance work that still requires human proof. Before this ADR, the tool could
not record that proof in a structured, reviewable way. That made release
readiness depend on PR comments or memory outside the vault, and it made manual
items look permanently incomplete even after a reviewer had run them.

Manual acceptance is still required for real MCP client usage, Obsidian vault
inspection, provider import review, daily maintenance inspection, and TestPyPI
publication. These checks cannot be honestly replaced by local unit tests.

## Decision

Add `ai-dememory acceptance`, backed by `scripts/manual_acceptance.py`.

The command supports:

- `ai-dememory acceptance list`
- `ai-dememory acceptance status --json`
- `ai-dememory acceptance verify --json`
- `ai-dememory acceptance record --item <id> --reviewed-by <name>
  --summary <text> [--artifact <path-or-url>]`

Evidence records are Markdown files under `inbox/release-acceptance/` with
frontmatter fields for `type`, `status`, `acceptance_item`, `reviewed_by`,
`reviewed_at`, `summary`, and `artifacts`.

`ai-dememory release-evidence` reads valid `passed` and `blocked` acceptance
records, separates completed manual acceptance from remaining manual acceptance,
and reports blocked attempts without marking them complete.
`ai-dememory acceptance verify` is the final read-only gate: it exits zero only
when every canonical manual acceptance item has reviewed passing evidence.

## Benefits

- Keeps manual release proof inside the reviewable vault workflow.
- Makes release evidence durable across PR comments and local sessions.
- Preserves the distinction between automated gates and human acceptance.
- Applies the existing secret scanner before writing evidence files.

## Limitations

- Evidence records prove that a reviewer recorded acceptance; they do not
  independently verify GUI actions or external PyPI configuration.
- Records are inbox artifacts. A maintainer must decide whether to commit them,
  archive them, or keep them local for a release handoff.
- The command does not run MCP clients, Docker, Obsidian, or publishing
  workflows.

## Future Risks

- Teams may need signed approvals or reviewer identity integration.
- Acceptance item ids must be updated when the release checklist changes.
- External artifacts may disappear if reviewers link to non-durable URLs.
- If release automation later consumes these records, status transitions need a
  stricter review model than append-only Markdown files.
