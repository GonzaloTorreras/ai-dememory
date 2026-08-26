#!/usr/bin/env python3
"""Strict, root-bound TOML helpers for ai DeMemory configuration files."""

from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import threading
import time
import tomllib
from typing import Any, Callable, Iterator

from memorylib import path_is_link_like, safe_write_text


CONFIG_NAME = ".ai-dememory.toml"
MAX_CONFIG_BYTES = 64 * 1024
CONFIG_WRITE_LOCK_NAME = ".ai-dememory-config.lock"
CONFIG_WRITE_LOCK_TIMEOUT_SECONDS = 5.0

_CONFIG_WRITE_THREAD_GUARD = threading.Lock()
_CONFIG_WRITE_THREAD_LOCKS: dict[str, tuple[Any, int]] = {}
_EXPECTED_SECTION_UNSET = object()

TYPE_BOOL = "bool"
TYPE_INT = "int"
TYPE_NUMBER = "number"
TYPE_STRING = "string"
TYPE_STRING_LIST = "string_list"


# This is deliberately a structural schema. Value ranges and policy enums remain
# owned by the consumers that already diagnose them. Keep this allowlist aligned
# with the checked-in vault template and fields emitted by the current writers.
MAIN_CONFIG_SCHEMA: dict[str, dict[str, str]] = {
    "memory": {
        "schema_version": TYPE_STRING,
        "canonical": TYPE_STRING,
    },
    "mcp": {
        "transport": TYPE_STRING,
        "include_sensitive_by_default": TYPE_BOOL,
    },
    "automation": {
        "profile_version": TYPE_INT,
        "intensity": TYPE_STRING,
        "model_policy": TYPE_STRING,
    },
    "review": {
        "reviewer": TYPE_STRING,
        "mode": TYPE_STRING,
        "require_human_for_durable": TYPE_BOOL,
        "allow_llm_conflict_recommendations": TYPE_BOOL,
        "allow_llm_false_positive_triage": TYPE_BOOL,
        "allow_llm_merge_proposals": TYPE_BOOL,
        "allow_autonomous_inbox_proposals": TYPE_BOOL,
        "allow_apply_reviewed": TYPE_BOOL,
        "require_secret_scan_before_promotion": TYPE_BOOL,
        "updated_at": TYPE_STRING,
    },
    "false_positives": {
        "enabled": TYPE_BOOL,
        "allow_ignore_file": TYPE_BOOL,
        "ignore_file": TYPE_STRING,
        "review_after_days": TYPE_INT,
        "triage_policy": TYPE_STRING,
    },
    "conflicts": {
        "enabled": TYPE_BOOL,
        "scan_on_validate": TYPE_BOOL,
        "scan_on_consolidate": TYPE_BOOL,
        "report_path": TYPE_STRING,
        "proposal_path": TYPE_STRING,
        "resolution_policy": TYPE_STRING,
        "llm_preselect_min_confidence": TYPE_NUMBER,
        "human_required_severities": TYPE_STRING_LIST,
        "llm_auto_deny_categories": TYPE_STRING_LIST,
    },
    "context": {
        "default_budget_tokens": TYPE_INT,
        "include_working_memory": TYPE_BOOL,
        "explain_results": TYPE_BOOL,
    },
    "recall": {
        "enabled": TYPE_BOOL,
        "per_turn": TYPE_BOOL,
        "default_budget_tokens": TYPE_INT,
        "baseline_budget_tokens": TYPE_INT,
        "max_keywords": TYPE_INT,
        "project_from_cwd": TYPE_BOOL,
        "min_relevance_score": TYPE_NUMBER,
        "hook_public_only": TYPE_BOOL,
        "clients": TYPE_STRING_LIST,
    },
    "learning": {
        "hook_metadata": TYPE_BOOL,
        "session_proposals": TYPE_BOOL,
        "clients": TYPE_STRING_LIST,
    },
    "resources": {
        "provider_file_limit": TYPE_INT,
        "provider_max_file_bytes": TYPE_INT,
        "provider_scan_entries": TYPE_INT,
        "maintenance_report_retention": TYPE_INT,
        "maintenance_timeout_seconds": TYPE_INT,
        "mcp_idle_timeout_seconds": TYPE_INT,
        "hook_capture_max_pending": TYPE_INT,
    },
    "lifecycle": {
        "enabled": TYPE_BOOL,
        "record_mark_seen": TYPE_BOOL,
        "record_outcomes": TYPE_BOOL,
        "ranking_uses_strength": TYPE_BOOL,
    },
    "embeddings": {
        "enabled": TYPE_BOOL,
        "provider": TYPE_STRING,
        "require_explicit_remote_opt_in": TYPE_BOOL,
    },
    "schedule": {
        "enabled": TYPE_BOOL,
        "daily_enabled": TYPE_BOOL,
        "weekly_enabled": TYPE_BOOL,
        "daily_time": TYPE_STRING,
        "weekly_day": TYPE_STRING,
        "weekly_time": TYPE_STRING,
        "mode": TYPE_STRING,
        "image": TYPE_STRING,
        "platform": TYPE_STRING,
        "intensity": TYPE_STRING,
        "root": TYPE_STRING,
        "command": TYPE_STRING,
        "plan_sha256": TYPE_STRING,
        "plan_projection": TYPE_STRING,
        "definition_digests": TYPE_STRING_LIST,
        "task_namespace": TYPE_STRING,
        "installed_profiles": TYPE_STRING_LIST,
        "installed_at": TYPE_STRING,
        "verified_at": TYPE_STRING,
    },
}

