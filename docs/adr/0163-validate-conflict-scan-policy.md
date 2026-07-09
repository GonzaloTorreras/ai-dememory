# ADR 0163: Validate Conflict Scan Policy

Status: Accepted

## Context

ADR 0161 exposed `[conflicts].scan_on_validate`, and ADR 0162 began enforcing
the `[conflicts].enabled` switch at review workflow boundaries. Validation still
only checked memory frontmatter, so the configured scan-on-validate policy did
not affect the `ai-dememory validate` command.

The conflict scanner is useful review evidence, but the project does not yet
have a severity policy that should make active conflicts fail validation.

## Decision

Run a non-blocking conflict scan summary during `ai-dememory validate` when:

- frontmatter validation succeeds;
- `[conflicts].enabled = true`; and
- `[conflicts].scan_on_validate = true`.

The command prints the total conflict count and active conflict count, but keeps
exit code `0` unless frontmatter validation or review policy parsing fails.
When conflict review is disabled, validation reports that the scan is disabled.
When `scan_on_validate = false`, validation reports that the scan was skipped by
policy.

## Benefits

- The configured scan-on-validate policy now has observable behavior.
- CI and local users get conflict visibility during normal validation without a
  separate report command.
- Active conflicts remain review work, not schema failures, until a severity
  policy exists.
- The command still avoids writing reports, review state, or canonical memory.

## Limitations

- Active conflicts do not fail validation yet.
- The scan summary does not include conflict ids; users still run
  `ai-dememory review conflicts` for detailed evidence.
- `scan_on_consolidate` remains future work.

## Future Work

- Add severity-aware validation failures if review policy later defines which
  conflict categories must block.
- Wire `scan_on_consolidate` into consolidation planning without mutating
  canonical memory.

## Dependencies

- ADR 0161 defines review policy defaults and policy output.
- ADR 0162 enforces enabled review workflow boundaries.
- ADR 0157 defines conflict categories.
- `scripts/validate_memory.py` owns validation command output.
- `scripts/review_memory.py` owns conflict scanning and policy parsing.
