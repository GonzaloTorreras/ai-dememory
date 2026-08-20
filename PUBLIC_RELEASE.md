# Public release provenance

This repository starts from a reviewed, sanitized source snapshot rather than
the former private development repository's Git history. The public root commit
`22e59f3044b1966b66617301a02a6b09c893f9f3` and its descendants are the only
development and release provenance.

- Export policy: explicit source and documentation allowlist
- Excluded: private Git history, generated inbox captures, local reports,
  indexes, working state, credentials and non-demo memory

The files under `memories/` are reviewed demonstration fixtures. Users should
keep their real vault in a separate private repository or unversioned path.

Former private commit and tree identifiers are intentionally not release
evidence. The initial public commit remains the only root commit; future
releases follow the checks and approval gates documented in this repository.
