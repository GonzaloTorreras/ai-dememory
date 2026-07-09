# MCP v2.0 Product Plan

This document defines the production-readiness target for the local personal
memory MCP server.

## Current Target

The v2.0 server should be stable enough to run as a local stdio MCP server for
Codex, Claude, Gemini, Obsidian-adjacent workflows, and future LLM tools without
turning generated artifacts into canonical memory.

## Protocol Baseline

- Target MCP protocol: `2025-11-25`.
- Required server capabilities: `tools`, `resources`, and `prompts`.
- Transport: stdio first. Remote HTTP/OAuth MCP is out of scope until remote
  access is explicitly required. A separate loopback REST API may exist for
  local scripts and dashboards.
- Tool names may use letters, numbers, `_`, `-`, and `.` and should stay unique
  within the server.

References:

- MCP lifecycle: https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
- MCP tools: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- MCP resources: https://modelcontextprotocol.io/specification/2025-11-25/server/resources
- MCP prompts: https://modelcontextprotocol.io/specification/2025-11-25/server/prompts
- MCP security: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- v2.0 protocol gap analysis: `docs/mcp-v2-gap-analysis.md`
- Local operations runbook: `docs/operations.md`
- Scheduler and maintenance: `docs/scheduler.md`
- Scheduler/plugin blueprint: `docs/scheduler-plugin-blueprint.md`
- Codex plugin packaging: `docs/codex-plugin.md`
- Client configuration examples: `docs/mcp-client-config.md`
- v2.0 release checklist: `docs/release-v2-checklist.md`

## v2.0 Acceptance Criteria

- Usable locally: documented setup and the unified `scripts/ai_dememory.py`
  dispatcher work on Windows PowerShell and WSL.
- Discoverable: MCP clients can list tools, resources, and prompts.
- Graph-aware: MCP clients can request generated memory/tag/project/type/scope
  relationships with `memory.graph`.
- Maintenance-aware: local clients can inspect maintenance status, detect
  providers, plan schedules, and capture recall misses without automatic
  durable writes.
- Setup-aware: local clients can request a read-only first-run setup plan and
  combined setup health for validation, recall review, MCP config, providers,
  hooks, schedules, maintenance preflight, generated artifacts, generated
  packet archive cleanup counts, and review queues without installing, reading
  provider files, writing files, or deleting archives.
- Health-aware: local clients can inspect doctor readiness checks without
  mutating files.
- Quality-aware: local clients can inspect recall fixture freshness and pending
  recall miss review work.
- Vector-gated: local clients can inspect vector readiness evidence without
  creating embeddings or enabling vector search.
- Sleep-aware: local clients can prepare consolidation review packets without
  mutating canonical memory.
- Working-aware: local clients can read generated current task state and write
  reviewed handoff material under `working/` without mutating canonical memory.
- Review-aware: clients can inspect review modes and configured review policy,
  request mode-specific review plans, list false-positive and conflict
  candidates, store and inspect advisory review recommendations, link accepted
  outcomes back to recommendation ids, close recommendation artifacts as
  accepted/rejected, inspect archived recommendation history, preview archived
  recommendation restore plans, then create conflict merge proposals without
  mutating canonical memory.
- Safe by default: private/sensitive memories are not returned unless a local
  user explicitly opts in through a supported tool argument.
- Connection-health aware: MCP `ping` receives a prompt empty response.
- Durable-safe: LLM writes are proposals under `inbox/llm-captures/`, never
  direct durable mutations.
- Rebuildable: SQLite index and distilled exports are reproducible from
  Markdown.
- Measurable: recall quality is checked with curated fixtures before adding
  vector search.
- Auditable: retrieval writes to `retrieval_log`; lifecycle scores preserve
  retrieval/outcome feedback across index rebuilds; consolidation is dry-run by
  default; reviewed false positives and conflicts are recorded in
  `.ai-dememory-ignore.toml`; durable provenance can be audited through MCP;
  manual release acceptance proof can be recorded under
  `inbox/release-acceptance/`; MCP clients can inspect manual acceptance
  status, verification, next-action plans, evidence templates, and review
  packets without recording evidence; MCP
  scheduler status reports invalid local scheduler config with stable `valid`
  and `validation_errors` fields without querying the host scheduler; hook
  status reports managed instruction-block state and bounded capture counts
  with review-after due state without writing files or reading raw payload
  bodies; review recommendation artifacts are stored and listed under
  `inbox/review-recommendations/` with `applies_review_decision=false`.
- Bounded: search limits, proposal size limits, repository path boundaries, and
  secret scan redaction are enforced.
- Testable: schema, scanner, indexer, search, resources, prompts, and stdio
  lifecycle have smoke coverage.
- Locally scriptable: non-MCP local tools can use the loopback REST API without
  adding remote-service assumptions.
- Plugin-ready: Codex can install a repo plugin that bundles skills, MCP config,
  and small lifecycle hooks while leaving package install passive.

## Deliberate Non-Goals

- No vector search until retrieval logs prove FTS recall failures.
- No remote HTTP MCP server until authentication and authorization requirements
  are explicit.
- No automatic durable memory mutation.
- No scheduler or provider import side effects during package/plugin install.
- No hook-driven weekly maintenance; OS schedulers own recurring jobs.
- No secret quarantine content in versioned memory.
- No server-initiated roots, sampling, elicitation, tasks, subscriptions, or
  logging notifications until a client workflow requires them and privacy impact
  is reviewed.
- No draft `2026-07-28` modern/stateless support in v2.0; the stable
  `2025-11-25` lifecycle remains the release baseline.

## Next Hardening Steps

1. Run one real MCP client smoke using `docs/mcp-client-config.md`, in addition
   to the repository stdio harness, and record reviewed proof with
   `ai-dememory acceptance record`.
2. Move the MCP implementation behind the official Python MCP SDK or keep the
   manual stdio server only as a compatibility shim if client compatibility
   issues appear.
3. Keep package install, local API, Docker MCP, and MCP stdio smoke checks in CI.
4. Add weekly recall quality fixtures from real retrieval misses with
   `ai-dememory recall-fixtures status`, MCP `memory.recall_fixture_status`,
   MCP `memory.recall_miss_candidate`, MCP `memory.recall_review_plan`, MCP
   `memory.recall_review_packet`, MCP
   `memory.recall_review_packet_archive_status`, MCP
   `memory.recall_review_packet_archive_retention_plan`, MCP
   `memory.recall_miss_review`, MCP `memory.vector_status`, and
   `ai-dememory recall-fixtures promote-miss`. Use
   `ai-dememory recall-fixtures packet --write-report` for human weekly review
   handoffs without promoting fixtures.
   MCP `memory.acceptance_packet_archive_status` lists generated manual
   acceptance packet snapshots without recording evidence. MCP
   `memory.acceptance_packet_archive_retention_plan` previews generated manual
   acceptance packet archive cleanup candidates without deleting files.
5. Revisit durable and release acceptance provenance if reviewer identity needs
   signed approvals or external identity integration.
6. Plan post-v2 work through `PLAN.md`: finish productization integrity, add a
   local shared-memory policy kernel, adversarial evaluation, traceability,
   supersession, quarantine, safe read-only governance surfaces, and gated super
   search without enabling automatic durable writes.
