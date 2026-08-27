#!/usr/bin/env python3
"""Validate the normative public planning schema, DAG, frontier, and evidence paths."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
from itertools import islice
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from typing import Any

from memorylib import repo_root


PLANNING_DIR = Path("contracts/planning")
SEQUENCE_NAME = "v3-execution-sequence.json"
SCHEMA_NAME = "v3-execution-sequence.schema.json"
LEDGER_NAME = "v3-execution-ledger.json"
EXTERNAL_RECEIPT_SCHEMA_NAME = "external-readback-receipt.schema.json"
EXTERNAL_RECEIPT_SCHEMA_REF = "../../external-readback-receipt.schema.json"
EVIDENCE_NAMESPACE = PurePosixPath("contracts/planning/evidence")
ROADMAP_PATH = Path("docs/v3-hybrid-visual-multiplatform-roadmap.md")
ROADMAP_TABLE_BEGIN = "<!-- BEGIN NORMATIVE TASK STATE TABLE -->"
ROADMAP_TABLE_END = "<!-- END NORMATIVE TASK STATE TABLE -->"
ROADMAP_TABLE_HEADER = ["Task ID", "Objective", "Batch", "State", "Notes"]
ROADMAP_TABLE_SEPARATOR = ["---", "---", "---", "---", "---"]
ROADMAP_TABLE_MAX_CHARS = 64 * 1024
ROADMAP_TABLE_MAX_ROWS = 512
ROADMAP_TABLE_MAX_LINE_CHARS = 8 * 1024
SEQUENCE_MAX_BYTES = 512 * 1024
SEQUENCE_SCHEMA_MAX_BYTES = 64 * 1024
LEDGER_MAX_BYTES = 256 * 1024
EXTERNAL_RECEIPT_SCHEMA_MAX_BYTES = 64 * 1024
EXTERNAL_RECEIPT_MAX_BYTES = 64 * 1024
DETAIL_ARTIFACT_MAX_BYTES = 64 * 1024
ROADMAP_MAX_BYTES = 256 * 1024
VALIDATION_ERROR_LIMIT = 256
EVIDENCE_DIRECTORY_MAX_ENTRIES = 4096
WINDOWS_FORBIDDEN_PATH_CHARS = frozenset('<>"|?*')
WINDOWS_RESERVED_PATH_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"{prefix}{suffix}" for prefix in ("COM", "LPT") for suffix in ("¹", "²", "³")}
)
WINDOWS_REPARSE_POINT_ATTRIBUTE = 0x400
SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "title",
        "description",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "enum",
        "minItems",
        "maxItems",
        "uniqueItems",
        "items",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
    }
)


class DuplicateJsonKeyError(ValueError):
    """Raised when a planning JSON object contains an ambiguous duplicate key."""


class NonFiniteJsonValueError(ValueError):
    """Raised when Python's permissive JSON decoder sees NaN or infinity."""


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(key)
        result[key] = value
    return result


def reject_non_finite_json_value(value: str) -> Any:
    raise NonFiniteJsonValueError(value)


def parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise NonFiniteJsonValueError(value)
    return parsed


def cap_validation_errors(errors: list[str]) -> list[str]:
    """Return a deterministic bounded diagnostic list."""
    if len(errors) <= VALIDATION_ERROR_LIMIT:
        return errors
    omitted = len(errors) - VALIDATION_ERROR_LIMIT + 1
    return [
        *errors[: VALIDATION_ERROR_LIMIT - 1],
        f"validation error limit reached; omitted {omitted} additional errors",
    ]


def read_bounded_bytes(
    path: Path,
    errors: list[str],
    *,
    max_bytes: int,
    label: str | None = None,
) -> bytes | None:
    """Read at most max_bytes without trusting a preceding mutable stat result."""
    display = label or path.as_posix()
    try:
        with path.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except FileNotFoundError:
        errors.append(f"{display}: missing")
        return None
    except OSError as exc:
        errors.append(f"{display}: cannot be read: {exc}")
        return None
    if len(payload) > max_bytes:
        errors.append(f"{display}: exceeds {max_bytes} bytes")
        return None
    return payload


def read_bounded_utf8(
    path: Path,
    errors: list[str],
    *,
    max_bytes: int,
    label: str | None = None,
) -> str | None:
    display = label or path.as_posix()
    payload = read_bounded_bytes(path, errors, max_bytes=max_bytes, label=display)
    if payload is None:
        return None
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{display}: invalid UTF-8")
        return None


def load_json_object(
    path: Path,
    errors: list[str],
    *,
    max_bytes: int,
    label: str | None = None,
) -> dict[str, Any] | None:
    display = label or path.as_posix()
    encoded = read_bounded_utf8(
        path, errors, max_bytes=max_bytes, label=display
    )
    if encoded is None:
        return None
    try:
        value = json.loads(
            encoded,
            object_pairs_hook=reject_duplicate_json_keys,
            parse_constant=reject_non_finite_json_value,
            parse_float=parse_finite_json_float,
        )
    except DuplicateJsonKeyError as exc:
        errors.append(f"{display}: duplicate JSON key {str(exc)!r}")
        return None
    except NonFiniteJsonValueError as exc:
        errors.append(f"{display}: non-finite JSON value {str(exc)!r}")
        return None
    except RecursionError:
        errors.append(f"{display}: invalid JSON nesting")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{display}: invalid JSON: {exc}")
        return None
    except ValueError:
        errors.append(f"{display}: invalid JSON value")
        return None
    if not isinstance(value, dict):
        errors.append(f"{display}: root must be an object")
        return None
    return value


