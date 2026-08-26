"""Strict vault selection with one explicit, local default selector.

Runtime selection is ``--root``, then ``AI_DEMEMORY_ROOT``, then a locally
saved default.  It never discovers a vault from CWD or from the package.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Literal, Mapping


CONFIG_HOME_ENV = "AI_DEMEMORY_CONFIG_HOME"
DEFAULT_VAULT_SELECTOR_FILE = "default-vault.json"
DEFAULT_VAULT_SELECTOR_SCHEMA_VERSION = 1
MAX_DEFAULT_VAULT_SELECTOR_BYTES = 4096
MAX_VAULT_CONFIG_BYTES = 64 * 1024


class VaultBindingError(ValueError):
    """Raised when a runtime command has no usable vault binding."""


@dataclass(frozen=True)
class VaultBinding:
    """A normalized vault and the deliberate binding which selected it."""

    root: Path
    source: Literal["argument", "environment", "default"]


def _is_unsafe_entry(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _has_stable_file_identity(metadata: os.stat_result) -> bool:
    """Require a usable identity to detect a swapped selector/config file."""
    return metadata.st_ino != 0


def _validate_regular_file(metadata: os.stat_result, label: str) -> None:
    if _is_unsafe_entry(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise VaultBindingError(f"{label} must be a regular file")
    if not _has_stable_file_identity(metadata):
        raise VaultBindingError(f"{label} has no stable file identity")
    if metadata.st_nlink != 1:
        raise VaultBindingError(f"{label} must not have multiple hard links")


def _is_windows_network_path(path: Path) -> bool:
    """Keep automatic local-default lookup from triggering UNC network I/O."""
    if os.name != "nt":
        return False
    return os.fspath(path).startswith(("\\\\", "//"))


def _absolute_path(value: str | Path, label: str, *, noun: str = "path") -> Path:
    try:
        path = Path(value).expanduser()
    except (TypeError, ValueError, OSError, RuntimeError) as exc:
        raise VaultBindingError(f"{label} requires an absolute {noun}") from exc
    if not path.is_absolute():
        raise VaultBindingError(f"{label} requires an absolute {noun}")
    # Avoid resolving before checking a selected vault's final directory.
    return Path(os.path.abspath(path))


def _local_selector_path(value: str | Path, label: str, *, noun: str = "path") -> Path:
    path = _absolute_path(value, label, noun=noun)
    if _is_windows_network_path(path):
        raise VaultBindingError(f"{label} requires a local {noun}")
    return path


def _read_flags() -> int:
    flags = os.O_RDONLY
    for name in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, name, 0)
    return flags


def _same_file(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        before.st_dev == after.st_dev
        and before.st_ino == after.st_ino
        and stat.S_IFMT(before.st_mode) == stat.S_IFMT(after.st_mode)
        and before.st_size == after.st_size
    )


def _read_regular(path: Path, *, limit: int, label: str) -> bytes:
    """Bounded final-entry read that rejects links, devices, and swaps."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise VaultBindingError(f"{label} is unreadable") from exc
    _validate_regular_file(before, label)
    if before.st_size > limit:
        raise VaultBindingError(f"{label} exceeds its byte limit")
    try:
        descriptor = os.open(path, _read_flags())
    except OSError as exc:
        raise VaultBindingError(f"{label} is unreadable") from exc
    try:
        opened = os.fstat(descriptor)
        _validate_regular_file(opened, label)
        if not _same_file(before, opened):
            raise VaultBindingError(f"{label} changed during access")
        body = bytearray()
        while len(body) <= limit:
            chunk = os.read(descriptor, min(64 * 1024, limit + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        if len(body) > limit:
            raise VaultBindingError(f"{label} exceeds its byte limit")
        after = path.lstat()
        _validate_regular_file(after, label)
        if not _same_file(opened, after):
            raise VaultBindingError(f"{label} changed during access")
        return bytes(body)
    except OSError as exc:
        raise VaultBindingError(f"{label} is unreadable") from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass


def _validate_selected_vault(value: str | Path) -> Path:
    """Require a real configured vault every time the selector is consumed."""
    root = _local_selector_path(value, "default vault", noun="vault path")
    try:
        root_metadata = root.lstat()
    except FileNotFoundError as exc:
        raise VaultBindingError("default vault directory does not exist") from exc
    except OSError as exc:
        raise VaultBindingError("default vault directory is unavailable") from exc
    if _is_unsafe_entry(root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
        raise VaultBindingError("default vault must be a real directory")
    try:
        _read_regular(
            root / ".ai-dememory.toml",
            limit=MAX_VAULT_CONFIG_BYTES,
            label="default vault config",
        )
    except FileNotFoundError as exc:
        raise VaultBindingError("default vault is missing .ai-dememory.toml") from exc
    # Command modules own strict TOML parsing. Selection validates only the
    # bounded, stable file identity so the invoked command can return its
    # schema-specific controlled diagnostic without duplicating that parser.
    return root.resolve(strict=True)


def _config_home(environ: Mapping[str, str] | None) -> Path | None:
    """Resolve a standard local config home without leaking host state to tests."""
    values = os.environ if environ is None else environ
    override = values.get(CONFIG_HOME_ENV)
    if override is not None:
        if not override.strip():
            raise VaultBindingError(f"{CONFIG_HOME_ENV} requires a non-empty absolute path")
        return _local_selector_path(override, CONFIG_HOME_ENV)
    if os.name == "nt":
        base = values.get("LOCALAPPDATA")
        if base:
            return _local_selector_path(base, "LOCALAPPDATA") / "ai-dememory"
        return None
    if sys.platform == "darwin":
        home = values.get("HOME")
        if home:
            return _local_selector_path(home, "HOME") / "Library" / "Application Support" / "ai-dememory"
        return None
    base = values.get("XDG_CONFIG_HOME")
    if base:
        return _local_selector_path(base, "XDG_CONFIG_HOME") / "ai-dememory"
    home = values.get("HOME")
    if home:
        return _local_selector_path(home, "HOME") / ".config" / "ai-dememory"
    return None


def default_vault_selector_path(environ: Mapping[str, str] | None = None) -> Path:
    """Return the selector path without creating files or directories."""
    home = _config_home(environ)
    if home is None:
        raise VaultBindingError(
            "default vault selector needs AI_DEMEMORY_CONFIG_HOME or a local user config directory"
        )
    return home / DEFAULT_VAULT_SELECTOR_FILE


def _selector_path(environ: Mapping[str, str] | None) -> Path | None:
    home = _config_home(environ)
    return None if home is None else home / DEFAULT_VAULT_SELECTOR_FILE


def _require_real_directory(path: Path, label: str, *, create: bool) -> bool:
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise VaultBindingError(f"{label} is unavailable") from exc
    if _is_unsafe_entry(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise VaultBindingError(f"{label} must be a real directory")
    return True


def _require_regular_or_missing(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise VaultBindingError("default vault selector is unavailable") from exc
    _validate_regular_file(metadata, "default vault selector")


def _selector_bytes(root: Path) -> bytes:
    return (json.dumps(
        {"schema_version": DEFAULT_VAULT_SELECTOR_SCHEMA_VERSION, "root": str(root)},
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n").encode("utf-8")


def _write_selector(selector: Path, body: bytes) -> None:
    _require_real_directory(selector.parent, "default vault selector directory", create=True)
    _require_regular_or_missing(selector)
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".default-vault-", suffix=".tmp", dir=selector.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        # An explicit use may replace a valid old choice, but never a link/device.
        _require_regular_or_missing(selector)
        os.replace(temporary, selector)
        temporary = None
    except OSError as exc:
        raise VaultBindingError("default vault selector could not be saved") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def save_default_vault(
    root: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> VaultBinding:
    """Explicitly validate and persist one default without changing environment state."""
    selected = _validate_selected_vault(root)
    selector = _selector_path(environ)
    if selector is None:
        raise VaultBindingError(
            "default vault selector needs AI_DEMEMORY_CONFIG_HOME or a local user config directory"
        )
    _write_selector(selector, _selector_bytes(selected))
    return VaultBinding(selected, "default")


def load_default_vault(
    *,
    environ: Mapping[str, str] | None = None,
) -> VaultBinding | None:
    """Load the saved default; malformed, unsafe, or stale state fails closed."""
    selector = _selector_path(environ)
    if selector is None:
        return None
    try:
        body = _read_regular(
            selector,
            limit=MAX_DEFAULT_VAULT_SELECTOR_BYTES,
            label="default vault selector",
        )
    except FileNotFoundError:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise VaultBindingError("default vault selector must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise VaultBindingError("default vault selector is malformed") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "root"}
        or payload.get("schema_version") != DEFAULT_VAULT_SELECTOR_SCHEMA_VERSION
        or not isinstance(payload.get("root"), str)
        or not payload["root"].strip()
    ):
        raise VaultBindingError("default vault selector is malformed")
    return VaultBinding(_validate_selected_vault(payload["root"]), "default")


def clear_default_vault(
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Clear a safe selector; this deliberately also recovers stale selections."""
    selector = _selector_path(environ)
    if selector is None or not _require_real_directory(
        selector.parent, "default vault selector directory", create=False
    ):
        return False
    _require_regular_or_missing(selector)
    try:
        selector.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise VaultBindingError("default vault selector could not be cleared") from exc
    return True


def resolve_runtime_vault(
    explicit_root: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> VaultBinding:
    """Resolve ``--root > AI_DEMEMORY_ROOT > saved default`` without CWD lookup."""
    if explicit_root is not None:
        if not explicit_root.strip():
            raise VaultBindingError("--root requires a non-empty vault path")
        return VaultBinding(
            _absolute_path(explicit_root, "--root", noun="vault path").resolve(),
            "argument",
        )
    values = os.environ if environ is None else environ
    configured_root = values.get("AI_DEMEMORY_ROOT")
    if configured_root is not None and configured_root != "":
        if not configured_root.strip():
            raise VaultBindingError("AI_DEMEMORY_ROOT requires a non-empty vault path")
        return VaultBinding(
            _absolute_path(
                configured_root,
                "AI_DEMEMORY_ROOT",
                noun="vault path",
            ).resolve(),
            "environment",
        )
    binding = load_default_vault(environ=environ)
    if binding is not None:
        return binding
    raise VaultBindingError(
        "runtime vault binding requires --root <vault-path>, AI_DEMEMORY_ROOT, or ai-dememory vault use <absolute-vault-path>"
    )
