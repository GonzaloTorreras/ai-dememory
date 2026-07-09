# ADR 0236: Publish Plan

## Status

Accepted

## Context

The publish workflow is already protected by `publish-guard`, manual
`workflow_dispatch`, explicit `confirm=publish`, Trusted Publishing
environments, package smoke, package build smoke, and Docker smoke. Release
evidence also reports whether manual acceptance, recall review, and automated
checks still block release.

Before running the manual GitHub Actions workflow, maintainers still need one
read-only local command that combines those signals into a concrete publish
handoff: which repository target will be selected, which dispatch inputs are
required, which preflight commands will run, and which release blockers remain.

## Decision

Add `ai-dememory publish-plan`.

The command returns a read-only plan for `--repository testpypi` or
`--repository pypi`. It reports:

- workflow path and target environment;
- required `workflow_dispatch` inputs;
- publish workflow guard issues;
- release evidence availability, readiness, blocker ids, manual acceptance
  remaining count, and recall fixture status;
- preflight command arrays derived from `publish-guard`'s required preflight
  contract; and
- next actions for unresolved blockers and explicit human approval.

The plan may run local read-only inspection commands, including git status and
remote URL checks, to collect release evidence and resolve the workflow URL. It
does not run publish workflow commands, run the listed preflight commands, write
files, publish packages, contact PyPI, or record manual acceptance evidence. In
a plain vault or non-git checkout, it returns
`release_evidence_available=false` instead of failing.

## Consequences

- Maintainers get a single pre-publish handoff before dispatching the manual
  workflow.
- TestPyPI remains the default target.
- PyPI plans remind maintainers to publish to TestPyPI and verify install
  evidence first.
- Installed package smoke can exercise the command from a plain vault without
  requiring a distribution checkout.

## Limitations

- The command cannot verify external PyPI/TestPyPI Trusted Publisher settings
  or GitHub environment protection rules.
- It does not prove the publish workflow has run.
- It does not replace manual acceptance records, real TestPyPI verification, or
  explicit human approval to publish.

## Future Work

- Add optional GitHub API lookup for workflow existence or latest run URLs only
  if a connector-backed release dashboard needs live metadata.
- Add a post-TestPyPI verification planner after the first real TestPyPI
  publish records the expected artifact evidence.
- Include signed tag guidance if package publishing moves from branches to
  release tags.

## Dependencies

- ADR 0012 defines the manual Trusted Publishing guard.
- ADR 0076 defines publish workflow preflight gates.
- ADR 0127 defines package and Docker smoke gates in publish preflight.
- ADR 0128 defines TestPyPI manual acceptance evidence requirements.
- ADR 0235 defines release evidence handoff commands.
- ADR 0240 defines offline workflow URL resolution.
- `scripts/publish_guard.py` owns the executable publish workflow contract.
- `.github/workflows/publish.yml` owns the manual package upload flow.

## References

- `scripts/publish_plan.py`
- `scripts/publish_guard.py`
- `.github/workflows/publish.yml`
- `docs/distribution.md`
- `tests/test_memory_tools.py`
