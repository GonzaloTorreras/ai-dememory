# ADR 0015: Durable Provenance Audit

## Status

Accepted for v2 draft.

## Context

Durable memories represent stable facts, preferences, policies, and long-lived
decisions. Earlier v2 work made `reviewed: true`, `reviewed_by`, and
`reviewed_at` required for durable memory validation, but release review still
needed an explicit audit command to summarize durable provenance state.

The MCP gap analysis previously listed reviewer/audit fields beyond
`reviewed: true` as an unresolved decision.

## Decision

Keep the durable provenance contract as:

- `reviewed: true`
- `reviewed_by`
- `reviewed_at`

Add `ai-dememory provenance`, backed by `scripts/durable_provenance.py`, to
audit durable memories and optionally write `reports/durable-provenance.md`.
When `--write-report` is used, `--report-path` may choose another generated
report path, but it must resolve inside the memory root. The final rendered
Markdown is secret-scanned before writing.

The command is read-only unless `--write-report` is used. Missing provenance is
reported per file, memory id, and field. The command exits non-zero when issues
exist.

## Benefits

- Makes durable provenance review explicit and repeatable.
- Gives release reviewers a focused audit separate from full schema validation.
- Keeps human approval metadata visible before publishing v2.
- Avoids adding a heavier promotion workflow while durable writes remain manual.

## Limitations

- The audit verifies metadata presence and date shape, not the truth of the
  reviewer's identity.
- It does not promote, rewrite, or archive memories.
- It does not replace manual review of proposed captures before promotion.
- Secret scanning can reject a generated report if future rendered fields
  contain secret-like text.

## Future Risks

- Larger teams may need stronger reviewer identity, signatures, or approval ids.
- If durable promotion becomes tool-assisted, the audit should verify promotion
  logs as well as frontmatter.
- Multi-vault usage may need organization-specific reviewer policy checks.
- If provenance reports become release artifacts, they may need immutable,
  timestamped output paths rather than the current generated default.
