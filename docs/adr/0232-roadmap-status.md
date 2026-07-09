# ADR 0232: Roadmap Status

## Status

Accepted

## Context

The v2 continuation plan spans multiple operational phases: context assembly,
working memory, lifecycle feedback, review workflows, sleep consolidation,
hooks, importers, git lessons, and vector gating. Most phases now have CLI,
MCP, documentation, tests, and ADR evidence, but the current state is spread
across many files.

Without a compact status command, future continuation work can accidentally
re-plan completed phases or miss the distinction between implemented, manual,
and intentionally gated work.

## Decision

Add `ai-dememory roadmap status`, backed by `scripts/roadmap_status.py`.

The command is read-only and reports one status row per roadmap phase. Each row
uses representative evidence paths to determine whether the phase has current
implementation evidence. The optional vector-search phase reports `gated` when
its measured recall gate exists, because embeddings are intentionally disabled
until reviewed recall failures justify a separate experiment.

CI and reviewer templates include `python3 scripts/ai_dememory.py roadmap
status --json` as a lightweight drift check.

## Consequences

- Continuation work gets a concise, machine-readable v2 roadmap map.
- Release handoffs can distinguish implemented features from intentionally
  gated vector-search activation.
- Missing phase evidence becomes visible in CI and release checks.
- The command stays cheap enough to run in every PR.

## Limitations

- Evidence paths prove that representative implementation artifacts exist, not
  that every behavior is semantically correct.
- The command does not run the underlying smoke tests.
- Manual acceptance and recall fixture freshness remain separate release
  blockers.

## Future Work

- Add MCP exposure only if clients need roadmap status inside the tool surface.
- Include PR links or ADR ranges if release handoffs need richer provenance.
- Add per-phase test counts only if the test suite becomes easier to query by
  feature area.

## Dependencies

- ADR 0019 defines CI workflow guard coverage.
- ADR 0023 defines pull request template validation.
- ADR 0032 defines release checklist validation.
- ADR 0231 defines draft PR handoff validation.
- `scripts/release_check.py` owns non-runtime release readiness aggregation.

## References

- `scripts/roadmap_status.py`
- `docs/roadmap-status.md`
- `.github/workflows/ci.yml`
- `.github/pull_request_template.md`
- `tests/test_memory_tools.py`
