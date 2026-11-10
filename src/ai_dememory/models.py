"""Public data structures shared by the core and optional modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Memory:
    memory_id: str
    title: str
    content: str
    created_at: str
    path: Path
    scope: str = "global"
    source: dict[str, str] = field(default_factory=dict)
    status: str = "active"
    key: str | None = None
    supersedes: str | None = None
    importance: str = "normal"
    importance_origin: str = "default"
    confidence: dict[str, Any] = field(default_factory=dict)
    memory_kind: str = "unspecified"
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        from .quality import confidence_status
        data["confidence_status"] = confidence_status(self)
        return data


@dataclass(frozen=True)
class SearchHit:
    memory_id: str
    title: str
    snippet: str
    score: float
    path: Path
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    title: str
    content: str
    status: str
    created_at: str
    path: Path
    scope: str = "global"
    source_revisions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class ModuleManifest:
    """The intentionally small contract implemented by optional modules."""

    module_id: str
    version: str
    summary: str
    capabilities: tuple[str, ...] = ()
    resource_budget: dict[str, int | bool | str] = field(default_factory=dict)
