# V3 Hybrid Visual And Multiplatform Roadmap

Status: C0 planning contract. This document does not claim V3 runtime delivery,
external evidence, or gate completion.

## Product Decision

Keep the proven local Python product and add capabilities by evidence, not by
rewriting for fashion. Python remains the domain/headless authority because the
current package, safety model, filesystem behavior, MCP server, scheduler, and
test corpus are Python-native and have no mandatory third-party runtime
dependencies.

Node/TypeScript is appropriate for a future visual plane when a real browser or
desktop experience exists. That plane should consume generated, versioned
contracts over a narrow local API. It must not become a second canonical writer,
embed private vault data into static assets, or make Node a requirement for CLI,
MCP, hooks, or maintenance.

## Architecture Invariants

1. Markdown is canonical; indexes and vector projections are disposable.
2. Every private operation uses an explicit, contained vault binding.
3. Durable memory requires review; automation creates proposals, not facts.
4. All writes are inventoried, fingerprinted where meaningful, secret-scanned,
   and recoverable.
5. MCP exposure, tokens, provider scans, processes, schedules, and artifacts are
   bounded by named profiles.
6. Public source, installed executable, and private vault remain separate.
7. A UI receives the least capability required and cannot widen server policy.
8. Compatibility and security gates require reproducible evidence, including
   external readback where the contract says so.
9. Learning evidence excludes raw prompts, transcripts, and tool payloads;
   retrieval or exposure alone never counts as credited utility.

## Historical Consolidation

The former private branch combined useful research with stale runtime,
machine-local evidence, personal memory, and a partially generated V3 plan. The
public V3 plan adopts the useful concepts but not the archive's repository
identity or claims.

Adopt:

- explicit source-adapter contracts and transformation ledgers;
- writer inventory, leases/fencing, recovery, and exact-artifact tests;
- backend capability/health contracts while keeping Markdown authoritative;
- portable export, health/repair, benchmark discipline, and threat modeling;
- a generated TypeScript contract boundary for an optional visual plane.

Adapt:

- palace-style evidence navigation as a view, not the memory domain model;
- temporal relationships as Markdown decisions plus regenerated projections;
- queue/worker ideas to bounded local maintenance before any remote service;
- multi-user governance only after authentication and ownership requirements
  exist.

Reject or defer:

- wholesale archive merges, automatic destructive sync, agent diaries as
  durable truth, vector databases as canonical authority, production Node as a
  CLI dependency, and broad unauthenticated MCP writes;
- archive memories, inbox data, reports, local paths, pins, receipts, and old
  release evidence;
- a hosted team service or many storage backends without measured demand.

## Normative Task Frontier

The machine-readable order is
`contracts/planning/v3-execution-sequence.json`. Current public tasks are:

<!-- BEGIN NORMATIVE TASK STATE TABLE -->

| Task ID | Objective | Batch | State | Notes |
| --- | --- | --- | --- | --- |
| `BRG-014` | Separate config-only setup from memory-only onboarding | `B04a` | `complete` | Stable verified baseline. |
| `BRG-003` | Deterministic explicit vault/root binding | `B04b` | `in_progress` | Sole current frontier. |
| `BRG-017` | Strict config parsing and diagnostics | `B04b` | `complete` | Completed within the current batch. |
| `BRG-019` | Bridge/MCP capability, effect, profile, and schema-budget inventories | `B04c` | `pending` | Starts after `BRG-003`. |
| `MIG-001` | Freeze writer, accepted-format, locking, and recovery inventories | `B05a` | `pending` | Starts after `BRG-019`. |
| `RET-001` | Truth-preserving regression and held-out recall evaluation | `B05b` | `pending` | Starts after `MIG-001`. |
| `GATE-B` | Demonstrate V2 compatibility before migration | `B06` | `blocked` | Requires external evidence. |
| `GRF-001` | Version a collision-safe graph projection contract | `B06a` | `future` | Starts after `GATE-B`. |
| `RET-002` | Compare bounded retrieval candidates in shadow mode | `B06b` | `future` | Starts after `GRF-001`. |
| `RET-003` | Design and gate any production retrieval change | `B06c` | `future` | Starts only after a passing, reviewed `RET-002`. |
| `OBS-001` | Bounded provider-neutral observation shadow | `B07a` | `future` | Starts after `GATE-B`. |
| `OUT-001` | Exact outcome attribution without exposure rewards | `B07b` | `future` | Starts after `OBS-001`. |
| `CON-001` | Deterministic governed candidate materialization | `B08a` | `future` | Starts after `OUT-001`. |
| `MEM-001` | Reviewed semantic and advisory procedural forms | `B08b` | `future` | Starts after `CON-001`. |
| `ONB-001` | V3 guided onboarding experience | `B20` | `future` | Distinct from `BRG-014`; starts after `GATE-B`. |

