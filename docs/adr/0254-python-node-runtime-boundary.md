# ADR 0254: Python and Node Runtime Boundary

## Status

Accepted for the current architecture by the Codex Operational Owner under
explicit owner-delegated repository authority on 2026-07-26. A transfer of
domain authority to Node requires a separate benchmark gate and ADR.

## Context

The public product is a local CLI and MCP server centered on Markdown,
filesystem safety, SQLite FTS, review workflows, package installation, and
cross-platform process integration. The public `origin/main` baseline at
`0b5c412` has 72 tracked Python files, approximately 40,000 lines of Python, no
tracked JavaScript or TypeScript, no mandatory third-party runtime dependencies,
and CI coverage on Python 3.11 through 3.13 across Windows, Linux, and macOS.

A full Node rewrite would therefore replace mature domain and recovery behavior
before it delivered a distinct user capability. The historical private
checkout contains one exploratory Python/Node proxy, but it used neither the
public commit nor real product paths and is not portable evidence. Current
MemPalace upstream is also Python and demonstrates that backend/source
contracts, queues, hybrid retrieval, temporal relations, and optional local
services do not require a Node domain runtime.

Node can still be a strong build tool for a future browser interface. That is a
separate decision from moving canonical memory authority out of Python.

## Decision

Keep Python as the sole authoritative domain and headless production runtime:

- Python owns canonical Markdown, identity, policy, secrets handling, imports,
  retrieval, generated indexes, review decisions, writers, recovery, CLI, MCP,
  and any local service API.
- Node is not required to install or run the CLI, hooks, scheduler, MCP server,
  maintenance, backup, restore, or migration paths.
- A future TypeScript/React dashboard may own presentation, generated client
  types, and build-time tooling. It must consume a versioned language-neutral
  contract and ship prebuilt assets so headless operation remains Node-free.
- Browser or TypeScript code must not write the vault or duplicate policy
  authority. Every mutation crosses the Python boundary and existing review
  controls.
- Optimize and measure the real Python product before funding a second runtime.
  A Node 24 LTS prototype may be opened only if optimized Python still misses a
  defined hard product SLO or a required integration cannot be delivered
  through the language-neutral boundary.
- A prototype creates evidence, not migration authority. Transfer requires
  contract, security, writer-fencing, recovery, platform, offline packaging,
  maintenance-cost, and rollback parity, plus a material measured advantage on
  every required target and a new owner-accepted ADR.

## Consequences

The project avoids a high-risk big-bang rewrite and can improve the product in
smaller, reversible seams. Python modules should still be decomposed around
domain, application, adapter, and delivery boundaries; keeping Python is not an
endorsement of the current module structure.

If a visual product becomes valuable, a strangler architecture can add it
without duplicating the memory engine. Generated schemas and bidirectional
contract tests become mandatory before the browser surface can mutate state.

## Limitations

Python one-shot startup, packaging, and concurrency may eventually constrain
high-frequency hooks or a warm local service. A two-language visual stack adds
code generation and contributor overhead even without a Node production
runtime. The current repository does not yet contain real-product latency, RSS,
or operating-cost baselines.

## Future Risks

TypeScript DTOs or validation could drift from Python and gradually acquire
domain authority. A dashboard build could accidentally make package installation
depend on Node or network access. Conversely, treating this ADR as permanent
could suppress a future runtime change even if rigorous product evidence later
shows a clear advantage.

## Dependencies

- ADR 0248 defines Python 3.11+ and isolated package namespaces.
- ADR 0253 defines the canonical public baseline for all future measurements.
- `pyproject.toml` defines the installable Python package and console entrypoint.
- `.github/workflows/ci.yml` defines the current cross-platform Python matrix.
- `docs/public-modernization-roadmap.md` defines measurement and migration
  checkpoints.

## Rollback

Any experimental Node or browser plane must be removable without changing
canonical Markdown bytes, IDs, review receipts, or the installed headless
Python path. If contract parity, packaging, security, or rollback fails, disable
that plane and continue on the verified Python baseline.
