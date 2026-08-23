# Security Policy

## Reporting A Vulnerability

Report suspected vulnerabilities through
[GitHub Private Vulnerability Reporting](https://github.com/GonzaloTorreras/ai-dememory/security/advisories/new).
Do not open a public issue, discussion, or pull request for an undisclosed
vulnerability, and do not include real credentials, private-memory content, or
personal data in a report. Use synthetic evidence wherever possible.

Include the affected version or commit, platform, reachable surface, expected
security property, observed result, and the smallest safe reproduction. GitHub
will keep the initial report private so scope, remediation, credit, and any
coordinated disclosure can be agreed before publication. This project does not
currently promise a response-time SLA or a bug bounty.

For ordinary bugs and documentation errors that do not create a security impact,
use the public issue tracker instead.

## Supported Versions

| Channel | Security support |
| --- | --- |
| Latest published stable release | Supported |
| Current default branch | Supported as unreleased development code |
| Older releases and historical/private checkouts | Not supported; reproduce on the latest stable release or current `main` |

The README states the exact current stable and source versions. Security fixes
normally land on protected `main` first and are released through the repository's
explicit, immutable-tag workflow. Published versions and tags are never replaced.

## System And Scope

This policy covers the public `ai-dememory` source and package, including:

- the Python CLI, local MCP server, optional local HTTP API, hooks, scheduler,
  maintenance and provider-import flows;
- Markdown parsing, generated SQLite/vector indexes, search, recall, graph,
  review, consolidation, and writer paths;
- generated client/plugin configuration, resource profiles, process ownership,
  and cleanup behavior;
- package, container, CI, tag, release, and trusted-publishing workflows; and
- the static documentation source shipped in this repository.

Private personal or project memory belongs in a separately bound vault. The
checked-in `memories/**` content is public fixture data, not a production vault.
The public source checkout, installed executable, and private vault are distinct
security boundaries and must not be collapsed into one directory or repository.

## Threat Model And Trust Boundaries

Treat Markdown/frontmatter, filenames, provider files, hook payloads, local
configuration, CLI/MCP/HTTP arguments, generated or stale index rows, imported
archive material, and release-dispatch inputs as attacker-controlled until they
are validated for their exact operation.

The local operating-system account and an explicitly selected vault root are the
primary trust anchors. An MCP or AI host is a separate process with its own data
handling policy: ai-dememory can constrain what it returns, but cannot guarantee
what that host does with content after an authorized response. GitHub branch and
environment protection, pinned workflow dependencies, OIDC Trusted Publishing,
and exact commit/tag authorization form the release trust boundary.

SQLite and vector indexes are generated hints, not authorities. Canonical
Markdown, its identity, current content hash, sensitivity, and review state must
be revalidated before indexed data influences a memory-bearing response or
write.

## Security Invariants

The following properties must hold:

- Every filesystem read, write, import, report, archive, and generated artifact
  remains inside its explicitly bound root and fails closed on traversal,
  symlink, junction, or identity ambiguity.
- Secret-like material is rejected or quarantined outside versioned memory and
  is not echoed in diagnostics, reports, recall results, or release evidence.
- Canonical Markdown remains authoritative. Stale or manipulated indexes cannot
  bypass canonical path, ID, content-hash, sensitivity, or review checks.
- Public-repository recall is restricted to revalidated `public` memories and
  excludes working, `internal`, `private`, `sensitive`, and secret-prohibited
  content before ranking and limiting.
- Durable pins and destructive review decisions require explicit human approval.
  Automation is preview-first, hash-bound where applied, and cannot silently
  promote raw captures into durable memory.
- The HTTP API binds to loopback by default. A non-loopback bind requires both an
  API key and TLS; credentials must not enter repository configuration or logs.
- Scans, imports, graph operations, recall, maintenance, reports, and MCP sessions
  enforce documented resource ceilings. Package-owned descendants remain in an
  owned process group or tree and are reaped on timeout, cancellation, or parent
  exit. Generated MCP configurations retain a bounded idle lease unless a user
  deliberately opts into a supervised persistent server.
- Python owns canonical memory and security policy. Optional Node/browser tooling
  may provide validation or presentation, but cannot become an alternate memory,
  writer, secret, or release authority.
- A package release is authorized only by the documented exact intent, tag, and
  commit tuple, protected environments, immutable tags, and the single canonical
  OIDC publisher. A branch push, successful CI run, legacy preflight, or local
  readiness report alone cannot publish.
- Pull-request documentation validation has no Pages, OIDC, environment, secret,
  or artifact-upload capability. Pages delivery is a separate manual workflow
  stored on trusted `main`; it requires an exact current-main SHA, a live API
  readback both before preparation and after the protected environment gate,
  and a clean tracked `site/` artifact whose canonical content matches Git blob IDs,
  with no special index flags, links, gitlinks, hard links, modified files, or
  untracked files.

## Reportable Findings And Severity Context

A finding is reportable when a realistic input or reachable workflow can break a
security invariant. Examples include:

- reading, recalling, overwriting, deleting, archiving, or publishing data
  outside the bound vault or allowed sensitivity ceiling;
- path traversal, symlink/junction escape, stale-index substitution, canonical-ID
  confusion, or content-hash bypass;
- secret or private-memory disclosure through CLI, MCP, HTTP, logs, reports,
  generated configuration, documentation, CI, or release artifacts;
- an unauthorized or non-reviewable canonical writer, durable promotion, hook,
  scheduler, or maintenance mutation;
- remote API exposure without the required authentication and transport controls;
- unbounded parsing, scanning, process spawning, child-process retention, or
  resource-policy bypass that creates a practical denial of service;
- bypass of branch, review, artifact-identity, tag, environment, OIDC publisher,
  or exact-release authorization; and
- exploitable workflow, package, container, or dependency supply-chain behavior.

Severity depends on reachability and demonstrated impact. Cross-boundary secret
or code-execution impact, unauthenticated network exposure, and release-publisher
compromise are normally high or critical. A local-only issue that requires the
same authorized user to edit the same vault directly is lower severity unless it
crosses another boundary or produces durable, surprising impact.

## Out Of Scope And Accepted Limitations

The following are not vulnerabilities by themselves:

- data handling performed by an external AI/MCP host after the user intentionally
  authorizes content delivery, unless ai-dememory violated its configured
  sensitivity or trust boundary;
- a user deliberately storing secrets in a private vault or disabling an
  explicit safety control, unless the product then leaks the material across a
  documented boundary;
- public demo fixtures, documentation-only inaccuracies without security impact,
  social engineering, spam, or denial of service against third-party services;
- dependency advisories without a reachable vulnerable path in the supported
  package; and
- the former private checkout, abandoned branches, unsupported releases, or
  third-party plugins that cannot reproduce the issue on supported public code.

These exclusions do not suppress a boundary bypass, secret disclosure, unsafe
default, or misleading security claim in supported code.

## Known Limitations And Compensating Controls

- Local-first operation is a deployment boundary, not end-to-end data isolation.
  Users remain responsible for the OS account, filesystem permissions, backups,
  selected MCP/AI host, and any private-vault remote.
- Vault-root binding starts from the root selected by the local user. Keep that
  root and its parent on a stable, trusted filesystem: path checks can reject
  escapes below the bound root, but cannot make a root that is replaced before
  an operation begins trustworthy.
- Secret scanning is heuristic and bounded. It reduces accidental storage and
  egress but cannot prove that arbitrary prose contains no personal or sensitive
  information.
- Some controls documented for the current default branch may not exist in the
  latest stable package. Reproduce findings against the exact version named in a
  report and consult the README's stable/source boundary.
- Vector search is optional; generated indexes are disposable and can be rebuilt
  from canonical Markdown. Index corruption must fail closed rather than become
  a second source of truth.
- GitHub secret scanning with push protection and Private Vulnerability Reporting
  are enabled for the public repository. CI, independent review, protected
  `main`, protected publishing environments, and immutable release evidence are
  defense in depth, not substitutes for fixing a validated vulnerability.
