# ADR 0160: Configured Review State Path

Status: Accepted

## Context

Reviewed false-positive suppressions and conflict decisions are stored in
`.ai-dememory-ignore.toml`. The v2 configuration direction includes
`[false_positives].allow_ignore_file` and `ignore_file`, but the implementation
always used the hard-coded default path.

The same state file currently stores both false-positive sections and conflict
sections, so changing the path must keep the review state model shared and
auditable rather than splitting decisions across unrelated files.

## Decision

Support a configured review state path:

```toml
[false_positives]
allow_ignore_file = true
ignore_file = ".ai-dememory-ignore.toml"
```

When `ignore_file` is configured, false-positive and conflict review state reads
and writes use that path. The path must resolve inside the vault. If
`allow_ignore_file` is explicitly `false` while a custom path is configured,
review-state access fails instead of silently writing elsewhere.

The default remains `.ai-dememory-ignore.toml` for compatibility.

## Benefits

- Vault owners can organize review state under a namespaced local path without
  changing CLI or MCP commands.
- False-positive and conflict decisions continue sharing one audited state
  file.
- Existing vaults keep their current behavior.

## Limitations

- Existing review state is not migrated when the path changes.
- The setting is named under `[false_positives]` for compatibility with the v2
  config direction, even though the file also stores conflict decisions.
- The configured file is still TOML-like state, not canonical memory.

## Future Work

- Add a migration command if users need to move existing review state safely.
- Consider a future `[review_state]` config section if more review object types
  share the file.
- Surface the active review state path in setup health if first-run diagnostics
  need to explain policy layout.

## Dependencies

- ADR 0001 defines review and conflict workflows.
- ADR 0149 defines stale false-positive suppression audits.
- ADR 0158 defines false-positive review window defaults.
- `scripts/review_memory.py` owns review state reads and writes.