<!-- END NORMATIVE TASK STATE TABLE -->

Current frontier: `BRG-003`.

No task may be marked complete from documentation alone. Evidence paths must
refer to current public commits and reproducible tests. `GATE-B` is the generic
authenticated-provider compatibility gate and remains blocked until its
selected provider returns exact readback. A task-specific local MCP
consumer receipt, such as the one required by `GRF-001`, is separate evidence
and cannot complete or retroactively replace `GATE-B`.

Every externally gated task declares a versioned `external_readback_contract`
in the execution-sequence JSON. A receipt must match that task's exact contract
id, kind, minimum session count, and fixture requirement; a valid receipt for a
different task or readback class cannot be substituted.

### Acceptance boundaries added by proposal validation

The [proposal validation handoff](proposal-validation-handoff.md) records the
evidence and rationale behind these refinements. It is explanatory and cannot
add or alter acceptance. This roadmap is authoritative for the detailed
acceptance boundaries below; the JSON contract is authoritative for task and
batch identity, state, dependencies, frontier, and evidence paths.

- `BRG-019` must generate exact inventories for provider events, aliases,
  fingerprints, writers and side effects, plus MCP tool families, compatibility
  aliases, deprecation state, profile exposure, tool counts, schema bytes,
  estimated tokens, and named budgets. Drift must fail an exact-artifact check.
  This task does not add an event ledger, learning loop, or MCP tool.
- `MIG-001` must cover every canonical, proposal, receipt, archive, report, and
  generated-index writer; each accepted frontmatter/input format; deduplication
  and queue limits; lock/fencing ownership; temporary paths; crash recovery;
  retention; and secret scanning. In particular, index rebuilds need a bounded
  shared writer boundary and unique per-attempt temporary files before their
  concurrency can be claimed safe.
- `RET-001` must separate passing regression fixtures from reviewed unresolved
  challenges, verify that every expected id/path exists, prevent train/test
  leakage, and let failures remain represented without weakening release
  regression checks. Spanish/Unicode cases must expose the current
  ASCII-tokenization baseline rather than disappearing from it. No
  `retrieval-benchmark-v1` schema or artifact is frozen by this planning change:
  `RET-001` must implement, version, test, and freeze it before `GATE-B`, without
  changing ranking or runtime dependencies.
- The future `retrieval-benchmark-v1` contract must declare
  `contract_name=retrieval-benchmark` and `schema_version=1`. Its canonical JSON
  encoding is UTF-8 without BOM or trailing LF, with object keys sorted by
  Unicode code point, no insignificant whitespace (`","` and `":"`
  separators), `ensure_ascii=false`, duplicate keys and non-finite numbers
  rejected, and strings preserved without Unicode normalization. Expected ids
  are unique and sorted by Unicode code point. The case-id payload is exactly
  `expected_ids`, `provenance_id`, `query`, and `scope`; it excludes `case_id`
  and mutable review timestamps. `case_id` is `ret_` plus the first 20 lowercase
  hexadecimal characters of the payload SHA-256.
- A held-out full-case record is exactly the canonical object with keys
  `case_id`, `corpus_role` (the literal `held_out`), `expected_ids`,
  `provenance_id`, `query`, `schema_version` (integer `1`), and `scope`. The
  corpus bytes are one canonical JSON array of those records sorted by
  `case_id`, with no BOM or trailing LF; `corpus_sha256` is the lowercase SHA-256
  of those exact bytes. A report also records `source_commit` as the full 40-hex
  commit and `source_artifact_sha256` as the lowercase raw-byte SHA-256 of the
  executed source/package artifact, plus
  `configuration_sha256`: the same canonical-byte digest over one schema-checked,
  fully materialized benchmark object containing control settings, candidate
  settings, hydration, policy, scope, lifecycle, sensitivity, profile, and
  harness settings. Both arms reference this one object; unknown, missing,
  path-dependent, or secret-bearing fields invalidate the run.
- Every candidate attempt is paired with an FTS control for the same case,
  reviewed expected ids, corpus, source artifact, host, effective configuration,
  and final hydration path. Case `Recall@10` is the fraction of expected ids in
  the first ten final hydrated ids; macro `Recall@10` is its unweighted case
  mean. `MRR@10` is the unweighted case mean reciprocal rank of the first
  expected id in those ten, or zero when absent. The excluded warm-up runs the
  full corpus once with FTS first and once with the candidate second. It is
  followed by five measured paired repetitions; zero-based even repetitions run
  FTS then candidate and odd repetitions reverse the order. Failed attempts
  score zero for both quality metrics and count as errors.
