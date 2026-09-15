# Security policy

## Report privately

Use [GitHub Private Vulnerability Reporting](https://github.com/GonzaloTorreras/ai-dememory/security/advisories/new)
for a suspected vulnerability. Do not put credentials, personal memory or an
undisclosed exploit in a public issue. Synthetic reproductions are preferred.

The development surface includes the active V3 branch; the latest published
stable package is supported until a newer stable package replaces it. Retired
2.x source paths and historical/private checkouts are not active V3 behavior.

## V3 trust boundaries

- A vault is a user-selected local directory outside the public source repo.
- Canonical Markdown and generated SQLite live under that vault. The index may
  contain copies of memory text and must receive the same filesystem protection.
- The machine-local app config stores only the selected vault path and enabled
  module ids. It stores no memory or credentials.
- `remember`, human `review accept` and evidenced `CoreServices.learn` are
  canonical writers. Explicit statements/outcomes can become active; inference
  remains provisional. `forget` retires records and can undo a correction.
- The bundled MCP module uses foreground stdio only. It opens no network port
  and creates no child process.
- The optional workbench listens only on loopback, checks Host/Origin and a
  per-start session token for writes, and provides no CORS or remote login.
  Untrusted websites must not read its state or trigger writes/provider calls.
- Configured extraction/consolidation can send selected text to outbound model
  endpoints and ordered fallbacks. Credentials are environment references in
  non-secret settings; each provider gets only its own resolved credential.
- Scopes separate retrieval contexts, not authenticated users. MCP callers and
  enabled plugins are trusted; a caller-provided evidence label is not proof of
  truth. Do not expose this local service as a multi-user or internet service.
- Third-party Python modules are trusted local code with the same authority as
  other installed dependencies. They are not sandboxed; manifest capabilities
  and resource budgets are declarations, not enforcement. `CoreServices` is a
  supported narrow interface, not confinement against bypass by trusted code.

## Implemented invariants

- The CLI uses an explicit `--vault` or saved default and does not treat the
  current checkout as a vault.
- The vault root and its managed directories cannot be symbolic links,
  junctions or paths resolving outside the vault. Nested linked memory paths
  are rejected rather than traversed.
- Only regular, non-linked Markdown files below `memories/` are indexed. The
  generated SQLite file and its WAL/SHM sidecars are also rejected when linked
  or redirected.
- Recall is local SQLite FTS and canonical reads come back from Markdown.
- Generated extraction requires literal source evidence. Exact user quotes may
  be active; paraphrases and assistant claims remain provisional. Model output
  cannot assign correction keys. Generated summaries remain review proposals.
- Recall excludes provisional/retired records and other project scopes.
  Explicit corrections stay in the same scope; stable core occurrence retries
  reuse their canonical identity. Full extraction retry receipts are pending;
  changed candidate indexes/dedupe aliases can still add bounded duplicate facts.
  This is not semantic contradiction detection.
- Provider attempts reserve configured budgets durably before dispatch; request
  and response sizes are bounded, redirects disabled, and non-loopback HTTP
  provider URLs rejected. Activity stores metadata, not raw prompts or errors.
- High-confidence private-key and common token shapes are rejected on memory and
  proposal writes. This is a narrow guard, not a comprehensive DLP scanner.
- Metadata, titles, memory content, MCP input and MCP output-producing reads are
  bounded. The real stdio transport reads and writes UTF-8 bytes on every
  platform.
- The generated index can be deleted and rebuilt from Markdown.

## User responsibilities and limitations

- Protect the operating-system account, vault directory, backups and any sync
  remote. Do not store credentials or secrets in memory.
- Review an optional module before installing it. The core cannot confine
  arbitrary Python package code.
- An AI client controls data after an authorized MCP response leaves this
  process.
- Secret detection is intentionally conservative and can miss sensitive prose.
- Remote inbound access, authentication and automatic harness hook installation
  are not implemented. Local HTTP, foreground scheduling and sourced learning
  are implemented and are in review scope. Never exclude their findings using
  the previous proposal-only architecture.
- `runtime.sqlite` budget receipts and `jobs.json` are durable operational state,
  unlike disposable search indexes. Protect and back them up with the vault.
- Provider prices/usage are estimates, not invoice enforcement. A synchronous
  model job can temporarily block local UI requests. Process/power failure
  between two Markdown correction writes can require manual reconciliation.

## Reportable examples

Report path escape, symlink traversal, unintended canonical write, proposal
bypass, sensitive output beyond the selected vault, unrequested network or
process activity, index substitution that overrides canonical Markdown, or a
release/workflow path that can publish without the documented approval boundary.
