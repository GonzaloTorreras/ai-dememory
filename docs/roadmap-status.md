# Roadmap Status

`ai-dememory roadmap status` reports the implementation state of the v2
operational memory roadmap. It is a read-only inspection command intended for
release handoffs and continuation work.

Run:

```bash
ai-dememory roadmap status
ai-dememory roadmap status --json
python3 scripts/ai_dememory.py roadmap status --json
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
exists. That means the measured vector gate is implemented, not that embeddings
are enabled. Embeddings remain disabled until reviewed recall failures justify a
separate experiment.

The normative future order is
`docs/v3-hybrid-visual-multiplatform-roadmap.md` plus
`contracts/planning/v3-execution-sequence.json`. `PLAN.md` and
`docs/shared-memory-governance-roadmap.md` retain useful R0-R7/P0-P6 research,
but are non-executable appendices and cannot advance a task or gate. They remain
separate because `ai-dememory roadmap status` reports current v2 implementation
evidence, not future work.

The command does not replace release gates. `release-check`,
`release-evidence`, manual acceptance, recall fixture freshness, and CI remain
the authoritative v2 release signals.
