# ADR 0247: AI-operated tag releases

## Status

Accepted on 2026-07-10. The no-human-approval authority clauses were superseded
by ADR 0252 on 2026-07-26. ADR 0255 also supersedes the legacy alternate-
publisher clauses. The tag, artifact, OIDC, and provenance controls remain
accepted. ADR 0258 supersedes the automatic post-CI tag trigger and repository
enable-switch clauses.

## Context

The first public snapshot retained a manual `workflow_dispatch` pipeline, PR URL
gate and human acceptance records inherited from the private development vault.
Those controls mixed product acceptance with distribution integrity and rebuilt
similar artifacts across multiple jobs. The original operating model also gave
Codex release authority without a per-release human approval step; that part is
historical and no longer applies.

## Decision

Adopt an AI-operated, human-account-owned model. After explicit authorization
of a release PR and its publication consequence, successful CI on `main` is
necessary but insufficient. ADR 0258's manual tuple-bound dispatch creates the
new immutable version tag. A second manual tuple-bound dispatch of the
canonical publisher validates tag, version, changelog and ancestry, builds
once, smokes the exact wheel and sdist, records checksums and attestations,
publishes through environment-bound OIDC, verifies the index installation and
creates the GitHub Release.

Manual acceptance remains a product-quality subsystem and is not a package
publication gate. The legacy `publish.yml` and `publish-plan` remain a
read-only readiness and compatibility surface; they cannot publish.
Local readiness is included in the owner-authorization handoff, where missing
evidence must be accepted explicitly; `release.yml` does not read private-vault
acceptance receipts or readiness fields.

This supersedes the ordinary approval and manual-dispatch decisions in ADRs
0012, 0016, 0128 and 0235 through 0245 where they conflict with this ADR.

## Safety invariants

- one PyPI version maps to one immutable tag reachable from protected `main`;
- tested and attested bytes are exactly the bytes passed to the publisher;
- no static PyPI token exists;
- Codex cannot bypass rulesets, rewrite tags or overwrite published versions;
- rollback is yank plus fix-forward, never history or artifact replacement;
- legal ownership and destructive break-glass remain human-held.

## Consequences

Repository rules, GitHub environments and both package-index Trusted Publishers
must be configured before release. A TestPyPI RC is required as migration
evidence. Each release requires explicit owner
authorization covering merge, the exact tagger tuple, and the exact publisher
tuple; account recovery and compromise response remain separately
human-controlled.

## Dependencies

- protected `main` and `v*` repository rulesets;
- GitHub environments named `testpypi` and `pypi` without routine reviewers;
- exact Trusted Publisher identities in TestPyPI and PyPI for
  `.github/workflows/release.yml`;
- GitHub Actions artifact attestations and repository OIDC availability.

## Limitations

The AI operator cannot be the legal owner of a GitHub or PyPI account and
cannot recover those accounts independently. The first Trusted Publisher setup
and any later ownership change require the human account owner. Index yanks and
security incidents may also require account-level intervention.

## Future Risks

A compromised protected branch, GitHub Action or publisher identity could turn
automation into a supply-chain amplifier. Pin drift, ruleset bypasses and OIDC
tuple changes must therefore be reviewed as release-security changes. The
legacy read-only preflight should be removed after its compatibility window.
