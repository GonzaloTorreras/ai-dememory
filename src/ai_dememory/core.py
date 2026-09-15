"""Stable, narrow services available to optional modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import load_config
from .proposals import MAX_PROPOSAL_FILES, ProposalStore
from .search import SearchIndex, _canonical_snippet, _TOKEN
from .vault import Vault, validate_scope


@dataclass
class CoreServices:
    """Shared local services for retrieval, evidenced learning and review."""

    vault: Vault

    def search(self, query: str, limit: int = 5, scope: str = "global") -> list[dict[str, Any]]:
        return [hit.to_dict() for hit in SearchIndex(self.vault).search(query, limit, scope)]

    def get(self, memory_id: str, max_chars: int = 20_000, scope: str = "global") -> dict[str, Any] | None:
        validate_scope(scope)
        if type(max_chars) is not int or not 256 <= max_chars <= 50_000:
            raise ValueError("max_chars must be between 256 and 50000")
        memory = self.vault.get(memory_id)
        if memory is None or memory.scope not in {"global", scope} or memory.status != "active":
            return None
        data = memory.to_dict()
        content = str(data["content"])
        data["content"] = content[:max_chars]
        data["truncated"] = len(content) > max_chars
        return data

    def context(self, query: str, limit: int = 5, max_chars: int = 4000,
                scope: str = "global") -> dict[str, Any]:
        if type(max_chars) is not int or not 256 <= max_chars <= 20_000:
            raise ValueError("max_chars must be between 256 and 20000")
        hits = SearchIndex(self.vault).search(query, limit, scope)
        text = ""
        included: list[str] = []
        sources: list[dict[str, Any]] = []
        for index, hit in enumerate(hits):
            memory = self.vault.read_memory(hit.path)
            separator = "\n\n" if text else ""
            remaining = max_chars - len(text) - len(separator)
            if remaining < 80:
                break
            budget = max(80, remaining // (len(hits) - index))
            heading = f"## {memory.title[:min(72, budget // 3)]}\n\n"
            excerpt = _canonical_snippet(memory.content, _TOKEN.findall(query),
                                         max_chars=max(1, budget - len(heading) - 4))
            text += separator + (heading + excerpt)[:remaining]
            included.append(memory.memory_id)
            sources.append({"memory_id": memory.memory_id, "scope": memory.scope, "source": memory.source})
        return {"query": query, "memory_ids": included, "sources": sources,
                "context": text[:max_chars].strip()}

    def learn(self, title: str, content: str, scope: str, source: dict[str, str], event_id: str,
              key: str | None = None, supersedes: str | None = None,
              provisional: bool = False) -> dict[str, Any]:
        return self.vault.learn(title, content, scope, source, event_id, key, supersedes, provisional)

    def forget(self, memory_id: str, scope: str = "global") -> dict[str, Any]:
        return self.vault.forget(memory_id, scope)

    def list_memories(self, scope: str = "global", limit: int = 50,
                      include_inactive: bool = False) -> list[dict[str, Any]]:
        validate_scope(scope)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not isinstance(include_inactive, bool):
            raise ValueError("include_inactive must be a boolean")
        memories = (self.vault.read_memory(path) for path in self.vault.iter_memory_paths())
        selected = [memory for memory in memories if memory.scope == scope
                    and (include_inactive or memory.status == "active")]
        selected.sort(key=lambda memory: (memory.created_at, memory.memory_id), reverse=True)
        return [memory.to_dict() for memory in selected[:limit]]

    def propose(self, title: str, content: str) -> dict[str, Any]:
        return ProposalStore(self.vault).propose(title, content).to_dict()

    def status(self) -> dict[str, Any]:
        config = load_config()
        proposals = ProposalStore(self.vault)
        return {
            "vault": str(self.vault.root),
            "name": self.vault.name,
            "memories": self.vault.memory_count(),
            "pending_proposals": proposals.count(),
            "proposal_file_limit": MAX_PROPOSAL_FILES,
            "index": SearchIndex(self.vault).status(),
            "enabled_modules": list(config.enabled_modules),
            "background_processes": 0,
            "model_calls": 0,
            "resource_scope": "core policy, not process telemetry",
        }
