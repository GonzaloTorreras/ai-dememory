# ADR 0170: Hook Capture Review Report

## Status

Accepted

## Context

ADR 0168 and ADR 0169 expose hook capture status through `memory.hook_status`
and setup health. That is enough for agents to see that `inbox/session-events/`
contains candidates, but reviewers still need a durable local handoff artifact
for routine review and release evidence.

Hook capture files may contain raw payload bodies only when a user explicitly
passes `--capture-raw`. Review status and operational triage should not require
reading those bodies.

## Decision

Add `ai-dememory hooks captures` as a CLI-only review helper:

- `--json` prints the existing bounded, frontmatter-only capture summary.
- `--write-report` writes `reports/hook-captures.md` by default.
- `--report-path` must resolve inside the memory root.
- The rendered report is secret-scanned before it is written.

The report includes counts, providers, events, review-after status, due paths,
latest capture metadata, malformed candidates, and payload fingerprints. It
does not include raw payload text.

## Benefits

- Reviewers get a durable Markdown artifact for hook capture triage.
- MCP remains read-only for hook setup and status inspection.
- Scheduled or manual local workflows can archive review evidence without
  promoting memory.
- Raw hook payload bodies are not required for routine review status.

## Limitations

- The report does not decide whether a capture should become canonical memory.
- The report is bounded by the requested limit and is not a full export of every
  candidate in high-volume vaults.
- Malformed capture entries are reported only by path and sanitized parse error.

## Future Risks

- Very large hook capture folders may need archival or date-window filtering
  beyond the bounded report limit.

## Dependencies

- ADR 0168 defines the bounded hook capture status summary.
- ADR 0169 defines review-after due-state classification for hook captures.
- `scripts/hook_event.py` owns hook capture metadata and report generation.
