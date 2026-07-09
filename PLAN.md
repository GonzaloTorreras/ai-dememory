# ai DeMemory Future Roadmap

This is the master future plan for `ai-dememory`. It is separate from
`ai-dememory roadmap status`, which reports current v2 implementation evidence.

The guiding target:

> Prove which agent may see which memory, why, when, and with what evidence.

## Product Boundary

The next roadmap should optimize for one human owner using many local tools,
agents, projects, and provider imports. It should not quietly become a hosted
team memory service.

Near-term assumptions:

- Local-first vaults remain the default.
- Markdown remains canonical.
- Generated indexes, traces, reports, and caches remain disposable.
- MCP and the local REST API remain local integration surfaces.
- LLM writes remain proposals unless a human reviewer promotes them.
- Retrieval changes must be measured against fixtures before becoming default.

Non-goals until explicitly approved:

- Remote multi-user service semantics.
- Remote MCP/OAuth product work.
- Automatic durable memory mutation.
- Vector retrieval as a default path.
- Provider/model calls inside retrieval without a privacy, latency, and cost
  gate.

## Current Baseline

The v2 local readiness baseline is mostly implemented:

- Release and CI guards are in place.
- Search and context assembly are explainable and token-budgeted.
- Working memory, lifecycle feedback, review workflows, hooks, imports, git
  lessons, and release evidence exist.
- Optional vector search is gated because current recall fixtures pass.

This means the next roadmap should not start with better embeddings or broader
automation. It should start with governance and evaluation.

## R0 - Productization And Plan Integrity

Outcome: the existing v2 product is releasable, installable, and documented
without broken roadmap links or ambiguous release signals.

Focus:

- Keep `README.md`, `docs/roadmap-status.md`, `docs/mcp-v2.md`, and this file
  aligned.
- Track future-planning documents that are linked from canonical docs.
- Keep package install, Docker stdio MCP, local API, release-check, and full unit
  tests green.
- Record real-client MCP acceptance evidence before calling v2 complete.
- Add a lightweight docs-link guard if broken internal links recur.

Exit criteria:

- No tracked doc links point to missing or untracked planning files.
- `release-check` and the unit suite pass from a clean worktree.
- Manual acceptance evidence identifies remaining release blockers plainly.

## R1 - Local Shared-Memory Policy Kernel

Outcome: every read and write proposal can be evaluated against the same local
policy model.

Start with existing fields before adding schema surface area:

- `scope`
- `project`
- `sensitivity`
- `source.kind`
- `status`
- `reviewed`
- `pin`
- `decay`
- `review_after`

Add an explicit access context:

- actor or client id
- tool or agent id
- action
- requested namespace or project
- read path, such as search, context, direct id, MCP resource, or REST endpoint

Focus:

- Implement one shared policy function.
- Apply it to search, context, `memory.get`, MCP resources, local REST
  `/memories/{id}`, graph-derived context, and direct path/id lookups.
- Return structured denial reasons without leaking hidden memory content.
- Default missing future fields conservatively so existing vaults keep
  validating.

Exit criteria:

- Direct-id reads cannot bypass sensitivity, namespace, status, or project
  policy.
- Policy decisions are testable and explainable.
- Existing vaults validate unchanged.

## R2 - Shared-Memory And Adversarial Evaluation

Outcome: quality is measured against shared-memory failure modes, not only
single-query top-N recall.

Fixture categories:

- Direct-id bypass denial.
- Cross-project leakage.
- Speaker or actor misattribution.
- Similar memories in different namespaces.
- Stale or superseded facts.
- Contradictory facts that require abstention or review.
- Poisoned imported text.
- Prompt injection inside quoted memory.
- Ambiguous queries that should narrow scope.
- Over-broad context packing that would include unrelated sensitive memory.

Focus:

- Keep current recall fixtures for simple retrieval.
- Add a shared-memory fixture format for multi-actor and policy-sensitive cases.
- Report failures by dimension: policy, retrieval, attribution, freshness,
  poisoning, context assembly, or abstention.
- Keep the new gate advisory until it has real reviewed examples.

Exit criteria:

- At least one fixture exists for each high-risk shared-memory failure mode.
- Fixture reports explain why a case failed.
- Release evidence can show shared-memory evaluation status without mutating
  memory.

## R3 - Traceability And Attribution

Outcome: the system can explain which memory influenced a result, through which
path, and under which policy decision.

Focus:

- Attach trace ids to search, context, `memory.get`, MCP resources, REST reads,
  and outcome feedback.
- Record allowed and denied reads without exposing denied memory content.
- Tie `memory.mark_seen` and `memory.outcome` to trace ids instead of only
  relying on "last result" state.
- Keep trace records generated and retention-bounded unless reviewed into
  canonical memory.

