# ADR 0127: Publish Workflow Smoke Gates

## Status

Accepted for hosted readiness smoke. Its publication and artifact-handoff
clauses were superseded by ADR 0255 on 2026-07-26; the legacy workflow is
read-only and discards smoke artifacts.

## Context

The manual publish workflow used Trusted Publishing and ran fast repository
preflight checks before building distributions. CI also runs fresh installed
package smoke, package build smoke, and Docker local MCP smoke on pull requests.

The release checklist says TestPyPI should happen only after package and Docker
smoke pass. Relying on a separate CI run leaves a gap when a maintainer manually
dispatches `.github/workflows/publish.yml` from a branch after CI has gone stale
or from a ref that was not the exact checked release candidate.

## Decision

Historical decision, superseded as described in Status: the original publisher
added the following preflight gates before its build job:

- `python scripts/ai_dememory.py install-smoke`
- `python scripts/ai_dememory.py package-build-smoke --check-clean`
- `python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:publish`

The original design kept the build job separate and uploaded only its `dist/`
artifact.

ADR 0255 removed both the build and publisher from this workflow. The smoke
commands remain as readiness diagnostics, and `publish-guard` now requires
manual `confirm=preflight`, read-only permissions, and no release capability.

## Benefits

- Prevents hosted readiness claims from bypassing fresh install and Docker
  smoke.
- Keeps the release checklist, compatibility workflow, and publish guard
  aligned.
- Discards smoke output instead of handing it to a publisher.

## Limitations

- The publish workflow now depends on Docker availability in GitHub-hosted
  runners.
- The smoke checks increase hosted preflight runtime.
- This does not record manual acceptance evidence or prove a real MCP client was
  used.
- Trusted Publisher configuration for the canonical `release.yml` workflow
  still has to be verified externally.

## Future Risks

- If Docker availability changes on GitHub-hosted runners, the Docker smoke gate
  may need a documented fallback or a self-hosted runner.
- Canonical signed-tag validation belongs to `release.yml`; this preflight must
  not claim equivalent provenance.
- If package smoke starts producing checkout-local build artifacts, the
  workflow must continue to discard them.

## Dependencies

- ADR 0011 defines reusable install and Docker smoke.
- ADR 0255 defines the current sole-publisher boundary.
- ADR 0076 defines the publish preflight job.
- ADR 0077 defines package build smoke.
- `.github/workflows/publish.yml` owns only the hosted read-only preflight.
- `scripts/publish_guard.py` enforces the workflow contract.
