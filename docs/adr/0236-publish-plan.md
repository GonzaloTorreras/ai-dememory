# ADR 0236: Publish Plan

## Status

Accepted as a read-only compatibility API. Publication and
`confirm=publish` clauses were superseded by ADR 0255 on 2026-07-26.

## Context

The original publish plan described a manual Trusted Publishing workflow.
ADR 0255 made the immutable-tag-driven `release.yml` workflow the sole
publisher and reduced `publish.yml` to a manual, read-only hosted readiness
preflight. Release evidence still reports whether manual acceptance, recall
review, and automated checks block the canonical release.

Maintainers still need one read-only local command that combines those signals:
which target index is being evaluated, which legacy preflight inputs are
required, which inspection commands run, and which release blockers remain.

## Decision

Add `ai-dememory publish-plan`.

The command returns a read-only plan for `--repository testpypi` or
`--repository pypi`. It reports:

- legacy preflight path and target index under evaluation;
- required `workflow_dispatch` inputs;
- canonical-release and legacy-preflight guard issues;
- release evidence availability, readiness, blocker ids, manual acceptance
  remaining count, and recall fixture status;
- preflight command arrays derived from `publish-guard`'s required preflight
  contract; and
- next actions for unresolved blockers and explicit owner authorization.

The plan may run local read-only inspection commands, including git status and
remote URL checks, to collect release evidence and resolve the workflow URL. It
does not run hosted workflow commands, run the listed preflight commands, write
files, publish packages, contact package indexes, request Trusted Publishing,
or record manual acceptance evidence. It reports
`uses_trusted_publishing=false` and `confirm=preflight`. In a plain vault or
non-git checkout, it returns
`release_evidence_available=false` instead of failing.

## Consequences

- Maintainers get one readiness handoff before deciding whether a canonical
  immutable-tag release can be authorized.
- TestPyPI remains the default target.
- PyPI plans require TestPyPI and install evidence first.
- Installed package smoke can exercise the command from a plain vault without
  requiring a distribution checkout.
- The names `publish-plan` and `publish_ready` remain for API compatibility and
  do not imply publication capability.

## Limitations

- The command cannot verify external PyPI/TestPyPI Trusted Publisher identities
  or GitHub environment protection rules.
- It does not prove the legacy preflight or canonical release has run.
- It does not replace manual acceptance records, real TestPyPI verification, or
  explicit owner authorization to merge, tag, or publish.

## Future Work

- Add optional GitHub API lookup for workflow existence or latest run URLs only
  if a connector-backed release dashboard needs live metadata.
- Remove the compatibility workflow and rename response fields in the next
  breaking API version if usage evidence shows they are no longer needed.

## Dependencies

- ADR 0255 defines the sole tag-driven publisher and legacy preflight boundary.
- ADR 0076 and ADR 0127 retain the historical preflight and smoke rationale.
- ADR 0128 defines TestPyPI manual acceptance evidence requirements.
- ADR 0235 defines release evidence handoff commands.
- ADR 0240 defines offline workflow URL resolution.
- `scripts/publish_guard.py` owns the executable publish workflow contract.
- `.github/workflows/release.yml` owns package publication.
- `.github/workflows/publish.yml` owns only the hosted read-only preflight.

## References

- `scripts/publish_plan.py`
- `scripts/publish_guard.py`
- `.github/workflows/publish.yml`
- `docs/distribution.md`
- `tests/test_memory_tools.py`
