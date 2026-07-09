# ADR 0031: ADR Quality Guard

## Status

Accepted for v2 draft.

## Context

The v2 implementation is being delivered as a stack of small feature PRs, and
each material decision should remain traceable in an ADR. Existing ADRs already
capture rationale and tradeoffs, but the repository did not have an executable
check that every decision record keeps the expected structure.

The goal requires ADRs to track caveats, why a decision exists, limitations,
future risks, benefits, dependencies, and related context. That convention needs
to be guarded like the MCP inventory, PR template, and release checklist.

## Decision

Add `ai-dememory adr-guard`, backed by `scripts/adr_guard.py`.

The guard validates every Markdown file under `docs/adr/` for:

- `# ADR NNNN: Title`
- accepted or proposed status
- non-empty context and decision sections
- benefits or legacy consequences
- limitations, caveats, or deferred scope
- future risks, future work, or deferred scope

ADR 0031 and later must also include a non-empty `Dependencies` section. Earlier
ADRs keep their legacy headings so this guard avoids a noisy historical rewrite.

`release-check` and CI run the guard so structural drift fails before release.

## Dependencies

- `ai_dememory_tool.cli` exposes the guard as `ai-dememory adr-guard`.
- `scripts/release_check.py` imports `validate_adr_docs`.
- `.github/workflows/ci.yml` and `scripts/ci_guard.py` include the command.
- ADR files live under `docs/adr/` with zero-padded numeric filenames.

## Benefits

- Makes the ADR quality contract executable.
- Keeps future decision records consistent without requiring manual review of
  every heading.
- Preserves legacy ADR vocabulary while raising the standard for new ADRs.
- Lets release readiness fail when a new decision omits tradeoffs or
  dependencies.

## Limitations

- The guard validates structure, not the quality or correctness of a decision.
- Legacy ADRs may use `Consequences`, `Caveats`, `Future Work`, or `Deferred`
  instead of the newer section names.
- Dependencies are required only for ADR 0031 and later.

## Future Risks

- If ADR numbering changes, the filename parser will need to be updated.
- If the team later wants stricter historical consistency, old ADRs should be
  migrated in a dedicated documentation-only PR.
- If ADRs move to another directory or format, release-check and the guard must
  change together.
