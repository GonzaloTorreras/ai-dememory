# Planning Contracts

These files are the public machine-readable V3 task order and state. They are
planning authority, not evidence that a feature or gate is complete.

- `v3-execution-sequence.json` contains the current legal frontier.
- `v3-execution-sequence.schema.json` validates its shape.
- `v3-execution-ledger.json` starts empty and accepts only current-public,
  reproducible evidence in future reviewed changes.

Historical/private ledgers, pins, receipts, local paths, memories, and release
evidence are intentionally excluded. A status may move to `complete` only with
the evidence required by the task; external readback cannot be replaced by a
local override.
