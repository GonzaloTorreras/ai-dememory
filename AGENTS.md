# ai DeMemory repository instructions

This is the public source and package repository. Private memories, credentials,
local selector files and generated indexes must never be committed.

## Start and continuity

- For non-trivial work, inspect branch, remotes and `git status --short
  --branch`, then read `DEVELOPMENT.md` and `docs/development-status.md`.
- `docs/roadmap.md` is the only active product plan. The old DAG, ADRs, V2
  roadmaps and research appendices are historical input, not authority.
- Work on a feature branch or worktree based on public `origin/main`. Never
  merge a historical/private checkout wholesale.
- Keep the PR body as the durable handoff: outcome, base/head, affected paths,
  tests, residual risk, rollback and pending approval.
- Only the lead integrator updates `docs/development-status.md`.

## Product contract

- V3 is a clean format. Do not add V2 readers, migrations, aliases or tests.
- Keep fewer than ten public top-level commands and no maintainer/release tools
  in the installed CLI.
- Markdown is canonical; SQLite is generated and disposable.
- The default install has no daemon, network, model call, Node dependency or
  child process.
- Disabled modules contribute zero runtime imports, tools and processes;
  installed third-party distribution dependencies remain installed.
- Human CLI actions may write canonical memory. Integrations use read and
  proposal services; durable promotion requires explicit human review.
- Python modules are trusted installed code, not sandboxes. Never claim module
  manifests or resource budgets are OS-enforced.

## Implementation and review

- Prefer one useful vertical slice over a new framework, guard, task system or
  ADR.
- Run the narrowest meaningful test first, then all `tests_v3`, compilation and
  an isolated package/CLI smoke when practical.
- For non-trivial PRs, use bounded, focused read-only subagents for relevant
  security, bug, test and maintainability review. They do not mutate or merge.
- Before marking a PR ready, obtain one fresh exact-diff read-only review and
  verify required CI against the current base/head.
- The sole GitHub owner may record a review receipt; do not create aliases,
  secondary accounts or fake collaborators.

## GitHub and release boundary

- `https://github.com/GonzaloTorreras/ai-dememory.git` is canonical `origin`.
  A retained archive remote must have push disabled.
- Prefer the native GitHub integration when available; `gh` is a fallback.
- Do not merge, tag, publish, deploy, change visibility, rotate secrets or
  dispatch trusted publishing without explicit user approval for that gate.
- Never force-push, rewrite published tags, weaken OIDC or bypass branch/tag
  protections. Package rollback is yank plus fix-forward, never replacement.

## Process and secret hygiene

- No command in the default product should create persistent children. The MCP
  module runs synchronously in the foreground.
- Do not terminate unrelated Node, Python, browser, shell or Codex processes.
- Never edit or commit `.env*`, credentials, private keys, service-account JSON,
  cookies, personal memory, local selector config or generated SQLite.
- If secret-like content is found, stop it at the write boundary and ask for
  human review; do not echo it into logs or fixtures.
