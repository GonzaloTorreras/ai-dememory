# ADR 0247: AI-operated tag releases

## Status

Accepted on 2026-07-10.

## Context

The first public snapshot retained a manual `workflow_dispatch` pipeline, PR URL
gate and human acceptance records inherited from the private development vault.
Those controls mixed product acceptance with distribution integrity and rebuilt
similar artifacts across multiple jobs. The intended operating model now gives
Codex routine repository and release authority without a human approval step.

## Decision

Adopt an AI-operated, human-account-owned model. Successful CI on `main` may
create a new immutable version tag. A canonical tag-triggered workflow validates
tag, version, changelog and ancestry, builds once, smokes the exact wheel and
sdist, records checksums and attestations, publishes through environment-bound
OIDC, verifies the index installation and creates the GitHub Release.

Manual acceptance remains a product-quality subsystem and is not a package
publication gate. The legacy `publish.yml` and `publish-plan` remain a recovery
and compatibility surface during migration, not the normal release path.

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
must be configured once before enabling `AI_RELEASE_ENABLED`. A TestPyPI RC is
required as migration evidence. Ordinary releases then proceed without human
approval; account recovery and compromise response do not.

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
tuple changes must therefore be reviewed as release-security changes, and the
legacy workflow should be removed after the migration window.
