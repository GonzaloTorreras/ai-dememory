# ADR 0168: Hook Capture Status Summary

Status: Accepted

## Context

ADR 0167 exposed managed hook instruction status through setup health and MCP.
That showed whether the local instruction blocks were installed, but did not
show whether hooks had produced any review candidates under
`inbox/session-events/`.

Reviewers need a lightweight way to inspect hook capture activity during setup
and maintenance without reading raw hook payload bodies or promoting memory.

## Decision

Add a bounded `captures` summary to the read-only hook status payload used by
MCP `memory.hook_status` and `memory.setup_health`.

The summary reports:

- total valid capture count;
- malformed frontmatter count;
- counts by provider and event;
- bounded latest candidate paths and metadata; and
- explicit `reads_raw_payloads=false` and `writes_files=false` flags.

The implementation reads frontmatter only from Markdown files under
`inbox/session-events/`. It does not inspect candidate bodies, install hooks,
write files, modify client settings, or promote canonical memory.

## Benefits

- Setup and plugin flows can distinguish "hooks installed but no captures yet"
  from "captures are waiting for review."
- Reviewers get provider/event counts without opening raw hook payload bodies.
- The summary stays additive to the existing hook status response and setup
  health shape.

## Limitations

- The summary is bounded and diagnostic; it is not a full review queue UI.
- Malformed files are counted and sampled, not repaired.
- The summary does not prove a hook is currently active in a running client.

## Future Work

- Add age windows or review-after counts if hook capture review becomes a
  recurring maintenance task.
- Add a generated hook capture review report only if reviewers need a durable
  handoff artifact.

## Dependencies

- ADR 0005 defines provider-aware hook capture.
- ADR 0141 defines hook event idempotency.
- ADR 0143 defines canonical JSON hook fingerprints.
- ADR 0167 exposes read-only hook status through MCP and setup health.
- `scripts/hook_event.py` owns hook capture metadata and status summaries.
