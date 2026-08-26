# Vault Configuration

ai DeMemory keeps operational policy in the private vault's
`.ai-dememory.toml`. Personal memories remain Markdown; this file is not a
memory store and must not contain credentials, transcripts, or prompt content.

**Release scope:** ai-dememory 2.1.1 is the current stable PyPI release. The
strict contract described here belongs to the unreleased 2.1.2 source
candidate until that version is tagged and published.

## The Short Version

- Use the wizard to create or update supported operational settings.
- Treat `.ai-dememory.toml` as real UTF-8 TOML, not a loose key/value file.
- Use only documented sections and keys, with exact TOML types.
- Partial configurations are valid; unknown sections and keys are not.
- Run Doctor after a manual edit:

```bash
ai-dememory --root <vault-path> doctor --json
```

Doctor is read-only. It reports a stable error code, field, and safe location
without echoing the configured value. It does not repair or rewrite the file.

## Supported Main Sections

The packaged [vault template](../vault-template/.ai-dememory.toml) is the
readable reference for ordinary settings. Product writers may add documented
receipt fields that are absent until their feature is used.

| Section | Purpose |
| --- | --- |
| `memory`, `mcp` | Canonical-memory and local MCP declarations. |
| `automation`, `resources` | Bounded intensity, model policy, and resource ceilings. |
| `review`, `false_positives`, `conflicts` | Human-review policy and safe state locations. |
| `context`, `recall`, `learning` | Retrieval budgets and opt-in local hook behavior. |
| `lifecycle`, `embeddings` | Lifecycle policy and the disabled-by-default vector boundary. |
| `schedule` | Optional schedule policy plus reviewed installation receipts. |
| `providers.<name>` | One of `codex`, `claude`, `chatgpt`, `cursor`, or `windsurf`. |

Every section and field is optional. The parser rejects unknown providers,
nested subsections, top-level scalar keys, duplicate definitions, and values
whose TOML type does not match the field. Policy ranges and enums are then
checked by the owning feature.

For example, boolean and numeric fields must not be quoted:

```toml
# Incorrect
[recall]
enabled = "true"
default_budget_tokens = "1200"

# Correct
[recall]
enabled = true
default_budget_tokens = 1200
```

Arrays used by this contract contain strings only. Non-finite numbers such as
`nan` and `inf` are rejected. Keep unrelated application settings in a
different file; ai DeMemory no longer silently preserves an unknown table as
if it were supported policy.

## Review-State File

`.ai-dememory-ignore.toml` is a separate, generated review-state projection.
It is not another general-purpose configuration file. Its only valid dynamic
tables are:

- `false_positives.fp_<16 lowercase hex characters>`; and
- `conflicts.conf_<16 lowercase hex characters>`.

The review commands own those records. A custom review-state path configured
through `false_positives.ignore_file` remains confined to the vault and uses
the same closed review-state schema. Diagnostics identify it with a fixed safe
label rather than exposing the configured path.

## Safe Writes And Failure Behavior

Before a product writer changes configuration it validates:

1. the existing document;
2. the requested section and values; and
3. the complete rendered candidate.

Only then does it perform the existing root-confined atomic write. A syntax,
schema, type, containment, size, race, or safe-file failure leaves the previous
bytes unchanged. Onboarding also validates its exact snapshot and final
candidate before it creates an apply plan or fingerprint.

Hooks and turn-context recall remain fail-open and inert: invalid configuration
cannot block the host or enable capture. Administrative commands fail with a
controlled non-zero result and no traceback. Error diagnostics do not include
raw values or configuration lines.

Some explicit local status and planning views intentionally show selected
provider or scheduler paths so the vault owner can review them. That privileged
status output is different from an error diagnostic; do not publish it as a
support log without reviewing it first.

## Migrating A Pre-2.1.2 Vault

The shipped 2.1.1 template already uses the supported types. Manual or legacy
customizations may need attention:

1. Back up `.ai-dememory.toml` outside the public source repository.
2. Remove duplicate tables and top-level scalar markers.
3. Move unrelated custom tables to a separate file.
4. Convert quoted booleans/numbers to TOML booleans/numbers.
5. Compare provider names and field spelling with the packaged template.
6. Run `ai-dememory --root <vault-path> doctor --json`.
7. Run the wizard only after Doctor reports the configuration check as valid.

There is deliberately no automatic "accept unknown config" mode: guessing how
to rewrite an unsupported policy could silently change safety or resource
limits. Restore the backup and fix the reported field if a manual migration is
uncertain.