PROVIDER_CONFIG_SCHEMA: dict[str, str] = {
    "enabled": TYPE_BOOL,
    "path": TYPE_STRING,
    "capture_raw": TYPE_BOOL,
}
KNOWN_PROVIDERS = frozenset({"codex", "claude", "chatgpt", "cursor", "windsurf"})

RECOMMENDATION_LINK_SCHEMA: dict[str, str] = {
    "recommendation_id": TYPE_STRING,
    "recommendation_path": TYPE_STRING,
    "recommendation_action": TYPE_STRING,
    "recommendation_policy_violation": TYPE_BOOL,
}
REVIEW_STATE_SCHEMA: dict[str, dict[str, str]] = {
    "false_positives": {
        "ignored": TYPE_BOOL,
        "reason": TYPE_STRING,
        "reviewer": TYPE_STRING,
        "reviewed_at": TYPE_STRING,
        "review_after": TYPE_STRING,
        **RECOMMENDATION_LINK_SCHEMA,
    },
    "conflicts": {
        "status": TYPE_STRING,
        "decision": TYPE_STRING,
        "proposal_path": TYPE_STRING,
        "reviewer": TYPE_STRING,
        "reviewed_at": TYPE_STRING,
        **RECOMMENDATION_LINK_SCHEMA,
    },
}

CONFIG_KINDS = frozenset({"main", "review_state"})
REVIEW_STATE_ID_PATTERNS = {
    "false_positives": re.compile(r"^fp_[0-9a-f]{16}$"),
    "conflicts": re.compile(r"^conf_[0-9a-f]{16}$"),
}


