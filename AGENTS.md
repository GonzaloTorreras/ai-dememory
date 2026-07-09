# ai DeMemory Repo Instructions

This repository stores personal and project memory for multiple LLM tools.

## GitHub Access

- Prefer the native Codex GitHub connector over gh for Codex-driven GitHub work.
- If GitHub tools are not visible, use tool discovery before falling back to gh.
- gh is optional local CLI only, not the primary Codex integration.

## PR And Merge Approval

- Treat this repository as agent-owned for day-to-day implementation, but keep
  PR and merge approval review-gated.
- Codex may act as release owner for repeatable, non-secret release checks:
  collecting evidence, setting `AI_DEMEMORY_PR_URL`, recording manual
  acceptance as `Codex Release Owner`, updating PR comments, and pushing scoped
  release-readiness commits when the proof was generated and inspected in this
  workspace.
- Whenever a PR is ready for review or a merge needs approval, delegate a fresh,
  read-only professional review to a subagent with the GitHub plugin context
  before asking for or acting on approval.
- Give the reviewer enough context to understand the stack, base/head branches,
  CI status, test evidence, and intended merge order, but avoid dumping noisy
  implementation history.
- The reviewer must not merge, publish, or mutate repository state. Use its
  findings to decide whether approval is safe or more work is needed.
- Do not merge, make the repository public, publish packages, rotate secrets, or
  dispatch trusted publishing without explicit user approval, even when Codex has
  completed the release evidence and double-checks.

## Memory Contract

- Markdown is canonical.
- SQLite/vector indexes are generated and disposable.
- Durable values are pinned and require explicit human approval to change.
- Active/project/archive memories may be consolidated by automation after review.

## Secret Policy

Do not store credentials or secret material. If secret-like content is detected, quarantine it outside versioned memory and ask for human review.

<!-- BEGIN AI-DEMEMORY HOOKS:codex -->
## ai DeMemory Hooks

`ai-dememory` hook capture is optional and review-first for this vault.

- Generate local hook config with `ai-dememory hooks config --client codex --root <vault-path>`.
- Supported events: UserPromptSubmit, PreCompact, PostCompact, Stop.
- Hook captures write metadata only to `inbox/session-events/` by default.
- Do not promote hook captures to durable memory without explicit human review.
- Do not store secrets, tokens, cookies, private keys, or `.env` content in memory.
<!-- END AI-DEMEMORY HOOKS:codex -->
