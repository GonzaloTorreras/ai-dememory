# ADR 0037: MCP Durable Provenance Status

## Status

Accepted for v2 draft.

## Context

ADR 0015 made durable memory provenance executable: durable memories require
`reviewed: true`, `reviewed_by`, and `reviewed_at`, and
`ai-dememory provenance` reports any gaps. That CLI command is part of release
readiness because durable memory should not ship without human review metadata.

MCP clients already expose read-only release readiness through manual acceptance
tools, recall fixture freshness, and vector readiness. They still could not ask
whether durable memory provenance was clean without shelling out.

## Decision

Expose `memory.provenance_status` as a read-only MCP tool.

The tool runs the same durable provenance audit as the CLI and returns:

- generation timestamp
- durable memory count
- issue count
- issue details with path, memory id, field, and message

The tool does not write `reports/durable-provenance.md`, does not mutate
frontmatter, and does not record manual acceptance evidence.

## Benefits

- Lets MCP clients and plugin skills report durable provenance readiness.
- Keeps durable review metadata visible alongside manual acceptance and other
  release status tools.
- Reuses the existing CLI audit rules instead of duplicating provenance logic.
- Preserves the boundary that durable memory changes still require explicit
  human review and Git history.

## Limitations

- The tool only audits metadata presence and date shape; it cannot prove the
  reviewer actually inspected the memory content.
- It does not write a Markdown report; use `ai-dememory provenance
  --write-report` for file-based release evidence.
- Non-durable memories may still need review, but this audit intentionally
  checks the stricter durable contract.

## Future Risks

- If reviewer identity needs signatures or external identity providers, the
  audit schema will need stronger proof fields.
- If teams add multiple durable memory owners, issue records may need owner and
  escalation metadata.
- If manual acceptance moves to an external system, provenance and acceptance
  status may need a shared evidence model.

## Dependencies

- Depends on ADR 0015 for the durable provenance audit contract.
- Depends on `scripts/durable_provenance.py` remaining the shared CLI/MCP audit
  implementation.
- Depends on MCP inventory and runtime smoke checks to keep the documented tool
  surface current.
