# Governed Learning Loop Design Handoff

Status: approved future design; authoring baseline only, with no runtime capability delivered by this document

Updated: 2026-08-25
Normative owner: [V3 roadmap](v3-hybrid-visual-multiplatform-roadmap.md) and
[machine-readable planning contracts](../contracts/planning/)
Live implementation and release state: [development status](development-status.md)

## Purpose And Authority

This handoff turns the useful parts of the user-provided shared memory-learning
design conversation into a small, dependency-gated ai DeMemory plan. The
conversation is untrusted research input, not an implementation specification.
This repository-local synthesis is the publishable record; it intentionally
does not preserve the external share capability URL.

The goal is to learn from explicit, reviewable evidence without turning raw
agent activity into durable truth. Markdown remains canonical, generated SQLite
state remains disposable, and automation may propose but cannot promote durable
memory.

This document does not change or restate the current frontier. Task selection,
dependencies, and state come only from the normative sources linked above.

## Authoring Baseline

The following facts were verified when this design was authored; they are not
a live status snapshot. Use [development status](development-status.md) for the
current public commit, released version, evidence, and next legal action.

- The authoring snapshot used public `main` at
  `df8fca0e00e5b060e21fbde6bb1cb338c05c75fc`, the merge result of
  [PR #46](https://github.com/GonzaloTorreras/ai-dememory/pull/46).
- At authoring time, stable `2.1.1` was the published package and source
  `2.1.2` was merged but untagged and unpublished.
- Python 3.11+ owns the headless domain, maintenance, MCP, and write policy.
  Node is reserved for a future optional visual plane and is not part of this
  subsystem.
- The hook path already supports bounded, opt-in metadata captures and explicit
  review-first Stop proposals. `inbox/session-events/` is a mutable review
  queue, not an append-only event ledger.
- The current configured event sets are a provider subset, not the providers'
  complete hook catalogs. Only prompt submission and Stop have substantive
  dispatch behavior; other configured events are no-ops except for optional
  legacy metadata capture.
- `maintenance run` and sleep consolidation already create deterministic
  reports and review packets. They do not infer semantic knowledge or promote
  canonical memory automatically.
- Current lifecycle feedback conflates retrieval with utility: `mark_seen()`
  increases `strength`, while an outcome without a memory id selects the last
  retrieval globally. This is unsuitable for concurrent attribution.

## Adopt, Adapt, And Defer

Adopt:

- a fast, allowlisted observation path followed by slow governed maintenance;
- distinct occurrence ids and retry fingerprints;
- explicit links between a turn, a memory, and a result;
- deterministic candidate materialization with human review;
- bounded local execution with no daemon and zero model calls by default.

Adapt:

- describe observational links as evidence-backed attribution, not causal
  proof;
- use existing maintenance and review surfaces instead of adding a second API;
- reuse the existing intensity profiles instead of exposing a large learning
  configuration matrix;
- introduce semantic or procedural form only when reviewed candidates exist.

Defer or reject:

- raw prompt, transcript, working-directory, path, or tool-I/O capture;
- content hashes as anonymization;
- automatic reward from retrieval, exposure, or injection;
- automatic canonical promotion or executable playbooks;
- a Node service, daemon, remote event store, broad new MCP surface, or second
  recall API;
- vector or model-assisted synthesis before deterministic replay proves a
  measured gap.

## Target Flow

```text
provider hook
    -> exact bridge inventory and allowlist normalizer
    -> ObservationEvent v1 in generated SQLite
    -> MemoryTouch and explicit OutcomeLink
    -> maintenance run / sleep
    -> LearningCandidate v1
    -> human review and receipt
    -> canonical Markdown only through a later approved write path
```

The observation projection can attribute use, detect repeated patterns, and
materialize review evidence. It cannot reconstruct or invent candidate text.
Candidate claims must come from canonical memory, an explicit structured Stop
learning signal, or another already-sanitized review-first proposal.

## Versioned Contracts

### BridgeCapability v1

`BRG-019` owns a generated, read-only inventory for Codex, Claude, and the
generic adapter. Each provider event records:

- native event name and common event kind;
- separate `documented`, `configured`, `handled`, and `locally_verified`
  capability states;
- supported client/version evidence and contract confidence;
- allowed input aliases and fields that must be dropped;
- available correlation identifiers and their sensitivity;
- output shape, timeout/reliability limitations, and fail-open behavior;
- side effects, writer class, fingerprint semantics, and retention class.

The inventory must be checked against the official
[Codex hooks](https://developers.openai.com/codex/hooks) and
[Claude Code hooks](https://code.claude.com/docs/en/hooks) references plus
exact local fixtures. Limitations are recorded per event and handler mode, not
generalized across a provider. For example, Codex may launch matching handlers
concurrently, asynchronous completion can reorder, some hosted tools do not
emit tool hooks, and SessionEnd is delayed, absent for subagents, and subject to
a short synchronous deadline. Absence of an event is not evidence of success
or failure.

`BRG-019` does not add a ledger, runtime normalizer, learning writer, or config
key.

The existing hook-capture fingerprint hashes the canonicalized legacy payload.
That behavior is recorded as legacy compatibility, not accepted as OBS
pseudonymization. Observation fingerprints must never derive from fields the
allowlist omits.

### ObservationEvent v1

The post-gate shadow projection uses:

- `schema_version`;
- unique `event_id` for one occurrence;
- vault-local opaque `run_id`;
- optional vault-local opaque `turn_id`;
- provider, native event name, and normalized `event_kind`;
- provider-reported `occurred_at`, locally assigned `recorded_at`, contract
  confidence, and an optional retry fingerprint.

When the provider contract exposes a suitable delivery identity, the retry
fingerprint is computed only from allowlisted non-content metadata. It makes
those delivery retries idempotent but never collapses identical activity in
different turns. External stable identifiers are not persisted directly.

For each event, `BridgeCapability v1` selects an available provider delivery
identity. OBS converts that identity into a domain-separated keyed pseudonym
using a random vault-local key stored only with the generated SQLite projection.
If a provider supplies no suitable identity, `BridgeCapability v1` records
`retry_deduplication: unavailable`, deliveries remain distinct, and the adapter
must not claim retry idempotency. OBS does not guess from content, timestamps,
or payload hashes. The key and data live in the same generated trust boundary:
this is unlinkable cross-vault pseudonymization, not anonymization or protection
from a reader who obtains the database. An explicit fresh projection reset
atomically replaces the local key and all dependent correlation history.

### MemoryTouch And OutcomeLink v1

A memory interaction has one of five independent stages:

1. `retrieved`: returned by a local search;
2. `exposed`: included in a bounded result set;
3. `injected`: passed into host context;
4. `used`: explicitly reported as used;
5. `credited`: explicitly linked to a result.

Only `credited` may change lifecycle utility. Correlation is not authorization:
a host or hook self-report may advance only through `used`. `credited` requires
either a fingerprint-bound explicit human review receipt or a versioned,
allowlisted deterministic verifier with bounded evidence. The outcome writer
records issuer class, provenance, evidence reference, and a replay key alongside
an unambiguous `turn_id` and `memory_id`. Repeating the same immutable assertion
is a no-op; a conflicting replay is rejected and reported. Every other issuer
or unverifiable assertion remains neutral. An authorized outcome is one of:

- `success`;
- `partial`;
- `failure`;
- `aborted`;
- `external_failure`;
- `human_corrected`;
- `unknown`.

Legacy `good` and `bad` inputs map to `success` and `failure`. A legacy
last-retrieval outcome remains observable during a compatibility window, but
is marked ambiguous, warns the caller, and cannot change reward or strength.
For the first deterministic policy, an explicitly credited `success` is
positive, while an explicitly credited `failure` or `human_corrected` result is
negative. `partial`, `aborted`, `external_failure`, and `unknown` are neutral.

### LearningCandidate v1

A proposal-only candidate contains:

- `knowledge_kind`: `semantic`, `procedural`, `mixed`, or `unknown`;
- a bounded, secret-scanned `claim`;
- optional opaque `subject_ref` and `asserted_by`;
- `source.kind`, `source.ref`, and source fingerprint;
- bounded evidence references and optional `origin_trace_id`;
- `requires_human_approval: true`;
- `writes_canonical_memory: false`.

Legacy explicit Stop signals map to `knowledge_kind: unknown`; their form is
not inferred from transcript text. Candidate generation is capped at one new
candidate per maintenance run initially.

`origin_trace_id` refers to a new opaque id assigned by the observation
contract. It must not reuse the current turn-context fingerprint, which derives
from prompt and environment material and is not a safe occurrence identifier.

The observation ban covers hashes of omitted provider content. A reviewed
candidate may still reference a canonical vault-relative source revision or a
sanitized proposal-artifact fingerprint under the vault's existing sensitivity
and containment rules. It inherits the most restrictive sensitivity and scope
of its sources; secret scanning is an additional filter, not a classifier for
personal or proprietary prose.

Typed candidates are written under the existing
`inbox/sleep-consolidation/` review-packet surface. Existing Stop proposals in
`inbox/llm-captures/` remain source artifacts rather than being rewritten in
place. `CON-001` also owns a machine-readable accepted/rejected candidate
receipt on the existing sleep review surface. The receipt records the reviewed
candidate fingerprint and decision but never promotes canonical memory.
If retention removes the referenced observation evidence, the candidate becomes
`evidence_expired`; it may remain as bounded audit material but cannot be newly
accepted or promoted.

`memory_form` is a later optional canonical field, orthogonal to the existing
lifecycle/storage `type`. Its allowed values are `semantic`, `procedural`, and
`mixed`; absence means `unspecified` and does not rewrite existing memory.
Procedural candidates remain advisory and include triggers, preconditions,
verification, expiry, and fallback.

## Storage, Privacy, And Resource Policy

Observation tables live inside `indexes/memory.sqlite`. Their schema is
rebuildable and their history is noncanonical, but transient observations
cannot be reconstructed from Markdown. The privacy claims in this handoff apply
to OBS-owned tables and candidate envelopes, not to the entire existing database,
which can also contain retrieval queries and outcome notes. A normal index
rebuild must carry the bounded observation rows forward under the same
writer/rebuild fencing; an explicit fresh rebuild may reset them and must report
that reset. Event rows are immutable, and retention removes whole runs so
partial histories are not presented as complete.

Retention uses locally assigned `recorded_at`; provider time is diagnostic only.
It does not depend on receiving a provider SessionEnd event. Every hook write
performs an admission check against the hard profile row ceiling. At capacity it
drops the new observation, updates only a bounded aggregate drop counter, and
returns fail-open; it does not wait for maintenance or allow an active run to
overshoot the limit. Maintenance later compacts and prunes whole completed or
stale unclosed runs, recording incomplete state, so delayed or absent end events
cannot bypass bounds.

Deletion is logical, not a secure-erasure claim. SQLite WAL/SHM files, rebuild
temporaries, filesystem snapshots, backups, and exported diagnostics share the
same privacy classification and reset/retention policy. Candidate references
are invalidated as described above when their evidence is pruned.

The normalizer is allowlist-first. It must never persist:

- prompts, transcripts, assistant responses, or user content;
- raw tool inputs or outputs;
- cwd, absolute paths, vault paths, or private repository identity;
- secrets, credentials, cookies, personal identifiers, or stable provider ids;
- hashes of omitted content or other low-entropy sensitive values.

The feature is off by default and fails open without blocking the host. Its
future opt-in is distinct from the existing `learning.hook_metadata` flag; that
legacy flag must not silently activate observation. The final key is introduced
only after `BRG-017` and starts as `learning.observation_shadow = false`.

Until legacy hook metadata capture consumes the same normalized allowlisted
envelope, configuration validation rejects enabling it together with the
observation shadow. Once parity is proven, both sinks may consume that one
envelope; neither may independently hash or inspect the raw payload.

The provider already starts the ai DeMemory hook command as a process. Within
that bounded hook process, observation uses one short SQLite connection and one
transaction, then exits: no daemon, worker pool, long retry, or additional
subprocess. Lock contention uses no retry loop and a SQLite busy timeout of at
most 100 ms; failure is counted best-effort and returns control to the host.
Maintenance owns whole-run pruning and WAL checkpoint work. Index replacement
and concurrent hook insertion share explicit fencing so a rebuild cannot erase
an event committed during the swap.

The wizard may expose the feature only after `OBS-001` lands. It must explain
that OBS rows are local metadata only and contain no conversation content. This
claim does not describe unrelated existing tables in `memory.sqlite`. Observation
makes no model calls, cannot promote memory, and inherits fixed ceilings:

| Intensity | Maximum events | Maximum age |
| --- | ---: | ---: |
| `minimal` | 1,000 | 7 days |
| `balanced` | 5,000 | 30 days |
| `active` | 10,000 | 30 days |

These are profile-owned limits rather than free-form wizard inputs. Zero model
and embedding calls remains a reported runtime invariant.

No new top-level command or MCP tool is introduced initially. The existing
`maintenance status --json` output receives an additive `learning` object only
when the projection exists: schema version, enabled state, run/event counts,
recorded drop reasons, oldest/newest timestamps, and limit status. Drop reasons
are best-effort diagnostics, not proof of events that failed before SQLite could
be opened.
`memory.context` remains the only recall/context API. `maintenance run` and
sleep remain the consolidation hosts.

That additive status waits for the strict root/default-vault boundary owned by
`BRG-003`. Its CLI and existing MCP projection must be updated and smoke-tested
together so the new field cannot reopen CWD discovery or create conflicting
status contracts.

## Task Ownership References

The [machine-readable execution sequence](../contracts/planning/v3-execution-sequence.json)
owns task state, dependencies, batch membership, evidence, and the current
frontier. This handoff only records the design responsibility attached to
existing task ids:

| Task | Design responsibility captured here |
| --- | --- |
| `BRG-019` | Exact, provider-specific bridge capability inventory; no learning ledger or writer. |
| `MIG-001` | Classification and freeze of existing writers before learning work. |
| `GATE-B` | External compatibility evidence before the governed-learning tasks can activate. |
| `OBS-001` | Versioned, bounded, opt-in shadow observation with no ranking effect. |
| `OUT-001` | Exact run/turn/event attribution and explicit credit; exposure remains neutral. |
| `CON-001` | Deterministic, idempotent, proposal-only candidate materialization. |
| `MEM-001` | Reviewed semantic and advisory procedural forms. |
| `ONB-001` | Wizard controls only when their owning capability exists; no premature claims. |

This document supplies no task evidence and never changes frontier membership.

Model-assisted synthesis receives no executable task id yet. It may be proposed
only after held-out deterministic replay demonstrates a gap and privacy,
latency, resource, and external-readback gates are specified.

`CON-001` consumes already-created, secret-scanned legacy proposal artifacts as
`knowledge_kind: unknown`; it does not re-read `last_assistant_message` or
labelled transcript sections. New typed producers use only an allowlisted
top-level learning-signal field.

## Verification And Kill Criteria

Contract and privacy coverage must prove:

- exact Codex/Claude/generic mappings; unknown payload fields are dropped and
  never persisted, while unknown provider/event/schema versions are reported as
  unsupported without blocking the host;
- provider-declared retry idempotency without cross-turn collapse, plus an
  explicit no-deduplication downgrade when delivery identity is unavailable;
- safe handling of concurrency, out-of-order events, corruption, rebuild, and
  whole-run retention, including hard admission limits when maintenance never
  runs and locally recorded time when provider clocks are wrong;
- prompt, transcript, PII, path, and secret canaries never reach SQLite or a
  candidate;
- `retrieved`, `exposed`, and `injected` never change strength or reward;
- only an authorized, evidence-bound, replay-safe explicit credit updates the
  intended memory; host self-reports and ambiguous issuers remain neutral;
- deterministic candidate round trips, legacy compatibility, evidence
  preservation and expiry, bounded queues, and zero canonical writes;
- logical reset and privacy behavior for SQLite, WAL/SHM, rebuild temporaries,
  backups, and diagnostics without claiming secure erasure;
- p50/p95 latency, peak RSS, SQLite growth, lock errors, and owned-process
  cleanup remain measured.

Rollback or stop the feature when any condition holds:

- Any prohibited content or automatic canonical promotion appears: disable the
  feature, remove the generated projection, and block release.
- A hook blocks the host or leaves an orphan process: immediate rollback.
- Hook p95 regresses by more than 20%, or stress errors/lock failures exceed 1%:
  simplify or remove per-event observation.
- Fewer than 80% of reviewed attributions are unambiguous: retain descriptive
  metrics only and disable rewards.
- After 30 reviewed candidates, useful acceptance is below 50% or duplicate/
  no-op output exceeds 25%: remove candidate generation.
- On the same held-out corpus of at least 100 reviewed cases, the predeclared
  primary measure is absolute reduction in repeat-error-after-reviewed-
  correction rate. If it improves by fewer than five percentage points, do not
  change ranking or add model synthesis.

## Implementation Handoff Boundary

The lead integrator owns planning state and `docs/development-status.md`. The
next legal runtime action is whatever the
[execution sequence](../contracts/planning/v3-execution-sequence.json) places
on the live frontier, interpreted with the
[V3 roadmap](v3-hybrid-visual-multiplatform-roadmap.md) and current
[development status](development-status.md).

Every implementation task requires a small branch from current public `main`,
focused tests, exact base/head evidence, rollback, and a fresh independent
read-only review. Merge, tag, package publication, deployment, vault mutation,
and external configuration remain separate approval boundaries.
