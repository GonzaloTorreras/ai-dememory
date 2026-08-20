# Public Modernization and Continuous Improvement Roadmap

Status: active working plan
Owner: Codex operational owner; repository owner gates production and release
Updated: 2026-08-05

## Executive Decision

Do not rebuild ai-dememory as a big-bang Node rewrite. Keep and harden the
public Python product, split it into explicit seams, and add a TypeScript/React
presentation plane only when a measured user workflow justifies it. Python
remains the only authority for canonical memory and all durable writes.

Use the former private checkout and MemPalace as research inputs, not merge
sources:

- the public repository is the only development and release authority;
- archive plans, hashes, release receipts, ADR numbers, and dirty-worktree
  snapshots are invalid until regenerated against a public commit;
- MemPalace patterns are adapted behind ai-dememory's review, privacy, and
  Markdown-canonical contracts; its implementation is not imported wholesale;
- reconstruction happens incrementally through a strangler boundary with a
  verified Python rollback path.

## What Was Wrong

### Repository and release identity

The public and former private repositories had competing authority, and active
documentation described both personal-memory storage and package distribution.
At the start of this modernization the source declared 2.1.0rc1 while PyPI
still served 2.0.0; the candidate has since completed exact TestPyPI and
post-install verification and the stable branch now converges source, package
and user documentation on 2.1.0. Earlier release documentation also treated
automated technical approval as authorization to merge and publish.

ADRs 0252, 0253, and 0255 now separate readiness from authorization, make the
public remote canonical, make the source/package/vault boundary explicit, and
leave only one package publisher. Future release evidence must state both source
version and published-index status.

### Architecture

Keeping Python is correct, but the current layout is not automatically correct:
large administrative and MCP modules combine transport, orchestration, policy,
filesystem, and reporting concerns. A wide CLI/MCP surface increases
documentation drift, test time, and capability exposure. Generated reports and
many guards are valuable, but they can become a second control plane if their
authority is not kept below canonical Markdown and reviewed decisions.

The remedy is modularization and capability reduction, not language
translation.

### Complexity concentration

The 2026-07-26 public working tree exposes 74 MCP tools. Server-enforced
profiles reduce the checked-in public plugin to three tools and generated
private-vault clients to four, but the implementation still concentrates
transport and application behavior in `mcp/server/memory_mcp.py`. The main
unit-test file and decision log remain large. Those are signs of accumulated
behavior and good regression intent, but also of weak fault isolation and
excessive navigation cost.

Do not erase that history. Generate an active-architecture index, mark
supersession explicitly, split tests by contract/domain, and move behavior
behind smaller services while retaining compatibility adapters. A new feature
must not add another MCP tool or micro-ADR when an existing profile, operation,
or architectural decision can express it.

### Planning evidence

The archive roadmap, execution ledger, threat model, MemPalace mapping, and
architecture value case are tightly connected by raw hashes. That proves exact
bytes but creates a repinning cascade: an editorial roadmap change can
invalidate the ledger, source mapping, threat snapshot, and value case without
changing product semantics.

The public plan will use versioned semantic projections for authority-bearing
facts. Raw commit/blob hashes remain provenance. A changed projection
invalidates its consumers; unrelated prose does not.

### Test topology

The original `unittest discover -s tests` command does not reliably discover
future nested planning, security, and conformance suites. The public baseline
must use an importable `tests` package and `discover -s tests -t .` everywhere
before those suites are introduced.

### Evidence gaps

The repository already guards a README-facing MCP inventory, but it still lacks
one checked-in, versioned, machine-generated cross-surface inventory covering
CLI commands, MCP profiles, canonical writers, recovery paths, and
documentation coverage. It also lacks real-product latency/RSS baselines and a
held-out recall corpus large enough to justify vector or runtime changes. These
are blockers to architectural claims, not reasons to fabricate precision.

## Target Architecture

```text
Clients and optional visual plane
        |
        | versioned JSON Schema / local API / MCP profiles
        v
Python delivery adapters
  CLI | MCP stdio | hooks | optional loopback service
        |
        v
Python application services
  recall | review | import | maintenance | migration | jobs
        |
        v
Domain and policy kernel
  identity | privacy | provenance | supersession | writer fencing
        |
        +-----------------------+
        |                       |
        v                       v
Canonical Markdown        Disposable projections
reviewed vault state      SQLite FTS | graph | vectors | reports
```

Required invariants:

1. Markdown is canonical; every index and graph is rebuildable.
2. One fenced Python writer owns each durable mutation.
3. Agent-facing writes create proposals unless an explicitly reviewed command
   applies a decision.
4. Public source, installed executable, and private vault never collapse into
   one path or repository role.
5. Read surfaces are capability-profiled; admin/release tools are not in the
   default MCP profile.
