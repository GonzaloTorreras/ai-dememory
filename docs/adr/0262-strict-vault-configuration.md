# ADR 0262: Strict Vault Configuration Contract

## Status

Accepted for `BRG-017` on 2026-08-26 before the 2.1.2 release candidate.

## Context

The original configuration helper recognized a permissive line-oriented TOML
subset. It ignored unknown and malformed input, overwrote duplicate keys in
memory, accepted arbitrary sections, and sometimes left type coercion to each
consumer. That made forward compatibility appear easy but created ambiguous
policy, inconsistent diagnostics, and writers that could preserve an invalid
document.

The same helper also reads generated false-positive and conflict receipts.
Those dynamic tables have a different schema from `.ai-dememory.toml`, so a
single filename-inferred allowlist would either reject valid review records or
make the main policy too permissive.

## Decision

- Parse UTF-8 configuration with Python 3.11 `tomllib`; add no dependency or
  service.
- Maintain two explicit version-1 structural schemas: `main` and
  `review_state`. Never infer the schema from a configurable filename.
- Accept missing, empty, and partial documents, but reject unknown sections,
  subsections, keys, providers, duplicate definitions, top-level scalars,
  wrong types, non-finite numbers, and non-string array members.
- Preserve the established flat consumer representation after validating
  dotted TOML tables such as `providers.codex` and dynamic review IDs.
- Keep value ranges, enums, and product-policy meaning in their existing
  consumers; structural parsing must not silently coerce strings into booleans
  or numbers.
- Keep `ConfigError` a `ValueError` subtype with stable `code`, `source`,
  `field`, `line`, and `column` attributes. Diagnostics never include raw
  values or source lines; configurable review-state paths use a fixed safe
  source label.
- Validate the existing document, requested update, and complete candidate
  before any configuration write. Preserve exact previous bytes on failure.
- Validate onboarding snapshots and candidates before plan creation or apply.
- Make Doctor report structural errors read-only. Normalize other CLI
  boundaries so they return controlled errors rather than tracebacks.
- Preserve inert fail-open behavior for lifecycle hooks and turn-context
  recall. Invalid configuration must never enable capture or block a host.
- Treat explicit admin/status projections that intentionally show local paths
  as a separate privileged contract; do not confuse them with error
  diagnostics.

## Consequences

- Typos and stale unsupported configuration fail visibly instead of being
  silently ignored.
- Provider and review-state dotted tables keep their existing runtime shape.
- Product writers cannot turn an invalid file into a superficially valid
  partial rewrite.
- Existing 2.1.1 vaults created from the packaged template remain compatible.
  Hand-written quoted numbers/booleans, duplicate tables, and custom sections
  require a reviewed manual migration.
- Python remains the only headless runtime; the change adds no daemon, child
  process, vector store, model call, or Node dependency.

## Rejected Alternatives

- Continue the permissive parser: leaves unknown policy and duplicate
  definitions undiagnosed.
- Add a third-party TOML dependency: unnecessary on the supported Python 3.11+
  baseline.
- Preserve unknown fields during writes: makes a closed schema unenforceable
  and can retain misspelled safety settings indefinitely.
- Infer review-state schema from `.ai-dememory-ignore.toml`: breaks custom
  vault-confined review paths.
- Automatically rewrite legacy files: cannot distinguish a typo from an
  intentional external setting safely.
- Couple default-vault selection to TOML semantics: selection owns filesystem
  safety; the selected command owns configuration validity.

## Limitations

- This contract validates structure and exact types, not every semantic range
  or enum. Consumers still own those checks.
- Error locations are best-effort safe metadata and may be absent for bounded
  file-read failures.
- Deliberate local status/admin output can expose configured paths to its local
  caller; errors remain redacted.
- `BRG-017` does not complete the separate `BRG-003` structural vault-binding
  and legacy command-policy inventory.

## Future Risks

- A new writer field can drift from the allowlist unless tests cover both the
  packaged template and complete generated receipts.
- A consumer can reintroduce raw configured values in semantic errors after
  structural parsing; redaction regressions must remain covered across CLI and
  MCP projections.
- Adding nested configuration without a versioned schema decision could break
  the flat compatibility representation.

## Rollback

Revert the strict parser and its integrations together. Do not retain strict
writers with permissive readers, or strict readers while allowing callers to
emit unhandled tracebacks. Preserve the previous configuration bytes and
restore a known-good packaged template before retrying an affected vault.

## Dependencies

- `docs/v3-hybrid-visual-multiplatform-roadmap.md` and
  `contracts/planning/v3-execution-sequence.json` define `BRG-017` / `B04b`.
- ADR 0253 defines the public repository baseline.
- ADR 0254 keeps Python authoritative and Node optional for a future visual
  plane.
- ADR 0257 defines bounded autonomy and resource profiles.
- `docs/configuration.md` is the user-facing contract and migration guide.
- `scripts/config_file.py` is the executable schema and safe writer.
