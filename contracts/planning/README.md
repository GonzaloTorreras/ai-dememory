# Planning Contracts

These files are the public machine-readable V3 task order and state. They are
planning authority, not evidence that a feature or gate is complete.

- `v3-execution-sequence.json` contains the current legal frontier.
- `v3-execution-sequence.schema.json` validates its shape.
- `external-readback-receipt.schema.json` defines the typed receipt required
  when a completed task has `external_readback_required: true`.
- `v3-execution-ledger.json` starts empty and accepts only current-public,
  reproducible evidence in future reviewed changes.

Historical/private ledgers, pins, receipts, local paths, memories, and release
evidence are intentionally excluded. A status may move to `complete` only with
the evidence required by the task; external readback cannot be replaced by a
local override.

Evidence paths are canonical forward-slash repo-relative paths to regular
files. Empty, absolute, traversing, non-normalized, missing, directory, or
symlink-escaping paths are invalid; `.git` metadata, NTFS alternate streams,
and non-portable Windows names are not evidence. A task with external readback
defines exactly one versioned `external_readback_contract` descriptor; a task
without the readback flag cannot define one. A task-bound external receipt lives at
`contracts/planning/evidence/<task-id>/<name>.json`, identifies the source,
consumer, server profile, allowlist, schema, environment, fixture, lifecycle,
redaction manifest, and sanitized readback by stable hashes, and records a
passing secret scan. Its contract id, kind, session count, and fixture identity
must satisfy the owning task descriptor. Optional task-specific `details` are
bounded name/hash identities, never raw transcripts or arbitrary payloads.
