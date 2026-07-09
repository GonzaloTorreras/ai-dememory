# ADR 0086: Plugin Review Receipt Tools

## Status

Accepted.

## Context

The Codex plugin exposes a guarded subset of the local MCP server. That subset
included read-heavy recall, setup, scheduler, maintenance, acceptance, and
review planning tools, plus `memory.conflict_keep` and
`memory.conflict_merge_proposal`.

After the MCP review receipt work, the plugin surface still omitted several
review-first tools that return structured receipts:

- `memory.false_positive_ignore`
- `memory.false_positive_unignore`
- `memory.conflict_dismiss`
- `memory.review_configure_mode`

This left plugin users with an incomplete review workflow. They could list
false positives and conflicts, but had to leave the plugin path to record some
review decisions or change the local review mode.

## Decision

Add the missing review-first receipt and configuration tools to the guarded
Codex plugin MCP allowlist.

The plugin now exposes:

- false-positive review listing, ignore, and unignore tools
- conflict review listing, dismiss, keep, and merge-proposal tools
- review mode listing, planning, and explicit mode configuration tools

The plugin keeps `default_tools_approval_mode` set to `prompt`. These tools
record reviewed state in `.ai-dememory-ignore.toml` or `.ai-dememory.toml`,
or write merge proposals under `inbox/conflict-resolution/`; they do not promote
or mutate canonical durable memory.

## Benefits

- Gives plugin users the same structured review receipt workflow as MCP and CLI
  users.
- Keeps false-positive and conflict decisions auditable without requiring a
  shell fallback.
- Makes the plugin review skill match the actual enabled MCP surface.

## Limitations

- The tools still rely on the caller to provide truthful reviewer labels.
- Prompt-gated approval depends on Codex plugin client behavior.
- The plugin remains a local workflow helper; it does not authenticate reviewer
  identity or publish review evidence externally.

## Future Risks

- If plugin manifests gain per-tool approval metadata, these review write tools
  should be marked separately from read-only tools.
- If users expect unattended review automation, the plugin skill must continue
  to reject automatic durable memory promotion.
- If review mode configuration becomes sensitive in shared vaults, it may need a
  separate admin-only profile.

## Dependencies

- ADR 0068 defines the guarded plugin MCP tool surface.
- ADR 0069 defines checked-in plugin MCP config smoke coverage.
- ADR 0081 defines MCP false-positive unignore receipts.
- ADR 0082 defines MCP review-mode configuration receipts.
- ADR 0083 defines MCP conflict-dismiss receipts.
- ADR 0085 defines MCP conflict-keep reviewer receipts.
- `plugins/ai-dememory/.mcp.json` remains the plugin MCP allowlist source.
