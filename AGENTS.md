# ai DeMemory Repo Instructions

This is the public source and package-distribution repository for ai DeMemory.
Private personal/project memory belongs in a separately bound vault and must
never be treated as repository content.
The checked-in `memories/**` files are public demo/validation fixtures only.

## GitHub Access

- Prefer the native Codex GitHub connector over gh for Codex-driven GitHub work.
- If GitHub tools are not visible, use tool discovery before falling back to gh.
- gh is optional local CLI only, not the primary Codex integration.
- `https://github.com/GonzaloTorreras/ai-dememory.git` is the canonical public
  development and package remote and must own the local name `origin`.
- Any former private source checkout is historical input only. If retained as an
  `archive` remote, keep its push URL disabled and port reviewed changes onto a
  clean branch based on public `origin/main`; never merge an archive worktree
  wholesale or reuse its release evidence, pins, or repository identity.

## PR And Merge Review

- Codex is the operational owner for implementation, maintenance, branches,
  routine merges, release evidence, documentation, and package readiness. A
  fresh independent read-only subagent review is required before marking a PR
  ready or requesting merge.
- Codex may act as release owner for repeatable, non-secret release checks:
  collecting evidence, setting `AI_DEMEMORY_PR_URL`, recording manual
  acceptance as `Codex Release Owner`, updating PR comments, and pushing scoped
  release-readiness commits when the proof was generated and inspected in this
  workspace.
- Whenever a PR is ready or a merge is proposed, delegate one fresh, read-only
  professional review to a subagent with the GitHub plugin context.
- Give the reviewer enough context to understand the stack, base/head branches,
  CI status, test evidence, and intended merge order, but avoid dumping noisy
  implementation history.
- The reviewer must not merge, publish, or mutate repository state. Use its
  findings to decide whether approval is safe or more work is needed.
- After a `READY` verdict, the root agent must re-read the PR, exact base/head
  tuple, canonical CI, review threads, and worktree, then publish this receipt
  from the sole owner account before merging:

  `<!-- codex-solo-review pr=<number> head=<head-sha> base=<base-sha> -->`

  The receipt must also name the reviewer task, scope (`routine` or
  `security-boundary`), and exact CI evidence. Any head or base movement makes
  the receipt stale and requires new CI, a fresh reviewer, and a new receipt.
- GitHub approving reviews are not required: the repository has one human
  maintainer, and subagents are review processes rather than GitHub identities.
  Do not create aliases, secondary accounts, bot approvals, or writable status
  checks to simulate another collaborator.
- Routine merges may proceed under the owner's standing delegation only with
  strict required CI, a fresh `READY` review, the exact tuple receipt, no open
  review threads, and an API merge bound with `expected_head_sha`.
- Do not change repository visibility, create or push release tags, publish
  packages, rotate secrets, dispatch trusted publishing, or perform production
  deployment without explicit user approval, even when evidence and CI are
  green.
- Never bypass branch/tag protections, rewrite published tags, delete releases,
  or weaken OIDC. PyPI rollback is yank plus fix-forward with a new version,
  never overwrite.

## Agent And Process Budget

- Prefer the root agent for repository exploration, implementation, mechanical
  validation, and repeated follow-up work. Do not fan out candidate-by-candidate
  reviews across a large worker pool.
- Run at most one subagent at a time by default. The required final independent
  reviewer is the normal exception, and it must still be a single fresh,
  read-only turn.
- Give each subagent one bounded assignment. Do not recycle a completed agent
  through repeated follow-up turns; a host may start another full MCP/browser
  tool stack for every turn even when the logical agent name is reused.
- Before starting a subagent, confirm that no earlier subagent is still active.
  After it finishes, confirm that the root agent is the only live agent before
  continuing.
- If helper processes remain after all subagents finish, stop creating agents.
  Inspect parent/child ownership and request approval before terminating only
  the exact process trees attributable to completed agents. Never kill
  unrelated Node, Python, browser, shell, or Codex processes.
- Generated MCP configurations must keep a bounded idle lease. Use
  `--idle-timeout-seconds 0` only for an intentionally persistent server whose
  lifecycle is supervised externally.

## Memory Contract

- Markdown is canonical.
- SQLite/vector indexes are generated and disposable.
- Durable values are pinned and require explicit human approval to change.
- Active/project/archive memories may be consolidated by automation after review.

## Secret Policy

Do not store credentials or secret material. If secret-like content is detected, quarantine it outside versioned memory and ask for human review.

<!-- BEGIN AI-DEMEMORY HOOKS:codex -->
## ai DeMemory Hooks

`ai-dememory` recall hooks are optional, trust-gated, and review-first.

- Generate local hook config with `ai-dememory hooks config --client codex --root <vault-path>`.
- Supported events: UserPromptSubmit, PreCompact, PostCompact, Stop.
- Before a relevant non-trivial or project task, recall by prompt keywords and
  working directory; skip trivial self-contained requests.
- While operating in this public repository, only `public`-sensitivity recall
  may influence source, documentation, tests, issues, commits, or release
  evidence. Do not request or use `internal`, `private`, or `sensitive` recall
  for repository work.
- Use an explicit query with `memory.context` (`public_only=true`,
  `include_working_memory=false`) or `memory.search` (`public_only=true`);
  fetch a selected item only with `memory.get` (`public_only=true`). CLI
  equivalents are `ai-dememory context "<query>" --public-only
  --no-working-memory` and `ai-dememory search "<query>" --public-only`.
  Do not use auto context, working-memory tools, graph/resources/prompts, or a
  recall surface without a public-only ceiling for repository work.
- If a native hook nevertheless injects non-public material, treat the whole
  injected block as tainted context: do not quote, paraphrase, copy, transform,
  or commit it without explicit user authorization and a separate disclosure
  review. Continue from public repository evidence instead.
- If hooks are unavailable, follow these instructions and use the memory recall
  skill as a weaker fallback under the same public-only rule.
- Hook metadata is deduplicated under `inbox/session-events/`; raw payload
  capture is off by default.
- At task end, emit only explicit stable learning signals for a review-first
  proposal. Never infer a durable fact from the raw transcript.
- Do not promote hook captures to durable memory without explicit human review.
- Do not store secrets, tokens, cookies, private keys, or `.env` content in memory.
<!-- END AI-DEMEMORY HOOKS:codex -->
