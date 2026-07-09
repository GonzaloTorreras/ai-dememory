# ADR 0235: Release Evidence Handoff Commands

## Status

Accepted

## Context

Release evidence already reports blockers, next actions, manual acceptance
plans, recall review state, vector readiness, setup health, and maintenance
state. Final PR handoffs still require reviewers to know which generated
packets and strict checks to run next.

That makes the last release stage more error-prone: the evidence explains what
is missing, but the command list is spread across README sections, setup plans,
and nested manual acceptance or recall review objects.

## Decision

Add top-level `handoff_commands` to release evidence.

The field contains command arrays for the release handoff:

- writing the release evidence report;
- running strict release evidence with the PR URL;
- planning manual acceptance;
- rendering a single manual acceptance template;
- writing the manual acceptance packet;
- verifying manual acceptance;
- writing the recall review packet;
- checking strict recall fixture freshness; and
- planning TestPyPI and PyPI publish handoffs; and
- running the publish workflow guard.

When a PR URL is provided, the commands include it. When reviewer metadata is
provided, the commands that support reviewer context include it. Otherwise they
use the literal `<pr-url>` and `<reviewer>` placeholders so reviewers can fill
them in explicitly.

The field also includes side-effect metadata. `payload_*` flags show that
generating the handoff command list itself does not mutate the system, run
commands, write files, or record acceptance evidence. `command_side_effects`
describes what happens if a reviewer runs an individual command; commands with
`--write-report` are marked with `writes_files=true`, and publish-plan commands
are marked with `runs_commands=true` for local read-only inspection.

## Consequences

- Reviewers can copy the final handoff commands directly from release evidence.
- MCP clients can display structured command arrays without parsing Markdown.
- Manual acceptance remains human-gated; the commands do not create passing
  evidence records.
- Publish and merge remain explicit human actions outside this command list.

## Limitations

- Some listed commands, such as `--write-report`, write generated reports when
  reviewers run them. The `payload_writes_files=false` flag applies only to
  building release evidence; `command_side_effects` records the effects of
  executing the suggested commands.
- Publish-plan handoff commands do not publish packages, but they do run local
  read-only inspection to resolve workflow metadata.
- The command list is static guidance; it does not prove the commands were run.
- The list does not fetch or infer PR URLs or reviewer identity from GitHub.
- Reviewer metadata is supplied by the caller and is not signed or externally
  verified.

## Future Work

- Add command groups if release handoffs need separate local, CI, and publish
  sections.
- Include workflow URLs after publish or CI evidence is recorded as manual
  acceptance artifacts.
- Add MCP-specific display hints only if clients need richer presentation than
  command arrays.

## Dependencies

- ADR 0013 defines v2 release evidence reports.
- ADR 0050 defines structured release blockers.
- ADR 0111 defines recall review plans in release evidence.
- ADR 0186 defines manual acceptance packets.
- ADR 0223 defines release evidence next actions.
- ADR 0239 adds publish-plan commands to release evidence handoffs.
- ADR 0243 adds reviewer and PR URL metadata propagation to release evidence
  handoffs.
- `scripts/release_evidence.py` owns release evidence JSON and Markdown.

## References

- `scripts/release_evidence.py`
- `docs/release-v2-checklist.md`
- `README.md`
- `tests/test_memory_tools.py`
