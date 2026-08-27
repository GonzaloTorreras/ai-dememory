# Proposal Validation Handoff

Status: non-executable research and planning handoff. This document records a
workspace-grounded review of an external repository assessment. It is not a
runtime specification, completion claim, release checklist, or second backlog.
Executable order and state live only in the
[V3 roadmap](v3-hybrid-visual-multiplatform-roadmap.md) and
[`contracts/planning/**`](../contracts/planning/).

## Executive decision

The assessment contains useful pressure tests, but its proposed solution is too
broad and several premises do not match the current source. The correct response
is to repair evidence quality and exact inventories before introducing retrieval
algorithms:

```text
BRG-003
  -> BRG-019 exact bridge/MCP inventory and budgets
  -> MIG-001 complete writer/format/locking inventory
  -> RET-001 truth-preserving recall evaluation
  -> GATE-B external compatibility evidence
       |-> GRF-001 versioned graph projection -> RET-002 shadow comparison
       `-> OBS-001 -> OUT-001 -> CON-001 -> MEM-001
```

Python remains the headless and policy authority. Markdown remains canonical;
SQLite, graph data, reports, and any future vector projection remain generated
and disposable. Review fatigue is addressed through bounded queues,
deduplication, deterministic grouping, and better review packets, never by
confidence-based mutation of canonical memory.

## Validation method and baseline

The supplied assessment was treated as an untrusted hypothesis list. Claims
were checked against current source, tests, generated inventory, and documented
contracts in this workspace. No copied checkout, generated index, private vault,
or pasted command output becomes planning evidence merely because it appears in
the assessment.

The strongest workspace anchors are:

- graph construction and pagination:
  [`scripts/graph_memory.py`](../scripts/graph_memory.py) and
  [`docs/memory-graph.md`](memory-graph.md);
- recall fixtures, evaluation, and context hydration:
  [`scripts/recall_fixtures.py`](../scripts/recall_fixtures.py),
  [`scripts/eval_recall.py`](../scripts/eval_recall.py), and
  [`scripts/context_memory.py`](../scripts/context_memory.py);
- accepted Markdown parsing and index rebuild:
  [`scripts/memorylib.py`](../scripts/memorylib.py),
  [`scripts/index_memory.py`](../scripts/index_memory.py), and
  [`docs/schema.md`](schema.md);
- MCP profiles and generated schema measurements:
  [`ai_dememory_tool/mcp_profiles.py`](../ai_dememory_tool/mcp_profiles.py),
  [`mcp/server/memory_mcp.py`](../mcp/server/memory_mcp.py), and
  [`scripts/mcp_inventory.py`](../scripts/mcp_inventory.py);
- review and writer behavior:
  [`scripts/review_memory.py`](../scripts/review_memory.py) and the integrated
  [`tests/test_memory_tools.py`](../tests/test_memory_tools.py).

A fresh `scripts/mcp_inventory.py --json` snapshot on this source reports:

| Profile | Tools | Schema bytes | Estimated schema tokens |
| --- | ---: | ---: | ---: |
| `public` | 3 | 3,347 | 837 |
| `core` | 4 | 3,904 | 976 |
| `working` | 11 | 9,062 | 2,266 |
| `review` | 44 | 49,798 | 12,450 |
| `admin` | 74 | 81,234 | 20,309 |

These values are a source snapshot, not permanent product constants. `BRG-019`
must turn profile budgets and documentation drift into generated, checked
contracts rather than requiring hand-maintained numbers.

## Claim disposition

### Confirmed findings

| Area | Confirmed issue | Consequence | Owner |
| --- | --- | --- | --- |
| Recall evidence | `promote_miss_to_fixture()` rolls back unless the promoted fixture already passes, while vector readiness consumes the passing regression set. An unresolved reviewed miss therefore cannot remain in the corpus used to justify a retrieval experiment. | A green regression set can coexist with unrepresented real misses; vector eligibility is not truth-preserving. | `RET-001` |
| Recall identity | `eval_recall.load_fixtures()` validates non-empty expected ids but does not prove that each id/path exists in canonical memory. | A nonexistent target can be reported as a retrieval miss instead of invalid evidence. | `RET-001` |
| Multilingual recall | The shared lexical tokenizer accepts only ASCII letters, digits, and underscores; search, prompt-keyword extraction, and final context hydration all reuse that boundary. | Spanish diacritics can fragment and non-Latin scripts can disappear before ranking, so a vector proposal could hide a cheaper lexical defect. | `RET-001` baseline cases, then `RET-002` |
| Future hydration | Context assembly revalidates a selected item from canonical lexical/project evidence. A future semantic-only candidate could be selected and then discarded. | Any experiment must evaluate end-to-end context delivery, not search ranking alone. | `RET-002` |
| Graph identity | `stable_id()` lowercases and replaces spaces; distinct metadata values such as `Foo Bar` and `foo-bar` can normalize to the same node id, while the first node wins. | Graph output can silently merge distinct labels. | `GRF-001` |
| Graph scope | References are resolved against only the memories in the requested page. This is documented behavior, but the output has no versioned field declaring that closure boundary. | Consumers can misread a page-local projection as a complete neighbor graph. | `GRF-001` |
| Graph reference meaning | `references` scans every body mention matching `mem_*`, including examples or code; it does not prove an intentional Markdown or Obsidian link. | A consumer can over-interpret a textual mention as a semantic relation. | `GRF-001` |
| Frontmatter parsing | Duplicate top-level or nested keys overwrite earlier values in the limited parser. | Ambiguous canonical input can validate with a different meaning than the author saw. | `MIG-001` format inventory, then a compatible parser fix |
| Index concurrency | `rebuild_index()` uses one fixed `memory.sqlite.tmp` path and has no shared rebuild-writer boundary. | Concurrent rebuild attempts can contend on or remove the same temporary file, especially on Windows. | `MIG-001` |
| Generated state | Rebuild snapshots lifecycle/feedback state before replacing the database. Concurrent generated-state writes after that snapshot can be lost. | SQLite is disposable, but user-visible feedback needs an explicit ownership/fencing contract. | `MIG-001` |
| MCP budget drift | The generator measures profile counts and schema bytes, but its docs check does not enforce the human profile table and the current admin byte count has drifted from that table. | Documentation can misstate the actual context cost even when tool names are current. | `BRG-019` |
| Proposal pressure | `memory.write_proposal` and review recommendations do not share one normalized fingerprint, deduplication policy, or queue cap; some readers scan every matching Markdown file. | Repeated agents can create avoidable review work and unbounded administrative scans. | `MIG-001`, then `CON-001` for deterministic candidate grouping |

### Overstated or stale claims

| Claim | Current evidence-based correction |
| --- | --- |
| “The graph has no typed relationships.” | It already emits `tagged`, `belongs_to_project`, `has_type`, `has_scope`, and `references`. It lacks canonical semantic predicates; that does not justify inferred NER relations. |
| “Obsidian aliases/sections are ignored.” | The `mem_*` matcher recognizes an id embedded in `[[mem_id|Alias]]`, `[[mem_id#Section]]`, or a Markdown URL. Title-, alias-, or path-only links are not resolved. |
| “Cross-page links are accidentally broken.” | References are deliberately page-local and documented as such. The real gap is an explicit, versioned closure contract. |
| “Search is pure FTS.” | FTS supplies candidates, but ranking also uses aliases, tags, project, confidence, lifecycle, recency, and explanatory metadata. Synonym/paraphrase expansion remains absent by design. |
| “All Obsidian notes must have sixteen fields and custom keys fail.” | The strict contract applies to canonical `memories/**`. Inbox or rough notes are separate, and additional flat keys are accepted. The compatibility gap is duplicate-key ambiguity and a poorly explicit accepted-format matrix. |
| “There is no locking.” | Config, onboarding, scheduler, review, and maintenance paths already have locks, compare-and-swap checks, atomic writes, or fencing. The confirmed exception is shared index rebuild ownership. |
| “Every client pays for 74 MCP tools.” | Profiles are server-enforced in both `tools/list` and `tools/call`; normal public/core clients expose three or four tools. Admin remains large and should be measured, not assumed to affect every turn. |
| “There is no progressive autonomy or resource explanation.” | Intensity profiles, model policy, review modes, bounded scheduling, and proposal-only automation already exist. Their usability may improve, but canonical auto-promotion is intentionally absent. |

### Rejected for the current plan

- Do not add NER, GraphRAG, entity inference, or semantic relations generated by
  a model before projection identity and evidence contracts are stable.
- Do not add embeddings, a vector database, a cross-encoder, HyDE, provider
  synthesis, or a production ranking change under this handoff.
- Do not auto-promote canonical memory from confidence scores, repeated agent
  agreement, retrieval frequency, or metadata-only observations.
- Do not collapse stable MCP names into one mega-tool or add new MCP status tools
  before the inventory and external compatibility gates.
- Do not adopt PyYAML or enable SQLite WAL as reflexive fixes. First freeze the
  accepted format and writer/concurrency contract; choose the smallest solution
  proven by tests.
- Do not migrate the headless runtime to Node. A future visual plane may consume
  generated contracts but cannot own vault policy or canonical writes.

## Normative task contracts

### `BRG-019` — exact bridge and MCP capability budgets

Acceptance must prove one generated inventory covers:

- provider-native events and common aliases;
- accepted and discarded fields, correlation/fingerprint inputs, sensitivity,
  reliability, writer class, and side effect;
- every MCP tool family, stable name, compatibility alias, deprecation state,
  writer/effect class, and profile membership;
- per-profile tool count, compact schema bytes, estimated tokens, and named hard
  or advisory budgets;
- exact docs/artifact drift detection with no ledger, learning, or new tool.

### `MIG-001` — complete writer and accepted-format freeze

The inventory must enumerate canonical Markdown writers and every proposal,
receipt, archive, report, configuration, generated database, and temporary-file
writer. Each row declares accepted format, authority, review boundary,
fingerprint/dedup behavior, queue/file cap, lock/fence owner, atomicity, recovery,
retention, secret scan, and compatibility alias.

The task must also define the limited frontmatter compatibility matrix and make
duplicate keys an explicit reject case with line diagnostics. Index rebuilds
must have a bounded cross-process writer boundary, a unique per-attempt temporary
file, controlled contention errors, atomic replacement, and Windows/POSIX stress
coverage. WAL is not an acceptance criterion.

### `RET-001` — truth-preserving recall evaluation

Use two separate, immutable-by-review roles:

1. passing regression fixtures protect already solved behavior;
2. held-out challenges preserve reviewed unresolved misses and cannot be
   promoted away merely because the current implementation fails them.

Acceptance requires canonical target existence checks, stable case ids, source
provenance, corpus hashes, train/test leakage checks, explicit invalid/unknown
states, deterministic summaries, and reviewed Spanish/Unicode cases that expose
the current ASCII baseline honestly. `vector status` may describe evidence only
after it consumes this separation correctly. The task must not change search,
context ranking, dependencies, or default runtime behavior.

Before `GATE-B`, `RET-001` must also own, version, and freeze the machine-readable
`retrieval-benchmark-v1` measurement/result contract that `RET-002` will later
populate. Freezing an evaluator contract does not authorize a candidate or
change runtime behavior. The contract requires `contract_name=retrieval-benchmark`
and `schema_version=1`, plus:

- deterministic case ids and a SHA-256 corpus digest. The id payload is compact
  UTF-8 JSON with sorted keys containing the exact query code points, sorted
  expected ids, scope, and immutable provenance id, but no `case_id` or mutable
  review timestamps; its id is `ret_` plus the first 20 hex characters of the
  payload SHA-256. The corpus digest covers the full case records sorted by case
  id and joined with LF, plus the exact policy/configuration digest and source
  commit;
- one paired FTS-control and candidate result for every case, using the same
  query, reviewed expected ids, corpus, host, policy, configuration, and final
  context-hydration path;
- case recall equal to the fraction of reviewed expected ids present in the
  first ten final hydrated context items; primary macro `Recall@10` is the
  unweighted mean of that value across held-out cases;
- secondary `MRR@10`, the unweighted case mean of the reciprocal rank of the
  first expected id in the first ten final hydrated items, with zero when none
  is present;
- one complete warm-up repetition per arm, excluded from results, followed by
  five measured paired repetitions. Odd repetitions run FTS then candidate;
  even repetitions reverse that order. A failed attempt scores zero for recall
  and MRR and also contributes to the error rate;
- a 95% paired percentile-bootstrap interval over the per-case mean candidate
  minus FTS `Recall@10` deltas, using 10,000 resamples and seed `20260827`.
  Cases use case-id order; sampling indices are derived as
  `uint64_be(SHA-256(seed || ":" || replicate || ":" || draw)[0:8]) mod N`,
  and the interval endpoints are the nearest-rank 2.5th and 97.5th percentiles,
  so results do not depend on a runtime-specific PRNG;
- per-arm nearest-rank p50/p95 end-to-end latency over all measured attempts,
  and peak aggregate RSS for the harness process tree sampled every 50 ms with
  boundary samples. The report records the OS, architecture, CPU, physical RAM,
  Python/dependency identity, candidate/model identity, sampler, case count,
  errors, lock failures, index bytes, and rebuild duration; and
- explicit counts for policy, provenance, and sensitive-data violations. Missing
  fields, mismatched digests/case ids, leaked child processes, or a non-reproducible
  protocol make a result invalid rather than partially comparable.

### `GATE-B` — compatibility readback

`GATE-B` now depends directly on `RET-001` as well as `MIG-001`. It still requires
external client readback and cannot be completed from repository tests or these
documents.

### `GRF-001` — versioned graph projection

After `GATE-B`, add collision rejection or collision-safe ids, `schema_version`,
`reference_scope=within_page`, `reference_detection=body_mention_v1`, strict
output schemas, deterministic ordering, and tests for wikilink-embedded ids,
non-link mentions, missing neighbors, collisions, pagination, and closure.

Completion also requires two fresh out-of-process MCP sessions against the same
deterministic public fixture vault and package artifact. The consumer must be
selected from the supported-client inventory frozen by `BRG-019`; this plan does
not preselect or claim a client/version. A secret-scanned receipt records the
selected client name/version, package source commit and artifact identity,
OS/Python/MCP protocol, sanitized exact `initialize`, `tools/list`, and
`memory.graph` request parameters, returned schema version/reference
scope/reference detection, schema-validation result, and the SHA-256 of compact
UTF-8 sorted-key canonical `memory.graph` result JSON. Both sessions must
reproduce those contract fields and the response hash. An in-process import or
direct function call never counts as external readback. The task changes a
disposable inspection projection only.

### `RET-002` — bounded retrieval comparison

Only after `GRF-001`, compare production FTS against one shared deterministic
Unicode normalization/tokenization candidate, fuzzy/query variants, bounded
one-hop graph candidates, and optionally one local multilingual vector
candidate. Use opt-in shadow reports and the frozen `retrieval-benchmark-v1`
contract. A candidate passes the v1 quantitative gate only when all of these are
true on the same valid run:

- at least 100 reviewed held-out cases are present with no train/test leakage;
- macro `Recall@10` after final context hydration improves by at least `0.05`
  (five absolute percentage points) over FTS;
- the lower bound of the 95% paired bootstrap interval for that improvement is
  greater than zero;
- candidate p95 end-to-end latency is at most `1.20` times FTS p95, and candidate
  peak process-tree RSS is at most `1.25` times FTS peak RSS;
- measured candidate attempts ending in an error or lock failure are at most 1%
  of candidate attempts, while an FTS control rate above 1% invalidates the
  benchmark; and
- candidate `MRR@10` is no more than `0.01` (one absolute point on the `[0,1]`
  scale) below FTS, with zero policy, provenance, or sensitive-data violations.

The report must also receive external consumer readback. These thresholds are
the `retrieval-benchmark-v1` experiment gate, not runtime defaults and not
authorization to implement, promote, package, or enable a candidate before its
owning tasks and review gates. Passing permits a production-design review only;
index size, rebuild duration, packaging, and maintenance measurements remain
reported decision inputs rather than hidden quantitative gates.

## Test and rollback gates

- Planning schema, DAG, docs links, secret scan, artifact guard, and empty-ledger
  checks remain mandatory for this planning change.
- `BRG-019` fails if generated inventory and docs/budgets drift.
- `MIG-001` fails on an unknown writer/format, duplicate YAML key accepted as
  authoritative, lost generated-state write, temp collision, leaked process, or
  uncontrolled lock failure.
- `RET-001` fails if an invalid target counts as a miss, an unresolved challenge
  disappears, a regression corpus is silently rewritten, hashes/provenance do
  not reproduce, or `retrieval-benchmark-v1` is not frozen and replayable before
  `GATE-B`.
- `GRF-001` fails on silent node collision, ambiguous closure, schema drift, or
  sensitive-data widening, or when its two out-of-process receipts do not
  reproduce the versioned contract fields and canonical response hash.
- `RET-002` rejects the shadow candidate and removes its generated experimental
  state while leaving FTS unchanged if the benchmark is invalid or any v1
  threshold above fails. Because the experiment is shadow-only, this is a
  candidate rollback, not a production ranking rollback.

## Additional learnings

1. Measurement quality precedes algorithm choice. A misleading green corpus is
   more dangerous than a known lexical limitation.
2. Generated projections need consumer semantics, not only deterministic JSON.
   Page closure and collision behavior are part of the graph contract.
3. MCP schema size is a capability budget. Profile enforcement solves default
   exposure; generated budget drift checks solve long-term growth.
4. Index concurrency is a writer-ownership problem. Storage pragmas cannot
   replace fencing, unique temporaries, and recovery tests.
5. Review throughput should improve without weakening truth governance. Exact
   deduplication, bounded queues, deterministic grouping, and at most one
   candidate per maintenance run are safer levers than auto-promotion.
6. A retrieval experiment must be evaluated through final context hydration.
   Candidate recall alone can hide a downstream filter that discards the win.
7. Multilingual correctness is a baseline contract, not evidence for vectors.
   Share one measured Unicode normalization boundary across candidate search,
   turn keywords, and final hydration before adding a model dependency.

## Next legal action

Complete `BRG-003` first. Then implement `BRG-019`, `MIG-001`, and `RET-001` in
that order as small reviewed changes. This handoff changes no runtime, version,
package, release, vault, configuration, vector state, MCP surface, or current
frontier.
