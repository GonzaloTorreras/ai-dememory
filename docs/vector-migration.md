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

It must also freeze the machine-readable `retrieval-benchmark-v1` contract
(`contract_name=retrieval-benchmark`, `schema_version=1`) before `GATE-B`. The
id payload is compact UTF-8 JSON with sorted keys containing the exact query
code points, sorted expected ids, scope, and immutable provenance id, but no
`case_id` or mutable review timestamps. Its id is `ret_` plus the first 20 hex
characters of the payload SHA-256; the corpus digest hashes the full case
records in case-id order joined by LF. The contract pairs every candidate result
with an FTS result for the same case id, reviewed
expected ids, corpus SHA-256, policy/config digest, host, and final
context-hydration path. Case recall is the fraction of expected ids in the first
ten final hydrated items; primary macro `Recall@10` is its unweighted case mean.
`MRR@10` is the secondary unweighted mean reciprocal rank and uses zero when no
expected id appears in the first ten items.

Each arm receives one full-corpus warm-up, excluded from results, and five
measured paired repetitions with alternating arm order. The 95% confidence
interval is a 10,000-resample paired percentile bootstrap over per-case mean
candidate-minus-FTS recall deltas with seed `20260827`; cases use case-id order,
portable sample indices come from the first eight bytes of
`SHA-256(seed || ":" || replicate || ":" || draw)` modulo the case count. The
nearest-rank 2.5th and 97.5th bootstrap values are the interval endpoints. The
result records exact source/dependency/candidate identity, nearest-rank p50/p95
end-to-end latency, 50 ms process-tree RSS samples and peak, errors, lock
failures, index bytes, rebuild duration, and policy/provenance/sensitive-data
violation counts. Failed attempts score zero quality and remain counted as
errors; a missing field or mismatched digest invalidates the run.

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

On one valid `retrieval-benchmark-v1` run, every candidate gate must pass:

- macro `Recall@10` gains at least `0.05` (five absolute percentage points) over
  FTS and the lower bound of its 95% paired bootstrap interval is greater than
  zero;
- candidate p95 end-to-end latency is at most 120% of FTS p95 and peak aggregate
  process-tree RSS is at most 125% of FTS;
- candidate attempts ending in an error or lock failure are at most 1% of its
  measured attempts; an FTS control rate above 1% invalidates the comparison;
- candidate `MRR@10` loses no more than `0.01` (one absolute point on `[0,1]`);
  and
- policy, provenance, and sensitive-data violations are all zero.

These thresholds are the version-one experiment gate, not runtime defaults or
permission to implement or enable a candidate before `RET-001`, `GATE-B`,
`GRF-001`, and `RET-002` reach their own review boundaries. Passing permits a
production-design review only. Index size, rebuild duration, packaging, and
maintenance cost remain mandatory report fields, not unstated numeric gates.

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
- macro `Recall@10` gain below `0.05`, or its lower 95% paired-bootstrap bound
  is not greater than zero;
- train/test leakage, missing expected targets, or disappearing unresolved
  challenges;
- any policy, provenance, or sensitive-data violation;
- candidate p95 latency above 120% of FTS, peak RSS above 125%, error-or-lock
  rate above 1%, invalid FTS control, or `MRR@10` loss greater than `0.01`;
- a vector-only candidate is discarded by final context hydration;
- the experiment requires a background daemon or makes Node/model downloads a
  headless installation dependency.

Failure rejects and removes the generated shadow candidate state; production
FTS remains unchanged. This is not a production rollback because no v1
experiment is allowed to alter production ranking.
