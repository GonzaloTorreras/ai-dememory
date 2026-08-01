# ADR 0012: Manual Trusted Publishing Guard

## Status

Superseded for publication behavior by ADR 0255 on 2026-07-26. Historical
rationale is retained; the current guard permits Trusted Publishing only in
`.github/workflows/release.yml` and requires `.github/workflows/publish.yml` to
remain a read-only preflight.

## Context

`ai-dememory` is intended to publish through GitHub Actions Trusted
Publishing. Publishing must remain explicit because package upload is a
distribution action, and the workspace policy forbids package publishing without
user approval.

The repository already has `.github/workflows/publish.yml`, but previous
release checks only confirmed that the file existed. They did not verify that
the workflow stayed manual-only, required confirmation, used PyPI environments,
or avoided stored PyPI tokens.

## Decision

Historical decision, superseded as described in Status: the original v2 draft
added `ai-dememory publish-guard`, backed by
`scripts/publish_guard.py`.

The original guard validated that the manual publisher:

- runs from `workflow_dispatch`
- does not run on push, pull request, or schedule
- requires `confirm=publish`
- supports explicit `testpypi` and `pypi` repository choices
- uses GitHub environments `testpypi` and `pypi`
- requests `id-token: write` for Trusted Publishing
- uses `pypa/gh-action-pypi-publish`
- builds distributions and runs `twine check`
- does not configure stored PyPI token/password fields

`release-check` fails if the guard reports issues.

ADR 0255 retained the command but inverted the legacy-workflow contract. The
current guard validates `release.yml` as the sole immutable-tag publisher and
rejects OIDC, environments, artifacts, pushes, releases, or uploads in
`publish.yml`.

## Benefits

- Makes accidental automatic package publishing less likely.
- Keeps TestPyPI/PyPI setup reviewable in source control.
- Gives maintainers a local preflight before running the manual workflow.
- Preserves the explicit user-approval boundary for package uploads.

## Limitations

- The guard statically inspects workflow text; it does not prove GitHub
  environment trusted publishers are configured in PyPI/TestPyPI.
- It does not publish, build artifacts, or contact PyPI.
- It cannot verify GitHub environment protection rules from the local checkout.

## Future Risks

- Workflow YAML refactors may require updating text checks.
- Future registry publishing, such as an MCP registry, should use a separate
  guard because PyPI Trusted Publishing requirements do not cover it.
- If publishing becomes multi-package, the guard must verify each package job
  independently.
