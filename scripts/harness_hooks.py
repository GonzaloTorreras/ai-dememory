#!/usr/bin/env python3
"""Provider-neutral JSON hook dispatch for per-turn recall and safe learning proposals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from config_file import load_config
from memorylib import slugify
from secret_scan import scan_text


DEFAULT_BUDGET_TOKENS = 1000
MAX_LEARNING_SIGNALS = 10
MAX_LEARNING_CHARS = 4000
LEARNING_KEYS = {
    "ai_dememory_learning",
    "ai_dememory_learnings",
    "learning_signal",
    "learning_signals",
    "lessons_learned",
    "memory_proposal",
}
LEARNING_MARKER_RE = re.compile(
    r"\[ai-dememory-learning\](.*?)\[/ai-dememory-learning\]",
    re.IGNORECASE | re.DOTALL,
)
LEARNING_HEADING_RE = re.compile(
    r"^#{1,3}\s*(?:learnings|lessons learned|reusable lessons|aprendizajes|"
    r"decisions|decisiones|root cause|causa ra[i\u00ed]z)\s*$",
    re.IGNORECASE,
)


def dispatch_hook_event(
    root: Path,
    event: str,
    payload_text: str,
    client: str = "generic",
    budget_tokens: int | None = None,
) -> dict[str, object]:
    """Return a hook-compatible JSON object and fail open on malformed input."""
    payload = parse_payload(payload_text)
    if payload is None:
        return {}

    if event == "Stop":
        try:
            maybe_write_session_proposal(root, payload, client)
        except Exception:
            # Learning is optional and must never block the harness.
            pass
        return {}
    if event != "UserPromptSubmit":
        return {}
    if not client_enabled(root, "recall", client):
        return {}

    prompt = first_string(payload, "prompt", "user_prompt", "input", "message")
    if not prompt:
        return {}
    cwd = first_string(payload, "cwd", "working_directory", "project_root") or str(root)
    session_id = first_string(payload, "session_id", "sessionId", "conversation_id") or None
    budget = effective_budget(root, payload, budget_tokens)

    try:
        from turn_context import build_turn_context

        context = build_turn_context(root, prompt, cwd, client, session_id, budget)
    except Exception:
        # Missing/stale indexes and provider differences are fail-open conditions.
        return {}
    if not isinstance(context, dict) or context.get("decision") != "inject":
        return {}
    additional_context = context.get("text")
    if not isinstance(additional_context, str) or not additional_context.strip():
        additional_context = context.get("additional_context") or context.get("context")
    if not isinstance(additional_context, str) or not additional_context.strip():
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": additional_context.strip(),
        }
    }


def parse_payload(payload_text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(payload_text)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def first_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def effective_budget(root: Path, payload: dict[str, Any], override: int | None) -> int:
    if isinstance(override, int):
        return max(200, min(20_000, override))
    payload_budget = payload.get("budget_tokens")
    if isinstance(payload_budget, int) and not isinstance(payload_budget, bool):
        return max(200, min(20_000, payload_budget))
    try:
        configured = load_config(root).get("recall", {}).get("default_budget_tokens", DEFAULT_BUDGET_TOKENS)
        return max(200, min(20_000, int(configured)))
    except (OSError, TypeError, ValueError):
        return DEFAULT_BUDGET_TOKENS


def section_config(root: Path, section: str) -> dict[str, Any]:
    try:
        value = load_config(root).get(section, {})
    except (OSError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def client_enabled(root: Path, section: str, client: str) -> bool:
    clients = section_config(root, section).get("clients")
    if clients is None:
        return True
    if not isinstance(clients, list):
        return False
    normalized = {str(value).strip().casefold() for value in clients if str(value).strip()}
    return client.casefold() in normalized or "all" in normalized


def hook_metadata_enabled(root: Path, client: str) -> bool:
    learning = section_config(root, "learning")
    return learning.get("hook_metadata", True) is True and client_enabled(root, "learning", client)


def session_proposals_enabled(root: Path, client: str) -> bool:
    learning = section_config(root, "learning")
    return learning.get("session_proposals", False) is True and client_enabled(root, "learning", client)


def maybe_write_session_proposal(root: Path, payload: dict[str, Any], client: str) -> Path | None:
    """Write only explicitly signalled lessons to the review inbox."""
    if not session_proposals_enabled(root, client):
        return None
    signals = extract_learning_signals(payload)
    if not signals:
        return None
    normalized = "\n".join(sorted(signal.casefold() for signal in signals))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    inbox = resolve_learning_inbox(root)
    if inbox.exists():
        matches = sorted(inbox.glob(f"*_session-learning_{digest}.md"))
        if matches:
            return matches[0]

    now = datetime.now(timezone.utc)
    created = now.date().isoformat()
    review_after = (now.date() + timedelta(days=7)).isoformat()
    safe_client = slugify(client, "generic")
    bullets = "\n".join(f"- {signal}" for signal in signals)
    text = f"""---
id: proposal_session_learning_{now.strftime('%Y%m%d_%H%M%S')}_{digest}
title: "Session learning proposal"
type: session
status: proposed
scope: session
project: null
tags: [learning, session, {safe_client}]
aliases: []
created_at: {created}
updated_at: {created}
confidence: 0.4
sensitivity: internal
source:
  kind: automation
  ref: "hook:{safe_client}:Stop"
  fingerprint: "{digest}"
pin: false
decay: fast
review_after: {review_after}
---

# Session learning proposal

Explicit learning signals emitted by the harness for human review:

{bullets}

This candidate is not durable memory. Review it before promotion.
"""
    if scan_text(text, "<hook-session-learning>"):
        return None
    inbox.mkdir(parents=True, exist_ok=True)
    inbox = resolve_learning_inbox(root)
    path = inbox / f"{now.strftime('%Y%m%dT%H%M%SZ')}_session-learning_{digest}.md"
    path.write_text(text, encoding="utf-8")
    return path


def extract_learning_signals(payload: dict[str, Any]) -> list[str]:
    found: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, str):
            clean = " ".join(value.split()).strip()
            if clean and len(clean) <= MAX_LEARNING_CHARS and clean not in found:
                found.append(clean)
        elif isinstance(value, list):
            for item in value:
                add(item)
        elif isinstance(value, dict):
            for item in value.values():
                add(item)

    # Only provider-authored structured fields and the final assistant message
    # are eligible. Never scan arbitrary transcript/user strings recursively.
    for key, value in payload.items():
        normalized_key = str(key).casefold()
        if normalized_key in LEARNING_KEYS:
            add(value)
        elif normalized_key == "last_assistant_message" and isinstance(value, str):
            add(explicit_section_signals(value))
            for match in LEARNING_MARKER_RE.finditer(value):
                add(match.group(1))
    return found[:MAX_LEARNING_SIGNALS]


def explicit_section_signals(text: str) -> list[str]:
    """Extract bullets only from explicitly labelled learning/decision sections."""
    output: list[str] = []
    active = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if LEARNING_HEADING_RE.fullmatch(line):
            active = True
            continue
        if active and line.startswith("#"):
            active = False
            continue
        if active and re.match(r"^[-*]\s+\S", line):
            output.append(re.sub(r"^[-*]\s+", "", line).strip())
            if len(output) >= MAX_LEARNING_SIGNALS:
                break
    return output


def resolve_learning_inbox(root: Path) -> Path:
    root_abs = Path(os.path.abspath(root))
    target = Path(os.path.abspath(root_abs / "inbox" / "llm-captures"))
    current = root_abs
    for part in target.relative_to(root_abs).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("learning proposal inbox must not contain symlinks")
    return target

