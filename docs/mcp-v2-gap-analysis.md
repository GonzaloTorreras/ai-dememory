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
| Tools | Implemented | 74 MCP tools expose schemas, annotations, structured output, and bounded writes. `ai-dememory mcp-inventory --check-docs` guards the documented inventory. |
| Resources | Implemented | Public/internal memory resources can be listed/read by id or path. |
| Resource templates | Implemented | `memory://id/{id}` and `memory://path/{path}` are advertised. |
| Prompts | Implemented | Recall, capture proposal, and inbox review prompts are listed/read. |
| Pagination | Implemented | Tool, resource, and prompt list methods return cursors. |
| Safe defaults | Implemented | Private/sensitive memory is excluded from resources and default reads/searches. |
| Package install smoke | Implemented | CI installs the wheel in a fresh environment and verifies vault setup, v2 command surfaces, recall fixture promotion, doctor profile summary, MCP release evidence and publish planning from a fresh vault, and direct MCP `initialize`/`notifications/initialized`/`ping` with response-id matching, missing-response diagnostics, unexpected/invalid/duplicate/result-less/non-object response rejection, and protocolVersion diagnostics. |
| CI workflow guard | Implemented | `ai-dememory ci-guard` verifies required v2 GitHub Actions gates stay present. |
| Generated artifact stage guard | Implemented | `ai-dememory artifact-guard` and `release-check` fail when generated indexes, reports, context exports, build outputs, or caches are staged. |
| Pull request template guard | Implemented | `ai-dememory pr-template-guard` keeps reviewer validation instructions aligned with current v2 gates. |
| Manual acceptance checklist guard | Implemented | `ai-dememory acceptance-guard` keeps checklist items aligned with `ACCEPTANCE_ITEMS` and release evidence. |
| ADR quality guard | Implemented | `ai-dememory adr-guard` validates decision record structure and dependency sections for new ADRs. |
| Release checklist guard | Implemented | `ai-dememory release-checklist-guard` keeps the release checklist aligned with current v2 gates. |
| Generated client config smoke | Implemented | `ai-dememory mcp-client-smoke` launches generated installed and Docker configs, sends `notifications/initialized`, matches JSON-RPC responses by id, verifies `initialize`/`ping`, and verifies config-file `enabled_tools` against paginated `tools/list` when present. |
| Local REST API smoke | Implemented | `ai-dememory api-smoke` verifies loopback health/search/graph, proposal writes, reindexing, API-key enforcement, and non-loopback bind refusal. |
| Vault health over MCP | Implemented | MCP `memory.doctor` returns local readiness checks, selected profile, and a status summary without mutating files. MCP `memory.validate_status` returns the structured `validate --json` payload without writing reports or review state. |
| Durable provenance audit | Implemented | Durable memories require `reviewed: true`, `reviewed_by`, and `reviewed_at`; `ai-dememory provenance` reports gaps. |
| Durable provenance over MCP | Implemented | MCP `memory.provenance_status` reports the same durable provenance audit without writing reports. |
| Working memory over MCP | Implemented | MCP `memory.working_current`, `memory.working_status`, `memory.working_snapshot`, and `memory.working_handoff` inspect/read/write generated working state without mutating canonical memory. |
| Manual acceptance evidence | Implemented | `ai-dememory acceptance` records reviewed proof for human-only release checks and can generate read-only plan reports and reviewer packets; `release-evidence` reports completed, blocked, remaining, readiness summary state, top-level next actions, setup health summary, maintenance summary, and release blockers. MCP exposes read-only status, verification, next-action planning, single-item evidence templates, packet rendering, distribution-checkout release evidence, and release evidence report rendering. |
| Recall quality fixtures | Implemented | `eval-recall` checks curated search expectations before vector migration. |
| Recall fixture promotion | Implemented | `ai-dememory recall-fixtures promote-miss` turns reviewed recall misses into curated fixtures with reviewer provenance, pass validation, and source-miss closure; `ai-dememory recall-fixtures check-miss` and MCP `memory.recall_miss_candidate` check current rank evidence before capture; `ai-dememory recall-fixtures review-miss` and MCP `memory.recall_miss_review` close rejected or dismissed misses without writing fixtures; `recall-fixtures status`, `recall-fixtures review-plan`, `recall-fixtures packet`, MCP `memory.recall_fixture_status`, MCP `memory.recall_review_plan`, and MCP `memory.recall_review_packet` report seed-only, stale, pending, invalid, bounded recent resolved weekly review state, and reviewer handoff guidance. |
| Recall freshness release evidence | Implemented | `ai-dememory release-evidence` includes `recall_fixture_freshness`, `recall_fixture_review_plan`, and `vector_readiness`, and adds quality blockers when current recall eval is unavailable or failing, pending/invalid recall miss files exist, or measured recall failures make a vector experiment eligible for review. |
| Vector readiness | Implemented | `ai-dememory vector status` and MCP `memory.vector_status` report whether measured recall failures justify a future vector experiment without enabling embeddings. |
| Roadmap status | Implemented | `ai-dememory roadmap status` and MCP `memory.roadmap_status` report read-only v2 operational roadmap phase status, including implemented and gated phases. |
| Publish planning | Implemented | `ai-dememory publish-plan` and MCP `memory.publish_plan` report manual TestPyPI/PyPI workflow dispatch inputs, preflight commands, release blockers, and false publish side-effect flags without uploading packages. |
| Runtime smoke | Implemented | PR-gated stdio smoke covers lifecycle negotiation, initialized notification, response-id matching, ping, paginated inventory/resources/prompts, sensitive filters, recall misses, lifecycle feedback, first-run setup plans, setup health with validation status, context config status, manual acceptance readiness, recall review, vector readiness, roadmap status, generated artifact freshness, generated packet archive status, and maintenance preflight, provider import/status/setup plans, maintenance status with generated artifact freshness and generated packet archive cleanup status, installed and Docker scheduler plans, hook config, sleep consolidation, review workflows, advisory review recommendation capture/status/archive status/archive restore preview/outcome links/outcome status, and proposal boundaries. |

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

## Remaining v2.0 Work

1. Run one GUI MCP client manually with the generated config and record proof
   with `ai-dememory acceptance record`; automated `mcp-client-smoke` now
   verifies generated installed and Docker command/args/env launch behavior.
2. Add weekly recall quality fixtures from real retrieval misses using
   `ai-dememory recall-fixtures status --strict --max-age-days 14`,
   `ai-dememory recall-fixtures review-plan`, `ai-dememory recall-fixtures
   packet --write-report`, and `ai-dememory recall-fixtures promote-miss`;
   close invalid reviewed misses with
   `ai-dememory recall-fixtures review-miss`.
3. Revisit the official SDK after v2.0 if client compatibility issues appear.
4. Reassess MCP Registry publishing only after PyPI/TestPyPI installation and
   real-client local MCP acceptance are complete.
