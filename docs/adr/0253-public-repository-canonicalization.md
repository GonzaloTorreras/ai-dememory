# ADR 0253: Public Repository Canonicalization

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-26.

## Context

ai-dememory was developed in a former private checkout before a clean public
source and package-distribution repository was established. Both checkouts
later contained useful but divergent work. Treating them as equal authorities
created contradictory documentation, colliding ADR numbers, stale release
claims, repository-bound hashes, and a risk of mixing public fixtures with a
live private vault.

The public repository already contains the released 2.0.0 lineage and the
unreleased 2.1.0 source line. The historical checkout contains later research
and planning, but its dirty-worktree evidence, repository identity, pins, and
release receipts cannot establish facts about public commits.

## Decision

Use `https://github.com/GonzaloTorreras/ai-dememory.git` as the sole canonical
development and package-distribution repository:

- the public remote owns the local name `origin`;
- any retained former private remote is named `archive`, is fetch-only, and has
  its push URL disabled;
- new work starts on a clean `codex/*` branch based on public `origin/main`;
- useful historical work is re-evaluated and ported semantically, never merged
  wholesale and never accepted merely because its files or hashes validate in
  the archive;
- ADRs, plans, threat models, inventories, benchmarks, and release evidence are
  renumbered or regenerated against the public tree;
- the public source checkout, installed executable, and private memory vault
  are distinct resources; `AI_DEMEMORY_ROOT` must identify an explicit vault,
  not the project or its public demo fixtures;
- `memories/**` in this repository remains public test/demo data only;
- line endings for source, contracts, and documentation are normalized through
  `.gitattributes` before introducing reproducibility-sensitive planning
  artifacts.

## Consequences

There is one development history and one release identity. Historical research
can still accelerate design, but every port carries a visible public diff and
new validation evidence. Private memory cannot leak into a package simply
because the project and vault share a checkout.

Repository-bound artifacts from the archive become design inputs, not
attainment. Planning work must prefer semantic projections and versioned
schemas over long chains of raw document hashes; raw commit and blob identities
may remain as provenance without making unrelated prose edits invalidate the
whole plan.

## Limitations

The former checkout may continue to drift and cannot be automatically compared
without a deliberate review. Disabling its push URL reduces accidental writes
but does not prove that all historical content is safe or licensed for public
use. Existing local installations and private vaults must be inspected
separately from either source checkout.

## Future Risks

A new clone could restore the wrong remote naming, or a contributor could copy
archive evidence without regenerating it. Hash-heavy contracts could recreate a
repinning cascade across roadmaps, ledgers, threat models, and value cases.
Release automation could also conflate a source version with a version actually
available on PyPI.

## Dependencies

- ADRs 0247 and 0258 define the public exact-tuple release mechanism.
- ADR 0248 defines the public package namespace and Python baseline.
- ADR 0252 defines agent authority and owner approval boundaries.
- `AGENTS.md` defines the canonical remote and archive handling policy.
- `.gitattributes` defines reproducible text normalization.
- `docs/install.md` defines the separation between tool and vault.

## Rollback

Fail closed if `origin` does not resolve to the canonical public repository, the
working branch is not based on public `main`, or a proposed artifact depends on
unreviewed archive identity. Restoring the private checkout as an authority
would require a new owner-accepted ADR, a clean public provenance migration, a
secret/license review, and replacement release evidence.
