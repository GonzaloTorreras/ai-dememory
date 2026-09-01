"""Canonical Markdown vault operations."""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import Memory
from .policy import reject_high_confidence_secrets


class VaultError(ValueError):
    pass


MAX_MEMORY_BYTES = 2_000_000
MAX_MEMORY_CONTENT_BYTES = 1_900_000
MAX_MEMORY_FILES = 10_000
MAX_TITLE_BYTES = 512
MAX_METADATA_VALUE_BYTES = 1_024


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


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:48] or "memory").strip("-")


def _default_title(content: str) -> str:
    first = next((line.strip() for line in content.splitlines() if line.strip()), "Memory")
    return first[:72]


def validate_title(value: str, subject: str) -> str:
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
        self, content: str, title: str | None = None, *, memory_id: str | None = None
    ) -> Memory:
        clean_content = content.strip()
        if not clean_content:
            raise VaultError("Memory content cannot be empty")
        if len(clean_content.encode("utf-8")) > MAX_MEMORY_CONTENT_BYTES:
            raise VaultError(f"Memory exceeds the {MAX_MEMORY_CONTENT_BYTES}-byte content limit")
        reject_high_confidence_secrets(clean_content)
        clean_title = validate_title(title or _default_title(clean_content), "Memory title")
        reject_high_confidence_secrets(clean_title)
        memory_id = memory_id or uuid.uuid4().hex
        existing = self.get(memory_id)
        if existing:
            if existing.title == clean_title and existing.content == clean_content:
                return existing
            raise VaultError(f"Memory id already exists with different content: {memory_id}")
        created_at = utc_now()
        filename = f"{created_at[:10]}-{_slug(clean_title)}-{memory_id[:8]}.md"
        path = self.memories_dir / filename
        payload = "\n".join(
            (
                "---",
                f"id: {json.dumps(memory_id)}",
                f"title: {json.dumps(clean_title)}",
                f"created_at: {json.dumps(created_at)}",
                "---",
                "",
                clean_content,
                "",
            )
        )
        _atomic_write(path, payload)
        return Memory(memory_id, clean_title, clean_content, created_at, path)

    def read_memory(self, path: Path) -> Memory:
        metadata, content = parse_markdown(path)
        memory_id = metadata.get("id", "").strip()
        if not memory_id:
            raise VaultError(f"Memory {path.name} requires id and title")
        title = validate_title(metadata.get("title", ""), f"Memory {path.name} title")
        return Memory(memory_id, title, content, metadata.get("created_at", ""), path)

    def get(self, memory_id: str) -> Memory | None:
        for path in self.iter_memory_paths():
            memory = self.read_memory(path)
            if memory.memory_id == memory_id:
                return memory
        return None

    def memory_count(self) -> int:
        return sum(1 for _ in self.iter_memory_paths())
