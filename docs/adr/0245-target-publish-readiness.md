# ADR 0245: Target Publish Readiness

## Status

Accepted.

## Context

`release_ready` is the final release-evidence gate. It requires a clean
worktree, no automated warnings or failures, fresh reviewed recall evidence, and
all manual acceptance records. One manual acceptance item is
`testpypi-publish`, but that record can exist only after a TestPyPI publish
workflow has actually run.

Using final `release_ready` as the precondition for TestPyPI dispatch therefore
creates a loop: TestPyPI cannot run until `release_ready` is true, but
`release_ready` cannot become true until TestPyPI evidence exists.

## Decision

Add target-specific `publish_ready` to `ai-dememory publish-plan`.

- For `testpypi`, `publish_ready` may defer only the `testpypi-publish`
  acceptance item.
- For `pypi`, `publish_ready` requires full `release_ready`.
- Publish guard now requires the manual workflow to accept a PR URL, export it
  as `AI_DEMEMORY_PR_URL`, and run `publish-plan --strict` after package and
  Docker smoke.
- The publish-plan payload keeps final `release_ready` so reviewers can see
  whether the overall release is complete before real PyPI.

## Consequences

- TestPyPI can be used to generate the evidence needed for final release
  readiness without weakening other release blockers.
- Real PyPI remains blocked until TestPyPI evidence and every other acceptance
  item are recorded.
- Publish workflow dispatches carry PR review context into release checks and
  MCP runtime gates through `AI_DEMEMORY_PR_URL`.
- The workflow can still be dispatched only after explicit approval and the
  configured GitHub environment protections.

## Limitations

- `publish_ready` is a dispatch gate, not proof that a package was published or
  installed successfully.
- The target-specific exception applies only to the TestPyPI evidence item; it
  cannot bypass the recall release gate, PR URL, Docker smoke, or other
  acceptance records.
- Local `publish-plan --strict` cannot verify GitHub environment reviewer
  configuration or PyPI/TestPyPI Trusted Publisher settings.

## Future Work

- Record TestPyPI workflow URL and fresh install evidence with
  `ai-dememory acceptance record --item testpypi-publish`.
- Re-run `ai-dememory publish-plan --repository pypi --strict` before real PyPI.
- Add live GitHub environment and PyPI publisher inspection if a connector or
  authenticated CLI path becomes available in release automation.

## Dependencies

- ADR 0012 defines the manual Trusted Publishing guard.
- ADR 0128 defines TestPyPI acceptance evidence requirements.
- ADR 0236 defines `ai-dememory publish-plan`.
- ADR 0243 defines release-evidence PR URL metadata.
- `.github/workflows/publish.yml` owns the manual publish workflow.
- `scripts/publish_plan.py` owns target-specific publish readiness.
