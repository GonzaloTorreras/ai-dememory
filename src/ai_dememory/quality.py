"""Small deterministic memory-quality rules; no provider or network imports."""

from __future__ import annotations

import hashlib
import json
import math


def validate_importance(value: str) -> str:
    if not isinstance(value, str) or value not in ("low", "normal", "high"):
        raise ValueError("Importance must be low, normal or high")
    return value


def evidence_revision(title: str, content: str, source: dict) -> str:
    payload = json.dumps([title, content, source], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_confidence(value: dict | None, revision: str | None = None) -> dict:
    """Host scores are explicitly advisory; only code supplies their method."""
    if value is None or value == {}:
        return {}
    required = {"support", "model", "rubric"}
    optional = {"certainty", "revision", "method"}
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError("Confidence requires support, model and rubric")
    for key in ("support", "certainty"):
        number = value.get(key)
        if key in value and (type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1):
            raise ValueError("Confidence values must be finite numbers between zero and one")
    for key in ("model", "rubric"):
        text = value[key]
        if not isinstance(text, str) or not text.strip() or len(text) > 128 or any(ord(c) < 32 for c in text):
            raise ValueError("Confidence model and rubric must be bounded plain strings")
    if value.get("method", "host_advisory") != "host_advisory":
        raise ValueError("Host confidence can only be advisory")
    stored_revision = value.get("revision", "")
    if (not isinstance(stored_revision, str) or len(stored_revision) != 64
            or any(c not in "0123456789abcdef" for c in stored_revision)) and revision is None:
        raise ValueError("Confidence requires an evidence revision")
    result = {**value, "method": "host_advisory", "revision": revision or stored_revision}
    return result


def confidence_status(memory) -> str:
    if not memory.confidence:
        return "unassessed"
    if memory.confidence.get("revision") != evidence_revision(memory.title, memory.content, memory.source):
        return "stale"
    return "advisory"
