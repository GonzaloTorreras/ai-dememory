# ADR 0159: Conflict Configured Paths

Status: Accepted

## Context

Conflict review already writes generated reports under `reports/conflicts.md`
and merge proposals under `inbox/conflict-resolution/`. The v2 configuration
direction includes vault-local conflict paths, but the implementation still used
module constants unless the report command received an explicit path.

Users running multiple review workflows may need namespaced report or proposal
folders while keeping generated artifacts and inbox candidates inside the vault.

## Decision

Add configured conflict paths to `.ai-dememory.toml`:

```toml
[conflicts]
report_path = "reports/conflicts.md"
proposal_path = "inbox/conflict-resolution"
```

`ai-dememory review conflicts` uses `report_path` when no explicit
`--report-path` or `--output` is supplied. Conflict merge proposals use
`proposal_path`. Both configured paths are resolved under the vault and rejected
if they escape the memory root.

Explicit CLI report paths still take precedence over config. Merge proposals
remain review candidates only and do not mutate canonical memory.

## Benefits

- Vault policy can organize conflict reports and proposals without wrapping the
  CLI.
- MCP and CLI conflict merge proposal behavior stay aligned because both use
  the same writer.
- Existing defaults remain unchanged for users who do not configure paths.

## Limitations

- The setting only controls conflict report/proposal locations, not false
  positive report paths or generated maintenance report paths.
- Existing proposal files are not moved when the config changes.
- The config parser supports simple scalar paths only.

## Future Work

- Add configured false-positive report paths if users need per-vault report
  layout control beyond the existing CLI `--report-path`.
- Surface configured review paths in setup health if first-run policy summaries
  become useful.
- Add archive/migration helpers if proposal folders are renamed.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0124 defines review report path guards.
- ADR 0157 defines conflict categories.
- `scripts/review_memory.py` owns conflict report and proposal writes.
