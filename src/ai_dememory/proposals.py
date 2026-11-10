"""Reviewable proposal storage for AI and optional modules."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .models import Memory, Proposal
from .policy import reject_high_confidence_secrets
from .vault import (
    MAX_MEMORY_BYTES,
    Vault,
    VaultError,
    _atomic_write,
    _exclusive_write_lock,
    _slug,
    parse_markdown,
    utc_now,
    validate_memory_id,
    validate_scope,
    validate_title,
)
from .quality import evidence_revision, recall_eligible


class ProposalError(ValueError):
    pass


MAX_PROPOSAL_CONTENT_BYTES = 64_000
MAX_PROPOSAL_FILES = 1_000
MAX_PROPOSAL_SOURCES = 8
_REVISION = re.compile(r"[0-9a-f]{64}")


class ProposalStore:
    def __init__(self, vault: Vault):
        self.vault = vault

    def propose(self, title: str, content: str, *, scope: str = "global",
                source_revisions: dict[str, str] | None = None) -> Proposal:
        try:
            clean_title = validate_title(title, "Proposal title")
        except VaultError as exc:
            raise ProposalError(str(exc)) from exc
        if not isinstance(content, str):
            raise ProposalError("Proposal content must be a string")
        try:
            scope = validate_scope(scope)
            source_revisions = self._validate_source_revisions(source_revisions)
        except VaultError as exc:
            raise ProposalError(str(exc)) from exc
        clean_content = content.strip()
        if not clean_content:
            raise ProposalError("Proposal title and content are required")
        if len(clean_content.encode("utf-8")) > MAX_PROPOSAL_CONTENT_BYTES:
            raise ProposalError(
                f"Proposal exceeds the {MAX_PROPOSAL_CONTENT_BYTES}-byte content limit"
            )
        if len(self._paths()) >= MAX_PROPOSAL_FILES:
            raise ProposalError(
                f"Proposal store reached its {MAX_PROPOSAL_FILES}-file limit; "
                "remove reviewed proposal files before adding more"
            )
        reject_high_confidence_secrets(clean_title + "\n" + clean_content)
        proposal_id = uuid.uuid4().hex
        created_at = utc_now()
        path = self.vault.proposals_dir / f"{created_at[:10]}-{_slug(clean_title)}-{proposal_id[:8]}.md"
        proposal = Proposal(proposal_id, clean_title, clean_content, "pending", created_at, path,
                            scope, source_revisions)
        self._write(proposal)
        return proposal

    @staticmethod
    def _validate_source_revisions(value: dict[str, str] | None) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict) or len(value) > MAX_PROPOSAL_SOURCES:
            raise ProposalError(f"Proposal may reference at most {MAX_PROPOSAL_SOURCES} source memories")
        clean: dict[str, str] = {}
        for memory_id, revision in value.items():
            validate_memory_id(memory_id)
            if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
                raise ProposalError("Proposal source revisions must be SHA-256 hex digests")
            clean[memory_id] = revision
        return clean

    def _write(self, proposal: Proposal, decided_at: str | None = None) -> None:
        lines = [
            "---",
            f"id: {json.dumps(proposal.proposal_id)}",
            f"title: {json.dumps(proposal.title)}",
            f"status: {json.dumps(proposal.status)}",
            f"created_at: {json.dumps(proposal.created_at)}",
            f"scope: {json.dumps(proposal.scope)}",
            f"source_revisions: {json.dumps(proposal.source_revisions, sort_keys=True)}",
        ]
        if decided_at:
            lines.append(f"decided_at: {json.dumps(decided_at)}")
        lines.extend(("---", "", proposal.content, ""))
        payload = "\n".join(lines)
        if len(payload.encode("utf-8")) > MAX_MEMORY_BYTES:
            raise ProposalError(f"Serialized proposal exceeds the {MAX_MEMORY_BYTES}-byte limit")
        _atomic_write(proposal.path, payload)

    def _read(self, path: Path) -> Proposal:
        try:
            metadata, content = parse_markdown(path)
            title = validate_title(metadata.get("title", ""), f"Proposal {path.name} title")
            scope = validate_scope(metadata.get("scope", "global"))
            source_revisions = self._validate_source_revisions(
                json.loads(metadata.get("source_revisions", "{}"))
            )
        except (VaultError, ValueError, TypeError) as exc:
            raise ProposalError(str(exc)) from exc
        required = ("id", "title", "status", "created_at")
        if any(not metadata.get(key, "").strip() for key in required):
            raise ProposalError(f"Proposal {path.name} has incomplete metadata")
        if len(content.encode("utf-8")) > MAX_PROPOSAL_CONTENT_BYTES:
            raise ProposalError(
                f"Proposal {path.name} exceeds the {MAX_PROPOSAL_CONTENT_BYTES}-byte content limit"
            )
        return Proposal(metadata["id"], title, content, metadata["status"], metadata["created_at"],
                        path, scope, source_revisions)

    def _paths(self) -> list[Path]:
        paths = [
            path
            for path in self.vault.proposals_dir.glob("*.md")
            if path.is_file() and not path.is_symlink()
        ]
        if len(paths) > MAX_PROPOSAL_FILES:
            raise ProposalError(f"Proposal store exceeds its {MAX_PROPOSAL_FILES}-file limit")
        return sorted(paths, reverse=True)

    def list(self, status: str | None = "pending", limit: int | None = None) -> list[Proposal]:
        if limit is not None and not 1 <= limit <= 100:
            raise ProposalError("Proposal list limit must be between 1 and 100")
        proposals: list[Proposal] = []
        for path in self._paths():
            proposal = self._read(path)
            if status is None or proposal.status == status:
                proposals.append(proposal)
                if limit is not None and len(proposals) >= limit:
                    break
        return proposals

    def count(self, status: str = "pending") -> int:
        return sum(1 for path in self._paths() if self._read(path).status == status)

    def get(self, proposal_id: str) -> Proposal | None:
        matches: list[Proposal] = []
        for path in self._paths():
            proposal = self._read(path)
            if proposal.proposal_id == proposal_id:
                return proposal
            if proposal.proposal_id.startswith(proposal_id):
                matches.append(proposal)
                if len(matches) > 1:
                    raise ProposalError(f"Ambiguous proposal id prefix: {proposal_id}")
        if len(matches) > 1:
            raise ProposalError(f"Ambiguous proposal id prefix: {proposal_id}")
        return matches[0] if matches else None

    def decide(self, proposal_id: str, accept: bool) -> tuple[Proposal, Memory | None]:
        with _exclusive_write_lock(self.vault.root / ".ai-dememory.proposals.lock"):
            if accept:
                with _exclusive_write_lock(self.vault.root / ".ai-dememory.write.lock"):
                    return self._decide(proposal_id, accept)
            return self._decide(proposal_id, accept)

    def _decide(self, proposal_id: str, accept: bool) -> tuple[Proposal, Memory | None]:
        proposal = self.get(proposal_id)
        if proposal is None:
            raise ProposalError(f"Proposal not found: {proposal_id}")
        if proposal.status != "pending":
            raise ProposalError(f"Proposal is already {proposal.status}")
        memory = None
        if accept:
            if not self._sources_are_fresh(proposal):
                raise ProposalError("Proposal source inputs are stale; create a new proposal")
            deterministic_id = uuid.uuid5(
                uuid.NAMESPACE_URL, f"ai-dememory:proposal:{proposal.proposal_id}"
            ).hex
            memory = self.vault._remember(proposal.content, proposal.title,
                                          memory_id=deterministic_id, scope=proposal.scope)
        updated = Proposal(
            proposal.proposal_id,
            proposal.title,
            proposal.content,
            "accepted" if accept else "rejected",
            proposal.created_at,
            proposal.path,
            proposal.scope,
            proposal.source_revisions,
        )
        self._write(updated, decided_at=utc_now())
        return updated, memory

    def _sources_are_fresh(self, proposal: Proposal) -> bool:
        for memory_id, revision in proposal.source_revisions.items():
            memory = self.vault.get(memory_id)
            if (memory is None or memory.scope != proposal.scope or not recall_eligible(memory)
                    or evidence_revision(memory.title, memory.content, memory.source) != revision):
                return False
        return True