- The 95% interval is a deterministic paired percentile bootstrap over each
  case's mean candidate-minus-FTS `Recall@10` delta. It uses seed `20260827`,
  exactly 10,000 replicate indices `0..9999`, and exactly `N` draw indices
  `0..N-1` per replicate for `N` cases sorted by `case_id`. Each sampled index is
  `uint64_be(SHA-256(UTF8(decimal(seed) + ":" + decimal(replicate) + ":" +
  decimal(draw)))[0:8]) mod N`; decimal values have no sign, leading zero,
  whitespace, BOM, or newline. Sort the 10,000 replicate means and use the
  one-based nearest-rank observations `ceil(0.025 * 10000)` and
  `ceil(0.975 * 10000)` as endpoints.
- The benchmark report must additionally record nearest-rank p50/p95
  end-to-end latency, process-tree RSS sampled every 50 ms plus attempt-boundary
  samples, peak RSS, environment and dependency/model identity, errors, lock
  failures, index bytes, rebuild duration, and policy, provenance, and
  sensitive-data violations. Any missing field, digest/case mismatch, leaked
  child process, or non-reproducible replay invalidates the result.
- `GRF-001` must fail closed on normalized-node collisions, add
  `schema_version`, state `reference_scope=within_page` and
  `reference_detection=body_mention_v1`, provide strict graph output schemas,
  and test reference, collision, and page-closure semantics. It must also prove
  two-run readback from a fresh out-of-process local MCP consumer selected from
  the `BRG-019` supported-client inventory against one deterministic public
  fixture vault and package artifact; this local consumer receipt is not the
  authenticated-provider evidence owned by `GATE-B`. No client/version is
  selected before `BRG-019` freezes the inventory.
- The secret-scanned `GRF-001` receipt records selected client name/version and
  lowercase raw-byte client-artifact SHA-256; selected server profile and
  effective allowlist (the profile must expose `memory.graph`, currently a
  review-class surface); package source commit and lowercase raw-byte artifact
  SHA-256; OS, Python, and MCP protocol; lowercase raw-byte SHA-256 of the
  graph/output-schema artifact; and a fixture-vault digest. The
  fixture digest is the lowercase SHA-256 of canonical JSON bytes for an array
  sorted by POSIX relative path, with one object per admitted fixture file:
  `path`, raw-byte `sha256`, and byte `size`. Generated, ignored, or unadmitted
  files make the receipt invalid rather than silently changing the manifest.
- Each of the two fresh sessions records the full ordered MCP lifecycle:
  `initialize` request/response, `notifications/initialized`, `tools/list`
  request/response, `tools/call` for `memory.graph` including exact parameters
  and response, then normal EOF and zero exit. The parsed lifecycle artifact is
  one canonical JSON array whose entries have exactly `ordinal` (zero-based),
  `direction` (`client_to_server`, `server_to_client`, or `control`), and
  `message`; fixed request ids are part of `message`, while EOF and exit are
  separate control messages. The receipt records returned schema version,
  reference scope/detection, and schema-validation result.
- Lifecycle redaction is replacement-only. Under `redaction_version=1`, a
  schema-bounded allowlist of RFC 6901 JSON pointers is sorted by Unicode code
  point; each present value is replaced with the exact JSON string
  `"<redacted:v1>"`, and missing, extra, removed, or wildcarded fields invalidate
  the run. The redaction manifest is a canonical JSON array of exact
  `pointer`/`reason` objects sorted by pointer. `transcript_sha256` is the
  lowercase SHA-256 of the post-replacement canonical lifecycle-array bytes.
  The graph result hash is separately calculated over parsed result JSON
  re-encoded with the same canonical JSON byte rules. The public fixture graph
  result itself must need no redaction, otherwise the run is invalid. Both
  sessions must reproduce the contract fields, fixture/schema/artifact
  identities, redaction manifest, transcript hash, and result hash. An
  in-process import or direct function call does not count. The task changes a
  disposable inspection projection only and does not authorize graph-aware
  recall.
- `RET-002` may compare FTS, a shared deterministic Unicode
  normalization/tokenization candidate, fuzzy/query variants, bounded one-hop
  graph candidates, and an optional local multilingual vector candidate only in
  opt-in shadow reports. Under `retrieval-benchmark-v1`, a candidate must use at
  least 100 reviewed held-out cases and improve macro `Recall@10` after final
  hydration by at least `0.05`, with the lower 95% paired-bootstrap bound above
  zero. Its p95 latency must be at most 120% of FTS, peak process-tree RSS at
  most 125% of FTS, and error-or-lock-failure rate at most 1%; `MRR@10` may
  fall by no more than `0.01`, and policy, provenance, and sensitive-data
  violations must all be zero. Out-of-process consumer readback of the shadow
  result is still required. These are v1 experiment gates, not runtime defaults.
  Any invalid run or failed threshold rejects the generated shadow candidate and
  leaves production FTS unchanged. A passing run permits only a reviewed
  production-design proposal under `RET-003`; `RET-002` cannot package, enable,
  promote, or change default ranking.
