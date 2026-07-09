# ADR 0142: Scheduler Input Validation

## Status

Accepted

## Context

The v2 scheduler path is review-first: users and MCP clients preview host
scheduler commands before installing anything. That preview is only useful when
the schedule values are explicit and valid.

Before this decision, invalid weekly day names could fall back to Sunday during
cron planning, and malformed times could surface as raw exceptions. That made a
bad setup value look like a valid reviewed schedule.

## Decision

Validate scheduler time and weekday inputs before generating schedule commands,
cron entries, or persisted schedule config.

Use normalized 24-hour `HH:MM` values for daily and weekly times. Accept only
`SUN`, `MON`, `TUE`, `WED`, `THU`, `FRI`, and `SAT` for weekly schedules.
Command builders raise validation errors for invalid values, and the CLI
reports them as normal argument errors.

`schedule_status` remains read-only. If persisted schedule config is invalid,
it reports `valid=false`, includes `validation_errors`, and returns no platform
status commands instead of querying or mutating the host scheduler.

## Consequences

- Scheduler dry-runs and cron exports no longer silently coerce invalid weekday
  names.
- MCP/plugin schedule status can surface invalid persisted config without
  touching the host scheduler.
- Persisted schedule config is normalized at write time.

## Limitations

- Validation covers local scheduler fields only; it does not verify that
  `systemctl`, `schtasks`, `launchctl`, Docker, or the selected image exists.
- It does not validate whether the chosen time is operationally convenient for
  the user's machine.
- Existing invalid config must still be edited or reconfigured by the user.

## Future Work

- Add a repair command if users need an interactive way to rewrite invalid
  schedule config.
- Add optional environment checks for Docker and host scheduler availability as
  separate diagnostics.
- Consider supporting localized weekday input only if the CLI gains locale-aware
  parsing.

## Dependencies

- ADR 0025 defines local maintenance scheduling.
- ADR 0026 defines Docker maintenance schedule planning.
- ADR 0066 defines read-only MCP scheduler status.
- ADR 0133 defines the scheduler and plugin implementation blueprint.
- ADR 0134 defines MCP cron entry planning.

## References

- `scripts/schedule_memory.py`
- `docs/scheduler.md`
- `tests/test_memory_tools.py`
