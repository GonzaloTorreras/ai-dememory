# ADR 0059: Search Match Explanations

Status: Accepted for the v2 draft.

## Context

Phase 1 of the v2 memory plan requires token-budgeted context and explainable
search. `ai-dememory search --why` already reported numeric ranking
components, including FTS score, tag overlap, alias match, recency, confidence,
type boost, pin boost, lifecycle strength, and penalties.

Those numbers explain how the score was assembled, but not which indexed text
caused a result to match the query. That makes recall misses and unexpected
hits harder to review because a user has to open each memory to determine
whether the title, tags, aliases, summary, or body caused the match.

## Decision

Add matched evidence fields to every search result `why` object:

- `matched_terms`
- `matched_fields`
- `matched_tags`
- `matched_aliases`

The same `SearchResult` object is used by:

- `ai-dememory search --why`
- `ai-dememory search --json`
- MCP `memory.search`
- `ai-dememory context` item metadata
- MCP `memory.context`

The numeric scoring components remain unchanged. The new fields are additive
metadata for review and debugging.

## Benefits

- Makes search explanations actionable without opening every candidate memory.
- Helps reviewers decide whether a recall miss needs better memory text,
  aliases, tags, or future retrieval changes.
- Keeps MCP clients and context assembly aligned with the CLI search surface.

## Limitations

- Matched fields are derived from local tokenization and indexed text; they are
  not semantic explanations.
- FTS ranking can still match differently from the simplified matched-field
  display in edge cases.
- The field list does not expose private or sensitive memories unless the
  caller explicitly opts into sensitive search.

## Future Risks

- If vector search is added later, vector explanations need their own evidence
  fields rather than reusing FTS-only match metadata.
- If the tokenizer changes, tests and recall-review documentation should be
  updated to keep explanations understandable.

## Dependencies

- ADR 0003 defines lifecycle scoring as a small explainable ranking component.
- ADR 0036 keeps vector search deferred until recall fixtures justify it.
- `scripts/search_memory.py` remains the source of truth for local ranking and
  explanation metadata.