class ConfigError(ValueError):
    """A stable, value-redacting structural configuration diagnostic."""

    def __init__(
        self,
        code: str,
        *,
        source: str,
        field: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.code = code
        self.source = str(source)
        self.field = field
        self.line = line
        self.column = column
        location = ""
        if line is not None:
            location = f":{line}"
            if column is not None:
                location += f":{column}"
        field_label = f" ({field})" if field else ""
        super().__init__(f"{self.source}{location}: config error [{code}]{field_label}")


class _SourceLocations:
    """Best-effort safe locations without retaining or reporting raw values."""

    def __init__(self, text: str) -> None:
        self.sections: dict[tuple[str, ...], tuple[int, int]] = {}
        self.fields: dict[tuple[str, ...], tuple[int, int]] = {}
        current: tuple[str, ...] = ()
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            stripped = raw_line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            header = _table_header_parts(raw_line)
            if header is not None:
                current = header
                self.sections.setdefault(header, (line_number, len(raw_line) - len(stripped) + 1))
                continue
            assignment = _assignment_key_parts(raw_line)
            if assignment is not None:
                key_parts, column = assignment
                self.fields.setdefault((*current, *key_parts), (line_number, column))

    def get(self, path: tuple[str, ...]) -> tuple[int | None, int | None]:
        if path in self.fields:
            return self.fields[path]
        probe = path
        while probe:
            if probe in self.sections:
                return self.sections[probe]
            probe = probe[:-1]
        return (1, 1)


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def root_bound_config_path(path: Path, root: Path) -> Path:
    """Anchor one config path below a vault while preserving a root alias."""

    logical_root = Path(os.path.abspath(Path(root).expanduser()))
    resolved_root = logical_root.resolve(strict=False)
    candidate = Path(os.path.abspath(Path(path).expanduser()))
    try:
        relative = candidate.relative_to(logical_root)
    except ValueError:
        try:
            relative = candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("config path must stay inside the memory root") from exc

    target = resolved_root / relative
    current = resolved_root
    for part in relative.parts:
        current = current / part
        if path_is_link_like(current):
            raise ValueError("config path must not contain symlinks or junctions")
    return target


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _has_stable_file_identity(value: os.stat_result) -> bool:
    """Require an inode value that can distinguish a raced file handle."""

    return value.st_ino != 0


def _has_single_hard_link(value: os.stat_result) -> bool:
    """Reject ambiguous or shared file metadata at the vault boundary."""

    return value.st_nlink == 1


def _validated_config_stat(path: Path, root: Path, expected: os.stat_result | None = None) -> os.stat_result | None:
    target = root_bound_config_path(path, root)
    try:
        observed = target.lstat()
    except FileNotFoundError:
        if expected is not None:
            raise ValueError("config path changed while reading") from None
        return None
    except OSError as exc:
        raise ValueError("config path could not be inspected safely") from exc
    if not stat.S_ISREG(observed.st_mode):
        raise ValueError("config path must be a regular file")
    if not _has_stable_file_identity(observed):
        raise ValueError("config path has no stable file identity")
    if observed.st_nlink > 1:
        raise ValueError("config path must not have multiple hard links")
    if not _has_single_hard_link(observed):
        raise ValueError("config path has no stable hard-link count")
    if expected is not None and not _same_file_identity(observed, expected):
        raise ValueError("config path changed while reading")
    return observed


def read_config_bytes(path: Path, *, root: Path) -> bytes | None:
    """Read a regular in-vault config without following links or stale paths."""

    target = root_bound_config_path(path, root)
    before = _validated_config_stat(target, root)
    if before is None:
        return None

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_CLOEXEC", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    flags |= int(getattr(os, "O_NONBLOCK", 0))
    fd = -1
    try:
        try:
            fd = os.open(target, flags)
        except FileNotFoundError:
            raise ValueError("config path changed while reading") from None
        except OSError as exc:
            raise ValueError("config path could not be opened safely") from exc
        try:
            opened = os.fstat(fd)
        except OSError as exc:
            raise ValueError("config path could not be read safely") from exc
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("config path must be a regular file")
        if not _has_stable_file_identity(opened):
            raise ValueError("config path has no stable file identity")
        if not _has_single_hard_link(opened):
            raise ValueError("config path has no stable hard-link count")
        if not _same_file_identity(before, opened):
            raise ValueError("config path changed while reading")
        _validated_config_stat(target, root, expected=opened)
        chunks: list[bytes] = []
        total_bytes = 0
        while True:
            try:
                chunk = os.read(fd, min(64 * 1024, MAX_CONFIG_BYTES + 1 - total_bytes))
            except OSError as exc:
                raise ValueError("config path could not be read safely") from exc
            if not chunk:
                break
            chunks.append(chunk)
            total_bytes += len(chunk)
            if total_bytes > MAX_CONFIG_BYTES:
                raise ValueError(f"config file exceeds {MAX_CONFIG_BYTES} byte limit")
        _validated_config_stat(target, root, expected=opened)
        return b"".join(chunks)
    finally:
        if fd >= 0:
            os.close(fd)


def read_config_path(path: Path, *, root: Path) -> str | None:
    content = read_config_bytes(path, root=root)
    if content is None:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("config file must be valid UTF-8") from exc


def _try_lock_config_fd(fd: int) -> bool:
    """Try one non-blocking, process-scoped byte lock."""

    os.lseek(fd, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(
                exc, "winerror", None
            ) == 33:
                return False
            raise
        return True

    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _unlock_config_fd(fd: int) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


def _borrow_config_thread_lock(key: str) -> Any:
    with _CONFIG_WRITE_THREAD_GUARD:
        existing = _CONFIG_WRITE_THREAD_LOCKS.get(key)
        if existing is None:
            # RLock ownership lets cleanup safely attempt release even when a
            # KeyboardInterrupt lands at the boundary of acquire(): releasing
            # a lock owned by another thread raises instead of unlocking it.
            lock = threading.RLock()
            _CONFIG_WRITE_THREAD_LOCKS[key] = (lock, 1)
            return lock
        lock, users = existing
        _CONFIG_WRITE_THREAD_LOCKS[key] = (lock, users + 1)
        return lock


def _return_config_thread_lock(key: str, lock: Any) -> None:
    with _CONFIG_WRITE_THREAD_GUARD:
        current = _CONFIG_WRITE_THREAD_LOCKS.get(key)
        if current is None or current[0] is not lock:
            return
        _, users = current
        if users <= 1:
            _CONFIG_WRITE_THREAD_LOCKS.pop(key, None)
        else:
            _CONFIG_WRITE_THREAD_LOCKS[key] = (lock, users - 1)


def _release_config_thread_lock(lock: Any) -> None:
    """Small seam that keeps release cancellation tests deterministic."""

    lock.release()


def _config_cancel_signals() -> tuple[int, ...]:
    signals = [signal.SIGINT]
    sigbreak = getattr(signal, "SIGBREAK", None)
    if sigbreak is not None:
        signals.append(sigbreak)
    return tuple(signals)


def _replay_config_signal(
    signum: int,
    frame: object,
    previous: Any,
) -> None:
    if previous == signal.SIG_IGN:
        return
    if previous == signal.SIG_DFL:
        if signum in _config_cancel_signals():
            signal.default_int_handler(signum, frame)
            return
        signal.raise_signal(signum)
        return
    if callable(previous):
        previous(signum, frame)


@contextmanager
def _defer_config_cancel_signals() -> Iterator[None]:
    """Defer cancellation until one config critical section is safe.

    Nested callers remain composable: after every handler is restored, a
    deferred signal is replayed to the handler that was active on entry. This
    lets an outer transaction keep deferring it while a standalone lock owner
    still observes the normal KeyboardInterrupt/default behavior.
    """

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    pending: list[tuple[int, object]] = []
    previous_handlers: dict[int, Any] = {}
    installed: list[int] = []

    def defer(signum: int, frame: object) -> None:
        pending.append((signum, frame))

    try:
        for signum in _config_cancel_signals():
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, defer)
            installed.append(signum)
    except BaseException:
        for signum in reversed(installed):
            signal.signal(signum, previous_handlers[signum])
        raise

    try:
        yield
    finally:
        restore_error: BaseException | None = None
        for signum in reversed(installed):
            try:
                signal.signal(signum, previous_handlers[signum])
            except BaseException as exc:  # pragma: no cover - host signal API failure
                if restore_error is None:
                    restore_error = exc
        if restore_error is not None:
            raise restore_error
        for signum, frame in pending:
            _replay_config_signal(signum, frame, previous_handlers[signum])


def _cleanup_config_lock(
    *,
    fd: int,
    locked: bool,
    lock_key: str,
    thread_lock: Any | None,
) -> None:
    """Release every lock resource even when one cleanup step is cancelled."""

    cleanup_error: BaseException | None = None

    def attempt(action: Callable[[], None], ignored: tuple[type[BaseException], ...]) -> None:
        nonlocal cleanup_error
        try:
            action()
        except ignored:
            return
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc

    with _defer_config_cancel_signals():
        if fd >= 0 and locked:
            attempt(lambda: _unlock_config_fd(fd), (OSError,))
        if fd >= 0:
            attempt(lambda: os.close(fd), (OSError,))
        if thread_lock is not None:
            attempt(lambda: _release_config_thread_lock(thread_lock), (RuntimeError,))
            attempt(lambda: _return_config_thread_lock(lock_key, thread_lock), ())

    if cleanup_error is not None:
        raise cleanup_error


@contextmanager
def _config_write_interrupt_boundary(
    commit_confirmed: Callable[[], bool],
) -> Iterator[None]:
    """Complete a config transaction before reporting process cancellation."""

    try:
        with _defer_config_cancel_signals():
            yield
    except KeyboardInterrupt:
        if commit_confirmed():
            return
        raise


def _config_lock_exit_checkpoint() -> None:
    """Internal seam for the yield-to-cleanup cancellation boundary."""


@contextmanager
def vault_operation_lock(
    root: Path,
    *,
    lock_name: str,
    source: str = CONFIG_NAME,
    timeout_seconds: float | None = None,
) -> Iterator[Callable[[], None]]:
    """Serialize one bounded per-vault operation with a kernel file lock.

    The persistent one-byte sentinel is intentional: unlinking a locked file
    can split the lock namespace. Kernel locks are released with the descriptor
    or process, so a crashed writer cannot leave a blocking orphan.
    """

    if re.fullmatch(r"\.ai-dememory-[a-z0-9-]+\.lock", lock_name) is None:
        raise ValueError("vault operation lock name is invalid")
    timeout = CONFIG_WRITE_LOCK_TIMEOUT_SECONDS if timeout_seconds is None else float(timeout_seconds)
    if not math.isfinite(timeout) or timeout < 0 or timeout > threading.TIMEOUT_MAX:
        raise ValueError("vault operation lock timeout is invalid")
    lock_path = root_bound_config_path(Path(root) / lock_name, root)
    lock_key = os.path.normcase(str(lock_path.resolve(strict=False)))
    thread_lock: Any | None = None
    deadline = time.monotonic() + timeout
    fd = -1
    locked = False

    def validate_lock_identity() -> None:
        try:
            _validated_config_stat(lock_path, root, expected=os.fstat(fd))
        except (OSError, ValueError):
            raise ConfigError("config_lock_error", source=source) from None

    # One composable fence spans acquisition, the guarded operation, and every
    # cleanup step. Without this outer lifetime fence there is a bytecode-sized
    # cancellation gap between resuming after yield and entering cleanup.
    with _defer_config_cancel_signals():
        try:
            try:
                thread_lock = _borrow_config_thread_lock(lock_key)
                remaining = max(0.0, deadline - time.monotonic())
                if not thread_lock.acquire(timeout=remaining):
                    raise ConfigError("config_busy", source=source)
                flags = os.O_RDWR | os.O_CREAT
                flags |= int(getattr(os, "O_CLOEXEC", 0))
                flags |= int(getattr(os, "O_NOFOLLOW", 0))
                flags |= int(getattr(os, "O_BINARY", 0))
                fd = os.open(lock_path, flags, 0o600)
                os.set_inheritable(fd, False)
                opened = os.fstat(fd)
                if not stat.S_ISREG(opened.st_mode):
                    raise OSError("config lock path must be a regular file")
                if not _has_stable_file_identity(opened) or not _has_single_hard_link(opened):
                    raise OSError("config lock path has no stable single-file identity")
                _validated_config_stat(lock_path, root, expected=opened)
                if opened.st_size == 0:
                    os.write(fd, b"\0")
                    os.fsync(fd)
                elif opened.st_size != 1:
                    raise OSError("config lock sentinel has an invalid size")

                while not _try_lock_config_fd(fd):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ConfigError("config_busy", source=source)
                    time.sleep(min(0.025, remaining))
                locked = True
                validate_lock_identity()
            except ConfigError:
                raise
            except (OSError, ValueError):
                raise ConfigError("config_lock_error", source=source) from None

            # Do not normalize exceptions raised by the guarded transaction:
            # its caller owns those diagnostics. Only failures of this lock
            # protocol become config_lock_error.
            yield validate_lock_identity
        finally:
            _config_lock_exit_checkpoint()
            _cleanup_config_lock(
                fd=fd,
                locked=locked,
                lock_key=lock_key,
                thread_lock=thread_lock,
            )


def config_write_lock(
    root: Path,
    *,
    source: str = CONFIG_NAME,
    timeout_seconds: float | None = None,
) -> Any:
    """Return the shared config read/modify/write coordination context."""

    return vault_operation_lock(
        root,
        lock_name=CONFIG_WRITE_LOCK_NAME,
        source=source,
        timeout_seconds=timeout_seconds,
    )


def _atomic_replace_config_text(
    path: Path,
    text: str,
    *,
    root: Path,
    source: str,
    expected_bytes: bytes | None,
    validate_lock_identity: Callable[[], None],
) -> Path:
    """Publish a complete config inode, including on first creation."""

    target = root_bound_config_path(path, root)
    candidate_bytes = text.encode("utf-8")
    temp_path = target.with_name(
        f".{target.name}.ai-dememory-config-{secrets.token_hex(8)}.tmp"
    )
    try:
        # The temporary inode may be incomplete while it is written, but the
        # authoritative path remains absent or points to the previous complete
        # inode until the final atomic replacement.
        safe_write_text(
            temp_path,
            text,
            root=root,
            overwrite=False,
        )
        validate_lock_identity()
        if read_config_bytes(target, root=root) != expected_bytes:
            raise ConfigError("config_changed", source=source)
        target = root_bound_config_path(target, root)
        try:
            os.replace(temp_path, target)
        except (OSError, KeyboardInterrupt):
            if _config_candidate_is_current(
                target,
                root=root,
                source=source,
                candidate_bytes=candidate_bytes,
                expected_bytes=expected_bytes,
                validate_lock_identity=validate_lock_identity,
            ):
                return target
            raise
        return target
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _config_candidate_is_current(
    path: Path,
    *,
    root: Path,
    source: str,
    candidate_bytes: bytes,
    expected_bytes: bytes | None,
    validate_lock_identity: Callable[[], None],
) -> bool:
    """Classify an interrupted replacement without exposing config values."""

    validate_lock_identity()
    try:
        observed_bytes = read_config_bytes(path, root=root)
    except (OSError, ValueError):
        raise ConfigError("config_write_error", source=source) from None
    if observed_bytes == candidate_bytes:
        return True
    if observed_bytes == expected_bytes:
        return False
    raise ConfigError("config_changed", source=source)


def parse_config_text(
    text: str,
    source: str = CONFIG_NAME,
    config_kind: str = "main",
) -> dict[str, dict[str, Any]]:
    """Parse and structurally validate one supported TOML configuration kind."""

    if config_kind not in CONFIG_KINDS:
        raise ConfigError("unknown_config_kind", source=source, field="config_kind")
    locations = _SourceLocations(text)
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        line, column = _toml_error_location(exc)
        raise ConfigError(
            _toml_error_code(exc),
            source=source,
            line=line,
            column=column,
        ) from None

    if config_kind == "main":
        return _validate_main_config(parsed, source=source, locations=locations)
    return _validate_review_state(parsed, source=source, locations=locations)


def load_config_path(
    path: Path,
    *,
    root: Path,
    config_kind: str = "main",
    diagnostic_source: str | None = None,
) -> dict[str, dict[str, Any]]:
    text = read_config_path(path, root=root)
    return (
        parse_config_text(
            text,
            source=(diagnostic_source if diagnostic_source is not None else _config_source(path, root)),
            config_kind=config_kind,
        )
        if text is not None
        else {}
    )


def _config_source(path: Path, root: Path) -> str:
    try:
        return root_bound_config_path(path, root).relative_to(Path(root).resolve(strict=False)).as_posix()
    except ValueError:
        return Path(path).name or CONFIG_NAME


def _toml_error_code(exc: tomllib.TOMLDecodeError) -> str:
    diagnostic = str(exc).lower()
    duplicate_markers = (
        "cannot overwrite a value",
        "cannot declare",
        "already exists",
        "duplicate",
    )
    return "duplicate_definition" if any(marker in diagnostic for marker in duplicate_markers) else "toml_syntax"


def _toml_error_location(exc: tomllib.TOMLDecodeError) -> tuple[int | None, int | None]:
    line = getattr(exc, "lineno", None)
    column = getattr(exc, "colno", None)
    if isinstance(line, int) and isinstance(column, int):
        return line, column
    match = re.search(r"\(at line (\d+), column (\d+)\)", str(exc))
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def _validate_main_config(
    parsed: dict[str, Any],
    *,
    source: str,
    locations: _SourceLocations,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for section, values in parsed.items():
        section_path = (section,)
        if not isinstance(values, dict):
            _raise_config("top_level_key", source, locations, section_path)
        if section == "providers":
            if not values:
                output[section] = {}
                continue
            for provider, provider_values in values.items():
                provider_path = (section, provider)
                if provider not in KNOWN_PROVIDERS:
                    _raise_config("unknown_provider", source, locations, provider_path)
                if not isinstance(provider_values, dict):
                    _raise_config("invalid_structure", source, locations, provider_path)
                output[f"providers.{provider}"] = _validate_section_values(
                    provider_values,
                    PROVIDER_CONFIG_SCHEMA,
                    source=source,
                    locations=locations,
                    path=provider_path,
                )
            continue
        schema = MAIN_CONFIG_SCHEMA.get(section)
        if schema is None:
            _raise_config("unknown_section", source, locations, section_path)
        output[section] = _validate_section_values(
            values,
            schema,
            source=source,
            locations=locations,
            path=section_path,
        )
    return output


def _validate_review_state(
    parsed: dict[str, Any],
    *,
    source: str,
    locations: _SourceLocations,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for namespace, records in parsed.items():
        namespace_path = (namespace,)
        schema = REVIEW_STATE_SCHEMA.get(namespace)
        if schema is None:
            code = "top_level_key" if not isinstance(records, dict) else "unknown_section"
            _raise_config(code, source, locations, namespace_path)
        if not isinstance(records, dict):
            _raise_config("invalid_structure", source, locations, namespace_path)
        for record_id, values in records.items():
            record_path = (namespace, record_id)
            if not REVIEW_STATE_ID_PATTERNS[namespace].fullmatch(record_id):
                _raise_config("unsafe_identifier", source, locations, record_path)
            if not isinstance(values, dict):
                _raise_config("invalid_structure", source, locations, record_path)
            output[f"{namespace}.{record_id}"] = _validate_section_values(
                values,
                schema,
                source=source,
                locations=locations,
                path=record_path,
            )
    return output


def _validate_section_values(
    values: dict[str, Any],
    schema: dict[str, str],
    *,
    source: str,
    locations: _SourceLocations,
    path: tuple[str, ...],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in values.items():
        field_path = (*path, key)
        expected = schema.get(key)
        if expected is None:
            code = "unknown_subsection" if isinstance(value, dict) else "unknown_key"
            _raise_config(code, source, locations, field_path)
        if isinstance(value, float) and not math.isfinite(value):
            _raise_config("non_finite_number", source, locations, field_path)
        if not _matches_type(value, expected):
            _raise_config("invalid_type", source, locations, field_path)
        output[key] = value
    return output


def _matches_type(value: Any, expected: str) -> bool:
    if expected == TYPE_BOOL:
        return isinstance(value, bool)
    if expected == TYPE_INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == TYPE_NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == TYPE_STRING:
        return isinstance(value, str)
    if expected == TYPE_STRING_LIST:
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return False


def _raise_config(
    code: str,
    source: str,
    locations: _SourceLocations,
    path: tuple[str, ...],
) -> None:
    line, column = locations.get(path)
    raise ConfigError(
        code,
        source=source,
        field=_diagnostic_field(code, path),
        line=line,
        column=column,
    )


def _diagnostic_field(code: str, path: tuple[str, ...]) -> str | None:
    """Return only schema-owned field components for public diagnostics."""

    if not path:
        return None
    if code in {"top_level_key", "unknown_section"}:
        return "<unknown>"
    if code == "unknown_provider":
        return "providers.<unknown>"
    if code in {"unknown_subsection", "unknown_key"}:
        parent = _known_diagnostic_parent(path[:-1])
        return ".".join((*parent, "<unknown>")) if parent else "<unknown>"
    if code == "unsafe_identifier":
        namespace = path[0] if path[0] in REVIEW_STATE_SCHEMA else "<unknown>"
        return f"{namespace}.<unsafe-id>"
    return ".".join(path)


def _known_diagnostic_parent(path: tuple[str, ...]) -> tuple[str, ...]:
    if len(path) == 1 and path[0] in MAIN_CONFIG_SCHEMA:
        return path
    if len(path) == 2 and path[0] == "providers" and path[1] in KNOWN_PROVIDERS:
        return path
    if (
        len(path) == 2
        and path[0] in REVIEW_STATE_SCHEMA
        and REVIEW_STATE_ID_PATTERNS[path[0]].fullmatch(path[1])
    ):
        return path
    return ()


def _section_diagnostic_field(section: str, config_kind: str) -> str:
    """Describe a writer section without reflecting caller-controlled text."""

    if config_kind == "main":
        if section in MAIN_CONFIG_SCHEMA:
            return section
        parts = tuple(section.split("."))
        if len(parts) == 2 and parts[0] == "providers" and parts[1] in KNOWN_PROVIDERS:
            return section
        return "<unknown>"
    if config_kind == "review_state":
        parts = tuple(section.split("."))
        if len(parts) == 2 and parts[0] in REVIEW_STATE_SCHEMA:
            if REVIEW_STATE_ID_PATTERNS[parts[0]].fullmatch(parts[1]):
                return section
            return f"{parts[0]}.<unsafe-id>"
        return "<unknown>"
    return "config_kind"


def _table_header_parts(raw_line: str) -> tuple[str, ...] | None:
    stripped = raw_line.strip()
    if not stripped.startswith("["):
        return None
    try:
        parsed = tomllib.loads(f"{stripped}\n")
    except tomllib.TOMLDecodeError:
        return None
    return _single_dict_path(parsed)


def _assignment_key_parts(raw_line: str) -> tuple[tuple[str, ...], int] | None:
    quote: str | None = None
    escaped = False
    equals_index: int | None = None
    for index, char in enumerate(raw_line):
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if quote == "'":
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            continue
        if char == "#":
            return None
        if char == "=":
            equals_index = index
            break
    if equals_index is None:
        return None
    key_text = raw_line[:equals_index].strip()
    if not key_text:
        return None
    try:
        parsed = tomllib.loads(f"{key_text} = 0\n")
    except tomllib.TOMLDecodeError:
        return None
    parts = _single_dict_path(parsed, scalar_leaf=True)
    if parts is None:
        return None
    return parts, len(raw_line) - len(raw_line.lstrip()) + 1


def _single_dict_path(
    value: dict[str, Any],
    *,
    scalar_leaf: bool = False,
) -> tuple[str, ...] | None:
    parts: list[str] = []
    current: Any = value
    while isinstance(current, dict) and len(current) == 1:
        key, current = next(iter(current.items()))
        parts.append(key)
    if scalar_leaf:
        return tuple(parts) if parts and not isinstance(current, (dict, list)) else None
    return tuple(parts) if parts and current == {} else None


def format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("configuration numbers must be finite")
        return repr(value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise ValueError("unsupported configuration value type")


def load_config(root: Path) -> dict[str, dict[str, Any]]:
    return load_config_path(config_path(root), root=root, config_kind="main")


def set_section(
    root: Path,
    section: str,
    values: dict[str, Any],
    *,
    config_kind: str = "main",
    expected_section: dict[str, Any] | object = _EXPECTED_SECTION_UNSET,
) -> Path:
    return set_section_path(
        config_path(root),
        section,
        values,
        root=root,
        config_kind=config_kind,
        expected_section=expected_section,
    )


def set_section_path(
    path: Path,
    section: str,
    values: dict[str, Any],
    *,
    root: Path,
    config_kind: str = "main",
    diagnostic_source: str | None = None,
    expected_section: dict[str, Any] | object = _EXPECTED_SECTION_UNSET,
    expected_main_section: tuple[str, dict[str, Any]] | None = None,
) -> Path:
    path = root_bound_config_path(path, root)
    source = diagnostic_source if diagnostic_source is not None else _config_source(path, root)

    # Validate caller-controlled values before acquiring the coordination lock
    # or creating any target directory. The complete candidate remains an
    # in-lock validation because it depends on the authoritative snapshot.
    _validate_section_update(
        section,
        values,
        source=source,
        config_kind=config_kind,
    )
    rendered = render_section(section, values)
    parse_config_text("\n".join(rendered) + "\n", source=source, config_kind=config_kind)
    try:
        "\n".join(rendered).encode("utf-8")
    except UnicodeEncodeError:
        raise ConfigError("config_encoding_error", source=source) from None

    commit_confirmed = False
    with _config_write_interrupt_boundary(
        lambda: commit_confirmed
    ), config_write_lock(root, source=source) as validate_lock_identity:
        if expected_main_section is not None:
            main_section, expected_main_values = expected_main_section
            current_main_values = load_config(root).get(main_section, {})
            if current_main_values != expected_main_values:
                raise ConfigError(
                    "config_changed",
                    source=source,
                    field=_section_diagnostic_field(main_section, "main"),
                )
        existing_bytes = read_config_bytes(path, root=root)
        existing_text = None
        if existing_bytes is not None:
            try:
                existing_text = existing_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise ConfigError("config_encoding_error", source=source) from None
        existing_config: dict[str, dict[str, Any]] = {}
        if existing_text is not None:
            existing_config = parse_config_text(
                existing_text,
                source=source,
                config_kind=config_kind,
            )
            _reject_uneditable_equivalent_header(existing_text, section, source=source)
        if expected_section is not _EXPECTED_SECTION_UNSET:
            expected = dict(expected_section) if isinstance(expected_section, dict) else expected_section
            if existing_config.get(section, {}) != expected:
                raise ConfigError(
                    "config_changed",
                    source=source,
                    field=_section_diagnostic_field(section, config_kind),
                )

        existing = existing_text.splitlines() if existing_text is not None else []
        output: list[str] = []
        index = 0
        replaced = False
        while index < len(existing):
            line = existing[index]
            if line.strip() == f"[{section}]":
                replaced = True
                output.extend(rendered)
                index += 1
                while index < len(existing):
                    if _table_header_parts(existing[index]) is not None:
                        break
                    index += 1
                if index < len(existing) and output and output[-1] != "":
                    output.append("")
                continue
            output.append(line)
            index += 1

        if not replaced:
            if output and output[-1] != "":
                output.append("")
            output.extend(rendered)

        candidate = "\n".join(output).rstrip() + "\n"
        parse_config_text(candidate, source=source, config_kind=config_kind)
        try:
            candidate_bytes = candidate.encode("utf-8")
        except UnicodeEncodeError:
            raise ConfigError("config_encoding_error", source=source) from None
        if len(candidate_bytes) > MAX_CONFIG_BYTES:
            raise ConfigError("config_too_large", source=source)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path = root_bound_config_path(path, root)
            validate_lock_identity()
            path = _atomic_replace_config_text(
                path,
                candidate,
                root=root,
                source=source,
                expected_bytes=existing_bytes,
                validate_lock_identity=validate_lock_identity,
            )
            commit_confirmed = True
        except OSError:
            raise ConfigError("config_write_error", source=source) from None
        return path


def ensure_safe_write_path(path: Path, root: Path | None = None) -> None:
    if root is not None:
        root = root.resolve()
        try:
            path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise ValueError("config path must stay inside the memory root") from exc

    if path_is_link_like(path):
        raise ValueError("config path must not be a symlink")

    parent = path.parent
    stop_at = root if root is not None else None
    while True:
        if parent.exists() and path_is_link_like(parent):
            raise ValueError("config path parent must not be a symlink")
        if stop_at is not None and parent.resolve(strict=False) == stop_at:
            break
        next_parent = parent.parent
        if next_parent == parent:
            break
        parent = next_parent


def render_section(section: str, values: dict[str, Any]) -> list[str]:
    lines = [f"[{section}]"]
    for key, value in values.items():
        lines.append(f"{key} = {format_scalar(value)}")
    return lines


def _validate_section_update(
    section: str,
    values: dict[str, Any],
    *,
    source: str,
    config_kind: str,
) -> None:
    locations = _SourceLocations("")
    if not isinstance(values, dict):
        raise ConfigError(
            "invalid_structure",
            source=source,
            field=_section_diagnostic_field(section, config_kind),
            line=1,
            column=1,
        )
    if config_kind == "main":
        schema = MAIN_CONFIG_SCHEMA.get(section)
        path = (section,)
        if schema is None:
            parts = tuple(section.split("."))
            if len(parts) == 2 and parts[0] == "providers":
                if parts[1] not in KNOWN_PROVIDERS:
                    _raise_config("unknown_provider", source, locations, parts)
                schema = PROVIDER_CONFIG_SCHEMA
                path = parts
            else:
                code = "unknown_subsection" if len(parts) > 1 else "unknown_section"
                _raise_config(code, source, locations, parts)
        _validate_section_values(
            values,
            schema,
            source=source,
            locations=locations,
            path=path,
        )
        return
    if config_kind == "review_state":
        parts = tuple(section.split("."))
        if len(parts) != 2 or parts[0] not in REVIEW_STATE_SCHEMA:
            _raise_config("unknown_section", source, locations, parts)
        if not REVIEW_STATE_ID_PATTERNS[parts[0]].fullmatch(parts[1]):
            _raise_config("unsafe_identifier", source, locations, parts)
        _validate_section_values(
            values,
            REVIEW_STATE_SCHEMA[parts[0]],
            source=source,
            locations=locations,
            path=parts,
        )
        return
    raise ConfigError("unknown_config_kind", source=source, field="config_kind")


def _reject_uneditable_equivalent_header(text: str, section: str, *, source: str) -> None:
    target = tuple(section.split("."))
    canonical = f"[{section}]"
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if _table_header_parts(raw_line) != target:
            continue
        if raw_line.strip() == canonical:
            return
        column = len(raw_line) - len(raw_line.lstrip()) + 1
        raise ConfigError(
            "unsupported_header_spelling",
            source=source,
            field=section,
            line=line_number,
            column=column,
        )
