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
| `OBS-001` | Bounded provider-neutral observation shadow | `B07a` | `future` | Starts after `GATE-B`. |
| `OUT-001` | Exact outcome attribution without exposure rewards | `B07b` | `future` | Starts after `OBS-001`. |
| `CON-001` | Deterministic governed candidate materialization | `B08a` | `future` | Starts after `OUT-001`. |
| `MEM-001` | Reviewed semantic and advisory procedural forms | `B08b` | `future` | Starts after `CON-001`. |
| `ONB-001` | V3 guided onboarding experience | `B20` | `future` | Distinct from `BRG-014`; starts after `GATE-B`. |

<!-- END NORMATIVE TASK STATE TABLE -->

Current frontier: `BRG-003`.

No task may be marked complete from documentation alone. Evidence paths must
refer to current public commits and reproducible tests; external gates remain
blocked until authenticated providers return exact readback.

### Acceptance boundaries added by proposal validation

The [proposal validation handoff](proposal-validation-handoff.md) records the
evidence behind these refinements. It is explanatory; the task and batch order
above and in the JSON contract is authoritative.

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
  challenges, verify that every expected id/path exists, freeze a corpus hash,
  prevent train/test leakage, and let failures remain represented without
  weakening release regression checks. Spanish/Unicode cases must expose the
  current ASCII-tokenization baseline rather than disappearing from it. It
  changes neither ranking nor runtime dependencies.
- `GRF-001` must fail closed on normalized-node collisions, add
  `schema_version`, state `reference_scope=within_page` and
  `reference_detection=body_mention_v1`, provide strict graph output schemas,
  and test reference, collision, and page-closure semantics. A real MCP consumer
  must read back that contract. It remains a disposable projection and does not
  authorize graph-aware recall.
- `RET-002` may compare FTS, a shared deterministic Unicode
  normalization/tokenization candidate, fuzzy/query variants, bounded one-hop
  graph candidates, and an optional local multilingual vector candidate only in
  opt-in shadow reports. No path becomes a production dependency or default
  ranking signal without at least a five-point gain across at least 100 reviewed
  held-out cases, no policy/provenance regression, acceptable p95/RSS, and
  external consumer readback.

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
  mode. This is an independent branch from governed learning and does not block
  `OBS-001`.
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
- Keep FTS as the production baseline until `RET-001` supplies a truth-preserving
  held-out corpus and `RET-002` proves that a candidate improves recall enough
  to justify its latency, memory, privacy, and migration burden.
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