def validate_json_schema(
    value: Any,
    schema: dict[str, Any],
    path: str = "$",
    *,
    max_errors: int = VALIDATION_ERROR_LIMIT,
) -> list[str]:
    """Validate the strict JSON-Schema subset used by the checked-in contract."""
    errors: list[str] = []
    if max_errors <= 0:
        return errors
    expected_type = schema.get("type")
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if isinstance(expected_type, str):
        checker = type_checks.get(expected_type)
        if checker is None:
            return [f"{path}: unsupported schema type {expected_type!r}"]
        if not checker(value):
            return [f"{path}: expected {expected_type}"]

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: value is not in the allowed enum")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if isinstance(required, list):
            for name in required:
                if name not in value:
                    errors.append(f"{path}: missing required property {name!r}")
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            for name in sorted(set(value) - set(properties)):
                errors.append(f"{path}: unexpected property {name!r}")
                if len(errors) >= max_errors:
                    return errors
        if isinstance(properties, dict):
            for name, child_schema in properties.items():
                if name in value and isinstance(child_schema, dict):
                    errors.extend(
                        validate_json_schema(
                            value[name],
                            child_schema,
                            f"{path}.{name}",
                            max_errors=max_errors - len(errors),
                        )
                    )
                    if len(errors) >= max_errors:
                        return errors

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if isinstance(minimum_items, int) and len(value) < minimum_items:
            errors.append(f"{path}: array has fewer than {minimum_items} items")
        maximum_items = schema.get("maxItems")
        if isinstance(maximum_items, int) and len(value) > maximum_items:
            errors.append(f"{path}: array has more than {maximum_items} items")
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_json_schema(
                        item,
                        item_schema,
                        f"{path}[{index}]",
                        max_errors=max_errors - len(errors),
                    )
                )
                if len(errors) >= max_errors:
                    return errors

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            errors.append(f"{path}: string is shorter than {minimum_length}")
        maximum_length = schema.get("maxLength")
        if isinstance(maximum_length, int) and len(value) > maximum_length:
            errors.append(f"{path}: string is longer than {maximum_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            errors.append(f"{path}: string does not match {pattern!r}")
        if schema.get("format") == "date":
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: invalid ISO date")
            else:
                if parsed.isoformat() != value:
                    errors.append(f"{path}: date must use canonical YYYY-MM-DD")

    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            errors.append(f"{path}: integer is below {minimum}")
        maximum = schema.get("maximum")
        if isinstance(maximum, int) and value > maximum:
            errors.append(f"{path}: integer is above {maximum}")
    return errors


def validate_schema_subset(schema: dict[str, Any], label: str) -> list[str]:
    """Fail closed on unsupported assertions or malformed supported keywords."""
    errors: list[str] = []
    pending: list[tuple[str, Any]] = [(label, schema)]
    while pending and len(errors) < VALIDATION_ERROR_LIMIT:
        path, node = pending.pop()
        if not isinstance(node, dict):
            errors.append(f"{path}: schema node must be an object")
            continue
        for keyword in sorted(set(node) - SUPPORTED_SCHEMA_KEYWORDS):
            errors.append(f"{path}: unsupported schema keyword {keyword!r}")
            if len(errors) >= VALIDATION_ERROR_LIMIT:
                break
        properties = node.get("properties")
        if properties is not None:
            if not isinstance(properties, dict):
                errors.append(f"{path}.properties: expected object")
            else:
                for name in reversed(list(properties)):
                    pending.append((f"{path}.properties.{name}", properties[name]))
        items = node.get("items")
        if items is not None:
            if not isinstance(items, dict):
                errors.append(f"{path}.items: expected object")
            else:
                pending.append((f"{path}.items", items))

        for keyword in ("$schema", "$id", "title", "description"):
            if keyword in node and not isinstance(node[keyword], str):
                errors.append(f"{path}.{keyword}: expected string")

        if "type" in node:
            schema_type = node["type"]
            if not isinstance(schema_type, str):
                errors.append(f"{path}.type: expected string")
            elif schema_type not in {
                "object",
                "array",
                "string",
                "integer",
                "boolean",
            }:
                errors.append(
                    f"{path}.type: unsupported schema type {schema_type!r}"
                )

        for keyword in ("additionalProperties", "uniqueItems"):
            if keyword in node and not isinstance(node[keyword], bool):
                errors.append(f"{path}.{keyword}: expected boolean")

        required = node.get("required")
        if required is not None:
            if not isinstance(required, list) or not all(
                isinstance(item, str) and item for item in required
            ):
                errors.append(f"{path}.required: expected non-empty string array")
            elif len(required) != len(set(required)):
                errors.append(f"{path}.required: array items must be unique")

        enum = node.get("enum")
        if enum is not None and (not isinstance(enum, list) or not enum):
            errors.append(f"{path}.enum: expected non-empty array")

        for keyword in ("minItems", "maxItems", "minLength", "maxLength"):
            if keyword not in node:
                continue
            bound = node[keyword]
            if (
                not isinstance(bound, int)
                or isinstance(bound, bool)
                or bound < 0
            ):
                errors.append(f"{path}.{keyword}: expected non-negative integer")

        for keyword in ("minimum", "maximum"):
            if keyword in node and (
                not isinstance(node[keyword], int)
                or isinstance(node[keyword], bool)
            ):
                errors.append(f"{path}.{keyword}: expected integer")

        for minimum_keyword, maximum_keyword in (
            ("minItems", "maxItems"),
            ("minLength", "maxLength"),
            ("minimum", "maximum"),
        ):
            minimum = node.get(minimum_keyword)
            maximum = node.get(maximum_keyword)
            if (
                isinstance(minimum, int)
                and not isinstance(minimum, bool)
                and isinstance(maximum, int)
                and not isinstance(maximum, bool)
                and minimum > maximum
            ):
                errors.append(
                    f"{path}: {minimum_keyword} must not exceed {maximum_keyword}"
                )

        schema_format = node.get("format")
        if schema_format is not None:
            if not isinstance(schema_format, str):
                errors.append(f"{path}.format: expected string")
            elif schema_format != "date":
                errors.append(f"{path}.format: unsupported format {schema_format!r}")

        pattern = node.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                errors.append(f"{path}.pattern: expected string")
                continue
            try:
                re.compile(pattern)
            except re.error:
                errors.append(f"{path}.pattern: invalid regular expression")
    return cap_validation_errors(errors)


def duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def dependency_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Find one deterministic dependency cycle without Python recursion."""
    state: dict[str, int] = {}
    for root in graph:
        if state.get(root, 0) != 0:
            continue
        active_path = [root]
        active_index = {root: 0}
        state[root] = 1
        stack: list[tuple[str, Any]] = [(root, iter(graph.get(root, [])))]
        while stack:
            node, dependencies = stack[-1]
            try:
                dependency = next(dependencies)
            except StopIteration:
                stack.pop()
                active_index.pop(node, None)
                active_path.pop()
                state[node] = 2
                continue
            dependency_state = state.get(dependency, 0)
            if dependency_state == 1:
                start = active_index[dependency]
                return [*active_path[start:], dependency]
            if dependency_state == 2:
                continue
            state[dependency] = 1
            active_index[dependency] = len(active_path)
            active_path.append(dependency)
            stack.append((dependency, iter(graph.get(dependency, []))))
    return None


def dependency_reachable(graph: dict[str, list[str]], start: str, target: str) -> bool:
    """Return whether target is start or one of its transitive dependencies."""
    pending = [start]
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(
            dependency for dependency in graph.get(node, []) if dependency not in visited
        )
    return False


def transitive_dependencies(graph: dict[str, list[str]], start: str) -> set[str]:
    """Return all known predecessor nodes without assuming an acyclic graph."""
    result: set[str] = set()
    pending = list(graph.get(start, []))
    while pending:
        node = pending.pop()
        if node in result or node == start:
            continue
        result.add(node)
        pending.extend(graph.get(node, []))
    return result


def validate_evidence_path(
    task_id: str, value: str, root: Path
) -> tuple[Path | None, list[str]]:
    """Resolve one canonical repo-relative evidence path to a contained file."""
    if not value or value != value.strip():
        return None, [
            f"task {task_id} has empty or whitespace-padded evidence path {value!r}"
        ]
    if "\\" in value:
        return None, [
            f"task {task_id} evidence path must use forward slashes: {value!r}"
        ]
    if len(value) > 512:
        return None, [
            f"task {task_id} evidence path exceeds 512 characters: {value!r}"
        ]
    path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if path.is_absolute() or windows_path.is_absolute() or bool(windows_path.drive):
        return None, [f"task {task_id} has absolute evidence path {value!r}"]
    if ":" in value:
        return None, [
            f"task {task_id} evidence path must not contain ':' or an alternate stream: "
            f"{value!r}"
        ]
    if ".." in path.parts:
        return None, [f"task {task_id} has traversal evidence path {value!r}"]
    if any(part.casefold() == ".git" for part in path.parts):
        return None, [f"task {task_id} evidence path cannot use .git metadata: {value!r}"]
    for part in path.parts:
        if (
            part.endswith((".", " "))
            or any(character in WINDOWS_FORBIDDEN_PATH_CHARS for character in part)
            or any(ord(character) < 32 for character in part)
            or part.split(".", 1)[0].upper() in WINDOWS_RESERVED_PATH_NAMES
        ):
            return None, [
                f"task {task_id} evidence path is not portable on Windows: {value!r}"
            ]
    if value == "." or path.as_posix() != value:
        return None, [f"task {task_id} has non-normalized evidence path {value!r}"]

    try:
        root_resolved = root.resolve(strict=True)
    except OSError as exc:
        return None, [f"repository root cannot be resolved: {exc}"]
    resolved = root_resolved
    for part in path.parts:
        try:
            entries = list(
                islice(resolved.iterdir(), EVIDENCE_DIRECTORY_MAX_ENTRIES + 1)
            )
        except OSError as exc:
            return None, [
                f"task {task_id} evidence path cannot inspect component {part!r}: {exc}"
            ]
        if len(entries) > EVIDENCE_DIRECTORY_MAX_ENTRIES:
            return None, [
                f"task {task_id} evidence directory exceeds "
                f"{EVIDENCE_DIRECTORY_MAX_ENTRIES} entries before component {part!r}"
            ]
        case_aliases = sorted(
            (entry.name for entry in entries if entry.name.casefold() == part.casefold()),
            key=lambda name: (name.casefold(), name),
        )
        if len(case_aliases) > 1:
            return None, [
                f"task {task_id} evidence path component {part!r} has ambiguous "
                f"case-fold spellings {case_aliases!r}"
            ]
        exact_entry = next((entry for entry in entries if entry.name == part), None)
        if exact_entry is None:
            if case_aliases:
                return None, [
                    f"task {task_id} evidence path component {part!r} does not match "
                    f"filesystem spelling {case_aliases[0]!r}"
                ]
            return None, [f"task {task_id} evidence path does not exist: {value}"]
        try:
            component_stat = exact_entry.lstat()
        except OSError as exc:
            return None, [
                f"task {task_id} evidence path cannot inspect component {part!r}: {exc}"
            ]
        if stat.S_ISLNK(component_stat.st_mode) or (
            getattr(component_stat, "st_file_attributes", 0)
            & WINDOWS_REPARSE_POINT_ATTRIBUTE
        ):
            return None, [
                f"task {task_id} evidence path component {part!r} must not be a "
                "symlink, junction, or reparse point"
            ]
        try:
            resolved = exact_entry.resolve(strict=True)
        except OSError as exc:
            return None, [
                f"task {task_id} evidence path cannot resolve component {part!r}: {exc}"
            ]
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            return None, [
                f"task {task_id} evidence path escapes repository root: {value!r}"
            ]
    try:
        is_file = resolved.is_file()
    except OSError as exc:
        return None, [
            f"task {task_id} evidence path cannot be inspected {value!r}: {exc}"
        ]
    if not is_file:
        return None, [f"task {task_id} evidence path is not a regular file: {value}"]
    try:
        final_stat = resolved.stat()
    except OSError as exc:
        return None, [
            f"task {task_id} evidence path cannot be inspected {value!r}: {exc}"
        ]
    if getattr(final_stat, "st_nlink", 1) != 1:
        return None, [
            f"task {task_id} evidence path must not be a hard link: {value}"
        ]
    return resolved, []


def is_external_receipt_path(task_id: str, value: str) -> bool:
    path = PurePosixPath(value)
    expected_parent = EVIDENCE_NAMESPACE / task_id
    return path.parent == expected_parent and path.suffix == ".json"


def validate_hashed_artifact(
    *,
    task_id: str,
    purpose: str,
    value: Any,
    expected_path: PurePosixPath,
    receipt_path: Path,
    root: Path,
    seen_paths: set[str],
) -> list[str]:
    """Bind one receipt claim to the exact bytes of a task-local artifact."""
    if not isinstance(value, dict):
        return [f"{purpose}: artifact descriptor is unavailable"]
    artifact_path = value.get("path")
    if not isinstance(artifact_path, str):
        return [f"{purpose}: artifact path is unavailable"]
    errors: list[str] = []
    expected_value = expected_path.as_posix()
    if artifact_path != expected_value:
        errors.append(
            f"{purpose}: path {artifact_path!r} must be {expected_value!r}"
        )
    if artifact_path in seen_paths:
        errors.append(f"{purpose}: artifact path {artifact_path!r} is reused")
    else:
        seen_paths.add(artifact_path)
    resolved, path_errors = validate_evidence_path(task_id, artifact_path, root)
    errors.extend(f"{purpose}: {error}" for error in path_errors)
    if resolved is None:
        return errors
    if resolved == receipt_path:
        errors.append(f"{purpose}: artifact must not reference its receipt")
        return errors
    artifact_errors: list[str] = []
    payload = read_bounded_bytes(
        resolved,
        artifact_errors,
        max_bytes=DETAIL_ARTIFACT_MAX_BYTES,
        label=artifact_path,
    )
    errors.extend(f"{purpose}: {error}" for error in artifact_errors)
    if payload is None:
        return errors
    declared_size = value.get("byte_size")
    if declared_size != len(payload):
        errors.append(
            f"{purpose}: byte_size {declared_size!r} does not match {len(payload)}"
        )
    actual_digest = hashlib.sha256(payload).hexdigest()
    if value.get("artifact_sha256") != actual_digest:
        errors.append(f"{purpose}: artifact_sha256 does not match artifact bytes")
    try:
        encoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{purpose}: artifact is not valid UTF-8")
        return errors
    try:
        artifact = json.loads(
            encoded,
            object_pairs_hook=reject_duplicate_json_keys,
            parse_constant=reject_non_finite_json_value,
            parse_float=parse_finite_json_float,
        )
    except DuplicateJsonKeyError as exc:
        errors.append(f"{purpose}: artifact has duplicate JSON key {str(exc)!r}")
    except NonFiniteJsonValueError as exc:
        errors.append(
            f"{purpose}: artifact has non-finite JSON value {str(exc)!r}"
        )
    except RecursionError:
        errors.append(f"{purpose}: artifact has invalid JSON nesting")
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{purpose}: artifact is not valid JSON")
    else:
        if not isinstance(artifact, (dict, list)):
            errors.append(f"{purpose}: artifact JSON root must be an object or array")
    return errors


def validate_external_receipt(
    *,
    task_id: str,
    evidence_value: str,
    resolved_path: Path,
    root: Path,
    receipt_schema: dict[str, Any] | None,
    readback_contract: dict[str, Any],
) -> list[str]:
    """Validate one typed receipt and bind it to the completed planning task."""
    prefix = f"task {task_id} external receipt {evidence_value}"
    if receipt_schema is None:
        return [f"{prefix}: receipt schema is unavailable"]
    receipt_errors: list[str] = []
    receipt = load_json_object(
        resolved_path,
        receipt_errors,
        max_bytes=EXTERNAL_RECEIPT_MAX_BYTES,
        label=evidence_value,
    )
    if receipt is None:
        return [f"{prefix}: {error}" for error in receipt_errors]
    errors = [
        f"{prefix}: {error}"
        for error in validate_json_schema(receipt, receipt_schema)
    ]
    if receipt.get("$schema") != EXTERNAL_RECEIPT_SCHEMA_REF:
        errors.append(
            f"{prefix}: $schema must be {EXTERNAL_RECEIPT_SCHEMA_REF!r}"
        )
    if receipt.get("task_id") != task_id:
        errors.append(
            f"{prefix}: task_id {receipt.get('task_id')!r} does not match {task_id!r}"
        )
    if receipt.get("contract_id") != readback_contract.get("contract_id"):
        errors.append(
            f"{prefix}: contract_id {receipt.get('contract_id')!r} does not match "
            f"{readback_contract.get('contract_id')!r}"
        )
    if receipt.get("kind") != readback_contract.get("kind"):
        errors.append(
            f"{prefix}: kind {receipt.get('kind')!r} does not match "
            f"{readback_contract.get('kind')!r}"
        )
    readback = receipt.get("readback")
    sessions = readback.get("sessions") if isinstance(readback, dict) else None
    minimum_sessions = readback_contract.get("minimum_sessions")
    if (
        isinstance(minimum_sessions, int)
        and not isinstance(minimum_sessions, bool)
        and (
            not isinstance(sessions, list)
            or len(sessions) < minimum_sessions
        )
    ):
        errors.append(
            f"{prefix}: session record count "
            f"{len(sessions) if isinstance(sessions, list) else None!r} is below "
            f"required minimum {minimum_sessions}"
        )
    artifact_namespace = EVIDENCE_NAMESPACE / task_id / "artifacts"
    seen_artifact_paths: set[str] = set()
    if isinstance(sessions, list):
        session_ids = [
            session.get("session_id")
            for session in sessions
            if isinstance(session, dict) and isinstance(session.get("session_id"), str)
        ]
        for duplicate in sorted(duplicate_values(session_ids)):
            errors.append(f"{prefix}: duplicate session_id {duplicate!r}")
        for index, session in enumerate(sessions):
            if not isinstance(session, dict):
                continue
            session_id = session.get("session_id")
            if not isinstance(session_id, str):
                continue
            for field, suffix in (
                ("lifecycle", "lifecycle"),
                ("redaction_manifest", "redaction"),
                ("result", "result"),
            ):
                errors.extend(
                    validate_hashed_artifact(
                        task_id=task_id,
                        purpose=f"{prefix} session[{index}].{field}",
                        value=session.get(field),
                        expected_path=artifact_namespace
                        / f"{session_id}-{suffix}.json",
                        receipt_path=resolved_path,
                        root=root,
                        seen_paths=seen_artifact_paths,
                    )
                )
    if (
        readback_contract.get("fixture_required") is True
        and receipt.get("fixture_identity") == "not-applicable"
    ):
        errors.append(f"{prefix}: fixture_identity must be a SHA-256 digest")

    secret_scan = receipt.get("secret_scan")
    if isinstance(secret_scan, dict):
        errors.extend(
            validate_hashed_artifact(
                task_id=task_id,
                purpose=f"{prefix} secret_scan.result",
                value=secret_scan.get("result"),
                expected_path=artifact_namespace / "secret-scan.json",
                receipt_path=resolved_path,
                root=root,
                seen_paths=seen_artifact_paths,
            )
        )

    required_names = readback_contract.get("required_detail_names")
    details = receipt.get("details")
    if isinstance(required_names, list) and isinstance(details, list):
        detail_names = [
            detail.get("name")
            for detail in details
            if isinstance(detail, dict) and isinstance(detail.get("name"), str)
        ]
        for duplicate in sorted(duplicate_values(detail_names)):
            errors.append(f"{prefix}: duplicate detail name {duplicate!r}")
        missing = sorted(set(required_names) - set(detail_names))
        unexpected = sorted(set(detail_names) - set(required_names))
        if missing or unexpected or len(detail_names) != len(required_names):
            errors.append(
                f"{prefix}: detail names must exactly match descriptor: "
                f"missing {missing!r}, unexpected {unexpected!r}"
            )
        for index, detail in enumerate(details):
            if not isinstance(detail, dict):
                continue
            name = detail.get("name")
            if not isinstance(name, str):
                continue
            errors.extend(
                validate_hashed_artifact(
                    task_id=task_id,
                    purpose=f"{prefix} details[{index}] {name!r}",
                    value=detail,
                    expected_path=artifact_namespace / f"{name}.json",
                    receipt_path=resolved_path,
                    root=root,
                    seen_paths=seen_artifact_paths,
                )
            )
    return cap_validation_errors(errors)


def split_markdown_table_row(line: str) -> list[str] | None:
    """Split one pipe-delimited row without treating escaped pipes as separators."""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    cells: list[str] = []
    current: list[str] = []
    inner = stripped[1:-1]
    index = 0
    while index < len(inner):
        character = inner[index]
        if character == "\\" and index + 1 < len(inner):
            current.extend((character, inner[index + 1]))
            index += 2
            continue
        if character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _inline_code_value(
    cell: str, *, field: str, row_number: int
) -> tuple[str | None, str | None]:
    if len(cell) < 3 or not cell.startswith("`") or not cell.endswith("`"):
        return None, f"roadmap table row {row_number} {field} must be one inline-code value"
    value = cell[1:-1]
    if not value or "`" in value:
        return None, f"roadmap table row {row_number} {field} must be one inline-code value"
    return value, None


def validate_roadmap_parity(sequence: dict[str, Any], roadmap: str) -> list[str]:
    """Validate the bounded normative roadmap projection against the sequence."""
    errors: list[str] = []
    begin_count = roadmap.count(ROADMAP_TABLE_BEGIN)
    end_count = roadmap.count(ROADMAP_TABLE_END)
    if begin_count != 1:
        errors.append(
            f"{ROADMAP_PATH.as_posix()}: expected exactly one normative table begin marker, "
            f"found {begin_count}"
        )
    if end_count != 1:
        errors.append(
            f"{ROADMAP_PATH.as_posix()}: expected exactly one normative table end marker, "
            f"found {end_count}"
        )
    if begin_count != 1 or end_count != 1:
        return errors

    begin_index = roadmap.index(ROADMAP_TABLE_BEGIN) + len(ROADMAP_TABLE_BEGIN)
    end_index = roadmap.index(ROADMAP_TABLE_END)
    if end_index <= begin_index:
        return [f"{ROADMAP_PATH.as_posix()}: normative table end marker precedes begin marker"]
    table = roadmap[begin_index:end_index]
    if len(table) > ROADMAP_TABLE_MAX_CHARS:
        return [
            f"{ROADMAP_PATH.as_posix()}: normative table exceeds "
            f"{ROADMAP_TABLE_MAX_CHARS} characters"
        ]
    lines = [line.strip() for line in table.splitlines() if line.strip()]
    if len(lines) > ROADMAP_TABLE_MAX_ROWS + 2:
        return [
            f"{ROADMAP_PATH.as_posix()}: normative table exceeds "
            f"{ROADMAP_TABLE_MAX_ROWS} task rows"
        ]
    for row_number, line in enumerate(lines, start=1):
        if len(line) > ROADMAP_TABLE_MAX_LINE_CHARS:
            errors.append(
                f"roadmap table row {row_number} exceeds "
                f"{ROADMAP_TABLE_MAX_LINE_CHARS} characters"
            )

    if len(lines) < 2:
        return [*errors, f"{ROADMAP_PATH.as_posix()}: normative table header is missing"]
    header = split_markdown_table_row(lines[0])
    separator = split_markdown_table_row(lines[1])
    if header != ROADMAP_TABLE_HEADER:
        errors.append(
            f"{ROADMAP_PATH.as_posix()}: normative table header must be "
            f"{' | '.join(ROADMAP_TABLE_HEADER)}"
        )
    if separator != ROADMAP_TABLE_SEPARATOR:
        errors.append(
            f"{ROADMAP_PATH.as_posix()}: normative table separator must contain five '---' cells"
        )

    roadmap_tasks: dict[str, dict[str, str]] = {}
    for row_number, line in enumerate(lines[2:], start=3):
        cells = split_markdown_table_row(line)
        if cells is None or len(cells) != 5:
            errors.append(f"roadmap table row {row_number} must contain exactly five cells")
            continue
        task_id, task_error = _inline_code_value(
            cells[0], field="Task ID", row_number=row_number
        )
        batch_id, batch_error = _inline_code_value(
            cells[2], field="Batch", row_number=row_number
        )
        status, status_error = _inline_code_value(
            cells[3], field="State", row_number=row_number
        )
        errors.extend(
            error for error in (task_error, batch_error, status_error) if error is not None
        )
        if task_id is None or batch_id is None or status is None:
            continue
        if task_id in roadmap_tasks:
            errors.append(f"roadmap table contains duplicate task {task_id}")
            continue
        roadmap_tasks[task_id] = {"batch": batch_id, "status": status}

    raw_tasks = sequence.get("tasks")
    if not isinstance(raw_tasks, list):
        errors.append("planning sequence tasks are unavailable for roadmap parity")
        return errors
    contract_tasks = {
        str(task["id"]): {"batch": str(task.get("batch")), "status": str(task.get("status"))}
        for task in raw_tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    missing = sorted(set(contract_tasks) - set(roadmap_tasks))
    extra = sorted(set(roadmap_tasks) - set(contract_tasks))
    if missing:
        errors.append("roadmap table is missing contract tasks: " + ", ".join(missing))
    if extra:
        errors.append("roadmap table contains unknown tasks: " + ", ".join(extra))
    for task_id in sorted(set(contract_tasks) & set(roadmap_tasks)):
        for field in ("batch", "status"):
            roadmap_value = roadmap_tasks[task_id][field]
            contract_value = contract_tasks[task_id][field]
            if roadmap_value != contract_value:
                errors.append(
                    f"roadmap task {task_id} {field} mismatch: "
                    f"roadmap {roadmap_value!r}, sequence {contract_value!r}"
                )

    frontier_lines = [
        line.strip()
        for line in roadmap.splitlines()
        if line.strip().startswith("Current frontier:")
    ]
    if len(frontier_lines) != 1:
        errors.append(
            f"{ROADMAP_PATH.as_posix()}: expected exactly one explicit Current frontier line, "
            f"found {len(frontier_lines)}"
        )
        return errors
    frontier_line = frontier_lines[0]
    match = re.fullmatch(r"Current frontier:\s*(.*?)\.", frontier_line)
    if match is None:
        errors.append(
            f"{ROADMAP_PATH.as_posix()}: Current frontier must end with a period"
        )
        return errors
    frontier_text = match.group(1)
    frontier: list[str] = []
    if frontier_text:
        for cell in frontier_text.split(","):
            value, error = _inline_code_value(
                cell.strip(), field="Current frontier", row_number=0
            )
            if error is not None:
                errors.append(
                    f"{ROADMAP_PATH.as_posix()}: Current frontier entries must be inline-code values"
                )
                frontier = []
                break
            if value is not None:
                frontier.append(value)
    expected_frontier = sequence.get("current_frontier")
    if isinstance(expected_frontier, list) and frontier != expected_frontier:
        errors.append(
            f"roadmap current frontier mismatch: roadmap {frontier!r}, "
            f"sequence {expected_frontier!r}"
        )
    return errors


def validate_sequence_semantics(
    sequence: dict[str, Any],
    root: Path,
    *,
    receipt_schema: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    raw_tasks = sequence.get("tasks")
    raw_batches = sequence.get("batches")
    frontier = sequence.get("current_frontier")
    if not isinstance(raw_tasks, list) or not isinstance(raw_batches, list) or not isinstance(frontier, list):
        return ["planning sequence shape is unavailable for semantic validation"]
    tasks = [item for item in raw_tasks if isinstance(item, dict) and isinstance(item.get("id"), str)]
    batches = [item for item in raw_batches if isinstance(item, dict) and isinstance(item.get("id"), str)]
    task_ids = [str(item["id"]) for item in tasks]
    batch_ids = [str(item["id"]) for item in batches]
    for duplicate in sorted(duplicate_values(task_ids)):
        errors.append(f"duplicate task id: {duplicate}")
    for duplicate in sorted(duplicate_values(batch_ids)):
        errors.append(f"duplicate batch id: {duplicate}")
    task_map = {str(item["id"]): item for item in tasks}
    batch_map = {str(item["id"]): item for item in batches}

    task_graph: dict[str, list[str]] = {}
    membership: dict[str, list[str]] = {task_id: [] for task_id in task_map}
    for batch_id, batch in batch_map.items():
        dependencies = batch.get("depends_on", [])
        if isinstance(dependencies, list):
            for dependency in dependencies:
                if dependency not in batch_map:
                    errors.append(f"batch {batch_id} depends on unknown batch {dependency}")
        members = batch.get("tasks", [])
        if isinstance(members, list):
            for task_id in members:
                if task_id not in task_map:
                    errors.append(f"batch {batch_id} contains unknown task {task_id}")
                else:
                    membership[task_id].append(batch_id)
    batch_graph = {
        batch_id: [item for item in batch.get("depends_on", []) if isinstance(item, str)]
        for batch_id, batch in batch_map.items()
    }
    readback_contract_ids: list[str] = []

    for task_id, task in task_map.items():
        batch_id = task.get("batch")
        if batch_id not in batch_map:
            errors.append(f"task {task_id} references unknown batch {batch_id}")
        if membership.get(task_id) != [batch_id]:
            errors.append(f"task {task_id} must appear exactly once in its declared batch")
        dependencies = [item for item in task.get("depends_on", []) if isinstance(item, str)]
        task_graph[task_id] = dependencies
        for dependency in dependencies:
            if dependency not in task_map:
                errors.append(f"task {task_id} depends on unknown task {dependency}")
                continue
            dependency_batch = task_map[dependency].get("batch")
            if (
                batch_id in batch_map
                and dependency_batch in batch_map
                and not dependency_reachable(
                    batch_graph, str(batch_id), str(dependency_batch)
                )
            ):
                errors.append(
                    f"task {task_id} in batch {batch_id} depends on task {dependency} "
                    f"in unreachable batch {dependency_batch}"
                )
        evidence = task.get("evidence", [])
        status = task.get("status")
        external_readback_required = task.get("external_readback_required") is True
        readback_contract = task.get("external_readback_contract")
        if external_readback_required:
            if not isinstance(readback_contract, dict):
                errors.append(
                    f"task {task_id} requires an external_readback_contract descriptor"
                )
            else:
                contract_id = readback_contract.get("contract_id")
                if isinstance(contract_id, str):
                    readback_contract_ids.append(contract_id)
        elif readback_contract is not None:
            errors.append(
                f"task {task_id} must not define external_readback_contract when "
                "external_readback_required is false"
            )
        if status == "complete":
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"complete task {task_id} must have non-empty evidence")
            for dependency in dependencies:
                dependency_task = task_map.get(dependency)
                if dependency_task is not None and dependency_task.get("status") != "complete":
                    errors.append(
                        f"complete task {task_id} has incomplete dependency {dependency}"
                    )
        if status == "future" and evidence != []:
            errors.append(f"future task {task_id} must have empty evidence")
        resolved_evidence: dict[str, Path] = {}
        if isinstance(evidence, list):
            for value in evidence:
                if not isinstance(value, str):
                    continue
                resolved, path_errors = validate_evidence_path(task_id, value, root)
                errors.extend(path_errors)
                if resolved is not None:
                    resolved_evidence[value] = resolved
        if status == "complete" and external_readback_required:
            valid_receipt = False
            receipt_candidates = [
                value
                for value in resolved_evidence
                if is_external_receipt_path(task_id, value)
            ]
            for value in receipt_candidates:
                if not isinstance(readback_contract, dict):
                    continue
                receipt_errors = validate_external_receipt(
                    task_id=task_id,
                    evidence_value=value,
                    resolved_path=resolved_evidence[value],
                    root=root,
                    receipt_schema=receipt_schema,
                    readback_contract=readback_contract,
                )
                errors.extend(receipt_errors)
                if not receipt_errors:
                    valid_receipt = True
            if not valid_receipt:
                errors.append(
                    f"complete task {task_id} requires a valid task-bound external-readback "
                    f"receipt under {EVIDENCE_NAMESPACE.as_posix()}/{task_id}/"
                )

    for duplicate in sorted(duplicate_values(readback_contract_ids)):
        errors.append(f"duplicate external readback contract_id: {duplicate}")

    for task_id, task in task_map.items():
        status = task.get("status")
        batch_id = task.get("batch")
        if status not in {"in_progress", "complete"} or batch_id not in batch_map:
            continue
        for predecessor_batch_id in sorted(
            transitive_dependencies(batch_graph, str(batch_id))
        ):
            predecessor_batch = batch_map.get(predecessor_batch_id)
            if predecessor_batch is None:
                continue
            predecessor_tasks = predecessor_batch.get("tasks", [])
            if not isinstance(predecessor_tasks, list):
                continue
            for predecessor_task_id in predecessor_tasks:
                predecessor_task = task_map.get(predecessor_task_id)
                if (
                    predecessor_task is not None
                    and predecessor_task.get("status") != "complete"
                ):
                    errors.append(
                        f"task {task_id} cannot be {status} until predecessor batch "
                        f"{predecessor_batch_id} task {predecessor_task_id} is complete"
                    )

    task_cycle = dependency_cycle(task_graph)
    if task_cycle:
        errors.append("task dependency cycle: " + " -> ".join(task_cycle))
    batch_cycle = dependency_cycle(batch_graph)
    if batch_cycle:
        errors.append("batch dependency cycle: " + " -> ".join(batch_cycle))

    in_progress_tasks = [
        task_id for task_id in task_ids if task_map[task_id].get("status") == "in_progress"
    ]
    frontier_ids = [task_id for task_id in frontier if isinstance(task_id, str)]
    missing_frontier = sorted(set(in_progress_tasks) - set(frontier_ids))
    stray_frontier = sorted(set(frontier_ids) - set(in_progress_tasks))
    if missing_frontier or stray_frontier:
        errors.append(
            "current_frontier must exactly match all in_progress tasks: "
            f"missing {missing_frontier!r}, non-in_progress {stray_frontier!r}"
        )

    for task_id in frontier:
        task = task_map.get(task_id)
        if task is None:
            errors.append(f"frontier references unknown task {task_id}")
            continue
        if task.get("status") != "in_progress":
            errors.append(f"frontier task {task_id} must be in_progress")
        for dependency in task_graph.get(task_id, []):
            if dependency in task_map and task_map[dependency].get("status") != "complete":
                errors.append(f"frontier task {task_id} has incomplete dependency {dependency}")
    return cap_validation_errors(errors)


def validate_planning_contract(root: Path) -> list[str]:
    planning = root / PLANNING_DIR
    errors: list[str] = []
    sequence = load_json_object(
        planning / SEQUENCE_NAME, errors, max_bytes=SEQUENCE_MAX_BYTES
    )
    schema = load_json_object(
        planning / SCHEMA_NAME, errors, max_bytes=SEQUENCE_SCHEMA_MAX_BYTES
    )
    receipt_schema = load_json_object(
        planning / EXTERNAL_RECEIPT_SCHEMA_NAME,
        errors,
        max_bytes=EXTERNAL_RECEIPT_SCHEMA_MAX_BYTES,
    )
    ledger = load_json_object(
        planning / LEDGER_NAME, errors, max_bytes=LEDGER_MAX_BYTES
    )
    if sequence is not None and schema is not None:
        schema_subset_errors = validate_schema_subset(schema, SCHEMA_NAME)
        errors.extend(schema_subset_errors)
        sequence_schema_errors = (
            [] if schema_subset_errors else validate_json_schema(sequence, schema)
        )
        errors.extend(sequence_schema_errors)
        if not schema_subset_errors and not sequence_schema_errors:
            receipt_schema_subset_errors = (
                validate_schema_subset(
                    receipt_schema, EXTERNAL_RECEIPT_SCHEMA_NAME
                )
                if receipt_schema is not None
                else []
            )
            errors.extend(receipt_schema_subset_errors)
            errors.extend(
                validate_sequence_semantics(
                    sequence,
                    root,
                    receipt_schema=(
                        receipt_schema
                        if not receipt_schema_subset_errors
                        else None
                    ),
                )
            )
            roadmap_path = root / ROADMAP_PATH
            roadmap = read_bounded_utf8(
                roadmap_path,
                errors,
                max_bytes=ROADMAP_MAX_BYTES,
                label=ROADMAP_PATH.as_posix(),
            )
            if roadmap is not None:
                errors.extend(validate_roadmap_parity(sequence, roadmap))
    if ledger is not None:
        expected_keys = {"contract_version", "updated_at", "entries"}
        if set(ledger) != expected_keys:
            errors.append("planning ledger must contain only contract_version, updated_at, and entries")
        if not isinstance(ledger.get("contract_version"), int) or isinstance(ledger.get("contract_version"), bool):
            errors.append("planning ledger contract_version must be an integer")
        if sequence is not None and ledger.get("contract_version") != sequence.get("contract_version"):
            errors.append("planning ledger and sequence contract versions must match")
        entries = ledger.get("entries")
        if not isinstance(entries, list):
            errors.append("planning ledger entries must be an array")
        elif len(entries) > 512:
            errors.append("planning ledger entries must contain at most 512 items")
        updated_at = ledger.get("updated_at")
        if not isinstance(updated_at, str):
            errors.append("planning ledger updated_at must be a date string")
        else:
            if len(updated_at) > 10:
                errors.append("planning ledger updated_at exceeds 10 characters")
            try:
                parsed = date.fromisoformat(updated_at)
            except ValueError:
                errors.append("planning ledger updated_at must be an ISO date")
            else:
                if parsed.isoformat() != updated_at:
                    errors.append(
                        "planning ledger updated_at must use canonical YYYY-MM-DD"
                    )
    return cap_validation_errors(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="Repository root. Defaults to this repo.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)
    root = repo_root(args.root)
    errors = validate_planning_contract(root)
    if args.json:
        print(json.dumps(errors, indent=2))
    elif errors:
        print("Planning contract validation failed:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Planning contract validation passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
