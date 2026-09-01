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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class SearchHit:
    memory_id: str
    title: str
    snippet: str
    score: float
    path: Path

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
