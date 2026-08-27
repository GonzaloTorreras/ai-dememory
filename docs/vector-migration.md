# Future Vector Migration

Status: non-executable research note. Do not implement vectors for the current
runtime. Markdown remains canonical and SQLite FTS plus reviewed metadata remain
the production retrieval baseline.

Normative ownership lives in the
[V3 roadmap](v3-hybrid-visual-multiplatform-roadmap.md) and
[`contracts/planning/v3-execution-sequence.json`](../contracts/planning/v3-execution-sequence.json):

1. `RET-001` repairs recall evaluation before `GATE-B`.
2. `GRF-001` versions the graph projection after `GATE-B`.
3. `RET-002` may then compare bounded retrieval candidates in shadow mode.

The [proposal validation handoff](proposal-validation-handoff.md) records why
this sequence changed.

## Current gate limitation

The existing commands remain useful descriptions of the current regression set:

```bash
ai-dememory vector status --json
ai-dememory vector status --write-report
ai-dememory vector status --write-report --report-path reports/vector-readiness.md
```

Today, the default report uses recall below `0.85` and at least two failing
regression cases to describe `eligible_for_vector_experiment`. That result must
not authorize implementation: `recall-fixtures promote-miss` accepts a fixture
only when it already passes and rolls back otherwise. Passing regressions
therefore protect solved behavior but cannot represent unresolved reviewed
misses. The evaluator also validates that expected ids are non-empty without
first proving that each id/path exists in canonical memory.

`RET-001` must separate these roles:

- a passing regression corpus protects behavior that already works;
- a held-out challenge corpus preserves reviewed unresolved misses;
- every expected id/path is validated against canonical Markdown;
- both corpora have stable case ids, provenance, hashes, and leakage checks;
- invalid, unknown, and unresolved cases remain distinguishable.

No vector readiness conclusion is trustworthy until that evidence boundary is
implemented and reproducible.

## Experiment trigger

After `GATE-B` and `GRF-001`, `RET-002` may open an opt-in experiment only when:

- at least 100 reviewed held-out cases exist without train/test leakage;
- important misses repeatedly involve different vocabulary after aliases,
  metadata, and deterministic query/fuzzy variants have been considered;
- evaluation includes final context hydration, not only search candidates;
- privacy, provenance, rollback, index rebuild, model identity, dimension,
  latency, peak RSS, disk growth, and maintenance cost are measured;
- a real external consumer reads back the experimental behavior.

The minimum improvement proposal is five recall points over the frozen FTS
control with no sensitive-data, precision, provenance, p95, or RSS regression.
Meeting that threshold permits a design review, not default activation.

## Candidate comparison, not backend selection

`RET-002` should compare the smallest useful sequence:

1. current FTS and metadata scoring as control;
2. one shared deterministic Unicode normalization/tokenization candidate,
   exercised through search, turn keywords, and final hydration;
3. deterministic fuzzy and reviewed alias/query variants;
4. bounded one-hop candidates from the versioned graph projection;
5. optionally, one local multilingual embedding candidate;
6. optionally, reciprocal-rank fusion of candidates above.

Do not preselect a vector database, model, fixed score weights, or provider in
this document. Backend choice follows measured corpus size and host constraints.
No model call or embedding dependency belongs in the default package merely to
run the comparison.

## Data and policy contract

- Embeddings and vector indexes are generated, disposable artifacts keyed by
  canonical `memory_id` and an explicit model/version identity.
- They must rebuild from permitted Markdown without becoming canonical memory.
- `secret-prohibited` content remains excluded; private/sensitive processing
  requires an explicit reviewed local policy.
- Policy filtering happens before any optional external reviewer or provider.
- Vector candidates augment the FTS control; they cannot bypass scope, project,
  sensitivity, lifecycle, provenance, review, or final hydration checks.
- Shadow reports are bounded, secret-scanned, and off by default.
- FTS remains the deterministic fallback and production baseline until a later
  reviewed task explicitly changes that contract.

## Stop and rollback gates

Do not proceed, or return to unchanged FTS, when any of these is true:

- fewer than 100 reviewed held-out cases;
- less than a five-point gain over the frozen control;
- train/test leakage, missing expected targets, or disappearing unresolved
  challenges;
- any sensitive-data, policy, provenance, or explainability regression;
- an unacceptable p95, RSS, disk, rebuild, packaging, or maintenance cost;
- a vector-only candidate is discarded by final context hydration;
- the experiment requires a background daemon or makes Node/model downloads a
  headless installation dependency.
