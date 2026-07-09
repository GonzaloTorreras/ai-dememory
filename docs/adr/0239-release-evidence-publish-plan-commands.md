# ADR 0239: Release Evidence Publish Plan Commands

## Status

Accepted

## Context

ADR 0235 added top-level release-evidence handoff commands for generated
reports, manual acceptance, recall review, strict release evidence, and
`publish-guard`. ADR 0236 later added `ai-dememory publish-plan` as the
read-only command that combines publish workflow dispatch inputs, preflight
commands, release blockers, and explicit non-publishing side-effect flags.

That left release evidence slightly behind the current publish workflow: the
handoff pointed maintainers at the guard, but not at the richer TestPyPI and
PyPI publish plans.

## Decision

Add `publish_plan_testpypi` and `publish_plan_pypi` to release evidence
top-level `handoff_commands`.

The commands are:

```bash
ai-dememory publish-plan --repository testpypi --pr-url <pr-url>
ai-dememory publish-plan --repository pypi --pr-url <pr-url>
```

When release evidence receives a PR URL, both command arrays include it.
Otherwise they use the literal `<pr-url>` placeholder, matching existing strict
release evidence and review packet commands.

The `handoff_commands` payload side-effect flags remain about constructing the
handoff: `payload_mutates_system=false`, `payload_runs_commands=false`,
`payload_records_evidence=false`, and `payload_writes_files=false`.
`command_side_effects` continues to describe the explicit reviewer action of
running suggested commands. The publish-plan commands remain non-publishing,
but are marked with `runs_commands=true` because publish planning performs
local read-only inspection.

## Consequences

- Final release handoffs now expose the same publish planning path as the CLI,
  MCP tool, installed smoke, and Docker smoke.
- Maintainers can inspect TestPyPI and PyPI plans directly from release
  evidence JSON or Markdown.
- Publish execution remains outside release evidence and still requires
  explicit human approval.

## Limitations

- The commands do not prove a publish workflow was dispatched or completed.
- The commands cannot verify external PyPI/TestPyPI Trusted Publisher settings.
- The `pypi` command is guidance only; it still reminds maintainers to complete
  TestPyPI first.

## Future Work

- Add post-TestPyPI verification commands after real TestPyPI evidence defines
  the expected checks.
- Include workflow URLs only after publish evidence is recorded as reviewed
  manual acceptance.
- Split handoff commands into command groups only if release handoffs become
  too large for a flat dictionary.

## Dependencies

- ADR 0013 defines v2 release evidence reports.
- ADR 0235 defines release evidence handoff commands.
- ADR 0236 defines CLI publish planning.
- ADR 0237 defines MCP publish planning.
- ADR 0238 defines package and Docker smoke for MCP publish planning.
- `scripts/release_evidence.py` owns release evidence JSON and Markdown.
- `scripts/publish_plan.py` owns publish-plan semantics.

## References

- `scripts/release_evidence.py`
- `scripts/publish_plan.py`
- `docs/release-v2-checklist.md`
- `tests/test_memory_tools.py`
