# ADR 0245: Target Publish Readiness

## Status

Accepted as target-specific readiness evidence. ADR 0255 superseded direct
dispatch to `publish.yml` on 2026-07-26; the field now scores local planning
for the canonical immutable-tag release and does not grant or revoke
publication capability.

## Context

`release_ready` is the aggregate local release-evidence signal. It requires a
clean worktree, no automated warnings or failures, fresh reviewed recall
evidence, and all manual acceptance records. One manual acceptance item is
`testpypi-publish`, but that record can exist only after the canonical
prerelease workflow has published to TestPyPI.

Using final `release_ready` as the precondition for a prerelease tag therefore
creates a loop: TestPyPI cannot run until `release_ready` is true, but
`release_ready` cannot become true until TestPyPI evidence exists.

## Decision

Add target-specific `publish_ready` to `ai-dememory publish-plan`.

- For `testpypi`, `publish_ready` may defer only the `testpypi-publish`
  acceptance item.
- Within `publish-plan`, `pypi` `publish_ready` requires full local
  `release_ready`.
- Publish guard requires the legacy hosted preflight to accept a PR URL, export
  it as `AI_DEMEMORY_PR_URL`, and run `publish-plan --strict` after package and
  Docker smoke, without granting it publication capability.
- The publish-plan payload keeps final `release_ready` so reviewers can see
  whether the overall release is complete before real PyPI.

## Consequences

- TestPyPI can be used to generate the evidence needed for final release
  readiness without weakening other release blockers.
- The local PyPI planner remains not ready by default until TestPyPI evidence
  and every other acceptance item are recorded. The canonical publisher does
  not consume this field.
- Hosted preflight runs carry PR review context into release checks and MCP
  runtime gates through `AI_DEMEMORY_PR_URL`.
- Publication still requires an explicitly authorized immutable tag and the
  canonical `release.yml` environment protections.

## Limitations

- `publish_ready` is compatibility-named readiness evidence, not proof or
  authorization that a package was published or installed successfully.
- The target-specific exception applies only to the TestPyPI evidence item; it
  cannot bypass the other local readiness checks used by the planner.
- `release.yml` cannot read private-vault receipts and does not enforce
  `release_ready` or `publish_ready`; missing evidence must instead be
  disclosed in the explicit owner-authorization handoff.
- Local `publish-plan --strict` cannot verify GitHub environment reviewer
  configuration or PyPI/TestPyPI Trusted Publisher settings.

## Future Work

- Record TestPyPI workflow URL and fresh install evidence with
  `ai-dememory acceptance record --item testpypi-publish`.
- Re-run `ai-dememory publish-plan --repository pypi --strict` before
  requesting authorization for a stable tag, or disclose every remaining
  local-readiness exception in that request.
- Add live GitHub environment and PyPI publisher inspection if a connector or
  authenticated CLI path becomes available in release automation.

## Dependencies

- ADR 0255 defines the sole canonical publisher.
- ADR 0128 defines TestPyPI acceptance evidence requirements.
- ADR 0236 defines `ai-dememory publish-plan`.
- ADR 0243 defines release-evidence PR URL metadata.
- `.github/workflows/release.yml` owns publication.
- `.github/workflows/publish.yml` owns only the hosted read-only preflight.
- `scripts/publish_plan.py` owns target-specific publish readiness.
