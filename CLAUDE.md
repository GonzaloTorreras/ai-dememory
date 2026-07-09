# Claude Instructions

<!-- BEGIN AI-DEMEMORY HOOKS:claude -->
## Claude Code Memory Hooks

`ai-dememory` hook capture is optional and review-first for this vault.

- Generate local hook config with `ai-dememory hooks config --client claude --root <vault-path>`.
- Supported events: UserPromptSubmit, SessionStart, PreCompact, Stop, SubagentStop, Notification.
- Hook captures write metadata only to `inbox/session-events/` by default.
- Do not promote hook captures to durable memory without explicit human review.
- Do not store secrets, tokens, cookies, private keys, or `.env` content in memory.
<!-- END AI-DEMEMORY HOOKS:claude -->
