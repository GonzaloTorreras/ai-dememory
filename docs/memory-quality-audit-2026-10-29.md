# Memory quality audit and correction plan — 2026-10-29

This report records an inspection of the installed V3 vault and source at
`e7b2941`. It is planning evidence, not a cleanup receipt. Private memory text,
identifiers, project names and per-record decisions remain in a local private
inventory outside this repository. No canonical memory or installed settings
were changed. The active product sequence remains [roadmap.md](roadmap.md).

## What was inspected

- Every canonical Markdown memory at the final snapshot: 141 files, 167,904 bytes, 82,479 body
  characters, dated 2026-09-15 through 2026-10-28. All bodies and stored evidence
  excerpts were read. No original conversation transcripts were imported.
- Installed package shape, provider/job settings, generated-index status and
  existing runtime tables, queried read-only. No credentials were read.
- Learning, scoped retrieval, hooks, lifecycle and consolidation code in the
  installed runtime and the active V3 source checkout.
- Nine local retrieval probes on separate disposable copies, using the installed
  implementation and the current source. No model or network calls.

The other historical checkout remains dirty and retired; it was not modified.
No open public PR was returned by the GitHub connector on this inspection.
The starting snapshot had 140 records. A concurrent writer added one dated
completion receipt during the audit; it was read and added to the final manifest.
The original 140 remained byte-identical. Retrieval probes use the initial
140-record snapshot, not a moving corpus. Public `main`'s Memory model was also
read through GitHub and still lacks the local quality fields.

## Verified inventory

| Observation | Count / state |
| --- | --- |
| Canonical records | 141 |
| Active / superseded / forgotten | 138 / 2 / 1 |
| Evidence labels: verified outcome / user statement / inference | 78 / 63 / 0 |
| Scopes with memory / global records | 12 project scopes / 0 |
| Readable label coverage | All 12 populated scopes; 16 labels known overall |
| Records with a correction key / supersession link | 65 / 2 |
| Exact normalized content duplicates within a scope | 0 |
| Explicit importance, lifecycle kind or expiry fields | 0 records |
| Stored evidence excerpt lengths | 7–425 characters |
| Provider profiles / routes / recorded provider attempts | 0 / 0 / 0 |
| Scheduled maintenance | Weekly, fixed `global` scope |
| Last saved run | 2026-10-28 07:00:43 UTC; zero changes, no-op |
| Existing hook metadata rows | 526; 326 recalled zero memories |

The installed runtime reports `3.0.0a2` and its Memory model lacks importance,
confidence, memory kind and expiry. Source at `e7b2941` also reports `3.0.0a2`,
but includes those fields. A version string alone therefore cannot identify
which behavior the user actually has. Jev is neither installed as this new
module nor enabled in the observed runtime.

The zero provider-attempt count describes DeMemory's provider jobs, not the
host agent's inference. All stored records have Codex provenance. MCP host
learning is demonstrably useful without a separately configured provider.

## Findings and causes

### 1. Delivery did not reach the runtime — highest priority

The September implementation fixed title weighting and added lifecycle,
importance and scoped proposals/scheduling, but the installed implementation
still uses the earlier BM25 weights and model shape. Shipping more source-only
features will not improve the working memory.

Deliver one uniquely versioned artifact and read back its executable, module
path, feature support and actual Codex hook/MCP runtime. Use a disposable vault
first, then a recoverable upgrade of the existing vault. Preserve identities and
data; this is an update within V3, not V2 migration work.

### 2. Maintenance targets an empty pool

Every memory belongs to a project, while the weekly task selects global. Its
latest no-op is expected. The installed consolidator also deliberately skips
model summaries for project scopes, and there is no configured model route.
This is a configuration and capability gap, not evidence that a model failed.

Use the existing selected/all-project scheduler after upgrade. Its three-scope
batch means twelve projects need at least four intervals. A daily cadence would
visit them in four days when budgets permit; a weekly cadence would take four
weeks. Display due/deferred/visited counts and separate local cleanup from
optional model summaries. No second scheduler or daemon is needed.

### 3. Historical states accumulate as active facts

