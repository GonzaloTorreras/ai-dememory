# Project wiki

Source candidate `3.0.0a6`; not a claim that the candidate is published or installed.

## Start with your project, not another store

Install this source candidate, then use an existing project folder:

```bash
ai-dememory setup --project . --yes
ai-dememory remember "Check attachments during restore tests." --project . --page lessons.md --title "Restore lessons"
ai-dememory recall "restore attachments" --project .
ai-dememory status --project .
```

Setup creates `docs/dememory/index.md` and adds a marked block to `AGENTS.md`.
It preserves existing instructions and manual index text. Only the index is
mandatory; overview, decisions, lessons, procedures, references, tools and
architecture are optional English templates. Content may remain in its original
language. Do not copy existing architecture/reference documents: link to them.

Wiki files are ordinary UTF-8 Markdown. A project with no DeMemory installation
still has readable pages and relative links. No provider, database or MCP server
is needed to edit or search a standalone wiki. Git versioning/publication is your
choice: a folder inside a repository is not permission to publish its contents.
Keep personal values, credentials and unrelated project information outside
public project memory. Setup never imports a private vault or conversations.

## Pages, navigation and correction

Use a page for a useful subject, not each turn or each isolated sentence. Update
an existing page with its conditions, exceptions and evidence. `overview.md` can
explain a study, renovation or business as well as software; `architecture.md`
is optional. `pills` describes returned compact context, not another canonical
copy of the same knowledge.

The generated root/topic indexes are small routing maps (about 2,400 characters
of generated root content and at most twelve direct entries). A complete
`catalog.md` preserves navigation to additional pages. Existing topic folders get
indexes; files are never moved merely because their count passes ten. Human text
outside marked index blocks is preserved and can exceed the suggested budget.

Typical pages should remain independently useful and short. Maintenance warns
above 6,000 characters, on broken/unsafe links and skipped inputs. Initial limits
are 500 pages, 24,000 characters/page and three topic-directory levels; these are
bounded implementation choices, not demonstrated optimal sizes. Current search
scans bounded local pages using literal/accent-normalized terms; it is not
semantic translation. Oversized matching sections are omitted with a warning,
not cut mid-sentence to fabricate a shorter claim.

Optional status markers are plain Markdown comments:

```md
<!-- dememory-status: provisional -->
```

`current` is the default. Provisional and archived pages are visible for editing
but excluded from factual recall; pages under `archive/` are historical. No marker
proves truth. When a page contains both current decisions and history, distinguish
them clearly in its text rather than pretending a page-level flag resolves them.

The dashboard sends the displayed SHA-256 revision on save. CLI updates require
`--expected-revision` from JSON recall sources or save readback; a missing/stale revision
never silently replaces an existing page. Direct file edits remain possible.
Page writes are atomic and writers fail fast on contention. Navigation is
rebuildable; page and index writes are not one filesystem transaction.

## Native hooks, without mandatory MCP

```bash
ai-dememory setup --project . --with-codex --yes
ai-dememory setup --project . --with-claude --yes
```

These merge owned local hooks without replacing unrelated client entries. Review
and trust them in the client; installation does not bypass trust. Prompt hooks
return bounded relevant reference text. SessionStart gives brief wiki guidance;
SessionEnd refreshes navigation locally after file edits. There is no blocking
Stop continuation, transcript reader or resident worker. A recursion marker keeps
memory worker invocations from calling themselves.

Existing global DeMemory prompt hooks prefer an initialized wiki for an enabled
project, but remain local-only: their short legacy timeout cannot safely host a
provider child. Newly installed wiki prompt hooks reserve a 25-second outer
cleanup budget around a three-second provider timeout; startup/cleanup is not a
three-second wall-clock promise. SessionStart/SessionEnd retain three seconds.
Do not install duplicate local and global prompt hooks unnecessarily;
client discovery/version behavior must be verified in the intended client.
Other harnesses can follow `AGENTS.md`; this does not claim native event-plugin
acceptance for every provider. Ordinary folder copying preserves content but
local routing/authentication must be rebound on another host.

## Workbench, shared reading and assistance

Enable the wiki module in Modules and open Project wiki. A selected private vault
is needed for this optional UI, provider budgets and operational metadata, not for
standalone wiki content. Attach an absolute project folder with explicit consent;
create/edit a page, inspect its revision, or search and open an exact source.

Shared wiki configuration names another initialized **project folder**. It is
read-only from the consumer: no cloning, junction or automatic value promotion.
The shared folder may be private and outside the repository. Only selected
source excerpts from it enter recall. Disable sharing to remove that input.

Local recall is the default and makes no model calls. Assisted recall uses an
existing generative provider profile, including the optional native Codex account
adapter. A preview binds the query, candidate excerpts, source revisions and
provider configuration. Confirmation sends only the displayed query/excerpts,
not a conversation history, absolute project paths or credentials.

The current fast librarian returns selected source IDs; code formats the exact
excerpts. It does not invent a generative summary. An empty selection is valid.
One provider attempt uses shared daily call/token/cost reservations, no paid
fallback chain, with a three-second cooperative provider timeout. Native process
and I/O cleanup are bounded by the existing adapter; this is not a universal
wall-clock latency guarantee. A failed/busy/budgeted attempt falls back to local
recall. Successful results are cached privately by query/config/source revisions;
identical failed automatic requests are not endlessly charged.

Native automatic assistance has **separate ongoing consent**, off by default.
Workbench session API keys cannot be copied into hooks: choose environment,
local no-auth or Codex account authentication, or keep manual preview assistance.
Jev is not a text-generating librarian; its existing advisory judgments remain
independent and do not change wiki admission or ranking.

## Maintenance and management

The curator currently rebuilds navigation and diagnoses links/size/lifecycle. It
does not automatically merge meanings, resolve contradictions or rewrite values.
An authorized host assistant can maintain the same pages through normal file
tools using the project guidance. A visible management conversation is optional,
replaceable and never the sole memory store; none is created implicitly.

The UI can schedule local maintenance per project while its foreground process
runs, at most one project per tick. This does not enable model consolidation or
history ingestion. An explicitly configured external scheduler may invoke
`ai-dememory serve wiki --run-due` once; no new OS task is installed automatically.
Private registry, locks, budgets and cache stay outside `docs/dememory/` and Git.

Disable the wiki module to stop future hook/assisted/scheduled work. Plain pages
remain readable. Never delete the private vault as part of trying this feature.
