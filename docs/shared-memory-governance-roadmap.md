# Shared Memory Governance Roadmap

This roadmap is the detailed governance appendix for the master future plan in
`../PLAN.md`. The master plan is the canonical R0-R7 roadmap; this document
keeps the detailed P0-P6 shared-memory governance work breakdown.

The goal is to move from a reviewed personal vault to governed shared memory
that can be used safely by multiple LLM tools, agents, projects, and review
workflows.

This is a planning document. It does not enable remote HTTP, automatic durable
writes, embeddings, provider imports, or scheduler side effects.

## Research Basis

The plan is based on the January-June 2026 shared-memory and agent-memory
research review. The strongest signals were:

- Governed Shared Memory for Multi-Agent LLM Systems: shared memory needs
  explicit subjects, actions, namespaces, direct-read enforcement, supersession,
  and provenance.
- GroupMemBench: shared memory must be tested for speaker grounding,
  multi-party updates, ambiguity, and project/person separation.
- Trojan Hippo: memory poisoning can persist quietly and trigger later.
- AgentLeak: multi-agent systems leak through internal channels, tool
  arguments, and side-channel traces, not only final answers.
- Memory Palace / MemPalace critiques: low-cost verbatim retrieval and
  metadata filters are useful, but spatial metaphors are not enough.
- Engram: bi-temporal memory and invalidation without deletion matter for
  long-running conversations.
- DCPM-style dual process memory: fast capture and slow consolidation should be
  separate, with review gates between them.
- MemORAI-style graph memory: relationship-aware retrieval is useful when it
  preserves provenance and does not replace source text.
- SuperLocalMemory-style local-first memory: SQLite, BM25/FTS, MCP, provenance,
  trust, and per-agent state fit this repository's direction.
- vstash-style hybrid retrieval: FTS plus graph/vector fusion is useful only
  after measured failures justify it.
- Agent libOS-style runtime models: actor identity, process identity,
  capabilities, and checkpoints are useful concepts for shared memory.
- Containment-gap and misattribution-gap work: memory integrity should be
  tested with counterfactuals so failures can be assigned to retrieval, policy,
  summarization, or model behavior.

## Current Gap

The current system is strong as a local, review-first memory vault:

- Markdown is canonical and human editable.
- SQLite FTS is generated and explainable.
- MCP exposes recall, review, setup, release, working-state, and maintenance
  surfaces.
- Sensitive content is excluded by default.
- Durable writes are review-gated.
- Vector search is blocked until recall fixtures prove it is needed.

The gap is that the system does not yet model shared memory as an access-
controlled resource. It lacks actor/action policy, namespace isolation,
bi-temporal validity, poisoning evaluation, direct-id read enforcement tests,
and multi-agent recall fixtures.

## Principles

- Policy applies to every read path, including direct id/path lookups.
- Memory writes are proposals until reviewed; fast capture does not imply
  durable truth.
- Original text remains recoverable; summaries and graph edges are derived.
- Stale, superseded, disputed, and poisoned memories are invalidated without
  silent deletion.
- Tests must cover leakage, poisoning, ambiguity, abstention, and stale updates,
  not only top-N recall.
- Embeddings and hybrid retrieval stay gated behind measured recall failures and
  a reviewed privacy model.

## Phase Summary

| Phase | Theme | Outcome |
| --- | --- | --- |
| P0 | Shared-memory policy model | Actor, namespace, action, trust, and time metadata exist in schema and validation. |
| P1 | Shared-memory evaluation | Fixtures cover leakage, poisoning, stale propagation, direct-id bypass, and multi-party recall. |
| P2 | Bi-temporal supersession | Retrieval can answer current and `as_of` questions without deleting prior facts. |
| P3 | Traceability and attribution | Memory use is auditable across search, context assembly, MCP tools, and outcomes. |
| P4 | Gated hybrid retrieval | Graph and optional vector experiments are measured behind recall and privacy gates. |
| P5 | Poisoning and quarantine defenses | Untrusted captures are isolated, scored, reviewed, and tested before promotion. |
| P6 | MCP and plugin product surface | Shared-memory status, policy checks, traces, and evaluations are exposed safely. |

## P0 - Shared-Memory Policy Model

