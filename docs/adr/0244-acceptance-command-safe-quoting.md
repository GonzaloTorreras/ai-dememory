# ADR 0244: Acceptance Command Safe Quoting

Status: Accepted.

## Context

ADR 0242 added reviewer and PR URL metadata to generated manual acceptance
record commands. Those commands are guidance, not automatically executed, but
reviewers commonly copy them into a shell after completing a manual check.

The initial generated commands used double-quoted values. Double quotes are easy
to read, but many shells still expand command substitutions or variables inside
them. Reviewer names and artifact URLs are caller-supplied handoff metadata, so
the generated examples should avoid expansion-prone quoting.

## Decision

Generate manual acceptance command argument values as single-quoted shell
literals.

The command generator now:

- normalizes multiline argument values to one line;
- wraps generated reviewer, summary, and artifact values in single quotes; and
- escapes embedded single quotes with the standard adjacent-quote pattern.

This affects generated `acceptance record` command strings from:

- `ai-dememory acceptance plan`
- `ai-dememory acceptance template`
- MCP `memory.acceptance_plan`
- MCP `memory.acceptance_template`
- release evidence embedded manual acceptance plans

The generated commands remain review guidance. They do not execute commands,
record evidence, authenticate reviewers, or prove that a manual check passed.

## Benefits

- Reduces accidental shell expansion when reviewer or artifact metadata contains
  `$`, backticks, or command-substitution-like text.
- Keeps the human copy/paste workflow while making default examples safer.
- Carries the same safer command format through CLI, MCP, and release evidence
  because they share the same command generator.

## Limitations

- Generated command strings are still examples; reviewers must inspect them
  before execution.
- Shell behavior varies across environments, especially between POSIX shells,
  PowerShell, and `cmd.exe`.
- The structured data remains safer than copy/pasting command strings when a
  client can execute commands from arrays or forms.

## Future Risks

- If generated commands need first-class Windows `cmd.exe` compatibility, add an
  explicit command rendering mode instead of one universal string.
- If acceptance recording becomes API-driven, clients should prefer structured
  fields over shell command strings.
- If multiple artifact values are prefilled, each value must use the same
  quoting helper.

## Dependencies

- ADR 0242 defines reviewer and PR URL metadata for manual acceptance plan and
  template commands.
- ADR 0243 propagates the same metadata through release evidence.
- `scripts/manual_acceptance.py` owns generated acceptance command strings.
- `tests/test_memory_tools.py` covers generated quoting behavior.
