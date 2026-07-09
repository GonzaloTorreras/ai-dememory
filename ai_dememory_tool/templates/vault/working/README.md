# Working Memory

This directory stores generated working state for the current task loop.

- `current.json`: current task snapshot.
- `recent-session.md`: human-readable current session notes.
- `handoffs/`: session handoffs for later continuation.

These files are operational context, not durable memory. Promote only reviewed
facts into `memories/`.