Outcome: every memory and every tool operation can be evaluated against a
subject, action, namespace, sensitivity, trust, and validity window.

Tasks:

1. Define the shared-memory policy vocabulary.
   - Add planned fields for `actor_id`, `agent_id`, `process_id`,
     `namespace`, `audience`, `channel`, `read_policy`, `write_policy`,
     `source_trust`, `valid_from`, `valid_to`, `transaction_time`,
     `supersedes`, and `superseded_by`.
   - Specify defaults for existing memories so current vaults keep validating.
   - Define which fields are canonical Markdown and which are generated index
     fields.

2. Update schema documentation and templates.
   - Extend `docs/schema.md` with shared-memory fields and compatibility
     defaults.
   - Update `templates/*.md`, `vault-template/templates/*.md`, and packaged
     vault templates.
   - Add examples for personal, project, tool, session, and imported memories.

3. Implement validation without breaking old vaults.
   - Accept missing shared-memory fields as defaulted during an initial
     migration period.
   - Validate enum values, path boundaries, id references, and time windows.
   - Reject policy values that would expose `private`, `sensitive`, or
     `secret-prohibited` memory by default.

4. Apply policy to all read paths.
   - Add a shared policy function used by search, context assembly, MCP
     resources, `memory.get`, direct path lookup, and REST endpoints.
   - Add tests proving direct id/path reads cannot bypass search filtering.
   - Return structured denial reasons without leaking hidden memory content.

5. Add a migration/report mode.
   - Add a read-only report listing memories that rely on defaulted policy
     fields.
   - Provide suggested frontmatter updates without editing canonical memory.
   - Add release evidence that reports whether shared-policy defaults are still
     in use.

Exit criteria:

- Existing vaults validate unchanged.
- New templates include shared-memory fields.
- `memory.get`, resources, search, context, and local API all enforce the same
  read policy.
- Tests cover direct-read bypass and policy denial behavior.

## P1 - Shared-Memory Evaluation

Outcome: recall quality is measured with shared-memory behavior, not only
single-query top-N retrieval.

Tasks:

1. Add a shared-memory fixture format.
   - Support multi-turn scenarios, multiple actors, expected visible ids,
     expected hidden ids, expected abstentions, and expected stale/superseded
     handling.
   - Keep the existing recall fixture format for simple retrieval checks.
   - Secret-scan fixture text and generated reports.

2. Build fixture categories.
   - Direct-id bypass: hidden memory is known by id but denied to the actor.
   - Cross-project leakage: similar project memories must not cross namespaces.
   - Speaker grounding: preferences and facts are attributed to the right
     person/tool/agent.
   - Stale propagation: superseded data must not outrank current data.
   - Contradiction handling: disputed facts trigger review/abstention.
   - Dormant poisoning: untrusted imported text must not become tool guidance.
   - Ambiguous query: retrieval asks for disambiguation or returns scoped
     context.
   - Over-broad context: token budgeting must not include unrelated sensitive
     memories.

3. Add an evaluator.
   - Add a CLI command that runs shared-memory fixtures read-only.
   - Report pass/fail per policy, retrieval, attribution, abstention, and
     freshness dimension.
   - Produce JSON and Markdown review reports under `reports/`.

4. Integrate with release evidence.
   - Add shared-memory evaluation freshness and blockers to release evidence.
   - Keep initial failures advisory until the feature is marked release-gated.
   - Add MCP read-only status once the CLI output is stable.

5. Seed realistic fixtures.
   - Convert current seed recall fixtures into simple shared-memory fixtures.
   - Add at least one fixture for each failure category.
   - Add reviewed promotions from real misses before making the gate strict.

Exit criteria:

- Shared-memory fixture runner exists and is read-only by default.
- At least eight fixture categories have coverage.
- Release evidence reports shared-memory evaluation status.
- Failures explain whether the defect is policy, retrieval, attribution,
  freshness, poisoning, or context assembly.

## P2 - Bi-Temporal Supersession

Outcome: memories can be invalidated, superseded, and queried as of a time
without deleting original evidence.

Tasks:

1. Define time semantics.
   - `valid_from` and `valid_to` describe when a memory claim is true.
   - `transaction_time` describes when the repository accepted or generated the
     memory state.
   - `updated_at` remains human-facing maintenance metadata.

