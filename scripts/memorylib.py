#!/usr/bin/env python3
"""Shared helpers for the local Markdown memory toolchain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any, Iterable

from resource_limits import (
    MAX_MEMORY_FILE_BYTES,
    MAX_MEMORY_FILES,
    MAX_MEMORY_SCAN_ENTRIES,
    MAX_MEMORY_TOTAL_BYTES,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

MEMORY_DIRS = (
    Path("memories/durable"),
    Path("memories/active"),
    Path("memories/projects"),
    Path("memories/tools"),
    Path("memories/archive"),
    Path("memories/sessions"),
)

REQUIRED_FIELDS = (
    "id",
    "title",
    "type",
    "status",
    "scope",
    "project",
    "tags",
    "aliases",
    "created_at",
    "updated_at",
    "confidence",
    "sensitivity",
    "source",
    "pin",
    "decay",
    "review_after",
)

TYPES = {"durable", "active", "project", "tool", "archive", "session"}
STATUSES = {"active", "proposed", "stale", "disputed", "archived", "superseded", "expired"}
SCOPES = {"personal", "project", "tool", "session", "global"}
SENSITIVITIES = {"public", "internal", "private", "sensitive", "secret-prohibited"}
SOURCE_KINDS = {
    "manual",
    "codex",
    "claude",
    "gemini",
    "automation",
    "import",
    "external",
    "conversation",
}
DECAYS = {"none", "slow", "normal", "fast"}

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_/-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class MemoryError(Exception):
    """Base exception for memory tooling."""


class FrontmatterError(MemoryError):
    """Raised when frontmatter cannot be parsed."""


@dataclass(frozen=True)
class MemoryDocument:
    path: Path
    frontmatter: dict[str, Any]
    content: str

    @property
    def relpath(self) -> str:
        try:
            return repo_relative_path(self.path, REPO_ROOT)
        except ValueError:
            return str(self.path)


def repo_root(path: str | Path | None = None) -> Path:
    global REPO_ROOT
    env_root = os.environ.get("AI_DEMEMORY_ROOT")
    if path:
        REPO_ROOT = Path(path).resolve()
    elif env_root:
        REPO_ROOT = Path(env_root).resolve()
    return REPO_ROOT


def logical_relative_path(path: str | Path, root: str | Path) -> Path:
    """Return an abspath-normalized relative path without following symlinks."""
    logical_root = Path(os.path.abspath(Path(root).expanduser()))
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = logical_root / candidate
    return Path(os.path.abspath(candidate)).relative_to(logical_root)


def contained_relative_path(path: str | Path, root: str | Path) -> Path:
    """Return the logical path below *root* after validating resolved containment.

    Both logical paths use ``abspath`` so platform aliases such as macOS
    ``/var`` and ``/private/var`` are never mixed in one ``relative_to`` call.
    Resolved containment is checked separately so a symlink cannot escape the
    root.  Returning the logical relative path preserves symlink components for
    callers that intentionally reject them one component at a time.
    """
    logical_root = Path(os.path.abspath(Path(root).expanduser()))
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = logical_root / candidate
    logical_candidate = Path(os.path.abspath(candidate))

    resolved_root = logical_root.resolve(strict=False)
    resolved_candidate = logical_candidate.resolve(strict=False)
    resolved_relative = resolved_candidate.relative_to(resolved_root)
    try:
        return logical_relative_path(logical_candidate, logical_root)
    except ValueError:
        # The caller may have supplied one side through an OS path alias and
        # the other through its canonical spelling. Resolved containment above
        # has already established that returning this path is safe.
        return resolved_relative


def repo_relative_path(path: Path, root: Path) -> str:
    """Return a repository-relative path with stable POSIX separators."""
    return contained_relative_path(path, root).as_posix()


def path_is_link_like(path: Path) -> bool:
    """Return True for symlinks, Windows junctions, and other reparse points."""

    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except (FileNotFoundError, OSError):
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def assert_safe_write_target(path: Path, root: Path | None = None) -> Path:
    """Validate an in-root regular-file target without following link components."""

    target = Path(os.path.abspath(path.expanduser()))
    logical_root = Path(os.path.abspath(root.expanduser())) if root is not None else None
    if logical_root is not None:
        try:
            relative = target.relative_to(logical_root)
        except ValueError as exc:
            raise ValueError("write target must stay inside the configured root") from exc
        current = logical_root
        if path_is_link_like(current):
            raise ValueError("write root must not be a symlink or junction")
        for part in relative.parts:
            current = current / part
            if path_is_link_like(current):
                raise ValueError("write target must not contain symlinks or junctions")
    else:
        current = target.parent
        while True:
            if current.exists() and path_is_link_like(current):
                raise ValueError("write target parent must not be a symlink or junction")
            parent = current.parent
            if parent == current:
                break
            current = parent
        if path_is_link_like(target):
            raise ValueError("write target must not be a symlink or junction")

    if target.exists() and not target.is_file():
        raise ValueError("write target must be a regular file")
    if not target.parent.is_dir():
        raise FileNotFoundError(f"write target parent does not exist: {target.parent}")
    return target


def safe_write_text(
    path: Path,
    text: str,
    *,
    root: Path | None = None,
    overwrite: bool,
    encoding: str = "utf-8",
) -> Path:
    """Write text without following links; replace existing files atomically."""

    target = assert_safe_write_target(path, root)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    flags |= int(getattr(os, "O_BINARY", 0))
    payload = text.encode(encoding)

    if not overwrite or not target.exists():
        fd = os.open(target, flags, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=True) as stream:
                fd = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if fd >= 0:
                os.close(fd)
        return target

    temp_path = target.with_name(
        f".{target.name}.ai-dememory-{secrets.token_hex(8)}.tmp"
    )
    fd = -1
    try:
        fd = os.open(temp_path, flags, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            fd = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        target = assert_safe_write_target(target, root)
        os.replace(temp_path, target)
        return target
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def resolve_reports_path(
    root: Path,
    path: str | Path,
    *,
    label: str = "report path",
) -> Path:
    """Resolve one generated report below ``reports/`` without link traversal."""

    logical_root = Path(os.path.abspath(root.expanduser()))
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = logical_root / candidate
    target = Path(os.path.abspath(candidate))
    reports_root = logical_root / "reports"
    try:
        relative = target.relative_to(logical_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the memory root") from exc
    try:
        target.relative_to(reports_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay under reports/") from exc

    current = logical_root
    for part in relative.parts:
        current = current / part
        if path_is_link_like(current):
            raise ValueError(f"{label} must not contain symlinks or junctions")
    return target


def is_memory_file(path: Path, root: Path) -> bool:
    if path.name == "README.md" or path.suffix.lower() != ".md":
        return False
    try:
        rel = contained_relative_path(path, root)
    except ValueError:
        return False
    return any(rel == d or d in rel.parents for d in MEMORY_DIRS)


def discover_memory_files(
    root: Path,
    *,
    max_scan_entries: int = MAX_MEMORY_SCAN_ENTRIES,
    max_files: int = MAX_MEMORY_FILES,
    max_file_bytes: int = MAX_MEMORY_FILE_BYTES,
    max_total_bytes: int = MAX_MEMORY_TOTAL_BYTES,
) -> list[Path]:
    """Discover canonical Markdown memories within explicit resource budgets."""

    files: list[Path] = []
    entries_seen = 0
    total_bytes = 0
    for memory_dir in MEMORY_DIRS:
        base = root / memory_dir
        if not base.exists():
            continue
        if path_is_link_like(base):
            raise MemoryError(
                f"memory scan path must not be a symlink or junction: {memory_dir.as_posix()}"
            )
        for current_raw, dir_names, file_names in os.walk(base, topdown=True, followlinks=False):
            current = Path(current_raw)
            dir_names.sort()
            file_names.sort()

            retained_dirs: list[str] = []
            for name in dir_names:
                entries_seen += 1
                if entries_seen > max_scan_entries:
                    raise MemoryError(
                        f"memory scan exceeded the {max_scan_entries} entry limit"
                    )
                candidate = current / name
                if path_is_link_like(candidate):
                    raise MemoryError(
                        "memory scan path must not contain symlinks or junctions: "
                        f"{logical_relative_path(candidate, root).as_posix()}"
                    )
                retained_dirs.append(name)
            dir_names[:] = retained_dirs

            for name in file_names:
                entries_seen += 1
                if entries_seen > max_scan_entries:
                    raise MemoryError(
                        f"memory scan exceeded the {max_scan_entries} entry limit"
                    )
                candidate = current / name
                if path_is_link_like(candidate):
                    raise MemoryError(
                        "memory scan path must not contain symlinks or junctions: "
                        f"{logical_relative_path(candidate, root).as_posix()}"
                    )
                if not is_memory_file(candidate, root):
                    continue
                try:
                    size = candidate.stat(follow_symlinks=False).st_size
                except OSError as exc:
                    raise MemoryError(f"memory file could not be inspected: {candidate}") from exc
                if size > max_file_bytes:
                    raise MemoryError(
                        f"memory file exceeds the {max_file_bytes} byte limit: "
                        f"{repo_relative_path(candidate, root)}"
                    )
                total_bytes += size
                if total_bytes > max_total_bytes:
                    raise MemoryError(
                        f"memory scan exceeded the {max_total_bytes} total byte limit"
                    )
                files.append(candidate)
                if len(files) > max_files:
                    raise MemoryError(
                        f"memory scan exceeded the {max_files} file limit"
                    )
    return sorted(files)


def discover_markdown_files(
    root: Path,
    relative_dir: str | Path,
    *,
    excluded_dirs: Iterable[str | Path] = (),
    max_scan_entries: int = MAX_MEMORY_SCAN_ENTRIES,
    max_files: int = MAX_MEMORY_FILES,
    max_file_bytes: int = MAX_MEMORY_FILE_BYTES,
    max_total_bytes: int = MAX_MEMORY_TOTAL_BYTES,
) -> list[Path]:
    """Discover Markdown below one in-root directory within fixed budgets."""

    base_relative = contained_relative_path(Path(root) / relative_dir, root)
    base = Path(root) / base_relative
    if not base.exists():
        return []
    if not base.is_dir():
        raise MemoryError(f"Markdown scan path must be a directory: {base_relative.as_posix()}")
    if path_is_link_like(base):
        raise MemoryError(
            f"Markdown scan path must not be a symlink or junction: {base_relative.as_posix()}"
        )

    excluded: set[Path] = set()
    for candidate in excluded_dirs:
        excluded_relative = contained_relative_path(Path(root) / candidate, root)
        try:
            excluded_relative.relative_to(base_relative)
        except ValueError as exc:
            raise MemoryError(
                "excluded Markdown scan directories must stay below the scan path"
            ) from exc
        excluded.add(excluded_relative)

    files: list[Path] = []
    entries_seen = 0
    total_bytes = 0
    for current_raw, dir_names, file_names in os.walk(base, topdown=True, followlinks=False):
        current = Path(current_raw)
        dir_names.sort()
        file_names.sort()

        retained_dirs: list[str] = []
        for name in dir_names:
            entries_seen += 1
            if entries_seen > max_scan_entries:
                raise MemoryError(
                    f"Markdown scan exceeded the {max_scan_entries} entry limit"
                )
            candidate = current / name
            candidate_relative = contained_relative_path(candidate, root)
            if path_is_link_like(candidate):
                raise MemoryError(
                    "Markdown scan path must not contain symlinks or junctions: "
                    f"{candidate_relative.as_posix()}"
                )
            if candidate_relative not in excluded:
                retained_dirs.append(name)
        dir_names[:] = retained_dirs

        for name in file_names:
            entries_seen += 1
            if entries_seen > max_scan_entries:
                raise MemoryError(
                    f"Markdown scan exceeded the {max_scan_entries} entry limit"
                )
            candidate = current / name
            candidate_relative = contained_relative_path(candidate, root)
            if path_is_link_like(candidate):
                raise MemoryError(
                    "Markdown scan path must not contain symlinks or junctions: "
                    f"{candidate_relative.as_posix()}"
                )
            if candidate.suffix.lower() != ".md" or candidate.name == "README.md":
                continue
            try:
                size = candidate.stat(follow_symlinks=False).st_size
            except OSError as exc:
                raise MemoryError(f"Markdown file could not be inspected: {candidate}") from exc
            if size > max_file_bytes:
                raise MemoryError(
                    f"Markdown file exceeds the {max_file_bytes} byte limit: "
                    f"{candidate_relative.as_posix()}"
                )
            total_bytes += size
            if total_bytes > max_total_bytes:
                raise MemoryError(
                    f"Markdown scan exceeded the {max_total_bytes} total byte limit"
                )
            files.append(candidate)
            if len(files) > max_files:
                raise MemoryError(
                    f"Markdown scan exceeded the {max_files} file limit"
                )
    return sorted(files)


def parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [parse_value(item) for item in split_inline_list(inner)]
    if raw.startswith('"') and raw.endswith('"'):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", raw):
        try:
            return int(raw)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+\.\d+", raw):
        try:
            return float(raw)
        except ValueError:
            pass
    return raw


def split_inline_list(inner: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    for char in inner:
        if escape:
            current.append(char)
            escape = False
            continue
        if char == "\\":
            current.append(char)
            escape = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char == ",":
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    items.append("".join(current).strip())
    return items


def parse_frontmatter_text(text: str, path: Path | None = None) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    label = str(path) if path else "<memory>"
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError(f"{label}: missing opening frontmatter delimiter")

    closing_index: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = idx
            break
    if closing_index is None:
        raise FrontmatterError(f"{label}: missing closing frontmatter delimiter")

    data: dict[str, Any] = {}
    current_map: dict[str, Any] | None = None
    current_key: str | None = None

    for line_no, line in enumerate(lines[1:closing_index], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  "):
            if current_map is None or current_key is None:
                raise FrontmatterError(f"{label}:{line_no}: nested field without parent")
            key, value = split_key_value(stripped, label, line_no)
            current_map[key] = parse_value(value)
            continue
        key, value = split_key_value(stripped, label, line_no)
        if value == "":
            data[key] = {}
            current_key = key
            current_map = data[key]
        else:
            data[key] = parse_value(value)
            current_key = None
            current_map = None

    body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
    return data, body


def split_key_value(line: str, label: str, line_no: int) -> tuple[str, str]:
    if ":" not in line:
        raise FrontmatterError(f"{label}:{line_no}: expected 'key: value'")
    key, value = line.split(":", 1)
    key = key.strip()
    if not key:
        raise FrontmatterError(f"{label}:{line_no}: empty key")
    return key, value.strip()


def read_bounded_text(
    path: Path,
    *,
    max_file_bytes: int = MAX_MEMORY_FILE_BYTES,
) -> str:
    if path_is_link_like(path):
        raise MemoryError(f"memory file must not be a symlink or junction: {path}")
    try:
        size = path.stat(follow_symlinks=False).st_size
    except OSError as exc:
        raise MemoryError(f"memory file could not be inspected: {path}") from exc
    if size > max_file_bytes:
        raise MemoryError(f"memory file exceeds the {max_file_bytes} byte limit: {path}")
    try:
        with path.open("rb") as stream:
            raw = stream.read(max_file_bytes + 1)
    except OSError as exc:
        raise MemoryError(f"memory file could not be read: {path}") from exc
    if len(raw) > max_file_bytes:
        raise MemoryError(f"memory file exceeds the {max_file_bytes} byte limit: {path}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MemoryError(f"memory file must be valid UTF-8: {path}") from exc


def load_memory(
    path: Path,
    *,
    max_file_bytes: int = MAX_MEMORY_FILE_BYTES,
) -> MemoryDocument:
    text = read_bounded_text(path, max_file_bytes=max_file_bytes)
    frontmatter, content = parse_frontmatter_text(text, path)
    return MemoryDocument(path=path, frontmatter=frontmatter, content=content)


def load_memories(root: Path) -> list[MemoryDocument]:
    return [load_memory(path) for path in discover_memory_files(root)]


def validate_document(document: MemoryDocument) -> list[str]:
    data = document.frontmatter
    errors: list[str] = []
    prefix = document.relpath

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"{prefix}: missing required field '{field}'")

    if errors:
        return errors

    expect_string(errors, prefix, data, "id")
    if isinstance(data.get("id"), str) and not ID_RE.fullmatch(data["id"]):
        errors.append(f"{prefix}: id must match {ID_RE.pattern}")

    expect_string(errors, prefix, data, "title")
    enum(errors, prefix, data, "type", TYPES)
    enum(errors, prefix, data, "status", STATUSES)
    enum(errors, prefix, data, "scope", SCOPES)
    enum(errors, prefix, data, "sensitivity", SENSITIVITIES)
    enum(errors, prefix, data, "decay", DECAYS)

    if data.get("sensitivity") == "secret-prohibited":
        errors.append(f"{prefix}: sensitivity 'secret-prohibited' is not allowed in canonical memory")

    if not (data.get("project") is None or isinstance(data.get("project"), str)):
        errors.append(f"{prefix}: project must be a string or null")

    for field in ("tags", "aliases"):
        value = data.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{prefix}: {field} must be an inline list of strings")

    for field in ("created_at", "updated_at", "review_after"):
        if not is_date_string(data.get(field)):
            errors.append(f"{prefix}: {field} must use YYYY-MM-DD")

    if is_date_string(data.get("created_at")) and is_date_string(data.get("updated_at")):
        if parse_date(data["updated_at"]) < parse_date(data["created_at"]):
            errors.append(f"{prefix}: updated_at cannot be before created_at")

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        errors.append(f"{prefix}: confidence must be a number between 0.0 and 1.0")
    elif not 0.0 <= float(confidence) <= 1.0:
        errors.append(f"{prefix}: confidence must be between 0.0 and 1.0")

    if not isinstance(data.get("pin"), bool):
        errors.append(f"{prefix}: pin must be true or false")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append(f"{prefix}: source must be a map with kind and ref")
    else:
        if source.get("kind") not in SOURCE_KINDS:
            errors.append(f"{prefix}: source.kind must be one of {sorted(SOURCE_KINDS)}")
        if "ref" not in source:
            errors.append(f"{prefix}: source.ref is required")
        elif not (source.get("ref") is None or isinstance(source.get("ref"), str)):
            errors.append(f"{prefix}: source.ref must be a string or null")

    if data.get("type") == "durable":
        if data.get("reviewed") is not True:
            errors.append(f"{prefix}: durable memories must include reviewed: true")
        expect_string(errors, prefix, data, "reviewed_by")
        if not is_date_string(data.get("reviewed_at")):
            errors.append(f"{prefix}: reviewed_at must use YYYY-MM-DD")

    return errors


def validate_memories(root: Path) -> tuple[list[MemoryDocument], list[str]]:
    documents: list[MemoryDocument] = []
    errors: list[str] = []
    for path in discover_memory_files(root):
        try:
            document = load_memory(path)
        except MemoryError as exc:
            errors.append(str(exc))
            continue
        documents.append(document)
        errors.extend(validate_document(document))

    seen: dict[str, Path] = {}
    for document in documents:
        memory_id = document.frontmatter.get("id")
        if not isinstance(memory_id, str):
            continue
        if memory_id in seen:
            errors.append(
                f"{document.relpath}: duplicate id '{memory_id}' also used by {seen[memory_id]}"
            )
        else:
            seen[memory_id] = document.path

    return documents, errors


def expect_string(errors: list[str], prefix: str, data: dict[str, Any], field: str) -> None:
    if not isinstance(data.get(field), str) or data.get(field) == "":
        errors.append(f"{prefix}: {field} must be a non-empty string")


def enum(
    errors: list[str],
    prefix: str,
    data: dict[str, Any],
    field: str,
    allowed: Iterable[str],
) -> None:
    value = data.get(field)
    allowed_set = set(allowed)
    if value not in allowed_set:
        errors.append(f"{prefix}: {field} must be one of {sorted(allowed_set)}")


def is_date_string(value: Any) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def today() -> date:
    return datetime.now(timezone.utc).date()


def extract_summary(content: str, max_chars: int = 320) -> str:
    useful_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        useful_lines.append(line)
        if sum(len(item) for item in useful_lines) >= max_chars:
            break
    summary = " ".join(useful_lines).strip()
    if len(summary) > max_chars:
        return summary[: max_chars - 1].rstrip() + "..."
    return summary


def content_hash(frontmatter: dict[str, Any], content: str) -> str:
    import hashlib
    import json

    payload = json.dumps(frontmatter, sort_keys=True, default=str) + "\n" + content
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def list_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return ""


def half_life_days(decay: str) -> float | None:
    return {"none": None, "slow": 180.0, "normal": 60.0, "fast": 14.0}.get(decay, 60.0)


def recency_score(updated_at: str, decay: str, now: date | None = None) -> float:
    if decay == "none":
        return 1.0
    if not is_date_string(updated_at):
        return 0.0
    half_life = half_life_days(decay)
    if half_life is None:
        return 1.0
    now_date = now or today()
    age_days = max(0, (now_date - parse_date(updated_at)).days)
    return math.pow(0.5, age_days / half_life)


def slugify(value: str, fallback: str = "memory") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback
