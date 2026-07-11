#!/usr/bin/env python3
"""Assemble token-budgeted memory context for an agent session."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any

from config_file import load_config
from index_memory import default_db_path
from memorylib import (
    MemoryDocument,
    MemoryError,
    discover_memory_files,
    extract_summary,
    is_memory_file,
    load_memory,
    repo_relative_path,
    repo_root,
)
from search_memory import result_to_dict, search, tokenize
from secret_scan import scan_text


DEFAULT_BUDGET_TOKENS = 2000
DEFAULT_BASELINE_BUDGET_TOKENS = 480


@dataclass(frozen=True)
class ContextDefaults:
    budget_tokens: int
    include_working_memory: bool
    explain_results: bool


@dataclass(frozen=True)
class ContextItem:
    id: str
    title: str
    path: str
    score: float
    estimated_tokens: int
    why: dict[str, Any]
    excerpt: str


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def assemble_context(
    root: Path,
    query: str,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    limit: int = 20,
    include_sensitive: bool = False,
    include_working_memory: bool = True,
    explain_results: bool = False,
    query_source: str = "explicit",
    project_hint: str | None = None,
    include_reviewed_durable: bool = False,
    baseline_budget_tokens: int = DEFAULT_BASELINE_BUDGET_TOKENS,
    require_reviewed_results: bool = False,
    min_relevance_score: float | None = None,
) -> dict[str, Any]:
    if budget_tokens < 200:
        raise ValueError("budget_tokens must be at least 200")
    if baseline_budget_tokens < 0:
        raise ValueError("baseline_budget_tokens cannot be negative")
    results = search(
        query,
        root,
        limit=limit,
        include_sensitive=include_sensitive,
        project_hint=project_hint,
    )
    remaining = budget_tokens
    items: list[ContextItem] = []
    sections: list[str] = []
    selected_ids: set[str] = set()
    degradation: list[str] = []
    security_filtered_items = 0
    relevant_result_ids = {
        result.id
        for result in results
        if min_relevance_score is None or result.score >= min_relevance_score
    }

    if include_working_memory:
        working = working_context(root)
        if working:
            tokens = estimate_tokens(working)
            if tokens <= remaining:
                sections.append("## Working Memory\n\n" + working)
                remaining -= tokens

    if include_reviewed_durable:
        durable_documents, durable_errors = reviewed_durable_documents(root, project_hint)
        degradation.extend(durable_errors)
        baseline_remaining = min(remaining, baseline_budget_tokens)
        for document in durable_documents:
            data = document.frontmatter
            if str(data.get("id")) not in relevant_result_ids:
                continue
            excerpt = extract_summary(document.content, max_chars=650)
            path = repo_relative_path(document.path, root)
            why = {
                "baseline": "reviewed_durable",
                "project_hint": project_hint,
                "project_match": 1.0 if same_project(data.get("project"), project_hint) else 0.0,
            }
            section = render_item(str(data["id"]), str(data["title"]), path, 1.0, excerpt, why, explain_results)
            tokens = estimate_tokens(section)
            if tokens > remaining or tokens > baseline_remaining:
                continue
            if scan_text(section, f"<context:{data['id']}>"):
                security_filtered_items += 1
                continue
            sections.append(section)
            remaining -= tokens
            baseline_remaining -= tokens
            selected_ids.add(str(data["id"]))
            items.append(
                ContextItem(
                    id=str(data["id"]),
                    title=str(data["title"]),
                    path=path,
                    score=1.0,
                    estimated_tokens=tokens,
                    why=why,
                    excerpt=excerpt,
                )
            )

    for result in results:
        if min_relevance_score is not None and result.score < min_relevance_score:
            continue
        if result.id in selected_ids:
            continue
        path = safe_memory_path(root, result.path)
        if path is None:
            degradation.append(f"invalid_memory_path:{result.id}")
            continue
        try:
            document = load_memory(path)
        except (MemoryError, OSError, UnicodeError):
            degradation.append(f"invalid_memory_payload:{result.id}")
            continue
        if require_reviewed_results and not auto_injectable(document):
            degradation.append(f"untrusted_memory_filtered:{result.id}")
            continue
        canonical_id = str(document.frontmatter.get("id", ""))
        if result.id != canonical_id:
            degradation.append(f"index_identity_mismatch:{result.id}")
            continue
        canonical_title = str(document.frontmatter.get("title", canonical_id))
        canonical_path = repo_relative_path(document.path, root)
        canonical_why = canonical_selection_evidence(document, query, result.score, project_hint)
        excerpt = extract_summary(document.content, max_chars=900)
        section = render_item(
            canonical_id,
            canonical_title,
            canonical_path,
            result.score,
            excerpt,
            canonical_why,
            explain_results,
        )
        tokens = estimate_tokens(section)
        if tokens > remaining:
            continue
        findings = scan_text(section, f"<context:{canonical_id}>")
        if findings:
            security_filtered_items += 1
            continue
        sections.append(section)
        remaining -= tokens
        items.append(
            ContextItem(
                id=canonical_id,
                title=canonical_title,
                path=canonical_path,
                score=result.score,
                estimated_tokens=tokens,
                why=canonical_why,
                excerpt=excerpt,
            )
        )

    text = "# Memory Context\n\n" + "\n\n".join(sections) if sections else "# Memory Context\n\n_No matching memory context._\n"
    return {
        "query": query,
        "query_source": query_source,
        "budget_tokens": budget_tokens,
        "estimated_tokens": estimate_tokens(text),
        "remaining_tokens": max(0, remaining),
        "explain_results": explain_results,
        "project_hint": project_hint,
        "degradation": unique_strings(degradation),
        "security_filtered_items": security_filtered_items,
        "items": [asdict(item) for item in items],
        "text": text,
    }


def reviewed_durable_documents(root: Path, project_hint: str | None) -> tuple[list[MemoryDocument], list[str]]:
    documents: list[MemoryDocument] = []
    errors: list[str] = []
    for path in discover_memory_files(root):
        try:
            document = load_memory(path)
        except (MemoryError, OSError, UnicodeError):
            errors.append(f"invalid_memory_payload:{repo_relative_path(path, root)}")
            continue
        data = document.frontmatter
        if data.get("type") != "durable" or data.get("reviewed") is not True:
            continue
        if data.get("status") != "active":
            continue
        if data.get("sensitivity") not in {"public", "internal"}:
            continue
        tags = data.get("tags") if isinstance(data.get("tags"), list) else []
        normalized_tags = {str(tag).casefold() for tag in tags}
        if "baseline" not in normalized_tags and "onboarding" not in normalized_tags:
            continue
        project = data.get("project")
        if project is not None and not same_project(project, project_hint):
            continue
        documents.append(document)
    documents.sort(
        key=lambda document: (
            not bool(document.frontmatter.get("pin")),
            document.frontmatter.get("project") is None,
            str(document.frontmatter.get("id", "")),
        )
    )
    return documents, errors


def auto_injectable(document: MemoryDocument) -> bool:
    data = document.frontmatter
    return (
        data.get("reviewed") is True
        and data.get("status") == "active"
        and data.get("sensitivity") in {"public", "internal"}
    )


def canonical_selection_evidence(
    document: MemoryDocument,
    query: str,
    score: float,
    project_hint: str | None,
) -> dict[str, Any]:
    """Rebuild rendered selection metadata from canonical Markdown.

    SQLite is disposable and may be stale. It can choose and score a candidate,
    but no index-controlled identity or descriptive metadata is injected into
    model context.
    """
    data = document.frontmatter
    query_terms = tokenize(query)
    content_terms = set(tokenize(document.content))
    title_terms = set(tokenize(str(data.get("title", ""))))
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    aliases = data.get("aliases") if isinstance(data.get("aliases"), list) else []
    tag_terms = set(tokenize(" ".join(str(value) for value in tags)))
    alias_terms = set(tokenize(" ".join(str(value) for value in aliases)))
    canonical_terms = content_terms | title_terms | tag_terms | alias_terms
    matched_terms = [term for term in query_terms if term in canonical_terms]
    matched_fields: list[str] = []
    if any(term in title_terms for term in query_terms):
        matched_fields.append("title")
    if any(term in content_terms for term in query_terms):
        matched_fields.append("content")
    if any(term in tag_terms for term in query_terms):
        matched_fields.append("tags")
    if any(term in alias_terms for term in query_terms):
        matched_fields.append("aliases")
    return {
        "ranking_score": score,
        "project_hint": project_hint,
        "project_match": 1.0 if same_project(data.get("project"), project_hint) else 0.0,
        "matched_terms": matched_terms,
        "matched_fields": matched_fields,
        "matched_tags": [str(value) for value in tags if set(tokenize(str(value))) & set(query_terms)],
        "matched_aliases": [str(value) for value in aliases if set(tokenize(str(value))) & set(query_terms)],
    }


def safe_memory_path(root: Path, relative_path: str) -> Path | None:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path if is_memory_file(path, root) else None


def same_project(project: Any, project_hint: str | None) -> bool:
    if not isinstance(project, str) or not project_hint:
        return False
    return tokenize(project) == tokenize(project_hint)


def unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def context_defaults(root: Path) -> ContextDefaults:
    config = load_config(root)
    context = config.get("context", {})
    return ContextDefaults(
        budget_tokens=config_int(context.get("default_budget_tokens"), DEFAULT_BUDGET_TOKENS, minimum=200, maximum=20000),
        include_working_memory=config_bool(context.get("include_working_memory"), True),
        explain_results=config_bool(context.get("explain_results"), False),
    )


def context_defaults_status(root: Path) -> dict[str, Any]:
    config = load_config(root)
    context = config.get("context", {})
    budget_value, budget_source = config_int_status(
        context.get("default_budget_tokens"),
        DEFAULT_BUDGET_TOKENS,
        minimum=200,
        maximum=20000,
    )
    working_value, working_source = config_bool_status(context.get("include_working_memory"), True)
    explain_value, explain_source = config_bool_status(context.get("explain_results"), False)
    settings = {
        "default_budget_tokens": {"value": budget_value, "source": budget_source},
        "include_working_memory": {"value": working_value, "source": working_source},
        "explain_results": {"value": explain_value, "source": explain_source},
    }
    invalid = {
        key: value["source"]
        for key, value in settings.items()
        if value["source"] in {"defaulted_invalid", "clamped_min", "clamped_max"}
    }
    errors = [
        f"[context].{key} used {source.replace('_', ' ')}"
        for key, source in invalid.items()
    ]
    return {
        "configured": "context" in config,
        "valid": not invalid,
        "path": ".ai-dememory.toml",
        "settings": settings,
        "errors": errors,
        "next_actions": (
            ["Fix invalid `[context]` defaults in `.ai-dememory.toml`."]
            if invalid
            else []
        ),
    }


def config_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    return config_int_status(value, default, minimum, maximum)[0]


def config_int_status(value: Any, default: int, minimum: int, maximum: int) -> tuple[int, str]:
    if value is None:
        return default, "default"
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default, "defaulted_invalid"
    if parsed < minimum:
        return minimum, "clamped_min"
    if parsed > maximum:
        return maximum, "clamped_max"
    return parsed, "configured"


def config_bool(value: Any, default: bool) -> bool:
    return config_bool_status(value, default)[0]


def config_bool_status(value: Any, default: bool) -> tuple[bool, str]:
    if value is None:
        return default, "default"
    if isinstance(value, bool):
        return value, "configured"
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True, "configured"
        if lowered in {"false", "0", "no", "off"}:
            return False, "configured"
    return default, "defaulted_invalid"


def working_context(root: Path) -> str:
    current = root / "working" / "current.json"
    recent = root / "working" / "recent-session.md"
    parts: list[str] = []
    if current.exists():
        parts.append("`working/current.json`:\n\n```json\n" + current.read_text(encoding="utf-8")[:2000] + "\n```")
    if recent.exists():
        parts.append(recent.read_text(encoding="utf-8")[:2000])
    return "\n\n".join(parts)


def resolve_context_query(root: Path, query: str = "", auto: bool = False) -> tuple[str, str]:
    query = query.strip()
    if query:
        return query, "explicit"
    if not auto:
        raise ValueError("query is required unless --auto has working memory")

    auto_query = working_context(root)[:500].strip()
    if not auto_query:
        raise ValueError("query is required unless --auto has working memory")
    if scan_text(auto_query, "<context.auto_query>"):
        raise ValueError("auto context query rejected by secret scan")
    return auto_query, "working_memory"


def render_item(
    memory_id: str,
    title: str,
    path: str,
    score: float,
    excerpt: str,
    why: dict[str, Any] | None = None,
    explain_results: bool = False,
) -> str:
    section = f"""## {title}

- id: `{memory_id}`
- path: `{path}`
- score: `{score:.4f}`

{excerpt}
"""
    if not explain_results or not why:
        return section
    lines = ["", "Why selected:"]
    for key in (
        "fts",
        "tag_overlap",
        "alias_match",
        "project_match",
        "recency",
        "confidence",
        "type_boost",
        "pin_boost",
        "lifecycle_strength",
        "status_penalty",
        "sensitivity_penalty",
    ):
        if key in why:
            lines.append(f"- {key}: `{why[key]}`")
    for key in ("matched_terms", "matched_fields", "matched_tags", "matched_aliases"):
        values = why.get(key)
        if values:
            lines.append(f"- {key}: `{', '.join(str(item) for item in values)}`")
    if why.get("baseline"):
        lines.append(f"- baseline: `{why['baseline']}`")
    if why.get("project_hint"):
        lines.append(f"- project_hint: `{why['project_hint']}`")
    return section.rstrip() + "\n" + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help="Context query. Defaults to current working context.")
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--budget", type=int, default=None, help="Approximate token budget.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum search results to consider.")
    parser.add_argument("--include-sensitive", action="store_true", help="Include private/sensitive memories.")
    working_group = parser.add_mutually_exclusive_group()
    working_group.add_argument(
        "--include-working-memory",
        dest="working_memory",
        action="store_true",
        help="Include working/current.json and recent session.",
    )
    working_group.add_argument(
        "--no-working-memory",
        dest="working_memory",
        action="store_false",
        help="Exclude working/current.json and recent session.",
    )
    parser.set_defaults(working_memory=None)
    explain_group = parser.add_mutually_exclusive_group()
    explain_group.add_argument("--why", dest="explain_results", action="store_true", help="Render ranking explanations in text output.")
    explain_group.add_argument("--no-why", dest="explain_results", action="store_false", help="Suppress ranking explanations in text output.")
    parser.set_defaults(explain_results=None)
    parser.add_argument("--auto", action="store_true", help="Use working memory as the query when no query is supplied.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    root = repo_root(args.root)
    try:
        defaults = context_defaults(root)
        budget = args.budget if args.budget is not None else defaults.budget_tokens
        include_working_memory = args.working_memory if args.working_memory is not None else defaults.include_working_memory
        explain_results = args.explain_results if args.explain_results is not None else defaults.explain_results
        query, query_source = resolve_context_query(root, " ".join(args.query), auto=args.auto)
        data = assemble_context(
            root,
            query,
            budget,
            limit=args.limit,
            include_sensitive=args.include_sensitive,
            include_working_memory=include_working_memory,
            explain_results=explain_results,
            query_source=query_source,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(data["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
