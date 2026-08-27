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
consumer, server profile, allowlist, schema, environment, fixture, and sanitized
readback by stable hashes, and records a passing secret scan. Its contract id,
kind, distinct per-session records, fixture identity, and every required detail
name must satisfy the owning task descriptor. Task-specific `details` reference
bounded, sanitized files under the same task's `artifacts/` directory; the
validator recomputes their byte sizes and raw-byte SHA-256 identities. They are
never raw transcripts or arbitrary inline payloads.

This validation establishes schema, task binding, containment, and hash
consistency. A checked-in receipt remains owner-attested evidence: it does not
cryptographically authenticate an external provider, reviewer, or causal claim.
Independent review and the owning task's external readback remain mandatory;
task-specific payload schemas and harnesses must be added before that future task
can complete when its acceptance criteria require semantic or numeric proof.
