# ADR 0006: Managed Hook Instruction Blocks

## Status

Accepted for v2 draft.

## Context

Hook capture has two separate setup surfaces:

- client hook configuration, which differs by Codex, Claude Code, OS, and user
  install location
- repository instruction files, which tell agents how to treat hook captures
  once they exist

The v2 plan requires hook list/install/uninstall support for Codex and Claude
and idempotent updates to `AGENTS.md` and `CLAUDE.md`. Those files may contain
user-authored policy, so the tool needs a bounded edit strategy.

## Decision

`ai-dememory hooks install` writes client-specific managed blocks only:

- Codex block in `AGENTS.md`
- Claude Code block in `CLAUDE.md`

Each block is wrapped with stable HTML comment markers:

```text
<!-- BEGIN AI-DEMEMORY HOOKS:<client> -->
<!-- END AI-DEMEMORY HOOKS:<client> -->
```

`ai-dememory hooks uninstall` removes only the matching managed block.
Unrelated file content is preserved. `ai-dememory hooks list` reports whether
the managed blocks are present and which events are supported.

The installer documents how to generate hook configuration, but it does not
write client settings files. Client hook config remains explicit via
`ai-dememory hooks config --client <client>`.

## Benefits

- Repeated install commands are idempotent.
- Uninstall is narrow and reversible through Git.
- Agents get consistent safety instructions in their native instruction files.
- Package install remains passive and does not mutate user configuration.

## Limitations

- The installer cannot prove that a user copied the generated hook config into
  a client settings file.
- Managed blocks are documentation and policy guidance, not enforcement.
- If a client changes its instruction-file convention, only the installer
  mapping needs to change.

## Future Risks

- More providers may require additional instruction files or workspace-specific
  locations.
- Client hook schemas may change, so generated config must remain covered by
  smoke tests and docs reviews.
- Users may manually edit inside managed blocks; a later install will replace
  the managed content by design.
