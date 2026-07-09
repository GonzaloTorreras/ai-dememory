# ADR 0127: Publish Workflow Smoke Gates

## Status

Accepted.

## Context

The manual publish workflow used Trusted Publishing and ran fast repository
preflight checks before building distributions. CI also runs fresh installed
package smoke, package build smoke, and Docker local MCP smoke on pull requests.

The release checklist says TestPyPI should happen only after package and Docker
smoke pass. Relying on a separate CI run leaves a gap when a maintainer manually
dispatches `.github/workflows/publish.yml` from a branch after CI has gone stale
or from a ref that was not the exact checked release candidate.

## Decision

Add the following publish preflight gates before the build job:

- `python scripts/ai_dememory.py install-smoke`
- `python scripts/ai_dememory.py package-build-smoke --check-clean`
- `python scripts/ai_dememory.py install-smoke --skip-package --docker --image ai-dememory:publish`

Keep the build job as a separate job with its own checkout. The smoke gates run
in the preflight workspace; the distribution build still starts from a fresh
workspace and uploads only the `dist/` artifact produced by the build job.

`publish-guard` now requires these smoke commands in addition to the existing
manual dispatch, confirmation, Trusted Publishing, and fast preflight checks.

## Benefits

- Prevents manual publishing from bypassing fresh install and Docker smoke.
- Ties TestPyPI/PyPI uploads to the exact ref selected in the publish workflow.
- Keeps the release checklist, publish workflow, and publish guard aligned.
- Leaves the distribution build workspace clean and isolated from smoke output.

## Limitations

- The publish workflow now depends on Docker availability in GitHub-hosted
  runners.
- The smoke checks increase manual publish runtime.
- This does not record manual acceptance evidence or prove a real MCP client was
  used.
- Trusted Publishing environment configuration still has to be verified in
  GitHub.

## Future Risks

- If Docker availability changes on GitHub-hosted runners, the Docker smoke gate
  may need a documented fallback or a self-hosted runner.
- If publish workflows later run from signed tags, these gates should remain on
  the selected tag ref.
- If package smoke starts producing checkout-local build artifacts, the build job
  must stay isolated from preflight.

## Dependencies

- ADR 0011 defines reusable install and Docker smoke.
- ADR 0012 defines the manual Trusted Publishing guard.
- ADR 0076 defines the publish preflight job.
- ADR 0077 defines package build smoke.
- `.github/workflows/publish.yml` owns the manual package upload flow.
- `scripts/publish_guard.py` enforces the workflow contract.
