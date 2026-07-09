# ADR 0051: MCP Release Evidence

Status: Accepted for the v2 draft.

## Context

Release readiness is now summarized by `ai-dememory release-evidence --json`,
including `release_ready`, `release_blockers`, MCP inventory, publish guard
state, and manual acceptance planning. MCP clients and Codex plugin skills could
inspect individual readiness pieces, but they could not ask for the same final
handoff evidence without shelling out.

Plain memory vaults also run the MCP server, so a release-evidence MCP tool must
not assume every root is the distribution repository.

## Decision

Expose `memory.release_evidence` as a read-only MCP tool.

The tool accepts an optional `pr_url` and returns:

- `available=true` with the same evidence dictionary as
  `ai-dememory release-evidence --json` when the MCP root is a git distribution
  checkout
- `available=false`, a reason, and `evidence=null` when the MCP root is a plain
  vault

The tool does not write `reports/v2-release-evidence.md`, record manual
acceptance evidence, run publishing, merge PRs, or modify memory files.

ADR 0194 later adds `memory.release_evidence_report` for read-only Markdown
rendering with the same no-write boundary.

## Benefits

- Lets MCP clients and Codex plugin skills inspect the final release-readiness
  handoff without shell access.
- Preserves the distinction between distribution checkouts and user vaults.
- Reuses the same CLI release-evidence implementation, including
  `release_blockers` and `manual_acceptance_plan`.

## Limitations

- The tool is local-evidence only; it does not query GitHub CI, PyPI, TestPyPI,
  or real GUI MCP clients.
- It can be slower than small status tools because it runs the full local
  release-check set.
- In plain vaults it intentionally reports unavailable instead of fabricating
  release evidence.
- Markdown rendering is handled by `memory.release_evidence_report`, not this
  structured evidence tool.

## Future Risks

- If release evidence starts querying external services, the MCP tool will need
  explicit network, credential, and privacy boundaries.
- If release evidence writes artifacts by default in the future, this MCP tool
  must keep a read-only mode or be split into a separate side-effecting tool.
- If the distribution repo and vault layouts converge, the availability check
  may need a stronger profile detector than `git rev-parse`.

## Dependencies

- ADR 0033 defines the release readiness summary.
- ADR 0049 embeds manual acceptance planning in release evidence.
- ADR 0050 defines structured release blockers.
- ADR 0194 defines read-only MCP release evidence report rendering.
- `scripts/release_evidence.py` remains the canonical release evidence
  implementation.
