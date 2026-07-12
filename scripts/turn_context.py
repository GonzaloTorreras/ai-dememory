#!/usr/bin/env python3
"""Build safe, bounded memory context for a single model turn."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any

from config_file import load_config
from context_memory import assemble_context
from index_memory import default_db_path
from memorylib import MemoryError, discover_memory_files, load_memory, repo_root, slugify
from search_memory import tokenize
from secret_scan import scan_text


DEFAULT_TURN_BUDGET_TOKENS = 1200
MAX_TURN_BUDGET_TOKENS = 8000
MAX_PROMPT_CHARS = 32_000
MAX_KEYWORDS = 12
MIN_RELEVANCE_SCORE = 0.18
DEFAULT_BASELINE_BUDGET_TOKENS = 480

STOP_WORDS = {
    "a", "al", "algo", "and", "are", "as", "con", "de", "del", "do", "el", "en",
    "es", "esta", "este", "esto", "for", "from", "hacer", "haz", "how", "i", "in",
    "is", "it", "la", "las", "lo", "los", "me", "mi", "of", "on", "or", "para",
    "por", "que", "se", "the", "this", "to", "un", "una", "unos", "y", "you",
}


@dataclass(frozen=True)
class RecallSettings:
    enabled: bool = True
    per_turn: bool = True
    default_budget_tokens: int = DEFAULT_TURN_BUDGET_TOKENS
    baseline_budget_tokens: int = DEFAULT_BASELINE_BUDGET_TOKENS
    max_keywords: int = MAX_KEYWORDS
    project_from_cwd: bool = True
    min_relevance_score: float = MIN_RELEVANCE_SCORE


def build_turn_context(
    root: Path,
    prompt: str,
    cwd: str | Path | None = None,
    client: str | None = None,
    session_id: str | None = None,
    budget_tokens: int | None = None,
) -> dict[str, Any]:
    """Retrieve relevant project memory without ever blocking the caller's turn."""
    root = Path(root).resolve()
    trace_id = make_trace_id(root, prompt, cwd, client, session_id, budget_tokens)
    settings, config_degradation = recall_settings(root)
    project, inference_degradation = infer_project(root, prompt, cwd, settings.project_from_cwd)
    base = base_payload(trace_id, project)
    base["degradation"] = unique(config_degradation + inference_degradation)
    base["degraded"] = bool(base["degradation"])

    if not settings.enabled:
        return skip(base, "recall_disabled")
    if not settings.per_turn:
        return skip(base, "per_turn_disabled")

    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
        return skip(base, "invalid_payload", "invalid_prompt")
    prompt_findings = scan_text(prompt, "<turn.prompt>")
    base["security"]["prompt_scanned"] = True
    if prompt_findings:
        base["security"]["secret_detected"] = True
        return skip(base, "secret_detected")

    try:
        budget = resolved_budget(settings, budget_tokens)
    except (TypeError, ValueError, OSError):
        return skip(base, "invalid_payload", "invalid_budget")
    base["budget_tokens"] = budget

    keywords = extract_keywords(prompt, project.get("slug"), settings.max_keywords)
    base["keywords"] = keywords
    base["query"] = " ".join(keywords)
    if not enough_signal(prompt):
        return skip(base, "insufficient_signal")
    if not default_db_path(root).exists():
        return skip(base, "memory_unavailable", "index_missing")

    try:
        context = assemble_context(
            root,
            base["query"],
            budget_tokens=budget,
            limit=20,
            include_sensitive=False,
            include_working_memory=False,
            explain_results=True,
            query_source="turn",
            project_hint=project.get("slug"),
            include_reviewed_durable=True,
            baseline_budget_tokens=settings.baseline_budget_tokens,  # bounded recall config
            require_reviewed_results=True,
            min_relevance_score=settings.min_relevance_score,
        )
    except (FileNotFoundError, MemoryError, OSError, UnicodeError, ValueError):
        return skip(base, "memory_unavailable", "invalid_memory_payload")
    except Exception:
        return skip(base, "memory_unavailable", "context_assembly_failed")

    base["degradation"] = unique(base["degradation"] + list(context.get("degradation", [])))
    base["degraded"] = bool(base["degradation"])
    base["security"]["filtered_items"] = int(context.get("security_filtered_items", 0))
    items = context.get("items")
    text = context.get("text")
    if not isinstance(items, list) or not isinstance(text, str):
        return skip(base, "memory_unavailable", "invalid_context_payload")
    if not items or scan_text(text, "<turn.context>"):
        if scan_text(text, "<turn.context>"):
            base["security"]["filtered_items"] += len(items)
        return skip(base, "no_relevant_memory" if not items else "no_safe_context")

    base.update(
        {
            "decision": "inject",
            "reason": "relevant_memory_found",
            "items": items,
            "text": text,
            "estimated_tokens": context.get("estimated_tokens", 0),
            "remaining_tokens": context.get("remaining_tokens", 0),
        }
    )
    return base


