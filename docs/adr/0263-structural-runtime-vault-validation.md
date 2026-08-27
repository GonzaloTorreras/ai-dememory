# ADR 0263: Structural Runtime Vault Validation

Status: Accepted

Date: 2026-08-26

Task: `BRG-003` / `B04b`

## Context

The strict resolver already used the deterministic order `--root`, then
`AI_DEMEMORY_ROOT`, then one saved local default. The saved default required an
existing directory and a bounded, stable `.ai-dememory.toml`, but argument and
environment bindings only became absolute canonical paths. They could therefore
select a missing directory, a non-directory, a linked final root, or an
uninitialized directory before a command opened a socket, acquired a lock, or
started other vault work.

Configuration syntax and schema are governed separately by `BRG-017`. Repeating
the TOML parser in the binding layer would create a second policy authority.

## Decision

On every surface already routed through `resolve_runtime_vault`, all three
runtime sources use one structural validator after source selection. An invalid
higher-precedence source fails closed and never falls through to a lower-
precedence source.

The validator:

1. expands `~` and requires an absolute path before filesystem access;
2. requires the selected final entry to exist, be a real directory, and expose
   a stable filesystem identity;
3. rejects a symlink, junction, or reparse point as the final vault root;
4. canonicalizes the root and snapshots every directory in the canonical chain;
5. reads only `.ai-dememory.toml` through the existing bounded,
   descriptor-checked regular-file reader;
6. rejects a missing, linked, non-regular, hard-linked, oversized, unstable, or
   concurrently substituted configuration marker; and
7. repeats the directory snapshot and returns only the canonical root when the
   chain remains stable.

The file reader compares identity, type, size and modification time across path
and descriptor snapshots, and compares descriptor change time before and after
the read. It does not interpret TOML. The selected command remains responsible
for the strict syntax and schema diagnostic.

Stable aliases in ancestor components are permitted after canonicalization. This
preserves platform aliases such as macOS `/var` to `/private/var` and ordinary
Windows path aliases, while a linked final vault directory remains invalid.

The saved selector remains local-only. This change does not silently alter the
existing explicit `--root` or `AI_DEMEMORY_ROOT` network-path policy; an
explicitly selected filesystem must still provide the identities and regular
file semantics required by the validator.

## Rootless And Bootstrap Boundaries

Static help, `providers detect`, `schedule doctor`, the static MCP tool list,
and the unbound hook no-op remain rootless and must not invoke this validator.
`init` and `vault-template` remain bootstrap operations because their purpose is
to create a vault rather than consume an initialized one.

This decision does not complete `BRG-003`. The later PR #54 supplied the
exhaustive `vault-bound`, `source-bound`, context-dependent, and package/
rootless inventory. Policy-specific dispatcher enforcement and removal of
unintended CWD/package discovery still must complete before the frontier can
advance to `BRG-019`.

## Consequences

- A root consumed through `resolve_runtime_vault` must already be initialized
  and contain `.ai-dememory.toml`; `ai-dememory init` is the creation path.
- A moved, removed, relinked, or structurally invalid vault fails before the
  selected command performs vault work.
- Binding adds a bounded configuration-marker read and directory metadata
  snapshots. It adds no daemon, child process, model call, database, network
  service, Node dependency, or canonical memory write.
- Filesystems without a usable stable identity fail closed. Mounted or remote
  filesystems cannot be classified portably from a path alone.
- Validation proves a stable handoff at binding time. It does not retain a root
  directory descriptor for the lifetime of MCP, API, or another long-running
  process; operation-specific safe readers, containment checks, and locks remain
  required.
- An attacker with enough local authority to modify a file and restore every
  observed identity, size, and timestamp is outside this local binding-time
  guarantee.

## Verification

The regression matrix covers every binding source, source precedence without
fallback, missing and non-directory roots, final links/reparse metadata,
canonical ancestor aliases, missing/linked/hard-linked/oversized configurations,
unstable identity, root replacement, descriptor substitution, in-place
same-size mutation, parser separation, and path-redacted errors. Integration
and installed-package checks must also prove that rootless surfaces remain
rootless and that invalid roots fail before sockets, locks, provider scans,
children, or writers.

## Limitations

The validator establishes a structurally stable root at command binding time;
it does not retain a directory handle for an entire long-running process. It
also cannot portably distinguish a local mount from every remote filesystem or
detect a hostile same-account writer that restores every observed identity and
timestamp. Operation-specific containment, safe readers, locks, and process
ownership remain required.

## Future Risks

- A new runtime entry point could bypass the shared resolver unless the planned
  exhaustive command-policy inventory classifies it.
- A filesystem may expose nominal identities whose stability is weaker than
  the local filesystems covered by CI.
- Broadening network-path support without crash, lock, and identity evidence
  could turn a deliberate explicit binding into unreliable runtime behavior.

## Dependencies

- `BRG-003` remains the active planning frontier.
- `BRG-017` remains authoritative for TOML syntax and schema validation.
- `BRG-019` must not begin until the remaining runtime command-policy inventory
  and CWD/package-discovery work closes `BRG-003`.

## Rollback

Revert the shared structural validator and its tests together. Do not retain
different structural rules for argument, environment, and saved-default
bindings. A rollback restores compatibility with uninitialized explicit roots
but also restores the ambiguity this ADR removes.
