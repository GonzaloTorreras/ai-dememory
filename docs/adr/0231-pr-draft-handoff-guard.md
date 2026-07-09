# ADR 0231: Draft PR Handoff Guard

## Status

Accepted

## Context

`docs/pr-draft.md` was being used as a PR handoff note, but it had drifted into
a historical artifact: it referenced an old pull request URL, an old title, and
a completed review state. That made it unsafe as a reusable guide for the
current stacked draft PR workflow.

The existing PR template guard validates reviewer checklist coverage, but it
does not validate the separate draft PR handoff runbook.

## Decision

Add `ai-dememory pr-draft-guard`, backed by `scripts/pr_draft_guard.py`, and
run it from CI and `ai-dememory release-check`.

The guard checks that `docs/pr-draft.md` keeps reusable draft handoff sections,
including required fields, body template, validation commands, safety notes,
and post-creation steps. It also rejects stale PR-specific text such as old PR
URLs, the original MVP title, and language that claims a draft PR is already
published or ready.

## Consequences

- Draft PR handoffs stay aligned with the current stacked draft workflow.
- Release readiness fails if the handoff is overwritten with one-off PR state.
- The PR template and release checklist now mention the draft handoff guard as
  part of normal validation.

## Limitations

- The guard is text-based and validates snippets, not the semantic correctness
  of a specific future PR body.
- It cannot prove a draft PR was opened, updated, or kept in draft.
- It intentionally allows placeholder PR URLs so the runbook remains reusable.

## Future Work

- Generate draft PR bodies from a checked template if handoff text needs more
  structure.
- Add GitHub API validation only if PR metadata drift becomes a recurring
  release risk.
- Keep the guard focused on stale handoff prevention, not complete PR review
  automation.

## Dependencies

- ADR 0019 defines CI workflow guard coverage.
- ADR 0023 defines pull request template validation.
- ADR 0032 defines release checklist validation.
- ADR 0107 defines PR-gated MCP runtime smoke.
- ADR 0230 defines the latest stacked draft PR release smoke workflow.

## References

- `docs/pr-draft.md`
- `scripts/pr_draft_guard.py`
- `.github/workflows/ci.yml`
- `scripts/release_check.py`
- `tests/test_memory_tools.py`
