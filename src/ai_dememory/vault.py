"""Canonical Markdown vault operations."""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import Memory
from .policy import reject_high_confidence_secrets


class VaultError(ValueError):
    pass


MAX_MEMORY_BYTES = 2_000_000
MAX_MEMORY_CONTENT_BYTES = 1_900_000
MAX_MEMORY_FILES = 10_000
MAX_TITLE_BYTES = 512
MAX_METADATA_VALUE_BYTES = 1_024
_MEMORY_ID = re.compile(r"[0-9a-f]{32}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive_write_lock(path: Path) -> Iterator[None]:
    """Fail fast when another process is already changing canonical memory."""
    if path.is_symlink():
        raise VaultError(f"Vault write lock cannot be a symbolic link: {path}")
    try:
        handle = path.open("a+b")
    except OSError as exc:
        raise VaultError(f"Cannot open the vault write lock {path}: {exc}") from exc
    try:
        parent = path.parent.resolve(strict=True)
        resolved = path.resolve(strict=True)
        if resolved.parent != parent or not resolved.is_file():
            raise VaultError(f"Vault write lock is not a local regular file: {path}")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise VaultError("Another memory write is already in progress; retry the command") from exc
        try:
            yield
        finally:
            try:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        handle.close()


def _rollback_unverified_write(path: Path, reason: object) -> VaultError:
    try:
        path.unlink()
    except OSError as exc:
        return VaultError(
            f"Saved memory could not be verified and rollback failed; inspect {path}: {exc}"
        )
    return VaultError(f"Saved memory could not be verified and was rolled back: {path}: {reason}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:48] or "memory").strip("-")


def _default_title(content: str) -> str:
    first = next((line.strip() for line in content.splitlines() if line.strip()), "Memory")
    return first[:72]


def validate_title(value: str, subject: str) -> str:
    if not isinstance(value, str):
        raise VaultError(f"{subject} must be a string")
    title = value.strip()
    if not title:
        raise VaultError(f"{subject} cannot be empty")
    try:
        encoded = title.encode("utf-8")
    except UnicodeError as exc:
        raise VaultError(f"{subject} contains invalid Unicode") from exc
    if len(encoded) > MAX_TITLE_BYTES:
        raise VaultError(f"{subject} exceeds the {MAX_TITLE_BYTES}-byte limit")
    return title


def validate_memory_id(value: str) -> str:
    if not isinstance(value, str) or not _MEMORY_ID.fullmatch(value):
        raise VaultError("Memory id must be exactly 32 lowercase hexadecimal characters")
    return value


def validate_scope(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}", value):
        raise VaultError("scope must be 1-128 letters, digits, dots, hyphens, underscores or colons")
    return value


def validate_source(value: Any) -> dict[str, str]:
    fields = {"provider", "session", "turn", "evidence_kind", "excerpt"}
    if not isinstance(value, dict) or set(value) != fields:
        raise VaultError("source requires provider, session, turn, evidence_kind and excerpt")
    if any(not isinstance(item, str) or not item.strip() for item in value.values()):
        raise VaultError("source fields must be non-empty strings")
    source = {key: item.strip() for key, item in value.items()}
    if source["evidence_kind"] not in {"user_statement", "verified_outcome", "inference"}:
        raise VaultError("Unsupported source evidence_kind")
    encoded = json.dumps(source, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_METADATA_VALUE_BYTES:
        raise VaultError("source exceeds the 1024-byte limit; provide a short evidence excerpt")
    reject_high_confidence_secrets(encoded)
    return source


def parse_markdown(path: Path) -> tuple[dict[str, str], str]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise VaultError(f"Cannot inspect memory {path}: {exc}") from exc
    if size > MAX_MEMORY_BYTES:
        raise VaultError(f"Memory {path.name} exceeds the {MAX_MEMORY_BYTES}-byte limit")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VaultError(f"Cannot read memory {path}: {exc}") from exc
    if not text.startswith("---\n"):
        raise VaultError(f"Memory {path.name} is missing frontmatter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise VaultError(f"Memory {path.name} has incomplete frontmatter")
    metadata: dict[str, str] = {}
    for line in text[4:marker].splitlines():
        if not line.strip():
            continue
        key, separator, raw = line.partition(":")
        if not separator or not key.strip():
            raise VaultError(f"Memory {path.name} has invalid frontmatter")
        value = raw.strip()
        if value.startswith('"'):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError as exc:
                raise VaultError(f"Memory {path.name} has invalid quoted metadata") from exc
            if not isinstance(decoded, str):
                raise VaultError(f"Memory {path.name} metadata values must be strings")
            value = decoded
        try:
            encoded = value.encode("utf-8")
        except UnicodeError as exc:
            raise VaultError(f"Memory {path.name} metadata contains invalid Unicode") from exc
        if len(encoded) > MAX_METADATA_VALUE_BYTES:
            raise VaultError(
                f"Memory {path.name} metadata value exceeds the "
                f"{MAX_METADATA_VALUE_BYTES}-byte limit"
            )
        metadata[key.strip()] = value
    return metadata, text[marker + 5 :].strip()


@dataclass(frozen=True)
class Vault:
    root: Path
    name: str

    def _managed_dir(self, name: str) -> Path:
        candidate = self.root / name
        if candidate.is_symlink():
            raise VaultError(f"Vault managed directory cannot be a symbolic link: {candidate}")
        try:
            candidate.mkdir(exist_ok=True)
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise VaultError(f"Cannot prepare vault managed directory {candidate}: {exc}") from exc
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise VaultError(f"Vault managed directory escapes the vault root: {candidate}") from exc
        if not resolved.is_dir():
            raise VaultError(f"Vault managed path is not a directory: {candidate}")
        return resolved

    @property
    def memories_dir(self) -> Path:
        return self._managed_dir("memories")

    @property
    def proposals_dir(self) -> Path:
        return self._managed_dir("proposals")

    @property
    def indexes_dir(self) -> Path:
        return self._managed_dir("indexes")

    @classmethod
    def create(cls, path: Path, name: str | None = None) -> "Vault":
        requested = path.expanduser()
        if requested.exists() and requested.is_symlink():
            raise VaultError("The vault root cannot be a symbolic link")
        root = requested.resolve()
        marker = root / ".ai-dememory.toml"
        if marker.exists():
            return cls.open(root)
        if root.exists() and not root.is_dir():
            raise VaultError(f"Vault path is not a directory: {root}")
        if root.exists() and any(root.iterdir()):
            raise VaultError(
                f"Refusing to initialize a non-empty directory: {root}. Choose a new or empty folder."
            )
        root.mkdir(parents=True, exist_ok=True)
        vault_name = (name or root.name or "My memory").strip()
        if not vault_name:
            raise VaultError("Vault name cannot be empty")
        payload = "\n".join(
            (
                "schema_version = 1",
                f"name = {json.dumps(vault_name)}",
                f"created_at = {json.dumps(utc_now())}",
                "",
            )
        )
        _atomic_write(marker, payload)
        vault = cls(root=root, name=vault_name)
        vault.memories_dir
        vault.proposals_dir
        vault.indexes_dir
        return vault

    @classmethod
    def open(cls, path: Path) -> "Vault":
        requested = path.expanduser()
        if requested.is_symlink():
            raise VaultError("The vault root cannot be a symbolic link")
        root = requested.resolve()
        marker = root / ".ai-dememory.toml"
        try:
            with marker.open("rb") as handle:
                data = tomllib.load(handle)
        except FileNotFoundError as exc:
            raise VaultError(f"Not an ai DeMemory V3 vault: {root}. Run `ai-dememory setup`.") from exc
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise VaultError(f"Cannot read vault configuration {marker}: {exc}") from exc
        if data.get("schema_version") != 1 or not isinstance(data.get("name"), str):
            raise VaultError(f"Unsupported or invalid V3 vault configuration: {marker}")
        vault = cls(root=root, name=data["name"])
        vault.memories_dir
        vault.proposals_dir
        vault.indexes_dir
        return vault

    def iter_memory_paths(self) -> Iterator[Path]:
        memories = self.memories_dir
        count = 0

        def walk(directory: Path) -> Iterator[Path]:
            nonlocal count
            try:
                entries = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError as exc:
                raise VaultError(f"Cannot inspect memory directory {directory}: {exc}") from exc
            for entry in entries:
                path = Path(entry.path)
                if entry.is_symlink():
                    raise VaultError(f"Linked paths are not allowed under memories: {path}")
                try:
                    canonical = path.resolve(strict=True)
                    canonical.relative_to(memories)
                except (OSError, ValueError) as exc:
                    raise VaultError(f"Memory path escapes the vault: {path}") from exc
                if canonical != path.absolute():
                    raise VaultError(f"Linked paths are not allowed under memories: {path}")
                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError as exc:
                    raise VaultError(f"Cannot inspect memory path {path}: {exc}") from exc
                if is_directory:
                    yield from walk(canonical)
                elif is_file and path.suffix == ".md":
                    count += 1
                    if count > MAX_MEMORY_FILES:
                        raise VaultError(f"Vault exceeds the {MAX_MEMORY_FILES}-memory limit")
                    yield canonical

        yield from walk(memories)

    def remember(
        self, content: str, title: str | None = None, *, memory_id: str | None = None,
        scope: str = "global",
    ) -> Memory:
        with _exclusive_write_lock(self.root / ".ai-dememory.write.lock"):
            return self._remember(content, title, memory_id=memory_id, scope=validate_scope(scope))

    def _remember(
        self, content: str, title: str | None = None, *, memory_id: str | None = None,
        scope: str = "global", source: dict[str, str] | None = None,
        status: str = "active", key: str | None = None, supersedes: str | None = None,
    ) -> Memory:
        """Write while the caller holds the vault lock."""
        if not isinstance(content, str):
            raise VaultError("Memory content must be a string")
        clean_content = content.strip()
        if not clean_content:
            raise VaultError("Memory content cannot be empty")
        if len(clean_content.encode("utf-8")) > MAX_MEMORY_CONTENT_BYTES:
            raise VaultError(f"Memory exceeds the {MAX_MEMORY_CONTENT_BYTES}-byte content limit")
        reject_high_confidence_secrets(clean_content)
        clean_title = validate_title(title or _default_title(clean_content), "Memory title")
        reject_high_confidence_secrets(clean_title)
        supplied_id = memory_id is not None
        memory_id = validate_memory_id(memory_id or uuid.uuid4().hex)
        if supplied_id:
            existing = self.get(memory_id)
            if existing:
                if existing.title == clean_title and existing.content == clean_content and existing.scope == scope:
                    return existing
                raise VaultError(f"Memory id already exists with different content: {memory_id}")
        if self.memory_count() >= MAX_MEMORY_FILES:
            raise VaultError(f"Vault has reached the {MAX_MEMORY_FILES}-memory limit")
        created_at = utc_now()
        filename = f"{created_at[:10]}-{_slug(clean_title)}-{memory_id}.md"
        path = self.memories_dir / filename
        if path.exists():
            raise VaultError(f"Memory path already exists: {path}")
        memory = Memory(memory_id, clean_title, clean_content, created_at, path,
                        scope, source or {}, status, key, supersedes)
        self._write_memory(memory)
        try:
            saved = self.read_memory(path)
        except VaultError as exc:
            raise _rollback_unverified_write(path, exc) from exc
        if saved != memory:
            raise _rollback_unverified_write(path, "stored fields did not match the request")
        return saved

    def _write_memory(self, memory: Memory) -> None:
        fields = {"id": memory.memory_id, "title": memory.title,
                  "created_at": memory.created_at, "scope": memory.scope,
                  "status": memory.status}
        if memory.source:
            fields["source"] = json.dumps(memory.source, ensure_ascii=False)
        if memory.key:
            fields["key"] = memory.key
        if memory.supersedes:
            fields["supersedes"] = memory.supersedes
        lines = ["---", *(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()),
                 "---", "", memory.content, ""]
        _atomic_write(memory.path, "\n".join(lines))

    def learn(
        self, title: str, content: str, scope: str, source: dict[str, str], event_id: str,
        key: str | None = None, supersedes: str | None = None, provisional: bool = False,
    ) -> dict[str, Any]:
        scope = validate_scope(scope)
        source = validate_source(source)
        title = validate_title(title, "Memory title")
        if not isinstance(content, str) or not content.strip():
            raise VaultError("Memory content must be a non-empty string")
        content = content.strip()
        if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 256:
            raise VaultError("event_id must be a non-empty string of at most 256 characters")
        if not isinstance(provisional, bool):
            raise VaultError("provisional must be a boolean")
        if key is not None:
            key = validate_scope(key)
        if supersedes is not None:
            supersedes = validate_memory_id(supersedes)
        provisional = provisional or source["evidence_kind"] == "inference"
        if provisional and supersedes:
            raise VaultError("Provisional learning cannot replace an active memory")
        seed = json.dumps([scope, source["provider"], source["session"], source["turn"],
                           event_id], ensure_ascii=False)
        memory_id = uuid.uuid5(uuid.NAMESPACE_URL, seed).hex
        with _exclusive_write_lock(self.root / ".ai-dememory.write.lock"):
            memories = [self.read_memory(path) for path in self.iter_memory_paths()]
            for memory in memories:
                if memory.memory_id == memory_id:
                    return {**memory.to_dict(), "admission": "duplicate"}
                if memory.scope == scope and memory.content == content and memory.key == key:
                    if memory.status == "active" or (memory.status == "provisional" and provisional):
                        return {**memory.to_dict(), "admission": "duplicate"}
            prior = next((memory for memory in memories if memory.memory_id == supersedes), None)
            if supersedes and (prior is None or prior.scope != scope or prior.status != "active"):
                raise VaultError("supersedes must reference an active memory in the same scope")
            if not provisional and key and prior is None:
                prior = next((memory for memory in memories
                              if memory.scope == scope and memory.key == key and memory.status == "active"), None)
            saved = self._remember(content, title, memory_id=memory_id, scope=scope, source=source,
                                   status="provisional" if provisional else "active", key=key,
                                   supersedes=prior.memory_id if prior else None)
            if prior:
                try:
                    self._write_memory(replace(prior, status="superseded"))
                except OSError:
                    saved.path.unlink()
                    raise
            return {**saved.to_dict(), "admission": "created"}

    def forget(self, memory_id: str, scope: str = "global") -> dict[str, Any]:
        validate_scope(scope)
        validate_memory_id(memory_id)
        with _exclusive_write_lock(self.root / ".ai-dememory.write.lock"):
            memory = self.get(memory_id)
            if memory is None or memory.scope != scope:
                raise VaultError("Memory not found in the requested scope")
            if memory.status == "forgotten":
                return {**memory.to_dict(), "restored_memory_id": None}
            prior = self.get(memory.supersedes) if memory.supersedes and memory.status == "active" else None
            updated = replace(memory, status="forgotten")
            self._write_memory(updated)
            if prior and prior.scope == scope and prior.status == "superseded":
                try:
                    self._write_memory(replace(prior, status="active"))
                except OSError:
                    self._write_memory(memory)
                    raise
            else:
                prior = None
            return {**updated.to_dict(), "restored_memory_id": prior.memory_id if prior else None}

    def read_memory(self, path: Path) -> Memory:
        try:
            canonical = path.resolve(strict=True)
            canonical.relative_to(self.memories_dir)
        except (OSError, ValueError) as exc:
            raise VaultError("Memory path escapes the vault memories directory") from exc
        if canonical != path.absolute() or not canonical.is_file():
            raise VaultError("Linked or non-file memory paths are not allowed")
        metadata, content = parse_markdown(path)
        raw_memory_id = metadata.get("id", "").strip()
        if not raw_memory_id:
            raise VaultError(f"Memory {path.name} requires id and title")
        memory_id = validate_memory_id(raw_memory_id)
        title = validate_title(metadata.get("title", ""), f"Memory {path.name} title")
        scope = validate_scope(metadata.get("scope", "global"))
        status = metadata.get("status", "active")
        if status not in {"active", "provisional", "superseded", "forgotten"}:
            raise VaultError(f"Memory {path.name} has invalid status")
        try:
            source = validate_source(json.loads(metadata["source"])) if "source" in metadata else {}
        except json.JSONDecodeError as exc:
            raise VaultError(f"Memory {path.name} has invalid source") from exc
        key = validate_scope(metadata["key"]) if "key" in metadata else None
        supersedes = validate_memory_id(metadata["supersedes"]) if "supersedes" in metadata else None
        return Memory(memory_id, title, content, metadata.get("created_at", ""), path,
                      scope, source, status, key, supersedes)

    def get(self, memory_id: str) -> Memory | None:
        validate_memory_id(memory_id)
        for path in self.iter_memory_paths():
            memory = self.read_memory(path)
            if memory.memory_id == memory_id:
                return memory
        return None

    def memory_count(self) -> int:
        return sum(1 for _ in self.iter_memory_paths())
