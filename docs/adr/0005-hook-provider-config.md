# ADR 0005: Provider-Aware Local Hook Configuration

## Status

Accepted for v2 draft.

## Context

The repository already bundled Codex plugin hooks for lightweight session-event
metadata capture. The next setup milestone needs the same local-only pattern to
work for multiple providers, especially Claude Code command hooks, without
turning package installation into background automation.

## Decision

Add provider-aware hook support to `scripts/hook_event.py` and expose generated
configuration through:

- `ai-dememory hooks events`
- `ai-dememory hooks config --client codex`
- `ai-dememory hooks config --client claude`
- MCP read-only tools `memory.hook_events` and `memory.hook_config`

Hook capture remains review-first. It writes only to `inbox/session-events/`,
stores metadata by default, and rejects secret-like rendered Markdown before
writing. Raw payload capture remains an explicit direct CLI option.

## Consequences

Users can install the package once, then generate local hook fragments for
Codex or Claude Code without copying ad hoc commands from documentation.

Provider event lists are maintained in code and validated at capture time.
Unsupported events fail early instead of creating ambiguous files.

Hook config generation does not install hooks. A human or client-specific setup
flow still decides where to place the generated fragment.

## Deferred

- Remote hook endpoints.
- HTTP/OAuth MCP server integration.
- Automatic durable promotion from hook captures.
- Provider-specific raw payload normalization beyond hashing.