The corpus contains successive inventory, installation, access, design and
implementation checkpoints. Earlier "unknown/not installed/pending" claims
coexist with later confirmations. These are often valid dated observations,
not logically inconsistent statements. Retrieval does not choose the current
state of the identified subject before composing context.

Existing keys frequently name a revision or completed step rather than the
stable subject. Different keys therefore never supersede one another. Whole
paragraphs also combine enduring preferences with temporary state. Replacing
the entire paragraph would lose useful qualifications.

Reuse `key`, `supersedes`, `memory_kind` and `expires_at`. Split mixed records
into a short subject-specific fact and a dated execution episode. Keep explicit
user correction behavior; do not infer a correction from a newer timestamp or
semantic similarity alone. A verified machine-state refresh may replace the
same narrowly identified machine-state key after its evidence is checked; it
cannot replace a durable user value. Preserve the earlier episode for history.

### 4. Evidence kind is too coarse for mixed paragraphs

Some user-statement records include interpretation, assumed units, generated
visual details or one-time permission. Some evidence excerpts contain only a
number/year, while the paragraph supplies the missing subject. A valid source
occurrence establishes where a statement was recorded, not that every claim in
the paragraph was stated or independently verified.

Keep explicit facts, approximate values and conditions. Separate assumptions
into provisional records. Include enough bounded question/answer context to
interpret a numeric answer; do not reconstruct missing context from guesses or
copy full conversations. One-time approvals belong to task history and never
become reusable permission. Host-asserted `verified_outcome` remains an assertion
with provenance, not a calibrated truth score.

The source extraction path also needs completion: `LearningJobs._valid_candidate`
accepts only title/content/evidence/message index, and `_extract_once` does not
pass lifecycle metadata to `learn`. Its normal paraphrases become provisional
whenever content differs from the literal evidence, while native host learning
can assert an active paraphrase. Merely shipping the new metadata fields will
therefore not classify future automatic extraction. Make explicit evidence,
claim interpretation and lifecycle consistent across the existing entry points;
keep routine supported facts automatic and genuinely uncertain deductions
provisional. Add one end-to-end extraction case rather than another admission
framework or a mandatory model call for each write.

### 5. Exact deduplication misses the actual problem

There are zero exact normalized duplicate bodies. Existing cleanup compares
exact text and leaves keyed/corrected records alone, so a no-op says little about
quality. Semantic overlaps and outdated subclaims remain invisible.

Do not start by deleting similar paragraphs. First reconcile identified
subjects and extract reusable lessons. Similar terms can refer to different
entities, activities, versions or design assumptions. The review found examples
where merging on wording would create a false contradiction.

### 6. Source improvements do not resolve current-state selection

Seven hand-selected positive probes all contained their target in top three,
but only four placed it first in either implementation. Six of the seven also
returned at least one dated state candidate. Source improved some ordering but
still mixed historical and current states. One nonsense query returned nothing;
a separate feature query exposed absent knowledge rather than a retrieval miss.

This is diagnostic evidence, not an accuracy benchmark or an estimate of real
failure probability. Add representative Spanish/English queries and explicit
historical/current expectations before tuning scores. Keep scope/status/expiry
eligibility ahead of ranking and allow empty results.

Jev's existing manual support/comparison evaluator is not a relevance selector.
Once state cleanup and candidate coverage are demonstrated, extend its existing
module with optional `rerank` and compare against the deterministic baseline.
Query relevance must not become permanent importance or truth. Opted-in external
reranking would send query text as well as candidate text; expose that preview.
Keep prompt-hook retrieval local during the initial evaluation.

### 7. General preferences are confined to projects

All records are project-scoped, including some statements about browser behavior,
report language, Linux logging or harness simplicity. Other projects cannot
retrieve them. However, a broadly worded statement made for one project is not
automatically a global instruction.

Five specific scope-review candidates are listed privately. Offer an explicit
global/project choice; promote only the approved general claim, without copying
its unrelated project detail. Preserve all current scope IDs and labels.

### 8. Observability describes activity, not usefulness

Recorded hook duration has p50 108 ms, p95 468 ms and maximum 1,984 ms over 526
rows. The sample mixes trivial skips and actual retrieval; it does not measure
model latency, RSS, relevance, end-to-end response time or causal benefit.
The hook can inject memory and then instruct the agent to call `memory.context`
again. This can duplicate context and work on the same question.

