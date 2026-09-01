# Security policy

## Report privately

Use [GitHub Private Vulnerability Reporting](https://github.com/GonzaloTorreras/ai-dememory/security/advisories/new)
for a suspected vulnerability. Do not put credentials, personal memory or an
undisclosed exploit in a public issue. Synthetic reproductions are preferred.

The supported development surface is current `main`; the latest published
stable package is supported until a newer stable package replaces it. Retired
2.x source paths and historical/private checkouts are not active V3 behavior.

## V3 trust boundaries

- A vault is a user-selected local directory outside the public source repo.
- Canonical Markdown and generated SQLite live under that vault. The index may
  contain copies of memory text and must receive the same filesystem protection.
- The machine-local app config stores only the selected vault path and enabled
  module ids. It stores no memory or credentials.
- `remember` and human `review accept` are canonical writers. Optional modules
  receive a read/proposal API with no canonical-write method.
- The bundled MCP module uses foreground stdio only. It opens no network port
  and creates no child process.
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
- AI/MCP writes end as proposals. Canonical promotion is an explicit human CLI
  operation and proposal acceptance uses a deterministic id to prevent duplicate
  memory if a decision write is retried.
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
- V3 has no cloud, HTTP API, scheduler, hooks, autonomous ingestion or automatic
  durable promotion. A claim about one of those surfaces is not a supported V3
  vulnerability unless that surface is later implemented.

## Reportable examples

Report path escape, symlink traversal, unintended canonical write, proposal
bypass, sensitive output beyond the selected vault, unrequested network or
process activity, index substitution that overrides canonical Markdown, or a
release/workflow path that can publish without the documented approval boundary.
