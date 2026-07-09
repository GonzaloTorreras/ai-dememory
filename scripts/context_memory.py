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
from memorylib import extract_summary, load_memory, repo_relative_path, repo_root
from search_memory import result_to_dict, search
from secret_scan import scan_text


DEFAULT_BUDGET_TOKENS = 2000


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
) -> dict[str, Any]:
    if budget_tokens < 200:
        raise ValueError("budget_tokens must be at least 200")
    results = search(query, root, limit=limit, include_sensitive=include_sensitive)
    remaining = budget_tokens
    items: list[ContextItem] = []
    sections: list[str] = []

    if include_working_memory:
        working = working_context(root)
        if working:
            tokens = estimate_tokens(working)
            if tokens <= remaining:
                sections.append("## Working Memory\n\n" + working)
                remaining -= tokens

    for result in results:
        path = root / result.path
        document = load_memory(path)
        excerpt = extract_summary(document.content, max_chars=900) or result.snippet
        section = render_item(result.id, result.title, result.path, result.score, excerpt, result.why, explain_results)
        tokens = estimate_tokens(section)
        if tokens > remaining:
            continue
        findings = scan_text(section, f"<context:{result.id}>")
        if findings:
            continue
        sections.append(section)
        remaining -= tokens
        items.append(
            ContextItem(
                id=result.id,
                title=result.title,
                path=result.path,
                score=result.score,
                estimated_tokens=tokens,
                why=result.why,
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
        "items": [asdict(item) for item in items],
        "text": text,
    }


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
