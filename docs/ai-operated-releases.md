# AI-Operated Releases

## Ownership model

ai-dememory is **AI-operated and human-account-owned**. Codex has standing
operational authority to maintain the repository, create and merge release
changes, update versions and changelog entries, create immutable tags, publish
packages and perform fix-forward recovery when automated gates pass. Gonzalo's
account or a future organization remains the legal GitHub and PyPI owner and
the destructive break-glass authority.

Routine release publication has no human approval step. This deliberately
differs from the Python Packaging Guide's conservative recommendation to place
manual approval on the `pypi` environment. Equivalent release safety is moved
to protected source control, immutable identity, exact-artifact verification,
OIDC scoping, provenance and post-publish checks.

## Canonical flow

1. Codex prepares a normal PR that changes `project.version` and adds a dated
   `CHANGELOG.md` section. Product acceptance reports may accompany the PR but
   do not gate package integrity.
2. CI runs compile, schema, secret, MCP, release, unit, install, package and
   Docker smokes. A fresh read-only reviewer checks the PR before Codex merges.
3. After successful CI on `main`, `tag-release.yml` derives `v<version>` and
   creates the annotated tag only when it does not already exist.
4. `release.yml` validates repository identity, tag syntax, tag-version-
   changelog alignment and ancestry from `origin/main`.
5. The workflow builds wheel and sdist once, runs `twine check`, installs and
   executes both exact artifacts in isolated environments, generates SHA-256
   checksums and records GitHub artifact attestations.
6. PEP 440 prereleases publish to TestPyPI; final versions publish to PyPI.
   Publishing uses the tag, workflow filename and GitHub environment as the
   Trusted Publisher OIDC identity. No static package token is stored.
7. The workflow installs the exact version from its target index, checks the
   CLI and then creates the GitHub Release with artifacts and checksums.

## Migration switch

The `AI_RELEASE_ENABLED` repository variable is intentionally absent or false
during setup. Enable it only after all of these are true:

- `main` and `v*` rulesets are active;
- GitHub environments `testpypi` and `pypi` exist without ordinary reviewers;
- PyPI and TestPyPI Trusted Publishers point exactly to
  `GonzaloTorreras/ai-dememory`, `.github/workflows/release.yml`, and their
  matching environment;
- an RC tag has completed the TestPyPI and post-install path;
- the recovery runbook has been exercised without uploading a duplicate.

Once enabled, a green CI run on `main` with a new version is sufficient to
complete the release without a human-in-the-loop.

## Recovery and rollback

`release.yml` also accepts a manual recovery dispatch for an existing tag and
requires the exact confirmation `recover-<tag>`. It checks out and republishes
only that immutable identity. PyPI versions and tags are never overwritten or
reused. If an artifact is already present, compare index hashes with
`SHA256SUMS`; mismatch is an incident, not a reason to use `skip-existing`.

For a bad release:

1. preserve the tag, workflow run and attestation;
2. yank the PyPI version with a public reason;
3. annotate the GitHub Release and open an incident issue;
4. fix forward with a new patch version and changelog entry;
5. never delete the release as a substitute for provenance.

Human action is reserved for account recovery, legal or billing changes,
trusted-publisher ownership changes, compromise and destructive break-glass.

## Lessons incorporated from Clawpatch

- one canonical release workflow owns validation, publication and GitHub
  Release creation;
- tag-version-changelog alignment is checked before publishing;
- the packed artifact is installed into an isolated temporary environment and
  the installed CLI is exercised against a synthetic fixture;
- release evidence includes package URLs, checksums, CI/run URLs and test proof;
- workflow, documentation and agent-facing release instructions are changed
  together so release skills cannot drift from the actual OIDC path.
