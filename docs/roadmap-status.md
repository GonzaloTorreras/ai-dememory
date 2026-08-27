# Roadmap Status

`ai-dememory roadmap status` reports the implementation state of the v2
operational memory roadmap. It is a read-only inspection command intended for
release handoffs and continuation work.

Run:

```bash
ai-dememory roadmap status
ai-dememory roadmap status --json
```

The command checks for representative evidence files for each phase:

- v2 baseline gates and smoke tests
- token-budgeted context and explainable search
- working memory and handoffs
- lifecycle scoring and outcomes
- false-positive and conflict review
- configurable review modes
- safe sleep consolidation
- Codex and Claude hooks
- importers and capture
- git lesson capture
- optional vector search

Output includes:

- `mutates_files=false`
- `writes_files=false`
- phase status counts
- evidence paths
- missing evidence, if any
- next actions

The vector-search phase is intentionally reported as `gated` when its evidence
exists. That means the descriptive v2 status calculation is implemented, not
that embeddings are enabled or vector work is authorized. Its current input is
a passing regression set: only solved misses can be promoted, while unresolved
reviewed misses have no held-out representation yet.

The normative future order is
`docs/v3-hybrid-visual-multiplatform-roadmap.md` plus
`contracts/planning/v3-execution-sequence.json`. `PLAN.md` and
`docs/shared-memory-governance-roadmap.md` retain useful R0-R7/P0-P6 research,
but are non-executable appendices and cannot advance a task or gate. They remain
separate because `ai-dememory roadmap status` reports current v2 implementation
evidence, not future work.

The normative future retrieval sequence is `RET-001` -> `GATE-B` -> `GRF-001`
-> shadow-only `RET-002` -> production-design gate `RET-003`. `RET-001` must
first separate passing regressions from reviewed held-out challenges;
`RET-002` may only compare bounded retrieval candidates after the compatibility
and graph-contract gates, and cannot authorize production ranking changes.

The command does not replace release gates. `release-check`,
`release-evidence`, manual acceptance, recall fixture freshness, and CI remain
the authoritative v2 release signals.