- `RET-003` is the sole future owner of any production retrieval design,
  implementation, package/dependency change, enablement, promotion, or default
  ranking change. It may start only after `RET-002` is complete with one valid,
  passing, independently reviewed benchmark and readback receipt. Its acceptance
  must select the smallest justified candidate; bind privacy, provenance,
  lifecycle, resource, license, platform, install/upgrade/uninstall, generated
  artifact, fallback, and rollback contracts; preserve deterministic FTS as a
  tested fail-safe; prove external readback; and require a separate explicit
  production approval. A passing `RET-002` is evidence for this design review,
  never production authorization by itself.

## Delivery Phases

### Phase 0: V2.1 stable baseline

- Keep the completed `BRG-014` implementation, its historical TestPyPI
  evidence, and the externally read-back stable `2.1.1` PyPI release as the
  compatibility baseline.
- Verify Windows/macOS/Linux CI, package install, MCP lifecycle, and site docs.
- Preserve Python-only production runtime and zero internal model calls.

### Phase 1: Compatibility and writer control

- Complete the remaining `BRG-003` frontier first, then `BRG-019` and
  `MIG-001`, as small PRs. Preserve the completed `BRG-017` strict-config
  boundary while those integrations are inventoried. Repair the recall evidence
  contract under `RET-001` before attempting `GATE-B`.
- Generate CLI, bridge, MCP profile/schema-budget, accepted-format, and complete
  writer inventories.
- Add exact-artifact, concurrent binding, crash recovery, and config strictness
  coverage without importing archive runtime wholesale.

### Phase 2: Measured retrieval and maintenance

- After `GATE-B`, stabilize the graph as a versioned disposable projection in
  `GRF-001`; only then may `RET-002` compare retrieval candidates in shadow
  mode. A passing comparison may open `RET-003` for production design, but does
  not itself change the package or default ranking. This is an independent
  branch from governed learning and does not block `OBS-001`.
- Treat the
  [governed learning loop handoff](governed-learning-loop-handoff.md) as the
  approved design for `OBS-001`, `OUT-001`, `CON-001`, and `MEM-001`. These
  remain future tasks until `GATE-B`; the handoff itself is not runtime
  evidence.
- Add the observation shadow first, then exact outcome attribution, deterministic
  candidate materialization, and only then reviewed memory forms. Keep
  observation off by default and prohibit ranking changes before explicit
  credit is measurable.
- Establish cold/warm latency, peak RSS, provider throughput, recovery, and
  host-agent-token SLOs per intensity.
- Use [the source-grounded query design](source-grounded-query-design.md) as
  non-normative research input when this phase has a legal task owner; it does
  not create acceptance evidence or executable work. Keep query-time synthesis
  read-only and durable consolidation proposal-first.
- Add incremental checkpoints, no-op maintenance, and stale-lock fencing.
- Keep FTS as the production baseline through `RET-002`. Only `RET-003`, after a
  valid comparison and separate approval, may own a production change justified
  against latency, memory, privacy, and migration burden.
- Do not add model-assisted synthesis to the executable DAG until a reviewed
  replay proves deterministic consolidation has a material gap.

### Phase 3: Generated contracts and local API

- Version JSON schemas for read models, commands, errors, capabilities, health,
  and pagination.
- Generate TypeScript types from those schemas; never hand-maintain two domain
  models.
- Add authenticated local API capability checks before exposing any write.

### Phase 4: Optional visual plane

- Build a static/prebuilt TypeScript/React interface for search, graph,
  provenance, review queues, setup health, and resource intensity.
- Keep private content runtime-local; GitHub Pages remains documentation only.
- Validate mobile/desktop layout, keyboard access, contrast, overflow, and
  browser smoke before distribution.

### Phase 5: Packaging and multiplatform evidence

- Keep pipx/uv and Python wheels authoritative for headless use.
- Evaluate a desktop wrapper only after the local web plane is useful and
  measurable.
- Prove install, upgrade, backup, export, recovery, process cleanup, and
  uninstallation on Windows, macOS, and Linux.

### Phase 6: Shared memory, only if demanded

- Require authentication, tenancy, authorization, audit, retention, conflict,
  and incident ownership before any remote/team service.
- Benchmark against local-first operation and retain portable Markdown export.

## Continuous Improvement Loop

For each monthly cycle:

1. inspect user-visible failures and resource measurements;
2. select the first legal task with measurable acceptance criteria;
3. implement one reversible slice;
4. run exact contract, security, package, and UI evidence as applicable;
5. publish a reviewed handoff and update the execution sequence only when
   evidence or dependencies changed;
6. delete or defer surfaces whose value does not justify complexity.