def base_payload(trace_id: str, project: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "skip",
        "reason": "not_evaluated",
        "project": project,
        "keywords": [],
        "query": "",
        "query_source": "turn",
        "items": [],
        "text": "",
        "trace_id": trace_id,
        "security": {
            "prompt_scanned": False,
            "secret_detected": False,
            "sensitive_excluded": True,
            "filtered_items": 0,
        },
        "degraded": False,
        "degradation": [],
    }


def skip(payload: dict[str, Any], reason: str, degradation: str | None = None) -> dict[str, Any]:
    payload["decision"] = "skip"
    payload["reason"] = reason
    payload["items"] = []
    payload["text"] = ""
    if degradation:
        payload["degradation"] = unique(payload["degradation"] + [degradation])
        payload["degraded"] = True
    return payload


def extract_keywords(prompt: str, project_slug: str | None = None, max_keywords: int = MAX_KEYWORDS) -> list[str]:
    output: list[str] = []
    for token in tokenize(prompt):
        if token in STOP_WORDS or len(token) < 3 and token not in {"ai", "ui"}:
            continue
        if token not in output:
            output.append(token)
        if len(output) >= max_keywords:
            break
    if project_slug:
        project_tokens = [token for token in tokenize(project_slug) if token not in STOP_WORDS]
        for token in reversed(project_tokens):
            if token in output:
                output.remove(token)
            output.insert(0, token)
    return output[:max_keywords]


def enough_signal(prompt: str) -> bool:
    semantic = [
        token
        for token in tokenize(prompt)
        if token not in STOP_WORDS and (len(token) >= 3 or token in {"ai", "ui"})
    ]
    return len(set(semantic)) >= 2 or bool(semantic and len(prompt.strip()) >= 24)


def resolved_budget(settings: RecallSettings, requested: int | None) -> int:
    if requested is None:
        requested = settings.default_budget_tokens
    if not isinstance(requested, int) or isinstance(requested, bool):
        raise TypeError("budget must be an integer")
    if requested < 200:
        raise ValueError("budget must be at least 200")
    return min(requested, MAX_TURN_BUDGET_TOKENS)