2. Implement supersession chains.
   - Validate `supersedes` and `superseded_by` references.
   - Prevent cycles.
   - Support one-to-many and many-to-one consolidation proposals.
   - Keep old memory searchable only when `include_superseded` or `as_of`
     semantics require it.

3. Add retrieval filters.
   - Support current-only retrieval.
   - Support `as_of` retrieval for historical context.
   - Penalize stale/disputed/superseded memories consistently across FTS,
     context, graph, and MCP.

4. Extend conflict review.
   - Classify conflicts as duplicate, supersession candidate, scope conflict,
     project conflict, and policy conflict.
   - Generate merge/supersession proposals under the inbox only.
   - Require review before canonical status changes.

5. Add tests and reports.
   - Test current retrieval, historical retrieval, supersession cycles, and
     contradictory active facts.
   - Add a report showing unresolved supersession candidates.
   - Add release evidence summary for active unresolved policy/supersession
     conflicts.

Exit criteria:

- Current retrieval excludes superseded memories by default.
- Historical retrieval can still recover prior evidence.
- Supersession chains validate, cannot cycle, and are review-gated.
- Conflict review distinguishes true contradiction from normal versioning.

## P3 - Traceability And Attribution

Outcome: the system can explain which memory influenced a response or decision,
through which path, and with what result.

Tasks:

1. Define trace records.
   - Capture actor, action, query, read path, memory ids, snippets, policy
     decisions, ranking scores, and outcome ids.
   - Redact or omit sensitive snippets unless explicitly allowed.
   - Keep traces generated and disposable unless reviewed into memory.

2. Instrument retrieval paths.
   - Extend search/context output with stable trace ids.
   - Link `memory.mark_seen` and `memory.outcome` to trace ids.
   - Add trace metadata to MCP receipts without echoing hidden content.

3. Instrument write proposals.
   - Link proposals to source trace ids and capture channels.
   - Record whether a write proposal came from user instruction, hook capture,
     provider import, git lesson, or LLM suggestion.
   - Surface missing provenance in setup health.

4. Add trace review tools.
   - Add read-only trace listing and trace detail commands.
   - Add generated reports for recent denied reads, policy overrides, and
     highly reused memories.
   - Keep retention bounded and configurable.

5. Add attribution tests.
   - Verify traces are created for search, context, `memory.get`, and MCP
     resources.
   - Verify sensitive content is not leaked in trace reports.
   - Verify outcome feedback updates the intended memory id.

Exit criteria:

- Every memory returned through supported read paths has a traceable source.
- Denied reads are auditable without revealing hidden content.
- Outcome feedback can be tied to retrieval evidence.
- Trace reports are generated artifacts, not canonical memory.

## P4 - Gated Hybrid Retrieval

Outcome: graph and optional vector retrieval can be tested without replacing
the FTS baseline or weakening privacy.

Tasks:

1. Preserve FTS as the baseline.
   - Keep current SQLite FTS ranking and explanations.
   - Add comparison metrics before changing default ranking.
   - Report whether improvements are due to policy, graph, vector, or better
     fixtures.

2. Add graph-aware retrieval candidates.
   - Use generated graph edges for project, actor, tag, alias, supersession,
     source, and trust relationships.
   - Keep graph edges derived from Markdown/index data.
   - Add explainable graph ranking components.

3. Define vector experiment criteria.
   - Require reviewed recall failures.
   - Require a privacy model for embedding provider, model, retention, and
     local/remote execution.
   - Require rollback and index rebuild instructions.

4. Add reciprocal-rank fusion experiment mode.
   - Compare FTS, graph, optional vector, and fused rankings.
   - Keep experiment output read-only unless an explicit report path is passed.
   - Add fixture-level explanations showing which retrieval path helped or
     hurt.

5. Add regression gates.
   - Hybrid retrieval must not increase sensitive leakage.
   - Hybrid retrieval must not reduce required recall on existing fixtures.
   - Hybrid retrieval must not hide provenance.

Exit criteria:

- Graph-aware ranking can run in report mode.
- Vector experiments remain disabled by default.
- Hybrid retrieval cannot become default without reviewed evidence.
- Reports explain both wins and regressions.