6. Node is absent from the headless runtime and never owns vault policy.
7. Every migration is inspectable, resumable, idempotent, and rollback-tested.
8. Resource and host-model policy are independent; deterministic runtime model
   and embedding calls remain zero in every current profile.

## Implemented Bounded-Autonomy Baseline

The current Phase 0 slice now includes ADR 0257 and a concrete operating
envelope:

- `minimal`, `balanced`, and `active` profiles bound recall tokens, provider
  candidates, file bytes, scanned entries, report retention, owned-process-tree
  runtime, hook queues, scheduler cadence, and MCP exposure;
- malformed or out-of-range overrides fail policy validation;
- model policy `off`, `advisory`, or `proposals` never lets ai-dememory call a
  model, enable embeddings, or promote durable memory automatically;
- the wizard previews vault-bound MCP/public-only hook configs, catalogs, hard
  caps, scheduler policy, and an exact apply fingerprint; its apply changes
  only `.ai-dememory.toml`, while optional `onboard` writes reviewed personal
  memory without rewriting operating policy;
- MCP profiles are enforced by `tools/list` and `tools/call`, with
  a three-tool public ceiling, a four-tool private-vault core, and
  resources/prompts reserved for explicit `admin`;
- provider traversal is bounded, does not follow symlinks, and explicitly
  reports when a truncated scan window is revisiting only known files;
- canonical discovery, secret scanning, graph construction, MCP input/output,
  and SQLite histories have shared hard ceilings and fail closed;
- graph delivery is paginated and capped independently from canonical storage;
- scheduler jobs are vault-namespaced, plan-fingerprint-bound, exclusively
  created, transactionally rolled back, definition-digest-backed, and exactly
  reverified before status or removal;
- unattended Docker schedules reject mutable tags and require an image digest;
- Docker maintenance has no network plus profile-specific CPU, memory, and PID
  caps;
- MCP stdio has a 120/600/1800-second self-lease, unprofiled stdio defaults to
  `core`, and every package-owned external command has closed stdin, a deadline,
  and complete process-tree reaping;
- release tags require a manual approval string bound to the exact tag and
  40-character green `main` commit; a repository variable can no longer turn
  any future merge into an automatic publication;
- setup health distinguishes manual maintenance, verified automation, and
  autonomy readiness.

This is a safe baseline, not a performance claim. Profile-level RSS, latency,
filesystem throughput, and host-agent token measurements remain open evidence.

The 2026-07-27 reliability pass reproduced the reported Windows orphan-process
failure: an MCP smoke child blocked in Git after inheriting protocol stdin, and
the timeout path initially left a grandchild alive. Central process ownership,
non-interactive Git, response deadlines, EOF shutdown, a kill-on-close Windows
Job Object, and POSIX process sessions now cover this path. Regression tests
create a real parent/grandchild tree and require both PIDs to disappear after
timeout, including when the leader exits first.

A provisional Windows/Python 3.12 source-checkout snapshot on 2026-07-26 gives
directional evidence only:

| Read-only command | Five-run average | Maximum | Sampled peak working set |
| --- | ---: | ---: | ---: |
| CLI help | 94 ms | 109 ms | 15.7 MiB |
| `setup plan --json` | 211 ms | 222 ms | 27.1 MiB |
| `maintenance status` | 1,469 ms | 1,505 ms | 28.4 MiB |

Peak working set was sampled across three additional runs. Caching canonical
root resolution in the full-repository secret scan reduced the local
`maintenance status` average from 1,916 ms to 1,469 ms (about 23%). This is not
a CI threshold: representative private-vault sizes, installed-wheel runs, other
operating systems, warm recall, and variance still need a checked-in benchmark
harness before SLOs are accepted.

## MemPalace: Adopt the Pattern, Preserve Our Contract

The upstream repository was refreshed on 2026-07-26 at
`MemPalace/mempalace` `develop` commit
`aa89bd82272f55381206c83b6f306e79351824eb` (version 3.6.0). Its current source
still supports the following comparison, but each adoption requires a fresh
public implementation and test.

