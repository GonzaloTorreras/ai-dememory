# ADR 0013: v2 Release Evidence Report

## Status

Accepted for v2 draft.

## Context

The v2 release checklist mixes automated gates, generated artifacts, and manual
acceptance. Individual checks can pass while the overall release remains
unproven because real MCP client acceptance, TestPyPI configuration, and manual
review steps still require human evidence.

Reviewers need one command that summarizes the current automated state without
pretending to complete manual acceptance.

## Decision

Add `ai-dememory release-evidence`, backed by `scripts/release_evidence.py`.

The command records:

- current branch and short commit
- whether the worktree is clean
- optional PR URL
- `release-check` results
- automated ok/warn/fail summary counts and `release_ready`
- MCP tool, prompt, and resource-template inventory
- publish guard and MCP inventory documentation issue counts
- manual acceptance total count
- completed manual acceptance items
- blocked manual acceptance evidence with reviewer, date, summary, and path
- manual acceptance items that still need passing human evidence

With `--write-report`, it writes `reports/v2-release-evidence.md` by default.
`--report-path` can select another generated report path inside the memory
root. The rendered report is secret-scanned before writing, and paths outside
the root are rejected.

## Benefits

- Gives reviewers a compact v2 readiness snapshot.
- Separates automated evidence from manual acceptance instead of conflating
  them.
- Distinguishes missing manual acceptance from reviewed blockers.
- Makes final release review easier to attach to a PR or local handoff.
- Keeps generated evidence outside canonical memory unless explicitly written.
- Allows custom in-root generated report paths for local handoff workflows.

## Limitations

- It summarizes checks; it does not run the expensive install smoke or Docker
  smoke itself.
- It cannot prove external PyPI/TestPyPI trusted publisher configuration.
- It cannot replace real MCP client testing or human review of generated inbox
  artifacts.
- Custom report paths are still generated artifacts and must not be staged as
  canonical memory.

## Future Risks

- The report can become stale if generated before later commits.
- Manual acceptance item names must be maintained as release scope changes.
- If report content grows to include new user-provided fields, rendered secret
  scanning must continue to cover the final Markdown output.
- Future remote MCP, registry, or Cloud Build distribution paths would require
  new evidence sections.
