# MCP v2.0 Gap Analysis

This gap analysis compares the local memory MCP server against the stable MCP
`2025-11-25` specification and the repository's v2.0 local-stdio goal.

Checked against official MCP pages on 2026-06-19:

- https://modelcontextprotocol.io/specification/2025-11-25
- https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
- https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping
- https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation
- https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- https://modelcontextprotocol.io/specification/2025-11-25/server/resources
- https://modelcontextprotocol.io/specification/2025-11-25/server/prompts
- https://modelcontextprotocol.io/specification/draft/basic/versioning
- https://modelcontextprotocol.io/docs/tools/inspector
- https://modelcontextprotocol.io/registry/quickstart.md
- https://modelcontextprotocol.io/extensions/tasks/overview.md

## Baseline Decision

Use stable MCP `2025-11-25` for v2.0. Draft `2026-07-28` documentation describes
the future modern/stateless era, but it is not the release baseline for this
local stdio server.

## Implemented

| Area | Status | Notes |
| --- | --- | --- |
| Lifecycle | Implemented | `initialize` negotiates `2025-11-25` or `2024-11-05`; `notifications/initialized` is accepted and exercised by client and runtime smoke. |
| Ping | Implemented | `ping` returns an empty result for connection health checks. |
| Tools | Implemented | The explicit `admin` profile retains 74 MCP tools for compatibility. Server-enforced `public`, `core`, `working`, and `review` profiles expose smaller allowlists in both `tools/list` and `tools/call`; ordinary clients do not all pay the admin schema cost. `ai-dememory mcp-inventory --check-docs` guards documented tool names. |
| Profile schema measurement | Implemented with a planning gap | `mcp-inventory --json` reports per-profile tool count, compact schema bytes, and estimated tokens. It does not yet make the human profile table or named growth budgets exact artifacts; `BRG-019` owns that gap. |
| Resources | Implemented | Public/internal memory resources can be listed/read by id or path. |
| Resource templates | Implemented | `memory://id/{id}` and `memory://path/{path}` are advertised. |
| Prompts | Implemented | Recall, capture proposal, and inbox review prompts are listed/read. |
| Pagination | Implemented | Tool, resource, and prompt list methods return cursors; `memory.graph` uses bounded limit/offset pages with next-page metadata. |
| Safe defaults | Implemented | The checked-in three-tool public profile server-forces public-only search/get/context, excludes sensitive and working state, and keeps graph/review/admin out of the public surface. |
| Package install smoke | Implemented | CI installs the wheel in a fresh environment and verifies vault setup, v2 command surfaces, recall fixture promotion, doctor profile summary, MCP release evidence and publish planning from a fresh vault, and direct MCP `initialize`/`notifications/initialized`/`ping` with response-id matching, missing-response diagnostics, unexpected/invalid/duplicate/result-less/non-object response rejection, and protocolVersion diagnostics. |
| CI workflow guard | Implemented | `ai-dememory ci-guard` verifies required v2 GitHub Actions gates stay present. |
| Generated artifact stage guard | Implemented | `ai-dememory artifact-guard` and `release-check` fail when generated indexes, reports, context exports, build outputs, or caches are staged. |
| Pull request template guard | Implemented | `ai-dememory pr-template-guard` keeps reviewer validation instructions aligned with current v2 gates. |
| Manual acceptance checklist guard | Implemented | `ai-dememory acceptance-guard` keeps checklist items aligned with `ACCEPTANCE_ITEMS` and release evidence. |
| ADR quality guard | Implemented | `ai-dememory adr-guard` validates decision record structure and dependency sections for new ADRs. |
| Release checklist guard | Implemented | `ai-dememory release-checklist-guard` keeps the release checklist aligned with current v2 gates. |
| Generated client config smoke | Implemented | Root-bound `ai-dememory --root <initialized-vault> mcp-client-smoke` launches generated installed and Docker configs, sends `notifications/initialized`, matches JSON-RPC responses by id, verifies `initialize`/`ping`, and verifies config-file `enabled_tools` against paginated `tools/list` when present. Loaded configs must be non-Docker and root-free; Docker uses a generated selected-root mount. |
| Local REST API smoke | Implemented | `ai-dememory api-smoke` verifies loopback health/search/paginated graph, proposal writes, reindexing, API-key enforcement, and non-loopback refusal without both API-key and TLS inputs. |
| Vault health over MCP | Implemented | MCP `memory.doctor` returns local readiness checks, selected profile, and a status summary without mutating files. MCP `memory.validate_status` returns the structured `validate --json` payload without writing reports or review state. |
| Durable provenance audit | Implemented | Durable memories require `reviewed: true`, `reviewed_by`, and `reviewed_at`; `ai-dememory provenance` reports gaps. |
| Durable provenance over MCP | Implemented | MCP `memory.provenance_status` reports the same durable provenance audit without writing reports. |
| Working memory over MCP | Implemented | MCP `memory.working_current`, `memory.working_status`, `memory.working_snapshot`, and `memory.working_handoff` inspect/read/write generated working state without mutating canonical memory. |
| Manual acceptance evidence | Implemented | `ai-dememory acceptance` records reviewed proof for human-only release checks and can generate read-only plan reports and reviewer packets; `release-evidence` reports completed, blocked, remaining, readiness summary state, top-level next actions, setup health summary, maintenance summary, and release blockers. MCP exposes read-only status, verification, next-action planning, single-item evidence templates, packet rendering, distribution-checkout release evidence, and release evidence report rendering. |
| Recall regression fixtures | Implemented | `eval-recall` checks curated passing search expectations. This protects solved behavior but is not a held-out corpus of unresolved misses. |
| Recall fixture promotion | Implemented | `ai-dememory recall-fixtures promote-miss` records a reviewed miss as a regression fixture only when that fixture now passes; otherwise it rolls back. The remaining status/review/packet surfaces triage or close misses, but they do not preserve unresolved challenges in a separate evaluation corpus. |
| Recall freshness release evidence | Implemented with a planning gap | `ai-dememory release-evidence` includes regression freshness, review planning, and current vector readiness. `RET-001` must separate passing regressions from held-out challenges and validate canonical targets before these signals can justify retrieval redesign. |
| Vector readiness | Implemented as a descriptive legacy gate | `ai-dememory vector status` and MCP `memory.vector_status` enable no embeddings. Their current regression-set result is not authorization for an experiment; normative tasks `RET-001`, `GATE-B`, `GRF-001`, and `RET-002` own that decision sequence. |
| Roadmap status | Implemented | `ai-dememory roadmap status` and MCP `memory.roadmap_status` report read-only v2 operational roadmap phase status, including implemented and gated phases. |
| Release readiness planning | Implemented | `ai-dememory publish-plan` and MCP `memory.publish_plan` report local TestPyPI/PyPI readiness, legacy read-only-preflight inputs, inspection commands, canonical-release readiness blockers, and false publish side-effect flags without uploading packages. The package workflow does not consume private-vault readiness receipts. |
| Runtime smoke | Implemented | PR-gated stdio smoke covers lifecycle negotiation, initialized notification, response-id matching, ping, paginated inventory/resources/prompts/graph, sensitive filters, recall misses, lifecycle feedback, first-run setup plans, setup health with validation status, context config status, manual acceptance readiness, recall review, vector readiness, roadmap status, generated artifact freshness, generated packet archive status, and maintenance preflight, provider import/status/setup plans, maintenance status with generated artifact freshness and generated packet archive cleanup status, installed and Docker scheduler plans, hook config, sleep consolidation, review workflows, advisory review recommendation capture/status/archive status/archive restore preview/outcome links/outcome status, and proposal boundaries. Owned process trees, frame queues and captured output are bounded. |