| MemPalace pattern | ai-dememory disposition | Local constraint |
| --- | --- | --- |
| Typed source-adapter contract and declared transformations | Adopt | Imports produce reviewable candidates; secrets and raw auto-ingest fail closed. |
| Backend capability, health, namespace, and maintenance contracts | Adapt | Markdown remains canonical; backends are disposable projections, not interchangeable truth stores. |
| Persisted embedder identity and dimension checks | Adopt when vectors reopen | Model changes require explicit rebuild evidence; FTS remains baseline. |
| Lexical/semantic candidate union | Experiment behind evaluation gate | No vector dependency until held-out recall and cost improve materially. |
| Temporal relationships and atomic supersession | Adapt | Markdown decision commits first; graph state is regenerated from canonical provenance. |
| Durable queue, deduplication, locks, audit, backup, and repair | Adopt incrementally | Add leases, fencing tokens, crash recovery, redaction, and Windows filesystem tests. |
| Verbatim evidence with structured navigation | Adopt selectively | Preserve source excerpts and provenance without making palace taxonomy the domain model. |
| Onboarding, health, repair, portable export, and benchmark discipline | Adopt | Keep preview/apply fingerprints and exact-artifact tests. |
| Broad MCP writes, agent diaries, and automatic destructive sync | Reject | Least capability, proposal-only writes, author/reviewer separation. |
| Vector database as canonical authority | Reject | Generated and disposable only. |
| Node required in production | Reject | Python authority; optional prebuilt visual assets only. |
| Remote team service and many storage vendors | Defer | Reopen only with authenticated multi-user requirements and operating ownership. |
| Binary extraction, associative hallways, salience decay, and optional daemon | Defer | Product outcome and privacy evidence must precede surface growth. |

Upstream links:

- https://github.com/MemPalace/mempalace/commit/aa89bd82272f55381206c83b6f306e79351824eb
- https://github.com/MemPalace/mempalace/blob/aa89bd82272f55381206c83b6f306e79351824eb/mempalace/backends/base.py
- https://github.com/MemPalace/mempalace/blob/aa89bd82272f55381206c83b6f306e79351824eb/mempalace/sources/base.py

## Migration Strategy

### Phase 0 - Canonical public baseline

Deliver:

- ADRs 0252 through 0257;
- public `origin`, disabled archive push, and vault separation;
- normalized line endings and recursive test discovery;
- corrected active documentation and public demo memories;
- green guards, unit tests, secret scan, and independent review.

Exit when one clean public branch contains reproducible evidence and no private
artifact or release claim is reused.

### Phase 1 - Measure before redesign

Generate current inventories for:

- CLI commands and compatibility aliases;
- default, extended, and admin MCP tools;
- every canonical or generated writer and its lock/review behavior;
- package/import boundaries and platform-specific paths;
- docs-to-command coverage and stale release claims;
- cold CLI/hook startup, warm recall latency, peak RSS, and held-out recall.

Create a public compatibility baseline and v2 support policy. Do not increment
the package version merely to land planning evidence. Add an active ADR index
and split `tests/test_memory_tools.py` into discoverable contract/domain suites
without changing behavior or reducing coverage.

Exit when every count is generated from public source and the hard Python
product SLOs are defined.

### Phase 2 - Modular Python kernel

Extract stable modules in this order:

1. path, identity, and privacy policy;
2. fenced writer and atomic file transaction;
3. source-adapter contracts and normalized candidate records;
4. application services for recall, review, import, maintenance, and jobs;
5. thin CLI, MCP profile, hook, and loopback delivery adapters.

Preserve existing CLI and MCP compatibility through adapters. Add conformance,
fault-injection, cross-process, symlink/ADS, interruption, and rollback tests
before moving a writer.

Exit when all durable writes pass through one inventoried kernel and the old
paths contain no hidden writer.

### Phase 3 - Retrieval and temporal improvements

Keep FTS as control. Add:

- Unicode normalization and explainable candidate generation;
- held-out recall/miss ledgers with contamination controls;
- temporal supersession and provenance projection;
- optional semantic candidate union with persisted embedder identity;
- rebuild, repair, and export receipts.

Promote an experiment only when it improves held-out product recall or a defined
workflow without violating latency, privacy, install size, or offline use.

### Phase 4 - Optional visual strangler

Only after a validated review or provenance workflow needs a visual surface:

- define versioned JSON Schema/OpenAPI contracts in Python;
- generate TypeScript types and clients; do not hand-maintain duplicate DTOs;
- ship static assets inside the Python artifact;
- keep all reads scoped and all mutations routed through Python policy;
- add browser security, accessibility, responsive, offline-install, and
  Node-absent runtime smokes.

Kill the slice if the dashboard duplicates policy, writes files directly,
requires Node after installation, or cannot be removed without data changes.

### Phase 5 - Canary, migration, and decommission

Use inspect, plan, backup, apply, verify, reconcile, and rollback stages bound
to vault identity and a reviewed plan fingerprint. Start with shadow reads, then
canary read surfaces, then proposal paths. Never run two canonical writers.

Legacy paths are decommissioned only after measured use falls below an accepted
threshold, last-version migration remains green, rollback drills pass, and the
repository owner explicitly approves removal.

## Public Planning Slices

Each slice is independently reviewable and may not claim later-gate attainment:

1. Governance and portability: ADRs, docs, line endings, recursive discovery.
2. Public baseline: inventories, compatibility contract, Python SLO plan,
   support policy.
