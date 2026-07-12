# ai DeMemory Repo Instructions

This repository stores personal and project memory for multiple LLM tools.

## GitHub Access

- Prefer the native Codex GitHub connector over gh for Codex-driven GitHub work.
- If GitHub tools are not visible, use tool discovery before falling back to gh.
- gh is optional local CLI only, not the primary Codex integration.

## AI-Operated Repository Authority

- The repository is AI-operated and human-account-owned. Codex owns routine
  maintenance, release PRs, versioning, changelog updates, merges, immutable
  tags, package publication, post-publish verification and fix-forward work.
- Normal releases do not require human approval. They require protected `main`,
  successful CI, a new PEP 440 version, a dated changelog entry, an immutable
  tag, exact-artifact smoke tests, OIDC Trusted Publishing and post-publish
  verification.
- Product and memory-vault acceptance remains review-first, but it is not a
  package-distribution gate. Never fabricate manual acceptance records to make
  a release pass.
- Whenever a PR is ready for merge, delegate a fresh,
  read-only professional review to a subagent with the GitHub plugin context
  before recording or acting on approval.
- Give the reviewer enough context to understand the stack, base/head branches,
  CI status, test evidence, and intended merge order, but avoid dumping noisy
  implementation history.
- The reviewer must not merge, publish, or mutate repository state. Codex uses
  its findings and required CI to decide whether to merge or continue fixing.
- After the fresh reviewer approves and CI is green for the exact unchanged PR
  number, head SHA, and base SHA, Codex records a tuple-bound
  `codex-double-check` receipt on the PR.
  The trusted default-branch workflow then submits the formal review as
  `github-actions[bot]`; no second human account is required.
- Auto-approval is restricted to non-draft PRs authored by `GonzaloTorreras`,
  targeting `main`, using an internal `codex/*` branch, with successful
  canonical CI for that exact tuple. It never checks out PR code or reads PR
  artifacts in the privileged workflow.
- A new head commit or movement of `main` invalidates the receipt. Codex must
  update the branch, rerun relevant tests, obtain a fresh read-only review,
  wait for green CI, and record a new tuple-bound receipt before approval or
  merge. Branch protection must require one approval, dismiss stale reviews,
  require approval after the latest push, and require the branch to be current.
- PRs that change `AGENTS.md`, `scripts/ci_guard.py`, `.github/workflows/*`, or
  `.github/actions/*` are outside auto-approval. They use the explicit
  security-boundary bootstrap procedure in `docs/auto-approval.md`.
- Codex must not bypass branch/tag protections, rewrite published tags, delete
  releases, change repository visibility, rotate credentials, or weaken OIDC.
  PyPI rollback is yank plus fix-forward with a new version, never overwrite.
- Human recovery authority remains available for account compromise, legal
  ownership, billing, PyPI ownership and destructive break-glass actions.

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
