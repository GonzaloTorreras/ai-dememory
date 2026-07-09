# ADR 0033: Release Evidence Readiness Summary

## Status

Accepted for v2 draft.

## Context

`ai-dememory release-evidence` already records release-check rows, MCP
inventory counts, publish guard issues, and manual acceptance arrays. Reviewers
still had to infer whether the evidence was release-ready by counting automated
warnings/failures and checking whether manual acceptance remained.

The final v2 handoff should make that state explicit without changing the
existing boundary: automated evidence is summarized, but manual acceptance still
requires reviewed human proof.

## Decision

Extend release evidence with:

- `automated_summary`: counts of `ok`, `warn`, `fail`, and total release-check
  rows.
- `manual_acceptance_total`: the canonical number of manual acceptance items.
- `release_ready`: true only when the worktree is clean, automated checks have
  no warnings or failures, and no manual acceptance items remain.
- `release_blockers`: the structured reasons `release_ready` is false.
- `manual_acceptance_plan`: a read-only next-action plan for remaining and
  blocked manual acceptance work.

The Markdown report renders these values near the top of the evidence output so
PR comments and local handoffs show the readiness status directly.

`--strict` exits nonzero unless `release_ready` is true. This is a final local
handoff gate, not a CI gate for draft PRs where manual acceptance is expected to
remain incomplete.

## Dependencies

- `scripts/release_evidence.py` computes summaries from `run_release_checks`
  and `acceptance_status`.
- `scripts/manual_acceptance.py` remains the source of truth for manual
  acceptance items and planning.
- `scripts/release_check.py` remains the source of truth for automated check
  rows.
- `tests/test_memory_tools.py` asserts the JSON and Markdown shapes.
- `docs/release-v2-checklist.md` lists the strict handoff command.

## Benefits

- Makes release evidence easier to inspect without custom JSON processing.
- Avoids treating incomplete manual acceptance as release-ready.
- Keeps blocked manual evidence visible while preserving the separate
  completion rule.
- Gives PR validation comments a stable summary field to cite.
- Gives automation a single blocker list instead of requiring it to infer
  readiness failures from several fields.

## Limitations

- `release_ready` is a summary of local evidence, not a replacement for GitHub
  CI status, TestPyPI configuration, or real MCP client testing.
- Warnings make `release_ready` false, so local runs without
  `AI_DEMEMORY_PR_URL` remain not ready until PR-gated checks run.
- The field can become stale if generated before later commits.

## Future Risks

- If release-check gains severity levels beyond ok/warn/fail, the summary shape
  will need to expand.
- If manual acceptance moves outside Markdown records, the readiness rule must
  follow the new source of truth.
- If GitHub check-run status becomes part of release evidence, `release_ready`
  should include that external state explicitly.