## Non-Blocking Gaps

| Area | v2.0 Decision | Reason |
| --- | --- | --- |
| Official Python SDK | Defer | The manual stdio server is small and covered; SDK migration is a hardening task, not needed for local v2.0 acceptance. |
| `resources/subscribe` / `resources/unsubscribe` | Defer | Memory files are local Markdown and no live resource update stream is required yet. |
| `logging/setLevel` and server log notifications | Defer | Current CLI diagnostics are sufficient; adding client-visible logs needs a privacy review. |
| Tasks | Defer | Current operations complete synchronously; no durable task state is required. |
| Server-initiated roots, sampling, elicitation | Defer | The server should not ask clients for filesystem roots, LLM sampling, or user input for the local memory MVP. |
| Remote HTTP and OAuth | Defer | Out of scope until remote access is explicitly approved. |
| Draft `2026-07-28` modern/stateless support | Defer | Future baseline; requires request metadata and compatibility design beyond local v2.0. |
| MCP Registry publish | Defer | The v2 distribution path is PyPI/TestPyPI plus local Docker and plugin templates; registry publishing needs separate package metadata and moderation review. |
| MCP Tasks extension | Defer | Current local operations finish synchronously or write review packets; task state would add new persistence and cancellation semantics. |
| Exact profile/schema budgets | Plan under `BRG-019` | Generated measurements exist, but families, aliases, effects, profile exposure, byte/token budgets, and docs drift are not yet one exact checked artifact. No new tool or rename is needed to close this gap. |

## Deferred Work And Continuous Assurance

These are post-baseline compatibility checks and recurring quality practices,
not unfinished requirements for the already released v2.0 baseline.

1. Run one GUI MCP client manually with the generated config and record proof
   with `ai-dememory acceptance record`; automated `mcp-client-smoke` now
   verifies generated installed and Docker command/args/env launch behavior.
2. Add weekly regression fixtures only after a reviewed miss has been fixed,
   using
   `ai-dememory recall-fixtures status --strict --max-age-days 14`,
   `ai-dememory recall-fixtures review-plan`, `ai-dememory recall-fixtures
   packet --write-report`, and `ai-dememory recall-fixtures promote-miss`;
   close invalid reviewed misses with
   `ai-dememory recall-fixtures review-miss`. Do not describe unresolved misses
   as promoted fixtures; `RET-001` owns their future held-out representation.
3. Revisit the official SDK after v2.0 if client compatibility issues appear.
4. Reassess MCP Registry publishing only after PyPI/TestPyPI installation and
   real-client local MCP acceptance are complete.
