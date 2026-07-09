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

The next strategic roadmap is `PLAN.md`. It defines the R0-R7 future direction:
productization and plan integrity, local shared-memory policy, adversarial
evaluation, traceability, supersession, quarantine, read-only governance
surfaces, and gated super search. The detailed governance appendix remains in
`docs/shared-memory-governance-roadmap.md`. These future plans are intentionally
documented separately because `ai-dememory roadmap status` reports current v2
implementation evidence, not future work.

The command does not replace release gates. `release-check`,
`release-evidence`, manual acceptance, recall fixture freshness, and CI remain
the authoritative v2 release signals.
