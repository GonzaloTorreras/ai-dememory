---
name: memory-review-inbox
description: Review ai-dememory inbox proposals, provider imports, explicit captures, hook captures, recall misses, false positives, and conflict candidates. Use when the user wants to promote, reject, clean, consolidate, dismiss, or write conflict merge proposals.
---

# Memory Review Inbox

MCP review operations require the opt-in `review` profile. The default `core`
profile intentionally omits these schemas; use the equivalent explicit CLI
workflow when the client cannot select a broader profile.

Review-first rules:

1. Run `ai-dememory secret-scan` before promoting anything from `inbox/`.
2. Treat `inbox/imports/` provider and explicit capture output,
   `inbox/git-lessons/`, `inbox/session-events/`, `inbox/llm-captures/`,
   `inbox/recall-feedback/`, `inbox/review-recommendations/`, and
   `inbox/conflict-resolution/` as
   candidate-only areas.
3. Rewrite approved facts into canonical memory frontmatter.
4. Durable memory requires `reviewed: true`, `reviewed_by`, and `reviewed_at`.
5. Leave rejected or unclear candidates in inbox with a note, or remove them
   only when the user asks.
6. Use `memory.review_modes` and `memory.review_plan` to inspect the active
   policy before LLM-assisted review. Use `memory.review_configure_mode` only
   when the user explicitly asks to change the local review policy.
   Use `memory.review_recommendation` to store advisory recommendations for
   audit only; it does not apply suppressions, conflict decisions, promotions,
   or canonical memory edits.
   Use `memory.review_recommendations` to inspect pending recommendation
   artifacts and malformed recommendation files without writing files.
   Use `memory.review_recommendation_archive_status` to inspect archived
   accepted/rejected recommendation artifacts without moving files; set `limit`
   and `offset` for paging, and `recursive=true` for date or project archive
   partitions.
   Use `memory.review_recommendation_archive_restore_preview` to inspect whether
   one archived recommendation can be reopened without moving files; set
   `recursive=true` for partitioned archives.
   Use `memory.review_recommendation_outcome` to mark a recommendation artifact
   accepted or rejected without applying the recommendation.
7. Use `memory.review_false_positives` before suppressing scanner findings.
   Use `memory.review_stale_false_positives` to audit suppressions whose
   scanner finding no longer exists. Use `memory.false_positive_ignore` and
   `memory.false_positive_unignore` only after a reviewed false-positive
   decision.
8. Use `memory.review_conflicts` before resolving a conflict. Use
   `memory.conflict_dismiss` only for reviewed dismissals,
   `memory.conflict_keep` only for reviewed keep decisions, and
   `memory.conflict_merge_proposal` only to create a review candidate that must
   not be treated as canonical memory.
9. Use `memory.recall_miss_candidate` before writing recall feedback when you
   need to verify rank evidence. Use `memory.recall_review_plan` before closing
   recall misses. Use `memory.recall_miss_review` only for reviewed `rejected`
   or `dismissed` outcomes. It must not be used to promote fixtures or
   canonical memory.
10. Use `memory.hook_capture_review` only after human approval to close a
    selected `inbox/session-events/` hook capture with reviewer metadata. It
    must not be used to promote durable memory or delete the capture.
11. Use `ai-dememory hooks archive --json` to preview moving resolved hook
    captures to `archive/session-events/`; run it with `--apply` only when the
    user approves the archival preview.

Canonical modes are `strict`, `balanced`, `assisted`, and
`autonomous_proposals`. Treat `autonomous_proposals` as inbox-only automation;
it does not permit canonical or durable memory writes without human review.

Never copy credential material into canonical memory.
