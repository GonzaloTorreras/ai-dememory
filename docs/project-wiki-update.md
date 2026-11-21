# Project wiki update

Approved implementation scope: 2026-11-21. This is the delivery plan for the
user-requested project-local wiki, not a new task DAG. It replaces vault-only
project learning as the preferred new workflow; existing private vaults are not
exported, deleted or migrated automatically.

## Outcome

One project owns `docs/dememory/index.md` and ordinary, linked Markdown pages.
Different harnesses read the same files. A small managed block in `AGENTS.md`
explains selective reading and evidenced learning without replacing other rules.
English templates are useful for software, research, business and personal work.
Only the index is mandatory. Shared knowledge has an explicit read-only binding;
personal values remain private and cannot be promoted or changed by consolidation.

## Delivery units and acceptance

1. **Portable content.** Initialize, save, read, correct and search plain Markdown;
   keep bounded root/topic navigation plus a complete catalog. Never move files
   merely because there are eleven. Warn on oversized pages, broken links and
   uncertain/historical content. Preserve unowned text and concurrent edits.
2. **Librarian and curator.** Local read-only recall is the default. Optional
   assisted recall uses one configured, budgeted provider attempt to select exact
   source excerpts, not invent facts. Preview binds query, settings and source
   revisions; ongoing native-hook consent is separate. Cache lives privately.
   The curator rebuilds navigation and reports problems; it does not silently
   rewrite meanings or personal values. Schedules use the existing foreground UI.
3. **Installation and harnesses.** Existing CLI commands gain project options.
   Codex/Claude hooks can recall without an MCP server. Adapters are trust-gated,
   fail-open and recursion-safe; no transcript scanner or resident child process.
4. **Workbench.** Attach a chosen project, create/edit pages from templates,
   inspect sources and warnings, configure shared reading, provider and cadence,
   and run maintenance from the UI. Existing loopback/Origin/session-token
   protections remain authoritative.
5. **Proof and handoff.** Synthetic end-to-end save/recall/correction, cross-project
   isolation, shared read-only behavior, stale preview/edit refusal, cache,
   provider failure/budget and disabled-module behavior; desktop/mobile UI;
   isolated built-wheel smoke and independent exact-diff reviews.

## Existing contract mapping

The legacy C0 inventory remains evidence, not a claim of completed external gates.
This increment exercises `BRG-003` (explicit project/shared roots), `BRG-019`
(hook effects and bounded context), `RET-001` (recall controls), `CON-001`
(deterministic maintenance), `MEM-001` (portable forms) and `ONB-001` (setup).
No legacy compatibility, graph, observation or external-readback gate is marked
complete by this work. The public V3 reset has no V2 migration requirement.

## Boundaries

- No mandatory model, MCP, daemon, graph/vector database, Node or new dependency.
- No raw conversation capture, automatic private import or global value edits.
- Reader workers are disposable. A visible project conversation can manage the
  wiki but is not a canonical store or a required serialized recall bottleneck.
- No new chat is created implicitly. Native cross-thread management remains a
  harness capability, not a fabricated universal API.
- No automatic package publication, merge, hook trust bypass or installed-runtime
  replacement in this implementation task. These remain separate approvals.

## Recovery

Disable the wiki module/hooks to stop automation; ordinary Markdown still works.
Keep canonical pages and existing vaults. Regenerate navigation/cache when needed.
No cleanup removes source notes or changes their scope. Changes to an existing
page require its exact revision, and unknown hook/AGENTS edits are preserved.
