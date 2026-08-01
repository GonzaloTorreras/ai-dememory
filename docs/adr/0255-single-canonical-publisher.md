# ADR 0255: Single Canonical Package Publisher

## Status

Accepted by the Codex Operational Owner under explicit owner-delegated
repository authority on 2026-07-26.

## Context

The repository had two workflows capable of package publication:
`.github/workflows/release.yml`, driven by immutable version tags, and the
older manual `.github/workflows/publish.yml`. Active documentation called the
latter a compatibility or recovery surface while it still requested OIDC,
targeted PyPI environments, built and transferred artifacts, and invoked the
PyPI publisher action. That was an alternate publisher, not a read-only
fallback, and contradicted the stated single-release-path design.

Multiple publisher identities expand the supply-chain attack surface, allow
branch-built bytes to diverge from tag-built bytes, and make authorization and
recovery semantics ambiguous.

## Decision

Use `.github/workflows/release.yml` as the sole package publisher:

- only the canonical workflow may request `id-token: write`, target the
  `testpypi` or `pypi` environment, transfer release artifacts to a publishing
  job, invoke the PyPI publisher action, or create the GitHub Release;
- PyPI and TestPyPI Trusted Publisher identities must reference only
  `.github/workflows/release.yml` and the matching environment;
- normal publication begins with an explicitly authorized immutable tag;
- recovery re-dispatches `.github/workflows/release.yml` for that existing tag
  with `confirm=recover-<tag>` and never rebuilds from an arbitrary branch;
- `.github/workflows/publish.yml` remains temporarily as a manual read-only
  readiness preflight, requires `confirm=preflight`, has only
  `contents: read`, disables persisted checkout credentials, and cannot request
  write permission, target an environment, upload/download artifacts, create a
  release, push, or invoke a package upload;
- `publish-plan` retains its name and response fields for compatibility but
  reports `uses_trusted_publishing=false`; its hosted workflow URL identifies
  the read-only preflight, not publication authority;
- `testpypi-publish` manual acceptance requires revision 2 evidence from the
  canonical immutable-tag workflow and exact-version post-index install;
  unversioned or revision-1 passes from the old publisher remain auditable but
  do not complete the current local acceptance/readiness signal;
- `publish-guard` inventories every checked-in workflow and rejects known
  publishing markers, package-registry permissions, and stored-secret
  references outside `release.yml`, including any return of publishing
  capability to the legacy workflow.

ADR 0255 supersedes publication clauses in ADRs 0012, 0076, 0077, 0127, 0128,
0236, 0237, 0238, 0239, 0240, 0245, and the legacy-workflow clause in ADR 0247
where they conflict. Their historical motivation and still-valid read-only
evidence contracts remain; ADRs 0237-0239 now describe readiness-only
compatibility surfaces.

## Consequences

Every released byte is built from one validated immutable tag, tested and
attested once, published through one OIDC identity, installed back from the
target index, and attached to one GitHub Release. The legacy preflight can still
exercise expensive hosted smokes without possessing release authority.

The compatibility names `publish.yml`, `publish-plan`, and `publish_ready` are
temporarily less precise than their behavior. Documentation and structured
output must therefore state that they are readiness-only.

## Limitations

Repository code cannot inspect package-index Trusted Publisher configuration or
prove that no stale external identity remains. That configuration must be
verified through the owning accounts before enabling release automation. The
legacy workflow still consumes hosted runner time and its name may confuse new
contributors until it is removed. Static marker inspection is defense in depth,
not a semantic proof that arbitrary code cannot implement a novel upload path;
all workflow changes still require supply-chain review.

## Future Risks

A later edit could restore OIDC, environment, artifact, token, release, or push
capability to the legacy workflow, or add a third publisher under a new
filename. Guard coverage and security review must treat any workflow permission
or release-surface change as supply-chain-sensitive.

## Dependencies

- ADR 0247 defines immutable tag releases and exact-artifact verification.
- ADR 0252 separates technical readiness from owner authorization.
- ADR 0258 defines the manual exact tag/commit authorization boundary.
- `.github/workflows/release.yml` is the sole publisher.
- `.github/workflows/tag-release.yml` creates an authorized release tag only
  after a manual tag/SHA-bound dispatch and green current-main CI readback.
- `scripts/publish_guard.py` enforces publisher uniqueness and legacy
  preflight restrictions.

## Rollback

Fail closed by leaving the manual tag workflow undispatched and the legacy
preflight read-only. Recover an interrupted release only from its existing
immutable tag through `.github/workflows/release.yml`. Reintroducing another publisher
requires a new owner-accepted ADR, explicit authorization, threat review,
environment/OIDC inventory, exact-artifact parity, and rollback evidence.
