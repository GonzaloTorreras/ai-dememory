# ADR 0032: Release Checklist Guard

## Status

Accepted for v2 draft.

## Context

The v2 release checklist is the human-facing map for repository state, static
checks, package smoke, Docker smoke, publishing, generated artifacts, MCP
runtime smoke, security review, and manual acceptance. Several individual
surfaces already have guards, but the checklist itself could drift when new
release gates are added.

The checklist should remain reviewable by humans and enforceable by automation.
Without a dedicated guard, a new gate can be wired into CI and release-check
while still being absent from the release checklist used for final acceptance.

## Decision

Add `ai-dememory release-checklist-guard`, backed by
`scripts/release_checklist_guard.py`.

The guard validates that `docs/release-v2-checklist.md` keeps the expected
release sections and important command snippets for static checks, package
install smoke, Docker local MCP smoke, publishing, generated artifacts, MCP
runtime smoke, security review, and manual acceptance.

`release-check`, CI, and the PR template run or list the guard so checklist
drift is visible before a release handoff.

## Dependencies

- `ai_dememory_tool.cli` exposes the guard as
  `ai-dememory release-checklist-guard`.
- `scripts/release_check.py` imports `validate_release_checklist`.
- `.github/workflows/ci.yml`, `scripts/ci_guard.py`, and
  `scripts/pr_template_guard.py` list the guard.
- The release checklist remains at `docs/release-v2-checklist.md`.

## Benefits

- Keeps the final human checklist aligned with executable release gates.
- Prevents new validation commands from being hidden in CI only.
- Complements `acceptance-guard`, which checks only manual acceptance items.
- Makes release readiness easier to audit from a single document.

## Limitations

- The guard checks required headings and snippets, not whether each checklist
  item has been manually completed.
- It intentionally does not replace specialized guards for CI, PR template,
  acceptance items, artifacts, publishing, or ADR structure.
- It validates text presence; wording around a snippet can still become stale.

## Future Risks

- If the checklist is generated in the future, this guard should validate the
  generator inputs instead of the rendered Markdown.
- If release gates become platform-specific, required snippets may need
  profiles instead of a single canonical list.
- If the checklist becomes too long, the guard may need to validate grouped
  evidence links rather than individual commands.
