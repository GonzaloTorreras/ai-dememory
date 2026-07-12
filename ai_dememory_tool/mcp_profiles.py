"""Named MCP tool allowlists for client configuration.

The server keeps the complete tool surface for backwards compatibility.  These
profiles only control what a supporting client advertises to a model.
"""

from __future__ import annotations

from collections.abc import Iterable


CORE_MCP_TOOLS = (
    "memory.search",
    "memory.get",
    "memory.context",
    "memory.graph",
    "memory.doctor",
    "memory.working_current",
    "memory.working_status",
)

WORKING_MCP_TOOLS = CORE_MCP_TOOLS + (
    "memory.working_snapshot",
    "memory.working_handoff",
    "memory.mark_seen",
    "memory.capture_miss",
    "memory.outcome",
)

REVIEW_MCP_TOOLS = WORKING_MCP_TOOLS + (
    "memory.write_proposal",
    "memory.validate_status",
    "memory.recall_miss_candidate",
    "memory.recall_fixture_status",
    "memory.recall_review_plan",
    "memory.recall_review_packet",
    "memory.recall_review_packet_archive_status",
    "memory.recall_review_packet_archive_retention_plan",
    "memory.recall_miss_review",
    "memory.provenance_status",
    "memory.hook_status",
    "memory.hook_events",
    "memory.hook_capture_review",
    "memory.capture_import",
    "memory.git_lessons",
    "memory.review_false_positives",
    "memory.review_stale_false_positives",
    "memory.review_conflicts",
    "memory.false_positive_ignore",
    "memory.false_positive_unignore",
    "memory.conflict_dismiss",
    "memory.conflict_keep",
    "memory.conflict_merge_proposal",
    "memory.review_modes",
    "memory.review_configure_mode",
    "memory.review_plan",
    "memory.review_recommendation",
    "memory.review_recommendations",
    "memory.review_recommendation_archive_status",
    "memory.review_recommendation_archive_restore_preview",
    "memory.review_recommendation_outcome_report",
    "memory.review_recommendation_outcome",
)

MCP_PROFILE_NAMES = ("core", "working", "review", "admin")
MCP_TOOL_PROFILES = {
    "core": CORE_MCP_TOOLS,
    "working": WORKING_MCP_TOOLS,
    "review": REVIEW_MCP_TOOLS,
}


def enabled_tools_for_profile(profile: str, all_tools: Iterable[str] | None = None) -> tuple[str, ...] | None:
    """Return a profile allowlist; ``admin`` deliberately means no filter.

    Supplying ``all_tools`` makes the admin profile explicit for inventory and
    metrics without making generated client configs repeat the complete schema.
    """

    if profile not in MCP_PROFILE_NAMES:
        raise ValueError(f"unknown MCP tool profile: {profile}")
    if profile == "admin":
        return tuple(all_tools) if all_tools is not None else None
    return MCP_TOOL_PROFILES[profile]