## P5 - Poisoning And Quarantine Defenses

Outcome: untrusted captures are isolated and tested before they can influence
agent behavior.

Tasks:

1. Define trust levels.
   - Add `source_trust` levels such as `trusted`, `reviewed`, `unreviewed`,
     `imported`, `adversarial-test`, and `quarantined`.
   - Define default trust per source kind and capture channel.
   - Keep human-reviewed durable memories highest trust.

2. Add quarantine workflow.
   - Route secret-like, prompt-injection-like, and policy-violating captures to
     quarantine outside canonical memory.
   - Store redacted evidence and review metadata only.
   - Add review commands that can dismiss, reject, or propose sanitized memory.

3. Add poisoning detectors.
   - Detect tool-instruction language in imported conversations.
   - Detect attempts to override memory policy or agent instructions.
   - Detect hidden trigger patterns and suspicious cross-project claims.
   - Keep detectors explainable and conservative.

4. Add adversarial fixtures.
   - Dormant trigger later in a session.
   - Imported text claiming to be system policy.
   - Cross-project instruction smuggling.
   - Poisoned alias that hijacks unrelated searches.
   - Prompt injection inside a quoted memory body.

5. Add review and release reporting.
   - Report active quarantine counts in setup health.
   - Add release blockers only after the workflow is stable.
   - Include stale quarantine review due counts in maintenance status.

Exit criteria:

- Unreviewed imported text cannot become durable guidance automatically.
- Poisoning fixtures prove quarantine and policy denial behavior.
- Reviewers can inspect sanitized evidence without exposing secrets.
- Setup health reports quarantine state.

## P6 - MCP And Plugin Product Surface

Outcome: shared-memory governance is usable from Codex and other local clients
without exposing unsafe write or broad-read capabilities by default.

Tasks:

1. Add read-only MCP tools first.
   - `memory.policy_check`: explain whether an actor/action can read or write a
     target memory.
   - `memory.shared_eval_status`: summarize shared-memory fixture status.
   - `memory.trace_status`: summarize trace availability and retention.
   - `memory.trust_status`: summarize source trust and quarantine counts.

2. Add bounded write tools only after review.
   - `memory.supersession_proposal`: write an inbox proposal, not canonical
     changes.
   - `memory.quarantine_review`: record reviewed quarantine outcomes.
   - `memory.trace_review`: record reviewed trace retention or dismissal
     outcomes.

3. Update plugin allowlists.
   - Keep broad mutation tools server-only by default.
   - Expose read-only status and planning tools to the plugin.
   - Require explicit broader local config for reindex, imports, and
     maintenance actions.

4. Update skills and docs.
   - Add plugin skill guidance for shared-memory recall, policy checks,
     trace review, and quarantine review.
   - Update README, MCP docs, local API docs, and operational loop docs.
   - Add examples for Codex, Claude, and Obsidian-adjacent workflows.

5. Add smoke and manual acceptance coverage.
   - Add CLI smoke for policy status and shared evaluation.
   - Add MCP runtime smoke for read-only tools.
   - Add manual acceptance items for real client policy checks and trace review.

Exit criteria:

- MCP exposes shared-memory governance status without mutating memory.
- Plugin installs stay review-first and safe by default.
- Smoke tests cover new read-only surfaces.
- Manual acceptance tells reviewers how to prove policy and trace behavior in a
  real client.

## Implementation Order

1. Land P0 schema, docs, validation defaults, and direct-read policy tests.
2. Land P1 fixture format and advisory shared-memory evaluator.
3. Land P2 supersession/time semantics, current retrieval filters, and conflict
   review extensions.
4. Land P3 trace records and outcome attribution.
5. Land P5 quarantine workflow before enabling broad provider imports.
6. Land P4 graph/hybrid experiments only after P1-P3 produce enough evidence.
7. Land P6 MCP/plugin surfaces after CLI behavior is stable.

P4 is intentionally after the governance and evaluation work. The repository
should not optimize retrieval before it can prove that retrieval is allowed,
current, attributable, and resistant to poisoning.

The super-search and retrieval-review direction is tracked in `../PLAN.md` R7.
It should remain gated behind the policy, evaluation, traceability, and
quarantine work described here.
