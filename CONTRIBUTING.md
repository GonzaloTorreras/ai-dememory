# Contributing

ai DeMemory favors small vertical changes over new frameworks.

## Setup

```bash
python -m venv .venv
python -m pip install -e .
python -m unittest discover -s tests_v3 -t .
```

For a manual smoke, use a temporary vault outside the checkout:

```bash
ai-dememory setup <temporary-vault> --yes
ai-dememory remember "test memory"
ai-dememory recall test
ai-dememory status --json
```

## Change rules

- Keep the public CLI below ten top-level commands.
- Put integrations in optional modules; disabled means no imports or runtime
  effects.
- Modules propose; only an explicit human CLI action writes canonical memory.
- Add a dependency only when the standard library cannot satisfy a measured
  need.
- Add tests for user-visible behavior and failure recovery, not implementation
  ceremony.
- Do not add V2 compatibility, task IDs, ADRs or guards by default.

Before a PR, run compile, all `tests_v3`, an isolated install smoke and one
fresh read-only review. Document skipped checks and residual risk honestly.