Reuse metadata-only hook/activity records. Distinguish skipped/no-match/returned
and current runtime identity. Avoid a second automatic recall when the already
injected context suffices; explicitly request a deeper retrieval when needed.
Do not add raw prompts or transcripts to logs.

## Proposed cleanup, covering all 141 records

| Proposed disposition | Records | Meaning |
| --- | --- | --- |
| Keep | 43 | Scoped explicit knowledge/requirements with useful qualifications |
| Split or reconcile | 22 | Mixed authority, missing context or partly outdated state |
| Review as execution episodes | 73 | Predominantly dated activity; extract useful facts first |
| Preserve existing inactive history | 3 | No reactivation or deletion |

These are review candidates, not automated classifications or deletion targets.
In particular, expiring all 73 episode candidates immediately would discard
some of the only evidence for the current state. No target record count or
compression ratio should substitute for retaining useful facts.

The private manifest enumerates every file, ID, scope, original SHA-256,
disposition and reason. It proposes zero physical deletions. The inventory is
not a recovery backup. Before any application, save exact canonical bytes,
configuration and a consistent operational SQLite backup outside Git; verify
restoration. Recheck hashes immediately before each edit, journal the mutation,
preserve source provenance and reject concurrent drift. Rebuild only the
generated search index. Review new summaries before retiring their inputs.

## Vertical delivery order

| Slice | Working result | Acceptance |
| --- | --- | --- |
| A. Deliver the existing fixes | A uniquely versioned wheel and the same behavior in CLI, MCP, hooks and UI | Isolated install, real terminal and native Codex save/recall; optional metadata survives; rollback restores matching runtime and data |
| B. Repair one current-state family | Reviewed split/current facts/history for a small family from the private manifest | Correct current answer, explicit historical lookup, original evidence retained, undo and scope isolation |
| C. Apply the remaining manifest | Per-project preview and bounded reviewed batches using existing writers | All 141 inputs accounted for; no unexplained disappearance, original-byte restore, no inferred permission or cross-entity merge |
| D. Maintain populated projects | Existing scheduler targets populated scopes; UI shows coverage and limits | Twelve-project rotation, no-op reason, restart, pause and shared budgets; default cleanup stays model-free |
| E. Improve admission and recall | Better single-claim capture, episode metadata and reusable subject keys | Known mixed/numeric/context cases; no feedback boost from retrieval; no-match and Spanish/English replay |
| F. Evaluate optional Jev reranking | Existing Recall UI compares baseline with bounded semantic selection | Labeled local fixtures first; external opt-in and measured usefulness/cost/latency before automatic use |

Each slice should land as a small reviewed PR and produce installed acceptance
where runtime changes are involved. Do not reopen completed source work as a new
framework. No Node service, vector store, new command family or learning ledger
is justified by this 141-record corpus.

## Continued development

- Review a small set of current/historical/no-answer cases after each artifact
  update, then the relevant regression suite. Existing test totals are not proof
  of recall quality in a user's vault.
- Revisit mixed and newly expired episodes in the existing weekly maintenance
  view; automate routine explicit capture, reserve review for uncertain merges,
  scope changes and lossy consolidation.
- Track useful top-three selection, missing-candidate cases, stale-state leakage,
  user correction rate and optional provider cost. Keep uncertainty visible;
  there is no measured probability of harm to report from these probes.
- Expand candidate retrieval only if misses demonstrate it. Add model-based
  ranking only if the simpler baseline still needs it. Defer remote networking
  until the local installed loop is reliable.

## Verification and limits

All 140 initial memory hashes matched after analysis; the additional concurrent
record was separately read and included, with all 141 hashes/count matching the
closing manifest. No parse failures, duplicate active keys or Unicode replacement
characters were observed. No external personal facts, infrastructure state or
historic test receipts were independently revalidated: this audit evaluates
stored knowledge and current memory behavior, not those external systems.

The retrieval probes wrote only their disposable copies. Existing runtime tables
were read-only. No global configuration, provider activation, release, merge,
scheduled task or private memory was changed.
