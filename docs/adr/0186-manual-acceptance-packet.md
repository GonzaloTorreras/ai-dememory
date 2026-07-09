# ADR 0186: Manual Acceptance Packet

Status: Accepted

## Context

The remaining v2 release work includes manual checks that cannot be completed
by automated CI: real MCP client use, Obsidian inspection, reviewed provider
imports, maintenance artifact inspection, review reports, and TestPyPI release
proof. Existing commands expose this work through `acceptance plan`,
`acceptance plan --write-report`, and single-item `acceptance template`.

Those surfaces are useful, but reviewers still need to assemble a practical
review packet that lists every incomplete item with fill-in notes, suggested
artifacts, and the exact pass/block record commands. The packet must not become
evidence by itself because acceptance requires real human-reviewed proof.

## Decision

Add `ai-dememory acceptance packet`.

The command renders a reviewer-facing Markdown packet for all incomplete manual
acceptance items. With `--write-report`, it writes
`reports/manual-acceptance-packet.md` by default. The report path must stay
inside the memory root and the rendered packet is secret-scanned before writing.

The packet includes:

- release acceptance summary counts;
- reviewer instructions;
- one fill-in section for each incomplete item;
- suggested artifacts;
- pass and block `ai-dememory acceptance record` commands;
- completed-item summary; and
- final gate reminders for `acceptance verify` and `release-evidence --strict`.

`acceptance packet --json` reports whether a file was written and includes:

- `mutates_system=false`;
- `records_evidence=false`;
- `writes_acceptance_records=false`; and
- `writes_files`, which is true only when `--write-report` writes the generated
  report.

Setup planning now lists `acceptance packet --write-report` with the other
generated handoff artifacts.

## Benefits

- Reviewers get one practical packet for the remaining human-only release work.
- The packet makes the required proof and record commands harder to miss.
- The generated report keeps manual acceptance review separate from acceptance
  evidence.
- Package install smoke exercises the command so installed users get the same
  handoff surface.

## Limitations

- The packet does not complete manual acceptance and cannot prove a check
  happened.
- ADR 0192 later exposes the same packet renderer as read-only MCP tool
  `memory.acceptance_packet`.
- The packet is overwritten at the configured report path.

## Future Work

- ADR 0211 adds CLI-only timestamped packet archives.
- ADR 0208 adds offset pagination for incomplete manual acceptance packet
  sections.
- ADR 0209 adds optional reviewer and PR URL packet metadata.

## Dependencies

- ADR 0016 defines manual acceptance evidence records.
- ADR 0047 defines manual acceptance planning.
- ADR 0058 defines suggested manual acceptance artifacts.
- ADR 0080 defines single-item acceptance templates.
- ADR 0116 defines the generated manual acceptance plan report.
- ADR 0192 defines read-only MCP manual acceptance packet rendering.
- ADR 0208 defines manual acceptance packet pagination.
- ADR 0209 defines optional manual acceptance packet metadata.
- ADR 0211 defines manual acceptance packet archives.
- `scripts/manual_acceptance.py` owns acceptance planning, templates, packets,
  and evidence recording.
