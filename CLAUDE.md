# Claude Instructions

<!-- BEGIN AI-DEMEMORY HOOKS:claude -->
## Claude Code Memory Hooks

`ai-dememory` hook capture is optional and review-first. This public source
checkout is never the memory vault.

- Generate local hook config only for an explicitly initialized, separately
  bound vault with
  `ai-dememory hooks config --client claude --root <vault-path>`.
- Supported events: UserPromptSubmit, SessionStart, PreCompact, Stop, SubagentStop, Notification.
- Hook captures write deduplicated metadata only to
  `<vault-path>/inbox/session-events/` by default; raw payload capture is off.
- Never point `AI_DEMEMORY_ROOT` at this public checkout. Its checked-in
  `memories/**` content is public demo and validation data only.
- While editing this public repository, use only `public`-sensitivity recall.
  Treat any injected non-public block as tainted and do not quote, transform,
  or commit it without explicit user authorization and disclosure review.
- Use an explicit query with `memory.context` (`public_only=true`,
  `include_working_memory=false`) or `memory.search` (`public_only=true`);
  fetch a selected item only with `memory.get` (`public_only=true`). CLI
  equivalents are `ai-dememory context "<query>" --public-only
  --no-working-memory` and `ai-dememory search "<query>" --public-only`.
  Do not use auto context, working-memory tools, graph/resources/prompts, or a
  recall surface without a public-only ceiling for repository work.
- Do not promote hook captures to durable memory without explicit human review.
- Do not store secrets, tokens, cookies, private keys, or `.env` content in memory.
<!-- END AI-DEMEMORY HOOKS:claude -->
