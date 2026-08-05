# ADR 0257: Bounded Autonomy and Resource Profiles

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-26.

## Context

The first-run flow exposed many independent switches but did not give a user one
reviewable answer to three practical questions: how much background work will
run, how much memory/model context can be consumed, and which operations an
agent may see. Scheduler names were global, provider scans could do more work
than a small vault needed, generated MCP configs depended on client-side
allowlists, and setup health did not distinguish a manually runnable vault from
a verified autonomous installation.

Package installation must remain passive. An easy setup path must not silently
install host jobs, read provider histories, capture raw prompts, call remote
models, enable embeddings, or promote durable memory. At the same time, advanced
users need a bounded way to opt into more recall, imports, working-session tools,
and review-first proposals.

## Decision

Define three versioned resource intensities:

- `minimal`: manual recall, the four-tool `core` MCP profile, no daily job,
  one weekly job, and the smallest import, context, report, timeout, and hook
  queue budgets;
- `balanced`: the default, with bounded per-turn recall, `core`, daily and
  weekly one-shot maintenance, and moderate budgets;
- `active`: larger bounded budgets, the `working` MCP profile, daily and weekly
  maintenance, and opt-in hook metadata for frequently changing vaults.

Every configurable numeric resource has an absolute minimum and maximum.
Out-of-range or malformed configuration fails policy validation rather than
silently escaping those ceilings. Provider traversal is bounded by candidate
count, bytes per file, and scanned directory entries; it does not follow
symlinks. Maintenance report retention and pending hook captures are capped.
Maintenance owns every external child in a separate process group/tree. A
deadline terminates and reaps that complete owned tree, including grandchildren;
Git children receive closed stdin, non-interactive environment, bounded output,
and a deadline. Windows children start suspended, are assigned to a
kill-on-close Job Object, and resume only after assignment; POSIX children use
an owned session/process group. Canonical scans, secret
scans, graph pages, MCP frames/queues, captured output, and generated SQLite
history also have non-configurable hard ceilings.

Separate resource intensity from host-model policy:

- `off` uses deterministic local tools only;
- `advisory` permits the already active host agent to triage and recommend;
- `proposals` permits that host agent to create review-first inbox proposals.

All three policies make zero model and embedding calls from the ai-dememory
runtime. They never promote durable memory automatically. Any tokens consumed
by an already running Codex, Claude, or other host agent remain host usage and
must not be described as free or as ai-dememory background inference.

The initial wizard previews the selected policy, hard caps, vault-bound MCP
configuration, public-only hook configuration, and scheduler plan. Its only
planned write is `.ai-dememory.toml`. In the human-guided TTY flow it retains
the answers in memory, prints the exact preview fingerprint, and asks once
whether to apply that exact plan. A decline writes nothing and exits as
incomplete. `setup wizard --json`, stdin, input-file, and explicit dry-run flows
remain passive and require a separate apply bound to the exact preview
fingerprint. Optional `onboard` uses an independent fingerprint and writes only
reviewed personal/project Markdown. Neither surface installs MCP config, hooks,
providers, or scheduler jobs.

Generated MCP configurations use an explicit vault, the selected
server-enforced profile, and `--require-bound-root`. The server filters
`tools/list`, rejects calls outside the selected profile, and withholds
resources and prompts outside `admin`; a client allowlist is defense in depth,
not the authorization boundary. The checked-in public plugin uses a separate
three-tool `public` profile that server-forces public-only recall, excludes
sensitive data, and disables working-memory injection.

Scheduler plans use vault-specific task namespaces and an exact plan
fingerprint. Definitions are created exclusively, never force-replaced. Setup
reads back the created host definitions, persists their SHA-256 receipt, and
rolls back jobs and files if readback or receipt persistence fails. Later
`schedule status` records verification only when the exact definitions still
match and the verification timestamp is fresh. A moved vault continues to
address the receipt's original task namespace for status/removal and local
systemd/launchd definition cleanup. The installed receipt, not later
resource-policy defaults, remains authoritative for cadence and intensity
during status and complete removal. Windows
rollback restores the exact captured task XML; removal performs the same
comparison and restores already removed jobs on partial failure. Docker jobs
require an immutable image digest, use no network, and apply
intensity-specific CPU, memory, and PID limits.

Setup health reports separate `manual_maintenance_ready`,
`automation_ready`, and `autonomy_ready` states. A valid local vault is not
reported autonomous merely because maintenance can be run manually.

## Consequences

The default installation has a small model-visible schema, bounded local work,
zero ai-dememory model calls, and no automatic host mutation. Users can choose a
larger operating envelope without changing the canonical-memory or human-review
contract. Generated configs are safe for clients that do not implement their
own tool allowlist.

The wizard and status payloads are larger because they expose catalogs, caps,
fingerprints, and readiness evidence. That cost is paid during setup and
inspection, not on every recall turn. `active` can still consume substantial
host-agent context, filesystem I/O, and CPU relative to `minimal`; the name is
an operating envelope, not a promise of fixed machine cost.

## Limitations

The Python process cannot forcibly pre-empt arbitrary pure-Python work in the
same interpreter. External work is tree-supervised and operations remain
interruptible and one-shot. Scheduled Docker mode adds CPU, memory, PID, and
wall-clock limits. Installed Windows/macOS/Linux mode guarantees owned-tree
cleanup and wall-clock deadlines; it does not claim native CPU or memory quotas.

Exclusive creation prevents ai-dememory from replacing a pre-existing
same-name task or definition. A same-user actor can still race or alter host
state after verification; the exact receipt detects that drift on the next
status/removal check but cannot prevent host-admin mutation.

The current profiles are policy presets, not measured performance SLOs. Peak
RSS, cold start, warm recall latency, real provider-scan throughput, and
host-model token usage still require reproducible benchmarks on representative
vault sizes.

## Future Work

- Add incremental maintenance checkpoints and no-op runs.
- Extend the current stale-lock lease and crash-recovery tests with
  cross-process interruption/fencing coverage.
- Publish Windows, Linux, and macOS latency/RSS/resource baselines by profile.
- Measure actual host-agent token use separately from deterministic runtime
  work and offer just-in-time escalation to `review` only when needed.
- Exercise exact scheduler readback and compensating rollback on real Windows,
  Linux, and macOS hosts.
- Revisit defaults only from real recall, resource, and operator-friction
  evidence.

## Dependencies

- ADR 0249 defines MCP tool profiles; this ADR upgrades them from client
  exposure hints to server-enforced capability boundaries.
- ADR 0250 defines prompt-aware recall and fingerprint-bound onboarding.
- ADR 0253 separates the public source repository from private vaults.
- ADR 0256 defines the public-only recall ceiling.
- `scripts/resource_policy.py` defines profiles, host-model policies, and hard
  limits.
- `scripts/onboarding.py` and `scripts/setup_plan.py` expose reviewed setup and
  readiness.
- `scripts/schedule_memory.py`, `scripts/provider_import.py`, and
  `scripts/hook_event.py` enforce bounded recurring work.
- `mcp/server/memory_mcp.py` enforces the selected MCP profile.

## Rollback

Select `minimal` with model policy `off`, disable scheduled jobs and hook
metadata, and keep recall manual. If profile validation or scheduler receipt
verification fails, do not install or run autonomous work. Direct CLI
maintenance remains available as a reviewed one-shot fallback.
