# ADR 0194: MCP Release Evidence Report

Status: Accepted

## Context

`ai-dememory release-evidence` is the final local v2 release handoff. It
returns structured evidence with `--json` and can write
`reports/v2-release-evidence.md` with `--write-report`. MCP already exposed the
structured data through `memory.release_evidence`, but MCP clients could not
render the same Markdown handoff without shelling out or writing a generated
report file.

Manual acceptance and recall quality remain release blockers. Codex plugin and
MCP workflows need a readable packet that summarizes blockers and next actions,
while evidence recording, fixture promotion, publishing, and report writing stay
explicit user actions.

## Decision

Expose read-only MCP tool `memory.release_evidence_report`.

The tool accepts optional `pr_url`, uses the same `build_release_evidence` and
`render_markdown` path as the CLI, and returns:

- availability and reason fields;
- release readiness and blocker count when available;
- `mutates_system=false`;
- `records_evidence=false`;
- `writes_files=false`;
- `report_path=null`; and
- rendered Markdown when the MCP root is the distribution checkout.

Plain vault roots return `available=false`, no Markdown, and a distribution
checkout explanation. The rendered Markdown is secret-scanned before return.
The MCP tool does not write `reports/v2-release-evidence.md`, does not record
manual acceptance, does not promote recall fixtures, and does not publish
packages.

## Benefits

- MCP clients can show the same release handoff as the CLI without shelling out.
- The report renderer stays shared between CLI and MCP surfaces.
- Plain vault behavior remains bounded and non-fatal.
- Runtime and unit tests cover both unavailable plain-vault behavior and
  distribution checkout rendering.

## Limitations

- The report is not release evidence by itself; it summarizes evidence that has
  already been recorded elsewhere.
- It does not make the release ready while manual acceptance or recall review
  blockers remain.
- It depends on the local git checkout for branch, HEAD, and cleanliness data.

## Future Work

- Add pagination or section filters if the Markdown report becomes too large
  for practical MCP clients.
- Add optional signed release evidence once reviewer identity requirements are
  stronger than local Markdown records.
- Revisit whether generated report archives are needed after the first real
  TestPyPI/PyPI release cycle.

## Dependencies

- ADR 0013 defines the v2 release evidence report.
- ADR 0051 exposes structured release evidence over MCP.
- ADR 0109 defines graceful unavailable behavior when git is missing.
- ADR 0118 defines release evidence report path and secret-scan guards.
- ADR 0185 defines the setup health summary embedded in release evidence.
- `scripts/release_evidence.py` owns evidence assembly and Markdown rendering.
- `mcp/server/memory_mcp.py` exposes the read-only MCP report renderer.
