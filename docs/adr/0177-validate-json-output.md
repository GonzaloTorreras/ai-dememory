# ADR 0177: Validate JSON Output

Status: Accepted

## Context

ADR 0163 made `ai-dememory validate` include non-blocking conflict scan
evidence in human-readable command output. Release gates, setup health checks,
and MCP-adjacent smoke tests increasingly consume JSON from related commands,
but validation only exposed text streams and exit codes.

Downstream automation needs a stable payload for frontmatter validation,
memory counts, conflict scan policy state, and blocking errors without changing
the existing terminal output that users and CI already read.

## Decision

Add `--json` to `ai-dememory validate` and the direct
`scripts/validate_memory.py` entry point. The JSON payload includes:

- `ok` and `exit_code`;
- `memory_count`;
- `messages` for successful human-readable summaries;
- `errors` for validation or review-policy failures; and
- `conflict_review` with scan availability, status, counts, and blocking state.

The default text output remains unchanged. Frontmatter errors and review-policy
failures still return exit code `1`; active conflicts remain non-blocking until
a severity policy says otherwise.

## Benefits

- Automation can inspect validation and conflict-scan state without parsing
  prose.
- Existing release and CI checks keep their current text behavior.
- The JSON payload mirrors the command exit code, so shell scripts can combine
  machine-readable evidence with ordinary failure handling.
- Conflict scan policy states become explicit as `scanned`, `skipped`,
  `disabled`, `failed`, or `not_run`.

## Limitations

- The payload reports conflict counts only, not full conflict objects.
- Active conflicts do not fail validation yet.
- The JSON schema is command-local and not yet published as an MCP contract.

## Future Risks

- If validation becomes severity-aware, callers must handle active conflict
  states becoming blocking.
- If detailed conflict evidence is added later, the command should preserve the
  existing top-level fields for compatibility.

## Dependencies

- ADR 0163 defines the validate-time conflict scan policy.
- `scripts/validate_memory.py` owns validation command output.
- `scripts/review_memory.py` owns conflict scanning and policy parsing.
- `scripts/release_checklist_guard.py` keeps release checklist examples aligned.
