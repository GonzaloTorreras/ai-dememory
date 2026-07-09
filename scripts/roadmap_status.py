#!/usr/bin/env python3
"""Report implementation status for the v2 operational memory roadmap."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from memorylib import repo_root


@dataclass(frozen=True)
class RoadmapPhaseSpec:
    phase: int
    title: str
    intent: str
    evidence_paths: tuple[str, ...]
    status_when_present: str = "implemented"
    next_action: str = "Keep covered by release checks and focused regression tests."


@dataclass(frozen=True)
class RoadmapPhaseStatus:
    phase: int
    title: str
    status: str
    intent: str
    evidence_paths: list[str]
    missing_evidence: list[str]
    next_action: str


PHASES: tuple[RoadmapPhaseSpec, ...] = (
    RoadmapPhaseSpec(
        phase=0,
        title="Stabilize current v2 baseline",
        intent="Keep release gates, CI, smoke tests, and release handoff evidence current.",
        evidence_paths=(
            "scripts/release_check.py",
            "scripts/ci_guard.py",
            "scripts/mcp_runtime_smoke.py",
            "scripts/install_smoke.py",
            "docs/release-v2-checklist.md",
            ".github/workflows/ci.yml",
        ),
    ),
    RoadmapPhaseSpec(
        phase=1,
        title="Token-budgeted context and explainable search",
        intent="Assemble bounded startup context and explain why memories ranked.",
        evidence_paths=(
            "scripts/context_memory.py",
            "scripts/search_memory.py",
            "docs/operational-loop.md",
            "docs/adr/0059-search-match-explanations.md",
            "docs/adr/0063-mcp-auto-context.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=2,
        title="Working memory and handoffs",
        intent="Capture generated task state and session handoffs without mutating canonical memory.",
        evidence_paths=(
            "scripts/working_memory.py",
            "vault-template/working/README.md",
            "vault-template/working/handoffs/README.md",
            "docs/adr/0038-mcp-working-memory-tools.md",
            "docs/adr/0060-working-status-summary.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=3,
        title="Lifecycle scoring and outcomes",
        intent="Record retrieval/usefulness feedback and expose generated lifecycle scores.",
        evidence_paths=(
            "scripts/lifecycle.py",
            "docs/adr/0003-lifecycle-scoring.md",
            "docs/adr/0061-lifecycle-feedback-receipts.md",
            "docs/adr/0062-outcome-feedback-receipts.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=4,
        title="False-positive review and conflict detection",
        intent="Make false-positive suppressions and memory conflicts deterministic review objects.",
        evidence_paths=(
            "scripts/review_memory.py",
            "docs/review-workflows.md",
            "docs/adr/0001-review-and-conflict-workflows.md",
            "docs/adr/0064-mcp-conflict-keep-resolution.md",
            "docs/adr/0065-mcp-false-positive-ignore-receipts.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=5,
        title="Configurable LLM-assisted cleanup",
        intent="Expose strict, balanced, assisted, and autonomous proposal review modes with audit artifacts.",
        evidence_paths=(
            "docs/adr/0002-configurable-review-modes.md",
            "docs/adr/0027-canonical-review-mode-names.md",
            "docs/adr/0082-mcp-review-mode-configuration.md",
            "docs/adr/0086-plugin-review-receipt-tools.md",
            "vault-template/.ai-dememory.toml",
        ),
    ),
    RoadmapPhaseSpec(
        phase=6,
        title="Safe sleep consolidation",
        intent="Generate sleep/consolidation plans and reviewed packets without rewriting canonical memory.",
        evidence_paths=(
            "scripts/sleep_consolidation.py",
            "docs/sleep-consolidation.md",
            "docs/adr/0004-safe-sleep-consolidation.md",
            "docs/adr/0225-sleep-dry-run-propose-aliases.md",
            "docs/adr/0226-sleep-apply-reviewed-alias.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=7,
        title="Codex and Claude hooks",
        intent="Generate hook configuration and review-first hook capture workflows for supported clients.",
        evidence_paths=(
            "scripts/hook_event.py",
            "docs/hooks.md",
            "plugins/ai-dememory/hooks/hooks.json",
            "docs/adr/0005-hook-provider-config.md",
            "docs/adr/0006-managed-hook-instruction-blocks.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=8,
        title="Importers and capture",
        intent="Capture provider chats and explicit files/text into review inboxes only.",
        evidence_paths=(
            "scripts/provider_import.py",
            "docs/import-capture.md",
            "vault-template/inbox/imports/README.md",
            "docs/adr/0007-import-capture-review-candidates.md",
            "docs/adr/0137-provider-import-dry-run.md",
            "docs/adr/0138-provider-import-idempotency.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=9,
        title="Git lesson capture",
        intent="Extract review-first project lesson candidates from git history.",
        evidence_paths=(
            "scripts/git_lessons.py",
            "docs/git-lessons.md",
            "docs/adr/0008-git-lesson-capture.md",
            "docs/adr/0139-mcp-git-lessons.md",
            "docs/adr/0140-git-lesson-idempotency.md",
        ),
    ),
    RoadmapPhaseSpec(
        phase=10,
        title="Optional vector search",
        intent="Keep embeddings disabled until measured recall failures justify a reviewed experiment.",
        evidence_paths=(
            "scripts/vector_gate.py",
            "docs/vector-migration.md",
            "docs/adr/0009-measured-vector-search-gate.md",
            "docs/adr/0184-release-evidence-vector-readiness.md",
            "quality/recall-fixtures.json",
        ),
        status_when_present="gated",
        next_action="Run `ai-dememory vector status` and approve an experiment only after reviewed recall failures justify it.",
    ),
)


def roadmap_status(root: Path) -> dict[str, object]:
    phases = [phase_status(root, spec) for spec in PHASES]
    counts: dict[str, int] = {}
    for phase in phases:
        counts[phase.status] = counts.get(phase.status, 0) + 1
    return {
        "root": str(root),
        "mutates_files": False,
        "writes_files": False,
        "phase_count": len(phases),
        "status_counts": counts,
        "phases": [asdict(phase) for phase in phases],
        "next_actions": next_actions(phases),
    }


def phase_status(root: Path, spec: RoadmapPhaseSpec) -> RoadmapPhaseStatus:
    missing = [path for path in spec.evidence_paths if not (root / path).exists()]
    status = "missing_evidence" if missing else spec.status_when_present
    next_action = f"Add or restore evidence: {', '.join(missing)}." if missing else spec.next_action
    return RoadmapPhaseStatus(
        phase=spec.phase,
        title=spec.title,
        status=status,
        intent=spec.intent,
        evidence_paths=list(spec.evidence_paths),
        missing_evidence=missing,
        next_action=next_action,
    )


def next_actions(phases: list[RoadmapPhaseStatus]) -> list[str]:
    actions: list[str] = []
    missing = [phase for phase in phases if phase.status == "missing_evidence"]
    if missing:
        actions.append("Restore missing roadmap evidence before claiming the v2 operational loop is implemented.")
    gated = [phase for phase in phases if phase.status == "gated"]
    if gated:
        actions.append("Keep gated phases disabled until their review evidence explicitly approves activation.")
    actions.append("Keep manual acceptance and recall fixture freshness as release blockers until reviewed evidence exists.")
    return actions


def render_markdown(payload: dict[str, object]) -> str:
    phases = payload["phases"]
    assert isinstance(phases, list)
    lines = [
        "# v2 Roadmap Status",
        "",
        f"- phases: `{payload['phase_count']}`",
        f"- mutates_files: `{str(payload['mutates_files']).lower()}`",
        f"- writes_files: `{str(payload['writes_files']).lower()}`",
        "",
        "## Phases",
        "",
    ]
    for item in phases:
        assert isinstance(item, dict)
        lines.extend(
            [
                f"### Phase {item['phase']}: {item['title']}",
                "",
                f"- status: `{item['status']}`",
                f"- intent: {item['intent']}",
                f"- next_action: {item['next_action']}",
                "- evidence:",
            ]
        )
        for path in item["evidence_paths"]:
            lines.append(f"  - `{path}`")
        missing = item["missing_evidence"]
        if missing:
            lines.append("- missing_evidence:")
            for path in missing:
                lines.append(f"  - `{path}`")
        lines.append("")
    lines.extend(["## Next Actions", ""])
    for action in payload["next_actions"]:
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    subparsers = parser.add_subparsers(dest="command")
    status = subparsers.add_parser("status", help="Report roadmap implementation status.")
    status.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    if args.command not in {None, "status"}:
        parser.error(f"unknown roadmap command: {args.command}")
    root = repo_root(getattr(args, "root", None))
    payload = roadmap_status(root)
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 1 if payload["status_counts"].get("missing_evidence") else 0


if __name__ == "__main__":
    raise SystemExit(main())
