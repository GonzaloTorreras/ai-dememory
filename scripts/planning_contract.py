#!/usr/bin/env python3
"""Validate the normative public planning schema, DAG, frontier, and evidence paths."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from memorylib import repo_root


PLANNING_DIR = Path("contracts/planning")
SEQUENCE_NAME = "v3-execution-sequence.json"
SCHEMA_NAME = "v3-execution-sequence.schema.json"
LEDGER_NAME = "v3-execution-ledger.json"


def load_json_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path.as_posix()}: missing")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{path.as_posix()}: invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path.as_posix()}: root must be an object")
        return None
    return value


def validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate the strict JSON-Schema subset used by the checked-in contract."""
    errors: list[str] = []
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
        if isinstance(properties, dict):
            for name, child_schema in properties.items():
                if name in value and isinstance(child_schema, dict):
                    errors.extend(validate_json_schema(value[name], child_schema, f"{path}.{name}"))

    if isinstance(value, list):
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_json_schema(item, item_schema, f"{path}[{index}]"))

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            errors.append(f"{path}: string is shorter than {minimum_length}")
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
    return errors


def duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def dependency_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    visited: set[str] = set()
    active: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in active:
            start = active.index(node)
            return [*active[start:], node]
        if node in visited:
            return None
        active.append(node)
        for dependency in graph.get(node, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        active.pop()
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
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


def validate_sequence_semantics(sequence: dict[str, Any], root: Path) -> list[str]:
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
        if isinstance(evidence, list):
            for value in evidence:
                if not isinstance(value, str):
                    continue
                path = PurePosixPath(value)
                if path.is_absolute() or ".." in path.parts:
                    errors.append(f"task {task_id} has unsafe evidence path {value!r}")
                elif not (root / Path(*path.parts)).exists():
                    errors.append(f"task {task_id} evidence path does not exist: {value}")

    task_cycle = dependency_cycle(task_graph)
    if task_cycle:
        errors.append("task dependency cycle: " + " -> ".join(task_cycle))
    batch_cycle = dependency_cycle(batch_graph)
    if batch_cycle:
        errors.append("batch dependency cycle: " + " -> ".join(batch_cycle))

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
    return errors


def validate_planning_contract(root: Path) -> list[str]:
    planning = root / PLANNING_DIR
    errors: list[str] = []
    sequence = load_json_object(planning / SEQUENCE_NAME, errors)
    schema = load_json_object(planning / SCHEMA_NAME, errors)
    ledger = load_json_object(planning / LEDGER_NAME, errors)
    if sequence is not None and schema is not None:
        errors.extend(validate_json_schema(sequence, schema))
        errors.extend(validate_sequence_semantics(sequence, root))
    if ledger is not None:
        expected_keys = {"contract_version", "updated_at", "entries"}
        if set(ledger) != expected_keys:
            errors.append("planning ledger must contain only contract_version, updated_at, and entries")
        if not isinstance(ledger.get("contract_version"), int) or isinstance(ledger.get("contract_version"), bool):
            errors.append("planning ledger contract_version must be an integer")
        if sequence is not None and ledger.get("contract_version") != sequence.get("contract_version"):
            errors.append("planning ledger and sequence contract versions must match")
        if not isinstance(ledger.get("entries"), list):
            errors.append("planning ledger entries must be an array")
        updated_at = ledger.get("updated_at")
        if not isinstance(updated_at, str):
            errors.append("planning ledger updated_at must be a date string")
        else:
            try:
                date.fromisoformat(updated_at)
            except ValueError:
                errors.append("planning ledger updated_at must be an ISO date")
    return errors


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