def infer_project(
    root: Path,
    prompt: Any,
    cwd: str | Path | None,
    project_from_cwd: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    prompt_text = prompt if isinstance(prompt, str) else ""
    prompt_tokens = tokenize(prompt_text)
    explicit = re.search(r"(?i)\b(?:project|proyecto|repo|repository)\s+([A-Za-z0-9_.-]+)", prompt_text)
    if explicit:
        return project_payload(explicit.group(1), None, "prompt"), []

    if project_from_cwd and cwd is not None:
        try:
            cwd_path = Path(cwd).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return project_payload(None, None, "none"), ["invalid_cwd"]
        if cwd_path != root:
            return project_payload(cwd_path.name, cwd_path, "cwd"), []

    known, errors = known_projects(root)
    for project in sorted(known, key=lambda value: (-len(tokenize(value)), value)):
        project_tokens = tokenize(project)
        if contains_sequence(prompt_tokens, project_tokens):
            return project_payload(project, None, "prompt"), errors

    if project_from_cwd and cwd is not None:
        cwd_path = Path(cwd).expanduser().resolve()
        if cwd_path == root and len(known) == 1:
            return project_payload(known[0], cwd_path, "cwd"), errors
        return project_payload(cwd_path.name, cwd_path, "cwd"), errors
    return project_payload(None, None, "none"), errors


def recall_settings(root: Path) -> tuple[RecallSettings, list[str]]:
    try:
        recall = load_config(root).get("recall", {})
    except (OSError, UnicodeError, ValueError):
        return RecallSettings(), ["invalid_recall_config"]
    if not isinstance(recall, dict):
        return RecallSettings(), ["invalid_recall_config"]

    errors: list[str] = []
    enabled = setting_bool(recall, "enabled", True, errors)
    per_turn = setting_bool(recall, "per_turn", True, errors)
    default_budget = setting_int(
        recall, "default_budget_tokens", DEFAULT_TURN_BUDGET_TOKENS, 200, MAX_TURN_BUDGET_TOKENS, errors
    )
    baseline_budget = setting_int(
        recall, "baseline_budget_tokens", DEFAULT_BASELINE_BUDGET_TOKENS, 0, MAX_TURN_BUDGET_TOKENS, errors
    )
    baseline_budget = min(baseline_budget, default_budget)
    max_keywords = setting_int(recall, "max_keywords", MAX_KEYWORDS, 2, 32, errors)
    project_from_cwd = setting_bool(recall, "project_from_cwd", True, errors)
    min_relevance = setting_float(recall, "min_relevance_score", MIN_RELEVANCE_SCORE, 0.0, 1.0, errors)
    return (
        RecallSettings(
            enabled=enabled,
            per_turn=per_turn,
            default_budget_tokens=default_budget,  # bounded recall config
            baseline_budget_tokens=baseline_budget,  # bounded recall config
            max_keywords=max_keywords,
            project_from_cwd=project_from_cwd,
            min_relevance_score=min_relevance,
        ),
        unique(errors),
    )


def setting_bool(values: dict[str, Any], key: str, default: bool, errors: list[str]) -> bool:
    value = values.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    errors.append(f"invalid_recall_setting:{key}")
    return default


def setting_int(
    values: dict[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
    errors: list[str],
) -> int:
    value = values.get(key)
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"invalid_recall_setting:{key}")
        return default
    if value < minimum or value > maximum:
        errors.append(f"invalid_recall_setting:{key}")
        return default
    return value


def setting_float(
    values: dict[str, Any],
    key: str,
    default: float,
    minimum: float,
    maximum: float,
    errors: list[str],
) -> float:
    value = values.get(key)
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"invalid_recall_setting:{key}")
        return default
    if isinstance(value, bool) or parsed < minimum or parsed > maximum:
        errors.append(f"invalid_recall_setting:{key}")
        return default
    return parsed


def known_projects(root: Path) -> tuple[list[str], list[str]]:
    projects: set[str] = set()
    errors: list[str] = []
    for path in discover_memory_files(root):
        try:
            document = load_memory(path)
        except (MemoryError, OSError, UnicodeError):
            errors.append("invalid_project_memory")
            continue
        project = document.frontmatter.get("project")
        if isinstance(project, str) and project.strip():
            projects.add(project.strip())
    return sorted(projects), unique(errors)


def project_payload(value: str | None, path: Path | None, source: str) -> dict[str, Any]:
    return {
        "slug": slugify(value, fallback="") if value else None,
        "path": str(path) if path is not None else None,
        "source": source,
    }


def contains_sequence(values: list[str], sequence: list[str]) -> bool:
    if not sequence or len(sequence) > len(values):
        return False
    width = len(sequence)
    return any(values[index : index + width] == sequence for index in range(len(values) - width + 1))


def make_trace_id(
    root: Path,
    prompt: Any,
    cwd: str | Path | None,
    client: str | None,
    session_id: str | None,
    budget_tokens: int | None,
) -> str:
    payload = json.dumps(
        {
            "root": str(root),
            "prompt_hash": hashlib.sha256(str(prompt).encode("utf-8", errors="replace")).hexdigest(),
            "cwd": str(cwd) if cwd is not None else None,
            "client": client,
            "session_id": session_id,
            "budget_tokens": budget_tokens,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "turn_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="+", help="User prompt or task text used for recall.")
    parser.add_argument("--root", default=None, help="Memory vault root.")
    parser.add_argument("--cwd", default=None, help="Active project working directory.")
    parser.add_argument("--client", default="generic")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--budget-tokens", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_turn_context(
            repo_root(args.root),
            " ".join(args.prompt),
            cwd=args.cwd,
            client=args.client,
            session_id=args.session_id,  # non-secret trace correlation
            budget_tokens=args.budget_tokens,  # bounded recall config
        )
    except (OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result["decision"] == "inject":
        print(result["text"])
    else:
        print(f"Memory context skipped: {result['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
