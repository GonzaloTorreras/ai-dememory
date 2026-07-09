# ADR 0228: Provider Configure Dry-Run

Status: Accepted

## Context

First-run setup needs a clear step where a user chooses which Codex, Claude,
ChatGPT, Cursor, or Windsurf folder should be used for local imports. The setup
plan already returned reviewable provider commands, and provider imports already
had a dry-run. The missing step was previewing the chosen provider configuration
itself before writing `.ai-dememory.toml`.

Without a configure preview, plugin and CLI setup flows had to jump directly
from "review this path" to mutating config, even though package and plugin
installation are supposed to stay passive.

## Decision

Add `ai-dememory providers configure <provider> --path <path> --dry-run
--json`.

The dry-run:

- validates the provider name;
- normalizes the selected path;
- reports whether the path exists;
- reports the `.ai-dememory.toml` section and values that would be written;
- returns `mutates_config=false`, `writes_files=false`,
  `reads_provider_files=false`, and `writes_import_candidates=false`; and
- does not write `.ai-dememory.toml`.

Provider setup plans now include `configure_dry_run_command` before the mutating
`configure_command`, so plugin and first-run setup flows can ask for explicit
approval after the preview.

## Benefits

- Users can choose provider folders during setup without immediately mutating
  vault config.
- Plugin skills can present a safer approval flow for provider imports.
- The configure step now matches the review-first pattern used by import
  dry-runs, scheduler dry-runs, and hook install dry-runs.
- Release checks can assert that provider setup remains passive until a user
  approves the mutating command.

## Limitations

- The dry-run only checks whether the selected path exists. It does not inspect
  chat files or estimate import volume.
- It does not validate provider-specific database schemas or export formats.
- It does not configure multiple providers in one command.

## Future Risks

- Provider folder layouts may change, so path existence is not enough to prove
  future import success.
- If provider-specific validation is added, it must remain separate from this
  config preview or clearly report when it reads provider files.
- If a guided interactive setup command is added later, it should reuse this
  dry-run output instead of inventing a separate config schema.

## Dependencies

- ADR 0078 defines read-only provider setup planning.
- ADR 0136 defines provider readiness in maintenance status.
- ADR 0137 defines provider import dry-run previews.
- ADR 0138 defines provider import idempotency.
- `scripts/provider_import.py` owns provider configuration and imports.
- `plugins/ai-dememory/skills/memory-setup/SKILL.md` owns plugin setup
  guidance.