3. Minimal planning kernel: semantic schemas, task DAG, execution state, empty
   evidence ledgers; avoid importing the archive's multi-megabyte validator.
4. External-resource preflight: fail closed as `provider_not_configured`,
   perform no writes, and never turn local strings into external evidence.
5. MemPalace adaptation receipt: separate immutable upstream provenance from
   the public local mapping and use semantic digests.
6. Architecture value framework: options, assumptions, owners, kill criteria,
   and calibration inputs without fake ROI.
7. Public threat model: regenerate controls and source snapshot from a clean
   public checkout with complete history.
8. Final value contract: bind only accepted public inputs after all prior
   reviews; keep every gate unachieved until its evidence exists.

## Quality Gates

For every slice:

- `git diff --check`;
- ADR, CI, release, artifact, schema, and secret guards affected by the diff;
- focal tests first, then `python -m unittest discover -s tests -t .`;
- normal and `python -O` execution for security-critical validators;
- exact install/package smoke when packaging or imports change;
- Windows, Linux, and macOS evidence for platform claims;
- fresh independent read-only review before PR readiness.

Additional gates:

| Area | Gate |
| --- | --- |
| Canonical writes | Uninventoried durable writers = 0; double writers = 0. |
| Recall | Held-out corpus exists; misses are reviewable; no empty set reports success. |
| Python/Node | Real Python SLO measured; headless Node processes/dependencies = 0 unless a later ADR authorizes otherwise. |
| Contracts | Schema drift and hand-maintained duplicate DTOs = 0. |
| Security | Secrets in source/demo memory = 0; threat-model triggers are current. |
| MemPalace | Every adopted capability has local tests and a current upstream provenance receipt. |
| Release | Source, tag, GitHub Release, and package index version are explicitly distinguished and exact artifacts are verified. |
| Documentation | Generated inventories match docs; superseded decisions are visibly linked. |

## Continuous Improvement Loop

Per change:

- run affected structural and behavior checks;
- update inventories when command, tool, writer, contract, or workflow surfaces
  change;
- trigger threat review when a trust boundary changes;
- preserve a tested rollback path.

Weekly while active:

- inspect blockers, flaky tests, stale suppressions, dependency drift, MemPalace
  upstream drift, and unresolved documentation contradictions;
- review real recall misses and operator friction;
- select the smallest next slice with measurable user value.

Monthly:

- refresh performance/RSS and held-out recall baselines;
- review CLI/MCP capability growth and remove or profile unused surfaces;
- audit generated-artifact retention and private-vault separation;
- recalibrate the roadmap rather than repinning unchanged semantics.

Before a release:

- regenerate public release evidence from the exact branch/tag;
- independently review the exact PR tuple;
- present version, artifact hashes, CI, and known risks; obtain explicit owner
  authorization for the exact tag tuple and the separate publication tuple.

## Immediate Next Steps

1. Enable GitHub Pages for merged commit `d5effee5`, dispatch the manual workflow
   against the then-current exact `main`, and complete desktop, mobile, 404,
   accessibility, and public-origin QA as explicit production operations.
2. Build generated CLI/writer inventories; keep the already generated MCP
   profile inventory current.
3. Add incremental maintenance checkpoints, no-op runs, stale-lock leases, and
   crash-recovery tests before increasing scheduler autonomy.
4. Define and measure real hook, startup, recall, import, write, recovery, peak
   RSS, and host-agent-token SLOs for each resource intensity.
5. Add just-in-time `review` profile escalation so normal turns remain on
   `core`/`working`, with an explicit return to the smaller surface.
6. Audit rollback of pre-existing scheduler state on Windows, Linux, and macOS.
7. Design the semantic planning schema and keep all external evidence ledgers
   empty until authenticated providers are configured.
8. Port only the external-resource fail-closed preflight.
9. Re-audit the current MemPalace head before implementing the first adapter or
   retrieval experiment.

The default decision remains: improve the verified Python product, preserve
Markdown and review authority, and earn every expansion with product evidence.

The separate
[documentation experience and static site plan](documentation-site-plan.md)
turns this architecture into a progressive public explanation. It keeps the
site static and Node-free, treats every factual claim as source-mapped content,
and isolates any future GitHub Pages workflow in its own security-reviewed
change. The content artifact now lives under [`site/`](../site/README.md): its
home, installation, architecture, and security-model routes are dependency-free.
The repository-level `SECURITY.md` and GitHub Private Vulnerability Reporting now
provide the reviewed reporting path. Pages validation and manual delivery are
isolated by ADR 0259; Pages enablement and dispatch remain separate
approval-gated production operations. During candidate preparation the
documentation kept published 2.0.0 and source-only 2.1 behavior separate; after
the verified RC, the stable 2.1.0 documentation can now describe the wizard,
profiles and idle leases without sending package users to mutable source installs.
