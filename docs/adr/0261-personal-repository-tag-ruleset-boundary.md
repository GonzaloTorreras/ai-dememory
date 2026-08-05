# ADR 0261: Personal Repository Tag Ruleset Boundary

## Status

Accepted by the repository owner on 2026-08-05 as a correction to the
pre-release 2.1 security model.

## Context

The release runbook and checklist said that the `v*` repository ruleset
rejected tag creation except for the native GitHub Actions integration used by
`.github/workflows/tag-release.yml`. Live API verification against the current
personal repository rejected that configuration with HTTP 422: the GitHub
Actions integration is not part of the personal ruleset source or an owner
organization.

Adding a creation rule without a valid bypass would block the guarded tagger.
Using an owner/admin bypass and creating tags directly would weaken the
auditable exact-tuple workflow. Adding a static credential to Actions would
weaken the OIDC-only release model. The documented configuration was therefore
not merely pending; it was unavailable in the current ownership topology.

## Decision

Use the strongest configuration that matches the real personal-repository
trust boundary:

- keep the active `v*` ruleset enforcement for deletion and non-fast-forward
  updates, so an existing release tag cannot be removed or retargeted;
- do not claim a creation-rule bypass that GitHub refuses to configure;
- create releases only through the manual, exact-tuple
  `.github/workflows/tag-release.yml` path, which rechecks current `main`, green
  push CI, version/changelog identity, collisions and the explicit confirmation
  tuple before creating an annotated tag;
- keep `.github/workflows/release.yml` manual and separate. A direct tag never
  triggers publication, and publication still requires the same tag/SHA tuple,
  environment-bound OIDC, artifact validation and post-index installation;
- treat the personal owner account, its authenticated Codex session and
  repository write access as one honest trust domain. There is no collaborator
  or second GitHub identity to distinguish cryptographically;
- if the repository moves to an organization or a dedicated tagger GitHub App
  is installed, add the tag-creation rule with only that installed integration
  as bypass, validate it with a canary tag, and update this ADR before claiming
  creation is ruleset-enforced.

## Consequences

- Documentation, checklist and live GitHub configuration agree.
- The checklist guard rejects reintroduction of the impossible native Actions
  creation-bypass claim and requires the effective immutability boundary.
- Published and candidate tags remain immutable after creation.
- Tag authorization and package publication remain separate, explicit and
  bound to one exact commit.
- A compromised sole-owner account can still create a new tag or dispatch a
  workflow. That is already the repository's ultimate administrative trust
  boundary and must not be disguised as independent enforcement.
- Moving to an organization or dedicated App can narrow creation authority
  later without changing artifact or publisher identity.

## Rejected Alternatives

- Native GitHub Actions integration bypass: rejected by GitHub for this
  personal repository.
- Creation rule with no bypass: blocks the approved tagger.
- Temporary ruleset disablement around each release: creates an unnecessary
  mutable-policy window and poor audit semantics.
- Owner/admin bypass plus direct API tags: bypasses the canonical guarded
  tagger.
- Static PAT stored in Actions: adds a long-lived release credential and
  weakens the OIDC-only design.

## Limitations

- Repository write access can create a new tag outside the tagger, although it
  cannot publish through the current workflow topology by tag push alone.
- The protection is strongest for existing tags; creation narrowing awaits an
  organization-owned or dedicated installed integration.
- GitHub account recovery and destructive administrative control remain human
  owner responsibilities.

## Future Risks

- A future workflow could add a tag-push publication trigger and turn direct
  creation into publication authority.
- New collaborators would widen the writer set and require reassessing this
  personal-owner exception before granting write access.
- A ruleset or ownership-topology change could make these statements stale;
  release preflight must continue to read live configuration.

## Rollback

Freeze releases and leave the existing deletion/non-fast-forward rules active.
Only replace this boundary after an organization or dedicated installed App
has been verified as the sole creation bypass and the tagger succeeds on a
non-release canary without gaining publisher authority.

## Dependencies

- ADR 0247 defines AI-operated, owner-account-held releases.
- ADR 0255 defines the single canonical OIDC publisher.
- ADR 0258 defines separate exact-tuple tag and publication dispatches.
- ADR 0260 records the sole-owner review trust domain.
- `docs/ai-operated-releases.md` is the release runbook.
- `docs/release-v2-checklist.md` is the manual acceptance surface.
- `scripts/release_checklist_guard.py` keeps that surface aligned with this
  decision.
