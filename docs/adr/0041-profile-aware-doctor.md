# ADR 0041: Profile-Aware Doctor

## Status

Accepted for the v2 draft.

## Context

The install and vault-creation docs say a fresh `ai-dememory` vault should pass
`ai-dememory doctor` with only a missing-index warning before the first index
build. In practice, the doctor command also tried to validate MCP server source
files. That check is valid in the tool distribution checkout, but a private
memory vault intentionally does not contain `mcp/server/memory_mcp.py`.

The same issue affects MCP `memory.doctor` when the server is launched against a
vault root.

## Decision

Make doctor checks profile-aware:

- vault roots are detected by `.ai-dememory.toml`;
- distribution roots are detected by `scripts/ai_dememory.py` and
  `mcp/server/memory_mcp.py`;
- all roots still run repository shape, SQLite FTS5, schema, secret scan, and
  index checks;
- only distribution roots run MCP contract definition validation.

Warnings remain non-fatal. A fresh vault therefore reports the expected
missing-index warning without failing on distribution-only MCP source files.

## Benefits

- Aligns doctor behavior with documented first-run vault setup.
- Keeps package install and Docker smoke useful for fresh vaults.
- Preserves MCP contract validation in the distribution checkout.

## Limitations

- The profile detection is intentionally simple and file-based.
- A custom checkout missing both profile markers may still fail the repository
  shape check.
- Vault doctor does not prove that the installed package's MCP server is valid;
  distribution CI and release checks continue to cover that.

## Future Risks

- If vault templates change marker files, profile detection must be updated.
- If users keep distribution code and vault data in one repo, doctor will run
  the broader distribution profile.
- Future remote or registry packaging may need a third diagnostic profile.

## Dependencies

- ADR 0011 requires reusable install smoke to cover fresh vault setup.
- ADR 0018 expands install smoke command coverage for package installs.
- ADR 0040 exposes doctor output over MCP and depends on these profile
  semantics.