Exit criteria:

- Every returned memory has traceable policy and ranking evidence.
- Denied reads are auditable without leaking hidden content.
- Outcome feedback can be traced back to the exact retrieval evidence.

## R4 - Supersession And Time Semantics

Outcome: memory can distinguish current truth, historical truth, and disputed
truth without deleting evidence.

Focus:

- Define `valid_from`, `valid_to`, and accepted transaction time semantics.
- Add reviewed supersession proposals instead of silent overwrites.
- Prevent supersession cycles.
- Keep current retrieval current-only by default.
- Allow explicit historical `as_of` retrieval when needed.

Exit criteria:

- Superseded memory does not outrank current memory by default.
- Historical retrieval can still recover prior evidence.
- Conflict review can distinguish duplicate, supersession, and true
  contradiction.

## R5 - Quarantine And Poisoning Defenses

Outcome: untrusted captures cannot become agent guidance just because they were
imported or indexed.

Focus:

- Define source trust levels such as reviewed, trusted, unreviewed, imported,
  adversarial-test, and quarantined.
- Route secret-like, prompt-injection-like, and policy-overriding captures to
  quarantine/review paths.
- Detect imported text that claims to be system policy, tool policy, or hidden
  instruction.
- Add poisoning fixtures before any broad provider-import or consolidation
  automation is allowed to influence context.

Exit criteria:

- Unreviewed imports cannot become durable guidance automatically.
- Poisoning fixtures prove denial or quarantine behavior.
- Setup health and maintenance status show quarantine counts and review due
  state.

## R6 - Read-Only Governance Product Surface

Outcome: governance is usable from Codex and other local clients without
exposing broad mutation by default.

Focus:

- Add read-only CLI/MCP status first:
  - policy status
  - policy check
  - shared evaluation status
  - trace status
  - trust/quarantine status
- Keep mutation tools proposal-only or server-only by default.
- Update plugin skills only after CLI behavior is stable.

Exit criteria:

- Codex plugin users can inspect governance state safely.
- Broader local configs remain explicit opt-ins.
- Manual acceptance explains how to verify policy, trace, and quarantine
  behavior in a real client.

## R7 - Super Search And Retrieval Review

Outcome: retrieval becomes robust to typos, aliases, fuzzy wording, and useful
memory combinations while remaining policy-gated, explainable, cheap, and low
latency.

This is not "turn vectors on." It is a staged retrieval-review layer that can
combine deterministic search, fuzzy matching, graph hints, optional embeddings,
and an optional cheap reviewer model.

Capabilities to explore:

- Strong fuzzy lexical matching for typos, accents, spelling variants, slugs,
  casing, and renamed projects.
- Alias and synonym expansion derived from reviewed metadata.
- Query rewriting that stays local and explainable by default.
- Candidate bundle review: decide whether memory X, X+Y, or a larger memory set
  is worth including.
- Optional "retrieval reviewer" connector: a local model or approved provider
  model that cheaply judges candidate usefulness before context is assembled.
- Strict latency, token, cost, and privacy budgets.
- Deterministic fallback when the reviewer connector is unavailable or not
  approved.

Gates:

- Policy filtering happens before any optional reviewer sees candidates.
- Private, sensitive, and denied memories are never sent to a provider reviewer.
- Provider use requires explicit local configuration and a reviewed privacy
  model.
- The feature stays advisory until shared-memory fixtures show it improves
  results without increasing leakage or hiding provenance.

Exit criteria:

- Fuzzy search improves measured misses without reducing precision on existing
  fixtures.
- Candidate-bundle review explains why memory X, X+Y, or a larger set was
  included or excluded.
- Latency and cost are bounded in reports.
- Super search cannot bypass policy, traceability, or quarantine.

## Implementation Order

1. R0: make the plan and release docs internally consistent.
2. R1: implement the shared policy kernel and direct-read bypass tests.
3. R2: add shared-memory and adversarial evaluation.
4. R3: add traceability and attribution.
5. R4: add supersession and time semantics.
6. R5: add quarantine and poisoning defenses.
7. R6: expose safe read-only governance status through MCP/plugin surfaces.
8. R7: add super-search experiments only after policy, evaluation, and traces
   can prove the retrieval is allowed, useful, current, and attributable.

## Supporting Docs

- Current implementation status: `docs/roadmap-status.md`
- Detailed governance appendix: `docs/shared-memory-governance-roadmap.md`
- MCP v2 product plan: `docs/mcp-v2.md`
- Memory quality and recall fixtures: `docs/memory-quality.md`
- Future vector gate: `docs/vector-migration.md`
- Review workflows: `docs/review-workflows.md`
- Operational loop: `docs/operational-loop.md`
