"""Stable, narrow services available to optional modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import load_config
from .proposals import MAX_PROPOSAL_FILES, ProposalStore
from .search import SearchIndex
from .vault import Vault


@dataclass
class CoreServices:
    """Supported module surface omits canonical writes; trusted Python is not confined."""

    vault: Vault

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [hit.to_dict() for hit in SearchIndex(self.vault).search(query, limit)]

    def get(self, memory_id: str, max_chars: int = 20_000) -> dict[str, Any] | None:
        if not 256 <= max_chars <= 50_000:
            raise ValueError("max_chars must be between 256 and 50000")
        memory = self.vault.get(memory_id)
        if memory is None:
            return None
        data = memory.to_dict()
        content = str(data["content"])
        data["content"] = content[:max_chars]
        data["truncated"] = len(content) > max_chars
        return data

    def context(self, query: str, limit: int = 5, max_chars: int = 4000) -> dict[str, Any]:
        if not 256 <= max_chars <= 20_000:
            raise ValueError("max_chars must be between 256 and 20000")
        hits = SearchIndex(self.vault).search(query, limit)
        text = ""
        included: list[str] = []
        for hit in hits:
            memory = self.vault.get(hit.memory_id)
            if memory is None:
                continue
            block = f"## {memory.title}\n\n{memory.content}\n"
            separator = "\n\n" if text else ""
            remaining = max_chars - len(text) - len(separator)
            if remaining <= 0:
                break
            text += separator + block[:remaining]
            included.append(memory.memory_id)
        return {"query": query, "memory_ids": included, "context": text[:max_chars].strip()}

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
        }
